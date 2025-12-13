# CLAUDE.md

This file provides guidance for Claude Code when working with this repository.

## Project Overview

This repository contains a fraud detection agent demo built with the Strands SDK and Amazon Bedrock. The project demonstrates the "Impossible Traveler" detection pattern - identifying fraudulent transactions based on physically impossible location changes.

## Repository Structure

```
lome/
├── local-prototype/     # Strands SDK agent implementation
│   ├── agent.py         # Fraud detection agent with Claude Opus 4.5
│   ├── tools.py         # Mock tools (get_user_profile, get_recent_transactions, block_credit_card)
│   ├── demo_simulation.py  # Demo runner script
│   ├── pyproject.toml   # Python dependencies (uv)
│   ├── run.sh           # Execution script with Pulumi ESC
│   └── uv.lock          # Locked dependencies
├── assets/              # Presentation assets
│   ├── slide1-world-map.png    # Scenario visualization (generated, gitignored)
│   ├── slide2-agent.png        # Agent architecture diagram (generated, gitignored)
│   └── create_slides.py        # Slide generator script
├── CLAUDE.md            # This file - Claude Code guidance
└── .gitignore
```

## Running the Demo

```bash
cd local-prototype
./run.sh
```

This uses `uv` for dependency management and `pulumi env run pulumi-idp/auth` for AWS credentials.

## Key Technologies

- **Strands SDK** (`strands-agents`): AWS open-source agent framework
- **Amazon Bedrock**: Claude Opus 4.5 model (`us.anthropic.claude-opus-4-5-20251101-v1:0`)
- **Pulumi ESC**: Credential management for AWS access
- **uv**: Python package manager

## Agent Architecture

The fraud agent uses three tools:
1. `get_user_profile()` - Retrieves user details and home location
2. `get_recent_transactions()` - Gets last known transaction
3. `block_credit_card()` - Blocks the card and creates a ticket

## Commands

- `uv sync` - Install dependencies
- `uv run python demo_simulation.py` - Run demo (requires AWS credentials)
- `pulumi env run pulumi-idp/auth -- <command>` - Run with Pulumi ESC credentials
