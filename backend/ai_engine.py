import json
import re
import requests

SYSTEM_RULES = """
You are a code analysis assistant.
Return strictly valid JSON with keys:
- "explanation": string (human-readable summary)
- "mermaid": string (Mermaid flowchart syntax)
- "nodeMap": object mapping nodeId -> { "startLine": int, "endLine": int }

Mermaid rules:
- Must start with: graph TD
- Include Start and End nodes
- Use solid arrows for main flow: -->
- Use dotted arrows for return/break/error paths: -.->

Keep node IDs stable and simple (e.g., N1, N2...).
No markdown fences. No extra keys. No commentary.
"""

def _mock_analyze(code: str, language: str):
    lines = code.splitlines()
    end_line = max(1, len(lines))

    mermaid = "\n".join([
        "graph TD",
        'S([Start]) --> N1["Parse input code"]',
        f'N1 --> N2["Execute {language} logic"]',
        'N2 --> E([End])'
    ])

    return {
        "explanation": f"This {language} snippet is analyzed and represented as a simplified execution flow. (Mock mode)",
        "mermaid": mermaid,
        "nodeMap": {
            "N2": {"startLine": 1, "endLine": end_line}
        }
    }

def _extract_json(text: str):
    try:
        return json.loads(text)
    except Exception:
        pass

    m = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not m:
        raise ValueError("No JSON object found in AI output.")
    return json.loads(m.group(0))

def _openai_analyze(code: str, language: str, api_key: str):
    model = "gpt-4o-mini"
    url = "https://api.openai.com/v1/responses"

    user_prompt = f"""
Analyze the following {language} code.
1) Produce a short human-readable explanation.
2) Produce a Mermaid flowchart (\"graph TD\") with Start/End, decisions, loops, and function calls where relevant.
3) Provide a node-to-line mapping (\"nodeMap\") for clickable highlighting.

Code:
{code}
""".strip()

    payload = {
        "model": model,
        "input": [
            {"role": "system", "content": SYSTEM_RULES},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.2
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    r = requests.post(url, headers=headers, json=payload, timeout=60)
    r.raise_for_status()
    data = r.json()

    text_chunks = []
    for item in data.get("output", []):
        for c in item.get("content", []):
            if c.get("type") == "output_text":
                text_chunks.append(c.get("text", ""))
    text = "\n".join(text_chunks).strip()

    obj = _extract_json(text)

    if "mermaid" not in obj or "explanation" not in obj or "nodeMap" not in obj:
        raise ValueError("AI JSON missing required keys.")
    if not str(obj["mermaid"]).lstrip().startswith("graph TD"):
        raise ValueError("Mermaid must start with 'graph TD'.")

    return obj

def _gemini_analyze(code: str, language: str, api_key: str):
    model = "gemini-2.0-flash"
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={api_key}"
    )

    user_prompt = f"""
{SYSTEM_RULES}

Analyze the following {language} code.
1) Produce a short human-readable explanation.
2) Produce a Mermaid flowchart (\"graph TD\") with Start/End, decisions, loops, and function calls where relevant.
3) Provide a node-to-line mapping (\"nodeMap\") for clickable highlighting.

Code:
{code}
""".strip()

    payload = {
        "contents": [
            {"role": "user", "parts": [{"text": user_prompt}]}
        ],
        "generationConfig": {"temperature": 0.2}
    }

    headers = {"Content-Type": "application/json"}

    r = requests.post(url, headers=headers, json=payload, timeout=60)
    r.raise_for_status()
    data = r.json()

    text = ""
    for candidate in data.get("candidates", []):
        for part in candidate.get("content", {}).get("parts", []):
            text += part.get("text", "")
    text = text.strip()

    obj = _extract_json(text)

    if "mermaid" not in obj or "explanation" not in obj or "nodeMap" not in obj:
        raise ValueError("AI JSON missing required keys.")
    if not str(obj["mermaid"]).lstrip().startswith("graph TD"):
        raise ValueError("Mermaid must start with 'graph TD'.")

    return obj


def analyze_code(code: str, language: str, openai_api_key: str = "", gemini_api_key: str = "", provider: str = "mock"):
    if provider == "openai":
        if not openai_api_key:
            return _mock_analyze(code, language)
        try:
            return _openai_analyze(code, language, openai_api_key)
        except Exception:
            return _mock_analyze(code, language)

    if provider == "gemini":
        if not gemini_api_key:
            return _mock_analyze(code, language)
        try:
            return _gemini_analyze(code, language, gemini_api_key)
        except Exception:
            return _mock_analyze(code, language)

    return _mock_analyze(code, language)
