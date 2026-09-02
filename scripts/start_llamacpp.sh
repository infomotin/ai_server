#!/bin/bash
# llama.cpp server startup script
LLAMA_SERVER="/usr/local/lib/ollama/llama-server"
MODEL_PATH="/usr/share/ollama/.ollama/models/blobs/sha256-74701a8c35f6c8d9a4b91f3f3497643001d63e0c7a84e085bed452548fa88d45"
PORT=${LLAMACPP_PORT:-8080}
HOST=${LLAMACPP_HOST:-127.0.0.1}
CTX_SIZE=${LLAMACPP_CTX:-2048}

echo "Starting llama.cpp server..."
echo "  Model: $MODEL_PATH"
echo "  Port: $PORT"
echo "  Context: $CTX_SIZE"

exec $LLAMA_SERVER \
    --model "$MODEL_PATH" \
    --port $PORT \
    --host $HOST \
    --ctx-size $CTX_SIZE \
    --n-predict 512 \
    --threads 2 \
    --no-mmap \
    2>&1
