#!/bin/bash
cd /www/AI_server
source .venv/bin/activate

# Kill existing
kill -9 $(lsof -t -i:8000) 2>/dev/null
kill -9 $(lsof -t -i:5000) 2>/dev/null
sleep 1

# Start API
python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 &
API_PID=$!

# Start Web
python -c "from web.app import app; app.run(host='0.0.0.0', port=5000, debug=False)" &
WEB_PID=$!

sleep 3
echo "API PID: $API_PID"
echo "Web PID: $WEB_PID"
echo "API Health: $(curl -s http://localhost:8000/health)"
echo "Web Status: $(curl -s -o /dev/null -w '%{http_code}' http://localhost:5000/integrations)"

wait
