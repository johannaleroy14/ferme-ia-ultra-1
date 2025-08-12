from typing import List, Dict, Optional
from urllib.parse import quote_plus
import httpx
from bs4 import BeautifulSoup

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
    proxy_cfg = proxies if proxies else None
    async with httpx.AsyncClient(proxies=proxy_cfg, follow_redirects=True, headers={"User-Agent":"Mozilla/5.0"}) as client:
        out_lines: List[str] = []
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
