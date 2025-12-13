#!/bin/bash
set -e

# Install dependencies with uv
echo "Installing dependencies with uv..."
uv sync

# Run the demo with AWS credentials from Pulumi ESC
echo "Running fraud detection demo with Pulumi ESC credentials..."
pulumi env run pulumi-idp/auth -- uv run python -u demo_simulation.py
