from __future__ import annotations
from pathlib import Path
import socket, requests, pandas as pd
from nse_data import cache_status
from mutual_funds import analyze_cached, load_universe
from fixed_income import load as load_bonds
from crypto_data import meta as crypto_meta
from dashboard_cache import cache_exists
from backup_manager import latest_backup
from news_gate import load_announcements
from macro_intelligence import meta as macro_meta
from data_center import build_data_health
from market_intelligence import institutional_summary, derivatives_summary, breadth_summary, load_delivery, load_surveillance, market_context
from data_vault import snapshot_index
from cloud_sync import status as cloud_status, full_status as cloud_full_status
from google_archive import status as google_status

BASE=Path(__file__).resolve().parent

def run():
    rows=[]
    try:
        socket.create_connection(("1.1.1.1",53),timeout=3).close();rows.append(("Internet","PASS","Internet connection available"))
    except Exception as e:rows.append(("Internet","WARN","Offline/local mode available: "+str(e)))
    cs=cache_status();rows.append(("NSE local history","PASS" if cs["sessions"]>=90 else "FAIL",f'{cs["sessions"]} sessions; latest {cs["last"]}'))
    rows.append(("Fast dashboard cache","PASS" if cache_exists() else "WARN","Saved dashboard available" if cache_exists() else "Run DAILY UPDATE once to build fast cache"))
    try:
        r=requests.get("https://api.mfapi.in/mf/search",params={"q":"HDFC"},timeout=8);rows.append(("Mutual Fund public fallback","PASS" if r.ok else "WARN",f"HTTP {r.status_code}"))
    except Exception as e:rows.append(("Mutual Fund public fallback","WARN",str(e)))
    mf_cached=analyze_cached()[0];u=load_universe();rows.append(("Mutual Fund cache","PASS" if len(mf_cached)>0 or len(u)>0 else "WARN",f"{len(u)} universe rows; {len(mf_cached)} deep-analyzed funds"))
    cm=crypto_meta();rows.append(('Crypto cache','PASS' if cm.get('ok',0)>0 else 'WARN',f"{cm.get('ok',0)} crypto assets cached; updated {cm.get('updated_at','never')}"))
    mm=macro_meta();rows.append(('Macro / global context','PASS' if mm.get('ok',0)>=4 else 'WARN',f"{mm.get('ok',0)} macro series cached; updated {mm.get('updated_at','never')}"))
    inst=institutional_summary();rows.append(('FII/FPI + DII','PASS' if inst.get('LatestDate') else 'WARN',f"{inst.get('Bias','UNAVAILABLE')} • 20D FII {inst.get('FII20D₹Cr','—')} Cr • 60D FII {inst.get('FII60D₹Cr','—')} Cr"))
    der=derivatives_summary();rows.append(('F&O participant positioning','PASS' if der.get('LatestDate') else 'WARN',str(der.get('Explanation') or der.get('Bias','No verified cache yet'))[:300]))
    br=breadth_summary();rows.append(('Market breadth','PASS' if br.get('LatestDate') else 'WARN',f"{br.get('Bias','UNAVAILABLE')} • score {br.get('Score','—')}"))
    rows.append(('Security delivery','PASS' if not load_delivery().empty else 'WARN',f"{len(load_delivery())} cached rows"))
    rows.append(('Surveillance','PASS' if not load_surveillance().empty else 'WARN',f"{len(load_surveillance())} cached rows; missing optional feed never fabricates a flag"))
    ctx=market_context();rows.append(('Market Intelligence engine','PASS' if ctx.get('DataCompleteness%',0)>=45 else 'WARN',f"{ctx.get('Regime','UNAVAILABLE')} • score {ctx.get('Score',0):.0f}/100 • completeness {ctx.get('DataCompleteness%',0):.0f}%"))
    pf=BASE/'data'/'my_portfolio.csv'
    if pf.exists():
        try:pc=len(pd.read_csv(pf));rows.append(('My Portfolio','PASS',f'{pc} saved purchase lots'))
        except Exception as e:rows.append(('My Portfolio','WARN',str(e)))
    else:rows.append(('My Portfolio','WARN','No saved investments yet'))
    plans=BASE/'data'/'allocation_plans.csv';rows.append(('Tracked money plans','PASS' if plans.exists() else 'WARN','Saved plans available' if plans.exists() else 'No optimizer plan tracked yet'))
    ipo=BASE/'data'/'ipo_watchlist.csv';rows.append(('IPO data','PASS' if ipo.exists() else 'WARN','Saved IPO/new-issue data available' if ipo.exists() else 'Run DAILY UPDATE or add verified IPO data'))
    try:b=load_bonds();rows.append(("Fixed Income list","PASS",f"{len(b)} instruments"))
    except Exception as e:rows.append(("Fixed Income list","FAIL",str(e)))
    for name,file in [("Backtest",BASE/"data"/"backtest_stats.csv"),("Walk-forward",BASE/"data"/"walk_forward_stats.csv")]:
        rows.append((name,"PASS" if file.exists() else "WARN","Ready" if file.exists() else f"Build {name.lower()} once for stronger confidence"))
    ann=load_announcements();rows.append(("Official announcement safety gate","PASS" if not ann.empty else "WARN",f"{len(ann)} NSE announcements cached" if not ann.empty else "Run DAILY UPDATE; Strong Buy is capped when the official gate is unavailable"))
    try:
        dh,score=build_data_health();rows.append(("Auto Data Center","PASS" if score>=70 else "WARN",f"Overall data-health score {score:.0f}%"))
    except Exception as e:rows.append(("Auto Data Center","WARN",str(e)))
    si=snapshot_index();rows.append(('Dated Data Vault','PASS' if not si.empty else 'WARN',f'{len(si)} dated snapshots' if not si.empty else 'First successful recommendation rebuild creates a dated snapshot'))
    csx=cloud_status();rows.append(('Supabase sync','PASS' if csx.get('enabled') else 'WARN',csx.get('message','Not configured; local PC mode still works')))
    gs=google_status();rows.append(('Google archive/index','PASS' if gs.get('configured') else 'OPTIONAL',gs.get('message','Optional archive not configured')))
    lb=latest_backup();rows.append(("Local backup","PASS" if lb else "WARN",lb.name if lb else "Backup is created after DAILY UPDATE"))
    return pd.DataFrame(rows,columns=["Check","Status","Detail"])
