#!/bin/bash
set -euo pipefail

echo "=== Creative Memory MCP Server Setup ==="

# 1. Install Ollama
if ! command -v ollama &>/dev/null; then
    echo "Installing Ollama..."
    if command -v brew &>/dev/null; then
        brew install ollama
    else
        echo "Homebrew not found. Install Ollama manually: https://ollama.com/download"
        exit 1
    fi
else
    echo "Ollama already installed: $(ollama --version 2>&1 || echo 'unknown version')"
fi

# 2. Start Ollama service
echo "Starting Ollama service..."
if command -v brew &>/dev/null; then
    brew services start ollama 2>/dev/null || true
else
    ollama serve &>/dev/null &
fi

echo "Waiting for Ollama to start..."
for i in $(seq 1 30); do
    if curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
        echo "Ollama is running."
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo "ERROR: Ollama did not start within 30 seconds."
        exit 1
    fi
    sleep 1
done

# 3. Pull embedding model
echo "Pulling nomic-embed-text model..."
ollama pull nomic-embed-text

# 4. Verify embedding model
echo "Verifying embedding model..."
RESPONSE=$(curl -s http://localhost:11434/api/embed \
    -d '{"model": "nomic-embed-text", "input": "test"}')
if echo "$RESPONSE" | python3 -c "import sys,json; d=json.load(sys.stdin); assert 'embeddings' in d" 2>/dev/null; then
    echo "nomic-embed-text is working correctly."
else
    echo "WARNING: Could not verify embedding model. Check Ollama status."
fi

# 5. Install Python dependencies
echo "Installing Python dependencies..."
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$SCRIPT_DIR"

if command -v uv &>/dev/null; then
    uv pip install -r requirements.txt
else
    pip3 install -r requirements.txt
fi

# 6. Create data directory
mkdir -p ~/.creative-memory/chroma
echo "Data directory: ~/.creative-memory/chroma/"

echo ""
echo "=== Setup Complete ==="
echo "Run the server:  uv run server.py"
echo "Or configure LM Studio with mcp.json.example"
