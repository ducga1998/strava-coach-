#!/usr/bin/env bash
# Upload a Cloudflare API Token to GitHub Actions (fixes Wrangler auth 9106 when the
# repo secret is wrong, expired, or missing Account → Cloudflare Pages → Edit).
#
# 1. Dashboard: https://dash.cloudflare.com/profile/api-tokens → Create Token
#    Use "Edit Cloudflare Workers" template OR custom with:
#    Permissions: Account → Cloudflare Pages → Edit
#    Account resources: your account (or All accounts)
# 2. Then:
#    export CLOUDFLARE_API_TOKEN='paste-token-here'
#    ./scripts/sync-cloudflare-token-to-github.sh
#
set -euo pipefail
REPO="${GITHUB_REPO:-ducga1998/strava-coach-}"
if [[ -z "${CLOUDFLARE_API_TOKEN:-}" ]]; then
  echo "Set CLOUDFLARE_API_TOKEN in the environment first (do not commit it)." >&2
  exit 1
fi
printf %s "$CLOUDFLARE_API_TOKEN" | gh secret set CLOUDFLARE_API_TOKEN --repo "$REPO"
echo "OK: GitHub secret CLOUDFLARE_API_TOKEN updated for $REPO. Re-run the workflow or push to main."
