from __future__ import annotations
from pathlib import Path
from datetime import datetime
import pandas as pd
import numpy as np

BASE=Path(__file__).resolve().parent
DATA=BASE/'data'

def _age_hours(path: Path):
    try:return max(0.0,(datetime.now().timestamp()-path.stat().st_mtime)/3600)
    except Exception:return np.nan

def _fmt_age(h):
    if pd.isna(h):return '—'
    if h<1:return f'{h*60:.0f} min'
    if h<48:return f'{h:.1f} h'
    return f'{h/24:.1f} d'

def _status(age_h,fresh_h=36,warn_h=96,exists=True):
    if not exists:return 'MISSING'
    if pd.isna(age_h):return 'UNKNOWN'
    if age_h<=fresh_h:return 'FRESH'
    if age_h<=warn_h:return 'STALE'
    return 'OLD'

def _row(name,path=None,source='',trust='VERIFIED',fresh_h=36,warn_h=96,fallback='',detail='',manual=False,status_override=None):
    p=Path(path) if path else None
    exists=bool(p and p.exists())
    age=_age_hours(p) if exists else np.nan
    st=status_override or ('MANUAL' if manual and exists else (_status(age,fresh_h,warn_h,exists) if p else ('MANUAL' if manual else 'UNKNOWN')))
    updated=''
    if exists:
        try:updated=datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec='minutes')
        except Exception:pass
    return {'Data':name,'Status':st,'LastUpdated':updated,'Age':_fmt_age(age),'Trust':trust,'Source':source,'Fallback':fallback,'Detail':detail}

def _newest(directory,pattern='*'):
    d=Path(directory)
    if not d.exists():return None
    fs=[p for p in d.glob(pattern) if p.is_file()]
    return max(fs,key=lambda p:p.stat().st_mtime) if fs else None

def build_data_health():
    rows=[]
    # NSE history is stored as daily CSV files under data/bhavcopy.
    nse_new=_newest(DATA/'bhavcopy','*.csv')
    rows.append(_row('NSE price history',nse_new,'NSE EOD/common files','OFFICIAL/VERIFIED',36,96,'Last valid local history','All-NSE technical engine'))
    # dashboard cache path may be a pickle/json depending on version; newest matching cache is enough for health view.
    dash=DATA/'dashboard_cache'/'meta.json' if (DATA/'dashboard_cache'/'meta.json').exists() else None
    rows.append(_row('Dashboard / rankings',dash,'Local calculated cache','CALCULATED',36,96,'Rebuild from local NSE history','Fast Start snapshot'))
    rows.append(_row('Corporate events',DATA/'corporate_events_all.csv','NSE corporate filings/event APIs','OFFICIAL',36,96,'Last valid event cache','Actions, board meetings, results, announcements, event calendar'))
    rows.append(_row('Corporate announcements',DATA/'corporate_announcements.csv','NSE announcements','OFFICIAL',36,96,'Last valid announcement cache','News/results safety gate'))
    rows.append(_row('Mutual Fund universe / NAV',DATA/'mf_universe.csv','AMFI Complete NAV; MFAPI fallback','OFFICIAL/FALLBACK',36,96,'Last valid AMFI/MFAPI cache','All active published-NAV scheme/plan rows'))
    rows.append(_row('MF deep histories',_newest(DATA/'mf_histories','*.json'),'MFAPI historical NAV','VERIFIED',168,720,'Use existing cached histories','Downloaded only for exact/ranked funds'))
    rows.append(_row('Crypto prices',DATA/'crypto'/'meta.json','Public crypto market endpoint','MARKET',12,36,'Last valid crypto cache','24/7 assets'))
    rows.append(_row('Macro context',DATA/'macro'/'meta.json','Yahoo market series','MARKET PROXY',36,96,'Last valid macro cache','Nifty, Bank Nifty, USD/INR, crude, Gold/Silver, US indices'))
    rows.append(_row('Physical Gold/Silver auto reference',DATA/'physical_metals_auto.json','Global bullion × USD/INR conversion','INDICATIVE',36,96,'Last valid auto reference or manual dealer override','Local dealer premium/tax/adjustment remains configurable'))
    rows.append(_row('IPO / new issues',DATA/'ipo_watchlist.csv','NSE current issues + verified manual/import fields','OFFICIAL/MANUAL',36,120,'Last valid IPO cache','GMP remains unofficial low-weight if entered'))
    rows.append(_row('Auto fundamentals',DATA/'alpha_fundamentals.csv','Alpha Vantage optional cache','THIRD-PARTY',720,1440,'Seed fundamentals / lower confidence','Optional; long-term confidence is capped when stale/missing'))
    rows.append(_row('Backtest',DATA/'backtest_stats.csv','Local historical calculation','CALCULATED',720,2160,'Existing validation','One-time / periodic rebuild'))
    rows.append(_row('Walk-forward validation',DATA/'walk_forward_stats.csv','Local historical walk-forward','CALCULATED',720,2160,'Existing validation','Stricter validation gate'))
    rows.append(_row('Portfolio',DATA/'my_portfolio.csv','User lots + automatic current prices','USER/CALCULATED',720,4320,'Manual current price for unsupported assets','Purchase-lot source of truth'))
    optfile=DATA/'investment_options.csv';opt_status='MISSING';opt_detail='Master investment options file is missing.'
    if optfile.exists():
        try:
            od=pd.read_csv(optfile);rates=pd.to_numeric(od.get('RateOrExpectedReturn%'),errors='coerce');active=od.get('ActiveStatus',pd.Series(['ACTIVE']*len(od))).astype(str).str.upper().isin(['ACTIVE','NEW INVESTMENT ALLOWED',''])
            valid=int((rates.notna()&active).sum());total=int(active.sum());opt_status='MANUAL' if total and valid>=max(5,int(total*.50)) else 'PARTIAL';opt_detail=f'{valid}/{total} active master-universe rows have a current rate/return input. Missing-rate products remain REVIEW/INPUT REQUIRED rather than fabricated.'
        except Exception:opt_status='PARTIAL';opt_detail='Master universe exists but current-rate completeness could not be verified.'
    rows.append(_row('Government/other investment rates',optfile,'Official/current quote entered or updated','MANUAL/VERIFIED',2160,4320,'Manual official-rate update',manual=True,status_override=opt_status,detail=opt_detail))
    # fixed-income actual filename can differ; find newest matching csv
    fixed=_newest(DATA,'*fixed*income*.csv') or _newest(DATA,'*bond*.csv');fixed_status=None;fixed_detail='Government/bond yield automation remains source-dependent'
    if fixed and fixed.exists():
        try:
            fd=pd.read_csv(fixed);y=pd.to_numeric(fd.get('Yield%'),errors='coerce');fixed_status='MANUAL' if y.notna().any() else 'PARTIAL';fixed_detail=f'{int(y.notna().sum())}/{len(fd)} fixed-income rows have a verified current Yield/YTM.'
        except Exception:fixed_status='PARTIAL'
    rows.append(_row('Fixed-income yields',fixed,'Current YTM entered/verified','MANUAL/VERIFIED',168,720,'Manual verified quote',manual=True,status_override=fixed_status,detail=fixed_detail))
    df=pd.DataFrame(rows)
    score_map={'FRESH':100,'MANUAL':85,'PARTIAL':55,'STALE':60,'OLD':35,'MISSING':0,'UNKNOWN':25}
    score=float(df.Status.map(score_map).fillna(25).mean()) if not df.empty else 0.0
    return df,round(score,1)

def action_needed(df):
    if df is None or df.empty:return pd.DataFrame()
    return df[df.Status.isin(['MISSING','STALE','OLD','PARTIAL'])].copy()
