# agent.py
import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List
from datetime import datetime, timezone
from strands import Agent
from strands.models import BedrockModel
from strands.hooks import AgentInitializedEvent, HookProvider, HookRegistry, MessageAddedEvent, AfterInvocationEvent
from bedrock_agentcore.memory import MemoryClient
from tools import get_user_profile, get_recent_transactions, block_credit_card

app = FastAPI(title="Advanced Fraud Detection Agent Server", version="3.0.0")

# Configuration from environment
MEMORY_ID = os.environ.get("BEDROCK_MEMORY_ID")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
GUARDRAIL_ID = os.environ.get("BEDROCK_GUARDRAIL_ID", "f1271z1qpypt")
GUARDRAIL_VERSION = os.environ.get("BEDROCK_GUARDRAIL_VERSION", "DRAFT")

# Namespace for long-term memory - must match what's configured in Pulumi
LONG_TERM_MEMORY_NAMESPACE = "/fraud-detection/users/{actorId}"

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
- You have access to LONG-TERM MEMORY containing fraud-related facts about users from PREVIOUS SESSIONS.
- CRITICAL: Before blocking a card, check BOTH short-term and long-term memory for any record of the card being blocked.
- If you see ANY previous record mentioning "BLOCKED" or "Card blocked" for a user, inform them the card is ALREADY BLOCKED and provide the existing ticket ID.

When you receive a valid transaction alert:
1. FIRST: Check the LONG-TERM MEMORY CONTEXT section below for any facts about this user from previous sessions.
2. SECOND: Check the SHORT-TERM CONVERSATION HISTORY for recent actions in this session.
3. If the card was already blocked (in either memory), respond: "Card for [user] is ALREADY BLOCKED (Ticket: [ticket_id]). No further action needed."
4. If NOT already blocked:
   a. Use get_user_profile() to check the user's home location.
   b. Use get_recent_transactions() to get their last transaction.
   c. Analyze for fraud indicators (impossible travel, unusual amounts, high-risk merchants).
   d. If fraud is detected, use block_credit_card() immediately.
5. Provide a brief analysis (2-3 sentences max).

Keep responses short and focused. No lengthy explanations.
"""


def build_system_prompt_with_context(long_term_facts: List[str], short_term_context: list) -> str:
    """Build system prompt including both long-term facts and short-term conversation context."""
    prompt_parts = [BASE_SYSTEM_PROMPT]

    # Add long-term memory facts
    if long_term_facts:
        prompt_parts.append("\n\nLONG-TERM MEMORY CONTEXT (from previous sessions):")
        for i, fact in enumerate(long_term_facts, 1):
            prompt_parts.append(f"  [{i}] {fact}")
    else:
        prompt_parts.append("\n\nLONG-TERM MEMORY CONTEXT: (No facts from previous sessions)")

    # Add short-term conversation history
    if short_term_context:
        prompt_parts.append("\n\nSHORT-TERM CONVERSATION HISTORY (this session):")
        try:
            for i, turn in enumerate(short_term_context, 1):
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
                    prompt_parts.append(f"  [{i}] {role.upper()}: {content}")
                except Exception as inner_e:
                    print(f"[MEMORY] Error processing turn {i}: {inner_e}")
                    prompt_parts.append(f"  [{i}] UNKNOWN: (error processing turn)")
        except Exception as e:
            print(f"[MEMORY] Error building context: {e}")
            prompt_parts.append("  (Error loading history)")
    else:
        prompt_parts.append("\n\nSHORT-TERM CONVERSATION HISTORY: (No previous interactions in this session)")

    return "\n".join(prompt_parts)


class MemoryHookProvider(HookProvider):
    """Hook provider for AgentCore short-term and long-term memory integration."""

    def __init__(self, memory_client: MemoryClient, memory_id: str, actor_id: str, session_id: str):
        self.memory_client = memory_client
        self.memory_id = memory_id
        self.actor_id = actor_id
        self.session_id = session_id
        self.recent_context = []
        self.long_term_facts: List[str] = []
        self.last_user_message = None
        self.last_assistant_message = None

    def on_agent_initialized(self, event: AgentInitializedEvent):
        """Called when agent initializes - retrieve long-term memory facts."""
        print(f"[MEMORY] Agent initialized with memory_id={self.memory_id}, actor={self.actor_id}, session={self.session_id}")

        # Retrieve long-term memory facts for this user
        try:
            namespace = LONG_TERM_MEMORY_NAMESPACE.replace("{actorId}", self.actor_id)
            print(f"[LONG-TERM MEMORY] Retrieving facts from namespace: {namespace}")

            memories = self.memory_client.retrieve_memories(
                memory_id=self.memory_id,
                namespace=namespace,
                query=f"fraud detection facts for user {self.actor_id}"
            )

            if memories:
                for memory in memories:
                    # Extract the content from memory records
                    if hasattr(memory, 'content'):
                        self.long_term_facts.append(str(memory.content))
                    elif isinstance(memory, dict) and 'content' in memory:
                        self.long_term_facts.append(str(memory['content']))
                    elif isinstance(memory, str):
                        self.long_term_facts.append(memory)
                    else:
                        self.long_term_facts.append(str(memory))

                print(f"[LONG-TERM MEMORY] Retrieved {len(self.long_term_facts)} facts from long-term memory")
                for i, fact in enumerate(self.long_term_facts, 1):
                    print(f"  [{i}] {fact[:100]}...")
            else:
                print(f"[LONG-TERM MEMORY] No facts found for user {self.actor_id}")

        except Exception as e:
            print(f"[LONG-TERM MEMORY] Failed to retrieve long-term memory: {type(e).__name__}: {e}")

    def on_message_added(self, event: MessageAddedEvent):
        """Track messages for storing to memory after invocation."""
        try:
            message = event.message
            role = message.get("role", "user")
            content = message.get("content", "")

            # Extract text content if it's a list
            if isinstance(content, list):
                text_parts = [c.get("text", "") for c in content if isinstance(c, dict) and "text" in c]
                content = " ".join(text_parts)

            if content:
                if role == "user":
                    self.last_user_message = content
                    print(f"[MEMORY] Captured user message (length: {len(content)} chars)")
                elif role == "assistant":
                    self.last_assistant_message = content
                    print(f"[MEMORY] Captured assistant message (length: {len(content)} chars)")

        except Exception as e:
            print(f"[MEMORY] Failed to capture message: {e}")

    def on_after_invocation(self, event: AfterInvocationEvent):
        """Store conversation pair to memory after agent responds (for long-term extraction)."""
        try:
            if self.last_user_message and self.last_assistant_message:
                print(f"[MEMORY] Storing conversation pair to memory for long-term extraction")

                # Create event with both user and assistant messages
                # This will be processed by the semantic strategy for long-term fact extraction
                self.memory_client.create_event(
                    memory_id=self.memory_id,
                    actor_id=self.actor_id,
                    session_id=self.session_id,
                    messages=[
                        (self.last_user_message, "USER"),
                        (self.last_assistant_message, "ASSISTANT")
                    ]
                )
                print(f"[MEMORY] Successfully stored conversation to memory (will be processed for long-term facts)")

                # Clear for next invocation
                self.last_user_message = None
                self.last_assistant_message = None
            else:
                print(f"[MEMORY] No complete conversation pair to store")

        except Exception as e:
            print(f"[MEMORY] Failed to store conversation to memory: {type(e).__name__}: {e}")

    def get_long_term_facts(self) -> List[str]:
        """Return retrieved long-term memory facts."""
        return self.long_term_facts

    def register_hooks(self, registry: HookRegistry):
        """Register hooks with the agent."""
        registry.add_callback(AgentInitializedEvent, self.on_agent_initialized)
        registry.add_callback(MessageAddedEvent, self.on_message_added)
        registry.add_callback(AfterInvocationEvent, self.on_after_invocation)


class InvocationRequest(BaseModel):
    input: Dict[str, Any]


class InvocationResponse(BaseModel):
    output: Dict[str, Any]


def create_agent_with_memory(actor_id: str, session_id: str) -> tuple[Agent, MemoryHookProvider | None]:
    """Create an agent with AgentCore short-term and long-term memory."""
    hooks = []
    memory_hook = None
    long_term_facts = []

    # Set up memory hooks for storing conversations and retrieving long-term facts
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

            # Pre-retrieve long-term facts before agent initialization
            # (This happens again in the hook, but we need it for the system prompt)
            namespace = LONG_TERM_MEMORY_NAMESPACE.replace("{actorId}", actor_id)
            print(f"[LONG-TERM MEMORY] Pre-retrieving facts from namespace: {namespace}")
            try:
                memories = memory_client.retrieve_memories(
                    memory_id=MEMORY_ID,
                    namespace=namespace,
                    query=f"fraud detection facts for user {actor_id}"
                )
                if memories:
                    for memory in memories:
                        if hasattr(memory, 'content'):
                            long_term_facts.append(str(memory.content))
                        elif isinstance(memory, dict) and 'content' in memory:
                            long_term_facts.append(str(memory['content']))
                        elif isinstance(memory, str):
                            long_term_facts.append(memory)
                        else:
                            long_term_facts.append(str(memory))
                    print(f"[LONG-TERM MEMORY] Pre-retrieved {len(long_term_facts)} facts")
            except Exception as e:
                print(f"[LONG-TERM MEMORY] Pre-retrieval failed (will try again in hook): {e}")

            print(f"[MEMORY] Memory hooks configured successfully")
        except Exception as e:
            print(f"[MEMORY] Failed to create memory hook: {type(e).__name__}: {e}")

    # Build system prompt with long-term facts (short-term context is empty at start)
    system_prompt = build_system_prompt_with_context(long_term_facts, [])
    print(f"[AGENT] System prompt length: {len(system_prompt)} chars")
    print(f"[AGENT] Long-term facts included: {len(long_term_facts)}")

    agent = Agent(
        model=bedrock_model,
        tools=[get_user_profile, get_recent_transactions, block_credit_card],
        system_prompt=system_prompt,
        hooks=hooks,
        state={"actor_id": actor_id, "session_id": session_id}
    )

    return agent, memory_hook


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
        agent, memory_hook = create_agent_with_memory(actor_id, session_id)

        result = agent(user_message)

        # Get the number of long-term facts retrieved
        long_term_facts_count = len(memory_hook.get_long_term_facts()) if memory_hook else 0

        response = {
            "message": result.message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "model": "fraud-detection-agent-advanced-v3",
            "actor_id": actor_id,
            "session_id": session_id,
            "memory_enabled": memory_client is not None and MEMORY_ID is not None,
            "long_term_memory_enabled": True,
            "long_term_facts_retrieved": long_term_facts_count,
        }
        return InvocationResponse(output=response)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent processing failed: {str(e)}")


@app.get("/ping")
async def ping():
    return {
        "status": "healthy",
        "version": "3.0.0",
        "memory_enabled": memory_client is not None and MEMORY_ID is not None,
        "memory_id": MEMORY_ID,
        "long_term_memory_enabled": True,
        "long_term_memory_namespace": LONG_TERM_MEMORY_NAMESPACE,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
