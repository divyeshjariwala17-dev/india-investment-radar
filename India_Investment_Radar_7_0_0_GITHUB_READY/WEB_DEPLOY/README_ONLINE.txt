INDIA INVESTMENT RADAR — ONLINE / MOBILE DEPLOYMENT
==================================================

PURPOSE
-------
This folder makes the same Radar code Docker-ready for a Linux server/VM.
Use this for access from desktop/mobile/tablet even when your Windows PC is OFF.

IMPORTANT
---------
1. The local Windows app works permanently on the installed PC without a cloud server.
2. Same-Wi-Fi phone access is available through OPEN_ON_PHONE_SAME_WIFI.bat, but that requires the PC to stay ON.
3. Anywhere access with the PC OFF requires an online server to stay ON.
4. No third-party hosting company can be guaranteed to remain free forever. This package is portable so you can move providers.
5. For permanent hosted data, use a persistent disk/volume mounted at /radar-data. Do NOT rely on an ephemeral container filesystem.

GITHUB
------
You can keep the code in a PRIVATE GitHub repository.
Do not commit portfolio data, passwords, API keys or local secrets.
The included .github/workflows/qa.yml runs the verifier after code changes.

DOCKER SERVER ROUTE
-------------------
On a Linux server with Docker + Docker Compose:
1. Upload/clone the complete repository.
2. From the project root run:
   docker compose -f WEB_DEPLOY/docker-compose.yml up -d --build
3. Open http://SERVER-IP:8501
4. Put HTTPS/reverse proxy in front before exposing the app publicly.

PERSISTENT DATA
---------------
The compose file creates a Docker volume and mounts it at /radar-data.
The entrypoint links /app/data to that persistent volume automatically.
Backups should also be copied outside the container/server periodically.

FREE-FIRST POLICY
-----------------
Automatic paid usage: OFF.
If a hosting free tier later changes, export/backup data and move this same Docker package to another compatible host.
