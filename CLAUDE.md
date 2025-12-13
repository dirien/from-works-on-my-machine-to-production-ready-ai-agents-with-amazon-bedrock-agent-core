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
├── advanced-bedrock-deployment/  # Advanced deployment with AgentCore Memory & Observability
│   ├── fraud-detection-agent/    # Agent container code with memory integration
│   │   ├── agent.py              # FastAPI agent with short-term memory hooks
│   │   ├── tools.py              # Tools with card blocking state tracking
│   │   ├── Dockerfile            # Container build for ARM64
│   │   ├── pyproject.toml        # Agent dependencies (includes bedrock-agentcore)
│   │   └── uv.lock               # Locked dependencies
│   ├── infra/                    # Pulumi infrastructure with Memory & CloudWatch
│   │   ├── __main__.py           # Pulumi program (Memory, Guardrails, CloudWatch, AgentCore)
│   │   └── pyproject.toml        # Pulumi dependencies
│   ├── invoke_agent.py           # Multi-user demo script (5 scenarios)
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

### Advanced Deployment (with Memory & Observability)

```bash
cd advanced-bedrock-deployment/infra
uv sync
uv run pulumi up
```

This deploys everything in the basic deployment plus:
- **AgentCore Memory**: Short-term memory for conversation history (7-day event expiry)
- **CloudWatch Observability**: Application logs and X-Ray traces
- **Memory Hooks**: Strands SDK hooks for storing messages to memory
- **Card Blocking State**: Tools track blocked card status across requests

## Testing the Deployed Agent

### Basic Test

```bash
cd basic-bedrock-deployment
./test.sh
```

### Advanced Demo (Multi-User with Memory)

```bash
cd advanced-bedrock-deployment
uv sync
uv run python invoke_agent.py <agent_runtime_arn> demo
```

The advanced demo runs 5 scenarios:
1. **John Doe - Impossible Travel**: Transaction in Tokyo triggers fraud (card blocked)
2. **Jane Smith - Normal Transaction**: Transaction at home location (no fraud)
3. **John Doe - Follow-up Transaction**: Memory recognizes card is ALREADY BLOCKED
4. **Alice Chen - Impossible Travel**: Transaction in Sydney triggers fraud (card blocked)
5. **Jane Smith - Second Transaction**: Consistent with home location (no fraud)

## Key Technologies

- **Strands SDK** (`strands-agents`): AWS open-source agent framework
- **Amazon Bedrock**: Claude Opus 4.5 model (`us.anthropic.claude-opus-4-5-20251101-v1:0`)
- **Amazon Bedrock AgentCore**: Managed runtime for agent containers
- **Amazon Bedrock AgentCore Memory**: Short-term memory for conversation history
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

### Advanced Production Deployment (Memory & Observability)
- `cd advanced-bedrock-deployment/infra && uv run pulumi up` - Deploy infrastructure with memory
- `cd advanced-bedrock-deployment && uv run python invoke_agent.py <arn> demo` - Run multi-user demo
- `cd advanced-bedrock-deployment/infra && uv run pulumi destroy` - Tear down infrastructure
