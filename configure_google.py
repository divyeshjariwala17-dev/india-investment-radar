from __future__ import annotations
from pathlib import Path
import sys
from google_archive import save_settings, test_connection, status

def main():
    print('\nINDIA INVESTMENT RADAR — GOOGLE ARCHIVE / DATA INDEX SETUP\n')
    print('Choose either PC Google Drive Desktop folder mode, or Google API service-account mode.')
    print('For PC mode, install Google Drive for Desktop first and enter the synced My Drive folder path.')
    print('For API/cloud mode, keep the service-account JSON in a private local path; NEVER commit it to GitHub.\n')
    cur=status()
    local=input(f"Google Drive Desktop synced root [{cur.get('local_folder','')}]: ").strip() or cur.get('local_folder','')
    drive_id=input(f"Google Drive folder ID (API mode) [{cur.get('drive_folder_id','')}]: ").strip() or cur.get('drive_folder_id','')
    sheet_id=input(f"Google Sheet ID (optional) [{cur.get('sheet_id','')}]: ").strip() or cur.get('sheet_id','')
    service_file=input('Private service-account JSON path (PC API mode; blank if not used): ').strip()
    share_email=input('Email to share an auto-created Sheet with (optional): ').strip()
    auto_idx=(input('Auto-update Google Sheet/CSV Data Index after Daily Update? [y/N]: ').strip().lower()=='y')
    auto_zip=(input('Auto-archive complete Data ZIP after Daily Update? [y/N]: ').strip().lower()=='y')
    vals={'local_drive_folder':local,'drive_folder_id':drive_id,'sheet_id':sheet_id,'auto_update_sheet_index':auto_idx,'auto_archive_after_update':auto_zip}
    if service_file:vals['service_account_file']=service_file
    if share_email:vals['share_email']=share_email
    save_settings(vals)
    print('\nSettings saved locally. Testing connection...')
    r=test_connection();print(('PASS: ' if r.get('ok') else 'WARNING: ')+str(r.get('message',r)))
    print('\nYou can change the same settings later inside Radar -> System -> Sync Center.')
    return 0 if r.get('ok') else 2

if __name__=='__main__':
    raise SystemExit(main())
