from __future__ import annotations
from pathlib import Path
from datetime import datetime, timedelta
import json, pandas as pd

BASE=Path(__file__).resolve().parent
DATA=BASE/'data'
DATA.mkdir(parents=True,exist_ok=True)
STATE=DATA/'source_runtime.json'
REGISTRY=DATA/'source_registry.csv'

DEFAULT_REGISTRY=[
 {'DataFamily':'NSE Stocks / ETFs','Primary':'NSE official EOD/common files','Backup1':'Last verified local NSE cache','Backup2':'Manual verified import','Critical':'YES','FreeFirst':'YES','Notes':'EOD technical engine; never fabricate missing sessions.'},
 {'DataFamily':'BSE / Corporate Cross-check','Primary':'BSE official public filings/market data where available','Backup1':'NSE official data','Backup2':'Last verified local cache','Critical':'NO','FreeFirst':'YES','Notes':'Cross-check/fallback, not mandatory for every workflow.'},
 {'DataFamily':'Corporate Events','Primary':'NSE official corporate actions/announcements/results','Backup1':'BSE official filings where available','Backup2':'Last verified event cache','Critical':'YES','FreeFirst':'YES','Notes':'BLOCK/REVIEW event gate.'},
 {'DataFamily':'Mutual Funds NAV','Primary':'AMFI Complete NAV','Backup1':'MFAPI public fallback','Backup2':'Last verified AMFI/MFAPI cache','Critical':'YES','FreeFirst':'YES','Notes':'Latest published NAV + on-demand history.'},
 {'DataFamily':'Gold / Silver','Primary':'Automatic public bullion/FX reference when available','Backup1':'NSE Gold/Silver ETF market proxies','Backup2':'Manual local dealer quote','Critical':'YES','FreeFirst':'YES','Notes':'Physical retail quote can override indicative benchmark.'},
 {'DataFamily':'Government / RBI','Primary':'RBI / Government official information','Backup1':'NSE debt/public market information where available','Backup2':'Manual verified official-rate input','Critical':'YES','FreeFirst':'YES','Notes':'T-Bills, G-Secs, SDL and policy/reference data.'},
 {'DataFamily':'Post Office / Small Savings','Primary':'Government/India Post official notifications','Backup1':'Last verified official-rate cache','Backup2':'Manual official-rate input','Critical':'NO','FreeFirst':'YES','Notes':'PPF/NSC/KVP/SCSS/Sukanya/PO products; rate validity is period-based.'},
 {'DataFamily':'FD / RD','Primary':'Official bank/SFB/NBFC published rates where configured','Backup1':'Last verified institution quote','Backup2':'Manual current official quote','Critical':'NO','FreeFirst':'YES','Notes':'No universal free authoritative API exists for all institutions.'},
 {'DataFamily':'IPO / SME IPO','Primary':'NSE/SEBI official issue data and documents where available','Backup1':'Last verified issue cache','Backup2':'Manual verified RHP/issue inputs','Critical':'YES','FreeFirst':'YES','Notes':'GMP remains optional/unofficial/low weight.'},
 {'DataFamily':'NPS','Primary':'NPS Trust official published scheme data where integrated','Backup1':'Last verified NPS data','Backup2':'Manual official input','Critical':'NO','FreeFirst':'YES','Notes':'Market-linked retirement analysis.'},
 {'DataFamily':'Crypto','Primary':'Public liquid-market endpoint','Backup1':'Alternative public endpoint when configured','Backup2':'Last verified crypto cache','Critical':'NO','FreeFirst':'YES','Notes':'Confidence reduced on feed disagreement/unavailability.'},
 {'DataFamily':'Macro / FX','Primary':'Public market series + official Indian references where integrated','Backup1':'Last verified macro cache','Backup2':'Manual verified context','Critical':'NO','FreeFirst':'YES','Notes':'Context only; core NSE engine can continue if unavailable.'},
 {'DataFamily':'FII / DII Institutional Flow','Primary':'NSE official FII/FPI & DII trading activity','Backup1':'Last verified local institutional-flow history','Backup2':'NSDL/CDSL final FPI data manual verification','Critical':'NO','FreeFirst':'YES','Notes':'NSE same-day figures are provisional; supporting market context, not a standalone signal.'},
 {'DataFamily':'F&O Participant Positioning','Primary':'NSE official participant-wise OI/volume and FII derivatives reports','Backup1':'Last verified local derivatives cache','Backup2':'REVIEW REQUIRED','Critical':'NO','FreeFirst':'YES','Notes':'Index futures/options positioning modifies market regime/confidence; never standalone BUY.'},
 {'DataFamily':'Market Breadth','Primary':'Calculated from official NSE EOD universe + NSE market statistics where available','Backup1':'Last verified breadth history','Backup2':'REVIEW REQUIRED','Critical':'NO','FreeFirst':'YES','Notes':'Advance/decline, moving-average participation and highs/lows context.'},
 {'DataFamily':'Security Delivery','Primary':'NSE official security-wise delivery/MTO report','Backup1':'Last verified delivery cache','Backup2':'No delivery modifier','Critical':'NO','FreeFirst':'YES','Notes':'Company-level participation confirmation; absence does not fabricate a value.'},
 {'DataFamily':'Index Valuation','Primary':'NSE official index P/E P/B dividend-yield reports','Backup1':'Last verified valuation cache','Backup2':'REVIEW REQUIRED','Critical':'NO','FreeFirst':'YES','Notes':'Valuation is context, not a deterministic timing signal.'},
 {'DataFamily':'Surveillance','Primary':'NSE official surveillance/ASM/GSM/ESM indicators where available','Backup1':'Last verified surveillance cache','Backup2':'Official corporate-event review','Critical':'YES','FreeFirst':'YES','Notes':'Serious restrictions can cap/block fresh recommendations.'},
 {'DataFamily':'FPI Sector Flows','Primary':'NSDL/CDSL official sector-wise FPI publications','Backup1':'Last verified sector cache','Backup2':'Manual official verification','Critical':'NO','FreeFirst':'YES','Notes':'Sector-allocation/rotation confirmation.'},
 {'DataFamily':'AMFI SIP / Domestic Flows','Primary':'AMFI official monthly/SIP publications','Backup1':'Last verified AMFI flow cache','Backup2':'Manual official verification','Critical':'NO','FreeFirst':'YES','Notes':'Domestic flow regime and long-term allocation context.'},
 {'DataFamily':'Google Archive / Index','Primary':'Google Drive Desktop synced folder or Google Drive/Sheets API','Backup1':'Local Data Vault + Excel/ZIP export','Backup2':'Supabase full-data persistence','Critical':'NO','FreeFirst':'YES','Notes':'Optional long-term archive/index; secrets are never committed to GitHub.'},
 {'DataFamily':'Market News Context','Primary':'Public RSS/news aggregation','Backup1':'NSE official corporate announcements/events','Backup2':'Last verified headline cache','Critical':'NO','FreeFirst':'YES','Notes':'General headlines are context only; official company filings remain the hard safety gate.'},
 {'DataFamily':'International','Primary':'Indian-listed NSE/AMFI products first','Backup1':'Public foreign-market reference when available','Backup2':'Last verified cache/manual input','Critical':'NO','FreeFirst':'YES','Notes':'No paid dependency required for core Indian product analysis.'},
 {'DataFamily':'Hosting / Online','Primary':'Configured free-tier host','Backup1':'Portable Docker deployment to alternate host','Backup2':'Local Windows app','Critical':'NO','FreeFirst':'YES','Notes':'No automatic paid upgrade; provider migration supported.'},
]


def ensure_registry():
    if not REGISTRY.exists():pd.DataFrame(DEFAULT_REGISTRY).to_csv(REGISTRY,index=False)


def load_registry():
    ensure_registry()
    try:return pd.read_csv(REGISTRY)
    except Exception:return pd.DataFrame(DEFAULT_REGISTRY)


def save_registry(df):
    ensure_registry();df.to_csv(REGISTRY,index=False)


def _load_state():
    if not STATE.exists():return {}
    try:return json.loads(STATE.read_text(encoding='utf-8'))
    except Exception:return {}


def _save_state(d):STATE.write_text(json.dumps(d,indent=2),encoding='utf-8')


def record_success(source_key:str,detail:str=''):
    d=_load_state();r=d.get(source_key,{})
    r.update({'status':'OK','last_success':datetime.now().isoformat(timespec='seconds'),'last_error':'','cooldown_until':'','detail':detail,'failures':0})
    d[source_key]=r;_save_state(d)


def record_failure(source_key:str,error:str,cooldown_minutes:int=15,rate_limited:bool=False):
    d=_load_state();r=d.get(source_key,{})
    fails=int(r.get('failures',0) or 0)+1
    # Exponential but capped, or explicit cooldown for rate limits.
    mins=max(cooldown_minutes,(2**min(fails,6))) if not rate_limited else max(15,cooldown_minutes)
    until=datetime.now()+timedelta(minutes=min(mins,24*60))
    r.update({'status':'RATE LIMITED' if rate_limited else 'FAILED','last_error':str(error)[:1000],'last_failure':datetime.now().isoformat(timespec='seconds'),'cooldown_until':until.isoformat(timespec='seconds'),'failures':fails})
    d[source_key]=r;_save_state(d)


def can_retry(source_key:str):
    r=_load_state().get(source_key,{})
    raw=r.get('cooldown_until')
    if not raw:return True,0
    try:
        dt=datetime.fromisoformat(raw);remain=(dt-datetime.now()).total_seconds()
        return remain<=0,max(0,int(remain))
    except Exception:return True,0


def clear_cooldown(source_key:str):
    d=_load_state();r=d.get(source_key,{})
    r['cooldown_until']='';r['status']='READY';d[source_key]=r;_save_state(d)


def runtime_status():
    d=_load_state();rows=[]
    for k,v in d.items():
        ok,remaining=can_retry(k)
        rows.append({'SourceKey':k,'Status':v.get('status','UNKNOWN'),'LastSuccess':v.get('last_success',''),'LastFailure':v.get('last_failure',''),'RetryInSeconds':0 if ok else remaining,'LastError':v.get('last_error',''),'Detail':v.get('detail','')})
    return pd.DataFrame(rows)


def no_paid_usage_policy():
    return {'AutomaticPaidUsage':'OFF','AutomaticSubscription':'OFF','AutomaticUpgrade':'OFF','SpendLimit₹':0,'FallbackPolicy':'FREE ALTERNATIVE → VERIFIED CACHE → WAIT/RETRY → MANUAL VERIFY → REVIEW REQUIRED'}
