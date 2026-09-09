from __future__ import annotations
from pathlib import Path
import hashlib, mimetypes, os
import requests

_PULLED=False
_LAST_HASHES={}
_LAST_STATUS={'enabled':False,'message':'Cloud persistence not configured'}

PERSIST_FILES=[
    'my_portfolio.csv','investment_goals.csv','allocation_plans.csv','recommendation_history.csv',
    'ui_settings.json','source_registry.csv','source_runtime.json','fixed_income_watchlist.csv',
    'investment_options.csv','ipo_watchlist.csv','physical_metals_state.json'
]


def _secret(name:str, default:str=''):
    v=os.getenv(name,'')
    if v:return v
    try:
        import streamlit as st
        if name in st.secrets:return str(st.secrets[name])
    except Exception:
        pass
    return default


def config():
    url=_secret('SUPABASE_URL').rstrip('/')
    # Prefer Supabase's current server-side Secret key (sb_secret_...).
    # Keep legacy names as fallback so existing deployments remain compatible.
    key=(
        _secret('SUPABASE_SECRET_KEY')
        or _secret('SUPABASE_SERVICE_ROLE_KEY')
        or _secret('SUPABASE_KEY')
    )
    bucket=_secret('SUPABASE_BUCKET','radar-private')
    enabled=bool(url and key and bucket)
    return {'enabled':enabled,'url':url,'key':key,'bucket':bucket}


def _headers(content_type:str|None=None):
    c=config();key=c['key']
    # Supabase's current sb_secret_/sb_publishable_ keys are API keys, not JWTs.
    # Send them in apikey only. Legacy service_role JWTs can also be sent as Bearer.
    h={'apikey':key}
    if key and not key.startswith('sb_'):
        h['Authorization']=f"Bearer {key}"
    if content_type:h['Content-Type']=content_type
    return h


def _hash(p:Path):
    if not p.exists() or not p.is_file():return ''
    try:return hashlib.sha256(p.read_bytes()).hexdigest()
    except Exception:return ''


def _remote_url(rel:str):
    c=config();return f"{c['url']}/storage/v1/object/{c['bucket']}/radar/{rel.replace(os.sep,'/')}"


def _download(rel:str):
    try:
        r=requests.get(_remote_url(rel),headers=_headers(),timeout=20)
        if r.status_code==200:return r.content
        if r.status_code in (400,404):return None
        return None
    except Exception:return None


def _upload(rel:str,data:bytes):
    ctype=mimetypes.guess_type(rel)[0] or 'application/octet-stream'
    h=_headers(ctype);h['x-upsert']='true'
    try:
        r=requests.post(_remote_url(rel),headers=h,data=data,timeout=30)
        return r.status_code in (200,201)
    except Exception:return False


def _iter_paths(data_dir:Path):
    for rel in PERSIST_FILES:
        yield rel,data_dir/rel
    assets=data_dir/'ui_assets'
    if assets.exists():
        for p in assets.glob('background.*'):
            if p.is_file():yield f'ui_assets/{p.name}',p


def pull_once(data_dir:Path):
    global _PULLED,_LAST_HASHES,_LAST_STATUS
    if _PULLED:return _LAST_STATUS
    _PULLED=True
    c=config()
    if not c['enabled']:
        _LAST_STATUS={'enabled':False,'message':'Cloud persistence not configured'}
        return _LAST_STATUS
    data_dir.mkdir(parents=True,exist_ok=True)
    ok=0
    for rel,p in _iter_paths(data_dir):
        b=_download(rel)
        if b is not None:
            p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b);ok+=1
    _LAST_HASHES={rel:_hash(p) for rel,p in _iter_paths(data_dir)}
    _LAST_STATUS={'enabled':True,'message':f'Cloud persistence connected ({ok} restored file(s))'}
    return _LAST_STATUS


def push_changed(data_dir:Path):
    global _LAST_HASHES,_LAST_STATUS
    c=config()
    if not c['enabled']:return {'enabled':False,'uploaded':0,'failed':0,'message':'Cloud persistence not configured'}
    uploaded=failed=0
    for rel,p in _iter_paths(data_dir):
        if not p.exists() or not p.is_file():continue
        h=_hash(p)
        if h and _LAST_HASHES.get(rel)!=h:
            if _upload(rel,p.read_bytes()):
                _LAST_HASHES[rel]=h;uploaded+=1
            else:failed+=1
    _LAST_STATUS={'enabled':True,'uploaded':uploaded,'failed':failed,'message':f'Cloud save: {uploaded} changed file(s), {failed} failed'}
    return _LAST_STATUS


def status():
    c=config();return {'enabled':c['enabled'],'bucket':c.get('bucket',''),'message':_LAST_STATUS.get('message','')}
