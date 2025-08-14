import os, json
from fastapi import FastAPI, Request
import httpx

app = FastAPI()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN","").strip().strip("'\"")
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
MODEL = os.getenv("OLLAMA_MODEL","llama3.2:3b")
MAX_TG = 3900

def http_client(timeout: float = 12.0) -> httpx.AsyncClient:
    transport = httpx.AsyncHTTPTransport(retries=1)
    return httpx.AsyncClient(http2=False, transport=transport, timeout=timeout, headers={
        "Connection": "keep-alive",
        "ngrok-skip-browser-warning": "true",
        "Accept": "application/json",
    })

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/env")
def show_env():
    return {"OLLAMA_BASE_URL": (os.getenv("OLLAMA_BASE_URL") or "").strip()}

@app.get("/diag")
async def diag():
    base = (os.getenv("OLLAMA_BASE_URL") or "").strip().rstrip("/")
    if not base:
        return {"ok": False, "err": "missing OLLAMA_BASE_URL"}
    url = f"{base}/api/tags"
    try:
        async with http_client(timeout=8.0) as c:
            r = await c.get(url)
            raw = await r.aread()
        snippet = raw[:200].decode("utf-8","ignore") if isinstance(raw,(bytes,bytearray)) else str(raw)[:200]
        return {"ok": True, "status": r.status_code, "snippet": snippet}
    except Exception as e:
        return {"ok": False, "err": repr(e), "url": url}

async def chat_ollama(user_text: str) -> tuple[str, dict]:
    meta = {"status": None, "error": None, "snippet": None}
    base = (os.getenv("OLLAMA_BASE_URL") or "").strip().rstrip("/")
    url = f"{base}/api/chat"
    payload = {"model": MODEL, "messages": [{"role":"user","content":user_text}], "stream": False}
    print(f"[chat_ollama] POST {url}")
    try:
        async with http_client(timeout=12.0) as c:
            r = await c.post(url, json=payload)
            meta["status"] = r.status_code
            raw = await r.aread()
            meta["snippet"] = (raw[:500] if isinstance(raw,(bytes,bytearray)) else str(raw)[:500])
            print(f"[chat_ollama] status={r.status_code}")
            print(f"[chat_ollama] body_snippet={meta['snippet']!r}")
            r.raise_for_status()
            data = json.loads(raw.decode("utf-8") if isinstance(raw,(bytes,bytearray)) else raw)
        reply = (data.get("message",{}).get("content") or data.get("response") or "").strip()
        if not reply:
            reply = "Désolé, je n’ai pas pu générer de réponse."
        return reply, meta
    except Exception as e:
        meta["error"] = repr(e)
        print(f"[chat_ollama] ERROR: {meta['error']}")
        return "Petit souci côté IA, réessaie dans une minute.", meta

async def send_telegram(chat_id: int, text: str) -> None:
    if len(text) > MAX_TG:
        text = text[:MAX_TG] + "\n\n…(réponse tronquée)"
    if not TELEGRAM_TOKEN:
        print("[telegram] SKIP: TELEGRAM_TOKEN manquant")
        return
    send_url = f"{TELEGRAM_API}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    try:
        async with http_client(timeout=10.0) as c:
            tr = await c.post(send_url, json=payload)
            st = tr.status_code
            tb = await tr.aread()
            print(f"[telegram] sendMessage status={st} body={tb[:300]!r}")
    except Exception as e:
        print(f"[telegram] ERROR sendMessage: {repr(e)}")

@app.post("/telegram/lyra123")
async def telegram_webhook(req: Request):
    upd = await req.json()
    msg = upd.get("message") or upd.get("edited_message") or {}
    chat = msg.get("chat") or {}
    chat_id = chat.get("id")
    text = msg.get("text") or ""
    print(f"[webhook] chat_id={chat_id} text={text!r}")

    if not chat_id:
        return {"ok": True, "note": "Pas de chat_id"}
    if not text:
        text = "bonjour"

    reply_text, meta = await chat_ollama(text)
    if meta.get("error"):
        reply_text = reply_text + "\n\n(_diag: ollama error – voir logs_)"

    await send_telegram(chat_id, reply_text)
    return {"ok": True}
