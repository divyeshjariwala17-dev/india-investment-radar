from __future__ import annotations
from pathlib import Path
from datetime import datetime
from io import BytesIO
import hashlib, json, mimetypes, os, re, zipfile
import requests
try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv=None

BASE=Path(__file__).resolve().parent
if load_dotenv:
    try: load_dotenv(BASE/'.env', override=False)
    except Exception: pass

_PULLED=False
_LAST_HASHES={}
_LAST_STATUS={'enabled':False,'message':'Cloud persistence not configured'}
_FULL_STATUS={'enabled':False,'message':'Full-data cloud sync not checked'}
_REMOTE_MANIFEST=None

# Small/important user state. These are synced individually so changes are cheap.
PERSIST_FILES=[
    'my_portfolio.csv','investment_goals.csv','portfolio_goals.csv','allocation_plans.csv','recommendation_history.csv',
    'ui_settings.json','source_registry.csv','source_runtime.json','fixed_income_watchlist.csv',
    'investment_options.csv','ipo_watchlist.csv','physical_metals_state.json','fd_rates.csv','small_savings_rates.csv',
    'alerts.csv','cloud_sync_status.json'
]

# Downloadable/calculated data needed to make the whole Radar useful immediately after a
# Render restart/redeploy. It is packed into small ZIP parts and stored under the SAME private
# Supabase bucket. No API key or secret is ever written into these packs.
CORE_FLAT_FILES=[
    'corporate_events_all.csv','corporate_actions.csv','corporate_announcements.csv','mf_universe.csv','mf_cache.json',
    'physical_metals_auto.json','alpha_fundamentals.csv','backtest_stats.csv','walk_forward_stats.csv',
    'cross_asset_opportunities.csv','cross_asset_history.csv'
]
CORE_DIRS=['dashboard_cache','mf_histories','crypto','macro','market_intelligence']
PACK_TARGET_UNCOMPRESSED=18*1024*1024  # comfortably below Supabase Free 50 MB/file limit
FULL_PREFIX='radar/full_data'
MANIFEST_REMOTE=f'{FULL_PREFIX}/manifest.json'


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
    key=(_secret('SUPABASE_SECRET_KEY') or _secret('SUPABASE_SERVICE_ROLE_KEY') or _secret('SUPABASE_KEY'))
    bucket=_secret('SUPABASE_BUCKET','radar-private')
    enabled=bool(url and key and bucket)
    return {'enabled':enabled,'url':url,'key':key,'bucket':bucket}


def _headers(content_type:str|None=None):
    c=config();key=c['key']
    h={'apikey':key}
    # Legacy service_role JWT still requires Bearer. New sb_secret_ keys must be apikey-only.
    if key and not key.startswith('sb_'):
        h['Authorization']=f'Bearer {key}'
    if content_type:h['Content-Type']=content_type
    return h


def _hash_bytes(data:bytes)->str:
    return hashlib.sha256(data).hexdigest()


def _hash_file(p:Path)->str:
    if not p.exists() or not p.is_file():return ''
    h=hashlib.sha256()
    try:
        with p.open('rb') as f:
            for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
        return h.hexdigest()
    except Exception:return ''


def _remote_url(rel:str):
    c=config();safe=rel.replace(os.sep,'/')
    return f"{c['url']}/storage/v1/object/{c['bucket']}/{safe}"


def _download(rel:str,timeout=60):
    try:
        r=requests.get(_remote_url(rel),headers=_headers(),timeout=timeout)
        if r.status_code==200:return r.content
        if r.status_code in (400,404):return None
        return None
    except Exception:return None


def _upload(rel:str,data:bytes,timeout=120):
    ctype=mimetypes.guess_type(rel)[0] or 'application/octet-stream'
    h=_headers(ctype);h['x-upsert']='true'
    try:
        r=requests.post(_remote_url(rel),headers=h,data=data,timeout=timeout)
        return r.status_code in (200,201)
    except Exception:return False


def _delete(rel:str,timeout=30):
    try:
        r=requests.delete(_remote_url(rel),headers=_headers(),timeout=timeout)
        return r.status_code in (200,204,404)
    except Exception:return False


def test_connection():
    c=config()
    if not c['enabled']:return {'ok':False,'message':'Supabase settings are not configured.'}
    try:
        url=f"{c['url']}/storage/v1/bucket/{c['bucket']}"
        r=requests.get(url,headers=_headers(),timeout=20)
        if r.status_code==200:return {'ok':True,'message':f"Connected to private bucket {c['bucket']}"}
        return {'ok':False,'message':f'Supabase bucket check returned HTTP {r.status_code}. Confirm URL, secret key and bucket name.'}
    except Exception as e:return {'ok':False,'message':f'Supabase connection failed: {e}'}


def _iter_personal_paths(data_dir:Path):
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
    for rel,p in _iter_personal_paths(data_dir):
        b=_download(f'radar/personal/{rel}')
        # Backward compatibility with 7.0.x path.
        if b is None:b=_download(f'radar/{rel}')
        if b is not None:
            p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b);ok+=1
    _LAST_HASHES={rel:_hash_file(p) for rel,p in _iter_personal_paths(data_dir)}
    _LAST_STATUS={'enabled':True,'message':f'Cloud persistence connected ({ok} personal file(s) restored)'}
    return _LAST_STATUS


def push_changed(data_dir:Path):
    global _LAST_HASHES,_LAST_STATUS
    c=config()
    if not c['enabled']:return {'enabled':False,'uploaded':0,'failed':0,'message':'Cloud persistence not configured'}
    uploaded=failed=0
    for rel,p in _iter_personal_paths(data_dir):
        if not p.exists() or not p.is_file():continue
        h=_hash_file(p)
        if h and _LAST_HASHES.get(rel)!=h:
            if _upload(f'radar/personal/{rel}',p.read_bytes()):
                _LAST_HASHES[rel]=h;uploaded+=1
            else:failed+=1
    _LAST_STATUS={'enabled':True,'uploaded':uploaded,'failed':failed,'message':f'Cloud personal save: {uploaded} changed file(s), {failed} failed'}
    return _LAST_STATUS


def _core_files(data_dir:Path):
    files=[]
    for rel in CORE_FLAT_FILES:
        p=data_dir/rel
        if p.exists() and p.is_file():files.append(p)
    for dname in CORE_DIRS:
        d=data_dir/dname
        if d.exists():files.extend([p for p in d.rglob('*') if p.is_file() and '.cloudpack' not in p.parts])
    # NSE EOD history is deliberately included because the cloud host's filesystem is ephemeral.
    bh=data_dir/'bhavcopy'
    if bh.exists():files.extend([p for p in bh.glob('*.csv') if p.is_file()])
    return sorted(set(files),key=lambda p:str(p.relative_to(data_dir)).lower())


def _group_key(data_dir:Path,p:Path):
    rel=p.relative_to(data_dir)
    top=rel.parts[0] if rel.parts else 'core'
    if top=='bhavcopy':
        m=re.match(r'(\d{4})-(\d{2})-',p.name)
        return f'bhavcopy_{m.group(1)}_{m.group(2)}' if m else 'bhavcopy_misc'
    if top in CORE_DIRS:return top
    return 'core_flat'


def _group_chunks(data_dir:Path):
    grouped={}
    for p in _core_files(data_dir):grouped.setdefault(_group_key(data_dir,p),[]).append(p)
    chunks=[]
    for g,files in sorted(grouped.items()):
        cur=[];total=0;part=1
        for p in files:
            sz=max(1,p.stat().st_size)
            if cur and total+sz>PACK_TARGET_UNCOMPRESSED:
                chunks.append((f'{g}_part{part:02d}',cur));part+=1;cur=[];total=0
            cur.append(p);total+=sz
        if cur:chunks.append((f'{g}_part{part:02d}',cur))
    return chunks


def _source_fingerprint(data_dir:Path,files:list[Path]):
    h=hashlib.sha256()
    for p in files:
        rel=str(p.relative_to(data_dir)).replace(os.sep,'/').encode('utf-8')
        st=p.stat();h.update(rel);h.update(str(st.st_size).encode());h.update(str(st.st_mtime_ns).encode())
    return h.hexdigest()


def _pack_bytes(data_dir:Path,files:list[Path]):
    bio=BytesIO()
    with zipfile.ZipFile(bio,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in files:z.write(p,str(p.relative_to(data_dir)).replace(os.sep,'/'))
    return bio.getvalue()


def _remote_manifest():
    global _REMOTE_MANIFEST
    b=_download(MANIFEST_REMOTE)
    if not b:return None
    try:
        _REMOTE_MANIFEST=json.loads(b.decode('utf-8'));return _REMOTE_MANIFEST
    except Exception:return None


def _local_readiness(data_dir:Path,min_sessions=90):
    sessions=len(list((data_dir/'bhavcopy').glob('*.csv'))) if (data_dir/'bhavcopy').exists() else 0
    cache=(data_dir/'dashboard_cache'/'meta.json').exists()
    mf=(data_dir/'mf_universe.csv').exists()
    return {'ready':sessions>=int(min_sessions) and cache,'sessions':sessions,'dashboard':cache,'mf_universe':mf}


def push_full_data(data_dir:Path,status_cb=None):
    """Persist all downloaded/calculated core datasets to private Supabase Storage.
    Packs are small and only changed packs are uploaded. The manifest is written last.
    """
    global _FULL_STATUS,_REMOTE_MANIFEST
    c=config()
    if not c['enabled']:
        return {'enabled':False,'ok':False,'message':'Cloud persistence not configured','uploaded_packs':0,'skipped_packs':0,'failed_packs':0}
    remote=_remote_manifest() or {}
    remote_by={x.get('name'):x for x in remote.get('packs',[]) if isinstance(x,dict)}
    packs=[];uploaded=skipped=failed=0
    chunks=_group_chunks(data_dir)
    for i,(group,files) in enumerate(chunks,1):
        source_fp=_source_fingerprint(data_dir,files)
        name=f'{group}.zip';old=remote_by.get(name,{})
        if status_cb:status_cb(f'Cloud data pack {i}/{len(chunks)}: {group}')
        if old.get('source_fingerprint')==source_fp and old.get('sha256'):
            packs.append(old);skipped+=1;continue
        data=_pack_bytes(data_dir,files)
        if len(data)>48*1024*1024:
            failed+=1;continue
        sha=_hash_bytes(data)
        ok=_upload(f'{FULL_PREFIX}/packs/{name}',data,timeout=180)
        if ok:
            uploaded+=1
            packs.append({'name':name,'sha256':sha,'bytes':len(data),'files':len(files),'source_fingerprint':source_fp})
        else:failed+=1
    ready=_local_readiness(data_dir,90)
    manifest={
        'schema':2,'created_at':datetime.now().isoformat(timespec='seconds'),'packs':packs,
        'nse_sessions':ready['sessions'],'dashboard':ready['dashboard'],'mf_universe':ready['mf_universe']
    }
    manifest_bytes=json.dumps(manifest,indent=2).encode('utf-8')
    manifest_ok=(failed==0 and _upload(MANIFEST_REMOTE,manifest_bytes,timeout=60))
    deleted=0
    if manifest_ok:
        _REMOTE_MANIFEST=manifest
        current_names={x.get('name') for x in packs}
        # After the new manifest is safely written, remove obsolete rolling-history packs
        # so the free 1 GB bucket does not grow forever.
        for old_name in set(remote_by)-current_names:
            if old_name and _delete(f'{FULL_PREFIX}/packs/{old_name}'):
                deleted+=1
    msg=(f'Full cloud data sync: {uploaded} pack(s) uploaded, {skipped} unchanged, {failed} failed, {deleted} obsolete removed; '
         f"NSE sessions {ready['sessions']}.")
    _FULL_STATUS={'enabled':True,'ok':bool(manifest_ok),'message':msg,'uploaded_packs':uploaded,'skipped_packs':skipped,'failed_packs':failed,'deleted_packs':deleted,'nse_sessions':ready['sessions']}
    _write_status(data_dir,_FULL_STATUS)
    return _FULL_STATUS


def pull_full_data(data_dir:Path,force=False,status_cb=None,min_sessions=90):
    """Restore verified full market/calculation packs from private Supabase Storage.
    Downloads are verified before extraction, so a partial/corrupt cloud download is not trusted.
    """
    global _FULL_STATUS,_REMOTE_MANIFEST
    c=config()
    if not c['enabled']:
        return {'enabled':False,'ok':False,'message':'Cloud persistence not configured','restored_packs':0}
    local=_local_readiness(data_dir,min_sessions)
    if local['ready'] and not force:
        _FULL_STATUS={'enabled':True,'ok':True,'message':f"Local full data already ready ({local['sessions']} NSE sessions); cloud restore not needed.",'restored_packs':0,'nse_sessions':local['sessions']}
        return _FULL_STATUS
    man=_remote_manifest()
    if not man or not man.get('packs'):
        _FULL_STATUS={'enabled':True,'ok':False,'message':'No full-data cloud snapshot exists yet. Build Full Data once, then sync it to cloud.','restored_packs':0}
        return _FULL_STATUS
    downloads=[];fails=[]
    for i,item in enumerate(man.get('packs',[]),1):
        name=item.get('name','')
        if status_cb:status_cb(f'Restoring cloud data pack {i}/{len(man.get("packs",[]))}: {name}')
        b=_download(f'{FULL_PREFIX}/packs/{name}',timeout=180)
        if not b or _hash_bytes(b)!=item.get('sha256'):
            fails.append(name);continue
        downloads.append((name,b))
    if fails:
        _FULL_STATUS={'enabled':True,'ok':False,'message':f'Cloud full-data restore stopped: {len(fails)} pack(s) missing/corrupt. Existing local data was preserved.','restored_packs':0,'failed':fails[:10]}
        return _FULL_STATUS
    restored=0
    data_dir.mkdir(parents=True,exist_ok=True)
    for name,b in downloads:
        try:
            with zipfile.ZipFile(BytesIO(b),'r') as z:z.extractall(data_dir)
            restored+=1
        except Exception as e:
            _FULL_STATUS={'enabled':True,'ok':False,'message':f'Cloud pack {name} could not be extracted: {e}','restored_packs':restored}
            return _FULL_STATUS
    ready=_local_readiness(data_dir,min_sessions)
    ok=bool(ready['ready'])
    msg=(f"Full cloud data restored: {restored} pack(s), {ready['sessions']} NSE sessions."
         if ok else f"Cloud packs restored but core readiness is incomplete ({ready['sessions']} NSE sessions). Run Full Data Setup/Repair.")
    _FULL_STATUS={'enabled':True,'ok':ok,'message':msg,'restored_packs':restored,'nse_sessions':ready['sessions']}
    _write_status(data_dir,_FULL_STATUS)
    return _FULL_STATUS


def pull_full_if_needed(data_dir:Path,min_sessions=90,status_cb=None):
    return pull_full_data(data_dir,force=False,status_cb=status_cb,min_sessions=min_sessions)


def _write_status(data_dir:Path,status:dict):
    try:
        safe={k:v for k,v in status.items() if k not in ('key','secret')}
        (data_dir/'cloud_sync_status.json').write_text(json.dumps(safe,indent=2,default=str),encoding='utf-8')
    except Exception:pass


def full_status(data_dir:Path|None=None):
    out=dict(_FULL_STATUS)
    if data_dir is not None:
        out.update({f'local_{k}':v for k,v in _local_readiness(data_dir,90).items()})
    return out


def status():
    c=config();return {'enabled':c['enabled'],'bucket':c.get('bucket',''),'message':_LAST_STATUS.get('message',''),'full_message':_FULL_STATUS.get('message','')}
