 import os, asyncio
from datetime import datetime, timezone
from typing import List, Dict, Optional
from urllib.parse import quote_plus
from collections import defaultdict, deque

from fastapi import FastAPI
import httpx
from bs4 import BeautifulSoup
from openai import AsyncOpenAI

app = FastAPI()

# === Config via variables d'env ===
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT = os.getenv("TELEGRAM_CHAT_ID", "")
WEBHOOK_SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET", "dev")
ALLOW_ALL_CHATS = os.getenv("ALLOW_ALL_CHATS", "0") == "1"

OSINT_KEYWORDS = os.getenv("OSINT_KEYWORDS", "ton-domaine.com").split(",")
TOR_SOCKS_URL = os.getenv("TOR_SOCKS_URL", "").strip()

HEARTBEAT_SECONDS = int(os.getenv("HEARTBEAT_SECONDS", "1800"))
OSINT_INTERVAL_SECONDS = int(os.getenv("OSINT_INTERVAL_SECONDS", "21600"))
RUN_OSINT_ON_BOOT = os.getenv("RUN_OSINT_ON_BOOT", "1") == "1"

# === Conversation (LLM) ===
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_API_BASE = os.getenv("OPENAI_API_BASE", "").strip()  # optionnel (OpenRouter, etc.)
CHAT_MODEL = os.getenv("CHAT_MODEL", "gpt-4o-mini")
TEMP = float(os.getenv("TEMP", "0.3"))
MEM_SIZE = int(os.getenv("MEM_SIZE", "12"))

history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=MEM_SIZE))
client: Optional[AsyncOpenAI] = None
if OPENAI_API_BASE:
    client = AsyncOpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_API_BASE) if OPENAI_API_KEY else None
else:
    client = AsyncOpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

SYSTEM_PROMPT = os.getenv(
    "SYSTEM_PROMPT",
    "Tu es Lyra: assistante utile, concise, en français, ton naturel. "
    "Réponds clairement, étape par étape si besoin. Évite les réponses trop longues."
)

def _split_chunks(text: str, size: int = 3800) -> List[str]:
    return [text[i:i+size] for i in range(0, len(text), size)]

async def ai_chat(chat_id: str, user_text: str) -> str:
    if not client:
        return "Mode conversation non configuré (OPENAI_API_KEY manquant sur Render)."
    msgs = [{"role": "system", "content": SYSTEM_PROMPT}]
    msgs.extend(list(history[chat_id]))
    msgs.append({"role": "user", "content": user_text})
    resp = await client.chat.completions.create(
        model=CHAT_MODEL,
        messages=msgs,
        temperature=TEMP,
    )
    reply = (resp.choices[0].message.content or "").strip()
    if not reply:
        reply = "Désolé, je n’ai pas de réponse là tout de suite."
    # mémorise
    history[chat_id].append({"role": "user", "content": user_text})
    history[chat_id].append({"role": "assistant", "content": reply})
    return reply

# === Utils Telegram ===
async def send_to(chat_id: str, msg: str):
    if not TOKEN:
        return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    async with httpx.AsyncClient(timeout=15) as c:
        for part in _split_chunks(msg):
            await c.post(url, data={"chat_id": chat_id, "text": part})

async def send(msg: str):
    if CHAT:
        await send_to(str(CHAT), msg)

# === OSINT (Ahmia, clearnet) ===
async def _search_ahmia(keyword: str, client_http: httpx.AsyncClient, limit: int = 5) -> List[Dict]:
    url = f"https://ahmia.fi/search/?q={quote_plus(keyword)}"
    r = await client_http.get(url, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    items: List[Dict] = []
    for a in soup.select("a")[:50]:
        href = a.get("href", "")
        text = " ".join((a.get_text() or "").split())
        if not href or href.startswith("#"):
            continue
        if "ahmia.fi" in href and "/search/" in href:
            continue
        items.append({"title": text[:120] or "(sans titre)", "url": href})
        if len(items) >= limit:
            break
    return items

async def run_osint(keywords: List[str], proxies: Optional[str] = None, per_kw_limit: int = 5) -> str:
    # httpx>=0.28 : utiliser proxy= (singulier) et seulement si défini
    kwargs = dict(follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"})
    if proxies:
        kwargs["proxy"] = proxies  # ex: socks5://host:port
    out_lines: List[str] = []
    async with httpx.AsyncClient(**kwargs) as client_http:
        for kw in keywords:
            try:
                kw = kw.strip()
                if not kw:
                    continue
                results = await _search_ahmia(kw, client_http, limit=per_kw_limit)
                if not results:
                    out_lines.append(f"[INFO] {kw}: aucun resultat exploitable.")
                else:
                    out_lines.append(f"[INFO] {kw}: {len(results)} resultats")
                    for i, it in enumerate(results, 1):
                        out_lines.append(f"  {i}. {it['title']}")
            except Exception as e:
                out_lines.append(f"[WARN] {kw}: erreur {e!r}")
    return "\n".join(out_lines[:1200]) if out_lines else "Aucun resultat OSINT."

# === Boucles périodiques ===
async def heartbeat_loop():
    while True:
        await asyncio.sleep(HEARTBEAT_SECONDS)
        await send("Heartbeat Render (web)")

async def osint_loop():
    while True:
        try:
            kws = [k.strip() for k in OSINT_KEYWORDS if k.strip()]
            summary = await run_osint(kws, proxies=TOR_SOCKS_URL or None, per_kw_limit=5)
            await send(f"OSINT (web)\n{summary}")
        except Exception as e:
            await send(f"[WARN] OSINT (web): {e!r}")
        await asyncio.sleep(OSINT_INTERVAL_SECONDS)

# === Webhook Telegram ===
@app.post(f"/telegram/{WEBHOOK_SECRET}")
async def telegram_webhook(payload: dict):
    msg = payload.get("message") or payload.get("edited_message") or {}
    chat = msg.get("chat") or {}
    text = (msg.get("text") or "").strip()
    chat_id = str(chat.get("id") or "")

    # Autorisation: par défaut, ne répond qu'au chat configuré
    if not ALLOW_ALL_CHATS and CHAT and chat_id and chat_id != str(CHAT):
        return {"ok": True}
    if not text:
        return {"ok": True}

    t = text.lower()

    # commandes
    if t.startswith("/start") or t.startswith("/help"):
        help_msg = (
            "Lyra en ligne 🤖\n"
            "/ping → pong\n"
            "/osint mot1, mot2 → mini scan Ahmia\n"
            "/reset → oublie la conversation\n"
            "Sinon… parle-moi normalement 🙂"
        )
        await send_to(chat_id, help_msg)
    elif t.startswith("/ping"):
        await send_to(chat_id, "pong")
    elif t.startswith("/reset"):
        history.pop(chat_id, None)
        await send_to(chat_id, "Mémoire effacée pour ce chat ✔️")
    elif t.startswith("/osint"):
        kws = text.split(" ", 1)[1] if " " in text else ",".join(OSINT_KEYWORDS)
        summary = await run_osint([k.strip() for k in kws.split(",") if k.strip()], proxies=TOR_SOCKS_URL or None)
        await send_to(chat_id, f"OSINT (on-demand)\n{summary}")
    else:
        # mode conversation
        reply = await ai_chat(chat_id, text)
        for part in _split_chunks(reply):
            await send_to(chat_id, part)

    return {"ok": True}

# === FastAPI lifecycle ===
@app.on_event("startup")
async def on_startup():
    await send(f"Web service OK - {datetime.now(timezone.utc).isoformat()}")
    if RUN_OSINT_ON_BOOT:
        try:
            kws = [k.strip() for k in OSINT_KEYWORDS if k.strip()]
            summary = await run_osint(kws, proxies=TOR_SOCKS_URL or None, per_kw_limit=5)
            await send(f"OSINT initial (web)\n{summary}")
        except Exception as e:
            await send(f"[WARN] OSINT boot (web): {e!r}")
    asyncio.create_task(heartbeat_loop())
    asyncio.create_task(osint_loop())

@app.get("/health")
def health():
    return {"status": "ok"}
