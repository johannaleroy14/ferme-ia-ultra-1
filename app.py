import os, json, httpx
from fastapi import FastAPI, Request
from utils_ollama import get_ollama_base, http_client

app = FastAPI()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip().strip("'\"")
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
MAX_TG = 3900

@app.get("/health")
async def health():
    return {"ok": True}

async def chat_ollama(user_text: str) -> tuple[str, dict]:
    meta = {"status": None, "error": None, "snippet": None}
    base = get_ollama_base()
    url = f"{base}/api/chat"
    payload = {"model": MODEL, "messages": [{"role": "user", "content": user_text}], "stream": False}
    print(f"[chat_ollama] POST {url}")
    try:
        async with http_client(timeout=12.0) as c:
            r = await c.post(url, json=payload, headers={"ngrok-skip-browser-warning": "true"})
            meta["status"] = r.status_code
            raw = await r.aread()
            meta["snippet"] = (raw[:500] if isinstance(raw, (bytes, bytearray)) else str(raw)[:500])
            print(f"[chat_ollama] status={r.status_code}")
            print(f"[chat_ollama] body_snippet={meta['snippet']!r}")
            r.raise_for_status()
            data = json.loads(raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else raw)
        reply = (data.get("message", {}).get("content") or data.get("response") or "").strip()
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

# --- DIAGNOSTIC: ping public base depuis Render ---
@app.get("/diag")
async def diag():
    try:
        base = get_ollama_base()
    except Exception as e:
        return {"ok": False, "err": f"env: {repr(e)}"}
    url = f"{base}/api/tags"
    try:
        async with http_client(timeout=6.0) as c:
            r = await c.get(url, headers={"ngrok-skip-browser-warning": "true"})
            raw = await r.aread()
            snippet = raw[:200].decode("utf-8", "ignore") if isinstance(raw, (bytes, bytearray)) else str(raw)[:200]
            return {"ok": True, "status": r.status_code, "snippet": snippet}
    except Exception as e:
        return {"ok": False, "err": repr(e), "url": url}
import os, json, asyncio, httpx
from fastapi import FastAPI, Request
from utils_ollama import get_ollama_base, http_client

app = FastAPI()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip().strip("'\"")
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
MAX_TG = 3900

@app.get("/health")
async def health():
    return {"ok": True}

async def chat_ollama(user_text: str) -> tuple[str, dict]:
    meta = {"status": None, "error": None, "snippet": None}
    base = get_ollama_base()
    url = f"{base}/api/chat"
    payload = {"model": MODEL, "messages": [{"role": "user", "content": user_text}], "stream": False}
    print(f"[chat_ollama] POST {url}")
    try:
        async with http_client(timeout=12.0) as c:
            r = await c.post(url, json=payload, headers={"ngrok-skip-browser-warning": "true"})
            meta["status"] = r.status_code
            raw = await r.aread()
            meta["snippet"] = (raw[:500] if isinstance(raw, (bytes, bytearray)) else str(raw)[:500])
            print(f"[chat_ollama] status={r.status_code}")
            print(f"[chat_ollama] body_snippet={meta['snippet']!r}")
            r.raise_for_status()
            data = json.loads(raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else raw)
        reply = (data.get("message", {}).get("content") or data.get("response") or "").strip()
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

@app.get("/diag")
async def diag():
    try:
        base = get_ollama_base()
    except Exception as e:
        return {"ok": False, "err": f"env: {repr(e)}"}
    url = f"{base}/api/tags"
    try:
        async with http_client(timeout=6.0) as c:
            r = await c.get(url, headers={"ngrok-skip-browser-warning": "true"})
            raw = await r.aread()
            return {
                "ok": True,
                "status": r.status_code,
                "len": len(raw) if isinstance(raw, (bytes, bytearray)) else None,
                "snippet": (raw[:200].decode("utf-8", "ignore") if isinstance(raw, (bytes, bytearray)) else str(raw)[:200]),
            }
    except Exception as e:
        return {"ok": False, "err": repr(e), "url": url}
import os
import httpx
from fastapi import FastAPI, HTTPException, Request
from utils_ollama import get_ollama_base, http_client

app = FastAPI()

@app.get("/health")
async def health():
    # Vérifie vraiment l’accès à Ollama
    base = get_ollama_base()
    async with http_client() as c:
        r = await c.get(f"{base}/api/tags")
        r.raise_for_status()
    return {"status": "ok"}

async def chat_ollama(user_text: str) -> str:
    base = get_ollama_base()
    url = f"{base}/api/chat"
    payload = {
        "model": os.getenv("OLLAMA_MODEL", "llama3.2:3b"),
        "messages": [{"role": "user", "content": user_text}],
        "stream": False,
    }
    print(f"[chat_ollama] POST {url}")
    async with http_client() as c:
        try:
            r = await c.post(url, json=payload)
            r.raise_for_status()
            data = r.json()
            # compat /generate vs /chat
            return ((data.get("message") or {}).get("content")
                    or data.get("response")
                    or "(Réponse vide d’Ollama)")
        except httpx.RequestError as e:
            print(f"[chat_ollama] RequestError: {e}")
            raise HTTPException(503, f"Connexion Ollama échouée: {e}") from e
        except httpx.HTTPStatusError as e:
            print(f"[chat_ollama] HTTP {e.response.status_code}: {e.response.text}")
            raise HTTPException(e.response.status_code, f"Ollama HTTP {e.response.status_code}: {e.response.text}") from e

# Webhook Telegram (secret: /telegram/lyra123)
@app.post("/telegram/lyra123")
async def telegram_webhook(req: Request):
    body = await req.json()
    text = (body.get("message", {}).get("text") or "").strip() or "bonjour"
    try:
        reply = await chat_ollama(text)
    except HTTPException as e:
        reply = f"(Service temporairement indisponible: {e.detail})"
    except Exception as e:
        reply = f"(Erreur inattendue: {e})"

    token = os.environ.get("TELEGRAM_TOKEN", "")
    chat_id = body.get("message", {}).get("chat", {}).get("id")
    if token and chat_id:
        async with http_client() as c:
            await c.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": reply},
            )
    return {"ok": True}
