#!/bin/bash
# Build the static site and push it to the gh-pages branch for GitHub Pages.
# Usage: ./deploy_pages.sh   (run from repo root; requires a GitHub remote)
set -e
cd "$(dirname "$0")"

# 1. Regenerate the static data from the DB
python3 export_static.py

# 2. Build a gh-pages branch containing only the static site
TMP=$(mktemp -d)
cp web/index.html web/data.json "$TMP/"
git branch -D gh-pages 2>/dev/null || true
git checkout --orphan gh-pages
git rm -rf . >/dev/null 2>&1 || true
cp "$TMP/index.html" "$TMP/data.json" .
git add index.html data.json
git commit -m "deploy: static allofculture explorer"
git push -f origin gh-pages
git checkout main
rm -rf "$TMP"
echo "deployed to gh-pages — enable Pages at Settings > Pages > branch: gh-pages"
