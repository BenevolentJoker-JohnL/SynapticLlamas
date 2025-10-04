#!/bin/bash
# SOLLOL Gateway - Drop-in Ollama Replacement
#
# This script starts SOLLOL on port 11434 (Ollama's port) with:
# - Auto-discovery of Ollama nodes on network
# - Auto-discovery of RPC backends for distributed inference
# - Automatic GGUF extraction from Ollama storage
#
# Usage:
#   ./start_gateway.sh                    # Auto-discover everything
#   ./start_gateway.sh 192.168.1.10:50052,192.168.1.11:50052  # Manual RPC backends

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo "======================================================================="
echo " SOLLOL Gateway - Drop-in Ollama Replacement"
echo "======================================================================="
echo ""

# Check if something is already running on 11434
if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  Port 11434 is already in use!${NC}"
    echo "   This is likely local Ollama. SOLLOL needs this port."
    echo ""
    echo "Options:"
    echo "  1. Stop local Ollama: sudo systemctl stop ollama"
    echo "  2. Move Ollama to different port: OLLAMA_HOST=0.0.0.0:11435 ollama serve"
    echo "  3. Use SOLLOL on different port: PORT=8000 ./start_gateway.sh"
    echo ""
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
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

# Set port (default: 11434 - Ollama's port)
export PORT="${PORT:-11434}"

echo "======================================================================="
echo ""
echo -e "${GREEN}🚀 Starting SOLLOL gateway on port $PORT (Ollama's port)${NC}"
echo ""
echo "What SOLLOL does:"
echo "  ✅ Discovers Ollama nodes on your network automatically"
echo "  ✅ Discovers RPC backends for distributed inference"
echo "  ✅ Extracts GGUF from Ollama storage automatically"
echo "  ✅ Routes small models → Ollama pool, large models → distributed"
echo ""
echo "Your apps can now use: http://localhost:$PORT (just like Ollama!)"
echo ""
echo "======================================================================="
echo ""

# Start the gateway
python3 -m sollol.gateway
