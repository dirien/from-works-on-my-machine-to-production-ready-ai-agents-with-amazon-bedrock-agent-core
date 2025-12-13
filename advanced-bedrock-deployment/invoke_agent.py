"""Invoke the Advanced Fraud Detection Agent with Memory on Bedrock AgentCore"""

import boto3
import json
import sys
import uuid
import time


def invoke_agent(agent_runtime_arn: str, prompt: str, actor_id: str = None, session_id: str = None) -> dict:
    """Invoke the agent with a given prompt, actor_id, and session_id."""
    client = boto3.client("bedrock-agentcore", region_name="us-east-1")

    # Generate default IDs if not provided
    if not actor_id:
        actor_id = "default_actor"
    if not session_id:
        session_id = str(uuid.uuid4()).replace("-", "") + str(uuid.uuid4()).replace("-", "")[:10]

    payload = json.dumps({
        "input": {
            "prompt": prompt,
            "actor_id": actor_id,
            "session_id": session_id,
        }
    })

    response = client.invoke_agent_runtime(
        agentRuntimeArn=agent_runtime_arn,
        runtimeSessionId=session_id,
        payload=payload,
        qualifier="DEFAULT",
    )

    response_body = response["response"].read()
    response_data = json.loads(response_body)
    return response_data


def run_demo_scenario(agent_runtime_arn: str):
    """Run a comprehensive demo showing multiple users and memory features."""

    print("=" * 70)
    print("ADVANCED FRAUD DETECTION AGENT DEMO - AgentCore Memory")
    print("=" * 70)

    # Generate unique session IDs for different users (min 33 characters required)
    john_session = f"john_session_{uuid.uuid4().hex}{uuid.uuid4().hex[:10]}"
    jane_session = f"jane_session_{uuid.uuid4().hex}{uuid.uuid4().hex[:10]}"
    alice_session = f"alice_session_{uuid.uuid4().hex}{uuid.uuid4().hex[:10]}"

    scenarios = [
        # Scenario 1: John Doe - Impossible travel (FRAUD)
        {
            "name": "John Doe - Impossible Travel Detection",
            "actor_id": "user_123",
            "session_id": john_session,
            "prompt": """ALERT: New Transaction Attempt
User ID: user_123
Amount: $2000
Merchant: Electronics Store
Location: Tokyo, Japan
Time: 09:15""",
            "expected": "FRAUD - impossible travel from London to Tokyo in 15 minutes",
        },

        # Scenario 2: Jane Smith - Normal transaction (NO FRAUD)
        {
            "name": "Jane Smith - Normal Transaction",
            "actor_id": "user_456",
            "session_id": jane_session,
            "prompt": """ALERT: New Transaction Attempt
User ID: user_456
Amount: $150
Merchant: Department Store
Location: New York, USA
Time: 14:30""",
            "expected": "NO FRAUD - transaction at home location",
        },

        # Scenario 3: John Doe - Another suspicious transaction (same session - memory should recall)
        {
            "name": "John Doe - Follow-up Transaction (Memory Test)",
            "actor_id": "user_123",
            "session_id": john_session,
            "prompt": """ALERT: New Transaction Attempt
User ID: user_123
Amount: $500
Merchant: Gift Card Kiosk
Location: Tokyo, Japan
Time: 09:20""",
            "expected": "FRAUD - card should already be blocked from previous alert",
        },

        # Scenario 4: Alice Chen - Impossible travel (FRAUD)
        {
            "name": "Alice Chen - Impossible Travel Detection",
            "actor_id": "user_321",
            "session_id": alice_session,
            "prompt": """ALERT: New Transaction Attempt
User ID: user_321
Amount: $3500
Merchant: Jewelry Store
Location: Sydney, Australia
Time: 10:30""",
            "expected": "FRAUD - impossible travel from Singapore to Sydney in 30 minutes",
        },

        # Scenario 5: Jane Smith - Another normal transaction (same session)
        {
            "name": "Jane Smith - Second Normal Transaction (Memory Test)",
            "actor_id": "user_456",
            "session_id": jane_session,
            "prompt": """ALERT: New Transaction Attempt
User ID: user_456
Amount: $89
Merchant: Restaurant
Location: New York, USA
Time: 19:00""",
            "expected": "NO FRAUD - consistent with home location and user profile",
        },
    ]

    results = []
    for i, scenario in enumerate(scenarios, 1):
        print(f"\n{'=' * 70}")
        print(f"SCENARIO {i}: {scenario['name']}")
        print(f"Expected: {scenario['expected']}")
        print(f"Actor ID: {scenario['actor_id']}")
        print(f"Session ID: {scenario['session_id']}")
        print("-" * 70)
        print(f"Prompt:\n{scenario['prompt']}")
        print("-" * 70)

        try:
            response = invoke_agent(
                agent_runtime_arn,
                scenario['prompt'],
                actor_id=scenario['actor_id'],
                session_id=scenario['session_id'],
            )
            print("Agent Response:")
            print(json.dumps(response, indent=2))
            results.append({"scenario": scenario['name'], "status": "SUCCESS", "response": response})
        except Exception as e:
            print(f"Error: {e}")
            results.append({"scenario": scenario['name'], "status": "ERROR", "error": str(e)})

        # Brief pause between scenarios
        if i < len(scenarios):
            print("\nWaiting 2 seconds before next scenario...")
            time.sleep(2)

    # Summary
    print("\n" + "=" * 70)
    print("DEMO SUMMARY")
    print("=" * 70)
    for result in results:
        status_icon = "OK" if result["status"] == "SUCCESS" else "FAIL"
        print(f"[{status_icon}] {result['scenario']}")

    return results


def main():
    if len(sys.argv) < 2:
        print("Usage: python invoke_agent.py <agent_runtime_arn> [mode]")
        print("")
        print("Modes:")
        print("  demo    - Run comprehensive demo with multiple users (default)")
        print("  single  - Run single fraud alert (original behavior)")
        print("")
        print("Examples:")
        print("  python invoke_agent.py arn:aws:... demo")
        print("  python invoke_agent.py arn:aws:... single")
        sys.exit(1)

    agent_runtime_arn = sys.argv[1]
    mode = sys.argv[2] if len(sys.argv) > 2 else "demo"

    if mode == "demo":
        run_demo_scenario(agent_runtime_arn)
    else:
        # Single fraud alert (original behavior)
        default_prompt = """ALERT: New Transaction Attempt
User ID: user_123
Amount: $2000
Merchant: Electronics Store
Location: Tokyo, Japan
Time: 09:15"""

        prompt = sys.argv[3] if len(sys.argv) > 3 else default_prompt

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
