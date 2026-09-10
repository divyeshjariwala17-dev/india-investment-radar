from __future__ import annotations
from pathlib import Path
from io import BytesIO
from datetime import datetime
import hashlib, json, zipfile
import pandas as pd

BASE=Path(__file__).resolve().parent
DATA=BASE/'data'
EXCLUDE_NAMES={'.env','local_secrets.json','alpha_key.txt'}
EXCLUDE_PARTS={'__pycache__','.git','.venv','venv'}

def inventory(data_dir:Path|None=None):
    root=data_dir or DATA;rows=[]
    if not root.exists():return pd.DataFrame(columns=['Path','Bytes','Modified','SHA256'])
    for p in root.rglob('*'):
        if not p.is_file() or p.name in EXCLUDE_NAMES or any(x in EXCLUDE_PARTS for x in p.parts):continue
        try:
            h=hashlib.sha256(p.read_bytes()).hexdigest()[:16]
            rows.append({'Path':str(p.relative_to(root)).replace('\\','/'),'Bytes':p.stat().st_size,'Modified':datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec='seconds'),'SHA256':h})
        except Exception:pass
    return pd.DataFrame(rows).sort_values('Path') if rows else pd.DataFrame(columns=['Path','Bytes','Modified','SHA256'])

def stock_excel(symbol,history,radar,events=None,announcements=None,public_news=None):
    sym=str(symbol).upper();bio=BytesIO()
    with pd.ExcelWriter(bio,engine='openpyxl') as w:
        h=history.copy() if history is not None else pd.DataFrame()
        if not h.empty and 'Symbol' in h.columns:h=h[h.Symbol.astype(str).str.upper().eq(sym)]
        h.to_excel(excel_writer=w,sheet_name='Price History',index=False)
        r=radar.copy() if radar is not None else pd.DataFrame()
        if not r.empty and 'Symbol' in r.columns:r=r[r.Symbol.astype(str).str.upper().eq(sym)]
        r.to_excel(excel_writer=w,sheet_name='Recommendations',index=False)
        for name,df in [('Corporate Events',events),('Announcements',announcements),('Public News',public_news)]:
            x=df.copy() if isinstance(df,pd.DataFrame) else pd.DataFrame()
            if not x.empty:
                col='Symbol' if 'Symbol' in x.columns else ('symbol' if 'symbol' in x.columns else None)
                if col:x=x[x[col].astype(str).str.upper().eq(sym)]
            x.to_excel(excel_writer=w,sheet_name=name[:31],index=False)
        pd.DataFrame([{'Symbol':sym,'GeneratedAt':pd.Timestamp.now().isoformat(timespec='seconds'),'Note':'Historical recommendations are preserved as stored; market outcomes are probabilistic.'}]).to_excel(excel_writer=w,sheet_name='Manifest',index=False)
    return bio.getvalue()

def category_excel(sheets:dict[str,pd.DataFrame]):
    bio=BytesIO()
    with pd.ExcelWriter(bio,engine='openpyxl') as w:
        for name,df in sheets.items():
            if isinstance(df,pd.DataFrame):df.to_excel(excel_writer=w,sheet_name=str(name)[:31],index=False)
    return bio.getvalue()

def complete_archive(data_dir:Path|None=None):
    root=data_dir or DATA;bio=BytesIO();manifest=[]
    with zipfile.ZipFile(bio,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in root.rglob('*') if root.exists() else []:
            if not p.is_file() or p.name in EXCLUDE_NAMES or any(x in EXCLUDE_PARTS for x in p.parts):continue
            rel=str(p.relative_to(root)).replace('\\','/')
            try:
                b=p.read_bytes();sha=hashlib.sha256(b).hexdigest();z.writestr('data/'+rel,b);manifest.append({'path':rel,'bytes':len(b),'sha256':sha})
            except Exception:pass
        z.writestr('MANIFEST.json',json.dumps({'created_at':pd.Timestamp.now().isoformat(timespec='seconds'),'files':manifest},indent=2))
    return bio.getvalue()
