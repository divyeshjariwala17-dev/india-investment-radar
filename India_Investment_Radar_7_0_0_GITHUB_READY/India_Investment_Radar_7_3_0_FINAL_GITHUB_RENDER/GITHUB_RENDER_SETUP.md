# India Investment Radar 7.3.0 FINAL MASTER — GitHub + Render

## Architecture
- **GitHub**: one master application codebase/version history.
- **Render**: online Streamlit runtime.
- **Supabase private Storage**: current synchronized working data and compressed data packs.
- **Google Drive**: optional long-term archive.
- **Google Sheets**: optional readable Data Vault index, not the raw multi-GB database.
- **PC**: full local/offline-capable copy from the same codebase.

## Upload/update GitHub
1. Extract the GitHub ZIP.
2. Upload/commit the contents of the folder itself to your private `india-investment-radar` repository.
3. Do **not** upload `.env`, Supabase secret keys, Google service-account JSON, local portfolio files or private runtime data.
4. Commit/push. If Render is connected to the repository with Auto Deploy, it rebuilds from the same codebase.

## Required Render private environment variables for cloud persistence
Set these in Render → Service → Environment:
- `SUPABASE_URL`
- `SUPABASE_SECRET_KEY`
- `SUPABASE_BUCKET=radar-private`

Never put their real values in GitHub.

## Optional Google cloud archive/index
For true cloud-side Google Drive/Sheets access:
1. Create a Google Cloud service account in your own Google project.
2. Enable Google Drive API and Google Sheets API.
3. Create or choose a Drive folder and share it with the service account email as Editor.
4. Optionally create a Google Sheet and share it with the same service account.
5. Add these as private Render environment variables:
   - `GOOGLE_SERVICE_ACCOUNT_JSON` = the full service-account JSON as a private secret value.
   - `GOOGLE_DRIVE_FOLDER_ID` = the Drive folder ID.
   - `GOOGLE_SHEET_ID` = optional existing Sheet ID.
   - `GOOGLE_SHARE_EMAIL` = optional email if a newly created Sheet should be shared.
6. Open Radar → System → Sync Center → Test Google connection.

Never commit the service-account JSON to GitHub.

## Render deployment
The package contains `Dockerfile` and `render.yaml`. The Docker build installs core + Google integration dependencies and runs `verify_install.py` before the image is accepted.

If you already have the Render service connected to GitHub, normally you only push the updated files; you do not need to create another Render service.

## First cloud run
1. Confirm Supabase variables are configured.
2. Open the Render URL.
3. Open **System → Sync Center** and test Supabase.
4. Download the latest verified cloud data if needed.
5. Run Daily Update to fetch missing/current data and rebuild recommendations.

## Hosting portability
The app remains a normal Docker/Streamlit Python application. Render is not hard-coded into investment logic, so the same GitHub code can be moved to another Docker-capable host later if free-plan policies change.
