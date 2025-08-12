import os
import re
import httpx

# Valide une URL ngrok du type https://<id>.ngrok-free.app
URL_RE = re.compile(r"^https://[a-z0-9-]+\.ngrok-free\.app$", re.I)

def get_ollama_base() -> str:
    raw = (os.getenv("OLLAMA_BASE_URL") or "").strip()
    raw = raw.strip("'").strip('"').rstrip("/")
    if not raw or "/api" in raw:
        raise ValueError("OLLAMA_BASE_URL manquant ou invalide (ne pas inclure /api)")
    if "ngrok-free.app" in raw and not URL_RE.match(raw):
        raise ValueError(f"OLLAMA_BASE_URL non valide: {raw}")
    return raw

def http_client() -> httpx.AsyncClient:
    transport = httpx.AsyncHTTPTransport(retries=2)
    return httpx.AsyncClient(
        http2=False,
        transport=transport,
        timeout=10.0,
        headers={"Connection": "keep-alive"},
    )
