#!/usr/bin/env bash
set -euo pipefail

# ----- CONFIG : à définir dans l'environnement avant d'exécuter -----
: "${RENDER_API_KEY:?RENDER_API_KEY manquant}"
: "${RENDER_SERVICE_ID:?RENDER_SERVICE_ID manquant (ex: srv-xxxxxxxxxxxx)}"
: "${RENDER_PUBLIC_URL:?RENDER_PUBLIC_URL manquant (ex: https://ferme-ia-ultra-web.onrender.com)}"

# ----- 1) Récupérer l'URL https ngrok (sans jq) -----
echo "[1/4] Recherche de l'URL ngrok…"
NGROK_URL="$(curl -s http://127.0.0.1:4040/api/tunnels \
  | grep -o 'https://[a-z0-9.-]*ngrok-free.app' | head -n1 || true)"

if [ -z "${NGROK_URL}" ]; then
  echo "ERREUR: Impossible de récupérer l'URL ngrok. Vérifie que 'ngrok http 11434' tourne."
  exit 2
fi
echo "   NGROK_URL=${NGROK_URL}"

# ----- 2) Mettre à jour l’ENV VAR sur Render (clé unique) -----
echo "[2/4] MAJ OLLAMA_BASE_URL sur Render…"
curl -fsS -X PUT \
  "https://api.render.com/v1/services/${RENDER_SERVICE_ID}/env-vars/OLLAMA_BASE_URL" \
  -H "Authorization: Bearer ${RENDER_API_KEY}" \
  -H "Content-Type: application/json" \
  -d "$(printf '{"value":"%s"}' "${NGROK_URL}")" >/dev/null
echo "   OK: OLLAMA_BASE_URL mis à jour."

# ----- 3) Déclencher un déploiement -----
echo "[3/4] Déclenchement du déploiement Render…"
curl -fsS -X POST \
  "https://api.render.com/v1/services/${RENDER_SERVICE_ID}/deploys" \
  -H "Authorization: Bearer ${RENDER_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{}' >/dev/null
echo "   OK: Deploy déclenché."

# ----- 4) Attendre que /health réponde 200 -----
echo "[4/4] Attente de disponibilité ${RENDER_PUBLIC_URL%/}/health …"
ATTEMPTS=60
SLEEP=5
for i in $(seq 1 $ATTEMPTS); do
  CODE="$(curl -s -o /dev/null -w '%{http_code}' "${RENDER_PUBLIC_URL%/}/health" || true)"
  if [ "$CODE" = "200" ]; then
    echo "   OK: Health 200 (${RENDER_PUBLIC_URL%/}/health)"
    exit 0
  fi
  echo "   … encore indisponible (code ${CODE}), retry ${i}/${ATTEMPTS}"
  sleep $SLEEP
done

echo "TIMEOUT: /health ne répond pas 200. Va voir les logs Render."
exit 4
