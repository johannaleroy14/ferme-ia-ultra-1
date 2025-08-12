# --- remplace ta fonction chat_ollama par ceci ---
import json, os, httpx

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")

async def chat_ollama(chat_id: int, user_text: str) -> str:
    if not OLLAMA_BASE_URL:
        return "⚠️ OLLAMA_BASE_URL manquant côté serveur."

    payload_chat = {
        "model": OLLAMA_MODEL,
        "stream": False,
        "messages": [
            {"role": "system", "content": "Tu es Lyra, assistant francophone, bref et utile."},
            {"role": "user", "content": user_text}
        ]
    }
    payload_gen = {"model": OLLAMA_MODEL, "prompt": user_text, "stream": False}

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36",
    }

    url_chat = f"{OLLAMA_BASE_URL}/api/chat"
    url_gen  = f"{OLLAMA_BASE_URL}/api/generate"

    timeout = httpx.Timeout(40.0)
    async with httpx.AsyncClient(follow_redirects=True, headers=headers, timeout=timeout, http2=True) as c:
        # 1) Tente /api/chat
        r = await c.post(url_chat, content=json.dumps(payload_chat))
        if r.status_code == 403:
            # 2) Fallback /api/generate si Cloudflare bloque /api/chat
            r = await c.post(url_gen, content=json.dumps(payload_gen))
        r.raise_for_status()
        data = r.json()

        # Normalisation de la réponse
        if isinstance(data, dict) and "message" in data and "content" in data["message"]:
            return str(data["message"]["content"]).strip()
        if isinstance(data, dict) and "response" in data:
            return str(data["response"]).strip()
        return json.dumps(data)[:1500]
# --- fin remplacement ---
