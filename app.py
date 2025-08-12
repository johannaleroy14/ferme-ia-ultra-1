import os, asyncio
from datetime import datetime, timezone
from typing import List, Dict, Optional
from urllib.parse import quote_plus

from fastapi import FastAPI
import httpx
from bs4 import BeautifulSoup

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

# === Utils Telegram ===
async def send_to(chat_id: str, msg: str):
    if not TOKEN:
        return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    async with httpx.AsyncClient(timeout=15) as c:
        await c.post(url, data={"chat_id": chat_id, "text": msg})

async def send(msg: str):
    if CHAT:
        await send_to(str(CHAT), msg)

# === OSINT (Ahmia, clearnet) ===
async def _search_ahmia(keyword: str, client: httpx.AsyncClient, limit: int = 5) -> List[Dict]:
    url = f"https://ahmia.fi/search/?q={quote_plus(keyword)}"
    r = await client.get(url, timeout=30)
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
    # httpx>=0.28 : utiliser proxy= (singulier)
    kwargs = dict(follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"})
    if proxies:
        kwargs["proxy"] = proxies  # ex: "socks5://host:port"
    out_lines: List[str] = []
    async with httpx.AsyncClient(**kwargs) as client:
        for kw in keywords:
            try:
                kw = kw.strip()
                if not kw:
                    continue
                results = await _search_ahmia(kw, client, limit=per_kw_limit)
                if not results:
                    out_lines.append(f"[INFO] {kw}: aucun resultat exploitable.")
                else:
                    out_lines.append(f"[INFO] {kw}: {len(results)} resultats")
                    for i, it in enumerate(results, 1):
                        out_lines.append(f"  {i}. {it['title']}")
            except Exception as e:
                out_lines.append(f"[WARN] {kw}: erreur {e!r}")
    return "\n".join(out_lines[:1200]) if out_lines else "Aucun resultat OSINT."

# === Boucles periodiques ===
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

    # Autorisation: par defaut, ne repond qu'au chat configure
    if not ALLOW_ALL_CHATS and CHAT and chat_id and chat_id != str(CHAT):
        return {"ok": True}

    if not text:
        return {"ok": True}

    t = text.lower()

    if t.startswith("/start") or t.startswith("/help"):
        help_msg = (
            "Bot en ligne.\n"
            "/ping -> pong\n"
            "/osint mot1, mot2 -> scan OSINT\n"
            "Messages normaux: bonjour/merci/etc.\n"
        )
        await send_to(chat_id, help_msg)
    elif t.startswith("/ping"):
        await send_to(chat_id, "pong")
    elif t.startswith("/osint"):
        kws = text.split(" ", 1)[1] if " " in text else ",".join(OSINT_KEYWORDS)
        summary = await run_osint([k.strip() for k in kws.split(",") if k.strip()], proxies=TOR_SOCKS_URL or None)
        await send_to(chat_id, f"OSINT (on-demand)\n{summary}")
    else:
        # Réponses simples pour messages non-commandes
        if any(w in t for w in ["bonjour", "salut", "coucou", "hello", "bonsoir"]):
            await send_to(chat_id, "Salut ! Je suis en ligne ✅\nEssaie /osint mot1, mot2 ou /help.")
        elif "merci" in t:
            await send_to(chat_id, "Avec plaisir !")
        elif any(w in t for w in ["ça va", "ca va", "comment ça va", "comment ca va"]):
            await send_to(chat_id, "Super et toi ? 🙂")
        else:
            await send_to(chat_id, "Je peux t’aider avec /osint mot1, mot2 — ou tape /help pour la liste.")
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
