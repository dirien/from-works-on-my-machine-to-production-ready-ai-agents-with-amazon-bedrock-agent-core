"""Invoke the Advanced Fraud Detection Agent with Memory and MCP Gateway on Bedrock AgentCore"""

import boto3
import json
import sys
import uuid
import time
import subprocess


def get_pulumi_outputs() -> dict:
    """Get Pulumi stack outputs for Gateway configuration."""
    try:
        result = subprocess.run(
            ["pulumi", "stack", "output", "--json", "--show-secrets"],
            cwd="infra",
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(result.stdout)
    except Exception as e:
        print(f"[WARNING] Could not get Pulumi outputs: {e}")
        return {}


def invoke_agent(
    agent_runtime_arn: str,
    prompt: str,
    actor_id: str = None,
    session_id: str = None,
    gateway_config: dict = None
) -> dict:
    """Invoke the agent with a given prompt, actor_id, session_id, and optional gateway config."""
    client = boto3.client("bedrock-agentcore", region_name="us-east-1")

    # Generate default IDs if not provided
    if not actor_id:
        actor_id = "default_actor"
    if not session_id:
        session_id = str(uuid.uuid4()).replace("-", "") + str(uuid.uuid4()).replace("-", "")[:10]

    payload_data = {
        "input": {
            "prompt": prompt,
            "actor_id": actor_id,
            "session_id": session_id,
        }
    }

    # Add gateway config if provided
    if gateway_config:
        payload_data["input"]["gateway_config"] = gateway_config

    payload = json.dumps(payload_data)

    response = client.invoke_agent_runtime(
        agentRuntimeArn=agent_runtime_arn,
        runtimeSessionId=session_id,
        payload=payload,
        qualifier="DEFAULT",
    )

    response_body = response["response"].read()
    response_data = json.loads(response_body)
    return response_data


def generate_session_id() -> str:
    """Generate a unique session ID (min 33 characters required by AgentCore)."""
    return f"session_{uuid.uuid4().hex}{uuid.uuid4().hex[:10]}"


def run_demo_scenario(agent_runtime_arn: str):
    """Run a comprehensive demo showing short-term memory (same session)."""

    print("=" * 70)
    print("FRAUD DETECTION DEMO - SHORT-TERM MEMORY (Same Session)")
    print("=" * 70)
    print("This demo shows short-term memory within the SAME session.")
    print("For long-term memory demo, use: python invoke_agent.py <arn> longterm")
    print("For MCP Gateway demo, use: python invoke_agent.py <arn> gateway")
    print("=" * 70)

    # Generate unique session IDs for different users (min 33 characters required)
    john_session = generate_session_id()
    jane_session = generate_session_id()
    alice_session = generate_session_id()

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

        # Scenario 3: John Doe - Another suspicious transaction (same session - short-term memory)
        {
            "name": "John Doe - Follow-up Transaction (Short-term Memory Test)",
            "actor_id": "user_123",
            "session_id": john_session,
            "prompt": """ALERT: New Transaction Attempt
User ID: user_123
Amount: $500
Merchant: Gift Card Kiosk
Location: Tokyo, Japan
Time: 09:20""",
            "expected": "FRAUD - card should already be blocked from previous alert (SHORT-TERM MEMORY)",
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
            "name": "Jane Smith - Second Normal Transaction",
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

    results = run_scenarios(agent_runtime_arn, scenarios)

    # Summary
    print("\n" + "=" * 70)
    print("SHORT-TERM MEMORY DEMO SUMMARY")
    print("=" * 70)
    for result in results:
        status_icon = "OK" if result["status"] == "SUCCESS" else "FAIL"
        print(f"[{status_icon}] {result['scenario']}")

    return results


def generate_demo_user_ids(fresh: bool = False) -> dict:
    """Generate user IDs for demo. If fresh=True, generate unique actor IDs to avoid memory interference.

    Note: We use different actor_ids for memory isolation but keep the same user IDs in prompts
    because the mock tools only recognize user_123, user_321, user_456.
    """
    if fresh:
        # Generate unique actor IDs with timestamp to avoid interference from previous runs
        # The actor_id is used for memory storage, while the prompt still uses known user IDs
        timestamp = int(time.time())
        return {
            "john": {"actor_id": f"demo_john_{timestamp}", "user_id": "user_123"},
            "alice": {"actor_id": f"demo_alice_{timestamp}", "user_id": "user_321"},
            "jane": {"actor_id": f"demo_jane_{timestamp}", "user_id": "user_456"},
            "bob": {"actor_id": f"demo_bob_{timestamp}", "user_id": "user_789"},
        }
    else:
        # Use fixed IDs (may have existing long-term memory from previous runs)
        return {
            "john": {"actor_id": "user_123", "user_id": "user_123"},
            "alice": {"actor_id": "user_321", "user_id": "user_321"},
            "jane": {"actor_id": "user_456", "user_id": "user_456"},
            "bob": {"actor_id": "user_789", "user_id": "user_789"},
        }


def run_longterm_demo(agent_runtime_arn: str, fresh: bool = False):
    """Run a demo showing long-term memory across DIFFERENT sessions."""

    # Generate user IDs (fresh or fixed)
    user_ids = generate_demo_user_ids(fresh)

    print("=" * 70)
    print("FRAUD DETECTION DEMO - LONG-TERM MEMORY (Cross-Session)")
    print("=" * 70)
    print("This demo shows long-term memory across DIFFERENT sessions.")
    print("The agent should remember facts about users from previous sessions.")
    if fresh:
        print(f"\n*** FRESH MODE: Using unique actor IDs to avoid memory interference ***")
        print(f"    John actor_id: {user_ids['john']['actor_id']} (user_id: {user_ids['john']['user_id']})")
        print(f"    Alice actor_id: {user_ids['alice']['actor_id']} (user_id: {user_ids['alice']['user_id']})")
        print(f"    Jane actor_id: {user_ids['jane']['actor_id']} (user_id: {user_ids['jane']['user_id']})")
    else:
        print(f"\n*** STANDARD MODE: Using fixed actor IDs (may have existing memory) ***")
        print("    Tip: Use 'longterm-fresh' mode for clean demo runs")
    print("=" * 70)

    # Phase 1: Initial fraud detection (creates long-term memory facts)
    print("\n" + "=" * 70)
    print("PHASE 1: INITIAL FRAUD DETECTION")
    print("These interactions create long-term memory facts about users.")
    print("=" * 70)

    phase1_scenarios = [
        {
            "name": "John Doe - Initial Fraud (Card Blocked)",
            "actor_id": user_ids["john"]["actor_id"],
            "session_id": generate_session_id(),  # New session
            "prompt": f"""ALERT: New Transaction Attempt
User ID: {user_ids["john"]["user_id"]}
Amount: $2000
Merchant: Electronics Store
Location: Tokyo, Japan
Time: 09:15""",
            "expected": "FRAUD DETECTED - card will be blocked, creating long-term memory fact",
        },
        {
            "name": "Alice Chen - Initial Fraud (Card Blocked)",
            "actor_id": user_ids["alice"]["actor_id"],
            "session_id": generate_session_id(),  # New session
            "prompt": f"""ALERT: New Transaction Attempt
User ID: {user_ids["alice"]["user_id"]}
Amount: $3500
Merchant: Jewelry Store
Location: Sydney, Australia
Time: 10:30""",
            "expected": "FRAUD DETECTED - card will be blocked, creating long-term memory fact",
        },
    ]

    phase1_results = run_scenarios(agent_runtime_arn, phase1_scenarios)

    # Wait for memory extraction to process
    print("\n" + "=" * 70)
    print("WAITING FOR LONG-TERM MEMORY EXTRACTION...")
    print("The semantic strategy needs time to process conversations into facts.")
    print("Waiting 30 seconds...")
    print("=" * 70)
    time.sleep(30)

    # Phase 2: New sessions - should retrieve long-term memory facts
    print("\n" + "=" * 70)
    print("PHASE 2: NEW SESSIONS - LONG-TERM MEMORY RETRIEVAL")
    print("These are COMPLETELY NEW sessions. The agent should remember")
    print("fraud-related facts about users from Phase 1.")
    print("=" * 70)

    phase2_scenarios = [
        {
            "name": "John Doe - NEW SESSION (Long-term Memory Test)",
            "actor_id": user_ids["john"]["actor_id"],
            "session_id": generate_session_id(),  # DIFFERENT session
            "prompt": f"""ALERT: New Transaction Attempt
User ID: {user_ids["john"]["user_id"]}
Amount: $800
Merchant: Online Store
Location: Paris, France
Time: 14:00""",
            "expected": "CARD ALREADY BLOCKED - should recall from LONG-TERM MEMORY that card was blocked",
        },
        {
            "name": "Alice Chen - NEW SESSION (Long-term Memory Test)",
            "actor_id": user_ids["alice"]["actor_id"],
            "session_id": generate_session_id(),  # DIFFERENT session
            "prompt": f"""ALERT: New Transaction Attempt
User ID: {user_ids["alice"]["user_id"]}
Amount: $1200
Merchant: Department Store
Location: Singapore
Time: 16:00""",
            "expected": "CARD ALREADY BLOCKED - should recall from LONG-TERM MEMORY that card was blocked",
        },
        {
            "name": "Jane Smith - NEW SESSION (No Long-term Memory)",
            "actor_id": user_ids["jane"]["actor_id"],
            "session_id": generate_session_id(),  # New session
            "prompt": f"""ALERT: New Transaction Attempt
User ID: {user_ids["jane"]["user_id"]}
Amount: $200
Merchant: Grocery Store
Location: New York, USA
Time: 18:00""",
            "expected": "NO FRAUD - Jane has no fraud history in long-term memory",
        },
    ]

    phase2_results = run_scenarios(agent_runtime_arn, phase2_scenarios)

    # Summary
    print("\n" + "=" * 70)
    print("LONG-TERM MEMORY DEMO SUMMARY")
    print("=" * 70)
    print("\nPHASE 1 - Initial Fraud Detection:")
    for result in phase1_results:
        status_icon = "OK" if result["status"] == "SUCCESS" else "FAIL"
        print(f"  [{status_icon}] {result['scenario']}")

    print("\nPHASE 2 - Long-term Memory Retrieval:")
    for result in phase2_results:
        status_icon = "OK" if result["status"] == "SUCCESS" else "FAIL"
        long_term_facts = result.get("response", {}).get("output", {}).get("long_term_facts_retrieved", 0)
        print(f"  [{status_icon}] {result['scenario']} (Long-term facts: {long_term_facts})")

    return {"phase1": phase1_results, "phase2": phase2_results}


def run_gateway_demo(agent_runtime_arn: str, fresh: bool = False):
    """Run a demo showing MCP Gateway integration with Risk Scoring Service.

    This demo showcases 6 diverse fraud scenarios that use both local tools
    and MCP Gateway tools for comprehensive fraud detection.
    """

    # Get Gateway config from Pulumi outputs
    print("=" * 70)
    print("LOADING MCP GATEWAY CONFIGURATION...")
    print("=" * 70)

    outputs = get_pulumi_outputs()
    gateway_config = None

    if outputs.get("gateway_url"):
        gateway_config = {
            "gateway_url": outputs.get("gateway_url"),
            "token_endpoint": outputs.get("gateway_token_endpoint"),
            "client_id": outputs.get("gateway_client_id"),
            "client_secret": outputs.get("gateway_client_secret"),
            "scope": outputs.get("gateway_scope"),
        }
        print(f"Gateway URL: {gateway_config['gateway_url']}")
        print(f"Token Endpoint: {gateway_config['token_endpoint']}")
        print(f"Scope: {gateway_config['scope']}")
        print("MCP Gateway configuration loaded successfully!")
    else:
        print("[WARNING] Gateway configuration not found in Pulumi outputs.")
        print("         The demo will run with local tools only.")
        print("         Deploy with 'pulumi up' to enable Gateway features.")

    # Generate user IDs (fresh or fixed)
    user_ids = generate_demo_user_ids(fresh)

    print("\n" + "=" * 70)
    print("FRAUD DETECTION DEMO - MCP GATEWAY INTEGRATION")
    print("=" * 70)
    print("This demo shows the MCP Gateway Risk Scoring Service in action.")
    print("The agent uses BOTH local tools and MCP Gateway tools:")
    print("")
    print("LOCAL TOOLS:")
    print("  - get_user_profile: User details and home location")
    print("  - get_recent_transactions: Last known transaction")
    print("  - block_credit_card: Block card and create ticket")
    print("")
    print("MCP GATEWAY TOOLS (via Risk Scoring Service):")
    print("  - calculate_risk_score: Fraud risk score 0-100")
    print("  - get_fraud_indicators: Known fraud indicators")
    print("  - check_merchant_reputation: Merchant risk rating")
    if fresh:
        print(f"\n*** FRESH MODE: Using unique actor IDs ***")
    print("=" * 70)

    # 6 Diverse Fraud Scenarios
    scenarios = [
        # Scenario 1: HIGH-RISK MERCHANT
        {
            "name": "1. HIGH-RISK MERCHANT - Jane at CryptoExchange123",
            "actor_id": user_ids["jane"]["actor_id"],
            "session_id": generate_session_id(),
            "gateway_config": gateway_config,
            "prompt": f"""ALERT: New Transaction Attempt
User ID: {user_ids["jane"]["user_id"]}
Amount: $5000
Merchant: CryptoExchange123
Location: New York, USA
Time: 10:00

Please analyze this transaction using all available tools including risk scoring.""",
            "expected": "HIGH RISK - CryptoExchange123 is a high-risk merchant (check_merchant_reputation)",
        },

        # Scenario 2: VELOCITY ATTACK (multiple rapid transactions)
        {
            "name": "2. VELOCITY ATTACK - Bob's Rapid Transactions",
            "actor_id": user_ids["bob"]["actor_id"],
            "session_id": generate_session_id(),
            "gateway_config": gateway_config,
            "prompt": f"""ALERT: New Transaction Attempt
User ID: {user_ids["bob"]["user_id"]}
Amount: $999
Merchant: Gaming TopUp Store
Location: Berlin, Germany
Time: 08:35

Note: This is the 5th transaction in the last 10 minutes for this user.
Please check fraud indicators and risk score.""",
            "expected": "HIGH RISK - Bob has velocity indicators (get_fraud_indicators)",
        },

        # Scenario 3: AMOUNT ANOMALY (10x typical spend)
        {
            "name": "3. AMOUNT ANOMALY - Alice's Large Purchase",
            "actor_id": user_ids["alice"]["actor_id"],
            "session_id": generate_session_id(),
            "gateway_config": gateway_config,
            "prompt": f"""ALERT: New Transaction Attempt
User ID: {user_ids["alice"]["user_id"]}
Amount: $8500
Merchant: LuxuryOutlet Online
Location: Singapore
Time: 11:00

This amount is much higher than typical for this user.
Please calculate risk score and check merchant.""",
            "expected": "HIGH RISK - Amount anomaly + high-risk merchant (calculate_risk_score)",
        },

        # Scenario 4: KNOWN FRAUD PATTERNS
        {
            "name": "4. KNOWN FRAUD PATTERNS - John's Indicator Check",
            "actor_id": user_ids["john"]["actor_id"],
            "session_id": generate_session_id(),
            "gateway_config": gateway_config,
            "prompt": f"""ALERT: New Transaction Attempt
User ID: {user_ids["john"]["user_id"]}
Amount: $300
Merchant: Overseas Electronics
Location: London, UK
Time: 12:00

This user has had previous alerts. Check their fraud indicators.""",
            "expected": "MEDIUM RISK - John has existing fraud indicators",
        },

        # Scenario 5: COMBINED SIGNALS (impossible travel + high-risk)
        {
            "name": "5. COMBINED SIGNALS - Alice's Multi-Factor Fraud",
            "actor_id": user_ids["alice"]["actor_id"],
            "session_id": generate_session_id(),
            "gateway_config": gateway_config,
            "prompt": f"""ALERT: New Transaction Attempt
User ID: {user_ids["alice"]["user_id"]}
Amount: $2500
Merchant: QuickCashAdvance
Location: Los Angeles, USA
Time: 11:30

User was just in Singapore 30 minutes ago!
Check ALL risk factors.""",
            "expected": "DEFINITE FRAUD - Impossible travel + high-risk merchant + amount anomaly",
        },

        # Scenario 6: CLEAN TRANSACTION (all clear)
        {
            "name": "6. CLEAN TRANSACTION - Jane's Normal Purchase",
            "actor_id": user_ids["jane"]["actor_id"],
            "session_id": generate_session_id(),
            "gateway_config": gateway_config,
            "prompt": f"""ALERT: New Transaction Attempt
User ID: {user_ids["jane"]["user_id"]}
Amount: $89
Merchant: Whole Foods
Location: New York, USA
Time: 18:30

Please analyze this transaction for fraud using all available tools.""",
            "expected": "NO FRAUD - Low-risk merchant, normal amount, home location",
        },
    ]

    results = run_scenarios_with_gateway(agent_runtime_arn, scenarios)

    # Summary
    print("\n" + "=" * 70)
    print("MCP GATEWAY DEMO SUMMARY")
    print("=" * 70)
    print("")
    for result in results:
        status_icon = "OK" if result["status"] == "SUCCESS" else "FAIL"
        mcp_enabled = result.get("response", {}).get("output", {}).get("mcp_gateway_enabled", False)
        mcp_tools = result.get("response", {}).get("output", {}).get("mcp_tools_count", 0)
        gateway_status = f"Gateway: YES ({mcp_tools} tools)" if mcp_enabled else "Gateway: NO"
        print(f"[{status_icon}] {result['scenario']}")
        print(f"     {gateway_status}")

    return results


def run_scenarios(agent_runtime_arn: str, scenarios: list) -> list:
    """Run a list of scenarios and return results (without gateway)."""
    results = []
    for i, scenario in enumerate(scenarios, 1):
        print(f"\n{'=' * 70}")
        print(f"SCENARIO {i}: {scenario['name']}")
        print(f"Expected: {scenario['expected']}")
        print(f"Actor ID: {scenario['actor_id']}")
        print(f"Session ID: {scenario['session_id'][:40]}...")
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
            print("\nWaiting 3 seconds before next scenario...")
            time.sleep(3)

    return results


def run_scenarios_with_gateway(agent_runtime_arn: str, scenarios: list) -> list:
    """Run a list of scenarios with optional Gateway config and return results."""
    results = []
    for i, scenario in enumerate(scenarios, 1):
        print(f"\n{'=' * 70}")
        print(f"SCENARIO {i}: {scenario['name']}")
        print(f"Expected: {scenario['expected']}")
        print(f"Actor ID: {scenario['actor_id']}")
        print(f"Session ID: {scenario['session_id'][:40]}...")
        gateway_status = "ENABLED" if scenario.get("gateway_config") else "DISABLED"
        print(f"MCP Gateway: {gateway_status}")
        print("-" * 70)
        print(f"Prompt:\n{scenario['prompt']}")
        print("-" * 70)

        try:
            response = invoke_agent(
                agent_runtime_arn,
                scenario['prompt'],
                actor_id=scenario['actor_id'],
                session_id=scenario['session_id'],
                gateway_config=scenario.get('gateway_config'),
            )
            print("Agent Response:")
            print(json.dumps(response, indent=2))
            results.append({"scenario": scenario['name'], "status": "SUCCESS", "response": response})
        except Exception as e:
            print(f"Error: {e}")
            results.append({"scenario": scenario['name'], "status": "ERROR", "error": str(e)})

        # Brief pause between scenarios
        if i < len(scenarios):
            print("\nWaiting 3 seconds before next scenario...")
            time.sleep(3)

    return results


def main():
    if len(sys.argv) < 2:
        print("Usage: python invoke_agent.py <agent_runtime_arn> [mode]")
        print("")
        print("Modes:")
        print("  demo           - Short-term memory demo (same session) - default")
        print("  longterm       - Long-term memory demo (cross-session, fixed user IDs)")
        print("  longterm-fresh - Long-term memory demo with FRESH user IDs")
        print("  gateway        - MCP Gateway demo (6 diverse fraud scenarios)")
        print("  gateway-fresh  - MCP Gateway demo with FRESH user IDs (recommended)")
        print("  single         - Run single fraud alert")
        print("")
        print("Examples:")
        print("  python invoke_agent.py arn:aws:... demo")
        print("  python invoke_agent.py arn:aws:... longterm")
        print("  python invoke_agent.py arn:aws:... longterm-fresh")
        print("  python invoke_agent.py arn:aws:... gateway        # MCP Gateway demo!")
        print("  python invoke_agent.py arn:aws:... gateway-fresh  # Best for live demos!")
        print("  python invoke_agent.py arn:aws:... single")
        sys.exit(1)

    agent_runtime_arn = sys.argv[1]
    mode = sys.argv[2] if len(sys.argv) > 2 else "demo"

    if mode == "demo":
        run_demo_scenario(agent_runtime_arn)
    elif mode == "longterm":
        run_longterm_demo(agent_runtime_arn, fresh=False)
    elif mode == "longterm-fresh":
        run_longterm_demo(agent_runtime_arn, fresh=True)
    elif mode == "gateway":
        run_gateway_demo(agent_runtime_arn, fresh=False)
    elif mode == "gateway-fresh":
        run_gateway_demo(agent_runtime_arn, fresh=True)
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
