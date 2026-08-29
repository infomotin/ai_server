#!/bin/bash

# OpenLocalAI Stop Script

echo "Stopping OpenLocalAI services..."

if [ -f ".api.pid" ]; then
    API_PID=$(cat .api.pid)
    if kill -0 $API_PID 2>/dev/null; then
        kill $API_PID
        echo "✓ API server stopped (PID: $API_PID)"
    fi
    rm .api.pid
fi

if [ -f ".web.pid" ]; then
    WEB_PID=$(cat .web.pid)
    if kill -0 $WEB_PID 2>/dev/null; then
        kill $WEB_PID
        echo "✓ Web UI stopped (PID: $WEB_PID)"
    fi
    rm .web.pid
fi

echo "All services stopped."
