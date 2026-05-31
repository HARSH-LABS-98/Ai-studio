            {"role":"user","content":f"Code:\n{code}\n\nInstruction: {instruction}"}
        , model=model)
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
        r    = req.get(
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
