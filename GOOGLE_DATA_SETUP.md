# Google Data + Archive Design

Google is deliberately an **archive and readable-index layer**, not the primary live database.

## Data locations
1. **Supabase** — current shared/cloud working data and compressed packs.
2. **PC data folder** — full local/offline data and user state.
3. **Data Vault** — dated snapshots preserving what the Radar actually knew/recommended on that date.
4. **Google Drive** — optional long-term ZIP/data archive.
5. **Google Sheets** — readable/searchable index of files/snapshots.
6. **Excel/CSV/ZIP** — downloadable portable exports.

## Why the full database is not put directly in Google Sheets
Long price histories, all NSE instruments, MF histories, recommendation snapshots and validation output become too large for a practical spreadsheet. Raw/high-volume data remains CSV/CSV.GZ/Parquet/ZIP; Sheets is the index/reference surface.

## PC mode — recommended easiest setup
Use Google Drive for Desktop. Set the synced local Drive folder in Radar → System → Sync Center. Radar writes archives into an `India Investment Radar` folder and Google Drive Desktop handles synchronization.

## Cloud/API mode
Use a Google service account + private Render environment secret. Share only the specific archive folder/Sheet with that account. The secret is not stored in GitHub or inside exported Radar archives.

## Automatic options
Both are OFF until you enable them:
- Auto-refresh Google Sheet/CSV Data Index after Daily Update.
- Auto-create/upload a complete data ZIP after Daily Update.

Full ZIPs may become large, so enabling a full archive every day can consume storage. The dated local/Supabase snapshot system remains available independently.
