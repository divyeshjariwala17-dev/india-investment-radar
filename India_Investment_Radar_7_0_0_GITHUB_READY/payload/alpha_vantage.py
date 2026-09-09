
from __future__ import annotations
from pathlib import Path
from datetime import date
import json, os, time
import requests
import pandas as pd

BASE = Path(__file__).resolve().parent
CACHE = BASE / "data" / "alpha_fundamentals.csv"
ENV = BASE / ".env"

def load_local_api_key():
    if not ENV.exists():
        return ""
    for line in ENV.read_text(encoding="utf-8", errors="ignore").splitlines():
        if line.strip().startswith("ALPHA_VANTAGE_API_KEY="):
            return line.split("=",1)[1].strip().strip('"').strip("'")
    return ""

def save_local_api_key(key: str):
    # Local-only convenience. The user should never paste the key into chat.
    key = (key or "").strip()
    content = f'ALPHA_VANTAGE_API_KEY="{key}"\n' if key else ""
    ENV.write_text(content, encoding="utf-8")

def _num(x, scale=1.0):
    try:
        if x in (None,"","None","-"): return None
        return float(x)*scale
    except Exception:
        return None

def _load_cache():
    if CACHE.exists():
        try: return pd.read_csv(CACHE)
        except Exception: pass
    return pd.DataFrame()

def refresh_fundamentals(symbols, api_key=None, max_symbols=5, status_cb=None):
    api_key = (api_key or load_local_api_key()).strip()
    if not api_key:
        return {"updated":0,"failed":0,"message":"No Alpha Vantage key saved locally."}
    old = _load_cache()
    rows = []
    if not old.empty:
        rows = old.to_dict("records")
    bysym = {str(r.get("symbol","")).upper():r for r in rows}
    updated=failed=0
    s = requests.Session()
    for symbol in list(dict.fromkeys([str(x).upper() for x in symbols]))[:max_symbols]:
        if status_cb: status_cb(f"Refreshing fundamentals: {symbol}")
        # Alpha Vantage documents BSE symbols with .BSE suffix.
        params={"function":"OVERVIEW","symbol":f"{symbol}.BSE","apikey":api_key}
        try:
            r=s.get("https://www.alphavantage.co/query",params=params,timeout=25)
            j=r.json()
            if "Note" in j or "Information" in j:
                return {"updated":updated,"failed":failed,
                        "message":j.get("Note") or j.get("Information")}
            if not j or not j.get("Symbol"):
                failed+=1; continue
            rec={
                "symbol":symbol,
                "company_name":j.get("Name") or symbol,
                "sector":j.get("Sector") or "",
                "market_cap_cr": (_num(j.get("MarketCapitalization")) or 0)/1e7 or None,
                "roe":_num(j.get("ReturnOnEquityTTM"),100),
                "opm_pct":_num(j.get("OperatingMarginTTM"),100),
                "pe":_num(j.get("PERatio")),
                "forward_pe":_num(j.get("ForwardPE")),
                "earnings_growth_yoy":_num(j.get("QuarterlyEarningsGrowthYOY"),100),
                "revenue_growth_yoy":_num(j.get("QuarterlyRevenueGrowthYOY"),100),
                "eps":_num(j.get("EPS")),
                "analyst_target":_num(j.get("AnalystTargetPrice")),
                "wk52_high_fund":_num(j.get("52WeekHigh")),
                "wk52_low_fund":_num(j.get("52WeekLow")),
                "fundamental_date":date.today().isoformat(),
                "fundamental_source":"Alpha Vantage OVERVIEW"
            }
            bysym[symbol]=rec
            updated+=1
            time.sleep(0.05)
        except Exception:
            failed+=1
    out=pd.DataFrame(list(bysym.values()))
    if not out.empty: out.to_csv(CACHE,index=False)
    return {"updated":updated,"failed":failed,"message":"OK"}

def load_auto_fundamentals():
    return _load_cache()
