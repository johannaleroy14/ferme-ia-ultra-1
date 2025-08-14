import os, json, asyncio
from typing import Dict, Any, List
from fastapi import FastAPI, Request
import httpx

app = FastAPI()

# ---- Config / ENV ----
TELEGRAM_TOKEN = (os.getenv("TELEGRAM_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN") or "").strip().strip("'\"")
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}" if TELEGRAM_TOKEN else ""
DEFAULT_MODEL = os.getenv("OLLAMA_MODEL","llama3.2:3b").strip()
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")  # ex: "6800524671"
DEFAULT_FALLBACK = "https://inputs-trail-coupled-specials.trycloudflare.com"
UNLIMITED_DEFAULT = (os.getenv("TELEGRAM_UNLIMITED_DEFAULT","1").strip() not in ("0","false","False"))

# ---- Agents (rôles) ----
AGENTS: Dict[str,str] = {
    "lyra": (
        "Tu es Lyra, cheffe d'exploitation agricole. Tu gères la planification "
        "des tâches, l'allocation des ressources, la météo et les priori        "des tâches, l'allocation des ressources, tapes actionnables."
    ),
    "sante": (
        "Tu es conseillère santé animale (ruminants, volailles). Propose des "
        "vérifications, signes cliniques à surveiller, biosécurité. Pas de diagnostic médical."
    ),
    "cultures": (
        "Tu es planificatrice cultures/maraîchage. Calendrier semis/récolte, rotation, irrigation, "
        "et intrants low-input. Donne toujours des quantités et fenêtres temporelles."
    ),
    "machines": (
        "Tu es technicienne maintenance machines agricoles. Checklists de maintenance, "
        "pannes fréquentes, pièces à contrôler, sécurité avant tout."
    ),
    "vente": (
        "Tu es responsable vente/AMAP/circuits courts. Pricing, messages clients, fiches produit, "
        "prévisionnel et suivi commandes."
    ),
}

# Sessions mémoire courte par chat
SESSIONS: Dict[int, Dict[str, Any]] = {}
HISTORY_LIMIT = 8
MAX_TG = 3900  # utilisé si /unlimited off

def is_admin(chat_id: Any) -> bool:
    return ADMIN_CHAT_ID and str(chat_id) == str(ADMIN_CHAT_ID)

def get_base() -> str:
    """Lit l'URL à CHAQUE requête: OLLAMA_BASE_URL > override > fallback."""
    base = (os.getenv("OLLAMA_BASE_URL") or SESSIONS.get(0, {}).get("override_base") or DEFAULT_FALLBACK).strip().rstrip("/")
    return base

def http_client() -> httpx.AsyncClient:
    tout = httpx.Timeout(connect=5.0, read=40.0, write=40.0, pool=60.0)
    transport = httpx.AsyncHTTPTransport(retries=2)
    return httpx.AsyncClient(http2=False, transport=transport, timeout=tout, headers={
        "Connection": "keep-alive",
        "ngrok-skip-browser-warning": "true",
        "Accept": "application/json",
    })

def get_session(chat_id: int) -> Dict[str, Any]:
    s = SESSIONS.setdefault(chat_id, {"agent": "lyra", "model": DEFAULT_MODEL, "history": [], "unlimited": UNLIMITED_DEFAULT})
    if "agent" not in s: s["agent"] = "lyra"
    if "model" not in s: s["model"] = DEFAULT_MODEL
    if "history" not in s: s["history"] = []
    if "unlimited" not in s: s["unlimited"] = UNLIMITED_DEFAULT
    return s

def system_prompt(agent: str) -> str:
    core = AGENTS.get(agent, AGENTS["lyra"])
    suffix = (
        "\n\nRègles: sois concise, en listes quand utile; donne des next-steps clairs; "
        "si info manquante, propose des options.\n"
    )
    return core + suffix

def chunk_text(text: str, limit: int = 4090) -> List[str]:
    """ Coupe proprement (paragraphes/ligne) en morceaux <= limit. """
    if len(text) <= limit:
        return [text]
    parts: List[str] = []
    for para in text.split("\n\n"):
        if not parts or len(parts[-1]) + len(para) + 2 > limit:
            parts.append(para)
        else:
            parts[-1] += "\n\n" + para
    # si encore trop long, raffine par lignes
    refined: List[str] = []
    for p in parts:
        if len(p) <= limit:
            refined.append(p)
        else:
            cur = ""
            for line in p.splitlines():
                if len(cur) + len(line) + 1 > limit:
                    refined.append(cur)
                    cur = line
                else:
                    cur = (cur + "\n" + line) if cur else line
            if cur:
                refined.append(cur)
    # dernier recours: hard wrap
    out: List[str] = []
    for p in refined:
        if len(p) <= limit:
            out.append(p)
        else:
            start = 0
            while start < len(p):
                out.append(p[start:start+limit])
                start += limit
    return out

async def send_action(chat_id: int, action: str = "typing"):
    if not TELEGRAM_TOKEN: return
    url = f"{TELEGRAM_API}/sendChatAction"
    payload = {"chat_id": chat_id, "action": action}
    try:
        async with http_client() as c:
            await c.post(url, json=payload)
    except Exception:
        pass

async def send_telegram(chat_id: int, text: str) -> None:
    """Envoie long: découpe auto en messages, sinon document .txt si énorme."""
    if not TELEGRAM_TOKEN:
        print("[telegram] SKIP: TELEGRAM_TOKEN manquant")
        return

    session = get_session(chat_id)
    unlimited = bool(session.get("unlimited", True))

    async with http_client() as c:
        if not unlimited:
            # mode limité: une bulle seulement
            if len(text) > MAX_TG:
                text = text[:MAX_TG] + "\n\n…(tronquée – /unlimited on pour tout envoyer)"
            send_url = f"{TELEGRAM_API}/sendMessage"
            payload = {"chat_id": chat_id, "text": text}
            tr = await c.post(send_url, json=payload)
            st = tr.status_code
            tb = await tr.aread()
            print(f"[telegram] sendMessage status={st} body={tb[:300]!r}")
            return

        # mode illimité
        limit = 4090  # marge sous 4096
        if len(text) <= limit:
            send_url = f"{TELEGRAM_API}/sendMessage"
            payload = {"chat_id": chat_id, "text": text}
            tr = await c.post(send_url, json=payload)
            st = tr.status_code
            tb = await tr.aread()
            print(f"[telegram] sendMessage status={st} body={tb[:300]!r}")
            return

        # si très long: fichier .txt
        if len(text) > limit * 6:
            url = f"{TELEGRAM_API}/sendDocument"
            files = {"document": ("reponse.txt", text.encode("utf-8"), "text/plain")}
            data = {"chat_id": str(chat_id), "caption": "Réponse complète (fichier)"}
            tr = await c.post(url, data=data, files=files)
            st = tr.status_code
            tb = await tr.aread()
            print(f"[telegram] sendDocument status={st} body={tb[:300]!r}")
            return

        # sinon: on découpe en plusieurs messages
        parts = chunk_text(text, limit=limit)
        total = len(parts)
        for i, part in enumerate(parts, 1):
            prefix = f"({i}/{total})\n" if total > 1 else ""
            payload = {"chat_id": chat_id, "text": prefix + part}
            tr = await c.post(f"{TELEGRAM_API}/sendMessage", json=payload)
            st = tr.status_code
            tb = await tr.aread()
            print(f"[telegram] sendMessage[{i}/{total}] status={st} body={tb[:200]!r}")
            await asyncio.sleep(0.12)  # petit délai anti rate-limit

async def chat_ollama(chat_id: int, user_text: str) -> str:
    session = get_session(chat_id)
    model = session.get("model", DEFAULT_MODEL)
    msgs: List[Dict[str,str]] = [{"role": "system", "content": system_prompt(session["agent"])}]
    for m in session["history"][-HISTORY_LIMIT:]:
        msgs.append(m)
    msgs.append({"role": "user", "content": user_text})

    payload = {"model": model, "messages": msgs, "stream": False}
    url = f"{get_base()}/api/chat"
    print(f"[chat_ollama] POST {url} (agent={session['agent']} model={model})")
    tries = 0
    while tries < 2:
        tries += 1
        try:
            async with http_client() as c:
                r = await c.post(url, json=payload)
                body = await r.aread()
                print(f"[chat_ollama] status={r.status_code}")
                print(f"[chat_ollama] body_snippet={(body[:500] if isinstance(body,(bytes,bytearray)) else str(body))!r}")
                r.raise_for_status()
                data = json.loads(body.decode("utf-8") if isinstance(body,(bytes,bytearray)) else body)
            reply = (data.get("message", {}).get("content") or data.get("response") or "").strip()
            if not reply:
                reply = "Désolé, je n’ai pas pu générer de réponse."
            session["history"].append({"role":"user","content":user_text})
            session["history"].append({"role":"assistant","content":reply})
            session["history"] = session["history"][-(HISTORY_LIMIT*2):]
            return reply
        except httpx.ReadTimeout:
            print("[chat_ollama] ReadTimeout, retrying…")
            await asyncio.sleep(0.5)
        except Exception as e:
            print("[chat_ollama] ERROR:", repr(e))
            return "Petit souci côté IA, réessaie dans une minute."
    return "Temps de réponse un peu long côté IA, réessaie juste maintenant."

# ---- API debug ----
@app.get("/health")
def health(): return {"ok": True}

@app.get("/env")
def env():
    return {
        "OLLAMA_BASE_URL_env": (os.getenv("OLLAMA_BASE_URL") or "").strip(),
        "BASE_used_now": get_base(),
        "TELEGRAM_TOKEN_set": bool(TELEGRAM_TOKEN),
    }

@app.get("/diag")
async def diag():
    url = f"{get_base()}/api/tags"
    try:
        async with http_client() as c:
            r = await c.get(url)
            raw = await r.aread()
        return {"ok": True, "status": r.status_code, "snippet": (raw[:200].decode('utf-8','ignore') if isinstance(raw,(bytes,bytearray)) else str(raw)[:200]), "url": url}
    except Exception as e:
        return {"ok": False, "err": repr(e), "url": url}

# ---- Webhook Telegram + commandes Lyra ----
@app.post("/telegram/lyra123")
async def telegram_webhook(req: Request):
    upd = await req.json()
    msg = upd.get("message") or upd.get("edited_message") or {}
    chat = msg.get("chat") or {}
    chat_id = chat.get("id")
    text = (msg.get("text") or "").strip()
    print(f"[webhook] chat_id={chat_id} text={text!r}")

    if not chat_id:
        return {"ok": True, "note": "Pas de chat_id"}

    # commandes
    if text.startswith("/start"):
        get_session(chat_id)
        await send_telegram(chat_id, "Salut, c’est Lyra 👩‍🌾. Tape /agents pour voir les rôles. /unlimited on|off pour le débit.")
        return {"ok": True}

    if text.startswith("/agents"):
        names = ", ".join(sorted(AGENTS.keys()))
        await send_telegram(chat_id, f"Agents dispo: {names}\nUtilise /agent nom  (ex: /agent cultures)")
        return {"ok": True}

    if text.startswith("/agent "):
        name = text.split(" ",1)[1].strip().lower()
        if name in AGENTS:
            get_session(chat_id)["agent"] = name
            await send_telegram(chat_id, f"✅ Agent actif: {name}")
        else:
            await send_telegram(chat_id, f"Agent inconnu. Tape /agents pour la liste.")
        return {"ok": True}

    if text.startswith("/model "):
        mdl = text.split(" ",1)[1].strip()
        get_session(chat_id)["model"] = mdl
        await send_telegram(chat_id, f"✅ Modèle défini: {mdl}")
        return {"ok": True}

    if text.startswith("/reset"):
        SESSIONS[chat_id] = {"agent":"lyra","model":DEFAULT_MODEL,"history":[],"unlimited":UNLIMITED_DEFAULT}
        await send_telegram(chat_id, "Mémoire effacée. Agent: lyra.")
        return {"ok": True}

    if text.startswith("/set_ollama "):
        if is_admin(chat_id):
            new = text.split(" ",1)[1].strip().rstrip("/")
            SESSIONS.setdefault(0, {})["override_base"] = new
            await send_telegram(chat_id, f"🔁 Base Ollama mise à jour: {new}\n(prise en compte immédiate)")
        else:
            await send_telegram(chat_id, "⛔ Commande admin uniquement.")
        return {"ok": True}

    if text.startswith("/unlimited"):
        arg = (text.split(" ",1)[1].strip().lower() if " " in text else "on")
        s = get_session(chat_id)
        if arg in ("on","oui","true","1"):
            s["unlimited"] = True
            await send_telegram(chat_id, "🚀 Mode illimité activé : messages longs découpés, fichiers si nécessaire.")
        elif arg in ("off","non","false","0"):
            s["unlimited"] = False
            await send_telegram(chat_id, "⛔ Mode illimité désactivé : une seule bulle (tronquage possible).")
        else:
            await send_telegram(chat_id, "Utilise /unlimited on ou /unlimited off")
        return {"ok": True}

    # conversation normale
    await send_action(chat_id, "typing")
    reply = await chat_ollama(chat_id, text if text else "bonjour")
    await send_telegram(chat_id, reply)
    return {"ok": True}
