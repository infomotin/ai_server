import os
import json
import requests
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, Response, make_response
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "openlocalai-prod-secret-2024")
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = False

API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")
INTERNAL_API_KEY = os.environ.get("INTERNAL_API_KEY", "sk-local-8312f2f4a129c8b7d02d65583929e61747c459f0c7e1bd2d67976abf2835625b")


def get_api_headers():
    headers = {"Content-Type": "application/json"}
    if "access_token" in session:
        headers["Authorization"] = f"Bearer {session['access_token']}"
    elif INTERNAL_API_KEY:
        headers["Authorization"] = f"Bearer {INTERNAL_API_KEY}"
    return headers


def _proxy_request(method, url, timeout=30):
    headers = get_api_headers()
    if method == "GET":
        return requests.get(url, headers=headers, params=request.args, timeout=timeout)
    if method == "POST":
        return requests.post(url, headers=headers, json=request.get_json(silent=True) or {}, params=request.args, timeout=timeout)
    if method == "PUT":
        return requests.put(url, headers=headers, json=request.get_json(silent=True) or {}, params=request.args, timeout=timeout)
    if method == "DELETE":
        return requests.delete(url, headers=headers, params=request.args, timeout=timeout)
    return None


def _handle_proxy_response(resp):
    try:
        data = resp.json()
    except ValueError:
        data = {"error": resp.text[:500]}
    if resp.status_code == 401 and isinstance(data, dict) and "Invalid or expired" in str(data.get("detail", "")):
        session.clear()
    return data, resp.status_code


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        data = {
            "username": request.form["username"],
            "email": request.form["email"],
            "password": request.form["password"]
        }

        try:
            response = requests.post(
                f"{API_BASE_URL}/auth/register",
                json=data,
                timeout=10
            )

            if response.status_code == 201:
                result = response.json()
                session["access_token"] = result["access_token"]
                session["user"] = result["user"]
                flash("Registration successful!", "success")
                return redirect(url_for("dashboard"))
            else:
                error = response.json().get("detail", "Registration failed")
                flash(error, "error")
        except requests.exceptions.RequestException as e:
            flash(f"Connection error: {str(e)}", "error")

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        data = {
            "email": request.form["email"],
            "password": request.form["password"]
        }

        try:
            response = requests.post(
                f"{API_BASE_URL}/auth/login",
                json=data,
                timeout=10
            )

            if response.status_code == 200:
                result = response.json()
                session["access_token"] = result["access_token"]
                session["user"] = result["user"]
                flash("Login successful!", "success")
                return redirect(url_for("dashboard"))
            else:
                error = response.json().get("detail", "Login failed")
                flash(error, "error")
        except requests.exceptions.RequestException as e:
            flash(f"Connection error: {str(e)}", "error")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out", "info")
    return redirect(url_for("index"))


@app.route("/dashboard")
def dashboard():
    if "access_token" not in session:
        return redirect(url_for("login"))

    try:
        keys_response = requests.get(
            f"{API_BASE_URL}/keys",
            headers=get_api_headers(),
            timeout=10
        )
        api_keys = keys_response.json() if keys_response.status_code == 200 else []

        settings_response = requests.get(
            f"{API_BASE_URL}/settings",
            headers=get_api_headers(),
            timeout=10
        )
        user_settings = settings_response.json() if settings_response.status_code == 200 else None

        skills_response = requests.get(
            f"{API_BASE_URL}/skills",
            headers=get_api_headers(),
            timeout=10
        )
        skills = skills_response.json() if skills_response.status_code == 200 else []

        data_response = requests.get(
            f"{API_BASE_URL}/data",
            headers=get_api_headers(),
            timeout=10
        )
        data_sources = data_response.json() if data_response.status_code == 200 else []

        usage = None
        if api_keys:
            usage_response = requests.get(
                f"{API_BASE_URL}/keys/{api_keys[0]['id']}/usage",
                headers=get_api_headers(),
                timeout=10
            )
            usage = usage_response.json() if usage_response.status_code == 200 else None

    except requests.exceptions.RequestException:
        api_keys = []
        user_settings = None
        skills = []
        data_sources = []
        usage = None

    return render_template(
        "dashboard.html",
        user=session.get("user"),
        api_keys=api_keys,
        user_settings=user_settings,
        skills=skills,
        data_sources=data_sources,
        usage=usage
    )


@app.route("/keys", methods=["GET", "POST"])
def manage_keys():
    if "access_token" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        data = {
            "name": request.form["name"],
            "rate_limit": int(request.form.get("rate_limit", 60))
        }

        try:
            response = requests.post(
                f"{API_BASE_URL}/keys",
                json=data,
                headers=get_api_headers(),
                timeout=10
            )

            if response.status_code == 201:
                result = response.json()
                flash(f"API Key created! Secret: {result['secret_key']}", "success")
            else:
                flash("Failed to create API key", "error")
        except requests.exceptions.RequestException as e:
            flash(f"Connection error: {str(e)}", "error")

    try:
        response = requests.get(
            f"{API_BASE_URL}/keys",
            headers=get_api_headers(),
            timeout=10
        )
        api_keys = response.json() if response.status_code == 200 else []
    except requests.exceptions.RequestException:
        api_keys = []

    return render_template("api_keys.html", api_keys=api_keys)


@app.route("/keys/<key_id>/delete", methods=["POST"])
def delete_key(key_id):
    if "access_token" not in session:
        return redirect(url_for("login"))

    try:
        response = requests.delete(
            f"{API_BASE_URL}/keys/{key_id}",
            headers=get_api_headers(),
            timeout=10
        )

        if response.status_code == 204:
            flash("API key revoked", "success")
        else:
            flash("Failed to revoke API key", "error")
    except requests.exceptions.RequestException as e:
        flash(f"Connection error: {str(e)}", "error")

    return redirect(url_for("manage_keys"))


OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")


@app.route("/api/management/default-model", methods=["GET", "POST"])
def api_default_model():
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    if request.method == "GET":
        try:
            r = requests.get(f"{API_BASE_URL}/settings", headers=get_api_headers(), timeout=5)
            data = r.json() if r.status_code == 200 else {}
            return jsonify({"model": data.get("default_model")})
        except requests.exceptions.RequestException:
            return jsonify({"model": None})
    data = request.get_json(silent=True) or {}
    model = data.get("model")
    if not model:
        return jsonify({"error": "model required"}), 400
    try:
        r = requests.post(f"{API_BASE_URL}/settings/model",
                          json={"model": model},
                          headers=get_api_headers(), timeout=10)
        if r.status_code == 200:
            return r.json()
        return jsonify({"error": r.text[:300]}), r.status_code
    except requests.exceptions.RequestException as e:
        return jsonify({"error": str(e)[:200]}), 500


@app.route("/api/ollama/create", methods=["POST"])
def api_ollama_create():
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    name = data.get("name")
    modelfile = data.get("modelfile")
    folder = data.get("folder", "/www/AI_server/models")
    if not name or not modelfile:
        return jsonify({"error": "name and modelfile required"}), 400

    try:
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/create",
            json={"name": name, "modelfile": modelfile},
            stream=True,
            timeout=300
        )
        last = {}
        for line in resp.iter_lines():
            if not line:
                continue
            try:
                last = json.loads(line.decode("utf-8"))
            except Exception:
                pass
        return jsonify(last or {"success": resp.status_code == 200})
    except requests.exceptions.RequestException as e:
        return jsonify({"error": str(e)[:200]}), 500


@app.route("/api/ollama/status")
def api_ollama_status():
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        r = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        if r.status_code == 200:
            return {"online": True, "version": r.headers.get("server", "ok")}
        return {"online": False}
    except requests.exceptions.RequestException as e:
        return {"online": False, "error": str(e)[:200]}


@app.route("/api/ollama/tags")
def api_ollama_tags():
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        r = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=10)
        return r.json() if r.status_code == 200 else {"models": []}
    except requests.exceptions.RequestException as e:
        return {"models": [], "error": str(e)[:200]}


@app.route("/api/ollama/ps")
def api_ollama_ps():
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        r = requests.get(f"{OLLAMA_BASE_URL}/api/ps", timeout=5)
        return r.json() if r.status_code == 200 else {"models": []}
    except requests.exceptions.RequestException:
        return {"models": []}


@app.route("/api/ollama/show")
def api_ollama_show():
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    name = request.args.get("name")
    if not name:
        return jsonify({"error": "name required"}), 400
    try:
        r = requests.post(f"{OLLAMA_BASE_URL}/api/show", json={"name": name}, timeout=15)
        return r.json() if r.status_code == 200 else {"error": r.text[:300]}
    except requests.exceptions.RequestException as e:
        return jsonify({"error": str(e)[:200]}), 500


@app.route("/api/ollama/delete", methods=["POST"])
def api_ollama_delete():
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    name = data.get("name")
    if not name:
        return jsonify({"error": "name required"}), 400
    try:
        r = requests.delete(f"{OLLAMA_BASE_URL}/api/delete", json={"name": name}, timeout=60)
        if r.status_code == 200:
            return {"success": True}
        return jsonify({"error": r.text[:300]}), r.status_code
    except requests.exceptions.RequestException as e:
        return jsonify({"error": str(e)[:200]}), 500


@app.route("/api/ollama/pull", methods=["POST"])
def api_ollama_pull():
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name required"}), 400

    def generate():
        try:
            with requests.post(
                f"{OLLAMA_BASE_URL}/api/pull",
                json={"name": name, "stream": True},
                stream=True,
                timeout=None
            ) as resp:
                for line in resp.iter_lines():
                    if not line:
                        continue
                    try:
                        payload = json.loads(line.decode("utf-8"))
                    except Exception:
                        continue
                    yield "data: " + json.dumps(payload) + "\n\n"
                yield "data: " + json.dumps({"status": "success", "done": True}) + "\n\n"
        except requests.exceptions.RequestException as e:
            yield "data: " + json.dumps({"error": str(e)[:200]}) + "\n\n"

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.route("/api/models/local")
def api_models_local():
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    base = "/www/AI_server/models"
    entries = []
    try:
        for name in os.listdir(base):
            full = os.path.join(base, name)
            if not os.path.isdir(full):
                continue
            size = 0
            file_count = 0
            gguf_files = []
            for root, _, files in os.walk(full):
                for f in files:
                    p = os.path.join(root, f)
                    try:
                        size += os.path.getsize(p)
                        file_count += 1
                        if f.endswith(".gguf"):
                            gguf_files.append(os.path.relpath(p, full))
                    except OSError:
                        pass
            entries.append({
                "name": name,
                "path": full,
                "size_bytes": size,
                "file_count": file_count,
                "gguf_files": gguf_files[:5]
            })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    return jsonify({"models": entries, "base_dir": base})


@app.route("/api/models/trained")
def api_models_trained():
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        resp = requests.get(f"{API_BASE_URL}/model-builder/custom-models",
                            headers=get_api_headers(), timeout=10)
        if resp.status_code == 200:
            return resp.json()
        return []
    except requests.exceptions.RequestException:
        return []


@app.route("/api/models/library")
def api_models_library():
    """Curated catalog of recommended Ollama models grouped by task."""
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify({
        "chat_small": [
            {"name": "qwen2.5:0.5b", "size": "397MB", "params": "0.5B", "desc": "Ultra-fast general chat, low RAM"},
            {"name": "llama3.2:1b", "size": "1.3GB", "params": "1B", "desc": "Strong tiny model from Meta"},
            {"name": "gemma2:2b", "size": "1.6GB", "params": "2B", "desc": "Google's compact model"},
            {"name": "phi3:mini", "size": "2.3GB", "params": "3.8B", "desc": "Microsoft's small but smart model"},
            {"name": "llama3.2:3b", "size": "2GB", "params": "3B", "desc": "Balanced quality/speed"}
        ],
        "chat_balanced": [
            {"name": "mistral-nemo", "size": "7GB", "params": "12B", "desc": "Best mid-size for general tasks"},
            {"name": "llama3.1:8b", "size": "4.7GB", "params": "8B", "desc": "Industry-standard 8B model"},
            {"name": "gemma2:9b", "size": "5.4GB", "params": "9B", "desc": "Strong reasoning"},
            {"name": "qwen2.5:7b", "size": "4.4GB", "params": "7B", "desc": "Great multilingual"},
            {"name": "mistral:7b", "size": "4.1GB", "params": "7B", "desc": "Classic 7B Mistral"}
        ],
        "chat_large": [
            {"name": "llama3.1:70b", "size": "38GB", "params": "70B", "desc": "Top quality (needs 64GB+ RAM)"},
            {"name": "qwen2.5:32b", "size": "20GB", "params": "32B", "desc": "Excellent multilingual"},
            {"name": "mixtral:8x7b", "size": "26GB", "params": "47B", "desc": "Mixture of experts"},
            {"name": "deepseek-r1:32b", "size": "20GB", "params": "32B", "desc": "Strong reasoning"}
        ],
        "code": [
            {"name": "qwen2.5-coder:1.5b", "size": "1GB", "params": "1.5B", "desc": "Lightweight coding"},
            {"name": "codellama:3.5", "size": "3.5GB", "params": "3.5B", "desc": "Code completion"},
            {"name": "qwen2.5-coder:7b", "size": "4.7GB", "params": "7B", "desc": "Strong coding at 7B"},
            {"name": "deepseek-coder-v2:16b", "size": "8.9GB", "params": "16B", "desc": "Top coding quality"}
        ],
        "embedding": [
            {"name": "nomic-embed-text", "size": "274MB", "params": "137M", "desc": "Best small embedder"},
            {"name": "mxbai-embed-large", "size": "670MB", "params": "335M", "desc": "High quality embeddings"},
            {"name": "all-minilm", "size": "46MB", "params": "22M", "desc": "Tiny embedder"}
        ],
        "vision": [
            {"name": "llama3.2-vision:11b", "size": "7.9GB", "params": "11B", "desc": "Image + text"},
            {"name": "llava:7b", "size": "4.7GB", "params": "7B", "desc": "Classic vision model"},
            {"name": "moondream:1.8b", "size": "1.1GB", "params": "1.8B", "desc": "Tiny vision model"}
        ],
        "reasoning": [
            {"name": "deepseek-r1:1.5b", "size": "1.1GB", "params": "1.5B", "desc": "Reasoning at small size"},
            {"name": "deepseek-r1:7b", "size": "4.7GB", "params": "7B", "desc": "Best mid-size reasoning"},
            {"name": "deepseek-r1:14b", "size": "9GB", "params": "14B", "desc": "Strong reasoning"},
            {"name": "qwq:32b", "size": "20GB", "params": "32B", "desc": "Qwen reasoning model"}
        ],
        "multilingual": [
            {"name": "qwen2.5:7b", "size": "4.4GB", "params": "7B", "desc": "29 languages"},
            {"name": "aya:8b", "size": "4.8GB", "params": "8B", "desc": "23 languages"},
            {"name": "llama3.1:8b", "size": "4.7GB", "params": "8B", "desc": "8 languages"}
        ]
    })


@app.route("/models")
def models():
    if "access_token" not in session:
        return redirect(url_for("login"))

    try:
        response = requests.get(
            f"{API_BASE_URL}/v1/models",
            headers=get_api_headers(),
            timeout=10
        )

        if response.status_code == 200:
            result = response.json()
            models = result.get("data", [])
        else:
            models = []
    except requests.exceptions.RequestException:
        models = []

    settings_response = None
    try:
        settings_response = requests.get(
            f"{API_BASE_URL}/settings",
            headers=get_api_headers(),
            timeout=10
        )
    except:
        pass

    current_model = None
    if settings_response and settings_response.status_code == 200:
        current_model = settings_response.json().get("default_model")

    return render_template("models.html", models=models, current_model=current_model)


@app.route("/models/switch", methods=["POST"])
def switch_model():
    if "access_token" not in session:
        return redirect(url_for("login"))

    model = request.form.get("model")
    if not model:
        flash("No model specified", "error")
        return redirect(url_for("models"))

    try:
        response = requests.post(
            f"{API_BASE_URL}/settings/model",
            json={"model": model},
            headers=get_api_headers(),
            timeout=10
        )

        if response.status_code == 200:
            flash(f"Default model switched to {model}", "success")
        else:
            flash("Failed to switch model", "error")
    except requests.exceptions.RequestException as e:
        flash(f"Connection error: {str(e)}", "error")

    return redirect(url_for("models"))


@app.route("/models/download", methods=["POST"])
def download_model():
    if "access_token" not in session:
        return redirect(url_for("login"))

    model = request.form.get("model")
    if not model:
        flash("No model specified", "error")
        return redirect(url_for("models"))

    try:
        response = requests.post(
            f"{API_BASE_URL}/v1/models/{model}/download",
            headers=get_api_headers(),
            timeout=10
        )

        if response.status_code == 200:
            flash(f"Model {model} download started", "success")
        else:
            flash("Failed to start model download", "error")
    except requests.exceptions.RequestException as e:
        flash(f"Connection error: {str(e)}", "error")

    return redirect(url_for("models"))


@app.route("/models/ollama/pull", methods=["POST"])
def ollama_pull():
    if "access_token" not in session:
        return redirect(url_for("login"))

    model = request.form.get("model")
    if not model:
        flash("No model specified", "error")
        return redirect(url_for("models"))

    try:
        import subprocess
        flash(f"Pulling model {model}... This may take a while.", "info")
        subprocess.Popen(
            ["ollama", "pull", model],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    except Exception as e:
        flash(f"Failed to start pull: {str(e)}", "error")

    return redirect(url_for("models"))


@app.route("/models/ollama/sync", methods=["POST"])
def ollama_sync():
    if "access_token" not in session:
        return redirect(url_for("login"))

    try:
        import subprocess
        result = subprocess.run(
            ["ollama", "list", "--format", "json"],
            capture_output=True, text=True, timeout=10
        )
        flash("Models synced with Ollama", "success")
    except Exception as e:
        flash(f"Sync failed: {str(e)}", "error")

    return redirect(url_for("models"))


@app.route("/models/huggingface/download", methods=["POST"])
def huggingface_download():
    if "access_token" not in session:
        return redirect(url_for("login"))

    model_id = request.form.get("model_id")
    file_pattern = request.form.get("file_pattern", "*q4*.gguf")

    if not model_id:
        flash("No model ID specified", "error")
        return redirect(url_for("models"))

    try:
        import subprocess
        import threading

        def download_in_background():
            model_dir = f"/www/AI_server/models/{model_id.replace('/', '_')}"
            os.makedirs(model_dir, exist_ok=True)
            try:
                subprocess.run(
                    ["pip", "install", "huggingface_hub", "sentencepiece"],
                    capture_output=True, timeout=120
                )
                from huggingface_hub import snapshot_download
                snapshot_download(
                    repo_id=model_id,
                    local_dir=model_dir,
                    allow_patterns=[file_pattern],
                    ignore_patterns=["*.txt", "*.md", "*.png", "*.jpg"]
                )
            except Exception:
                pass

        thread = threading.Thread(target=download_in_background, daemon=True)
        thread.start()
        flash(f"Downloading {model_id} ({file_pattern}) in background...", "info")
    except Exception as e:
        flash(f"Download failed: {str(e)}", "error")

    return redirect(url_for("models"))


@app.route("/models/upload", methods=["POST"])
def upload_model():
    if "access_token" not in session:
        return redirect(url_for("login"))

    model_name = request.form.get("model_name")
    model_file = request.files.get("model_file")

    if not model_name or not model_file:
        flash("Model name and file are required", "error")
        return redirect(url_for("models"))

    try:
        model_dir = f"/www/AI_server/models/{model_name}"
        os.makedirs(model_dir, exist_ok=True)
        file_path = os.path.join(model_dir, model_file.filename)
        model_file.save(file_path)

        flash(f"Model '{model_name}' uploaded to {file_path}", "success")
    except Exception as e:
        flash(f"Upload failed: {str(e)}", "error")

    return redirect(url_for("models"))


@app.route("/skills")
def manage_skills():
    if "access_token" not in session:
        return redirect(url_for("login"))

    try:
        response = requests.get(
            f"{API_BASE_URL}/skills",
            headers=get_api_headers(),
            timeout=10
        )
        skills = response.json() if response.status_code == 200 else []
    except requests.exceptions.RequestException:
        skills = []

    return render_template("skills.html", skills=skills)


@app.route("/skills/create", methods=["POST"])
def create_skill():
    if "access_token" not in session:
        return redirect(url_for("login"))

    data = {
        "name": request.form["name"],
        "description": request.form.get("description", ""),
        "system_prompt": request.form["system_prompt"]
    }

    try:
        response = requests.post(
            f"{API_BASE_URL}/skills",
            json=data,
            headers=get_api_headers(),
            timeout=10
        )

        if response.status_code == 201:
            flash("Skill created successfully!", "success")
        else:
            error = response.json().get("detail", "Failed to create skill")
            flash(error, "error")
    except requests.exceptions.RequestException as e:
        flash(f"Connection error: {str(e)}", "error")

    return redirect(url_for("manage_skills"))


@app.route("/skills/<skill_id>/delete", methods=["POST"])
def delete_skill(skill_id):
    if "access_token" not in session:
        return redirect(url_for("login"))

    try:
        response = requests.delete(
            f"{API_BASE_URL}/skills/{skill_id}",
            headers=get_api_headers(),
            timeout=10
        )

        if response.status_code == 204:
            flash("Skill deleted", "success")
        else:
            flash("Failed to delete skill", "error")
    except requests.exceptions.RequestException as e:
        flash(f"Connection error: {str(e)}", "error")

    return redirect(url_for("manage_skills"))


@app.route("/api/skills/<skill_id>/test", methods=["POST"])
def api_test_skill(skill_id):
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    try:
        resp = requests.post(
            f"{API_BASE_URL}/skills/{skill_id}/test",
            json=data,
            headers=get_api_headers(),
            timeout=60
        )
        return jsonify(resp.json()), resp.status_code
    except requests.exceptions.RequestException as e:
        return jsonify({"success": False, "error": str(e)[:300]}), 500


# ============= Programming Hub Routes =============

@app.route("/programming")
def programming_hub():
    if "access_token" not in session:
        return redirect(url_for("login"))
    return render_template("programming.html")


@app.route("/api/programming/run", methods=["POST"])
def api_run_code():
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    import subprocess, time, tempfile, os
    data = request.get_json(silent=True) or {}
    code = data.get("code", "")
    lang = data.get("language", "python")

    if not code.strip():
        return jsonify({"success": False, "error": "No code provided"}), 400

    start = time.time()

    try:
        if lang == "python":
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, dir='/tmp') as f:
                f.write(code)
                f.flush()
                result = subprocess.run(
                    ['python3', f.name],
                    capture_output=True, text=True, timeout=15,
                    cwd='/tmp', env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'}
                )
                os.unlink(f.name)
                elapsed = round((time.time() - start) * 1000)
                return jsonify({
                    "success": result.returncode == 0,
                    "stdout": result.stdout[-5000:] if result.stdout else "",
                    "stderr": result.stderr[-3000:] if result.stderr else "",
                    "language": "python",
                    "latency_ms": elapsed,
                    "exit_code": result.returncode
                })

        elif lang == "javascript":
            with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False, dir='/tmp') as f:
                f.write(code)
                f.flush()
                result = subprocess.run(
                    ['node', f.name],
                    capture_output=True, text=True, timeout=15,
                    cwd='/tmp'
                )
                os.unlink(f.name)
                elapsed = round((time.time() - start) * 1000)
                return jsonify({
                    "success": result.returncode == 0,
                    "stdout": result.stdout[-5000:] if result.stdout else "",
                    "stderr": result.stderr[-3000:] if result.stderr else "",
                    "language": "javascript",
                    "latency_ms": elapsed,
                    "exit_code": result.returncode
                })

        elif lang == "bash":
            with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False, dir='/tmp') as f:
                f.write(code)
                f.flush()
                result = subprocess.run(
                    ['bash', f.name],
                    capture_output=True, text=True, timeout=15,
                    cwd='/tmp'
                )
                os.unlink(f.name)
                elapsed = round((time.time() - start) * 1000)
                return jsonify({
                    "success": result.returncode == 0,
                    "stdout": result.stdout[-5000:] if result.stdout else "",
                    "stderr": result.stderr[-3000:] if result.stderr else "",
                    "language": "bash",
                    "latency_ms": elapsed,
                    "exit_code": result.returncode
                })

        else:
            return jsonify({"success": False, "error": f"Unsupported language: {lang}"}), 400

    except subprocess.TimeoutExpired:
        return jsonify({"success": False, "error": "Code execution timed out (15s limit)", "latency_ms": 15000})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)[:500], "latency_ms": round((time.time() - start) * 1000)})


@app.route("/api/programming/explain", methods=["POST"])
def api_explain_code():
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    code = data.get("code", "")
    model = data.get("model", "qwen2.5-coder:1.5b")

    if not code.strip():
        return jsonify({"success": False, "error": "No code provided"}), 400

    import time
    start = time.time()

    try:
        resp = requests.post(
            "http://localhost:11434/api/chat",
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": "You are an expert programming teacher. Explain code step by step in simple terms. Describe what each part does, the overall logic, input/output, time complexity, and potential improvements. Use clear formatting with bullet points. Also provide a trace table showing variable values at each step."},
                    {"role": "user", "content": f"Explain this code in detail with variable trace:\n\n{code}"}
                ],
                "stream": False
            },
            timeout=60
        )
        elapsed = round((time.time() - start) * 1000)

        if resp.status_code == 200:
            result = resp.json()
            reply = result.get("message", {}).get("content", "No response")
            tokens = result.get("eval_count", 0)
            return jsonify({"success": True, "explanation": reply, "tokens": tokens, "latency_ms": elapsed, "model": model})
        else:
            return jsonify({"success": False, "error": "Ollama error", "latency_ms": elapsed})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)[:300], "latency_ms": round((time.time() - start) * 1000)})


@app.route("/api/programming/book-qa", methods=["POST"])
def api_book_qa():
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    book_text = data.get("book_text", "")
    book_title = data.get("book_title", "Unknown Book")
    model = data.get("model", "qwen2.5-coder:1.5b")

    if not book_text.strip():
        return jsonify({"success": False, "error": "No book text provided"}), 400

    import time
    start = time.time()

    try:
        resp = requests.post(
            "http://localhost:11434/api/chat",
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": f"You are a book analysis expert. Analyze the book '{book_title}' and generate: 1) A brief summary (3-5 sentences) 2) Key themes and ideas 3) 10 quiz questions with answers 4) Character analysis 5) Important quotes 6) Critical thinking questions. Format everything clearly with markdown."},
                    {"role": "user", "content": f"Analyze this book content and generate Q&A:\n\n{book_text[:6000]}"}
                ],
                "stream": False
            },
            timeout=90
        )
        elapsed = round((time.time() - start) * 1000)

        if resp.status_code == 200:
            result = resp.json()
            reply = result.get("message", {}).get("content", "No response")
            tokens = result.get("eval_count", 0)
            return jsonify({"success": True, "analysis": reply, "tokens": tokens, "latency_ms": elapsed, "model": model})
        else:
            return jsonify({"success": False, "error": "Ollama error", "latency_ms": elapsed})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)[:300], "latency_ms": round((time.time() - start) * 1000)})


@app.route("/api/programming/skill-test", methods=["POST"])
def api_programming_skill_test():
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    topic = data.get("topic", "python")
    difficulty = data.get("difficulty", "medium")
    model = data.get("model", "qwen2.5-coder:1.5b")

    import time
    start = time.time()

    try:
        resp = requests.post(
            "http://localhost:11434/api/chat",
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": f"You are a programming exam creator. Generate a {difficulty} level programming quiz on {topic}. Create 5 questions mixing multiple choice, code completion, and debugging challenges. For each question provide: question, options (if MC), correct answer, and explanation. Format as JSON array."},
                    {"role": "user", "content": f"Generate a {difficulty} {topic} programming quiz with 5 questions. Include code snippets where relevant."}
                ],
                "stream": False
            },
            timeout=60
        )
        elapsed = round((time.time() - start) * 1000)

        if resp.status_code == 200:
            result = resp.json()
            reply = result.get("message", {}).get("content", "No response")
            tokens = result.get("eval_count", 0)
            return jsonify({"success": True, "quiz": reply, "tokens": tokens, "latency_ms": elapsed, "model": model, "topic": topic, "difficulty": difficulty})
        else:
            return jsonify({"success": False, "error": "Ollama error", "latency_ms": elapsed})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)[:300], "latency_ms": round((time.time() - start) * 1000)})


@app.route("/api/programming/sql-explain", methods=["POST"])
def api_sql_explain():
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    code = data.get("code", "")
    model = data.get("model", "qwen2.5-coder:1.5b")

    if not code.strip():
        return jsonify({"success": False, "error": "No SQL provided"}), 400

    import time
    start = time.time()

    try:
        resp = requests.post(
            "http://localhost:11434/api/chat",
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": "You are a SQL expert. Analyze this SQL query and explain: 1) What the query does step by step, 2) Tables and joins used, 3) WHERE conditions and filters, 4) GROUP BY and HAVING logic, 5) Performance tips, 6) Potential issues, 7) How to optimize it. Use clear formatting with examples."},
                    {"role": "user", "content": f"Explain this SQL query in detail:\n\n{code}"}
                ],
                "stream": False
            },
            timeout=60
        )
        elapsed = round((time.time() - start) * 1000)

        if resp.status_code == 200:
            result = resp.json()
            reply = result.get("message", {}).get("content", "No response")
            tokens = result.get("eval_count", 0)
            return jsonify({"success": True, "explanation": reply, "tokens": tokens, "latency_ms": elapsed, "model": model})
        else:
            return jsonify({"success": False, "error": "Ollama error", "latency_ms": elapsed})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)[:300], "latency_ms": round((time.time() - start) * 1000)})


@app.route("/api/programming/book-upload", methods=["POST"])
def api_book_upload():
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    import time, tempfile, os
    start = time.time()
    model = request.form.get("model", "qwen2.5-coder:1.5b")
    book_title = request.form.get("book_title", "Unknown Book")
    mode = request.form.get("mode", "analyze")

    book_text = ""
    if "file" in request.files:
        f = request.files["file"]
        if f.filename:
            content = f.read()
            if f.filename.endswith(".txt"):
                book_text = content.decode("utf-8", errors="ignore")
            elif f.filename.endswith(".pdf"):
                try:
                    import subprocess
                    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                        tmp.write(content)
                        tmp.flush()
                        result = subprocess.run(["pdftotext", tmp.name, "-"], capture_output=True, text=True, timeout=30)
                        book_text = result.stdout
                        os.unlink(tmp.name)
                except Exception:
                    return jsonify({"success": False, "error": "PDF parsing failed. Install poppler-utils: apt install poppler-utils"})
            else:
                book_text = content.decode("utf-8", errors="ignore")[:50000]

    url = request.form.get("url", "")
    if url and not book_text:
        try:
            import subprocess, re
            result = subprocess.run(
                ["curl", "-sL", "--max-time", "15", url],
                capture_output=True, text=True, timeout=20
            )
            book_text = result.stdout[:50000]
            book_text = re.sub(r'<[^>]+>', ' ', book_text)
            book_text = re.sub(r'\s+', ' ', book_text).strip()
        except Exception:
            return jsonify({"success": False, "error": "Failed to fetch URL"})

    if not book_text.strip():
        return jsonify({"success": False, "error": "No content provided"}), 400

    if mode == "quiz":
        prompt = f"Based on this book content, generate 10 quiz questions with 4 options each, correct answer marked with [CORRECT], and explanation. Format as numbered list.\n\nBook: {book_title}\n\nContent:\n{book_text[:6000]}"
    elif mode == "summary":
        prompt = f"Provide a comprehensive summary of '{book_title}'. Include: 1) Overview (2-3 paragraphs) 2) Key themes 3) Main characters/people 4) Important events 5) Lessons learned. Format with markdown.\n\nContent:\n{book_text[:6000]}"
    else:
        prompt = f"Analyze the book '{book_title}' in depth. Include: 1) Summary 2) Themes 3) Character analysis 4) Writing style 5) Historical context 6) Critical analysis 7) Key quotes 8) Quiz questions with answers 9) Discussion questions. Format with markdown.\n\nContent:\n{book_text[:6000]}"

    try:
        resp = requests.post(
            "http://localhost:11434/api/chat",
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": "You are a literary analysis expert and educator. Provide thorough, well-structured analysis with clear formatting."},
                    {"role": "user", "content": prompt}
                ],
                "stream": False
            },
            timeout=90
        )
        elapsed = round((time.time() - start) * 1000)

        if resp.status_code == 200:
            result = resp.json()
            reply = result.get("message", {}).get("content", "No response")
            tokens = result.get("eval_count", 0)
            return jsonify({"success": True, "analysis": reply, "tokens": tokens, "latency_ms": elapsed, "model": model})
        else:
            return jsonify({"success": False, "error": "Ollama error", "latency_ms": elapsed})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)[:300], "latency_ms": round((time.time() - start) * 1000)})


@app.route("/api/programming/visualino", methods=["POST"])
def api_visualino_code():
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    blocks = data.get("blocks", [])
    board = data.get("board", "esp32")
    model = data.get("model", "qwen2.5-coder:1.5b")

    block_desc = "\n".join([f"- {b.get('type','?')}: {b.get('label','')}" for b in blocks])

    import time
    start = time.time()

    try:
        board_info = {
            "esp32": "ESP32 with Arduino framework, WiFi, Bluetooth, GPIO pins, ADC, DAC, PWM",
            "arduino": "Arduino Uno, ATmega328P, digital/analog pins, Serial, I2C, SPI",
            "esp8266": "ESP8266 NodeMCU, WiFi, GPIO, ADC, PWM, limited RAM",
            "stm32": "STM32 Blue Pill, ARM Cortex-M0, GPIO, ADC, UART, SPI, I2C"
        }.get(board, "generic microcontroller")

        resp = requests.post(
            "http://localhost:11434/api/chat",
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": f"You are an expert embedded systems programmer. Generate Arduino/C++ code for {board} ({board_info}). Include proper setup(), loop(), comments, pin definitions, and library imports. Code should be ready to compile and upload."},
                    {"role": "user", "content": f"Generate code for this block program:\n{block_desc}\n\nBoard: {board}\n\nProvide complete, compilable Arduino code with comments."}
                ],
                "stream": False
            },
            timeout=60
        )
        elapsed = round((time.time() - start) * 1000)

        if resp.status_code == 200:
            result = resp.json()
            reply = result.get("message", {}).get("content", "No response")
            tokens = result.get("eval_count", 0)
            return jsonify({"success": True, "code": reply, "tokens": tokens, "latency_ms": elapsed, "model": model, "board": board})
        else:
            return jsonify({"success": False, "error": "Ollama error", "latency_ms": elapsed})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)[:300], "latency_ms": round((time.time() - start) * 1000)})


@app.route("/api/programming/optimize", methods=["POST"])
def api_optimize_query():
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    code = data.get("code", "")
    model = data.get("model", "qwen2.5-coder:1.5b")

    if not code.strip():
        return jsonify({"success": False, "error": "No SQL provided"}), 400

    import time
    start = time.time()

    try:
        resp = requests.post(
            "http://localhost:11434/api/chat",
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": """You are a database performance expert. Analyze this SQL query and provide:
1. PROBLEMS FOUND: List each issue with severity (Critical/Warning/Info)
2. WHY IT'S SLOW: Explain the root cause of each problem (e.g., full table scan, missing index, unnecessary sorting)
3. OPTIMIZED QUERY: Provide the rewritten, faster query
4. INDEXES TO ADD: Specific CREATE INDEX statements with explanation of why each helps
5. EXECUTION PLAN: Describe what the database engine does step by step
6. PERFORMANCE RATING: Score 1-10 with justification
7. EXPECTED IMPROVEMENT: Estimate speedup factor

Be specific, use examples, and explain the WHY behind every suggestion."""},
                    {"role": "user", "content": f"Optimize this SQL query:\n\n{code}"}
                ],
                "stream": False
            },
            timeout=60
        )
        elapsed = round((time.time() - start) * 1000)

        if resp.status_code == 200:
            result = resp.json()
            reply = result.get("message", {}).get("content", "No response")
            tokens = result.get("eval_count", 0)
            return jsonify({"success": True, "optimization": reply, "tokens": tokens, "latency_ms": elapsed, "model": model})
        else:
            return jsonify({"success": False, "error": "Ollama error", "latency_ms": elapsed})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)[:300], "latency_ms": round((time.time() - start) * 1000)})


@app.route("/data")
def manage_data():
    if "access_token" not in session:
        return redirect(url_for("login"))

    try:
        response = requests.get(
            f"{API_BASE_URL}/data",
            headers=get_api_headers(),
            timeout=10
        )
        data_sources = response.json() if response.status_code == 200 else []
    except requests.exceptions.RequestException:
        data_sources = []

    knowledge_bases = []
    try:
        resp = requests.get(f"{API_BASE_URL}/management/knowledge-bases", headers=get_api_headers(), timeout=10)
        if resp.status_code == 200:
            knowledge_bases = resp.json()
    except requests.exceptions.RequestException:
        pass

    return render_template("data.html", data_sources=data_sources, knowledge_bases=knowledge_bases)


@app.route("/data/upload", methods=["POST"])
def upload_data():
    if "access_token" not in session:
        return redirect(url_for("login"))

    if "file" not in request.files:
        flash("No file provided", "error")
        return redirect(url_for("manage_data"))

    file = request.files["file"]
    name = request.form.get("name", file.filename)

    if file.filename == "":
        flash("No file selected", "error")
        return redirect(url_for("manage_data"))

    try:
        files = {"file": (file.filename, file.read(), file.content_type)}
        data = {"name": name}
        response = requests.post(
            f"{API_BASE_URL}/data/upload",
            files=files,
            data=data,
            headers={"Authorization": f"Bearer {session['access_token']}"},
            timeout=30
        )

        if response.status_code == 201:
            flash("File uploaded successfully!", "success")
        else:
            flash("Failed to upload file", "error")
    except requests.exceptions.RequestException as e:
        flash(f"Connection error: {str(e)}", "error")

    return redirect(url_for("manage_data"))


@app.route("/data/<source_id>/delete", methods=["POST"])
def delete_data(source_id):
    if "access_token" not in session:
        return redirect(url_for("login"))

    try:
        response = requests.delete(
            f"{API_BASE_URL}/data/{source_id}",
            headers=get_api_headers(),
            timeout=10
        )

        if response.status_code == 204:
            flash("Data source deleted", "success")
        else:
            flash("Failed to delete data source", "error")
    except requests.exceptions.RequestException as e:
        flash(f"Connection error: {str(e)}", "error")

    return redirect(url_for("manage_data"))


@app.route("/chat")
def chat():
    if "access_token" not in session:
        return redirect(url_for("login"))

    try:
        models_response = requests.get(
            f"{API_BASE_URL}/v1/models",
            headers=get_api_headers(),
            timeout=10
        )
        models = models_response.json().get("data", []) if models_response.status_code == 200 else []

        skills_response = requests.get(
            f"{API_BASE_URL}/skills",
            headers=get_api_headers(),
            timeout=10
        )
        skills = skills_response.json() if skills_response.status_code == 200 else []

        settings_response = requests.get(
            f"{API_BASE_URL}/settings",
            headers=get_api_headers(),
            timeout=10
        )
        user_settings = settings_response.json() if settings_response.status_code == 200 else None

    except requests.exceptions.RequestException:
        models = []
        skills = []
        user_settings = None

    return render_template(
        "chat.html",
        models=models,
        skills=skills,
        user_settings=user_settings
    )


@app.route("/api/chat", methods=["POST"])
def api_chat():
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json
    messages = data.get("messages", [])
    model = data.get("model") or "llama3.2:1b"
    skill_id = data.get("skill_id")
    temperature = data.get("temperature", 0.7)
    max_tokens = data.get("max_tokens", 1000)

    system_prompt = None
    if skill_id:
        try:
            skill_resp = requests.get(
                f"{API_BASE_URL}/skills/{skill_id}",
                headers=get_api_headers(),
                timeout=10
            )
            if skill_resp.status_code == 200:
                skill_data = skill_resp.json()
                system_prompt = skill_data.get("system_prompt")
        except Exception:
            pass

    ollama_messages = []
    if system_prompt:
        ollama_messages.append({"role": "system", "content": system_prompt})
    for m in messages:
        ollama_messages.append({"role": m.get("role", "user"), "content": m.get("content", "")})

    try:
        import uuid
        import time

        payload = {
            "model": model,
            "messages": ollama_messages,
            "temperature": temperature,
            "options": {"num_predict": max_tokens},
            "stream": False
        }

        response = requests.post(
            "http://localhost:11434/api/chat",
            json=payload,
            timeout=120
        )

        if response.status_code == 200:
            result = response.json()
            content = result.get("message", {}).get("content", "")
            prompt_tokens = result.get("prompt_eval_count", 0)
            completion_tokens = result.get("eval_count", 0)

            return jsonify({
                "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": model,
                "choices": [{
                    "index": 0,
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": "stop"
                }],
                "usage": {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": prompt_tokens + completion_tokens
                }
            })
        else:
            return jsonify({"error": f"Ollama returned {response.status_code}"}), 500
    except requests.exceptions.ConnectionError:
        return jsonify({"error": "Cannot connect to Ollama. Is it running?"}), 503
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/management")
def management():
    if "access_token" not in session:
        return redirect(url_for("login"))

    try:
        models_response = requests.get(
            f"{API_BASE_URL}/management/models",
            headers=get_api_headers(),
            timeout=10
        )
        models_data = models_response.json() if models_response.status_code == 200 else {"models": [], "current_model": None}

        tasks_response = requests.get(
            f"{API_BASE_URL}/management/tasks",
            headers=get_api_headers(),
            timeout=10
        )
        tasks = tasks_response.json() if tasks_response.status_code == 200 else []

        kbs_response = requests.get(
            f"{API_BASE_URL}/management/knowledge-bases",
            headers=get_api_headers(),
            timeout=10
        )
        knowledge_bases = kbs_response.json() if kbs_response.status_code == 200 else []

        restrictions_response = requests.get(
            f"{API_BASE_URL}/management/restrictions",
            headers=get_api_headers(),
            timeout=10
        )
        restrictions = restrictions_response.json() if restrictions_response.status_code == 200 else []

        resources_response = requests.get(
            f"{API_BASE_URL}/management/resources",
            headers=get_api_headers(),
            timeout=10
        )
        resources = resources_response.json() if resources_response.status_code == 200 else {}

    except requests.exceptions.RequestException:
        models_data = {"models": [], "current_model": None}
        tasks = []
        knowledge_bases = []
        restrictions = []
        resources = {}

    return render_template(
        "management.html",
        models=models_data.get("models", []),
        current_model=models_data.get("current_model"),
        tasks=tasks,
        knowledge_bases=knowledge_bases,
        restrictions=restrictions,
        resources=resources
    )


@app.route("/management/model/switch", methods=["POST"])
def management_switch_model():
    if "access_token" not in session:
        return redirect(url_for("login"))

    model = request.form.get("model")
    if not model:
        flash("No model specified", "error")
        return redirect(url_for("management"))

    try:
        response = requests.post(
            f"{API_BASE_URL}/settings/model",
            json={"model": model},
            headers=get_api_headers(),
            timeout=10
        )
        if response.status_code == 200:
            flash(f"Switched to {model}", "success")
        else:
            flash("Failed to switch model", "error")
    except requests.exceptions.RequestException as e:
        flash(f"Connection error: {str(e)}", "error")

    return redirect(url_for("management"))


@app.route("/management/pdf/upload", methods=["POST"])
def management_upload_pdf():
    if "access_token" not in session:
        return redirect(url_for("login"))

    if "pdf_file" not in request.files:
        flash("No file provided", "error")
        return redirect(url_for("management"))

    file = request.files["pdf_file"]
    kb_name = request.form.get("kb_name", file.filename)
    model_id = request.form.get("model_id")

    if file.filename == "":
        flash("No file selected", "error")
        return redirect(url_for("management"))

    try:
        files = {"file": (file.filename, file.read(), file.content_type)}
        data = {"kb_name": kb_name}
        if model_id:
            data["model_id"] = model_id

        response = requests.post(
            f"{API_BASE_URL}/management/train/pdf",
            files=files,
            data=data,
            headers={"Authorization": f"Bearer {session['access_token']}"},
            timeout=60
        )

        if response.status_code == 200:
            flash("PDF processing started in background", "success")
        else:
            flash("Failed to start PDF processing", "error")
    except requests.exceptions.RequestException as e:
        flash(f"Connection error: {str(e)}", "error")

    return redirect(url_for("management"))


@app.route("/management/web/crawl", methods=["POST"])
def management_web_crawl():
    if "access_token" not in session:
        return redirect(url_for("login"))

    url = request.form.get("url")
    max_pages = request.form.get("max_pages", 10, type=int)
    model_id = request.form.get("model_id")

    if not url:
        flash("No URL specified", "error")
        return redirect(url_for("management"))

    try:
        payload = {"url": url, "max_pages": max_pages}
        if model_id:
            payload["model_id"] = model_id

        response = requests.post(
            f"{API_BASE_URL}/management/train/web",
            json=payload,
            headers=get_api_headers(),
            timeout=30
        )

        if response.status_code == 200:
            flash("Web crawl started in background", "success")
        else:
            flash("Failed to start web crawl", "error")
    except requests.exceptions.RequestException as e:
        flash(f"Connection error: {str(e)}", "error")

    return redirect(url_for("management"))


@app.route("/management/kb/toggle/<kb_id>", methods=["POST"])
def management_toggle_kb(kb_id):
    if "access_token" not in session:
        return redirect(url_for("login"))

    try:
        response = requests.post(
            f"{API_BASE_URL}/management/knowledge-bases/{kb_id}/toggle",
            headers=get_api_headers(),
            timeout=10
        )
        if response.status_code == 200:
            flash("Knowledge base toggled", "success")
        else:
            flash("Failed to toggle knowledge base", "error")
    except requests.exceptions.RequestException as e:
        flash(f"Connection error: {str(e)}", "error")

    return redirect(url_for("management"))


@app.route("/management/kb/delete/<kb_id>", methods=["POST"])
def management_delete_kb(kb_id):
    if "access_token" not in session:
        return redirect(url_for("login"))

    try:
        response = requests.delete(
            f"{API_BASE_URL}/management/knowledge-bases/{kb_id}",
            headers=get_api_headers(),
            timeout=10
        )
        if response.status_code == 200:
            flash("Knowledge base deleted", "success")
        else:
            flash("Failed to delete knowledge base", "error")
    except requests.exceptions.RequestException as e:
        flash(f"Connection error: {str(e)}", "error")

    return redirect(url_for("management"))


@app.route("/management/restriction/create", methods=["POST"])
def management_create_restriction():
    if "access_token" not in session:
        return redirect(url_for("login"))

    name = request.form.get("name")
    mode = request.form.get("restriction_mode", "none")
    security_level = request.form.get("security_level", "none")
    allowed_topics = request.form.get("allowed_topics", "")
    blocked_topics = request.form.get("blocked_topics", "")

    if not name:
        flash("Name is required", "error")
        return redirect(url_for("management"))

    try:
        payload = {
            "name": name,
            "restriction_mode": mode,
            "security_level": security_level
        }
        if allowed_topics:
            payload["allowed_topics"] = [t.strip() for t in allowed_topics.split(",") if t.strip()]
        if blocked_topics:
            payload["blocked_topics"] = [t.strip() for t in blocked_topics.split(",") if t.strip()]

        response = requests.post(
            f"{API_BASE_URL}/management/restrictions",
            json=payload,
            headers=get_api_headers(),
            timeout=10
        )
        if response.status_code == 200:
            flash("Restriction profile created", "success")
        else:
            flash("Failed to create restriction", "error")
    except requests.exceptions.RequestException as e:
        flash(f"Connection error: {str(e)}", "error")

    return redirect(url_for("management"))


@app.route("/management/restriction/activate/<profile_id>", methods=["POST"])
def management_activate_restriction(profile_id):
    if "access_token" not in session:
        return redirect(url_for("login"))

    try:
        response = requests.post(
            f"{API_BASE_URL}/management/restrictions/{profile_id}/activate",
            headers=get_api_headers(),
            timeout=10
        )
        if response.status_code == 200:
            flash("Restriction profile activated", "success")
        else:
            flash("Failed to activate profile", "error")
    except requests.exceptions.RequestException as e:
        flash(f"Connection error: {str(e)}", "error")

    return redirect(url_for("management"))


@app.route("/management/restriction/deactivate", methods=["POST"])
def management_deactivate_restrictions():
    if "access_token" not in session:
        return redirect(url_for("login"))

    try:
        response = requests.post(
            f"{API_BASE_URL}/management/restrictions/deactivate",
            headers=get_api_headers(),
            timeout=10
        )
        if response.status_code == 200:
            flash("Restrictions deactivated", "success")
        else:
            flash("Failed to deactivate restrictions", "error")
    except requests.exceptions.RequestException as e:
        flash(f"Connection error: {str(e)}", "error")

    return redirect(url_for("management"))


@app.route("/management/restriction/delete/<profile_id>", methods=["POST"])
def management_delete_restriction(profile_id):
    if "access_token" not in session:
        return redirect(url_for("login"))

    try:
        response = requests.delete(
            f"{API_BASE_URL}/management/restrictions/{profile_id}",
            headers=get_api_headers(),
            timeout=10
        )
        if response.status_code == 200:
            flash("Restriction profile deleted", "success")
        else:
            flash("Failed to delete profile", "error")
    except requests.exceptions.RequestException as e:
        flash(f"Connection error: {str(e)}", "error")

    return redirect(url_for("management"))


@app.route("/management/task/cancel/<task_id>", methods=["POST"])
def management_cancel_task(task_id):
    if "access_token" not in session:
        return redirect(url_for("login"))

    try:
        response = requests.delete(
            f"{API_BASE_URL}/management/tasks/{task_id}",
            headers=get_api_headers(),
            timeout=10
        )
        if response.status_code == 200:
            flash("Task cancelled", "success")
        else:
            flash("Failed to cancel task", "error")
    except requests.exceptions.RequestException as e:
        flash(f"Connection error: {str(e)}", "error")

    return redirect(url_for("management"))


@app.route("/api/management/resources")
def api_management_resources():
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        response = requests.get(
            f"{API_BASE_URL}/management/resources",
            headers=get_api_headers(),
            timeout=10
        )
        return response.json() if response.status_code == 200 else {}
    except requests.exceptions.RequestException:
        return {}


@app.route("/api/management/tasks")
def api_management_tasks():
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        response = requests.get(
            f"{API_BASE_URL}/management/tasks",
            headers=get_api_headers(),
            timeout=10
        )
        return response.json() if response.status_code == 200 else []
    except requests.exceptions.RequestException:
        return []


@app.route("/api/management/model-info/<model_id>")
def api_management_model_info(model_id):
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        response = requests.get(
            f"{API_BASE_URL}/management/models/{model_id}/info",
            headers=get_api_headers(),
            timeout=10
        )
        return response.json() if response.status_code == 200 else {"detail": "Not found"}
    except requests.exceptions.RequestException:
        return {"detail": "Connection error"}


@app.route("/api/management/live-metrics")
def api_management_live_metrics():
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        resp = requests.get(f"{API_BASE_URL}/management/live-metrics",
                            headers=get_api_headers(), timeout=10)
        return resp.json() if resp.status_code == 200 else {"current": {}, "history": []}
    except requests.exceptions.RequestException:
        return {"current": {}, "history": [], "error": "Connection error"}


@app.route("/api/management/activity")
def api_management_activity():
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        limit = request.args.get("limit", 50, type=int)
        resp = requests.get(f"{API_BASE_URL}/management/activity",
                            params={"limit": limit}, headers=get_api_headers(), timeout=10)
        return resp.json() if resp.status_code == 200 else []
    except requests.exceptions.RequestException:
        return []


@app.route("/api/management/health-check")
def api_management_health_check():
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        resp = requests.get(f"{API_BASE_URL}/management/health-check",
                            headers=get_api_headers(), timeout=10)
        return resp.json() if resp.status_code == 200 else {"ollama_reachable": False}
    except requests.exceptions.RequestException:
        return {"ollama_reachable": False, "error": "Connection error"}


@app.route("/api/management/benchmark", methods=["POST"])
def api_management_benchmark():
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        data = request.get_json() or {}
        resp = requests.post(f"{API_BASE_URL}/management/benchmark",
                             json=data, headers=get_api_headers(), timeout=120)
        return resp.json() if resp.status_code == 200 else {"error": "Benchmark failed"}
    except requests.exceptions.RequestException as e:
        return {"error": str(e)[:300]}


@app.route("/api/management/playground", methods=["POST"])
def api_management_playground():
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        data = request.get_json() or {}
        resp = requests.post(f"{API_BASE_URL}/management/playground",
                             json=data, headers=get_api_headers(), timeout=120)
        return resp.json() if resp.status_code == 200 else {"error": "Playground failed"}
    except requests.exceptions.RequestException as e:
        return {"error": str(e)[:300]}


@app.route("/api/management/kb/<kb_id>/search", methods=["POST"])
def api_management_kb_search(kb_id):
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        data = request.get_json() or {}
        resp = requests.post(f"{API_BASE_URL}/management/knowledge-bases/{kb_id}/search",
                             json=data, headers=get_api_headers(), timeout=30)
        return resp.json() if resp.status_code == 200 else {"results": [], "error": "Search failed"}
    except requests.exceptions.RequestException as e:
        return {"results": [], "error": str(e)[:300]}


@app.route("/api/management/kb/create", methods=["POST"])
def api_management_kb_create():
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        data = request.get_json() or {}
        resp = requests.post(f"{API_BASE_URL}/management/knowledge-bases",
                             json=data, headers=get_api_headers(), timeout=15)
        if resp.status_code == 200:
            return resp.json()
        return jsonify({"detail": resp.text[:300]}), resp.status_code
    except requests.exceptions.RequestException as e:
        return jsonify({"detail": str(e)[:300]}), 500


@app.route("/model-builder")
def model_builder():
    if "access_token" not in session:
        return redirect(url_for("login"))

    try:
        templates_resp = requests.get(
            f"{API_BASE_URL}/model-builder/templates",
            headers=get_api_headers(),
            timeout=10
        )
        templates = templates_resp.json().get("templates", []) if templates_resp.status_code == 200 else []

        models_resp = requests.get(
            f"{API_BASE_URL}/model-builder/models",
            headers=get_api_headers(),
            timeout=10
        )
        custom_models = models_resp.json() if models_resp.status_code == 200 else []

        stats_resp = requests.get(
            f"{API_BASE_URL}/model-builder/stats",
            headers=get_api_headers(),
            timeout=10
        )
        stats = stats_resp.json() if stats_resp.status_code == 200 else {}

    except requests.exceptions.RequestException:
        templates = []
        custom_models = []
        stats = {}

    return render_template(
        "model_builder.html",
        templates=templates,
        custom_models=custom_models,
        stats=stats
    )


@app.route("/model-builder/create", methods=["POST"])
def model_builder_create():
    if "access_token" not in session:
        return redirect(url_for("login"))

    domain = request.form.get("domain", "custom")
    name = request.form.get("name")
    description = request.form.get("description", "")
    base_model = request.form.get("base_model", "llama3.2:1b")
    system_prompt = request.form.get("system_prompt", "")
    restricted_topics = request.form.get("restricted_topics", "")
    blocked_topics = request.form.get("blocked_topics", "")
    temperature = request.form.get("temperature", 0.7, type=float)
    max_tokens = request.form.get("max_tokens", 1000, type=int)

    if not name:
        flash("Model name is required", "error")
        return redirect(url_for("model_builder"))

    payload = {
        "name": name,
        "description": description,
        "domain": domain,
        "base_model": base_model,
        "system_prompt": system_prompt,
        "temperature": temperature,
        "max_tokens": max_tokens
    }
    if restricted_topics:
        payload["restricted_topics"] = [t.strip() for t in restricted_topics.split(",") if t.strip()]
    if blocked_topics:
        payload["blocked_topics"] = [t.strip() for t in blocked_topics.split(",") if t.strip()]

    try:
        response = requests.post(
            f"{API_BASE_URL}/model-builder/models",
            json=payload,
            headers=get_api_headers(),
            timeout=10
        )
        if response.status_code == 200:
            flash(f"Model '{name}' created successfully!", "success")
        else:
            flash("Failed to create model", "error")
    except requests.exceptions.RequestException as e:
        flash(f"Connection error: {str(e)}", "error")

    return redirect(url_for("model_builder"))


@app.route("/model-builder/<model_id>/train/pdf", methods=["POST"])
def model_builder_train_pdf(model_id):
    if "access_token" not in session:
        return redirect(url_for("login"))

    if "train_file" not in request.files:
        flash("No file provided", "error")
        return redirect(url_for("model_builder"))

    file = request.files["train_file"]
    if file.filename == "":
        flash("No file selected", "error")
        return redirect(url_for("model_builder"))

    try:
        files = {"file": (file.filename, file.read(), file.content_type)}
        data = {"chunk_size": 1000}
        response = requests.post(
            f"{API_BASE_URL}/model-builder/models/{model_id}/train/pdf",
            files=files,
            data=data,
            headers={"Authorization": f"Bearer {session['access_token']}"},
            timeout=60
        )
        if response.status_code == 200:
            flash("PDF training started in background", "success")
        else:
            flash("Failed to start training", "error")
    except requests.exceptions.RequestException as e:
        flash(f"Connection error: {str(e)}", "error")

    return redirect(url_for("model_builder"))


@app.route("/model-builder/<model_id>/train/text", methods=["POST"])
def model_builder_train_text(model_id):
    if "access_token" not in session:
        return redirect(url_for("login"))

    text = request.form.get("train_text", "")
    if not text.strip():
        flash("No text provided", "error")
        return redirect(url_for("model_builder"))

    try:
        payload = {"model_id": model_id, "text": text, "chunk_size": 1000}
        response = requests.post(
            f"{API_BASE_URL}/model-builder/models/{model_id}/train/text",
            json=payload,
            headers=get_api_headers(),
            timeout=30
        )
        if response.status_code == 200:
            flash("Text training started in background", "success")
        else:
            flash("Failed to start training", "error")
    except requests.exceptions.RequestException as e:
        flash(f"Connection error: {str(e)}", "error")

    return redirect(url_for("model_builder"))


@app.route("/model-builder/<model_id>/train/web", methods=["POST"])
def model_builder_train_web(model_id):
    if "access_token" not in session:
        return redirect(url_for("login"))

    url_input = request.form.get("train_url", "")
    max_pages = request.form.get("max_pages", 10, type=int)

    if not url_input.strip():
        flash("No URL provided", "error")
        return redirect(url_for("model_builder"))

    try:
        payload = {"model_id": model_id, "url": url_input, "max_pages": max_pages}
        response = requests.post(
            f"{API_BASE_URL}/model-builder/models/{model_id}/train/web",
            json=payload,
            headers=get_api_headers(),
            timeout=30
        )
        if response.status_code == 200:
            flash("Web training started in background", "success")
        else:
            flash("Failed to start training", "error")
    except requests.exceptions.RequestException as e:
        flash(f"Connection error: {str(e)}", "error")

    return redirect(url_for("model_builder"))


@app.route("/model-builder/<model_id>/delete", methods=["POST"])
def model_builder_delete(model_id):
    if "access_token" not in session:
        return redirect(url_for("login"))

    try:
        response = requests.delete(
            f"{API_BASE_URL}/model-builder/models/{model_id}",
            headers=get_api_headers(),
            timeout=10
        )
        if response.status_code == 200:
            flash("Model deleted", "success")
        else:
            flash("Failed to delete model", "error")
    except requests.exceptions.RequestException as e:
        flash(f"Connection error: {str(e)}", "error")

    return redirect(url_for("model_builder"))


@app.route("/api/model-builder/models")
def api_model_builder_models():
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        response = requests.get(
            f"{API_BASE_URL}/model-builder/models",
            headers=get_api_headers(),
            timeout=10
        )
        return response.json() if response.status_code == 200 else []
    except requests.exceptions.RequestException:
        return []


@app.route("/api/model-builder/model/<model_id>")
def api_model_builder_model(model_id):
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        response = requests.get(
            f"{API_BASE_URL}/model-builder/models/{model_id}",
            headers=get_api_headers(),
            timeout=10
        )
        return response.json() if response.status_code == 200 else {"detail": "Not found"}
    except requests.exceptions.RequestException:
        return {"detail": "Connection error"}


@app.route("/api/model-builder/model/<model_id>/test", methods=["POST"])
def api_model_builder_test(model_id):
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    if not data.get("message"):
        return jsonify({"error": "Message required"}), 400
    try:
        response = requests.post(
            f"{API_BASE_URL}/model-builder/models/{model_id}/test",
            json=data,
            headers=get_api_headers(),
            timeout=60
        )
        return response.json() if response.status_code == 200 else ({"error": "Test failed"}, 502)
    except requests.exceptions.RequestException as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/model-builder/model/<model_id>/logs")
def api_model_builder_logs(model_id):
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        response = requests.get(
            f"{API_BASE_URL}/model-builder/models/{model_id}/logs",
            headers=get_api_headers(),
            timeout=10
        )
        return response.json() if response.status_code == 200 else {"error": "Not found"}
    except requests.exceptions.RequestException as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/model-builder/model/<model_id>/clone", methods=["POST"])
def api_model_builder_clone(model_id):
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    if not data.get("name"):
        return jsonify({"error": "Name required"}), 400
    try:
        response = requests.post(
            f"{API_BASE_URL}/model-builder/models/{model_id}/clone",
            json=data,
            headers=get_api_headers(),
            timeout=10
        )
        return response.json() if response.status_code == 200 else ({"error": "Clone failed"}, 500)
    except requests.exceptions.RequestException as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/model-builder/model/<model_id>/export")
def api_model_builder_export(model_id):
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        response = requests.get(
            f"{API_BASE_URL}/model-builder/models/{model_id}/export",
            headers=get_api_headers(),
            timeout=10
        )
        return response.json() if response.status_code == 200 else {"error": "Not found"}
    except requests.exceptions.RequestException as e:
        return jsonify({"error": str(e)}), 500


@app.route("/model-builder/lightweight/create", methods=["POST"])
def model_builder_lightweight_create():
    if "access_token" not in session:
        return redirect(url_for("login"))

    name = request.form.get("name")
    task_type = request.form.get("task_type")
    base_model = request.form.get("base_model", "qwen2.5:0.5b")
    custom_knowledge = request.form.get("custom_knowledge", "")
    custom_prompt = request.form.get("custom_prompt", "")

    if not name or not task_type:
        flash("Name and task type are required", "error")
        return redirect(url_for("model_builder"))

    try:
        payload = {
            "name": name,
            "task_type": task_type,
            "base_model": base_model,
            "custom_knowledge": custom_knowledge,
            "custom_prompt": custom_prompt
        }
        response = requests.post(
            f"{API_BASE_URL}/model-builder/lightweight/create",
            json=payload,
            headers=get_api_headers(),
            timeout=10
        )
        if response.status_code == 200:
            flash(f"Lightweight model '{name}' created! Ready to use.", "success")
        else:
            flash("Failed to create lightweight model", "error")
    except requests.exceptions.RequestException as e:
        flash(f"Connection error: {str(e)}", "error")

    return redirect(url_for("model_builder"))


@app.route("/api/model-builder/lightweight/tasks")
def api_lightweight_tasks():
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        response = requests.get(
            f"{API_BASE_URL}/model-builder/lightweight/tasks",
            headers=get_api_headers(),
            timeout=10
        )
        return response.json() if response.status_code == 200 else []
    except requests.exceptions.RequestException:
        return []


# ============= Model Firewall Routes =============

@app.route("/firewall")
def firewall():
    if "access_token" not in session:
        return redirect(url_for("login"))

    profiles = []
    stats = {"total_profiles": 0, "active_profiles": 0, "blocked_requests": 0, "pending_reviews": 0, "block_rate": "0%"}

    try:
        resp = requests.get(f"{API_BASE_URL}/firewall/profiles", headers=get_api_headers(), timeout=10)
        if resp.status_code == 200:
            profiles = resp.json()
    except requests.exceptions.RequestException:
        pass

    try:
        resp = requests.get(f"{API_BASE_URL}/firewall/stats", headers=get_api_headers(), timeout=10)
        if resp.status_code == 200:
            stats = resp.json()
    except requests.exceptions.RequestException:
        pass

    return render_template("firewall.html", profiles=profiles, stats=stats)


@app.route("/firewall/create", methods=["POST"])
def firewall_create():
    if "access_token" not in session:
        return redirect(url_for("login"))

    name = request.form.get("name")
    description = request.form.get("description", "")
    protection_mode = request.form.get("protection_mode", "standard")

    if not name:
        flash("Profile name is required", "error")
        return redirect(url_for("firewall"))

    try:
        payload = {"name": name, "description": description, "protection_mode": protection_mode}
        resp = requests.post(f"{API_BASE_URL}/firewall/profiles", json=payload, headers=get_api_headers(), timeout=10)
        if resp.status_code == 200:
            flash(f"Firewall '{name}' created with {protection_mode} mode", "success")
        else:
            flash("Failed to create firewall profile", "error")
    except requests.exceptions.RequestException as e:
        flash(f"Connection error: {str(e)}", "error")

    return redirect(url_for("firewall"))


@app.route("/firewall/<profile_id>/activate", methods=["POST"])
def firewall_activate(profile_id):
    if "access_token" not in session:
        return redirect(url_for("login"))

    try:
        resp = requests.post(f"{API_BASE_URL}/firewall/profiles/{profile_id}/activate", headers=get_api_headers(), timeout=10)
        if resp.status_code == 200:
            flash("Firewall profile activated", "success")
        else:
            flash("Failed to activate profile", "error")
    except requests.exceptions.RequestException as e:
        flash(f"Connection error: {str(e)}", "error")

    return redirect(url_for("firewall"))


@app.route("/firewall/<profile_id>/delete", methods=["POST"])
def firewall_delete(profile_id):
    if "access_token" not in session:
        return redirect(url_for("login"))

    try:
        resp = requests.delete(f"{API_BASE_URL}/firewall/profiles/{profile_id}", headers=get_api_headers(), timeout=10)
        if resp.status_code == 200:
            flash("Firewall profile deleted", "success")
        else:
            flash("Failed to delete profile", "error")
    except requests.exceptions.RequestException as e:
        flash(f"Connection error: {str(e)}", "error")

    return redirect(url_for("firewall"))


@app.route("/firewall/rule/add", methods=["POST"])
def firewall_rule_add():
    if "access_token" not in session:
        return redirect(url_for("login"))

    profile_id = request.form.get("profile_id")
    name = request.form.get("name")
    category = request.form.get("category", "content")
    pattern = request.form.get("pattern")
    action = request.form.get("action", "deny")
    response_message = request.form.get("response_message", "")
    priority = request.form.get("priority", 0)

    if not profile_id or not name or not pattern:
        flash("Profile ID, name, and pattern are required", "error")
        return redirect(url_for("firewall"))

    try:
        payload = {
            "name": name, "category": category, "pattern": pattern,
            "action": action, "response_message": response_message,
            "priority": int(priority)
        }
        resp = requests.post(f"{API_BASE_URL}/firewall/profiles/{profile_id}/rules",
                             json=payload, headers=get_api_headers(), timeout=10)
        if resp.status_code == 200:
            flash(f"Rule '{name}' added", "success")
        else:
            flash("Failed to add rule", "error")
    except requests.exceptions.RequestException as e:
        flash(f"Connection error: {str(e)}", "error")

    return redirect(url_for("firewall"))


@app.route("/firewall/rule/<rule_id>/delete", methods=["POST"])
def firewall_rule_delete(rule_id):
    if "access_token" not in session:
        return redirect(url_for("login"))

    try:
        resp = requests.delete(f"{API_BASE_URL}/firewall/rules/{rule_id}", headers=get_api_headers(), timeout=10)
        if resp.status_code == 200:
            flash("Rule deleted", "success")
        else:
            flash("Failed to delete rule", "error")
    except requests.exceptions.RequestException as e:
        flash(f"Connection error: {str(e)}", "error")

    return redirect(url_for("firewall"))


@app.route("/api/firewall/profiles")
def api_firewall_profiles():
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        resp = requests.get(f"{API_BASE_URL}/firewall/profiles", headers=get_api_headers(), timeout=10)
        return resp.json() if resp.status_code == 200 else []
    except requests.exceptions.RequestException:
        return []


@app.route("/api/firewall/profiles/<profile_id>")
def api_firewall_profile(profile_id):
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        resp = requests.get(f"{API_BASE_URL}/firewall/profiles/{profile_id}", headers=get_api_headers(), timeout=10)
        return resp.json() if resp.status_code == 200 else {"detail": "Not found"}
    except requests.exceptions.RequestException:
        return {"detail": "Connection error"}


@app.route("/api/firewall/check/<profile_id>", methods=["POST"])
def api_firewall_check(profile_id):
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        data = request.get_json()
        resp = requests.post(f"{API_BASE_URL}/firewall/check/{profile_id}",
                             json=data, headers=get_api_headers(), timeout=10)
        return resp.json() if resp.status_code == 200 else {"action": "error"}
    except requests.exceptions.RequestException:
        return {"action": "error", "reason": "Connection error"}


@app.route("/api/firewall/stats")
def api_firewall_stats():
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        resp = requests.get(f"{API_BASE_URL}/firewall/stats", headers=get_api_headers(), timeout=10)
        return resp.json() if resp.status_code == 200 else {}
    except requests.exceptions.RequestException:
        return {}


# ============= Database Connector Routes =============

@app.route("/api/database/test", methods=["POST"])
def api_database_test():
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        data = request.get_json()
        resp = requests.post(f"{API_BASE_URL}/database/test", json=data, headers=get_api_headers(), timeout=15)
        return resp.json() if resp.status_code == 200 else {"success": False, "message": "Test failed"}
    except requests.exceptions.RequestException:
        return {"success": False, "message": "Connection error"}


@app.route("/api/database/databases", methods=["POST"])
def api_database_list():
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        data = request.get_json()
        resp = requests.post(f"{API_BASE_URL}/database/databases", json=data, headers=get_api_headers(), timeout=15)
        return resp.json() if resp.status_code == 200 else {"databases": []}
    except requests.exceptions.RequestException:
        return {"databases": []}


@app.route("/api/database/connect", methods=["POST"])
def api_database_connect():
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        data = request.get_json()
        resp = requests.post(f"{API_BASE_URL}/database/connect", json=data, headers=get_api_headers(), timeout=15)
        return resp.json() if resp.status_code == 200 else {"detail": "Connection failed"}
    except requests.exceptions.RequestException:
        return {"detail": "Connection error"}


@app.route("/api/database/table/preview")
def api_database_preview():
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        conn_url = request.args.get("connection_url", "")
        table_name = request.args.get("table_name", "")
        limit = request.args.get("limit", 5, type=int)
        offset = request.args.get("offset", 0, type=int)
        resp = requests.post(
            f"{API_BASE_URL}/database/table/data",
            params={"connection_url": conn_url, "table_name": table_name, "limit": limit, "offset": offset},
            headers=get_api_headers(), timeout=15
        )
        return resp.json() if resp.status_code == 200 else {"columns": [], "rows": []}
    except requests.exceptions.RequestException:
        return {"columns": [], "rows": [], "error": "Connection error"}


@app.route("/api/database/table/columns", methods=["POST"])
def api_database_columns():
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        data = request.get_json()
        resp = requests.post(f"{API_BASE_URL}/database/table/columns", json=data, headers=get_api_headers(), timeout=15)
        return resp.json() if resp.status_code == 200 else {"columns": [], "error": "Failed"}
    except requests.exceptions.RequestException:
        return {"columns": [], "error": "Connection error"}


@app.route("/api/database/table/row-count", methods=["POST"])
def api_database_row_count():
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        data = request.get_json()
        resp = requests.post(f"{API_BASE_URL}/database/table/row-count", json=data, headers=get_api_headers(), timeout=15)
        return resp.json() if resp.status_code == 200 else {"row_count": 0, "error": "Failed"}
    except requests.exceptions.RequestException:
        return {"row_count": 0, "error": "Connection error"}


@app.route("/api/database/table/export", methods=["POST"])
def api_database_export():
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        data = request.get_json()
        resp = requests.post(f"{API_BASE_URL}/database/table/export", json=data, headers=get_api_headers(), timeout=30)
        return resp.json() if resp.status_code == 200 else {"error": "Export failed"}
    except requests.exceptions.RequestException:
        return {"error": "Connection error"}


# ============= Training Routes =============
@app.route("/api/training/jobs", methods=["GET"])
def api_training_list():
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        resp = requests.get(f"{API_BASE_URL}/training/jobs", headers=get_api_headers(), timeout=10)
        return resp.json() if resp.status_code == 200 else {"jobs": []}
    except requests.exceptions.RequestException:
        return {"jobs": [], "error": "Connection error"}


@app.route("/api/training/jobs", methods=["POST"])
def api_training_create():
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        data = request.get_json()
        resp = requests.post(f"{API_BASE_URL}/training/jobs", json=data, headers=get_api_headers(), timeout=10)
        return resp.json() if resp.status_code == 200 else {"error": "Failed to create job"}
    except requests.exceptions.RequestException:
        return {"error": "Connection error"}


@app.route("/api/training/jobs/<job_id>", methods=["GET"])
def api_training_get(job_id):
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        resp = requests.get(f"{API_BASE_URL}/training/jobs/{job_id}", headers=get_api_headers(), timeout=10)
        return resp.json() if resp.status_code == 200 else {"error": "Not found"}
    except requests.exceptions.RequestException:
        return {"error": "Connection error"}


@app.route("/api/training/jobs/<job_id>/start", methods=["POST"])
def api_training_start(job_id):
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        resp = requests.post(f"{API_BASE_URL}/training/jobs/{job_id}/start", headers=get_api_headers(), timeout=10)
        return resp.json() if resp.status_code == 200 else {"error": "Failed"}
    except requests.exceptions.RequestException:
        return {"error": "Connection error"}


@app.route("/api/training/jobs/<job_id>/cancel", methods=["POST"])
def api_training_cancel(job_id):
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        resp = requests.post(f"{API_BASE_URL}/training/jobs/{job_id}/cancel", headers=get_api_headers(), timeout=10)
        return resp.json() if resp.status_code == 200 else {"error": "Failed"}
    except requests.exceptions.RequestException:
        return {"error": "Connection error"}


@app.route("/api/training/jobs/<job_id>/test", methods=["POST"])
def api_training_test(job_id):
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        data = request.get_json()
        resp = requests.post(f"{API_BASE_URL}/training/jobs/{job_id}/test", json=data, headers=get_api_headers(), timeout=30)
        return resp.json() if resp.status_code == 200 else {"error": "Failed"}
    except requests.exceptions.RequestException:
        return {"error": "Connection error"}


@app.route("/api/training/jobs/<job_id>/feedback", methods=["POST"])
def api_training_feedback(job_id):
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        data = request.get_json()
        resp = requests.post(f"{API_BASE_URL}/training/jobs/{job_id}/feedback", json=data, headers=get_api_headers(), timeout=10)
        return resp.json() if resp.status_code == 200 else {"error": "Failed"}
    except requests.exceptions.RequestException:
        return {"error": "Connection error"}


@app.route("/api/training/jobs/<job_id>/retrain", methods=["POST"])
def api_training_retrain(job_id):
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        resp = requests.post(f"{API_BASE_URL}/training/jobs/{job_id}/retrain", headers=get_api_headers(), timeout=10)
        return resp.json() if resp.status_code == 200 else {"error": "Failed"}
    except requests.exceptions.RequestException:
        return {"error": "Connection error"}


@app.route("/api/training/jobs/<job_id>", methods=["DELETE"])
def api_training_delete(job_id):
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        resp = requests.delete(f"{API_BASE_URL}/training/jobs/{job_id}", headers=get_api_headers(), timeout=10)
        return resp.json() if resp.status_code == 200 else {"error": "Failed"}
    except requests.exceptions.RequestException:
        return {"error": "Connection error"}


@app.route("/api/training/stages", methods=["GET"])
def api_training_stages():
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        resp = requests.get(f"{API_BASE_URL}/training/stages", headers=get_api_headers(), timeout=5)
        return resp.json() if resp.status_code == 200 else {"stages": []}
    except requests.exceptions.RequestException:
        return {"stages": []}


# ============== Camera Routes ==============
@app.route("/cameras")
def cameras_page():
    if "access_token" not in session:
        return redirect(url_for("login"))
    return render_template("cameras.html")


@app.route("/api/cameras", methods=["GET"])
def api_cameras_list():
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        resp = requests.get(f"{API_BASE_URL}/cameras", headers=get_api_headers(), timeout=10)
        return resp.json() if resp.status_code == 200 else {"cameras": []}
    except requests.exceptions.RequestException:
        return {"cameras": [], "error": "Connection error"}


@app.route("/api/cameras", methods=["POST"])
def api_cameras_create():
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        data = request.get_json()
        resp = requests.post(f"{API_BASE_URL}/cameras", json=data, headers=get_api_headers(), timeout=10)
        return resp.json() if resp.status_code in (200, 201) else {"error": "Failed"}
    except requests.exceptions.RequestException:
        return {"error": "Connection error"}


@app.route("/api/cameras/<camera_id>", methods=["GET"])
def api_cameras_get(camera_id):
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        resp = requests.get(f"{API_BASE_URL}/cameras/{camera_id}", headers=get_api_headers(), timeout=10)
        return resp.json() if resp.status_code == 200 else {"error": "Not found"}
    except requests.exceptions.RequestException:
        return {"error": "Connection error"}


@app.route("/api/cameras/<camera_id>", methods=["PUT", "DELETE"])
def api_cameras_modify(camera_id):
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        data = request.get_json() if request.method == "PUT" else None
        resp = requests.request(
            request.method, f"{API_BASE_URL}/cameras/{camera_id}",
            json=data, headers=get_api_headers(), timeout=10
        )
        return resp.json() if resp.status_code == 200 else {"error": "Failed"}
    except requests.exceptions.RequestException:
        return {"error": "Connection error"}


@app.route("/api/cameras/<camera_id>/test", methods=["GET", "POST"])
def api_cameras_test(camera_id):
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        resp = requests.post(f"{API_BASE_URL}/cameras/{camera_id}/test", headers=get_api_headers(), timeout=15)
        return resp.json() if resp.status_code == 200 else {"error": "Failed"}
    except requests.exceptions.RequestException:
        return {"error": "Connection error"}


@app.route("/api/cameras/<camera_id>/snapshot", methods=["POST"])
def api_cameras_snapshot(camera_id):
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        resp = requests.post(f"{API_BASE_URL}/cameras/{camera_id}/snapshot", headers=get_api_headers(), timeout=15)
        return resp.json() if resp.status_code == 200 else {"error": "Failed"}
    except requests.exceptions.RequestException:
        return {"error": "Connection error"}


@app.route("/api/cameras/<camera_id>/record/start", methods=["POST"])
def api_cameras_record_start(camera_id):
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        data = request.get_json() or {}
        resp = requests.post(f"{API_BASE_URL}/cameras/{camera_id}/record/start", json=data, headers=get_api_headers(), timeout=10)
        return resp.json() if resp.status_code == 200 else {"error": "Failed"}
    except requests.exceptions.RequestException:
        return {"error": "Connection error"}


@app.route("/api/cameras/<camera_id>/record/stop", methods=["POST"])
def api_cameras_record_stop(camera_id):
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        resp = requests.post(f"{API_BASE_URL}/cameras/{camera_id}/record/stop", headers=get_api_headers(), timeout=10)
        return resp.json() if resp.status_code == 200 else {"error": "Failed"}
    except requests.exceptions.RequestException:
        return {"error": "Connection error"}


@app.route("/api/cameras/<camera_id>/recordings", methods=["GET"])
def api_cameras_recordings(camera_id):
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        resp = requests.get(f"{API_BASE_URL}/cameras/{camera_id}/recordings", headers=get_api_headers(), timeout=10)
        return resp.json() if resp.status_code == 200 else {"recordings": []}
    except requests.exceptions.RequestException:
        return {"recordings": [], "error": "Connection error"}


@app.route("/api/cameras/recordings/all", methods=["GET"])
def api_cameras_recordings_all():
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        resp = requests.get(f"{API_BASE_URL}/cameras/recordings/all", headers=get_api_headers(), timeout=10)
        return resp.json() if resp.status_code == 200 else {"recordings": []}
    except requests.exceptions.RequestException:
        return {"recordings": [], "error": "Connection error"}


@app.route("/api/cameras/recordings/<rec_id>", methods=["GET"])
def api_recording_get(rec_id):
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        resp = requests.get(f"{API_BASE_URL}/cameras/recordings/{rec_id}", headers=get_api_headers(), timeout=10)
        return resp.json() if resp.status_code == 200 else {"error": "Not found"}
    except requests.exceptions.RequestException:
        return {"error": "Connection error"}


@app.route("/api/cameras/recordings/<rec_id>", methods=["DELETE"])
def api_recording_delete(rec_id):
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        resp = requests.delete(f"{API_BASE_URL}/cameras/recordings/{rec_id}", headers=get_api_headers(), timeout=10)
        return resp.json() if resp.status_code == 200 else {"error": "Failed"}
    except requests.exceptions.RequestException:
        return {"error": "Connection error"}


@app.route("/api/cameras/recordings/<rec_id>/analyze", methods=["POST"])
def api_recording_analyze(rec_id):
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        resp = requests.post(f"{API_BASE_URL}/cameras/recordings/{rec_id}/analyze", headers=get_api_headers(), timeout=120)
        return resp.json() if resp.status_code == 200 else {"error": "Failed"}
    except requests.exceptions.RequestException:
        return {"error": "Connection error"}


@app.route("/api/cameras/recordings/<rec_id>/stream")
def api_recording_stream(rec_id):
    """Stream a recording file with Range request support (for video playback)."""
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    # Get recording file path from API
    try:
        resp = requests.get(f"{API_BASE_URL}/cameras/recordings/{rec_id}", headers=get_api_headers(), timeout=10)
        if resp.status_code != 200:
            return jsonify({"error": "Not found"}), 404
        rec = resp.json()
        file_path = rec.get("file_path")
        if not file_path or not os.path.exists(file_path):
            return jsonify({"error": "File missing"}), 404
        # Use Flask's send_file with Range support
        return send_file_with_range(file_path)
    except requests.exceptions.RequestException:
        return jsonify({"error": "Connection error"}), 500


def send_file_with_range(file_path):
    """Send file with HTTP Range support for video seeking."""
    import re
    file_size = os.path.getsize(file_path)
    range_header = request.headers.get('Range', None)
    if range_header:
        # Parse Range: bytes=START-END
        m = re.match(r'bytes=(\d+)-(\d*)', range_header)
        if m:
            start = int(m.group(1))
            end = int(m.group(2)) if m.group(2) else file_size - 1
            end = min(end, file_size - 1)
            length = end - start + 1
            with open(file_path, 'rb') as f:
                f.seek(start)
                data = f.read(length)
            resp = Response(
                data,
                status=206,
                mimetype='video/mp4',
                headers={
                    'Content-Range': f'bytes {start}-{end}/{file_size}',
                    'Accept-Ranges': 'bytes',
                    'Content-Length': str(length),
                }
            )
            return resp
    # No range - send whole file
    return send_file(file_path, mimetype='video/mp4', conditional=True)


@app.route("/api/cameras/<camera_id>/snapshot.jpg")
def api_camera_snapshot_image(camera_id):
    """Serve latest snapshot for a camera."""
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    # Find latest snapshot
    snap_dir = Path("/www/AI_server/data/camera_snapshots")
    if snap_dir.exists():
        files = sorted(snap_dir.glob(f"{camera_id}-*.jpg"), key=lambda p: p.stat().st_mtime, reverse=True)
        if files:
            return send_file(str(files[0]), mimetype='image/jpeg')
    return Response(status_code=404)


@app.route("/api/cameras/<camera_id>/permissions", methods=["POST"])
def api_camera_permissions(camera_id):
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        data = request.get_json()
        resp = requests.post(f"{API_BASE_URL}/cameras/{camera_id}/permissions", json=data, headers=get_api_headers(), timeout=10)
        return resp.json() if resp.status_code == 200 else {"error": "Failed"}
    except requests.exceptions.RequestException:
        return {"error": "Connection error"}


@app.route("/api/cameras/roles/me", methods=["GET", "POST"])
def api_my_role():
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        if request.method == "POST":
            data = request.get_json() or {}
            resp = requests.post(f"{API_BASE_URL}/cameras/roles/me", json=data, headers=get_api_headers(), timeout=10)
        else:
            resp = requests.get(f"{API_BASE_URL}/cameras/roles/me", headers=get_api_headers(), timeout=10)
        return resp.json() if resp.status_code == 200 else {"error": "Failed"}
    except requests.exceptions.RequestException:
        return {"error": "Connection error"}


@app.route("/api/cameras/brands/presets", methods=["GET"])
def api_brand_presets():
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        resp = requests.get(f"{API_BASE_URL}/cameras/brands/presets", headers=get_api_headers(), timeout=5)
        return resp.json() if resp.status_code == 200 else {}
    except requests.exceptions.RequestException:
        return {}


@app.route("/api/cameras/admin/users", methods=["GET"])
def api_admin_list_users():
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        resp = requests.get(f"{API_BASE_URL}/cameras/admin/users", headers=get_api_headers(), timeout=10)
        return resp.json() if resp.status_code == 200 else {"users": [], "error": "Admin only"}
    except requests.exceptions.RequestException:
        return {"users": [], "error": "Connection error"}


# ============== AI Assistants Routes ==============


# ============= AI Assistants Routes =============

@app.route("/api/models")
def api_models():
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        resp = requests.get(f"{API_BASE_URL}/v1/models", headers=get_api_headers(), timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, dict) and "data" in data:
                return data["data"]
            return data
        return []
    except requests.exceptions.RequestException:
        return []


@app.route("/assistants")
def assistants():
    assistants = []
    stats = {"total_assistants": 0, "active_assistants": 0, "total_tasks": 0, "total_logs": 0}

    try:
        resp = requests.get(f"{API_BASE_URL}/assistants", headers=get_api_headers(), timeout=10)
        if resp.status_code == 200:
            assistants = resp.json()
    except requests.exceptions.RequestException:
        pass

    try:
        resp = requests.get(f"{API_BASE_URL}/assistants/stats", headers=get_api_headers(), timeout=10)
        if resp.status_code == 200:
            stats = resp.json()
    except requests.exceptions.RequestException:
        pass

    return render_template("assistants.html", assistants=assistants, stats=stats)


@app.route("/assistants/create", methods=["POST"])
def assistants_create():
    if "access_token" not in session:
        return redirect(url_for("login"))

    name = request.form.get("name")
    template = request.form.get("template", "custom")
    model_id = request.form.get("model_id", "llama3.2:1b")
    personality = request.form.get("personality", "professional")

    if not name:
        flash("Name is required", "error")
        return redirect(url_for("assistants"))

    try:
        payload = {
            "name": name,
            "template": template,
            "model_id": model_id,
            "personality": personality,
            "description": request.form.get("description") or None,
            "system_prompt": request.form.get("system_prompt") or None,
            "temperature": float(request.form["temperature"]) if request.form.get("temperature") else None,
            "max_tokens": int(request.form["max_tokens"]) if request.form.get("max_tokens") else None,
            "color": request.form.get("color") or None,
            "icon": request.form.get("icon") or None,
        }
        tags_raw = request.form.get("tags", "")
        if tags_raw:
            payload["tags"] = [t.strip() for t in tags_raw.split(",") if t.strip()]
        payload = {k: v for k, v in payload.items() if v is not None}
        resp = requests.post(f"{API_BASE_URL}/assistants", json=payload, headers=get_api_headers(), timeout=10)
        if resp.status_code in (200, 201):
            flash(f"Assistant '{name}' created!", "success")
        else:
            flash("Failed to create assistant", "error")
    except requests.exceptions.RequestException as e:
        flash(f"Connection error: {str(e)}", "error")

    return redirect(url_for("assistants"))


@app.route("/assistants/<assistant_id>/delete", methods=["POST"])
def assistants_delete(assistant_id):
    if "access_token" not in session:
        return redirect(url_for("login"))

    try:
        resp = requests.delete(f"{API_BASE_URL}/assistants/{assistant_id}", headers=get_api_headers(), timeout=10)
        if resp.status_code == 200:
            flash("Assistant deleted", "success")
        else:
            flash("Failed to delete assistant", "error")
    except requests.exceptions.RequestException as e:
        flash(f"Connection error: {str(e)}", "error")

    return redirect(url_for("assistants"))


@app.route("/assistants/task/add", methods=["POST"])
def assistants_task_add():
    if "access_token" not in session:
        return redirect(url_for("login"))

    assistant_id = request.form.get("assistant_id")
    task_type = request.form.get("task_type")
    name = request.form.get("name", "")
    schedule = request.form.get("schedule", "")

    if not assistant_id or not task_type:
        flash("Assistant ID and task type are required", "error")
        return redirect(url_for("assistants"))

    try:
        payload = {"task_type": task_type, "name": name, "schedule": schedule}
        resp = requests.post(f"{API_BASE_URL}/assistants/{assistant_id}/tasks",
                             json=payload, headers=get_api_headers(), timeout=10)
        if resp.status_code == 200:
            flash("Task added", "success")
        else:
            flash("Failed to add task", "error")
    except requests.exceptions.RequestException as e:
        flash(f"Connection error: {str(e)}", "error")

    return redirect(url_for("assistants"))


@app.route("/assistants/task/<task_id>/delete", methods=["POST"])
def assistants_task_delete(task_id):
    if "access_token" not in session:
        return redirect(url_for("login"))

    try:
        resp = requests.delete(f"{API_BASE_URL}/assistants/tasks/{task_id}", headers=get_api_headers(), timeout=10)
        if resp.status_code == 200:
            flash("Task deleted", "success")
        else:
            flash("Failed to delete task", "error")
    except requests.exceptions.RequestException as e:
        flash(f"Connection error: {str(e)}", "error")

    return redirect(url_for("assistants"))


@app.route("/integrations")
def integrations():
    resp = make_response(render_template("integrations.html", active_page="integrations"))
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


@app.route("/agent")
def agent():
    if "access_token" not in session:
        return redirect(url_for("login"))
    return render_template("agent.html", active_page="agent")


@app.route("/api/agent/<path:path>", methods=["GET", "POST", "PUT", "DELETE"])
def api_agent_proxy(path):
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        url = f"{API_BASE_URL}/agent/{path}"
        if request.method == "GET":
            resp = requests.get(url, headers=get_api_headers(), params=request.args, timeout=120)
        elif request.method == "POST":
            resp = requests.post(url, headers=get_api_headers(), json=request.get_json(silent=True) or {}, timeout=120)
        elif request.method == "PUT":
            resp = requests.put(url, headers=get_api_headers(), json=request.get_json(silent=True) or {}, params=request.args, timeout=120)
        elif request.method == "DELETE":
            resp = requests.delete(url, headers=get_api_headers(), timeout=120)
        else:
            return jsonify({"error": "Method not allowed"}), 405
        return resp.json() if resp.status_code == 200 else jsonify({"error": resp.text[:500]}), resp.status_code
    except requests.exceptions.RequestException as e:
        return jsonify({"error": str(e)[:300]}), 500


@app.route("/api/mcp/<path:path>", methods=["GET", "POST", "PUT", "DELETE"])
def api_mcp_proxy(path):
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        url = f"{API_BASE_URL}/mcp/{path}"
        if request.method == "GET":
            resp = requests.get(url, headers=get_api_headers(), params=request.args, timeout=30)
        elif request.method == "POST":
            resp = requests.post(url, headers=get_api_headers(), json=request.get_json(silent=True) or {}, timeout=60)
        elif request.method == "DELETE":
            resp = requests.delete(url, headers=get_api_headers(), timeout=30)
        else:
            return jsonify({"error": "Method not allowed"}), 405
        return resp.json() if resp.status_code == 200 else jsonify({"error": resp.text[:500]}), resp.status_code
    except requests.exceptions.RequestException as e:
        return jsonify({"error": str(e)[:300]}), 500


@app.route("/api/assistants")
def api_assistants():
    try:
        resp = requests.get(f"{API_BASE_URL}/assistants", headers=get_api_headers(), timeout=10)
        return resp.json() if resp.status_code == 200 else []
    except requests.exceptions.RequestException:
        return []


@app.route("/api/assistants/<assistant_id>")
def api_assistant(assistant_id):
    try:
        resp = requests.get(f"{API_BASE_URL}/assistants/{assistant_id}", headers=get_api_headers(), timeout=10)
        return resp.json() if resp.status_code == 200 else {"detail": "Not found"}
    except requests.exceptions.RequestException:
        return {"detail": "Connection error"}


@app.route("/api/assistants/stats")
def api_assistants_stats():
    try:
        resp = requests.get(f"{API_BASE_URL}/assistants/stats", headers=get_api_headers(), timeout=10)
        return resp.json() if resp.status_code == 200 else {}
    except requests.exceptions.RequestException:
        return {}


@app.route("/api/assistants/<assistant_id>/chat", methods=["POST"])
def api_assistants_chat(assistant_id):
    try:
        data = request.get_json()
        resp = requests.post(
            f"{API_BASE_URL}/assistants/{assistant_id}/chat",
            json=data,
            headers=get_api_headers(),
            timeout=120
        )
        return resp.json() if resp.status_code == 200 else {"response": "Error", "success": False}
    except requests.exceptions.RequestException:
        return {"response": "Connection error", "success": False}


@app.route("/api/assistants/proxy", methods=["GET", "POST", "PUT", "DELETE"])
@app.route("/api/assistants/proxy/", methods=["GET", "POST", "PUT", "DELETE"])
def api_assistants_proxy_root():
    return _assistants_proxy_forward("")


def _assistants_proxy_forward(path):
    url = f"{API_BASE_URL}/assistants/{path}" if path else f"{API_BASE_URL}/assistants"
    try:
        resp = _proxy_request(request.method, url, timeout=60)
        if resp is None:
            return jsonify({"error": "Method not allowed"}), 405
        data, status = _handle_proxy_response(resp)
        return jsonify(data), status
    except requests.exceptions.RequestException as e:
        return jsonify({"error": str(e)[:300]}), 500


@app.route("/api/assistants/proxy/<path:path>", methods=["GET", "POST", "PUT", "DELETE"])
def api_assistants_proxy(path):
    return _assistants_proxy_forward(path)


# ============= Integrations API Routes =============

@app.route("/api/integrations/test", methods=["POST"])
def api_integration_test():
    try:
        data = request.get_json()
        resp = requests.post(f"{API_BASE_URL}/integrations/test", json=data, headers=get_api_headers(), timeout=15)
        return resp.json() if resp.status_code == 200 else {"success": False, "message": "Test failed"}
    except requests.exceptions.RequestException:
        return {"success": False, "message": "Connection error"}


@app.route("/api/integrations/read", methods=["POST"])
def api_integration_read():
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        data = request.get_json()
        integration_type = data.get("integration_type", "")
        config = data.get("config", {})
        folder = data.get("folder", "INBOX")
        channel_id = data.get("channel_id")
        limit = data.get("limit", 20)

        resp = requests.post(
            f"{API_BASE_URL}/integrations/{integration_type}/read",
            json=config,
            params={"folder": folder, "channel_id": channel_id, "limit": limit},
            headers=get_api_headers(), timeout=30
        )
        return resp.json() if resp.status_code == 200 else {"success": False, "messages": []}
    except requests.exceptions.RequestException:
        return {"success": False, "messages": [], "error": "Connection error"}


@app.route("/api/integrations/send", methods=["POST"])
def api_integration_send():
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        data = request.get_json()
        integration_type = data.get("integration_type", "")
        to = data.get("to", "")
        text = data.get("text", "")
        config = data.get("config", {})
        reply_to = data.get("reply_to")

        payload = {"to": to, "text": text, "reply_to": reply_to}
        resp = requests.post(
            f"{API_BASE_URL}/integrations/{integration_type}/send",
            json=payload,
            params={"config": json.dumps(config)} if config else {},
            headers=get_api_headers(), timeout=15
        )
        return resp.json() if resp.status_code == 200 else {"success": False, "message": "Send failed"}
    except requests.exceptions.RequestException:
        return {"success": False, "message": "Connection error"}


@app.route("/api/integrations/email/read", methods=["POST"])
def api_email_read():
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        data = request.get_json()
        config = data.get("config", {})
        folder = data.get("folder", "INBOX")
        limit = data.get("limit", 20)
        unread_only = data.get("unread_only", False)

        resp = requests.post(
            f"{API_BASE_URL}/integrations/email/read",
            json=config,
            params={"folder": folder, "limit": limit, "unread_only": unread_only},
            headers=get_api_headers(), timeout=30
        )
        return resp.json() if resp.status_code == 200 else {"success": False, "emails": []}
    except requests.exceptions.RequestException:
        return {"success": False, "emails": [], "error": "Connection error"}


@app.route("/api/integrations/email/compose", methods=["POST"])
def api_email_compose():
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        data = request.get_json()
        resp = requests.post(
            f"{API_BASE_URL}/integrations/email/compose",
            json=data,
            headers=get_api_headers(), timeout=15
        )
        return resp.json() if resp.status_code == 200 else {"success": False}
    except requests.exceptions.RequestException:
        return {"success": False, "message": "Connection error"}


@app.route("/api/integrations/telegram/updates", methods=["POST"])
def api_telegram_updates():
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        data = request.get_json()
        config = data.get("config", {})
        limit = data.get("limit", 20)

        resp = requests.post(
            f"{API_BASE_URL}/integrations/telegram/updates",
            json=config,
            params={"limit": limit},
            headers=get_api_headers(), timeout=15
        )
        return resp.json() if resp.status_code == 200 else {"success": False, "messages": []}
    except requests.exceptions.RequestException:
        return {"success": False, "messages": [], "error": "Connection error"}


@app.route("/api/integrations/telegram/send", methods=["POST"])
def api_telegram_send():
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        data = request.get_json()
        payload = {"to": data.get("chat_id", ""), "text": data.get("text", "")}
        config = data.get("config", {})

        resp = requests.post(
            f"{API_BASE_URL}/integrations/telegram/send",
            json=payload,
            params={"config": json.dumps(config)} if config else {},
            headers=get_api_headers(), timeout=15
        )
        return resp.json() if resp.status_code == 200 else {"success": False}
    except requests.exceptions.RequestException:
        return {"success": False, "message": "Connection error"}


@app.route("/api/integrations/discord/guilds", methods=["POST"])
def api_discord_guilds():
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        data = request.get_json()
        config = data.get("config", {})

        resp = requests.post(
            f"{API_BASE_URL}/integrations/discord/guilds",
            json=config,
            headers=get_api_headers(), timeout=15
        )
        return resp.json() if resp.status_code == 200 else {"guilds": []}
    except requests.exceptions.RequestException:
        return {"guilds": []}


@app.route("/api/integrations/discord/channels", methods=["POST"])
def api_discord_channels():
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        data = request.get_json()
        guild_id = data.get("guild_id", "")
        config = data.get("config", {})

        resp = requests.post(
            f"{API_BASE_URL}/integrations/discord/channels",
            json=config,
            params={"guild_id": guild_id},
            headers=get_api_headers(), timeout=15
        )
        return resp.json() if resp.status_code == 200 else {"channels": []}
    except requests.exceptions.RequestException:
        return {"channels": []}


@app.route("/api/integrations/discord/messages", methods=["POST"])
def api_discord_messages():
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        data = request.get_json()
        channel_id = data.get("channel_id", "")
        config = data.get("config", {})
        limit = data.get("limit", 20)

        resp = requests.post(
            f"{API_BASE_URL}/integrations/discord/messages",
            json=config,
            params={"channel_id": channel_id, "limit": limit},
            headers=get_api_headers(), timeout=15
        )
        return resp.json() if resp.status_code == 200 else {"messages": []}
    except requests.exceptions.RequestException:
        return {"messages": []}


@app.route("/api/integrations/discord/send", methods=["POST"])
def api_discord_send():
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        data = request.get_json()
        payload = {"to": data.get("channel_id", ""), "text": data.get("text", "")}
        config = data.get("config", {})

        resp = requests.post(
            f"{API_BASE_URL}/integrations/discord/send",
            json=payload,
            params={"config": json.dumps(config)} if config else {},
            headers=get_api_headers(), timeout=15
        )
        return resp.json() if resp.status_code == 200 else {"success": False}
    except requests.exceptions.RequestException:
        return {"success": False, "message": "Connection error"}


@app.route("/api/integrations/facebook/posts", methods=["POST"])
def api_facebook_posts():
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        data = request.get_json()
        config = data.get("config", {})
        limit = data.get("limit", 10)

        resp = requests.post(
            f"{API_BASE_URL}/integrations/facebook/posts",
            json=config,
            params={"limit": limit},
            headers=get_api_headers(), timeout=15
        )
        return resp.json() if resp.status_code == 200 else {"posts": []}
    except requests.exceptions.RequestException:
        return {"posts": []}


@app.route("/api/integrations/facebook/comments", methods=["POST"])
def api_facebook_comments():
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        data = request.get_json()
        post_id = data.get("post_id", "")
        config = data.get("config", {})

        resp = requests.post(
            f"{API_BASE_URL}/integrations/facebook/comments",
            json=config,
            params={"post_id": post_id},
            headers=get_api_headers(), timeout=15
        )
        return resp.json() if resp.status_code == 200 else {"comments": []}
    except requests.exceptions.RequestException:
        return {"comments": []}


@app.route("/api/integrations/facebook/comment", methods=["POST"])
def api_facebook_comment():
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        data = request.get_json()
        payload = {"to": data.get("post_id", ""), "text": data.get("text", "")}
        config = data.get("config", {})

        resp = requests.post(
            f"{API_BASE_URL}/integrations/facebook/comment",
            json=payload,
            params={"config": json.dumps(config)} if config else {},
            headers=get_api_headers(), timeout=15
        )
        return resp.json() if resp.status_code == 200 else {"success": False}
    except requests.exceptions.RequestException:
        return {"success": False, "message": "Connection error"}


@app.route("/api/integrations/whatsapp/send", methods=["POST"])
def api_whatsapp_send():
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        data = request.get_json()
        payload = {"to": data.get("to", ""), "text": data.get("text", "")}
        config = data.get("config", {})

        resp = requests.post(
            f"{API_BASE_URL}/integrations/whatsapp/send",
            json=payload,
            params={"config": json.dumps(config)} if config else {},
            headers=get_api_headers(), timeout=15
        )
        return resp.json() if resp.status_code == 200 else {"success": False}
    except requests.exceptions.RequestException:
        return {"success": False, "message": "Connection error"}


@app.route("/api/integrations/messenger/send", methods=["POST"])
def api_messenger_send():
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        data = request.get_json()
        payload = {"to": data.get("recipient_id", ""), "text": data.get("text", "")}
        config = data.get("config", {})

        resp = requests.post(
            f"{API_BASE_URL}/integrations/messenger/send",
            json=payload,
            params={"config": json.dumps(config)} if config else {},
            headers=get_api_headers(), timeout=15
        )
        return resp.json() if resp.status_code == 200 else {"success": False}
    except requests.exceptions.RequestException:
        return {"success": False, "message": "Connection error"}


# ============= QR Code / Barcode Integration =============

@app.route("/api/integrations/qr/generate", methods=["POST"])
def api_qr_generate():
    data = request.get_json(silent=True) or {}
    content = data.get("content", "https://openlocalai.dev")
    size = data.get("size", 300)
    try:
        import qrcode
        from io import BytesIO
        import base64
        qr = qrcode.QRCode(version=1, box_size=10, border=2)
        qr.add_data(content)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode()
        return jsonify({"success": True, "image": f"data:image/png;base64,{b64}", "content": content})
    except ImportError:
        return jsonify({"success": False, "error": "qrcode module not installed. Run: pip install qrcode[pil]"}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/integrations/barcode/scan", methods=["POST"])
def api_barcode_scan():
    if "image" not in request.files:
        return jsonify({"success": False, "error": "No image provided"}), 400
    file = request.files["image"]
    try:
        import cv2
        import numpy as np
        from pyzbar import pyzbar
        file_bytes = np.frombuffer(file.read(), np.uint8)
        img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
        barcodes = pyzbar.decode(img)
        results = []
        for barcode in barcodes:
            results.append({
                "data": barcode.data.decode("utf-8"),
                "type": barcode.type,
                "rect": {"x": barcode.rect.left, "y": barcode.rect.top, "w": barcode.rect.width, "h": barcode.rect.height}
            })
        return jsonify({"success": True, "barcodes": results, "count": len(results)})
    except ImportError:
        return jsonify({"success": False, "error": "opencv/pyzbar not installed"}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/integrations/barcode/generate", methods=["POST"])
def api_barcode_generate():
    data = request.get_json(silent=True) or {}
    content = data.get("content", "TEST-12345")
    barcode_type = data.get("type", "code128")
    try:
        from barcode import Code128, Code39, EAN13
        from barcode.writer import ImageWriter
        from io import BytesIO
        import base64
        writers = {"code128": Code128, "code39": Code39, "ean13": EAN13}
        cls = writers.get(barcode_type, Code128)
        barcode_obj = cls(content, writer=ImageWriter())
        buf = BytesIO()
        barcode_obj.write(buf)
        b64 = base64.b64encode(buf.getvalue()).decode()
        return jsonify({"success": True, "image": f"data:image/png;base64,{b64}", "content": content, "type": barcode_type})
    except ImportError:
        return jsonify({"success": False, "error": "python-barcode not installed. Run: pip install python-barcode"}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ============= Webhook Manager =============

WEBHOOKS_FILE = "/www/AI_server/data/webhooks.json"

def _load_webhooks():
    import os
    if os.path.exists(WEBHOOKS_FILE):
        with open(WEBHOOKS_FILE) as f:
            return json.load(f)
    return []

def _save_webhooks(hooks):
    import os
    os.makedirs(os.path.dirname(WEBHOOKS_FILE), exist_ok=True)
    with open(WEBHOOKS_FILE, "w") as f:
        json.dump(hooks, f, indent=2)

@app.route("/api/integrations/webhooks", methods=["GET"])
def api_webhooks_list():
    hooks = _load_webhooks()
    user_id = session.get("user", {}).get("id", "default")
    return jsonify([h for h in hooks if h.get("user_id") == user_id])

@app.route("/api/integrations/webhooks", methods=["POST"])
def api_webhooks_create():
    data = request.get_json(silent=True) or {}
    hooks = _load_webhooks()
    import uuid
    hook = {
        "id": str(uuid.uuid4()),
        "user_id": session.get("user", {}).get("id", "default"),
        "name": data.get("name", "Untitled Webhook"),
        "url": data.get("url", ""),
        "method": data.get("method", "POST"),
        "headers": data.get("headers", {}),
        "body": data.get("body", ""),
        "events": data.get("events", []),
        "active": True,
        "last_triggered": None,
        "trigger_count": 0,
        "created_at": datetime.now().isoformat()
    }
    hooks.append(hook)
    _save_webhooks(hooks)
    return jsonify({"success": True, "webhook": hook})

@app.route("/api/integrations/webhooks/<hook_id>", methods=["DELETE"])
def api_webhooks_delete(hook_id):
    hooks = _load_webhooks()
    hooks = [h for h in hooks if h["id"] != hook_id]
    _save_webhooks(hooks)
    return jsonify({"success": True})

@app.route("/api/integrations/webhooks/<hook_id>/test", methods=["POST"])
def api_webhooks_test(hook_id):
    hooks = _load_webhooks()
    hook = next((h for h in hooks if h["id"] == hook_id), None)
    if not hook:
        return jsonify({"error": "Webhook not found"}), 404
    try:
        resp = requests.request(
            method=hook.get("method", "POST"),
            url=hook["url"],
            headers=hook.get("headers", {}),
            json=hook.get("body") if hook.get("body") else None,
            timeout=10
        )
        hook["last_triggered"] = datetime.now().isoformat()
        hook["trigger_count"] = hook.get("trigger_count", 0) + 1
        _save_webhooks(hooks)
        return jsonify({"success": True, "status": resp.status_code, "response": resp.text[:500]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ============= API Connection Tester =============

@app.route("/api/integrations/api-test", methods=["POST"])
def api_connection_test():
    data = request.get_json(silent=True) or {}
    url = data.get("url", "")
    method = data.get("method", "GET")
    headers = data.get("headers", {})
    body = data.get("body", "")
    auth_type = data.get("auth_type", "none")
    auth_token = data.get("auth_token", "")

    if not url:
        return jsonify({"success": False, "error": "URL required"}), 400

    if auth_type == "bearer" and auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"
    elif auth_type == "basic" and auth_token:
        import base64
        headers["Authorization"] = f"Basic {base64.b64encode(auth_token.encode()).decode()}"

    try:
        import time
        start = time.time()
        resp = requests.request(
            method=method.upper(),
            url=url,
            headers=headers,
            json=body if body and method.upper() in ("POST", "PUT", "PATCH") else None,
            timeout=15
        )
        elapsed = round((time.time() - start) * 1000)
        return jsonify({
            "success": True,
            "status": resp.status_code,
            "time_ms": elapsed,
            "headers": dict(resp.headers),
            "body": resp.text[:2000],
            "size": len(resp.content)
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ============= External Services Catalog =============

@app.route("/api/integrations/catalog", methods=["GET"])
def api_integration_catalog():
    return jsonify({
        "services": [
            {"id": "whatsapp_web", "name": "WhatsApp Web", "icon": "fab fa-whatsapp", "color": "green", "category": "messaging", "auth_type": "qr", "description": "Scan QR code to connect WhatsApp Web"},
            {"id": "telegram_bot", "name": "Telegram Bot", "icon": "fab fa-telegram", "color": "sky", "category": "messaging", "auth_type": "token", "description": "Connect via Bot Token from @BotFather"},
            {"id": "slack", "name": "Slack", "icon": "fab fa-slack", "color": "purple", "category": "messaging", "auth_type": "token", "description": "Connect to Slack workspace"},
            {"id": "discord_bot", "name": "Discord Bot", "icon": "fab fa-discord", "color": "indigo", "category": "messaging", "auth_type": "token", "description": "Connect Discord bot"},
            {"id": "email_imap", "name": "Email (IMAP/SMTP)", "icon": "fas fa-envelope", "color": "blue", "category": "messaging", "auth_type": "credentials", "description": "Read and send emails"},
            {"id": "github", "name": "GitHub", "icon": "fab fa-github", "color": "gray", "category": "dev", "auth_type": "token", "description": "Repos, issues, pull requests"},
            {"id": "gitlab", "name": "GitLab", "icon": "fab fa-gitlab", "color": "orange", "category": "dev", "auth_type": "token", "description": "Repos, issues, CI/CD"},
            {"id": "jira", "name": "Jira", "icon": "fab fa-jira", "color": "blue", "category": "dev", "auth_type": "token", "description": "Project management and issues"},
            {"id": "google_calendar", "name": "Google Calendar", "icon": "fas fa-calendar", "color": "blue", "category": "productivity", "auth_type": "oauth", "description": "Events and scheduling"},
            {"id": "google_sheets", "name": "Google Sheets", "icon": "fas fa-table", "color": "green", "category": "productivity", "auth_type": "oauth", "description": "Spreadsheet integration"},
            {"id": "notion", "name": "Notion", "icon": "fas fa-book", "color": "gray", "category": "productivity", "auth_type": "token", "description": "Notes, docs, databases"},
            {"id": "stripe", "name": "Stripe", "icon": "fas fa-credit-card", "color": "purple", "category": "payments", "auth_type": "token", "description": "Payment processing webhooks"},
            {"id": "paypal", "name": "PayPal", "icon": "fab fa-paypal", "color": "blue", "category": "payments", "auth_type": "token", "description": "Payment notifications"},
            {"id": "twilio_sms", "name": "Twilio SMS", "icon": "fas fa-sms", "color": "red", "category": "messaging", "auth_type": "credentials", "description": "Send and receive SMS"},
            {"id": "openai_api", "name": "OpenAI API", "icon": "fas fa-brain", "color": "green", "category": "ai", "auth_type": "token", "description": "GPT-4, DALL-E, Whisper"},
            {"id": "anthropic_api", "name": "Anthropic API", "icon": "fas fa-robot", "color": "amber", "category": "ai", "auth_type": "token", "description": "Claude models"},
            {"id": "mqtt", "name": "MQTT (IoT)", "icon": "fas fa-microchip", "color": "cyan", "category": "iot", "auth_type": "credentials", "description": "IoT device messaging"},
            {"id": "webhook_custom", "name": "Custom Webhook", "icon": "fas fa-plug", "color": "gray", "category": "custom", "auth_type": "url", "description": "Any HTTP endpoint"},
            {"id": "n8n", "name": "n8n Automation", "icon": "fas faworkflow", "color": "red", "category": "automation", "auth_type": "token", "description": "Workflow automation"},
            {"id": "zapier", "name": "Zapier", "icon": "fas fa-bolt", "color": "orange", "category": "automation", "auth_type": "token", "description": "App automation platform"},
        ]
    })


# ============= WhatsApp Web Bridge (Node.js) =============

WA_BRIDGE_URL = "http://localhost:3333"


def _wa_bridge_request(method, path, timeout=30, **kwargs):
    try:
        return requests.request(method, f"{WA_BRIDGE_URL}{path}", timeout=timeout, **kwargs)
    except requests.exceptions.RequestException as e:
        return None


@app.route("/api/integrations/whatsapp/qr", methods=["POST"])
def api_whatsapp_qr():
    data = request.get_json(silent=True) or {}
    phone = data.get("phone", "")
    message = data.get("message", "Hello! I'm interested in your business.")
    session_id = data.get("session_id", f"wa_{session.get('user', {}).get('id', 'default')}")

    bridge = _wa_bridge_request("POST", f"/sessions/{session_id}/init", timeout=10)
    if bridge is None:
        return jsonify({
            "success": False,
            "error": "WhatsApp bridge not running. Please start it with: cd /www/AI_server/whatsapp_web && node server.js",
            "fallback": True
        }), 503

    import time
    for _ in range(20):
        time.sleep(1)
        qr_resp = _wa_bridge_request("GET", f"/sessions/{session_id}/qr", timeout=5)
        if qr_resp and qr_resp.status_code == 200:
            try:
                d = qr_resp.json()
                if d.get("success"):
                    return jsonify({
                        "success": True,
                        "image": d.get("qrImage"),
                        "content": d.get("qr"),
                        "session_id": session_id,
                        "is_real_whatsapp_web": True,
                        "instructions": "Open WhatsApp on your iPhone → Settings → Linked Devices → Link a Device → Scan this QR code",
                        "scan_steps": [
                            "1. Open WhatsApp Business on your iPhone",
                            "2. Tap Settings (gear icon) at the bottom right",
                            "3. Tap 'Linked Devices'",
                            "4. Tap 'Link a Device'",
                            "5. Point your camera at this QR code"
                        ]
                    })
            except Exception:
                pass

    return jsonify({
        "success": False,
        "error": "QR code not ready yet. Please try again in a few seconds.",
        "session_id": session_id
    }), 408


@app.route("/api/integrations/whatsapp/status", methods=["GET"])
def api_whatsapp_status():
    session_id = request.args.get("session_id", f"wa_{session.get('user', {}).get('id', 'default')}")
    bridge = _wa_bridge_request("GET", f"/sessions/{session_id}/status", timeout=5)
    if bridge is None:
        return jsonify({"success": False, "bridge_running": False, "error": "Bridge not running"}), 503
    try:
        return jsonify(bridge.json())
    except Exception:
        return jsonify({"success": False, "error": "Invalid response from bridge"}), 500


@app.route("/api/integrations/whatsapp/logout", methods=["POST"])
def api_whatsapp_logout():
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id", f"wa_{session.get('user', {}).get('id', 'default')}")
    bridge = _wa_bridge_request("POST", f"/sessions/{session_id}/logout", timeout=15)
    if bridge is None:
        return jsonify({"success": False, "error": "Bridge not running"}), 503
    try:
        return jsonify(bridge.json())
    except Exception:
        return jsonify({"success": False, "error": "Invalid response"}), 500


@app.route("/api/integrations/whatsapp/send-wa", methods=["POST"])
def api_whatsapp_send_wa():
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id", f"wa_{session.get('user', {}).get('id', 'default')}")
    to = data.get("to", "")
    text = data.get("text", "")
    if not to or not text:
        return jsonify({"success": False, "message": "Recipient and text required"}), 400
    bridge = _wa_bridge_request("POST", f"/sessions/{session_id}/send", json={"to": to, "text": text}, timeout=15)
    if bridge is None:
        return jsonify({"success": False, "error": "Bridge not running"}), 503
    try:
        return jsonify(bridge.json())
    except Exception:
        return jsonify({"success": False, "error": "Invalid response"}), 500


@app.route("/api/integrations/whatsapp/chat-link-qr", methods=["POST"])
def api_whatsapp_chat_link_qr():
    """Generate a wa.me click-to-chat QR code (works with WhatsApp Business app)"""
    data = request.get_json(silent=True) or {}
    phone = data.get("phone", "")
    message = data.get("message", "Hello! I'm interested in your business.")
    try:
        import qrcode
        from io import BytesIO
        import base64
        import urllib.parse

        clean_phone = ''.join(c for c in phone if c.isdigit())
        if not clean_phone:
            qr_content = "https://www.whatsapp.com/channel/"
            instructions = "Scan with WhatsApp to open the official WhatsApp channel directory."
        else:
            qr_content = f"https://wa.me/{clean_phone}?text={urllib.parse.quote(message)}"
            instructions = f"Scan with your iPhone WhatsApp Business app to start a chat with +{clean_phone}."

        qr = qrcode.QRCode(version=1, box_size=10, border=2, error_correction=qrcode.constants.ERROR_CORRECT_M)
        qr.add_data(qr_content)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode()
        return jsonify({
            "success": True,
            "image": f"data:image/png;base64,{b64}",
            "content": qr_content,
            "phone": clean_phone,
            "instructions": instructions,
            "scan_steps": [
                "1. Open WhatsApp Business on your iPhone",
                "2. Tap the camera icon next to the new chat button",
                "3. Point your camera at this QR code",
                "4. WhatsApp will open a chat with the business"
            ]
        })
    except ImportError:
        return jsonify({"success": False, "error": "qrcode module not installed"}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/integrations/whatsapp/test", methods=["POST"])
def api_whatsapp_test():
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    config = data.get("config", {})
    if not config.get("phone_number_id") or not config.get("access_token"):
        return jsonify({"success": False, "message": "Phone Number ID and Access Token required"}), 400
    try:
        from src.services.integrations_service import WhatsAppIntegration
        wa = WhatsAppIntegration(config)
        result = wa.test_connection()
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "message": str(e)[:200]}), 500


@app.route("/api/integrations/whatsapp/webhook", methods=["GET", "POST"])
def api_whatsapp_webhook():
    if request.method == "GET":
        verify_token = request.args.get("hub.verify_token", "")
        challenge = request.args.get("hub.challenge", "")
        expected = "openlocalai_whatsapp_token"
        if verify_token == expected:
            return challenge, 200
        return "Forbidden", 403
    try:
        payload = request.get_json(silent=True) or {}
        entries = payload.get("entry", [])
        for entry in entries:
            changes = entry.get("changes", [])
            for change in changes:
                value = change.get("value", {})
                messages = value.get("messages", [])
                for msg in messages:
                    from_num = msg.get("from", "")
                    msg_type = msg.get("type", "")
                    text = ""
                    if msg_type == "text":
                        text = msg.get("text", {}).get("body", "")
                    elif msg_type == "image":
                        text = "[Image]"
                    elif msg_type == "audio":
                        text = "[Audio]"
                    elif msg_type == "video":
                        text = "[Video]"
                    else:
                        text = f"[{msg_type}]"
                    save_whatsapp_message(from_num, text, msg_type, "inbound", value.get("metadata", {}).get("phone_number_id", ""))
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 200


def save_whatsapp_message(from_num, text, msg_type, direction, phone_id):
    import json as json_mod
    import os
    storage_path = "/www/AI_server/data/whatsapp_messages.json"
    os.makedirs(os.path.dirname(storage_path), exist_ok=True)
    messages = []
    if os.path.exists(storage_path):
        try:
            with open(storage_path, 'r') as f:
                messages = json_mod.load(f)
        except:
            messages = []
    from datetime import datetime
    messages.append({
        "from": from_num,
        "text": text,
        "type": msg_type,
        "direction": direction,
        "phone_id": phone_id,
        "timestamp": datetime.utcnow().isoformat()
    })
    messages = messages[-200:]
    with open(storage_path, 'w') as f:
        json_mod.dump(messages, f, indent=2)


@app.route("/api/integrations/whatsapp/messages", methods=["GET"])
def api_whatsapp_messages():
    import json as json_mod
    import os
    storage_path = "/www/AI_server/data/whatsapp_messages.json"
    if not os.path.exists(storage_path):
        return jsonify({"success": True, "messages": []})
    try:
        with open(storage_path, 'r') as f:
            messages = json_mod.load(f)
        return jsonify({"success": True, "messages": messages[-50:]})
    except:
        return jsonify({"success": True, "messages": []})


@app.route("/api/integrations/telegram/qr", methods=["POST"])
def api_telegram_qr():
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    bot_token = data.get("bot_token", "")
    if not bot_token:
        return jsonify({"success": False, "error": "Bot token required"}), 400
    try:
        import qrcode
        from io import BytesIO
        import base64
        qr_content = f"https://t.me/{bot_token.split(':')[0]}" if ":" in bot_token else "https://t.me/BotFather"
        qr = qrcode.QRCode(version=1, box_size=10, border=2)
        qr.add_data(qr_content)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode()
        return jsonify({"success": True, "image": f"data:image/png;base64,{b64}", "content": qr_content, "instructions": "Scan to open your Telegram bot"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)


# ============= Admin RBAC Routes =============

def require_admin(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if "access_token" not in session:
            return redirect(url_for("login"))
        if not session.get("user", {}).get("is_admin"):
            flash("Admin access required", "error")
            return redirect(url_for("dashboard"))
        return f(*args, **kwargs)
    return decorated


@app.route("/admin/users")
@require_admin
def admin_users():
    try:
        resp = requests.get(f"{API_BASE_URL}/rbac/users/roles", headers=get_api_headers(), timeout=10)
        users = resp.json() if resp.status_code == 200 else []
    except:
        users = []
    return render_template("admin/users.html", users=users)


@app.route("/admin/roles")
@require_admin
def admin_roles():
    try:
        resp = requests.get(f"{API_BASE_URL}/rbac/roles?include_permissions=true", headers=get_api_headers(), timeout=10)
        roles = resp.json() if resp.status_code == 200 else []
    except:
        roles = []
    return render_template("admin/roles.html", roles=roles)


@app.route("/admin/permissions")
@require_admin
def admin_permissions():
    try:
        resp = requests.get(f"{API_BASE_URL}/rbac/permissions", headers=get_api_headers(), timeout=10)
        permissions = resp.json() if resp.status_code == 200 else []
    except:
        permissions = []
    try:
        modules_resp = requests.get(f"{API_BASE_URL}/rbac/modules?include_menus=true", headers=get_api_headers(), timeout=10)
        modules = modules_resp.json() if modules_resp.status_code == 200 else []
    except:
        modules = []
    return render_template("admin/permissions.html", permissions=permissions, modules=modules)


@app.route("/admin/menus")
@require_admin
def admin_menus():
    try:
        modules_resp = requests.get(f"{API_BASE_URL}/rbac/modules?include_menus=true", headers=get_api_headers(), timeout=10)
        modules = modules_resp.json() if modules_resp.status_code == 200 else []
    except:
        modules = []
    return render_template("admin/menus.html", modules=modules)


@app.route("/admin/init-rbac", methods=["POST"])
@require_admin
def admin_init_rbac():
    try:
        resp = requests.post(f"{API_BASE_URL}/rbac/init", headers=get_api_headers(), timeout=10)
        if resp.status_code == 200:
            flash("RBAC system initialized successfully!", "success")
        else:
            flash("Failed to initialize RBAC", "error")
    except Exception as e:
        flash(f"Connection error: {str(e)}", "error")
    return redirect(url_for("admin_roles"))


@app.route("/api/admin/roles", methods=["POST"])
@require_admin
def api_create_role():
    data = request.get_json(silent=True) or {}
    try:
        resp = requests.post(f"{API_BASE_URL}/rbac/roles", json=data, headers=get_api_headers(), timeout=10)
        return resp.json(), resp.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/admin/roles/<role_id>", methods=["PUT"])
@require_admin
def api_update_role(role_id):
    data = request.get_json(silent=True) or {}
    try:
        resp = requests.put(f"{API_BASE_URL}/rbac/roles/{role_id}", json=data, headers=get_api_headers(), timeout=10)
        return resp.json(), resp.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/admin/roles/<role_id>", methods=["DELETE"])
@require_admin
def api_delete_role(role_id):
    try:
        resp = requests.delete(f"{API_BASE_URL}/rbac/roles/{role_id}", headers=get_api_headers(), timeout=10)
        return resp.json(), resp.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/admin/roles/<role_id>/toggle", methods=["POST"])
@require_admin
def api_toggle_role(role_id):
    try:
        resp = requests.post(f"{API_BASE_URL}/rbac/roles/{role_id}/toggle", headers=get_api_headers(), timeout=10)
        return resp.json(), resp.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/admin/users/<user_id>/role", methods=["POST"])
@require_admin
def api_assign_user_role(user_id):
    data = request.get_json(silent=True) or {}
    try:
        resp = requests.post(f"{API_BASE_URL}/rbac/users/{user_id}/role", json=data, headers=get_api_headers(), timeout=10)
        return resp.json(), resp.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============= AI Chat Proxy (browser -> Flask -> API) =============
@app.route("/api/ai/chat", methods=["POST"])
def api_ai_chat_proxy():
    data = request.get_json(silent=True) or {}
    try:
        resp = requests.post(f"{API_BASE_URL}/v1/chat/completions", json=data, headers=get_api_headers(), timeout=60)
        result = resp.json()
        return jsonify(result), resp.status_code
    except Exception as e:
        return jsonify({"error": str(e)[:300]}), 500


# ============= Integration AI - read messages proxy =============
@app.route("/api/integrations/all/messages", methods=["GET"])
def api_all_messages():
    messages = []
    storage_path = "/www/AI_server/data/whatsapp_messages.json"
    import os
    if os.path.exists(storage_path):
        try:
            with open(storage_path, 'r') as f:
                import json as json_mod
                wa_msgs = json_mod.load(f)
                for m in wa_msgs[-50:]:
                    m['platform'] = 'whatsapp'
                    messages.append(m)
        except:
            pass
    messages.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
    return jsonify({"success": True, "messages": messages[:50]})


@app.route("/api/integrations/email/messages", methods=["GET"])
def api_email_messages_proxy():
    return jsonify({"success": True, "messages": [], "info": "Configure IMAP in connected integrations"})


@app.route("/api/integrations/facebook/messages", methods=["GET"])
def api_facebook_messages_proxy():
    return jsonify({"success": True, "messages": [], "info": "Connect Facebook Page in connected integrations"})


@app.route("/api/integrations/telegram/messages", methods=["GET"])
def api_telegram_messages_proxy():
    return jsonify({"success": True, "messages": [], "info": "Configure Telegram Bot in connected integrations"})


# ============= Video/Audio Call Endpoints =============
@app.route("/api/call/video", methods=["POST"])
def api_video_call():
    data = request.get_json(silent=True) or {}
    room_id = data.get("room_id", f"call-{int(__import__('time').time())}")
    callee = data.get("callee", "")
    caller = data.get("caller", "User")
    return jsonify({
        "success": True,
        "room_id": room_id,
        "join_url": f"/video-call/{room_id}",
        "callee": callee,
        "caller": caller
    })


@app.route("/api/call/audio", methods=["POST"])
def api_audio_call():
    data = request.get_json(silent=True) or {}
    room_id = data.get("room_id", f"call-{int(__import__('time').time())}")
    callee = data.get("callee", "")
    caller = data.get("caller", "User")
    return jsonify({
        "success": True,
        "room_id": room_id,
        "join_url": f"/audio-call/{room_id}",
        "callee": callee,
        "caller": caller
    })


@app.route("/video-call/<room_id>")
def video_call_page(room_id):
    return """<!DOCTYPE html>
<html><head><title>Video Call - """ + room_id + """</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
<style>
body{margin:0;background:#0f172a;font-family:system-ui;color:white;display:flex;flex-direction:column;height:100vh}
#videos{flex:1;display:flex;gap:8px;padding:8px;min-height:0}
video{flex:1;background:#1e293b;border-radius:12px;object-fit:cover;min-height:0}
#controls{display:flex;justify-content:center;gap:12px;padding:16px;background:#1e293b}
.ctrl-btn{width:56px;height:56px;border-radius:50%;border:none;font-size:20px;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:all .2s}
.btn-mute{background:#334155;color:white}
.btn-video{background:#334155;color:white}
.btn-end{background:#ef4444;color:white}
.ctrl-btn:hover{transform:scale(1.1)}
.status{text-align:center;padding:8px;color:#94a3b8;font-size:14px}
</style></head><body>
<div class="status" id="status">Connecting to room: """ + room_id + """...</div>
<div id="videos"><video id="local" autoplay muted playsinline></video><video id="remote" autoplay playsinline></video></div>
<div id="controls">
<button class="ctrl-btn btn-mute" onclick="toggleMute()" title="Mute"><i class="fas fa-microphone"></i></button>
<button class="ctrl-btn btn-video" onclick="toggleVideo()" title="Camera"><i class="fas fa-video"></i></button>
<button class="ctrl-btn btn-end" onclick="endCall()" title="End"><i class="fas fa-phone-slash"></i></button>
</div>
<script>
var localStream,muted=false,camOff=false;
var localV=document.getElementById('local'),remoteV=document.getElementById('remote'),statusEl=document.getElementById('status');
var ROOM='""" + room_id + """';
async function init(){try{localStream=await navigator.mediaDevices.getUserMedia({video:true,audio:true});localV.srcObject=localStream;statusEl.textContent='In call - Room: '+ROOM;}catch(e){statusEl.textContent='Camera/mic access denied. '+e.message;}}
init();
function toggleMute(){muted=!muted;if(localStream)localStream.getAudioTracks().forEach(function(t){t.enabled=!muted});document.querySelector('.btn-mute').innerHTML=muted?'<i class="fas fa-microphone-slash"></i>':'<i class="fas fa-microphone"></i>';}
function toggleVideo(){camOff=!camOff;if(localStream)localStream.getVideoTracks().forEach(function(t){t.enabled=!camOff});document.querySelector('.btn-video').innerHTML=camOff?'<i class="fas fa-video-slash"></i>':'<i class="fas fa-video"></i>';}
function endCall(){if(localStream)localStream.getTracks().forEach(function(t){t.stop()});statusEl.textContent='Call ended';document.getElementById('controls').innerHTML='<a href="/integrations" class="ctrl-btn btn-mute" style="width:auto;border-radius:12px;padding:0 24px;text-decoration:none;color:white">Back to Integrations</a>';}
</script></body></html>"""


@app.route("/audio-call/<room_id>")
def audio_call_page(room_id):
    return """<!DOCTYPE html>
<html><head><title>Audio Call - """ + room_id + """</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
<style>
body{margin:0;background:#0f172a;font-family:system-ui;color:white;display:flex;flex-direction:column;height:100vh;align-items:center;justify-content:center}
.caller-avatar{width:120px;height:120px;border-radius:50%;background:linear-gradient(135deg,#6366f1,#8b5cf6);display:flex;align-items:center;justify-content:center;font-size:48px;margin-bottom:24px}
.caller-name{font-size:24px;font-weight:600;margin-bottom:8px}
.caller-status{color:#94a3b8;margin-bottom:40px}
#controls{display:flex;gap:16px}
.ctrl-btn{width:64px;height:64px;border-radius:50%;border:none;font-size:22px;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:all .2s}
.btn-mute{background:#334155;color:white}
.btn-speaker{background:#334155;color:white}
.btn-end{background:#ef4444;color:white}
.ctrl-btn:hover{transform:scale(1.1)}
.pulse{animation:pulse 2s infinite}
@keyframes pulse{0%,100%{box-shadow:0 0 0 0 rgba(99,102,241,.4)}50%{box-shadow:0 0 0 20px rgba(99,102,241,0)}}
</style></head><body>
<div class="caller-avatar pulse" id="avatar"><i class="fas fa-phone"></i></div>
<div class="caller-name">Audio Call</div>
<div class="caller-status" id="status">Room: """ + room_id + """</div>
<div id="controls">
<button class="ctrl-btn btn-mute" onclick="toggleMute()"><i class="fas fa-microphone"></i></button>
<button class="ctrl-btn btn-speaker" onclick="toggleSpeaker()"><i class="fas fa-volume-up"></i></button>
<button class="ctrl-btn btn-end" onclick="endCall()"><i class="fas fa-phone-slash"></i></button>
</div>
<script>
var localStream,muted=false,speakerOn=true;
var statusEl=document.getElementById('status');
async function init(){try{localStream=await navigator.mediaDevices.getUserMedia({audio:true});statusEl.textContent='In call - Room: """ + room_id + """';}catch(e){statusEl.textContent='Mic access denied. '+e.message;}}
init();
function toggleMute(){muted=!muted;if(localStream)localStream.getAudioTracks().forEach(function(t){t.enabled=!muted});document.querySelector('.btn-mute').innerHTML=muted?'<i class="fas fa-microphone-slash"></i>':'<i class="fas fa-microphone"></i>';}
function toggleSpeaker(){speakerOn=!speakerOn;document.querySelector('.btn-speaker').innerHTML=speakerOn?'<i class="fas fa-volume-up"></i>':'<i class="fas fa-volume-mute"></i>';}
function endCall(){if(localStream)localStream.getTracks().forEach(function(t){t.stop()});statusEl.textContent='Call ended';document.querySelector('.caller-avatar').classList.remove('pulse');document.querySelector('.caller-avatar').innerHTML='<i class="fas fa-phone-slash"></i>';document.getElementById('controls').innerHTML='<a href="/integrations" class="ctrl-btn btn-mute" style="width:auto;border-radius:12px;padding:0 24px;text-decoration:none;color:white">Back</a>';}
</script></body></html>"""
