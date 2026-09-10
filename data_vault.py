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

# ---------------------------------------------------------------------------
# v7.3.0 dated snapshot archive
# ---------------------------------------------------------------------------
VAULT = DATA / 'vault' / 'daily'
VAULT.mkdir(parents=True, exist_ok=True)


def _write_table_compact(df: pd.DataFrame, path_base: Path):
    """Write Parquet when available, otherwise compressed CSV. Returns actual path."""
    if df is None:
        df = pd.DataFrame()
    path_base.parent.mkdir(parents=True, exist_ok=True)
    try:
        p = path_base.with_suffix('.parquet')
        df.to_parquet(p, index=False, compression='snappy')
        return p
    except Exception:
        p = path_base.with_suffix('.csv.gz')
        df.to_csv(p, index=False, compression='gzip')
        return p


def archive_daily_snapshot(data_date=None, radar=None, breadth=None, outlook=None, mf=None, bonds=None, ipos=None, market_context=None, extra_tables=None):
    """Preserve what the Radar actually knew/calculated on a date.

    This avoids look-ahead rewriting: later versions can inspect the stored dated snapshot rather
    than recomputing an old recommendation with today's inputs.
    """
    dt = pd.to_datetime(data_date or pd.Timestamp.now()).date()
    folder = VAULT / f'{dt:%Y}' / f'{dt:%m}'
    folder.mkdir(parents=True, exist_ok=True)
    written=[]
    tables={
        'stock_radar':radar if isinstance(radar,pd.DataFrame) else pd.DataFrame(),
        'market_outlook':outlook if isinstance(outlook,pd.DataFrame) else pd.DataFrame(),
        'mutual_funds':mf if isinstance(mf,pd.DataFrame) else pd.DataFrame(),
        'fixed_income':bonds if isinstance(bonds,pd.DataFrame) else pd.DataFrame(),
        'ipos':ipos if isinstance(ipos,pd.DataFrame) else pd.DataFrame(),
    }
    if isinstance(extra_tables,dict):
        for k,v in extra_tables.items():
            if isinstance(v,pd.DataFrame):tables[str(k)]=v
    for name,df in tables.items():
        if df is None or df.empty:continue
        x=df.copy()
        if 'SnapshotDate' not in x.columns:x['SnapshotDate']=dt.isoformat()
        p=_write_table_compact(x,folder/f'{name}_{dt:%Y%m%d}')
        written.append(str(p.relative_to(DATA)).replace('\\','/'))
    context_path=folder/f'market_context_{dt:%Y%m%d}.json'
    context_path.write_text(json.dumps({'SnapshotDate':dt.isoformat(),'MarketContext':market_context or {},'Breadth':breadth or {},'CreatedAt':pd.Timestamp.now().isoformat(timespec='seconds')},indent=2,default=str),encoding='utf-8')
    written.append(str(context_path.relative_to(DATA)).replace('\\','/'))
    manifest={
        'snapshot_date':dt.isoformat(),'created_at':pd.Timestamp.now().isoformat(timespec='seconds'),
        'files':written,'rule':'Stored values are the actual dated Radar state; do not rewrite old recommendations using future data.'
    }
    mp=folder/f'manifest_{dt:%Y%m%d}.json';mp.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    return {'ok':True,'date':dt.isoformat(),'files':len(written),'folder':str(folder)}


def snapshot_index():
    rows=[]
    if not VAULT.exists():return pd.DataFrame(columns=['Date','Files','Folder'])
    for mp in VAULT.rglob('manifest_*.json'):
        try:
            d=json.loads(mp.read_text(encoding='utf-8'))
            rows.append({'Date':d.get('snapshot_date',''),'Files':len(d.get('files',[])),'CreatedAt':d.get('created_at',''),'Folder':str(mp.parent.relative_to(DATA)).replace('\\','/')})
        except Exception:pass
    return pd.DataFrame(rows).sort_values('Date',ascending=False) if rows else pd.DataFrame(columns=['Date','Files','CreatedAt','Folder'])


def instrument_snapshot_history(symbol:str):
    sym=str(symbol).strip().upper();frames=[]
    if not sym or not VAULT.exists():return pd.DataFrame()
    for p in list(VAULT.rglob('stock_radar_*.parquet'))+list(VAULT.rglob('stock_radar_*.csv.gz')):
        try:
            d=pd.read_parquet(p) if p.suffix=='.parquet' else pd.read_csv(p)
            if 'Symbol' in d.columns:
                x=d[d.Symbol.astype(str).str.upper().eq(sym)].copy()
                if not x.empty:frames.append(x)
        except Exception:pass
    if not frames:return pd.DataFrame()
    out=pd.concat(frames,ignore_index=True,sort=False)
    sortcol='SnapshotDate' if 'SnapshotDate' in out.columns else ('DataDate' if 'DataDate' in out.columns else None)
    if sortcol:out=out.sort_values(sortcol)
    return out
