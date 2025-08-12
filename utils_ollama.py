import os, re, sys
import httpx

URL_RE = re.compile(r"^https://[a-z0-9-]+\.ngrok-free\.app$", re.I)

def get_ollama_base() -> str:
    raw = (os.getenv("OLLAMA_BASE_URL") or "").strip().strip("'\"").rstrip("/")
    if not raw or "/api" in raw:
        raise ValueError("OLLAMA_BASE_URL manquant ou invalide (ne pas inclure /api)")
    if "ngrok-free.app" in raw and not URL_RE.match(raw):
        raise ValueError(f"OLLAMA_BASE_URL non valide: {raw}")
    return raw

def http_client(timeout: float = 10.0) -> httpx.AsyncClient:
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

try:
    base = get_ollama_base()
    print(f"[boot] OLLAMA_BASE_URL={base}", file=sys.stderr)
except Exception as e:
    print(f"[boot] OLLAMA_BASE_URL invalid: {e}", file=sys.stderr)
import os, re, sys
import httpx

URL_RE = re.compile(r"^https://[a-z0-9-]+\.ngrok-free\.app$", re.I)

def get_ollama_base() -> str:
    raw = (os.getenv("OLLAMA_BASE_URL") or "").strip().strip("'\"").rstrip("/")
    if not raw or "/api" in raw:
        raise ValueError("OLLAMA_BASE_URL manquant ou invalide (ne pas inclure /api)")
    if "ngrok-free.app" in raw and not URL_RE.match(raw):
        raise ValueError(f"OLLAMA_BASE_URL non valide: {raw}")
    return raw

def http_client(timeout: float = 10.0) -> httpx.AsyncClient:
    # HTTP/1.1 + retries + header anti-403 ngrok
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

# Log early au démarrage (utile sur Render)
try:
    base = get_ollama_base()
    print(f"[boot] OLLAMA_BASE_URL={base}", file=sys.stderr)
except Exception as e:
    print(f"[boot] OLLAMA_BASE_URL invalid: {e}", file=sys.stderr)
import os, re
import httpx

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
    # HTTP/1.1 + retries + header anti-403 ngrok
    transport = httpx.AsyncHTTPTransport(retries=2)
    return httpx.AsyncClient(
        http2=False,
        transport=transport,
        timeout=15.0,
        headers={
            "Connection": "keep-alive",
            "ngrok-skip-browser-warning": "true",
            "Accept": "application/json",
        },
    )
