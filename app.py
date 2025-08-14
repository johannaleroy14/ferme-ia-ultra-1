import os
import httpx
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def root():
    return {"ok": True, "app": "alive"}

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/diag")
async def diag():
    base = (os.getenv("OLLAMA_BASE_URL") or "").strip().rstrip("/")
    if not base:
        return {"ok": False, "err": "missing OLLAMA_BASE_URL"}
    url = f"{base}/api/tags"
    try:
        async with httpx.AsyncClient(timeout=8.0, http2=False, headers={"ngrok-skip-browser-warning":"true"}) as c:
            r = await c.get(url)
            raw = await r.aread()
        snippet = raw[:200].decode("utf-8","ignore") if isinstance(raw, (bytes, bytearray)) else str(raw)[:200]
        return {"ok": True, "status": r.status_code, "snippet": snippet}
    except Exception as e:
        return {"ok": False, "err": repr(e), "url": url}

# --- DEBUG: voir l'ENV sur Render ---
import os
@app.get("/env")
def show_env():
    return {"OLLAMA_BASE_URL": (os.getenv("OLLAMA_BASE_URL") or "").strip()}
