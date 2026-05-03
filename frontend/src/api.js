const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || "http://127.0.0.1:8000";

export async function analyzeCode({ code, language }) {
  const res = await fetch(`${BACKEND_URL}/api/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ code, language })
  });

  const data = await res.json();
  if (!res.ok) {
    throw new Error(data?.error || "Request failed");
  }
  return data;
}
