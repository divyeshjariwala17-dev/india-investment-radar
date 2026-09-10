from __future__ import annotations

from pathlib import Path
from io import BytesIO
from datetime import datetime
import json
import os
import shutil

import pandas as pd

BASE=Path(__file__).resolve().parent
DATA=BASE/'data';DATA.mkdir(parents=True,exist_ok=True)
SETTINGS=DATA/'google_archive_settings.json'
INDEX_LOCAL=DATA/'Google_Sheet_Data_Index.csv'

DEFAULT={
    'local_drive_folder':'',
    'drive_folder_id':'',
    'sheet_id':'',
    'service_account_file':'',
    'share_email':'',
    'auto_archive_after_update':False,
    'auto_update_sheet_index':False,
}


def _load():
    d=dict(DEFAULT)
    if SETTINGS.exists():
        try:d.update(json.loads(SETTINGS.read_text(encoding='utf-8')))
        except Exception:pass
    # Environment variables override local non-secret settings on Render/other hosts.
    envmap={
        'GOOGLE_DRIVE_FOLDER_ID':'drive_folder_id','GOOGLE_SHEET_ID':'sheet_id',
        'GOOGLE_SERVICE_ACCOUNT_FILE':'service_account_file','GOOGLE_SHARE_EMAIL':'share_email',
        'GOOGLE_LOCAL_DRIVE_FOLDER':'local_drive_folder'
    }
    for e,k in envmap.items():
        if os.getenv(e):d[k]=os.getenv(e)
    return d


def save_settings(settings:dict):
    d=_load()
    for k in DEFAULT:
        if k in settings:d[k]=settings[k]
    # Do not store a JSON secret blob here; only a local file path can be stored.
    SETTINGS.write_text(json.dumps(d,indent=2),encoding='utf-8')
    return d


def _service_account_info():
    raw=os.getenv('GOOGLE_SERVICE_ACCOUNT_JSON','').strip()
    if raw:
        try:return json.loads(raw)
        except Exception:return None
    return None


def _credentials():
    try:
        from google.oauth2 import service_account
    except Exception as e:
        raise RuntimeError('Google API packages are not installed. Run Repair/Update or install requirements_google.txt.') from e
    scopes=['https://www.googleapis.com/auth/drive','https://www.googleapis.com/auth/spreadsheets']
    info=_service_account_info()
    if info:
        return service_account.Credentials.from_service_account_info(info,scopes=scopes)
    cfg=_load();f=str(cfg.get('service_account_file','')).strip()
    if f and Path(f).expanduser().exists():
        return service_account.Credentials.from_service_account_file(str(Path(f).expanduser()),scopes=scopes)
    raise RuntimeError('Google service account is not configured. Use Google Drive Desktop folder mode, or configure a service-account JSON file/Render secret.')


def _services():
    from googleapiclient.discovery import build
    c=_credentials()
    return build('drive','v3',credentials=c,cache_discovery=False),build('sheets','v4',credentials=c,cache_discovery=False)


def status():
    cfg=_load();local=str(cfg.get('local_drive_folder','')).strip();api=False;detail=[]
    if local:
        p=Path(local).expanduser();detail.append('Google Drive Desktop folder configured' if p.exists() else 'Google Drive Desktop path configured but not found')
    try:
        if _service_account_info() or (cfg.get('service_account_file') and Path(str(cfg.get('service_account_file'))).expanduser().exists()):
            api=True;detail.append('Google API credentials configured')
    except Exception:pass
    return {
        'configured':bool(local or api),'local_mode':bool(local),'api_mode':api,
        'local_folder':local,'drive_folder_id':cfg.get('drive_folder_id',''),'sheet_id':cfg.get('sheet_id',''),
        'auto_archive_after_update':bool(cfg.get('auto_archive_after_update',False)),
        'auto_update_sheet_index':bool(cfg.get('auto_update_sheet_index',False)),
        'message':' • '.join(detail) if detail else 'Google archive is optional and not configured yet.'
    }


def test_connection():
    cfg=_load();local=str(cfg.get('local_drive_folder','')).strip()
    if local:
        p=Path(local).expanduser()
        try:
            p.mkdir(parents=True,exist_ok=True)
            t=p/'.iir_write_test';t.write_text('ok',encoding='utf-8');t.unlink(missing_ok=True)
            return {'ok':True,'mode':'LOCAL DRIVE DESKTOP','message':f'Writable Google Drive synced folder: {p}'}
        except Exception as e:
            return {'ok':False,'mode':'LOCAL DRIVE DESKTOP','message':f'Google Drive folder is not writable: {e}'}
    try:
        drive,_=_services();fid=str(cfg.get('drive_folder_id','')).strip()
        if fid:
            item=drive.files().get(fileId=fid,fields='id,name,mimeType').execute()
            return {'ok':True,'mode':'GOOGLE API','message':f"Connected to Drive folder: {item.get('name',fid)}"}
        drive.files().list(pageSize=1,fields='files(id,name)').execute()
        return {'ok':True,'mode':'GOOGLE API','message':'Google API credentials work. Configure a Drive folder ID for archives.'}
    except Exception as e:
        return {'ok':False,'mode':'NOT CONFIGURED','message':str(e)}


def _local_archive_path(filename:str):
    cfg=_load();root=str(cfg.get('local_drive_folder','')).strip()
    if not root:return None
    p=Path(root).expanduser()/'India Investment Radar'/'Archive'/datetime.now().strftime('%Y/%m')
    p.mkdir(parents=True,exist_ok=True)
    return p/filename


def archive_bytes(filename:str,data:bytes,mime='application/octet-stream'):
    cfg=_load()
    # Prefer local Drive Desktop on PC because it requires no API secret and Google syncs it normally.
    lp=_local_archive_path(filename)
    if lp is not None:
        try:
            lp.write_bytes(data)
            return {'ok':True,'mode':'LOCAL DRIVE DESKTOP','id':str(lp),'message':f'Archived to Google Drive synced folder: {lp}'}
        except Exception as e:
            local_error=str(e)
    else:local_error=''
    try:
        drive,_=_services();folder=str(cfg.get('drive_folder_id','')).strip()
        if not folder:raise RuntimeError('GOOGLE_DRIVE_FOLDER_ID is not configured')
        from googleapiclient.http import MediaIoBaseUpload
        body={'name':filename,'parents':[folder]}
        media=MediaIoBaseUpload(BytesIO(data),mimetype=mime,resumable=True)
        f=drive.files().create(body=body,media_body=media,fields='id,name,webViewLink').execute()
        return {'ok':True,'mode':'GOOGLE API','id':f.get('id',''),'url':f.get('webViewLink',''),'message':f"Archived to Google Drive: {f.get('name',filename)}"}
    except Exception as e:
        msg=str(e)
        if local_error:msg='Local Drive failed: '+local_error+' | API failed: '+msg
        return {'ok':False,'mode':'UNAVAILABLE','message':msg}


def archive_file(path:Path):
    path=Path(path)
    if not path.exists():return {'ok':False,'message':f'File not found: {path}'}
    return archive_bytes(path.name,path.read_bytes())


def build_index(inventory:pd.DataFrame,snapshots:pd.DataFrame|None=None):
    rows=[]
    now=pd.Timestamp.now().isoformat(timespec='seconds')
    if inventory is not None and not inventory.empty:
        for _,r in inventory.iterrows():
            rows.append({'IndexType':'DATA FILE','Name':str(r.get('Path','')),'Date/Modified':str(r.get('Modified','')),'Bytes':r.get('Bytes',''),'SHA256':str(r.get('SHA256','')),'Status':'AVAILABLE','UpdatedAt':now})
    if snapshots is not None and not snapshots.empty:
        for _,r in snapshots.iterrows():
            rows.append({'IndexType':'DAILY SNAPSHOT','Name':str(r.get('Folder','')),'Date/Modified':str(r.get('Date','')),'Bytes':'','SHA256':'','Status':f"{r.get('Files',0)} files",'UpdatedAt':now})
    out=pd.DataFrame(rows)
    out.to_csv(INDEX_LOCAL,index=False)
    return out


def _ensure_sheet(sheets,drive,cfg):
    sid=str(cfg.get('sheet_id','')).strip()
    if sid:return sid
    body={'properties':{'title':'India Investment Radar Data Index'}}
    created=sheets.spreadsheets().create(body=body,fields='spreadsheetId').execute()
    sid=created['spreadsheetId']
    cfg=save_settings({'sheet_id':sid})
    share=str(cfg.get('share_email','')).strip()
    if share:
        try:drive.permissions().create(fileId=sid,body={'type':'user','role':'writer','emailAddress':share},sendNotificationEmail=True).execute()
        except Exception:pass
    return sid


def update_sheet_index(inventory:pd.DataFrame,snapshots:pd.DataFrame|None=None):
    idx=build_index(inventory,snapshots)
    cfg=_load()
    # In Drive Desktop mode, always write an easy-to-open CSV index in the synced folder.
    lp=_local_archive_path('India_Investment_Radar_Data_Index.csv')
    local_msg=''
    if lp is not None:
        try:
            idx.to_csv(lp,index=False);local_msg=f'Local synced index written: {lp}'
        except Exception as e:local_msg=f'Local index warning: {e}'
    try:
        drive,sheets=_services();sid=_ensure_sheet(sheets,drive,cfg)
        values=[list(idx.columns)]+idx.fillna('').astype(str).values.tolist() if not idx.empty else [['IndexType','Name','Date/Modified','Bytes','SHA256','Status','UpdatedAt']]
        sheets.spreadsheets().values().clear(spreadsheetId=sid,range='Data Index!A:Z',body={}).execute() if _sheet_exists(sheets,sid,'Data Index') else _add_sheet(sheets,sid,'Data Index')
        sheets.spreadsheets().values().update(spreadsheetId=sid,range='Data Index!A1',valueInputOption='RAW',body={'values':values}).execute()
        return {'ok':True,'mode':'GOOGLE SHEETS','sheet_id':sid,'rows':len(idx),'message':f'Google Sheet Data Index updated ({len(idx)} rows). '+local_msg}
    except Exception as e:
        if lp is not None and lp.exists():
            return {'ok':True,'mode':'LOCAL DRIVE DESKTOP','rows':len(idx),'message':local_msg+'; Google Sheets API not used: '+str(e)}
        return {'ok':False,'mode':'UNAVAILABLE','rows':len(idx),'message':'Google Sheet index unavailable: '+str(e)}


def _sheet_exists(sheets,sid,title):
    try:
        m=sheets.spreadsheets().get(spreadsheetId=sid,fields='sheets.properties').execute()
        return any(x.get('properties',{}).get('title')==title for x in m.get('sheets',[]))
    except Exception:return False


def _add_sheet(sheets,sid,title):
    try:sheets.spreadsheets().batchUpdate(spreadsheetId=sid,body={'requests':[{'addSheet':{'properties':{'title':title}}}]}).execute()
    except Exception:pass


def auto_after_update(archive_bytes_factory=None,inventory=None,snapshots=None):
    cfg=_load();results=[]
    if cfg.get('auto_update_sheet_index') and inventory is not None:
        results.append(update_sheet_index(inventory,snapshots))
    if cfg.get('auto_archive_after_update') and archive_bytes_factory is not None:
        try:
            data=archive_bytes_factory();name='India_Investment_Radar_Data_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'.zip'
            results.append(archive_bytes(name,data,'application/zip'))
        except Exception as e:results.append({'ok':False,'message':'Automatic Google archive failed: '+str(e)})
    return results
