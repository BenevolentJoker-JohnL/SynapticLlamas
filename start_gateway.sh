#!/bin/bash
# SynapticLlamas Gateway - Quick Start Script
#
# This script starts the SynapticLlamas gateway with distributed inference support.
#
# Usage:
#   ./start_gateway.sh                    # Ollama-only mode
#   ./start_gateway.sh 192.168.1.10:50052,192.168.1.11:50052  # With distributed inference

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "======================================================================="
echo " SynapticLlamas Gateway - Distributed AI Orchestration"
echo "======================================================================="
echo ""

# Check if Ollama is running
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  Warning: Ollama doesn't seem to be running on localhost:11434${NC}"
    echo "   Start Ollama with: ollama serve"
    echo ""
fi

# Parse RPC backends from command line
if [ "$1" != "" ]; then
    export RPC_BACKENDS="$1"
    echo -e "${GREEN}✅ Distributed inference: Manual configuration${NC}"
    echo "   RPC backends: $RPC_BACKENDS"
    echo ""
    echo "Make sure RPC servers are running on these nodes:"
    IFS=',' read -ra BACKENDS <<< "$RPC_BACKENDS"
    for backend in "${BACKENDS[@]}"; do
        echo "   → $backend: rpc-server --host 0.0.0.0 --port ${backend##*:} --mem 2048"
    done
    echo ""
else
    echo -e "${GREEN}🔍 Distributed inference: Auto-discovery mode${NC}"
    echo "   Gateway will scan the network for RPC servers on port 50052"
    echo "   Start RPC servers on worker nodes:"
    echo "   → rpc-server --host 0.0.0.0 --port 50052 --mem 2048"
    echo ""
    echo "   To manually specify backends instead:"
    echo "   ./start_gateway.sh 192.168.1.10:50052,192.168.1.11:50052"
    echo ""
fi

# Set port (default: 8000)
export PORT="${PORT:-8000}"

echo "======================================================================="
echo ""
echo -e "${GREEN}🚀 Starting gateway on port $PORT...${NC}"
echo ""

# Start the gateway
python3 -m sollol.gateway
