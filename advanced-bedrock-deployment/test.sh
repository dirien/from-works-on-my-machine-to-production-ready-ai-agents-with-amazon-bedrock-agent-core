#!/bin/bash
# Test script for invoking the deployed Fraud Detection Agent
# Uses Pulumi outputs to get the agent runtime ARN
# Uses Pulumi ESC for AWS credentials

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Get the agent runtime ARN from Pulumi outputs
echo "Getting agent runtime ARN from Pulumi..."
AGENT_RUNTIME_ARN=$(cd "$SCRIPT_DIR/infra" && pulumi stack output agent_runtime_arn 2>/dev/null)

if [ -z "$AGENT_RUNTIME_ARN" ]; then
    echo "Error: Could not get agent_runtime_arn from Pulumi outputs."
    echo "Make sure you have deployed the stack with 'pulumi up'"
    exit 1
fi

echo "Agent Runtime ARN: $AGENT_RUNTIME_ARN"

# Install dependencies if needed
cd "$SCRIPT_DIR"
uv sync --quiet

# Run the invoke script with Pulumi ESC credentials
echo ""
echo "Invoking agent with fraud detection alert..."
pulumi env run pulumi-idp/auth -- uv run python "$SCRIPT_DIR/invoke_agent.py" "$AGENT_RUNTIME_ARN"
