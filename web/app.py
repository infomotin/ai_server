import os
import requests
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "openlocalai-prod-secret-2024")
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = False

API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")


def get_api_headers():
    headers = {"Content-Type": "application/json"}
    if "access_token" in session:
        headers["Authorization"] = f"Bearer {session['access_token']}"
    return headers


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
        resp = requests.post(
            f"{API_BASE_URL}/database/table/data",
            params={"connection_url": conn_url, "table_name": table_name, "limit": limit, "offset": 0},
            headers=get_api_headers(), timeout=15
        )
        return resp.json() if resp.status_code == 200 else {"columns": [], "rows": []}
    except requests.exceptions.RequestException:
        return {"columns": [], "rows": [], "error": "Connection error"}


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


# ============= AI Assistants Routes =============

@app.route("/assistants")
def assistants():
    if "access_token" not in session:
        return redirect(url_for("login"))

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
        payload = {"name": name, "template": template, "model_id": model_id, "personality": personality}
        resp = requests.post(f"{API_BASE_URL}/assistants", json=payload, headers=get_api_headers(), timeout=10)
        if resp.status_code == 200:
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
    if "access_token" not in session:
        return redirect(url_for("login"))
    return render_template("integrations.html", active_page="integrations")


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
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        resp = requests.get(f"{API_BASE_URL}/assistants", headers=get_api_headers(), timeout=10)
        return resp.json() if resp.status_code == 200 else []
    except requests.exceptions.RequestException:
        return []


@app.route("/api/assistants/<assistant_id>")
def api_assistant(assistant_id):
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        resp = requests.get(f"{API_BASE_URL}/assistants/{assistant_id}", headers=get_api_headers(), timeout=10)
        return resp.json() if resp.status_code == 200 else {"detail": "Not found"}
    except requests.exceptions.RequestException:
        return {"detail": "Connection error"}


@app.route("/api/assistants/stats")
def api_assistants_stats():
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        resp = requests.get(f"{API_BASE_URL}/assistants/stats", headers=get_api_headers(), timeout=10)
        return resp.json() if resp.status_code == 200 else {}
    except requests.exceptions.RequestException:
        return {}


# ============= Integrations API Routes =============

@app.route("/api/integrations/test", methods=["POST"])
def api_integration_test():
    if "access_token" not in session:
        return jsonify({"error": "Unauthorized"}), 401
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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
