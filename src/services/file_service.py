import os
import re
import subprocess
import fnmatch
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime


IGNORE_DIRS = {
    '.git', 'node_modules', '__pycache__', '.venv', 'venv', 'env',
    '.idea', '.vscode', 'dist', 'build', '.next', '.nuxt',
    'vendor', 'target', '.gradle', '.maven', 'coverage',
    '.tox', 'eggs', '*.egg-info', '.mypy_cache', '.pytest_cache'
}

IGNORE_FILES = {
    '*.pyc', '*.pyo', '*.class', '*.o', '*.so', '*.dylib',
    '*.exe', '*.dll', '*.bin', '*.dat', '*.db', '*.sqlite',
    '*.jpg', '*.jpeg', '*.png', '*.gif', '*.ico', '*.svg',
    '*.mp3', '*.mp4', '*.avi', '*.mov', '*.wav',
    '*.zip', '*.tar', '*.gz', '*.rar', '*.7z',
    '*.pdf', '*.doc', '*.docx', '*.xls', '*.xlsx',
    '.DS_Store', 'Thumbs.db'
}


def should_ignore(path: str, is_dir: bool = False) -> bool:
    name = os.path.basename(path)
    if is_dir:
        return name in IGNORE_DIRS or name.startswith('.')
    for pattern in IGNORE_FILES:
        if fnmatch.fnmatch(name, pattern):
            return True
    return False


def list_directory(path: str, max_depth: int = 3, current_depth: int = 0) -> List[Dict[str, Any]]:
    items = []
    try:
        entries = sorted(os.listdir(path))
    except PermissionError:
        return [{"name": "Permission Denied", "path": path, "type": "error"}]

    for entry in entries:
        full_path = os.path.join(path, entry)
        is_dir = os.path.isdir(full_path)

        if should_ignore(full_path, is_dir):
            continue

        item = {
            "name": entry,
            "path": full_path,
            "type": "directory" if is_dir else "file",
            "size": os.path.getsize(full_path) if not is_dir else 0,
        }

        if is_dir and current_depth < max_depth:
            item["children"] = list_directory(full_path, max_depth, current_depth + 1)

        items.append(item)

    return items


def read_file(path: str, offset: int = 0, limit: int = 500) -> Dict[str, Any]:
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()

        total_lines = len(lines)
        selected = lines[offset:offset + limit]
        content = ''.join(selected)

        return {
            "success": True,
            "content": content,
            "total_lines": total_lines,
            "offset": offset,
            "limit": limit,
            "has_more": offset + limit < total_lines
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def write_file(path: str, content: str) -> Dict[str, Any]:
    try:
        os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        return {"success": True, "message": f"Written {len(content)} bytes to {path}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def edit_file(path: str, old_text: str, new_text: str) -> Dict[str, Any]:
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()

        if old_text not in content:
            return {"success": False, "error": "Old text not found in file"}

        count = content.count(old_text)
        new_content = content.replace(old_text, new_text, 1)

        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_content)

        return {
            "success": True,
            "message": f"Replaced {count} occurrence(s)",
            "changes_made": True
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def search_files(path: str, pattern: str, file_pattern: str = "*",
                 max_results: int = 50, case_sensitive: bool = False) -> List[Dict[str, Any]]:
    results = []
    flags = 0 if case_sensitive else re.IGNORECASE

    try:
        regex = re.compile(pattern, flags)
    except re.error:
        return [{"error": f"Invalid regex pattern: {pattern}"}]

    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if not should_ignore(os.path.join(root, d), True)]

        for fname in files:
            if not fnmatch.fnmatch(fname, file_pattern):
                continue
            if should_ignore(os.path.join(root, fname)):
                continue

            fpath = os.path.join(root, fname)
            try:
                with open(fpath, 'r', encoding='utf-8', errors='replace') as f:
                    for i, line in enumerate(f, 1):
                        if regex.search(line):
                            results.append({
                                "file": fpath,
                                "line": i,
                                "content": line.rstrip()[:200]
                            })
                            if len(results) >= max_results:
                                return results
            except Exception:
                continue

    return results


def run_command(command: str, cwd: str = "/www", timeout: int = 30) -> Dict[str, Any]:
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=timeout
        )
        return {
            "success": True,
            "stdout": result.stdout[:10000],
            "stderr": result.stderr[:5000],
            "returncode": result.returncode
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"Command timed out after {timeout}s"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_file_info(path: str) -> Dict[str, Any]:
    try:
        stat = os.stat(path)
        return {
            "exists": True,
            "is_file": os.path.isfile(path),
            "is_dir": os.path.isdir(path),
            "size": stat.st_size,
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "permissions": oct(stat.st_mode)[-3:]
        }
    except Exception:
        return {"exists": False}


def create_directory(path: str) -> Dict[str, Any]:
    try:
        os.makedirs(path, exist_ok=True)
        return {"success": True, "message": f"Created directory: {path}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def delete_file(path: str) -> Dict[str, Any]:
    try:
        if os.path.isfile(path):
            os.remove(path)
            return {"success": True, "message": f"Deleted file: {path}"}
        elif os.path.isdir(path):
            import shutil
            shutil.rmtree(path)
            return {"success": True, "message": f"Deleted directory: {path}"}
        return {"success": False, "error": "Path not found"}
    except Exception as e:
        return {"success": False, "error": str(e)}
