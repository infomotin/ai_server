#!/bin/bash
cd /www/AI_server
source .venv/bin/activate

# Kill existing
kill -9 $(lsof -t -i:8000) 2>/dev/null
kill -9 $(lsof -t -i:5000) 2>/dev/null
sleep 1

# Start API as daemon
setsid python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 > /tmp/api_server.log 2>&1 &

# Start Web as daemon
setsid python -c "from web.app import app; app.run(host='0.0.0.0', port=5000, debug=False)" > /tmp/web_server.log 2>&1 &

sleep 4
echo "API: $(curl -s http://localhost:8000/health)"
echo "Web: HTTP $(curl -s -o /dev/null -w '%{http_code}' http://localhost:5000/integrations)"
