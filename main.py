from flask import Flask, render_template, request, jsonify
from openai import OpenAI
import os, requests as req

app = Flask(__name__)

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
SUPABASE_URL       = os.environ.get("SUPABASE_URL")
SUPABASE_KEY       = os.environ.get("SUPABASE_KEY")
VERCEL_TOKEN       = os.environ.get("VERCEL_TOKEN")

MODELS = {
    "deepseek": "deepseek/deepseek-chat",
    "llama":    "meta-llama/llama-3-8b-instruct:free",
    "mistral":  "mistralai/mistral-7b-instruct:free",
    "gemma":    "google/gemma-7b-it:free"
}

def get_client():
    return OpenAI(
        api_key=OPENROUTER_API_KEY,
        base_url="https://openrouter.ai/api/v1"
    )

def db_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }

def ai_call(messages, model="deepseek", max_tokens=4000):
    for attempt in range(3):
        try:
            r = get_client().chat.completions.create(
                model=MODELS.get(model, MODELS["deepseek"]),
                messages=messages,
                max_tokens=max_tokens,
                temperature=0.7
            )
            return r.choices[0].message.content
        except Exception as e:
            if attempt == 2:
                raise Exception(str(e))

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/api/generate", methods=["POST"])
def generate():
    try:
        data   = request.json
        prompt = data.get("prompt","")
        model  = data.get("model","deepseek")
        if not prompt:
            return jsonify({"error":"No prompt"})
        system = """You are an expert web developer.
Generate a COMPLETE single-file HTML app.
RULES:
- Return ONLY raw HTML, no markdown, no backticks
- All CSS in <style> tags
- All JS in <script> tags
- Dark theme, beautiful, fully functional"""
        code = ai_call([
            {"role":"system","content":system},
            {"role":"user","content":f"Build this: {prompt}"}
        ], model=model)
        code = code.replace("```html","").replace("```","").strip()
        return jsonify({"code":code})
    except Exception as e:
        return jsonify({"error":str(e)})

@app.route("/api/chat", methods=["POST"])
def chat():
    try:
        data     = request.json
        messages = data.get("messages",[])
        model    = data.get("model","llama")
        if not messages:
            return jsonify({"error":"No messages"})
        system = "You are a helpful AI coding assistant. Be concise and practical."
        reply  = ai_call([{"role":"system","content":system}]+messages, model=model, max_tokens=2000)
        return jsonify({"reply":reply})
    except Exception as e:
        return jsonify({"error":str(e)})

@app.route("/api/edit", methods=["POST"])
def edit_code():
    try:
        data        = request.json
        code        = data.get("code","")
        instruction = data.get("instruction","")
        model       = data.get("model","deepseek")
        if not code or not instruction:
            return jsonify({"error":"Code and instruction required"})
        system  = "Edit the HTML code based on instruction. Return ONLY complete updated HTML, no markdown."
        updated = ai_call([
            {"role":"system","content":system},
            {"role":"user","content":f"Code:\n{code}\n\nInstruction: {instruction}"}
        ], model=model)
        updated = updated.replace("```html","").replace("```","").strip()
        return jsonify({"code":updated})
    except Exception as e:
        return jsonify({"error":str(e)})

@app.route("/api/projects/save", methods=["POST"])
def save_project():
    try:
        data = request.json
        r    = req.post(
            f"{SUPABASE_URL}/rest/v1/projects",
            headers=db_headers(),
            json={"name":data.get("name",""),"code":data.get("code","")}
        )
        return jsonify({"success":True,"id":r.json()[0]["id"]})
    except Exception as e:
        return jsonify({"error":str(e)})

@app.route("/api/projects", methods=["GET"])
def get_projects():
    try:
        r = req.get(
            f"{SUPABASE_URL}/rest/v1/projects?select=id,name,created_at&order=created_at.desc&limit=50",
            headers=db_headers()
        )
        return jsonify({"projects":r.json()})
    except Exception as e:
        return jsonify({"error":str(e)})

@app.route("/api/projects/<int:pid>", methods=["GET"])
def get_project(pid):
    try:
        r = req.get(
            f"{SUPABASE_URL}/rest/v1/projects?id=eq.{pid}&select=*",
            headers=db_headers()
        )
        data = r.json()
        if not data:
            return jsonify({"error":"Not found"})
        return jsonify({"project":data[0]})
    except Exception as e:
        return jsonify({"error":str(e)})

@app.route("/api/projects/<int:pid>", methods=["DELETE"])
def delete_project(pid):
    try:
        req.delete(
            f"{SUPABASE_URL}/rest/v1/projects?id=eq.{pid}",
            headers=db_headers()
        )
        return jsonify({"success":True})
    except Exception as e:
        return jsonify({"error":str(e)})

@app.route("/api/deploy", methods=["POST"])
def deploy():
    try:
        data = request.json
        code = data.get("code","")
        name = data.get("name","my-ai-app").lower().replace(" ","-")
        if not code:
            return jsonify({"error":"No code"})
        if not VERCEL_TOKEN:
            return jsonify({"error":"VERCEL_TOKEN not set"})
        r = req.post(
            "https://api.vercel.com/v13/deployments",
            headers={"Authorization":f"Bearer {VERCEL_TOKEN}","Content-Type":"application/json"},
            json={"name":name,"files":[{"file":"index.html","data":code}],"projectSettings":{"framework":None}},
            timeout=30
        )
        result = r.json()
        if r.status_code in [200,201]:
            return jsonify({"url":f"https://{result.get('url','')}","success":True})
        return jsonify({"error":result.get("error",{}).get("message","Deploy failed")})
    except Exception as e:
        return jsonify({"error":str(e)})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
