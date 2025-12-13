# agent.py
import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any
from datetime import datetime, timezone
from strands import Agent
from strands.models import BedrockModel
from strands.hooks import AgentInitializedEvent, HookProvider, HookRegistry, MessageAddedEvent
from bedrock_agentcore.memory import MemoryClient
from tools import get_user_profile, get_recent_transactions, block_credit_card

app = FastAPI(title="Advanced Fraud Detection Agent Server", version="2.0.0")

# Configuration from environment
MEMORY_ID = os.environ.get("BEDROCK_MEMORY_ID")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
GUARDRAIL_ID = os.environ.get("BEDROCK_GUARDRAIL_ID", "f1271z1qpypt")
GUARDRAIL_VERSION = os.environ.get("BEDROCK_GUARDRAIL_VERSION", "DRAFT")

# Initialize memory client if memory ID is configured
memory_client = None
if MEMORY_ID:
    memory_client = MemoryClient(region_name=AWS_REGION)

# Configure Bedrock model with cross-region inference for Claude Opus 4.5
bedrock_model = BedrockModel(
    model_id="us.anthropic.claude-opus-4-5-20251101-v1:0",
    region_name=AWS_REGION,
    guardrail_id=GUARDRAIL_ID,
    guardrail_version=GUARDRAIL_VERSION,
    guardrail_trace="enabled",
    guardrail_redact_input=True,
    guardrail_redact_input_message="This request is outside the scope of fraud detection. Please submit a fraud-related query.",
    guardrail_redact_output=True,
    guardrail_redact_output_message="This response was blocked as it falls outside the scope of fraud detection.",
)

# Base system prompt for the fraud detection agent
BASE_SYSTEM_PROMPT = """
You are a Senior Fraud Analyst Agent at a financial institution.
Your ONLY mission is to analyze transaction alerts for fraud. You must REFUSE all other requests.

STRICT BOUNDARIES:
- You ONLY respond to transaction fraud alerts containing: User ID, Amount, Merchant, Location, and Time.
- For ANY other question or request, respond ONLY with: "I can only help with fraud detection. Please provide a transaction alert with User ID, Amount, Merchant, Location, and Time."
- Do NOT answer general knowledge questions, geography questions, or engage in conversation.
- Do NOT explain what you could do or offer alternatives. Just decline.

MEMORY CAPABILITIES:
- You have access to SHORT-TERM MEMORY containing recent interactions within this session.
- IMPORTANT: Before blocking a card, check if the conversation history shows the card was already blocked.
- If you see a previous message mentioning "BLOCKED" or "Card blocked" for a user, inform them the card is ALREADY BLOCKED and provide the existing ticket ID.

When you receive a valid transaction alert:
1. FIRST: Check the conversation history below for any previous actions on this user's card.
2. If the card was already blocked in this session, respond: "Card for [user] is ALREADY BLOCKED (Ticket: [ticket_id]). No further action needed."
3. If NOT already blocked:
   a. Use get_user_profile() to check the user's home location.
   b. Use get_recent_transactions() to get their last transaction.
   c. Analyze for fraud indicators (impossible travel, unusual amounts, high-risk merchants).
   d. If fraud is detected, use block_credit_card() immediately.
4. Provide a brief analysis (2-3 sentences max).

Keep responses short and focused. No lengthy explanations.
"""


def build_system_prompt_with_context(recent_context: list) -> str:
    """Build system prompt including recent conversation context from memory."""
    if not recent_context:
        return BASE_SYSTEM_PROMPT + "\n\nCONVERSATION HISTORY: (No previous interactions in this session)"

    # Format the recent context for the system prompt
    context_lines = ["\n\nCONVERSATION HISTORY FROM THIS SESSION:"]
    try:
        for i, turn in enumerate(recent_context, 1):
            try:
                if isinstance(turn, dict):
                    role = turn.get("role", "unknown")
                    content = turn.get("content", "")
                    if not content:
                        content = turn.get("text", str(turn))
                elif isinstance(turn, (list, tuple)) and len(turn) >= 2:
                    content, role = str(turn[0]), str(turn[1])
                else:
                    content = str(turn)
                    role = "unknown"
                # Truncate long content
                content = str(content)
                if len(content) > 300:
                    content = content[:300] + "..."
                context_lines.append(f"[{i}] {role.upper()}: {content}")
            except Exception as inner_e:
                print(f"[MEMORY] Error processing turn {i}: {inner_e}")
                context_lines.append(f"[{i}] UNKNOWN: (error processing turn)")
    except Exception as e:
        print(f"[MEMORY] Error building context: {e}")
        return BASE_SYSTEM_PROMPT + "\n\nCONVERSATION HISTORY: (Error loading history)"

    return BASE_SYSTEM_PROMPT + "\n".join(context_lines)


class MemoryHookProvider(HookProvider):
    """Hook provider for AgentCore short-term memory integration."""

    def __init__(self, memory_client: MemoryClient, memory_id: str, actor_id: str, session_id: str):
        self.memory_client = memory_client
        self.memory_id = memory_id
        self.actor_id = actor_id
        self.session_id = session_id
        self.recent_context = []

    def on_agent_initialized(self, event: AgentInitializedEvent):
        """Called when agent initializes - log memory configuration."""
        print(f"[MEMORY] Agent initialized with memory_id={self.memory_id}, actor={self.actor_id}, session={self.session_id}")

    def on_message_added(self, event: MessageAddedEvent):
        """Store message to memory when added."""
        try:
            message = event.message
            role = message.get("role", "user")
            content = message.get("content", "")

            # Extract text content if it's a list
            if isinstance(content, list):
                text_parts = [c.get("text", "") for c in content if isinstance(c, dict) and "text" in c]
                content = " ".join(text_parts)

            if content:
                print(f"[MEMORY] Storing {role} message to short-term memory (length: {len(content)} chars)")
                self.memory_client.create_event(
                    memory_id=self.memory_id,
                    actor_id=self.actor_id,
                    session_id=self.session_id,
                    messages=[(content, role)]
                )
                print(f"[MEMORY] Successfully stored message to memory")
        except Exception as e:
            print(f"[MEMORY] Failed to store message to memory: {e}")

    def register_hooks(self, registry: HookRegistry):
        """Register hooks with the agent."""
        registry.add_callback(AgentInitializedEvent, self.on_agent_initialized)
        registry.add_callback(MessageAddedEvent, self.on_message_added)


class InvocationRequest(BaseModel):
    input: Dict[str, Any]


class InvocationResponse(BaseModel):
    output: Dict[str, Any]


def create_agent_with_memory(actor_id: str, session_id: str) -> Agent:
    """Create an agent with AgentCore short-term memory."""
    hooks = []

    # Set up memory hooks for storing conversations
    if memory_client and MEMORY_ID:
        try:
            print(f"[MEMORY] Setting up memory for actor={actor_id}, session={session_id}")
            memory_hook = MemoryHookProvider(
                memory_client=memory_client,
                memory_id=MEMORY_ID,
                actor_id=actor_id,
                session_id=session_id
            )
            hooks.append(memory_hook)
            print(f"[MEMORY] Memory hooks configured successfully")
        except Exception as e:
            print(f"[MEMORY] Failed to create memory hook: {type(e).__name__}: {e}")

    # Use base system prompt (memory retrieval happens in hooks)
    system_prompt = BASE_SYSTEM_PROMPT + "\n\nCONVERSATION HISTORY: Memory is enabled for this session."
    print(f"[AGENT] System prompt length: {len(system_prompt)} chars")

    return Agent(
        model=bedrock_model,
        tools=[get_user_profile, get_recent_transactions, block_credit_card],
        system_prompt=system_prompt,
        hooks=hooks,
        state={"actor_id": actor_id, "session_id": session_id}
    )


@app.post("/invocations", response_model=InvocationResponse)
async def invoke_agent(request: InvocationRequest):
    try:
        user_message = request.input.get("prompt", "")
        actor_id = request.input.get("actor_id", "default_actor")
        session_id = request.input.get("session_id", f"session_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}")

        if not user_message:
            raise HTTPException(
                status_code=400,
                detail="No prompt found in input"
            )

        # Create agent with memory for this request
        agent = create_agent_with_memory(actor_id, session_id)

        result = agent(user_message)
        response = {
            "message": result.message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "model": "fraud-detection-agent-advanced",
            "actor_id": actor_id,
            "session_id": session_id,
            "memory_enabled": memory_client is not None and MEMORY_ID is not None,
        }
        return InvocationResponse(output=response)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent processing failed: {str(e)}")


@app.get("/ping")
async def ping():
    return {
        "status": "healthy",
        "memory_enabled": memory_client is not None and MEMORY_ID is not None,
        "memory_id": MEMORY_ID,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
