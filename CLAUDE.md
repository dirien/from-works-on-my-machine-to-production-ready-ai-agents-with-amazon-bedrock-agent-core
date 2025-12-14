# CLAUDE.md

This file provides guidance for Claude Code when working with this repository.

## Project Overview

This repository contains a fraud detection agent demo built with the Strands SDK and Amazon Bedrock. The project demonstrates multiple fraud detection patterns including:
- **Impossible Traveler**: Detecting fraudulent transactions based on physically impossible location changes
- **High-Risk Merchant**: Identifying transactions at risky merchants via MCP Gateway
- **Velocity Attack**: Detecting multiple rapid transactions
- **Amount Anomaly**: Flagging purchases outside typical spending patterns

## Repository Structure

```
├── local-prototype/              # Local Strands SDK agent implementation
│   ├── agent.py                  # Fraud detection agent with Claude Opus 4.5
│   ├── tools.py                  # Mock tools (get_user_profile, get_recent_transactions, block_credit_card)
│   ├── demo_simulation.py        # Demo runner script
│   ├── pyproject.toml            # Python dependencies (uv)
│   ├── run.sh                    # Execution script with Pulumi ESC
│   └── uv.lock                   # Locked dependencies
├── basic-bedrock-deployment/     # Basic production deployment to AWS Bedrock AgentCore
│   ├── fraud-detection-agent/    # Agent container code
│   │   ├── agent.py              # FastAPI-wrapped fraud detection agent
│   │   ├── tools.py              # Mock tools for fraud detection
│   │   ├── Dockerfile            # Container build for ARM64
│   │   ├── pyproject.toml        # Agent dependencies
│   │   └── uv.lock               # Locked dependencies
│   ├── infra/                    # Pulumi infrastructure
│   │   ├── __main__.py           # Pulumi program (ECR, IAM, Guardrails, AgentCore)
│   │   └── pyproject.toml        # Pulumi dependencies
│   ├── invoke_agent.py           # Script to invoke deployed agent
│   ├── test.sh                   # Test script with Pulumi ESC credentials
│   └── pyproject.toml            # Test script dependencies
├── advanced-bedrock-deployment/  # Advanced deployment with Memory & MCP Gateway
│   ├── fraud-detection-agent/    # Agent container code with memory & gateway integration
│   │   ├── agent.py              # FastAPI agent with memory hooks & MCP Gateway support
│   │   ├── tools.py              # Local tools with card blocking state tracking
│   │   ├── Dockerfile            # Container build for ARM64
│   │   ├── pyproject.toml        # Agent dependencies (bedrock-agentcore, mcp)
│   │   └── uv.lock               # Locked dependencies
│   ├── mcp-risk-server/          # MCP Risk Scoring Server (accessed via Gateway)
│   │   ├── server.py             # FastMCP server with risk tools
│   │   ├── Dockerfile            # Container build for ARM64
│   │   ├── pyproject.toml        # MCP server dependencies
│   │   └── uv.lock               # Locked dependencies
│   ├── infra/                    # Pulumi infrastructure with Memory, Gateway & CloudWatch
│   │   ├── __main__.py           # Pulumi program (Memory, Gateway, Cognito, OAuth2, etc.)
│   │   └── pyproject.toml        # Pulumi dependencies
│   ├── invoke_agent.py           # Multi-user demo script (memory & gateway demos)
│   └── pyproject.toml            # Test script dependencies
├── assets/                       # Presentation assets
├── CLAUDE.md                     # This file - Claude Code guidance
└── .gitignore
```

## Running the Local Demo

```bash
cd local-prototype
./run.sh
```

This uses `uv` for dependency management and `pulumi env run pulumi-idp/auth` for AWS credentials.

## Deploying to AWS Bedrock AgentCore

### Basic Deployment

```bash
cd basic-bedrock-deployment/infra
uv sync
uv run pulumi up
```

This deploys:
- ECR repository for the agent container
- Docker image built and pushed to ECR
- IAM roles and policies for AgentCore
- Bedrock Guardrails for fraud detection scope enforcement
- Bedrock AgentCore Agent Runtime

### Advanced Deployment (with Memory & MCP Gateway)

```bash
cd advanced-bedrock-deployment/infra
uv sync
uv run pulumi up
```

This deploys everything in the basic deployment plus:

**Memory Infrastructure:**
- **AgentCore Memory**: Memory storage with 30-day event expiry
- **Short-term Memory**: Conversation history within the same session
- **Long-term Memory**: Semantic extraction strategy for cross-session memory
  - Custom semantic strategy extracts fraud-related facts from conversations
  - Uses Claude Haiku for efficient fact extraction
  - Namespace: `/fraud-detection/users/{actorId}` for per-user isolation
- **Memory Hooks**: Strands SDK hooks for storing messages and retrieving long-term facts

**MCP Gateway Infrastructure:**
- **Cognito User Pool (Gateway)**: JWT authentication for Gateway access
- **Cognito User Pool (Runtime)**: OAuth2 authentication for Gateway→MCP Server
- **OAuth2 Credential Provider**: Manages Gateway outbound authentication
- **AgentCore Gateway**: MCP protocol gateway with semantic tool search
- **MCP Risk Server Runtime**: FastMCP server deployed to AgentCore
- **Gateway Target**: Connects Gateway to MCP Risk Server endpoint

**Observability:**
- **CloudWatch Logs**: Application logs for agent, memory, gateway, and MCP server
- **X-Ray Traces**: Distributed tracing for request flow across all components
- **OpenTelemetry**: Auto-instrumentation via AWS Distro for OpenTelemetry (ADOT)

## Testing the Deployed Agent

### Basic Test

```bash
cd basic-bedrock-deployment
./test.sh          # Automatically selects stack and fetches ARN
./test.sh --help   # Show usage
```

### Advanced Demo (Short-term Memory - Same Session)

```bash
cd advanced-bedrock-deployment
./test.sh              # Run default 'demo' mode (auto-fetches ARN)
./test.sh demo         # Explicit short-term memory demo
./test.sh --help       # Show all available demo modes
```

The short-term memory demo runs 5 scenarios within the SAME session:
1. **John Doe - Impossible Travel**: Transaction in Tokyo triggers fraud (card blocked)
2. **Jane Smith - Normal Transaction**: Transaction at home location (no fraud)
3. **John Doe - Follow-up Transaction**: Short-term memory recognizes card is ALREADY BLOCKED
4. **Alice Chen - Impossible Travel**: Transaction in Sydney triggers fraud (card blocked)
5. **Jane Smith - Second Transaction**: Consistent with home location (no fraud)

### Advanced Demo (Long-term Memory - Cross-Session)

```bash
cd advanced-bedrock-deployment
./test.sh longterm         # Long-term memory demo
./test.sh longterm-fresh   # Long-term memory with fresh IDs (recommended)
```

The long-term memory demo runs in 2 phases with DIFFERENT sessions:

**Phase 1 - Initial Fraud Detection:**
1. **John Doe - Initial Fraud**: Card blocked, fact stored to long-term memory
2. **Alice Chen - Initial Fraud**: Card blocked, fact stored to long-term memory

*Waits 30 seconds for semantic extraction to process*

**Phase 2 - New Sessions (Long-term Memory Retrieval):**
3. **John Doe - NEW SESSION**: Agent recalls from long-term memory that card is ALREADY BLOCKED
4. **Alice Chen - NEW SESSION**: Agent recalls from long-term memory that card is ALREADY BLOCKED
5. **Jane Smith - NEW SESSION**: No fraud history in long-term memory, normal processing

### Advanced Demo (MCP Gateway - Risk Scoring)

```bash
cd advanced-bedrock-deployment
./test.sh gateway         # MCP Gateway demo
./test.sh gateway-fresh   # MCP Gateway with fresh IDs (recommended)
```

The MCP Gateway demo runs 6 diverse fraud scenarios using both local tools and MCP Gateway tools:

1. **High-Risk Merchant**: Jane at CryptoExchange123 (uses `check_merchant_reputation`)
2. **Velocity Attack**: Bob's rapid transactions (uses `get_fraud_indicators`)
3. **Amount Anomaly**: Alice's 10x typical spend (uses `calculate_risk_score`)
4. **Known Fraud Patterns**: John's indicator check (uses `get_fraud_indicators`)
5. **Combined Signals**: Alice - impossible travel + high-risk merchant (all tools)
6. **Clean Transaction**: Jane's normal purchase at Whole Foods (all tools, no fraud)

### Demo Modes with Fresh IDs (Recommended for Live Demos)

```bash
cd advanced-bedrock-deployment
./test.sh longterm-fresh   # Long-term memory with fresh IDs
./test.sh gateway-fresh    # MCP Gateway with fresh IDs
```

**Why use fresh mode?**
- Old test runs store facts in long-term memory that persist for 30 days
- Without fresh mode, subsequent runs may see "card already blocked" from previous tests
- Fresh mode isolates each demo run with unique actor IDs (e.g., `demo_john_1765656257`)

## Key Technologies

- **Strands SDK** (`strands-agents`): AWS open-source agent framework
- **Amazon Bedrock**: Claude Opus 4.5 model (`us.anthropic.claude-opus-4-5-20251101-v1:0`)
- **Amazon Bedrock AgentCore**: Managed runtime for agent containers
- **Amazon Bedrock AgentCore Memory**: Memory storage for conversation history
  - Short-term memory: Raw conversation events within sessions
  - Long-term memory: Semantic extraction strategy for cross-session facts
- **Amazon Bedrock AgentCore Memory Strategy**: Custom semantic extraction
  - Uses Claude Haiku for efficient fact extraction and consolidation
  - Extracts fraud-related facts (card status, tickets, patterns)
- **Amazon Bedrock AgentCore Gateway**: MCP protocol gateway for tool discovery
  - JWT authentication via Cognito
  - OAuth2 credential provider for outbound auth
  - Semantic tool search for intelligent tool discovery
- **Amazon Bedrock Guardrails**: Content filtering and topic enforcement
- **Amazon CloudWatch**: Application logs for observability
- **AWS X-Ray**: Distributed tracing for request flow visualization
- **AWS Distro for OpenTelemetry (ADOT)**: Auto-instrumentation for agent tracing
- **Amazon Cognito**: OAuth2/JWT authentication for Gateway
- **Model Context Protocol (MCP)**: Standard protocol for tool integration
- **FastMCP**: Python framework for building MCP servers
- **Pulumi**: Infrastructure as Code for AWS resources
- **Pulumi ESC**: Credential management for AWS access
- **uv**: Python package manager
- **FastAPI**: Web framework for agent API endpoint

## Agent Architecture

The fraud agent uses two types of tools:

### Local Tools (Direct Access)
1. `get_user_profile()` - Retrieves user details and home location
2. `get_recent_transactions()` - Gets last known transaction
3. `block_credit_card()` - Blocks the card and creates a ticket

### MCP Gateway Tools (via Risk Scoring Service)
1. `calculate_risk_score()` - Returns risk score 0-100 with factors
2. `get_fraud_indicators()` - Gets known fraud indicators for a user
3. `check_merchant_reputation()` - Checks merchant risk rating and fraud history

## Commands

### Local Development
- `uv sync` - Install dependencies
- `uv run python demo_simulation.py` - Run demo (requires AWS credentials)
- `pulumi env run pulumi-idp/auth -- <command>` - Run with Pulumi ESC credentials

### Basic Production Deployment
- `cd basic-bedrock-deployment/infra && uv run pulumi up` - Deploy infrastructure
- `cd basic-bedrock-deployment && ./test.sh` - Test deployed agent
- `cd basic-bedrock-deployment/infra && uv run pulumi destroy` - Tear down infrastructure

### Advanced Production Deployment (Memory & MCP Gateway)
- `cd advanced-bedrock-deployment/infra && uv run pulumi up` - Deploy all infrastructure
- `cd advanced-bedrock-deployment && ./test.sh` - Short-term memory demo (auto-fetches ARN)
- `cd advanced-bedrock-deployment && ./test.sh longterm` - Long-term memory demo
- `cd advanced-bedrock-deployment && ./test.sh longterm-fresh` - Long-term memory (fresh IDs)
- `cd advanced-bedrock-deployment && ./test.sh gateway` - MCP Gateway demo
- `cd advanced-bedrock-deployment && ./test.sh gateway-fresh` - MCP Gateway (fresh IDs, recommended)
- `cd advanced-bedrock-deployment/infra && uv run pulumi destroy` - Tear down infrastructure

## Pulumi Stack Outputs

After deployment, the following outputs are available:

```bash
cd advanced-bedrock-deployment/infra
pulumi stack output --json
```

Key outputs include:
- `agent_runtime_arn` - ARN for invoking the fraud detection agent
- `gateway_url` - URL for the MCP Gateway
- `gateway_client_id` - Cognito client ID for Gateway access
- `gateway_client_secret` - Cognito client secret (sensitive)
- `mcp_server_runtime_url` - URL for the MCP Risk Server
- `memory_id` - ID of the AgentCore Memory resource
