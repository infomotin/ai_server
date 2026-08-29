import json
import httpx
from datetime import datetime
from typing import Optional, List, Dict, Any

from src.models.agent_models import AgentSession, AgentMessage, AgentProvider, AgentFile
from src.services.file_service import (
    read_file, write_file, edit_file, search_files,
    list_directory, run_command, get_file_info
)

SYSTEM_PROMPT_PLAN = """You are an expert coding agent in PLAN mode. You analyze codebases and create detailed plans.

CAPABILITIES:
- Read and analyze code files
- Search codebases for patterns
- List directory structures
- Run read-only commands

When in PLAN mode:
1. First understand the project structure
2. Read relevant files to understand context
3. Create a detailed, step-by-step plan
4. Explain what changes are needed and why
5. Do NOT make any changes - only plan

Available tools:
- read_file(path, offset?, limit?): Read file contents
- list_directory(path, max_depth?): List directory contents
- search_files(path, pattern, file_pattern?): Search for patterns
- run_command(command, cwd?): Run read-only commands
- get_file_info(path): Get file metadata

Respond with structured plans using markdown. Be specific about file paths and code changes."""

SYSTEM_PROMPT_BUILD = """You are an expert coding agent in BUILD mode. You implement code changes based on plans.

CAPABILITIES:
- Read and write code files
- Edit existing code
- Search codebases
- Run commands (build, test, etc.)
- Create new files and directories

When in BUILD mode:
1. Execute the plan step by step
2. Make changes to files as needed
3. Verify changes work (run tests, builds)
4. Report what was done

Available tools:
- read_file(path, offset?, limit?): Read file contents
- write_file(path, content): Write to a file
- edit_file(path, old_text, new_text): Edit specific parts of files
- list_directory(path, max_depth?): List directory contents
- search_files(path, pattern, file_pattern?): Search for patterns
- run_command(command, cwd?): Run commands
- create_directory(path): Create a directory

IMPORTANT: Always confirm file changes. Show what you're changing before doing it."""

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file. Use offset and limit for large files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute path to the file"},
                    "offset": {"type": "integer", "description": "Line number to start from (0-based)", "default": 0},
                    "limit": {"type": "integer", "description": "Maximum number of lines to read", "default": 200}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file. Creates the file if it doesn't exist.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute path to the file"},
                    "content": {"type": "string", "description": "Content to write to the file"}
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "Edit a specific part of a file by replacing old text with new text.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute path to the file"},
                    "old_text": {"type": "string", "description": "Exact text to find and replace"},
                    "new_text": {"type": "string", "description": "Text to replace with"}
                },
                "required": ["path", "old_text", "new_text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "List contents of a directory with optional depth limit.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path to list"},
                    "max_depth": {"type": "integer", "description": "Maximum depth to traverse", "default": 2}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_files",
            "description": "Search for a pattern in files using regex.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory to search in"},
                    "pattern": {"type": "string", "description": "Regex pattern to search for"},
                    "file_pattern": {"type": "string", "description": "File pattern (e.g., *.py)", "default": "*"},
                    "max_results": {"type": "integer", "description": "Maximum results", "default": 30}
                },
                "required": ["path", "pattern"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Execute a shell command.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Shell command to execute"},
                    "cwd": {"type": "string", "description": "Working directory", "default": "/www"},
                    "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 30}
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_file_info",
            "description": "Get metadata about a file or directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to get info about"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_directory",
            "description": "Create a directory (and parents if needed).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path to create"}
                },
                "required": ["path"]
            }
        }
    }
]


def execute_tool(tool_name: str, arguments: dict, project_path: str = "/www") -> Any:
    if tool_name == "read_file":
        path = arguments.get("path", "")
        if not os.path.isabs(path):
            path = os.path.join(project_path, path)
        result = read_file(path, arguments.get("offset", 0), arguments.get("limit", 200))
        return result

    elif tool_name == "write_file":
        path = arguments.get("path", "")
        if not os.path.isabs(path):
            path = os.path.join(project_path, path)
        return write_file(path, arguments.get("content", ""))

    elif tool_name == "edit_file":
        path = arguments.get("path", "")
        if not os.path.isabs(path):
            path = os.path.join(project_path, path)
        return edit_file(path, arguments.get("old_text", ""), arguments.get("new_text", ""))

    elif tool_name == "list_directory":
        path = arguments.get("path", project_path)
        if not os.path.isabs(path):
            path = os.path.join(project_path, path)
        return list_directory(path, arguments.get("max_depth", 2))

    elif tool_name == "search_files":
        path = arguments.get("path", project_path)
        if not os.path.isabs(path):
            path = os.path.join(project_path, path)
        return search_files(
            path,
            arguments.get("pattern", ""),
            arguments.get("file_pattern", "*"),
            arguments.get("max_results", 30)
        )

    elif tool_name == "run_command":
        cwd = arguments.get("cwd", project_path)
        return run_command(arguments.get("command", ""), cwd, arguments.get("timeout", 30))

    elif tool_name == "get_file_info":
        path = arguments.get("path", "")
        if not os.path.isabs(path):
            path = os.path.join(project_path, path)
        return get_file_info(path)

    elif tool_name == "create_directory":
        path = arguments.get("path", "")
        if not os.path.isabs(path):
            path = os.path.join(project_path, path)
        from src.services.file_service import create_directory
        return create_directory(path)

    return {"error": f"Unknown tool: {tool_name}"}


import os


PROVIDER_URLS = {
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com/v1",
    "nvidia": "https://integrate.api.nvidia.com/v1",
    "groq": "https://api.groq.com/openai/v1",
    "deepseek": "https://api.deepseek.com/v1",
    "mistral": "https://api.mistral.ai/v1",
    "together": "https://api.together.xyz/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "ollama": "http://localhost:11434",
    "custom": None
}


class AgentService:
    def __init__(self, provider: AgentProvider):
        self.provider = provider
        self.api_url = provider.api_url.rstrip('/')
        self.api_key = provider.api_key
        self.model = provider.model
        self.provider_type = provider.provider_type

    def _build_url(self) -> str:
        if "/v1/chat/completions" in self.api_url:
            return self.api_url
        if "/v1" in self.api_url:
            return f"{self.api_url}/chat/completions"
        if self.provider_type == "anthropic":
            return f"{self.api_url}/messages"
        return f"{self.api_url}/v1/chat/completions"

    def _build_headers(self) -> dict:
        headers = {"Content-Type": "application/json"}

        if self.provider_type == "anthropic":
            if self.api_key:
                headers["x-api-key"] = self.api_key
                headers["anthropic-version"] = "2023-06-01"
        else:
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

        if self.provider_type == "nvidia":
            headers["Accept"] = "application/json"

        return headers

    def _build_payload_anthropic(self, messages: List[Dict], tools: List[Dict] = None) -> dict:
        system_msg = ""
        filtered = []
        for m in messages:
            if m["role"] == "system":
                system_msg = m["content"]
            else:
                filtered.append(m)

        payload = {
            "model": self.model,
            "messages": filtered,
            "max_tokens": 4096
        }
        if system_msg:
            payload["system"] = system_msg
        if tools:
            payload["tools"] = [{
                "name": t["function"]["name"],
                "description": t["function"].get("description", ""),
                "input_schema": t["function"].get("parameters", {})
            } for t in tools]
        return payload

    def chat(self, messages: List[Dict], tools: List[Dict] = None,
             tool_choice: str = "auto", max_tokens: int = 4096) -> Dict[str, Any]:
        url = self._build_url()
        headers = self._build_headers()

        if self.provider_type == "anthropic":
            payload = self._build_payload_anthropic(messages, tools)
        else:
            payload = {
                "model": self.model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": 0.3
            }
            if tools:
                payload["tools"] = tools
                payload["tool_choice"] = tool_choice

        try:
            with httpx.Client(timeout=120.0, verify=False) as client:
                resp = client.post(url, json=payload, headers=headers)

                if resp.status_code != 200:
                    error_text = resp.text[:300]
                    return {"success": False, "error": f"HTTP {resp.status_code}: {error_text}"}

                data = resp.json()

                if self.provider_type == "anthropic":
                    content = ""
                    tool_calls = []
                    for block in data.get("content", []):
                        if block.get("type") == "text":
                            content += block.get("text", "")
                        elif block.get("type") == "tool_use":
                            tool_calls.append({
                                "id": block.get("id", ""),
                                "type": "function",
                                "function": {
                                    "name": block.get("name", ""),
                                    "arguments": json.dumps(block.get("input", {}))
                                }
                            })
                    usage = data.get("usage", {})
                    return {
                        "success": True,
                        "content": content,
                        "tool_calls": tool_calls if tool_calls else None,
                        "finish_reason": data.get("stop_reason", "end_turn"),
                        "tokens": usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
                    }
                else:
                    choice = data.get("choices", [{}])[0]
                    message = choice.get("message", {})
                    usage = data.get("usage", {})
                    return {
                        "success": True,
                        "content": message.get("content", ""),
                        "tool_calls": message.get("tool_calls"),
                        "finish_reason": choice.get("finish_reason"),
                        "tokens": usage.get("total_tokens", 0)
                    }
        except httpx.TimeoutException:
            return {"success": False, "error": "Request timed out (120s)"}
        except httpx.ConnectError as e:
            return {"success": False, "error": f"Connection failed: {str(e)[:150]}"}
        except Exception as e:
            return {"success": False, "error": f"Error: {str(e)[:200]}"}


def run_agent_turn(session: AgentSession, user_message: str, db=None) -> Dict[str, Any]:
    if db is None:
        from src.models.engine import get_db_session
        for s in get_db_session():
            db = s
            break

    provider = None
    if session.provider_id:
        provider = db.query(AgentProvider).filter_by(id=session.provider_id).first()

    if not provider:
        provider = db.query(AgentProvider).filter_by(
            user_id=session.user_id, is_active=True
        ).first()

    if not provider:
        return {"success": False, "error": "No AI provider configured. Add a provider first."}

    history = db.query(AgentMessage).filter_by(
        session_id=session.id
    ).order_by(AgentMessage.created_at).all()

    system_prompt = SYSTEM_PROMPT_BUILD if session.mode == "build" else SYSTEM_PROMPT_PLAN

    messages = [{"role": "system", "content": system_prompt}]
    for msg in history:
        messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": user_message})

    db.add(AgentMessage(
        session_id=session.id,
        role="user",
        content=user_message
    ))
    db.commit()

    agent = AgentService(provider)
    all_tool_results = []
    max_iterations = 15

    for iteration in range(max_iterations):
        response = agent.chat(messages, TOOL_DEFINITIONS, "auto")

        if not response.get("success"):
            return {"success": False, "error": response.get("error", "Unknown error")}

        assistant_content = response.get("content", "")
        tool_calls = response.get("tool_calls")
        tokens = response.get("tokens", 0)

        if tool_calls:
            messages.append({
                "role": "assistant",
                "content": assistant_content or "",
                "tool_calls": tool_calls
            })

            if assistant_content:
                db.add(AgentMessage(
                    session_id=session.id,
                    role="assistant",
                    content=assistant_content,
                    tokens_used=tokens
                ))
                db.commit()

            for tc in tool_calls:
                func_name = tc["function"]["name"]
                try:
                    func_args = json.loads(tc["function"]["arguments"])
                except json.JSONDecodeError:
                    func_args = {}

                result = execute_tool(func_name, func_args, session.project_path)

                all_tool_results.append({
                    "tool": func_name,
                    "args": func_args,
                    "result": result
                })

                result_str = json.dumps(result, default=str)[:8000]
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result_str
                })

                db.add(AgentFile(
                    session_id=session.id,
                    file_path=func_args.get("path", ""),
                    action=func_name,
                    content=json.dumps(result, default=str)[:5000]
                ))
                db.commit()

        else:
            if assistant_content:
                db.add(AgentMessage(
                    session_id=session.id,
                    role="assistant",
                    content=assistant_content,
                    tokens_used=tokens
                ))
                db.commit()

            return {
                "success": True,
                "content": assistant_content,
                "tool_results": all_tool_results,
                "iterations": iteration + 1,
                "tokens": tokens
            }

    return {
        "success": True,
        "content": "Maximum iterations reached. Here's what was accomplished:\n\n" +
                    "\n".join([f"- {tr['tool']}: {json.dumps(tr['args'])[:80]}" for tr in all_tool_results]),
        "tool_results": all_tool_results,
        "iterations": max_iterations,
        "tokens": 0
    }
