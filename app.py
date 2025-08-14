import os, json
import httpx
from fastapi import FastAPI, Request
from utils_ollama import get_ollama_base, http_client

app = FastAPI()

# Token Telegram (Render peut fournir TELEGRAM_BOT_TOKEN ou TELEGRAM_TOKEN)
TELEGRAM_TOKEN = (os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN") or "").strip()
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}" if TELEGRAM_TOKEN else ""
MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")

# Override dynamique (via /set_ollama)
BASE_OVERRIDE = None

def current_base() -> str | None:
    global BASE_OVERRIDE
    if BASE_OVERRIDE:
        return BASE_OVERRIDE
    try:
        return get_ollama_base()
    except Exception:
        return None

async def chat_ollama(user_text: str) -> str:
    base = current_base()
    if not base:
        return "⚠️ OLLAMA_BASE_URL non configurée. Envoie /set_ollama https://…trycloudflare.com"

    url = f"{base}/api/chat"
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": user_text}],
        "stream": False,
    }
    async with http_client() as c:
        print(f"[chat_ollama] POST {url} (model={MODEL})")
        try:
            r = await c.post(url, json=payload, headers={"ngrok-skip-browser-warning": "true"})
            print(f"[chat_ollama] status={r.status_code}")
            body = await r.aread()
            print(f"[chat_ollama] body_snippet={body[:180]!r}")
            r.raise_for_status()
            data = json.loads(body.decode("utf-8"))
        except Exception as e:
            print("[chat_ollama] ERROR:", repr(e))
            return "Petit souci côté IA, réessaie dans une minute."

    reply = (
        data.get("message", {}).get("content")
        or data.get("response")
        or ""
    )
    return reply.strip() or "Désolé, je n’ai pas pu générer de réponse."

@app.get("/")
def root():
    return {"ok": True, "app": "ferme-ia-ultra-web"}

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/env")
def env():
    src = "TELEGRAM_BOT_TOKEN" if os.getenv("TELEGRAM_BOT_TOKEN") else ("TELEGRAM_TOKEN" if os.getenv("TELEGRAM_TOKEN") else None)
    return {
        "OLLAMA_BASE_URL_env": (os.getenv("OLLAMA_BASE_URL") or "").strip(),
        "BASE_used_now": current_base(),
        "TELEGRAM_TOKEN_set": bool(TELEGRAM_TOKEN),
        "TELEGRAM_TOKEN_source": src,
    }

@app.get("/diag")
async def diag():
    base = current_base()
    if not base:
        return {"ok": False, "err": "missing OLLAMA_BASE_URL"}
    test_url = f"{base}/api/tags"
    try:
        async with http_client() as c:
            r = await c.get(test_url, headers={"ngrok-skip-browser-warning": "true"})
            body = await r.aread()
            return {"ok": True, "status": r.status_code, "snippet": body.decode("utf-8")[:120], "url": test_url}
    except Exception as e:
        return {"ok": False, "err": repr(e), "url": test_url}

# Webhook Telegram
@app.post("/telegram/lyra123")
async def telegram_webhook(req: Request):
    upd = await req.json()
    msg = upd.get("message") or upd.get("edited_message") or {}
    chat = msg.get("chat") or {}
    chat_id = chat.get("id")
    text = (msg.get("text") or "").strip()

    print(f"[webhook] chat_id={chat_id} text={text!r}")

    # Pas de token => on ne tente pas l'envoi
    if not chat_id:
        return {"ok": True, "note": "no chat_id"}
    if not TELEGRAM_TOKEN:
        return {"ok": True, "note": "TELEGRAM_TOKEN missing"}

    # Commande /set_ollama (autorisé pour tout le monde, plus de restriction admin)
    if text.startswith("/set_ollama"):
        parts = text.split(maxsplit=1)
        if len(parts) == 2:
            url = parts[1].strip().rstrip("/")
            # Validation simple (évite les /api et espaces)
            if url.startswith("http") and "/api" not in url:
                global BASE_OVERRIDE
                BASE_OVERRIDE = url
                resp = f"✅ Base Ollama mise à jour : {url}"
            else:
                resp = "❌ URL invalide. Exemple: https://xxxxx.trycloudflare.com"
        else:
            resp = "Usage: /set_ollama https://xxxxx.trycloudflare.com"
        if TELEGRAM_API:
            async with http_client() as c:
                tr = await c.post(f"{TELEGRAM_API}/sendMessage", json={"chat_id": chat_id, "text": resp})
                print(f"[telegram] sendMessage status={tr.status_code}")
        return {"ok": True}

    # Message normal => appel Ollama
    reply_text = await chat_ollama(text or "bonjour")
    if TELEGRAM_API:
        async with http_client() as c:
            tr = await c.post(f"{TELEGRAM_API}/sendMessage", json={"chat_id": chat_id, "text": reply_text})
            print(f"[telegram] sendMessage status={tr.status_code}")
    return {"ok": True}
