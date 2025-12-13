# CLAUDE.md

This file provides guidance for Claude Code when working with this repository.

## Project Overview

This repository contains a fraud detection agent demo built with the Strands SDK and Amazon Bedrock. The project demonstrates the "Impossible Traveler" detection pattern - identifying fraudulent transactions based on physically impossible location changes.

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
├── advanced-bedrock-deployment/  # Advanced deployment with Short-term & Long-term Memory
│   ├── fraud-detection-agent/    # Agent container code with memory integration
│   │   ├── agent.py              # FastAPI agent with short-term & long-term memory hooks
│   │   ├── tools.py              # Tools with card blocking state tracking
│   │   ├── Dockerfile            # Container build for ARM64
│   │   ├── pyproject.toml        # Agent dependencies (includes bedrock-agentcore)
│   │   └── uv.lock               # Locked dependencies
│   ├── infra/                    # Pulumi infrastructure with Memory, Strategy & CloudWatch
│   │   ├── __main__.py           # Pulumi program (Memory, Strategy, Guardrails, CloudWatch, AgentCore)
│   │   └── pyproject.toml        # Pulumi dependencies
│   ├── invoke_agent.py           # Multi-user demo script (short-term & long-term memory)
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

### Advanced Deployment (with Short-term & Long-term Memory)

```bash
cd advanced-bedrock-deployment/infra
uv sync
uv run pulumi up
```

This deploys everything in the basic deployment plus:
- **AgentCore Memory**: Memory storage with 30-day event expiry
- **Short-term Memory**: Conversation history within the same session
- **Long-term Memory**: Semantic extraction strategy for cross-session memory
  - Custom semantic strategy extracts fraud-related facts from conversations
  - Uses Claude Haiku for efficient fact extraction
  - Namespace: `/fraud-detection/users/{actorId}` for per-user isolation
- **CloudWatch Observability**: Application logs and X-Ray traces
- **Memory Hooks**: Strands SDK hooks for storing messages and retrieving long-term facts
- **Card Blocking State**: Tools track blocked card status across requests

## Testing the Deployed Agent

### Basic Test

```bash
cd basic-bedrock-deployment
./test.sh
```

### Advanced Demo (Short-term Memory - Same Session)

```bash
cd advanced-bedrock-deployment
uv sync
uv run python invoke_agent.py <agent_runtime_arn> demo
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
uv sync
uv run python invoke_agent.py <agent_runtime_arn> longterm
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

### Advanced Demo (Long-term Memory - Fresh Mode for Live Demos)

```bash
cd advanced-bedrock-deployment
uv sync
uv run python invoke_agent.py <agent_runtime_arn> longterm-fresh
```

The `longterm-fresh` mode is **recommended for live demos**. It generates unique actor IDs with timestamps to avoid interference from previous test runs while keeping the same user IDs in prompts (so the mock tools work correctly).

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
- **Amazon Bedrock Guardrails**: Content filtering and topic enforcement
- **Amazon CloudWatch**: Application logs and X-Ray traces for observability
- **Pulumi**: Infrastructure as Code for AWS resources
- **Pulumi ESC**: Credential management for AWS access
- **uv**: Python package manager
- **FastAPI**: Web framework for agent API endpoint

## Agent Architecture

The fraud agent uses three tools:
1. `get_user_profile()` - Retrieves user details and home location
2. `get_recent_transactions()` - Gets last known transaction
3. `block_credit_card()` - Blocks the card and creates a ticket

## Commands

### Local Development
- `uv sync` - Install dependencies
- `uv run python demo_simulation.py` - Run demo (requires AWS credentials)
- `pulumi env run pulumi-idp/auth -- <command>` - Run with Pulumi ESC credentials

### Basic Production Deployment
- `cd basic-bedrock-deployment/infra && uv run pulumi up` - Deploy infrastructure
- `cd basic-bedrock-deployment && ./test.sh` - Test deployed agent
- `cd basic-bedrock-deployment/infra && uv run pulumi destroy` - Tear down infrastructure

### Advanced Production Deployment (Short-term & Long-term Memory)
- `cd advanced-bedrock-deployment/infra && uv run pulumi up` - Deploy infrastructure with memory
- `cd advanced-bedrock-deployment && uv run python invoke_agent.py <arn> demo` - Run short-term memory demo
- `cd advanced-bedrock-deployment && uv run python invoke_agent.py <arn> longterm` - Run long-term memory demo (fixed user IDs)
- `cd advanced-bedrock-deployment && uv run python invoke_agent.py <arn> longterm-fresh` - Run long-term memory demo (fresh IDs, recommended for live demos)
- `cd advanced-bedrock-deployment/infra && uv run pulumi destroy` - Tear down infrastructure
