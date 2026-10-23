#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
#  Rozgar — GitHub par ek command mein push
#
#    tools/push.sh https://github.com/USERNAME/rozgar ghp_xxxxxxxx
#    GITHUB_TOKEN=ghp_xxx tools/push.sh https://github.com/USERNAME/rozgar
#
#  Token repo mein save NAHI hota — sirf is command ke andar use hota hai.
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

REPO="${1:-}"
TOKEN="${2:-${GITHUB_TOKEN:-}}"
BRANCH="${BRANCH:-main}"

if [[ -z "$REPO" || -z "$TOKEN" ]]; then
  cat <<'USAGE'
Usage:
  tools/push.sh https://github.com/USERNAME/rozgar <token>

Token: GitHub → Settings → Developer settings → Personal access tokens
       → Fine-grained tokens → permissions:
         Contents: Read and write
         Workflows: Read and write
         Metadata: Read-only (auto)
USAGE
  exit 1
fi

# normalise: ssh form, trailing .git, trailing slash
REPO="${REPO%.git}"; REPO="${REPO%/}"
[[ "$REPO" == git@github.com:* ]] && REPO="https://github.com/${REPO#git@github.com:}"
REPO="${REPO#http://}"; REPO="${REPO#https://}"; REPO="${REPO#github.com/}"
SLUG="$REPO"                                   # username/repo
AUTH="https://x-access-token:${TOKEN}@github.com/${SLUG}.git"

echo "→ repo : ${SLUG}"
echo "→ branch: ${BRANCH}"
git -c credential.helper= push "$AUTH" "HEAD:${BRANCH}" 2>&1 | sed "s|${TOKEN}|***|g"

echo "✓ push ho gaya"

# ── GitHub Pages ko "GitHub Actions" source par set karein (agar permission ho)
if [[ "${ENABLE_PAGES:-1}" == "1" ]]; then
  code=$(curl -s -o /tmp/pages.json -w '%{http_code}' -X POST \
    -H "Authorization: Bearer ${TOKEN}" \
    -H "Accept: application/vnd.github+json" \
    -H "X-GitHub-Api-Version: 2022-11-28" \
    "https://api.github.com/repos/${SLUG}/pages" \
    -d '{"build_type":"workflow"}' || true)
  case "$code" in
    201|204) echo "✓ Pages on ho gaya (source: GitHub Actions)" ;;
    409)     echo "• Pages pehle se on hai" ;;
    403|404) echo "• Pages khud on karna hoga: Settings → Pages → Source = GitHub Actions" ;;
    *)       echo "• Pages API: HTTP ${code} (Settings → Pages se on karein)" ;;
  esac
fi

OWNER="${SLUG%%/*}"; NAME="${SLUG##*/}"
if [[ "$NAME" == "${OWNER}.github.io" ]]; then
  echo "🌐 Site: https://${OWNER}.github.io/"
else
  echo "🌐 Site: https://${OWNER}.github.io/${NAME}/"
fi
echo "   (pehli build 3–5 minute leti hai — Actions tab mein progress dekhein)"
