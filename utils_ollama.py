import os, re
import httpx

URL_RE = re.compile(r"^https://[a-z0-9-]+\.(ngrok-free\.app|trycloudflare\.com|loca\.lt)$", re.I)

def get_ollama_base() -> str:
    raw = (os.getenv("OLLAMA_BASE_URL") or "").strip().strip("'\"").rstrip("/")
    if not raw or "/api" in raw:
        raise ValueError("OLLAMA_BASE_URL manquant ou invalide (ne pas inclure /api)")
    if any(k in raw for k in ("ngrok-free.app","trycloudflare.com","loca.lt")) and not URL_RE.match(raw):
        raise ValueError(f"OLLAMA_BASE_URL non valide: {raw}")
    return raw

def http_client(timeout: float = 12.0) -> httpx.AsyncClient:
    transport = httpx.AsyncHTTPTransport(retries=1)
    return httpx.AsyncClient(
        http2=False,
        transport=transport,
        timeout=timeout,
        headers={
            "Connection": "keep-alive",
            "ngrok-skip-browser-warning": "true",
            "Accept": "application/json",
        },
    )
