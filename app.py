# --- PATCH OLLAMA ---
import os, httpx  # assure-toi que ces imports existent en haut de app.py

async def chat_ollama(chat_id: int, user_text: str) -> str:
    """
    Appelle d'abord /api/chat. Si Cloudflare renvoie 403, on retombe sur /api/generate.
    On envoie un User-Agent "navigateur" pour limiter les 403.
    """
    base = (os.environ.get("OLLAMA_BASE_URL") or "http://localhost:11434").rstrip("/")
    model = os.environ.get("OLLAMA_MODEL") or "llama3.2:3b"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json",
        "Content-Type": "application/json",
        # Optionnel mais utile pour certains filtres CF :
        "Origin": base,
        "Referer": base + "/",
    }

    timeout = httpx.Timeout(60.0)

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        # 1) tentative via /api/chat (conversationnelle)
        try:
            payload_chat = {
                "model": model,
                "messages": [{"role": "user", "content": user_text}],
                "stream": False,
            }
            r = await client.post(f"{base}/api/chat", headers=headers, json=payload_chat)
            if r.status_code == 403:
                # Cloudflare a bloqué: on passe directement au fallback
                raise RuntimeError("CF 403 on /api/chat")
            r.raise_for_status()
            data = r.json()
            text = (data.get("message") or {}).get("content") or data.get("response")
            return text or "Désolé, je n’ai rien reçu du modèle."
        except Exception:
            # 2) fallback fiable via /api/generate (mono-instruction)
            payload_gen = {
                "model": model,
                "prompt": user_text,
                "stream": False,
            }
            rg = await client.post(f"{base}/api/generate", headers=headers, json=payload_gen)
            rg.raise_for_status()
            data = rg.json()
            return data.get("response") or "Désolé, je n’ai rien reçu du modèle."
