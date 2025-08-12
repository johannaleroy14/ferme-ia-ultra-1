# app.py
import os
import httpx
from fastapi import FastAPI, HTTPException, Request
from utils_ollama import get_ollama_base, http_client

app = FastAPI()

@app.get("/health")
async def health():
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
    print(f"[chat_ollama] POST {url}")  # log utile dans Render

    async with http_client() as c:
        try:
            r = await c.post(url, json=payload)
            r.raise_for_status()
            data = r.json()
            return ((data.get("message") or {}).get("content")
                    or data.get("response")
                    or "(Réponse vide d’Ollama)")
        except httpx.RequestError as e:
            print(f"[chat_ollama] RequestError: {e}")
            raise HTTPException(503, f"Connexion Ollama échouée: {e}") from e
        except httpx.HTTPStatusError as e:
            print(f"[chat_ollama] HTTP {e.response.status_code}: {e.response.text}")
            raise HTTPException(e.response.status_code, f"Ollama HTTP {e.response.status_code}: {e.response.text}") from e

# Ton chemin secret de webhook: /telegram/lyra123
@app.post("/telegram/lyra123")
async def telegram_webhook(req: Request):
    body = await req.json()
    text = (body.get("message", {}).get("text") or "").strip() or "bonjour"
    try:
        reply = await chat_ollama(text)
    except HTTPException as e:
        reply = f"(Service temporairement indisponible: {e.detail})"
    # Répondre à Telegram
    token = os.environ.get("TELEGRAM_TOKEN", "")
    chat_id = body.get("message",{}).get("chat",{}).get("id")
    if token and chat_id:
        async with http_client() as c:
            await c.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": reply},
            )
    return {"ok": True}

