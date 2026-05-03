# AI-Driven Code-to-Logic Flowchart Mapper

A local web app that converts pasted **Python/JavaScript** code into:
- a short human explanation (“What this code does”)
- a **Mermaid.js** flowchart (`graph TD`)
- (extra) clickable flowchart nodes that highlight related code lines

## Architecture
- Frontend: React (Vite) + Mermaid.js
- Backend: Python Flask API
- AI: OpenAI (optional) or Mock mode

---

## 1) Setup (Backend)

```bash
cd backend
python -m venv .venv

# Windows PowerShell:
. .venv\Scripts\Activate.ps1
# macOS/Linux:
# source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
```

### Run backend
```bash
python app.py
```

Backend runs on: http://127.0.0.1:8000  
Health check: http://127.0.0.1:8000/health

### Enable OpenAI (optional)
Edit `backend/.env`:
- `AI_PROVIDER=openai`
- `OPENAI_API_KEY=...`

If you leave it as `mock`, everything still works (but flowcharts are basic).

---

## 2) Setup (Frontend)

```bash
cd frontend
npm install
npm run dev
```

Frontend runs on: http://127.0.0.1:5173

If your backend is on a different URL, set:
```bash
# macOS/Linux
export VITE_BACKEND_URL=http://127.0.0.1:8000
# Windows PowerShell
setx VITE_BACKEND_URL "http://127.0.0.1:8000"
```

---

## 3) Demo Walkthrough

1. Start backend (`python app.py`)
2. Start frontend (`npm run dev`)
3. Paste `demo_samples/python_sample.py`
4. Select language = Python
5. Click **Generate Flowchart**
6. Click nodes in the flowchart to highlight mapped code lines (best-effort)

---

## Notes / Constraints
- This is a prototype. Node-to-line mapping depends on the AI output quality.
- Mermaid click behavior is enabled via `securityLevel: "loose"` for simplicity in local runs.
