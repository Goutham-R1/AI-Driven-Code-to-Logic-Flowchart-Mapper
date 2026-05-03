import ast as _ast
import json
import re
import requests

# ---------------------------------------------------------------------------
# System prompt used by AI providers
# ---------------------------------------------------------------------------

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

# ---------------------------------------------------------------------------
# AST-based Python flowchart builder
# ---------------------------------------------------------------------------

def _unparse(node) -> str:
    """Safely convert an AST node back to source text."""
    try:
        return _ast.unparse(node)
    except (AttributeError, TypeError, ValueError):
        # AttributeError: ast.unparse missing (Python < 3.9, shouldn't happen with 3.12+)
        # TypeError/ValueError: unexpected node type or unparseable construct
        return type(node).__name__


def _esc(text: str) -> str:
    """Escape characters that would break Mermaid node label syntax."""
    return (
        str(text)
        .replace('"', "'")
        .replace("{", "(")
        .replace("}", ")")
        .replace("[", "(")
        .replace("]", ")")
        .replace("\n", " ")
        .strip()
    )


class _MermaidBuilder:
    """Walk a Python AST and produce a Mermaid TD flowchart + nodeMap."""

    # Stable IDs for the fixed Start/End terminal nodes
    _START = "S"
    _END = "FLOW_END"

    def __init__(self):
        self._node_defs = []
        self._edge_defs = []
        self.node_map = {}
        self._counter = 0

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _new_id(self, prefix="N"):
        self._counter += 1
        return f"{prefix}{self._counter}"

    def _def_node(self, nid, label, shape="rect"):
        label = _esc(label)
        if shape == "diamond":
            self._node_defs.append(f'{nid}{{"{label}"}}')
        elif shape == "stadium":
            self._node_defs.append(f'{nid}(["{label}"])')
        elif shape == "subroutine":
            self._node_defs.append(f'{nid}[["{label}"]]')
        else:
            self._node_defs.append(f'{nid}["{label}"]')

    def _edge(self, src, dst, style="solid", label=""):
        if style == "dotted":
            if label:
                self._edge_defs.append(f"{src} -. {label} .-> {dst}")
            else:
                self._edge_defs.append(f"{src} -.-> {dst}")
        else:
            if label:
                self._edge_defs.append(f"{src} -->|{label}| {dst}")
            else:
                self._edge_defs.append(f"{src} --> {dst}")

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def build(self, code: str):
        """Return (mermaid_str, node_map) or (None, None) on parse error."""
        try:
            tree = _ast.parse(code)
        except SyntaxError:
            return None, None

        first_id, final_exits = self._body(tree.body)

        # Connect top-level exits to End
        for exit_id, exit_type in final_exits:
            self._edge(exit_id, self._END, "dotted" if exit_type == "return" else "solid")

        end_id = self._END
        start_id = self._START
        parts = ["graph TD"]
        parts.append(f'{start_id}(["Start"])')
        parts.append(f'{end_id}(["End"])')
        parts.append(f"{start_id} --> {first_id}" if first_id else f"{start_id} --> {end_id}")
        parts.extend(self._node_defs)
        parts.extend(self._edge_defs)
        return "\n".join(parts), self.node_map

    # ------------------------------------------------------------------
    # Statement list processing
    # ------------------------------------------------------------------

    def _body(self, stmts):
        """Process a statement list. Returns (first_id, exits_list)."""
        if not stmts:
            return None, []

        first_id = None
        pending_normals = []   # ids of normal-exit nodes awaiting a successor
        accumulated = []       # return/break exits that cannot continue

        for stmt in stmts:
            eid, exits = self._stmt(stmt)
            if eid is None:
                continue

            if first_id is None:
                first_id = eid

            for prev_id in pending_normals:
                self._edge(prev_id, eid)

            pending_normals = []
            for (xid, xtype) in exits:
                if xtype == "normal":
                    pending_normals.append(xid)
                else:
                    accumulated.append((xid, xtype))

        final = [(nid, "normal") for nid in pending_normals] + accumulated
        return first_id, final

    # ------------------------------------------------------------------
    # Statement dispatch
    # ------------------------------------------------------------------

    def _stmt(self, stmt):
        if isinstance(stmt, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
            return self._funcdef(stmt)
        if isinstance(stmt, _ast.If):
            return self._if(stmt)
        if isinstance(stmt, _ast.For):
            return self._for(stmt)
        if isinstance(stmt, _ast.While):
            return self._while(stmt)
        if isinstance(stmt, _ast.Return):
            return self._return(stmt)
        if isinstance(stmt, _ast.Try):
            return self._try(stmt)
        return self._generic(stmt)

    # ------------------------------------------------------------------
    # Individual statement handlers
    # ------------------------------------------------------------------

    def _funcdef(self, stmt):
        args = [a.arg for a in stmt.args.args]
        label = f"def {stmt.name}({', '.join(args)})"
        nid = self._new_id("F")
        self._def_node(nid, label[:50], "subroutine")
        self.node_map[nid] = {"startLine": stmt.lineno, "endLine": stmt.lineno}

        body_first, body_exits = self._body(stmt.body)
        if body_first:
            self._edge(nid, body_first)

        # Connect all body exits to End (return exits use dotted arrows)
        for exit_id, exit_type in body_exits:
            self._edge(exit_id, self._END, "dotted" if exit_type == "return" else "solid")

        # The function *definition* itself is just one step in the outer flow
        return nid, [(nid, "normal")]

    def _if(self, stmt):
        cond = _unparse(stmt.test)
        cond_short = cond[:35] + ("..." if len(cond) > 35 else "")
        nid = self._new_id("D")
        self._def_node(nid, cond_short, "diamond")
        self.node_map[nid] = {"startLine": stmt.lineno, "endLine": stmt.lineno}

        all_exits = []

        # True / "if" branch
        true_first, true_exits = self._body(stmt.body)
        if true_first:
            self._edge(nid, true_first, "solid", "Yes")
        else:
            all_exits.append((nid, "normal"))
        all_exits.extend(true_exits)

        # False / elif / else branch
        if stmt.orelse:
            false_first, false_exits = self._body(stmt.orelse)
            if false_first:
                self._edge(nid, false_first, "solid", "No")
            else:
                all_exits.append((nid, "normal"))
            all_exits.extend(false_exits)
        else:
            all_exits.append((nid, "normal"))

        return nid, all_exits

    def _for(self, stmt):
        try:
            label = f"for {_unparse(stmt.target)} in {_unparse(stmt.iter)}"
        except Exception:
            label = "for loop"
        label_short = label[:35] + ("..." if len(label) > 35 else "")
        nid = self._new_id("L")
        self._def_node(nid, label_short, "diamond")
        self.node_map[nid] = {
            "startLine": stmt.lineno,
            "endLine": getattr(stmt, "end_lineno", stmt.lineno),
        }

        body_first, body_exits = self._body(stmt.body)
        if body_first:
            self._edge(nid, body_first, "solid", "each item")

        # Normal body exits loop back to the loop condition node;
        # non-normal exits (return/break) propagate out of the loop.
        non_normal = []
        for exit_id, exit_type in body_exits:
            if exit_type == "normal":
                self._edge(exit_id, nid)
            else:
                non_normal.append((exit_id, exit_type))

        return nid, [(nid, "normal")] + non_normal

    def _while(self, stmt):
        try:
            cond = _unparse(stmt.test)
        except Exception:
            cond = "condition"
        label = f"while {cond}"
        label_short = label[:35] + ("..." if len(label) > 35 else "")
        nid = self._new_id("W")
        self._def_node(nid, label_short, "diamond")
        self.node_map[nid] = {
            "startLine": stmt.lineno,
            "endLine": getattr(stmt, "end_lineno", stmt.lineno),
        }

        body_first, body_exits = self._body(stmt.body)
        if body_first:
            self._edge(nid, body_first, "solid", "True")

        # Normal body exits loop back to the while condition;
        # non-normal exits (return/break) propagate out of the loop.
        non_normal = []
        for exit_id, exit_type in body_exits:
            if exit_type == "normal":
                self._edge(exit_id, nid)
            else:
                non_normal.append((exit_id, exit_type))

        return nid, [(nid, "normal")] + non_normal

    def _return(self, stmt):
        try:
            val = _unparse(stmt.value) if stmt.value else ""
        except Exception:
            val = ""
        label = f"return {val}" if val else "return"
        label_short = label[:35] + ("..." if len(label) > 35 else "")
        nid = self._new_id("R")
        self._def_node(nid, label_short, "rect")
        self.node_map[nid] = {"startLine": stmt.lineno, "endLine": stmt.lineno}
        return nid, [(nid, "return")]

    def _try(self, stmt):
        nid = self._new_id("T")
        self._def_node(nid, "try block", "rect")
        self.node_map[nid] = {"startLine": stmt.lineno, "endLine": stmt.lineno}

        body_first, body_exits = self._body(stmt.body)
        if body_first:
            self._edge(nid, body_first)

        all_exits = list(body_exits)

        for handler in stmt.handlers:
            exc_type = ""
            if handler.type:
                try:
                    exc_type = _unparse(handler.type)
                except Exception:
                    exc_type = "Exception"
            h_nid = self._new_id("H")
            h_label = f"except {exc_type}" if exc_type else "except"
            self._def_node(h_nid, h_label, "rect")
            self.node_map[h_nid] = {"startLine": handler.lineno, "endLine": handler.lineno}
            self._edge(nid, h_nid, "dotted", "Error")

            h_first, h_exits = self._body(handler.body)
            if h_first:
                self._edge(h_nid, h_first)
            all_exits.extend(h_exits)

        return nid, all_exits

    def _generic(self, stmt):
        try:
            label = _unparse(stmt)
        except Exception:
            label = type(stmt).__name__
        label_short = label[:40] + ("..." if len(label) > 40 else "")
        nid = self._new_id("N")
        self._def_node(nid, label_short, "rect")
        lineno = getattr(stmt, "lineno", 1)
        end_lineno = getattr(stmt, "end_lineno", lineno)
        self.node_map[nid] = {"startLine": lineno, "endLine": end_lineno}
        return nid, [(nid, "normal")]


def _build_explanation(code: str) -> str:
    """Produce a short human-readable description from the Python AST."""
    try:
        tree = _ast.parse(code)
    except SyntaxError:
        return "Could not parse code (syntax error)."

    findings = []
    for node in _ast.walk(tree):
        if isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
            args = [a.arg for a in node.args.args]
            findings.append(f"defines function '{node.name}({', '.join(args)})'")
        elif isinstance(node, _ast.If):
            try:
                cond = _unparse(node.test)
                findings.append(f"has conditional: if {cond[:30]}")
            except Exception:
                findings.append("has a conditional branch")
        elif isinstance(node, _ast.For):
            try:
                findings.append(
                    f"iterates: for {_unparse(node.target)} in {_unparse(node.iter)[:20]}"
                )
            except Exception:
                findings.append("has a for-loop")
        elif isinstance(node, _ast.While):
            try:
                findings.append(f"loops while: {_unparse(node.test)[:30]}")
            except Exception:
                findings.append("has a while-loop")

    if not findings:
        return "This snippet executes a linear sequence of statements."

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for f in findings:
        if f not in seen:
            seen.add(f)
            unique.append(f)

    return "This code " + "; ".join(unique[:6]) + "."


# ---------------------------------------------------------------------------
# Mock / fallback analyzer
# ---------------------------------------------------------------------------

def _mock_analyze(code: str, language: str) -> dict:
    if language == "python":
        builder = _MermaidBuilder()
        mermaid, node_map = builder.build(code)
        if mermaid is not None and node_map is not None:
            explanation = _build_explanation(code) + " (AST analysis – mock mode)"
            return {"explanation": explanation, "mermaid": mermaid, "nodeMap": node_map}

    # Fallback for non-Python code or AST parse failure
    lines = code.splitlines()
    end_line = max(1, len(lines))
    mermaid = "\n".join([
        "graph TD",
        'S(["Start"]) --> N1["Parse input code"]',
        f'N1 --> N2["Execute {language} logic"]',
        'N2 --> E(["End"])',
    ])
    return {
        "explanation": (
            f"This {language} snippet runs through a sequence of operations. (Mock mode)"
        ),
        "mermaid": mermaid,
        "nodeMap": {"N2": {"startLine": 1, "endLine": end_line}},
    }


# ---------------------------------------------------------------------------
# JSON extraction helper
# ---------------------------------------------------------------------------

def _extract_json(text: str):
    try:
        return json.loads(text)
    except Exception:
        pass

    m = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not m:
        raise ValueError("No JSON object found in AI output.")
    return json.loads(m.group(0))


# ---------------------------------------------------------------------------
# OpenAI provider  (fixed endpoint + payload)
# ---------------------------------------------------------------------------

_OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"


def _openai_analyze(code: str, language: str, api_key: str):
    model = "gpt-4o-mini"
    url = _OPENAI_CHAT_URL

    user_prompt = (
        f"Analyze the following {language} code.\n"
        "1) Produce a short human-readable explanation.\n"
        '2) Produce a Mermaid flowchart ("graph TD") with Start/End, decisions, loops, '
        "and function calls where relevant.\n"
        '3) Provide a node-to-line mapping ("nodeMap") for clickable highlighting.\n\n'
        f"Code:\n{code}"
    )

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_RULES},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    r = requests.post(url, headers=headers, json=payload, timeout=60)
    r.raise_for_status()
    data = r.json()

    text = data["choices"][0]["message"]["content"].strip()

    obj = _extract_json(text)

    if "mermaid" not in obj or "explanation" not in obj or "nodeMap" not in obj:
        raise ValueError("AI JSON missing required keys.")
    if not str(obj["mermaid"]).lstrip().startswith("graph TD"):
        raise ValueError("Mermaid must start with 'graph TD'.")

    return obj


# ---------------------------------------------------------------------------
# Gemini provider  (unchanged logic, kept working)
# ---------------------------------------------------------------------------

def _gemini_analyze(code: str, language: str, api_key: str):
    model = "gemini-2.0-flash"
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={api_key}"
    )

    user_prompt = (
        f"{SYSTEM_RULES}\n\n"
        f"Analyze the following {language} code.\n"
        "1) Produce a short human-readable explanation.\n"
        '2) Produce a Mermaid flowchart ("graph TD") with Start/End, decisions, loops, '
        "and function calls where relevant.\n"
        '3) Provide a node-to-line mapping ("nodeMap") for clickable highlighting.\n\n'
        f"Code:\n{code}"
    )

    payload = {
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generationConfig": {"temperature": 0.2},
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


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyze_code(
    code: str,
    language: str,
    openai_api_key: str = "",
    gemini_api_key: str = "",
    provider: str = "mock",
) -> dict:
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
