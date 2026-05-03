import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

from ai_engine import analyze_code

load_dotenv()

app = Flask(__name__)
CORS(app)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/api/analyze")
def api_analyze():
    data = request.get_json(force=True) or {}
    code = data.get("code", "")
    language = data.get("language", "python").lower()

    if language not in ("python", "javascript"):
        return jsonify({"error": "language must be 'python' or 'javascript'"}), 400

    if not code.strip():
        return jsonify({"error": "code is required"}), 400

    result = analyze_code(
        code=code,
        language=language,
        openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
        provider=os.getenv("AI_PROVIDER", "mock").strip().lower()
    )

    return jsonify(result)

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.getenv("PORT", "8000")), debug=True)
