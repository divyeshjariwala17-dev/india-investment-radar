from __future__ import annotations
from pathlib import Path
import socket,requests,pandas as pd
from nse_data import cache_status
from mutual_funds import analyze_cached, load_universe
from fixed_income import load as load_bonds
from crypto_data import meta as crypto_meta
from dashboard_cache import cache_exists
from backup_manager import latest_backup
from news_gate import load_announcements
from macro_intelligence import meta as macro_meta
from data_center import build_data_health

BASE=Path(__file__).resolve().parent

def run():
    rows=[]
    try:
        socket.create_connection(("1.1.1.1",53),timeout=3).close();rows.append(("Internet","PASS","Internet connection available"))
    except Exception as e:rows.append(("Internet","FAIL",str(e)))
    cs=cache_status();rows.append(("NSE local history","PASS" if cs["sessions"]>=90 else "FAIL",f'{cs["sessions"]} sessions; latest {cs["last"]}'))
    rows.append(("Fast dashboard cache","PASS" if cache_exists() else "WARN","Saved dashboard available" if cache_exists() else "Run DAILY UPDATE once to build fast cache"))
    try:
        r=requests.get("https://api.mfapi.in/mf/search",params={"q":"HDFC"},timeout=8);rows.append(("Mutual Fund API","PASS" if r.ok else "FAIL",f"HTTP {r.status_code}"))
    except Exception as e:rows.append(("Mutual Fund API","FAIL",str(e)))
    mf_cached=analyze_cached()[0];u=load_universe();rows.append(("Mutual Fund cache","PASS" if len(mf_cached)>0 or len(u)>0 else "WARN",f"{len(u)} universe rows; {len(mf_cached)} deep-analyzed funds"))
    cm=crypto_meta();rows.append(('Crypto cache','PASS' if cm.get('ok',0)>0 else 'WARN',f"{cm.get('ok',0)} crypto assets cached; updated {cm.get('updated_at','never')}"))
    mm=macro_meta();rows.append(('Macro context','PASS' if mm.get('ok',0)>=4 else 'WARN',f"{mm.get('ok',0)} macro series cached; updated {mm.get('updated_at','never')}"))
    pf=BASE/'data'/'my_portfolio.csv'
    if pf.exists():
        try:
            pc=len(pd.read_csv(pf));rows.append(('My Portfolio','PASS',f'{pc} saved purchase lots'))
        except Exception as e:rows.append(('My Portfolio','WARN',str(e)))
    else:rows.append(('My Portfolio','WARN','No saved investments yet'))
    plans=BASE/'data'/'allocation_plans.csv'
    if plans.exists():
        try:
            n=len(pd.read_csv(plans));rows.append(('Tracked money plans','PASS',f'{n} allocation plan(s) saved'))
        except Exception as e:rows.append(('Tracked money plans','WARN',str(e)))
    else:rows.append(('Tracked money plans','WARN','No optimizer plan tracked yet'))
    ipo=BASE/'data'/'ipo_watchlist.csv'
    rows.append(('IPO data','PASS' if ipo.exists() else 'WARN','Saved IPO/new-issue data available' if ipo.exists() else 'Run DAILY UPDATE or add verified IPO data'))
    opt=BASE/'data'/'investment_options.csv'
    rows.append(('Other investment assumptions','PASS' if opt.exists() else 'WARN','Current/editable investment-option table available' if opt.exists() else 'Open Other Investments once to create defaults'))
    try:b=load_bonds();rows.append(("Fixed Income list","PASS",f"{len(b)} instruments"))
    except Exception as e:rows.append(("Fixed Income list","FAIL",str(e)))
    for name,file in [("Backtest",BASE/"data"/"backtest_stats.csv"),("Walk-forward",BASE/"data"/"walk_forward_stats.csv")]:
        rows.append((name,"PASS" if file.exists() else "WARN","Ready" if file.exists() else f"Build {name.lower()} once for stronger confidence"))
    ann=load_announcements();rows.append(("News / Results safety gate","PASS" if not ann.empty else "WARN",f"{len(ann)} NSE announcements cached" if not ann.empty else "Run DAILY UPDATE; if NSE blocks endpoint, Strong Buy is automatically capped"))
    try:
        dh,score=build_data_health();rows.append(("Auto Data Center","PASS" if score>=75 else "WARN",f"Overall data-health score {score:.0f}%"))
    except Exception as e:rows.append(("Auto Data Center","WARN",str(e)))
    lb=latest_backup();rows.append(("Local backup","PASS" if lb else "WARN",lb.name if lb else "Backup is created after DAILY UPDATE"))
    return pd.DataFrame(rows,columns=["Check","Status","Detail"])
