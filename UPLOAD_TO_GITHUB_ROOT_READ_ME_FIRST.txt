INDIA INVESTMENT RADAR v7.3.0 - GITHUB/RENDER ROOT UPLOAD FIX

IMPORTANT:
1. Open this folder after extracting the ZIP.
2. Upload ALL contents of this folder to the ROOT of your existing GitHub repo.
3. app.py and deposit_rates.py MUST be visible at the SAME GitHub level.
4. Also upload all other .py files, data folder, .streamlit folder, Dockerfile,
   render.yaml, requirements.txt and other files in this package.
5. Do NOT upload this outer folder as a subfolder.
6. Do NOT put these files inside your old WEB_DEPLOY/payload/resources folders.
7. Keep your existing Render environment variables. Never upload .env/secrets.
8. Render Root Directory should be blank (repo root) for this package.
9. After commit, use Render: Manual Deploy -> Clear build cache & deploy.

BEFORE DEPLOY CHECK ON GITHUB ROOT:
- app.py
- deposit_rates.py
- radar_engine.py
- market_intelligence.py
- daily_recommendations.py
- market_outlook.py
- money_optimizer.py
- data_vault.py
- Dockerfile
- render.yaml
- requirements.txt

If deposit_rates.py is not visible next to app.py, STOP: upload is incomplete.
