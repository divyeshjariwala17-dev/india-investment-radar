# India Investment Radar 7.3.0 FINAL MASTER — PC Setup

## What this installation does
The PC installer creates one stable local installation under `%LOCALAPPDATA%\IndiaInvestmentRadar`. Program updates are copied into that location while the `data` folder and `.env` secrets are preserved. A private `.venv` is created for the Radar, so it does not depend on the Python packages of your other applications.

The launcher scans ports 8507–8599 and uses a free port automatically. You do not need to edit a port number.

## First installation
1. Extract the PC ZIP to a normal folder such as Downloads or Desktop. Do not run it from inside the ZIP preview.
2. Double-click **INSTALL_OR_UPDATE_PC.bat**.
3. If Python 3.11+ is already installed, the installer uses it. If Python is missing and Windows Package Manager is available, the installer attempts a user-level Python 3.13 installation.
4. The installer creates/repairs the private environment, installs dependencies, runs the offline verification suite, and creates a Desktop/Start Menu shortcut named **India Investment Radar 7.3.0**.
5. Open the Desktop shortcut.
6. On a new PC, run **FIRST SETUP / FULL DATA** once if the app says NSE history/validation is not ready.
7. Then use **DAILY UPDATE — UPDATE EVERYTHING** after the Indian market closes for normal EOD use.

## Existing installation / update
Run the same **INSTALL_OR_UPDATE_PC.bat**. The installer updates code and dependencies but deliberately does not delete/replace your existing `data` folder or `.env` file.

## Supabase PC + cloud sync
After installation, run **CONFIGURE_CLOUD_SYNC_PC.bat** inside `%LOCALAPPDATA%\IndiaInvestmentRadar`, or open **System → Sync Center**. Enter the same Supabase Project URL, secret key and private bucket used by Render. Never put the secret key in GitHub.

## Google archive
The easiest PC method is Google Drive for Desktop:
1. Install/sign in to Google Drive for Desktop.
2. Open Radar → **System → Sync Center**.
3. Enter the synced Drive root/folder path, e.g. `G:\My Drive`.
4. Save and click **Test Google connection**.
5. Optionally enable automatic Data Index refresh and/or full ZIP archive after Daily Update.

This mode needs no Google API secret. The Radar creates `India Investment Radar/Archive/YYYY/MM` inside the synced folder.

## Useful maintenance files in the installed folder
- `START_RADAR.bat` — opens the app.
- `STOP_RADAR.bat` — stops the local Radar server.
- `VERIFY_INSTALLATION.bat` — offline module/integration test.
- `REPAIR_INSTALLATION.bat` — repairs dependencies without deleting user data.
- `CONFIGURE_CLOUD_SYNC_PC.bat` — private Supabase configuration.
- `CONFIGURE_GOOGLE_ARCHIVE_PC.bat` — Google archive setup.
- `BACKUP_DATA_NOW.bat` — local backup.
- `OPEN_DATA_FOLDER.bat` — opens the local data folder.

## Offline use
The app can open using verified local/cache data when internet is unavailable. Fresh market collection obviously requires internet. Stale/missing data is shown in Auto Data Center and confidence is reduced or action is blocked where appropriate.

## Important limitation
No package can guarantee that NSE/AMFI/RBI/Google/Render/Supabase public or third-party interfaces will never change. This build is designed to fail safely: preserve the last verified cache, mark freshness/failure, use configured free fallbacks where safe, and avoid falsely confident recommendations.
