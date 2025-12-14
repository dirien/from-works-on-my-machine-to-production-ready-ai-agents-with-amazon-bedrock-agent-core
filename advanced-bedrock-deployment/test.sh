#!/bin/bash
# Test script for invoking the deployed Fraud Detection Agent
# Uses Pulumi outputs to get the agent runtime ARN
# Uses Pulumi ESC for AWS credentials

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Default demo mode
DEMO_MODE="${1:-demo}"

# Show usage if help requested
if [ "$1" == "-h" ] || [ "$1" == "--help" ]; then
    echo "Usage: $0 [demo_mode]"
    echo ""
    echo "Available demo modes:"
    echo "  demo           - Short-term memory demo (same session)"
    echo "  longterm       - Long-term memory demo (cross-session)"
    echo "  longterm-fresh - Long-term memory demo with fresh IDs"
    echo "  gateway        - MCP Gateway demo"
    echo "  gateway-fresh  - MCP Gateway demo with fresh IDs (recommended)"
    echo ""
    echo "Examples:"
    echo "  $0              # Run default 'demo' mode"
    echo "  $0 gateway-fresh # Run MCP Gateway demo with fresh IDs"
    echo "  $0 longterm-fresh # Run long-term memory demo with fresh IDs"
    exit 0
fi

# Change to infra directory
cd "$SCRIPT_DIR/infra"

# Ensure dependencies are installed
uv sync --quiet

# Select the Pulumi stack
echo "Selecting Pulumi stack 'dev'..."
if ! pulumi env run pulumi-idp/auth -- uv run pulumi stack select dev 2>/dev/null; then
    echo "Error: Could not select stack 'dev'."
    echo "Available stacks:"
    pulumi env run pulumi-idp/auth -- uv run pulumi stack ls 2>/dev/null || echo "  (no stacks found)"
    echo ""
    echo "To create the stack, run: cd infra && pulumi env run pulumi-idp/auth -- uv run pulumi up"
    exit 1
fi

# Get the agent runtime ARN from Pulumi outputs
echo "Getting agent runtime ARN from Pulumi..."
AGENT_RUNTIME_ARN=$(pulumi env run pulumi-idp/auth -- uv run pulumi stack output agent_runtime_arn 2>/dev/null)

if [ -z "$AGENT_RUNTIME_ARN" ]; then
    echo "Error: Could not get agent_runtime_arn from Pulumi outputs."
    echo "Make sure you have deployed the stack with 'pulumi up'"
    exit 1
fi

echo "Agent Runtime ARN: $AGENT_RUNTIME_ARN"
echo "Demo Mode: $DEMO_MODE"
echo ""

# Install dependencies if needed
cd "$SCRIPT_DIR"
uv sync --quiet

# Run the invoke script with Pulumi ESC credentials
echo "Invoking agent with demo mode: $DEMO_MODE"
echo "========================================"
pulumi env run pulumi-idp/auth -- uv run python "$SCRIPT_DIR/invoke_agent.py" "$AGENT_RUNTIME_ARN" "$DEMO_MODE"
