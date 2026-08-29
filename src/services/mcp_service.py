import json
import subprocess
import asyncio
import httpx
from typing import Dict, Any, List, Optional
from datetime import datetime


class MCPStdioClient:
    def __init__(self, command: str, args: List[str] = None, env: Dict[str, str] = None):
        self.command = command
        self.args = args or []
        self.env = env or {}
        self.process = None

    async def start(self) -> Dict[str, Any]:
        try:
            import os
            full_env = {**os.environ, **self.env}
            self.process = await asyncio.create_subprocess_exec(
                self.command, *self.args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=full_env
            )
            init_msg = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "openlocalai", "version": "1.0.0"}
                }
            }
            await self._send(init_msg)
            response = await self._receive()

            list_tools_msg = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
                "params": {}
            }
            await self._send(list_tools_msg)
            tools_response = await self._receive()

            return {
                "success": True,
                "tools": tools_response.get("result", {}).get("tools", []),
                "server_info": response.get("result", {}).get("serverInfo", {})
            }
        except Exception as e:
            return {"success": False, "error": str(e)[:300]}

    async def call_tool(self, name: str, arguments: dict) -> Dict[str, Any]:
        try:
            msg = {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments}
            }
            await self._send(msg)
            response = await self._receive()
            return response.get("result", {})
        except Exception as e:
            return {"content": [{"type": "text", "text": f"Error: {str(e)[:200]}"}]}

    async def stop(self):
        if self.process:
            try:
                self.process.terminate()
                await asyncio.wait_for(self.process.wait(), timeout=5)
            except:
                self.process.kill()

    async def _send(self, msg: dict):
        if self.process and self.process.stdin:
            data = json.dumps(msg) + "\n"
            self.process.stdin.write(data.encode())
            await self.process.stdin.drain()

    async def _receive(self) -> dict:
        if self.process and self.process.stdout:
            line = await asyncio.wait_for(self.process.stdout.readline(), timeout=30)
            if line:
                return json.loads(line.decode().strip())
        return {}


class MCPSSEClient:
    def __init__(self, url: str, headers: Dict[str, str] = None):
        self.url = url
        self.headers = headers or {}
        self.tools = []

    async def connect(self) -> Dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{self.url}/tools",
                    headers={**self.headers, "Accept": "application/json"}
                )
                if resp.status_code == 200:
                    data = resp.json()
                    self.tools = data.get("tools", [])
                    return {"success": True, "tools": self.tools}
                else:
                    resp2 = await client.get(self.url, headers=self.headers)
                    return {"success": True, "tools": [], "message": "Connected (no tools listed)"}
        except Exception as e:
            return {"success": False, "error": str(e)[:300]}

    async def call_tool(self, name: str, arguments: dict) -> Dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{self.url}/tools/{name}/call",
                    json={"arguments": arguments},
                    headers={**self.headers, "Content-Type": "application/json"}
                )
                return resp.json() if resp.status_code == 200 else {"error": f"HTTP {resp.status_code}"}
        except Exception as e:
            return {"content": [{"type": "text", "text": f"Error: {str(e)[:200]}"}]}


class MCPManager:
    def __init__(self):
        self.clients: Dict[str, Any] = {}

    async def connect_server(self, server_config: dict) -> Dict[str, Any]:
        server_type = server_config.get("server_type", "stdio")
        name = server_config.get("name", "unnamed")

        if server_type == "stdio":
            client = MCPStdioClient(
                command=server_config.get("command", ""),
                args=server_config.get("args", []),
                env=server_config.get("env", {})
            )
            result = await client.start()
        elif server_type == "sse":
            client = MCPSSEClient(
                url=server_config.get("url", ""),
                headers=server_config.get("headers", {})
            )
            result = await client.connect()
        else:
            return {"success": False, "error": f"Unknown server type: {server_type}"}

        if result.get("success"):
            self.clients[name] = client

        return result

    async def call_tool(self, server_name: str, tool_name: str, arguments: dict) -> Dict[str, Any]:
        client = self.clients.get(server_name)
        if not client:
            return {"content": [{"type": "text", "text": f"Server '{server_name}' not connected"}]}
        return await client.call_tool(tool_name, arguments)

    async def disconnect_server(self, server_name: str):
        client = self.clients.pop(server_name, None)
        if client and hasattr(client, 'stop'):
            await client.stop()

    def get_all_tools(self) -> List[dict]:
        tools = []
        for name, client in self.clients.items():
            client_tools = getattr(client, 'tools', [])
            for tool in client_tools:
                tools.append({
                    "name": f"mcp_{name}_{tool.get('name', '')}",
                    "mcp_server": name,
                    "original_name": tool.get("name", ""),
                    "description": tool.get("description", ""),
                    "input_schema": tool.get("inputSchema", {})
                })
        return tools


mcp_manager = MCPManager()
