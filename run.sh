#!/bin/bash
cd /www/AI_server
kill -9 $(lsof -t -i:8000) 2>/dev/null
kill -9 $(lsof -t -i:5000) 2>/dev/null
sleep 1
nohup ./.venv/bin/python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 > api.log 2>&1 &
nohup ./.venv/bin/python web/app.py > web.log 2>&1 &
sleep 4
echo "API:" $(curl -s http://localhost:8000/ | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('status','FAIL'))" 2>/dev/null)
echo "WEB:" $(curl -s -o /dev/null -w "%{http_code}" http://localhost:5000/ 2>/dev/null)
echo "Ports:" $(ss -tlnp | grep -cE ':(8000|5000)')
