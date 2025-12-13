# CLAUDE.md

This file provides guidance for Claude Code when working with this repository.

## Project Overview

This repository contains a fraud detection agent demo built with the Strands SDK and Amazon Bedrock. The project demonstrates the "Impossible Traveler" detection pattern - identifying fraudulent transactions based on physically impossible location changes.

## Repository Structure

```
├── local-prototype/           # Local Strands SDK agent implementation
│   ├── agent.py               # Fraud detection agent with Claude Opus 4.5
│   ├── tools.py               # Mock tools (get_user_profile, get_recent_transactions, block_credit_card)
│   ├── demo_simulation.py     # Demo runner script
│   ├── pyproject.toml         # Python dependencies (uv)
│   ├── run.sh                 # Execution script with Pulumi ESC
│   └── uv.lock                # Locked dependencies
├── basic-bedrock-deployment/  # Production deployment to AWS Bedrock AgentCore
│   ├── fraud-detection-agent/ # Agent container code
│   │   ├── agent.py           # FastAPI-wrapped fraud detection agent
│   │   ├── tools.py           # Mock tools for fraud detection
│   │   ├── Dockerfile         # Container build for ARM64
│   │   ├── pyproject.toml     # Agent dependencies
│   │   └── uv.lock            # Locked dependencies
│   ├── infra/                 # Pulumi infrastructure
│   │   ├── __main__.py        # Pulumi program (ECR, IAM, Guardrails, AgentCore)
│   │   └── pyproject.toml     # Pulumi dependencies
│   ├── invoke_agent.py        # Script to invoke deployed agent
│   ├── test.sh                # Test script with Pulumi ESC credentials
│   └── pyproject.toml         # Test script dependencies
├── assets/                    # Presentation assets
├── CLAUDE.md                  # This file - Claude Code guidance
└── .gitignore
```

## Running the Local Demo

```bash
cd local-prototype
./run.sh
```

This uses `uv` for dependency management and `pulumi env run pulumi-idp/auth` for AWS credentials.

## Deploying to AWS Bedrock AgentCore

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

## Testing the Deployed Agent

```bash
cd basic-bedrock-deployment
./test.sh
```

## Key Technologies

- **Strands SDK** (`strands-agents`): AWS open-source agent framework
- **Amazon Bedrock**: Claude Opus 4.5 model (`us.anthropic.claude-opus-4-5-20251101-v1:0`)
- **Amazon Bedrock AgentCore**: Managed runtime for agent containers
- **Amazon Bedrock Guardrails**: Content filtering and topic enforcement
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

### Production Deployment
- `cd basic-bedrock-deployment/infra && uv run pulumi up` - Deploy infrastructure
- `cd basic-bedrock-deployment && ./test.sh` - Test deployed agent
- `cd basic-bedrock-deployment/infra && uv run pulumi destroy` - Tear down infrastructure
