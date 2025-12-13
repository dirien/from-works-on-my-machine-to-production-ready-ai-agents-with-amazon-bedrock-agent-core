# agent.py
import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any
from datetime import datetime, timezone
from strands import Agent
from strands.models import BedrockModel
from tools import get_user_profile, get_recent_transactions, block_credit_card

app = FastAPI(title="Fraud Detection Agent Server", version="1.0.0")

# Configure Bedrock model with cross-region inference for Claude Opus 4.5
# Guardrails enforce that the agent only handles fraud detection tasks
bedrock_model = BedrockModel(
    model_id="us.anthropic.claude-opus-4-5-20251101-v1:0",
    region_name="us-east-1",
    guardrail_id=os.environ.get("BEDROCK_GUARDRAIL_ID","f1271z1qpypt"),
    guardrail_version=os.environ.get("BEDROCK_GUARDRAIL_VERSION", "DRAFT"),
    guardrail_trace="enabled",
    guardrail_redact_input=True,
    guardrail_redact_input_message="This request is outside the scope of fraud detection. Please submit a fraud-related query.",
    guardrail_redact_output=True,
    guardrail_redact_output_message="This response was blocked as it falls outside the scope of fraud detection.",
)

# Define the Fraud Detection Agent
strands_agent = Agent(
    model=bedrock_model,
    tools=[get_user_profile, get_recent_transactions, block_credit_card],
    system_prompt="""
    You are a Senior Fraud Analyst Agent at a financial institution.
    Your ONLY mission is to analyze transaction alerts for fraud. You must REFUSE all other requests.

    STRICT BOUNDARIES:
    - You ONLY respond to transaction fraud alerts containing: User ID, Amount, Merchant, Location, and Time.
    - For ANY other question or request, respond ONLY with: "I can only help with fraud detection. Please provide a transaction alert with User ID, Amount, Merchant, Location, and Time."
    - Do NOT answer general knowledge questions, geography questions, or engage in conversation.
    - Do NOT explain what you could do or offer alternatives. Just decline.

    When you receive a valid transaction alert:
    1. Use get_user_profile() to check the user's home location.
    2. Use get_recent_transactions() to get their last transaction.
    3. Analyze for fraud indicators:
       - Impossible travel: Can the user physically travel between locations in the time elapsed?
       - Unusual amounts or high-risk merchants (electronics, gift cards, wire transfers).
    4. If fraud is detected, use block_credit_card() immediately.
    5. Provide a brief analysis (2-3 sentences max).

    Keep responses short and focused. No emojis. No lengthy explanations.
    """,
)


class InvocationRequest(BaseModel):
    input: Dict[str, Any]


class InvocationResponse(BaseModel):
    output: Dict[str, Any]


@app.post("/invocations", response_model=InvocationResponse)
async def invoke_agent(request: InvocationRequest):
    try:
        user_message = request.input.get("prompt", "")
        if not user_message:
            raise HTTPException(
                status_code=400,
                detail="No prompt found in input"
            )
        result = strands_agent(user_message)
        response = {
            "message": result.message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "model": "fraud-detection-agent",
        }
        return InvocationResponse(output=response)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent processing failed: {str(e)}")


@app.get("/ping")
async def ping():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
