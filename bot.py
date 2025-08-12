import os
import asyncio
from datetime import datetime, timezone
import httpx

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT = os.getenv("TELEGRAM_CHAT_ID", "")

async def send(msg: str):
    if not (TOKEN and CHAT):
        return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    async with httpx.AsyncClient(timeout=15) as c:
        await c.post(url, data={"chat_id": CHAT, "text": msg})

async def main():
    await send(f"Worker Render OK - {datetime.now(timezone.utc).isoformat()}")
    while True:
        await asyncio.sleep(1800)  # toutes les 30 minutes
        await send("Heartbeat Render")

if __name__ == "__main__":
    asyncio.run(main())
