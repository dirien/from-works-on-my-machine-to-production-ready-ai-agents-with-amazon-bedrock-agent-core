# From "Works on My Machine" to Production-Ready: AI Agents with Amazon Bedrock AgentCore

This repository demonstrates the journey of building and deploying AI agents—from a local prototype running on your laptop to a fully production-ready deployment on AWS. Using a real-world fraud detection scenario, you'll see how the same agent concept evolves through three stages of maturity.

## The Story

Imagine you're a financial institution that needs to detect fraudulent credit card transactions in real-time. A customer's card is used in London at 9:00 AM, and then suddenly in Tokyo at 9:15 AM. That's physically impossible—the agent needs to catch this and block the card immediately.

This repository shows you how to build that agent, starting with a quick prototype on your machine and ending with a production system that includes persistent memory, distributed tool access, and full observability.

## The Three Stages

### Stage 1: Local Prototype

Get your idea working quickly. No infrastructure, no deployment—just Python code and an LLM.

**What it does:** A fraud detection agent that analyzes transactions for impossible travel, unusual amounts, and suspicious merchants. When it detects fraud, it blocks the card.

**Where:** `local-prototype/`

### Stage 2: Basic Production Deployment

Deploy your agent to AWS with proper infrastructure, guardrails, and API access.

**What it adds:**
- Containerized agent running on Amazon Bedrock AgentCore
- Content filtering via Bedrock Guardrails
- Infrastructure as Code with Pulumi

**Where:** `basic-bedrock-deployment/`

### Stage 3: Advanced Production Deployment

Add memory, external tools via MCP Gateway, and full observability.

**What it adds:**
- **Short-term memory:** The agent remembers what happened earlier in the conversation
- **Long-term memory:** Facts persist across sessions (e.g., "John's card was blocked last week")
- **MCP Gateway:** Access external risk-scoring tools without hardcoding integrations
- **Observability:** CloudWatch logs and X-Ray distributed tracing

**Where:** `advanced-bedrock-deployment/`

---

## Prerequisites

Before running any demo, you'll need:

- **Python 3.11+** installed
- **[uv](https://github.com/astral-sh/uv)** - Fast Python package manager
- **AWS credentials** with access to Amazon Bedrock
- **[Pulumi](https://www.pulumi.com/)** - For deploying infrastructure
- **[Pulumi ESC](https://www.pulumi.com/docs/esc/)** - For credential management (configured as `pulumi-idp/auth`)
- **Docker** - For building container images (production deployments only)

---

## Stage 1: Run the Local Prototype

The fastest way to see the agent in action. Everything runs on your machine.

```bash
cd local-prototype
./run.sh
```

This script:
1. Installs Python dependencies with `uv`
2. Loads AWS credentials from Pulumi ESC
3. Runs a fraud detection simulation

**What you'll see:**

The agent receives a transaction alert for John Doe—a $2,000 purchase at an electronics store in Tokyo, just 15 minutes after his last transaction in London. The agent:

1. Retrieves John's profile (home: London, UK)
2. Checks his recent transaction history (last transaction: London at 9:00 AM)
3. Calculates that Tokyo is ~9,500km away—impossible to travel in 15 minutes
4. Blocks the card and creates a fraud ticket

```
ALERT: New Transaction Attempt
User ID: user_123
Amount: $2000
Merchant: Electronics Store
Location: Tokyo, Japan
Time: 09:15

[ACTION] BLOCKING CARD for user_123. REASON: Impossible travel detected...
```

### How it works

The agent uses three simple tools defined in `tools.py`:

| Tool | Purpose |
|------|---------|
| `get_user_profile()` | Retrieves user's home location and account status |
| `get_recent_transactions()` | Gets the last known transaction time and location |
| `block_credit_card()` | Blocks the card and creates a support ticket |

The agent's system prompt in `agent.py` instructs it to analyze transactions for fraud indicators and take protective action when necessary.

---

## Stage 2: Deploy to AWS (Basic)

Deploy the same agent to Amazon Bedrock AgentCore with production infrastructure.

### Deploy the infrastructure

```bash
cd basic-bedrock-deployment/infra
uv sync
uv run pulumi up
```

This creates:
- **ECR repository** for your agent container
- **Docker image** automatically built and pushed
- **IAM roles** with least-privilege permissions
- **Bedrock Guardrails** to keep the agent focused on fraud detection
- **AgentCore Runtime** to host your containerized agent

### Test the deployed agent

```bash
cd basic-bedrock-deployment
./test.sh
```

The test script automatically fetches the agent ARN from Pulumi outputs and invokes the agent with the same fraud scenario.

### What's different from local?

| Local | Production |
|-------|------------|
| Runs in your terminal | Runs in a managed container |
| Direct Bedrock API calls | API-accessible endpoint |
| No guardrails | Content filtering enforced |
| Manual credential handling | IAM-based authentication |

### Clean up

```bash
cd basic-bedrock-deployment/infra
uv run pulumi destroy
```

---

## Stage 3: Deploy with Memory and MCP Gateway (Advanced)

This is where it gets interesting. The agent now has memory across conversations and can access external tools through the MCP Gateway.

### Deploy the infrastructure

```bash
cd advanced-bedrock-deployment/infra
uv sync
uv run pulumi up
```

This creates everything from Stage 2, plus:

**Memory infrastructure:**
- **AgentCore Memory** with 30-day retention
- **Semantic extraction strategy** that pulls fraud-related facts from conversations
- Per-user memory namespaces (`/fraud-detection/users/{userId}`)

**MCP Gateway infrastructure:**
- **Cognito User Pools** for authentication
- **OAuth2 credential provider** for secure tool access
- **MCP Risk Server** with additional fraud analysis tools
- **Gateway Target** connecting everything together

**Observability:**
- **CloudWatch Logs** for all components
- **X-Ray tracing** across the entire request flow

### Demo 1: Short-term memory (same session)

See how the agent remembers what happened earlier in the conversation.

```bash
cd advanced-bedrock-deployment
./test.sh demo
```

This runs 5 scenarios in a single session:

1. **John Doe** - Impossible travel detected → Card blocked
2. **Jane Smith** - Normal transaction at home → Allowed
3. **John Doe again** - Agent remembers his card is already blocked
4. **Alice Chen** - Impossible travel detected → Card blocked
5. **Jane Smith again** - Still normal, still allowed

The key moment is scenario 3: when John has another suspicious transaction, the agent doesn't try to block the card again—it remembers it already did.

### Demo 2: Long-term memory (cross-session)

See how facts persist even when you start a new conversation.

```bash
cd advanced-bedrock-deployment
./test.sh longterm-fresh
```

This runs in two phases:

**Phase 1 (Session A):**
- John's card gets blocked for fraud
- Alice's card gets blocked for fraud
- Facts are extracted and stored to long-term memory

*30-second pause for semantic extraction*

**Phase 2 (Session B - completely new session):**
- John has a new transaction → Agent recalls "John's card was blocked" from memory
- Alice has a new transaction → Agent recalls "Alice's card was blocked" from memory
- Jane (no history) → Processed normally

The `-fresh` flag generates unique user IDs for each run, preventing interference from previous test data.

### Demo 3: MCP Gateway (external risk tools)

See how the agent accesses external risk-scoring services through the MCP Gateway.

```bash
cd advanced-bedrock-deployment
./test.sh gateway-fresh
```

This runs 6 scenarios using both local tools and MCP Gateway tools:

| Scenario | What's detected | Tools used |
|----------|-----------------|------------|
| Jane at CryptoExchange123 | High-risk merchant | `check_merchant_reputation` |
| Bob's rapid transactions | Velocity attack | `get_fraud_indicators` |
| Alice's 10x typical spend | Amount anomaly | `calculate_risk_score` |
| John's indicator check | Known fraud patterns | `get_fraud_indicators` |
| Alice - travel + merchant | Combined signals | All tools |
| Jane at Whole Foods | Clean transaction | All tools (no fraud) |

The MCP Risk Server provides three additional tools:

| Tool | Purpose |
|------|---------|
| `calculate_risk_score()` | Returns 0-100 risk score with contributing factors |
| `get_fraud_indicators()` | Retrieves known fraud indicators for a user |
| `check_merchant_reputation()` | Checks merchant risk rating and fraud history |

### Clean up

```bash
cd advanced-bedrock-deployment/infra
uv run pulumi destroy
```

---

## Understanding the Architecture

### Local prototype

```
┌─────────────┐     ┌─────────────┐
│ Your Script │────▶│ Strands SDK │────▶ Amazon Bedrock (Claude)
└─────────────┘     └─────────────┘
                           │
                    ┌──────┴──────┐
                    ▼             ▼
              Local Tools    Mock Database
```

### Basic production

```
┌──────────┐     ┌────────────────────┐     ┌─────────────────┐
│ API Call │────▶│ Bedrock AgentCore  │────▶│  Bedrock Model  │
└──────────┘     │    (Container)     │     │  (Claude Opus)  │
                 └────────────────────┘     └─────────────────┘
                          │
                   ┌──────┴──────┐
                   ▼             ▼
              Guardrails    Local Tools
```

### Advanced production

```
┌──────────┐     ┌────────────────────┐     ┌─────────────────┐
│ API Call │────▶│ Bedrock AgentCore  │────▶│  Bedrock Model  │
└──────────┘     │    (Container)     │     │  (Claude Opus)  │
                 └────────────────────┘     └─────────────────┘
                          │
           ┌──────────────┼──────────────┐
           ▼              ▼              ▼
      Local Tools    Memory API    MCP Gateway
           │              │              │
           │         ┌────┴────┐    ┌────┴────┐
           │         ▼         ▼    ▼         │
           │    Short-term  Long-term   Risk Server
           │     Memory     Memory     (FastMCP)
           │
    ┌──────┴──────┐
    ▼             ▼
CloudWatch     X-Ray
  Logs        Traces
```

---

## Key Technologies

| Technology | Purpose |
|------------|---------|
| [Strands SDK](https://github.com/strands-agents/strands) | AWS open-source agent framework |
| Amazon Bedrock | Claude Opus 4.5 model hosting |
| Amazon Bedrock AgentCore | Managed runtime for agent containers |
| Amazon Bedrock Guardrails | Content filtering and topic enforcement |
| AgentCore Memory | Short-term and long-term memory storage |
| AgentCore Gateway | MCP protocol gateway for tool discovery |
| [Model Context Protocol](https://modelcontextprotocol.io/) | Standard protocol for tool integration |
| [FastMCP](https://github.com/jlowin/fastmcp) | Python framework for building MCP servers |
| [Pulumi](https://www.pulumi.com/) | Infrastructure as Code |
| [Pulumi ESC](https://www.pulumi.com/docs/esc/) | Credential and secret management |
| [uv](https://github.com/astral-sh/uv) | Fast Python package manager |

---

## Tips for Live Demos

**Use fresh mode for repeatability:**

```bash
./test.sh longterm-fresh   # Unique IDs each run
./test.sh gateway-fresh    # Unique IDs each run
```

Long-term memory persists for 30 days. Without fresh mode, you might see "card already blocked" from previous test runs.

**Check Pulumi outputs:**

```bash
cd advanced-bedrock-deployment/infra
pulumi stack output --json
```

This shows all the ARNs, URLs, and IDs for your deployed resources.

**View logs in CloudWatch:**

After running a demo, check CloudWatch Logs in the AWS Console. Look for log groups starting with `/agentcore/` for agent, memory, gateway, and MCP server logs.

**Trace requests in X-Ray:**

X-Ray shows the full request flow across all components. This is invaluable for debugging and understanding latency.

---

## Troubleshooting

**"Could not select stack 'dev'"**

Run `uv run pulumi up` first to create the stack.

**"User not found in risk database"**

The MCP Risk Server has a fixed set of mock users. Use the predefined user IDs: `user_123` (John), `user_456` (Jane), `user_789` (Bob), `user_321` (Alice).

**Memory not persisting across sessions**

Long-term memory uses semantic extraction which runs asynchronously. Wait 30+ seconds between Phase 1 and Phase 2 of the longterm demo.

**Gateway authentication errors**

Ensure the Cognito client credentials are correctly configured. Check the Pulumi outputs for `gateway_client_id` and `gateway_client_secret`.

---

## License

This project is provided as a demonstration and learning resource.
