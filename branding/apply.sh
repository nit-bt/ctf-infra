#!/usr/bin/env bash
# Apply the CTFC branding to a CTFd instance through its API.
# Usage: URL=http://localhost:8000 TOKEN=ctfd_xxx ./apply.sh
# Get TOKEN from CTFd as admin: Settings > Access Tokens > Generate.
# Safe to run again: it re-uploads the images and overwrites theme, logo, favicon and home page.
set -euo pipefail
cd "$(dirname "$0")"
: "${URL:?set URL, e.g. URL=http://localhost:8000}"
: "${TOKEN:?set TOKEN (Settings > Access Tokens)}"
command -v jq >/dev/null || { echo "need jq: sudo apt install -y jq"; exit 1; }
H="Authorization: Token $TOKEN"

upload() {  # prints the /files/... location
  curl -fsS -H "$H" -F "file=@$1" -F type=page "$URL/api/v1/files" | jq -r '.data[0].location'
}
patch_cfg() {  # reads JSON from stdin
  curl -fsS -o /dev/null -X PATCH -H "$H" -H 'Content-Type: application/json' -d @- "$URL/api/v1/configs"
}

echo "uploading images..."
LOGO=$(upload ctfc-logo.png)
BADGE=$(upload ctfc-logo.png)   # navbar: full logo
ICON=$(upload favicon.ico)

echo "theme, logo, favicon..."
jq -n --rawfile h theme-header.html --arg b "$BADGE" --arg i "$ICON" \
  '{ctf_theme:"core-beta", theme_header:$h, ctf_logo:$b, ctf_small_icon:$i}' | patch_cfg

echo "home page..."
HTML=$(sed "s#LOGO_URL#/files/$LOGO#" index-page.html)
ID=$(curl -fsS -H "$H" -H "Content-Type: application/json" "$URL/api/v1/pages" | jq -r '.data[] | select(.route=="index") | .id' | head -1)
BODY=$(jq -n --arg c "$HTML" '{title:"Home", route:"index", format:"html", content:$c, draft:false, hidden:false, auth_required:false}')
if [ -n "$ID" ]; then
  curl -fsS -o /dev/null -X PATCH -H "$H" -H 'Content-Type: application/json' -d "$BODY" "$URL/api/v1/pages/$ID"
else
  curl -fsS -o /dev/null -X POST  -H "$H" -H 'Content-Type: application/json' -d "$BODY" "$URL/api/v1/pages"
fi

echo "done. open $URL in a private window to check."
