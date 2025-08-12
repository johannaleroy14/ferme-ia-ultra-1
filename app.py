import os, asyncio
from datetime import datetime, timezone
from fastapi import FastAPI
import httpx
from osint import run_osint

app = FastAPI()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT = os.getenv("TELEGRAM_CHAT_ID", "")

OSINT_KEYWORDS = os.getenv("OSINT_KEYWORDS", "ton-domaine.com").split(",")
TOR_SOCKS_URL = os.getenv("TOR_SOCKS_URL", "").strip()
HEARTBEAT_SECONDS = int(os.getenv("HEARTBEAT_SECONDS", "1800"))
OSINT_INTERVAL_SECONDS = int(os.getenv("OSINT_INTERVAL_SECONDS", "21600"))
RUN_OSINT_ON_BOOT = os.getenv("RUN_OSINT_ON_BOOT", "1") == "1"

async def send(msg: str):
    if not (TOKEN and CHAT): return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    async with httpx.AsyncClient(timeout=15) as c:
        await c.post(url, data={"chat_id": CHAT, "text": msg})

async def heartbeat_loop():
    while True:
        await asyncio.sleep(HEARTBEAT_SECONDS)
        await send("Heartbeat Render (web)")

async def osint_loop():
    while True:
        try:
            kws = [k.strip() for k in OSINT_KEYWORDS if k.strip()]
            summary = await run_osint(kws, proxies=TOR_SOCKS_URL or None, per_kw_limit=5)
            await send(f"🛰️ Rapport OSINT (web)\n{summary}")
        except Exception as e:
            await send(f"⚠️ OSINT (web): {e!r}")
        await asyncio.sleep(OSINT_INTERVAL_SECONDS)

@app.on_event("startup")
async def on_startup():
    await send(f"Web service OK - {datetime.now(timezone.utc).isoformat()}")
    if RUN_OSINT_ON_BOOT:
        try:
            kws = [k.strip() for k in OSINT_KEYWORDS if k.strip()]
            summary = await run_osint(kws, proxies=TOR_SOCKS_URL or None, per_kw_limit=5)
            await send(f"🛰️ Rapport OSINT initial (web)\n{summary}")
        except Exception as e:
            await send(f"⚠️ OSINT boot (web): {e!r}")
    asyncio.create_task(heartbeat_loop())
    asyncio.create_task(osint_loop())

@app.get("/health")
def health():
    return {"status": "ok"}
