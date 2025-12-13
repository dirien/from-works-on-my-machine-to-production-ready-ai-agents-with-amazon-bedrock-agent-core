"""Invoke the deployed Fraud Detection Agent on Bedrock AgentCore"""

import boto3
import json
import sys
import uuid


def invoke_agent(agent_runtime_arn: str, prompt: str) -> dict:
    """Invoke the agent with a given prompt."""
    client = boto3.client("bedrock-agentcore", region_name="us-east-1")

    payload = json.dumps({"input": {"prompt": prompt}})

    # Generate a unique session ID (min 33 characters required)
    session_id = str(uuid.uuid4()).replace("-", "") + str(uuid.uuid4()).replace("-", "")[:10]

    response = client.invoke_agent_runtime(
        agentRuntimeArn=agent_runtime_arn,
        runtimeSessionId=session_id,
        payload=payload,
        qualifier="DEFAULT",
    )

    response_body = response["response"].read()
    response_data = json.loads(response_body)
    return response_data


def main():
    if len(sys.argv) < 2:
        print("Usage: python invoke_agent.py <agent_runtime_arn> [prompt]")
        print("")
        print("If no prompt is provided, a sample fraud alert will be used.")
        sys.exit(1)

    agent_runtime_arn = sys.argv[1]

    # Default fraud alert prompt
    default_prompt = """ALERT: New Transaction Attempt
User ID: user_123
Amount: $2000
Merchant: Electronics Store
Location: Tokyo, Japan
Time: 09:15"""

    prompt = sys.argv[2] if len(sys.argv) > 2 else default_prompt

    print(f"Sending prompt to agent...")
    print(f"Prompt: {prompt}")
    print("-" * 50)

    try:
        response = invoke_agent(agent_runtime_arn, prompt)
        print("Agent Response:")
        print(json.dumps(response, indent=2))
    except Exception as e:
        print(f"Error invoking agent: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
