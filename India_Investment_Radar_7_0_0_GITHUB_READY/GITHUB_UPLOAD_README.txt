INDIA INVESTMENT RADAR 7.0.0 — GITHUB READY

This copy is prepared for a PRIVATE GitHub repository.
It excludes Python cache files, local secrets, runtime state and backups.

DO NOT COMMIT:
- portfolio/private data
- passwords or API keys
- .env
- payload/data/local_secrets.json
- payload/data/alpha_key.txt
- payload/data/.runtime.json
- payload/backups/

Recommended repository: india-investment-radar (PRIVATE)

For online deployment see WEB_DEPLOY/README_ONLINE.txt.

CLOUD PERSISTENCE (7.0.1)
-------------------------
For Streamlit Community Cloud, critical personal state can be mirrored to a PRIVATE Supabase Storage bucket.
Create a private bucket named radar-private and add these Streamlit Secrets (never commit them):
SUPABASE_URL="https://YOUR_PROJECT.supabase.co"
SUPABASE_SERVICE_ROLE_KEY="YOUR_SERVICE_ROLE_KEY"
SUPABASE_BUCKET="radar-private"

The app syncs only critical user-created state such as portfolio, goals, allocation plans, recommendation history, UI settings/background, edited investment options, IPO watchlist and fixed-income watchlist. Large/regenerable market caches are not uploaded.
