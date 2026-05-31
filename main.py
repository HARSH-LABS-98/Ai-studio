from flask import Flask, render_template, request, jsonify
import os
import requests as req

app = Flask(__name__)

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
SUPABASE_URL       = os.environ.get("SUPABASE_URL")
SUPABASE_KEY       = os.environ.get("SUPABASE_KEY")
VERCEL_TOKEN       = os.environ.get("VERCEL_TOKEN")

def call_ai(messages, model="deepseek/deepseek-chat", max_tokens=3000):
    models_to_try = [
        "deepseek/deepseek-chat",
        "meta-llama/llama-3-8b-instruct:free",
        "mistralai/mistral-7b-instruct:free"
    ]
    for m in models_to_try:
        try:
            print(f"Trying: {m}")
            r = req.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://ai-studio-rzhw.onrender.com",
                    "X-Title": "AI Studio"
                },
                json={
                    "model": m,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": 0.7,
                    "stream": False
                },
                timeout=120,
                stream=False
            )
            print(f"Status: {r.status_code}")
            if r.status_code == 200:
                data = r.json()
                if "choices" in data:
                    return data["choices"][0]["message"]["content"]
            else:
                print(f"Error: {r.text[:200]}")
        except Exception as e:
            print(f"Model {m} failed: {e}")
            continue
    return None

def db_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/api/test")
def test():
    return jsonify({
        "status": "ok",
        "has_key": bool(OPENROUTER_API_KEY),
        "key_start": OPENROUTER_API_KEY[:10] if OPENROUTER_API_KEY else "missing"
    })

@app.route("/api/generate", methods=["POST"])
def generate():
    try:
        data   = request.get_json(force=True, silent=True) or {}
        prompt = data.get("prompt", "").strip()
        if not prompt:
            return jsonify({"error": "No prompt provided"})
        if not OPENROUTER_API_KEY:
            return jsonify({"error": "OPENROUTER_API_KEY not set"})

        system = (
            "You are an expert web developer. "
            "Generate a COMPLETE single-file HTML application. "
            "Return ONLY raw HTML starting with <!DOCTYPE html>. "
            "No markdown, no backticks, no explanation. "
            "All CSS in <style> tags, all JS in <script> tags. "
            "Dark theme, beautiful, fully functional."
        )
        result = call_ai([
            {"role": "system", "content": system},
            {"role": "user", "content": f"Build this app: {prompt}"}
        ], max_tokens=3000)

        if not result:
            return jsonify({"error": "AI failed. Please try again."})

        code = result.strip().replace("```html", "").replace("```", "").strip()
        if not code.startswith("<!"):
            idx = code.find("<!DOCTYPE")
            if idx == -1:
                idx = code.find("<html")
            if idx != -1:
                code = code[idx:]

        return jsonify({"code": code})

    except Exception as e:
        print(f"Generate error: {e}")
        return jsonify({"error": str(e)})

@app.route("/api/chat", methods=["POST"])
def chat():
    try:
        data     = request.get_json(force=True, silent=True) or {}
        messages = data.get("messages", [])
        if not messages:
            return jsonify({"error": "No messages"})

        result = call_ai(
            [{"role": "system", "content": "You are a helpful AI coding assistant. Be concise and practical."}] + messages,
            model="meta-llama/llama-3-8b-instruct:free",
            max_tokens=1500
        )
        return jsonify({"reply": result or "Sorry, could not respond. Try again."})

    except Exception as e:
        return jsonify({"error": str(e)})

@app.route("/api/edit", methods=["POST"])
def edit_code():
    try:
        data        = request.get_json(force=True, silent=True) or {}
        code        = data.get("code", "").strip()
        instruction = data.get("instruction", "").strip()
        if not code or not instruction:
            return jsonify({"error": "Code and instruction required"})

        result = call_ai([
            {"role": "system", "content": "Edit the HTML code based on instruction. Return ONLY complete updated HTML. No markdown."},
            {"role": "user", "content": f"Code:\n{code[:2000]}\n\nInstruction: {instruction}"}
        ], max_tokens=3000)

        if not result:
            return jsonify({"error": "AI failed to edit."})

        updated = result.strip().replace("```html", "").replace("```", "").strip()
        return jsonify({"code": updated})

    except Exception as e:
        return jsonify({"error": str(e)})

@app.route("/api/projects/save", methods=["POST"])
def save_project():
    try:
        data = request.get_json(force=True, silent=True) or {}
        r    = req.post(
            f"{SUPABASE_URL}/rest/v1/projects",
            headers=db_headers(),
            json={"name": data.get("name", "Untitled")[:100], "code": data.get("code", "")},
            timeout=10
        )
        if r.status_code in [200, 201]:
            return jsonify({"success": True, "id": r.json()[0]["id"]})
        return jsonify({"error": r.text[:100]})
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route("/api/projects", methods=["GET"])
def get_projects():
    try:
        r = req.get(
            f"{SUPABASE_URL}/rest/v1/projects?select=id,name,created_at&order=created_at.desc&limit=50",
            headers=db_headers(),
            timeout=10
        )
        return jsonify({"projects": r.json() if r.status_code == 200 else []})
    except Exception as e:
        return jsonify({"projects": [], "error": str(e)})

@app.route("/api/projects/<int:pid>", methods=["GET"])
def get_project(pid):
    try:
        r    = req.get(f"{SUPABASE_URL}/rest/v1/projects?id=eq.{pid}&select=*", headers=db_headers(), timeout=10)
        data = r.json()
        if not data:
            return jsonify({"error": "Not found"})
        return jsonify({"project": data[0]})
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route("/api/projects/<int:pid>", methods=["DELETE"])
def delete_project(pid):
    try:
        req.delete(f"{SUPABASE_URL}/rest/v1/projects?id=eq.{pid}", headers=db_headers(), timeout=10)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route("/api/deploy", methods=["POST"])
def deploy():
    try:
        data = request.get_json(force=True, silent=True) or {}
        code = data.get("code", "")
        name = data.get("name", "my-app").lower().replace(" ", "-")[:50]
        if not code:
            return jsonify({"error": "No code"})
        if not VERCEL_TOKEN:
            return jsonify({"error": "VERCEL_TOKEN not set"})
        r = req.post(
            "https://api.vercel.com/v13/deployments",
            headers={"Authorization": f"Bearer {VERCEL_TOKEN}", "Content-Type": "application/json"},
            json={"name": name, "files": [{"file": "index.html", "data": code}], "projectSettings": {"framework": None}},
            timeout=30
        )
        result = r.json()
        if r.status_code in [200, 201]:
            return jsonify({"url": f"https://{result.get('url', '')}", "success": True})
        return jsonify({"error": result.get("error", {}).get("message", "Deploy failed")})
    except Exception as e:
        return jsonify({"error": str(e)})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
