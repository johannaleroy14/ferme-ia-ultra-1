import os, sys, asyncio, httpx
TOKEN=os.getenv("TELEGRAM_BOT_TOKEN","")
CHAT=os.getenv("TELEGRAM_CHAT_ID","")
MSG="Ping direct (test)"
async def main():
    if not TOKEN or not CHAT:
        print("Variables manquantes:", {"TOKEN": bool(TOKEN), "CHAT": bool(CHAT)})
        sys.exit(1)
    url=f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    async with httpx.AsyncClient(timeout=15) as c:
        r=await c.post(url, data={"chat_id":CHAT,"text":MSG})
        print("Status:", r.status_code)
        print("Body:", r.text)
asyncio.run(main())
