import json
import os
import re
import httpx
import requests
from datetime import datetime
from typing import Optional, List, Dict, Any

from src.models.agent_models import AgentSession, AgentMessage, AgentProvider, AgentFile
from src.services.file_service import (
    read_file, write_file, edit_file, search_files,
    list_directory, run_command, get_file_info, create_directory, delete_file
)

SYSTEM_PROMPT_PLAN = """You are OpenLocalAI - an expert AI coding agent like Cursor AI or GitHub Copilot.

## Your Capabilities
- Read, write, edit, and analyze code files
- Search across entire codebases with regex
- Execute shell commands (builds, tests, git, etc.)
- Create and delete files and directories
- Understand project structure and dependencies

## Operating Modes
You have two modes:
1. **PLAN mode** - Analyze code, understand structure, create detailed plans WITHOUT making changes
2. **BUILD mode** - Execute plans, make actual code changes, run commands, verify work

## How to Work

### In PLAN mode:
1. First explore the project structure using list_directory
2. Read relevant files to understand context and dependencies
3. Use search_files to find specific patterns, functions, or implementations
4. Create a detailed, actionable plan with specific file paths and changes
5. DO NOT make any changes - only plan

### In BUILD mode:
1. Execute the plan step by step
2. Use write_file for new files, edit_file for modifications
3. Run tests and builds to verify changes
4. Report completion with specific details of what was done

## Critical Rules
- Always confirm file paths before modifying
- Show diffs for significant changes
- If a change fails, explain why and suggest alternatives
- Use the project_path as the root for all relative paths

## Communication Style
- Be concise but thorough
- Use markdown code blocks for code snippets
- Show file paths prominently
- List specific changes made at the end of BUILD mode

Available tools:
- read_file(path, offset?, limit?): Read file contents (offset/limit are line numbers)
- list_directory(path, max_depth?): List directory tree structure
- search_files(path, pattern, file_pattern?, max_results?): Search with regex
- run_command(command, cwd?, timeout?): Execute shell commands
- get_file_info(path): Get file metadata (size, modified, permissions)
- write_file(path, content): Create or overwrite a file
- edit_file(path, old_text, new_text): Replace specific text in a file
- create_directory(path): Create a directory and parents
- delete_file(path): Delete file or directory

Remember: In PLAN mode, never make changes. In BUILD mode, execute the plan and verify."""

SYSTEM_PROMPT_BUILD = """You are OpenLocalAI - an expert AI coding agent like Cursor AI or GitHub Copilot in BUILD mode.

## Your Mission
You are tasked with implementing code changes. You MUST:
1. Execute the plan step by step
2. Make actual file changes
3. Run tests and builds to verify
4. Report completion with specific details

## Tools Available
- read_file(path, offset?, limit?): Read file contents
- write_file(path, content): Create or overwrite file
- edit_file(path, old_text, new_text): Replace specific text (MUST match exactly)
- list_directory(path, max_depth?): List directory
- search_files(path, pattern, file_pattern?, max_results?): Regex search
- run_command(command, cwd?, timeout?): Execute commands
- get_file_info(path): File metadata
- create_directory(path): Create directory
- delete_file(path): Delete file/directory

## Critical Instructions

### File Operations:
- Always verify file exists before editing (use read_file first)
- For edit_file: old_text MUST match exactly, including whitespace
- For write_file: overwrites entire file, use with caution
- Always confirm paths in your response before changes

### Command Execution:
- Run tests: `cd <project> && python -m pytest` or similar
- Run builds: `cd <project> && npm run build` or similar
- Verify syntax: `python -m py_compile <file>` for Python

### Error Handling:
- If edit fails: re-read file, find exact text, retry
- If command fails: analyze error, fix issues, retry
- Report all errors clearly

### Completion:
When done, summarize:
- Files modified/created
- Changes made
- Tests run and results
- Any remaining issues

Work systematically through the plan. Make changes, verify them, then report."""

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read file contents. Use offset and limit (line numbers) for large files. Returns success, content, total_lines, has_more.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute path to the file"},
                    "offset": {"type": "integer", "description": "Line number to start from (0-based)", "default": 0},
                    "limit": {"type": "integer", "description": "Max lines to read", "default": 200}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file. CREATES or OVERWRITES the file. Use edit_file instead for partial changes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute path to the file"},
                    "content": {"type": "string", "description": "Full content to write"}
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "Edit specific text in a file by replacing old_text with new_text. old_text MUST match exactly.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute path to the file"},
                    "old_text": {"type": "string", "description": "Exact text to find and replace (must match exactly)"},
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
            "description": "List directory contents with optional depth. Returns files and subdirectories with their types.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path to list"},
                    "max_depth": {"type": "integer", "description": "Max traversal depth", "default": 2}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_files",
            "description": "Search for regex pattern in files. Returns file paths, line numbers, and matching content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory to search in"},
                    "pattern": {"type": "string", "description": "Regex pattern"},
                    "file_pattern": {"type": "string", "description": "File glob pattern", "default": "*"},
                    "max_results": {"type": "integer", "description": "Max results", "default": 50}
                },
                "required": ["path", "pattern"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Execute shell command. Returns stdout, stderr, and return code.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Shell command"},
                    "cwd": {"type": "string", "description": "Working directory", "default": "/www"},
                    "timeout": {"type": "integer", "description": "Timeout seconds", "default": 30}
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_file_info",
            "description": "Get file metadata: exists, is_file, is_dir, size, modified, permissions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to check"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_directory",
            "description": "Create directory and any parent directories if needed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path to create"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_file",
            "description": "Delete a file or directory. Cannot be undone!",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to delete"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the internet using DuckDuckGo. Returns a list of results with title, url, and snippet. Use this to find current information, news, or pages on the web.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query"},
                    "max_results": {"type": "integer", "description": "Max results", "default": 5}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_fetch",
            "description": "Fetch the text content of a web page/URL (HTML stripped to readable text). Use this to read articles, docs, or pages found via web_search.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The URL to fetch"},
                    "max_chars": {"type": "integer", "description": "Max characters of text to return", "default": 4000}
                },
                "required": ["url"]
            }
        }
    }
]


def web_search_impl(query: str, max_results: int = 5) -> Dict[str, Any]:
    """Search the web via Bing (no API key needed). Returns title, real URL, snippet."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9"
        }
        resp = requests.get(
            "https://www.bing.com/search",
            params={"q": query, "setlang": "en", "cc": "US", "mkt": "en-US"},
            headers=headers,
            timeout=20
        )
        if resp.status_code != 200:
            return {"success": False, "error": f"Search failed: HTTP {resp.status_code}"}
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "html.parser")
        import urllib.parse
        results = []
        for li in soup.select("#b_results > li"):
            a = li.select_one("h2 a")
            if not a:
                continue
            title = a.get_text(strip=True)
            href = a.get("href", "")
            # Decode Bing redirect links
            if href.startswith("https://www.bing.com/ck/a") or href.startswith("http://www.bing.com/ck/a"):
                parsed = urllib.parse.urlparse(href)
                qp = urllib.parse.parse_qs(parsed.query)
                if qp.get("u"):
                    raw = qp["u"][0]
                    import base64
                    try:
                        if raw.startswith("a1"):
                            decoded = base64.urlsafe_b64decode(raw[2:] + "===").decode("utf-8", "replace")
                        else:
                            decoded = base64.urlsafe_b64decode(raw + "===").decode("utf-8", "replace")
                        if decoded.startswith("http"):
                            href = decoded
                    except Exception:
                        pass
                elif qp.get("p"):
                    href = urllib.parse.unquote(qp["p"][0])
            sn = li.select_one(".b_caption p")
            snippet = sn.get_text(strip=True)[:300] if sn else ""
            results.append({"title": title, "url": href, "snippet": snippet})
            if len(results) >= max_results:
                break
        if not results:
            return {"success": False, "error": "No search results found"}
        return {"success": True, "query": query, "results": results}
    except Exception as e:
        return {"success": False, "error": str(e)[:300]}


def web_fetch_impl(url: str, max_chars: int = 4000) -> Dict[str, Any]:
    """Fetch a URL and return readable text (HTML stripped)."""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"}
        resp = requests.get(url, headers=headers, timeout=30, verify=False)
        if resp.status_code != 200:
            return {"success": False, "error": f"HTTP {resp.status_code}"}
        content_type = resp.headers.get("Content-Type", "")
        text = resp.text
        if "json" in content_type:
            try:
                return {"success": True, "url": url, "content": json.dumps(resp.json())[:max_chars]}
            except Exception:
                pass
        if "html" in content_type or "<html" in text.lower()[:1000] or "<div" in text.lower()[:1000]:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(text, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
                tag.decompose()
            text = soup.get_text(separator="\n", strip=True)
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        return {"success": True, "url": url, "content": text[:max_chars]}
    except Exception as e:
        return {"success": False, "error": str(e)[:300]}


def execute_tool(tool_name: str, arguments: dict, project_path: str = "/www") -> Any:
    """Execute a tool and return its result."""
    
    def normalize_path(path):
        """Normalize path to be within project directory."""
        if not path:
            return project_path
        if os.path.isabs(path):
            # If absolute path, check if it's within project_path
            abs_project = os.path.abspath(project_path)
            abs_path = os.path.abspath(path)
            # If path starts with project_path, use it as-is
            if abs_path.startswith(abs_project):
                return path
            # Otherwise, use project_path as base
            return os.path.join(project_path, os.path.basename(path))
        return os.path.join(project_path, path)
    
    if tool_name == "read_file":
        path = normalize_path(arguments.get("path", ""))
        return read_file(path, arguments.get("offset", 0), arguments.get("limit", 200))

    elif tool_name == "write_file":
        path = normalize_path(arguments.get("path", ""))
        return write_file(path, arguments.get("content", ""))

    elif tool_name == "edit_file":
        path = normalize_path(arguments.get("path", ""))
        return edit_file(path, arguments.get("old_text", ""), arguments.get("new_text", ""))

    elif tool_name == "list_directory":
        path = normalize_path(arguments.get("path", project_path))
        return list_directory(path, arguments.get("max_depth", 2))

    elif tool_name == "search_files":
        path = normalize_path(arguments.get("path", project_path))
        return search_files(
            path,
            arguments.get("pattern", ""),
            arguments.get("file_pattern", "*"),
            arguments.get("max_results", 50)
        )

    elif tool_name == "run_command":
        cwd = normalize_path(arguments.get("cwd", project_path))
        return run_command(arguments.get("command", ""), cwd, arguments.get("timeout", 30))

    elif tool_name == "get_file_info":
        path = normalize_path(arguments.get("path", ""))
        return get_file_info(path)

    elif tool_name == "create_directory":
        path = normalize_path(arguments.get("path", ""))
        return create_directory(path)

    elif tool_name == "delete_file":
        path = normalize_path(arguments.get("path", ""))
        return delete_file(path)

    elif tool_name == "web_search":
        return web_search_impl(arguments.get("query", ""), arguments.get("max_results", 5))

    elif tool_name == "web_fetch":
        return web_fetch_impl(arguments.get("url", ""), arguments.get("max_chars", 4000))

    return {"error": f"Unknown tool: {tool_name}"}


PROVIDER_URLS = {
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com/v1",
    "nvidia": "https://integrate.api.nvidia.com/v1",
    "groq": "https://api.groq.com/openai/v1",
    "deepseek": "https://api.deepseek.com/v1",
    "mistral": "https://api.mistral.ai/v1",
    "together": "https://api.together.xyz/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "llamacpp": "http://localhost:8080",
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

    def _build_payload(self, messages: List[Dict], tools: List[Dict] = None,
                       tool_choice: str = "auto", max_tokens: int = 4096) -> dict:
        if self.provider_type == "anthropic":
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
                "max_tokens": max_tokens
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
            return payload

    def chat(self, messages: List[Dict], tools: List[Dict] = None,
             tool_choice: str = "auto", max_tokens: int = 4096) -> Dict[str, Any]:
        url = self._build_url()
        headers = self._build_headers()
        payload = self._build_payload(messages, tools, tool_choice, max_tokens)

        try:
            with httpx.Client(timeout=180.0, verify=False) as client:
                resp = client.post(url, json=payload, headers=headers)

                if resp.status_code != 200:
                    error_text = resp.text[:500]
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
                    content = message.get("content", "")
                    tool_calls = message.get("tool_calls")
                    
                    # Parse tool calls from content if small model returns them as text
                    if not tool_calls and content and '{"type":"function"' in content:
                        try:
                            import re
                            tool_pattern = r'\{"type":"function","function":\{[^}]+\}\}'
                            matches = re.findall(tool_pattern, content)
                            if matches:
                                tool_calls = []
                                for i, m in enumerate(matches):
                                    tc = json.loads(m)
                                    tc["id"] = f"call_{i}"
                                    tool_calls.append(tc)
                                content = ""  # Clear content since it's tool calls
                        except Exception:
                            pass
                    
                    return {
                        "success": True,
                        "content": content,
                        "tool_calls": tool_calls,
                        "finish_reason": choice.get("finish_reason"),
                        "tokens": usage.get("total_tokens", 0)
                    }
        except httpx.TimeoutException:
            return {"success": False, "error": "Request timed out (180s)"}
        except httpx.ConnectError as e:
            return {"success": False, "error": f"Connection failed: {str(e)[:150]}"}
        except Exception as e:
            return {"success": False, "error": f"Error: {str(e)[:200]}"}


def run_agent_turn(session: AgentSession, user_message: str, db=None, provider_id: str = None) -> Dict[str, Any]:
    """Run a single turn in the agent session."""
    if db is None:
        from src.models.engine import get_db_session
        sessions = get_db_session()
        for s in sessions:
            db = s
            break

    provider = None
    if provider_id:
        provider = db.query(AgentProvider).filter_by(id=provider_id).first()
        if provider:
            session.provider_id = provider_id
            db.commit()
    
    if not provider and session.provider_id:
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

    # Use shorter prompt for small local models
    is_small_model = provider.provider_type in ("ollama", "llamacpp")
    if is_small_model:
        system_prompt = "You are a coding agent. Reply concisely. Do NOT use function calls - just answer directly."
        tools = None  # Don't send tools to small models - they cause format errors
    else:
        system_prompt = SYSTEM_PROMPT_BUILD if session.mode == "build" else SYSTEM_PROMPT_PLAN
        tools = TOOL_DEFINITIONS

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
    max_iterations = 20 if not is_small_model else 5  # Fewer iterations for small models

    for iteration in range(max_iterations):
        response = agent.chat(messages, tools, "auto")

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
