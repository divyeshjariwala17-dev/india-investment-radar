from __future__ import annotations
from pathlib import Path
import json, pickle
import pandas as pd

BASE = Path(__file__).resolve().parent
CACHE_DIR = BASE / "data" / "dashboard_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

FILES = {
    "radar": CACHE_DIR / "radar.csv",
    "breadth": CACHE_DIR / "breadth.json",
    "market_outlook": CACHE_DIR / "market_outlook.csv",
    "market_proxy": CACHE_DIR / "market_proxy.csv",
    "mf": CACHE_DIR / "mutual_funds.csv",
    "mf_details": CACHE_DIR / "mutual_fund_details.pkl",
    "bonds": CACHE_DIR / "bonds.csv",
    "meta": CACHE_DIR / "meta.json",
}


def save_cache(radar, breadth, mout, proxy, mf, mfd, bonds, meta=None, histories=None):
    if radar is not None: radar.to_csv(FILES["radar"], index=False)
    FILES["breadth"].write_text(json.dumps(breadth or {}, indent=2, default=str), encoding="utf-8")
    if mout is not None: mout.to_csv(FILES["market_outlook"], index=False)
    if proxy is not None: proxy.to_csv(FILES["market_proxy"], index=False)
    if mf is not None: mf.to_csv(FILES["mf"], index=False)
    with open(FILES["mf_details"], "wb") as f: pickle.dump(mfd or {}, f)
    if bonds is not None: bonds.to_csv(FILES["bonds"], index=False)
    FILES["meta"].write_text(json.dumps(meta or {}, indent=2, default=str), encoding="utf-8")
    if histories:
        chart_dir = CACHE_DIR / "charts"
        chart_dir.mkdir(exist_ok=True)
        # Save charts only for stocks that are present in the current radar, keeping startup light.
        syms = set(radar[radar.get("Signal", "WATCH") != "AVOID"].head(180).Symbol.astype(str).unique()) if radar is not None and not radar.empty else set(histories)
        for sym in syms:
            g = histories.get(sym)
            if g is None or g.empty: continue
            cols = [c for c in ["Date","Close","EMA10","EMA21","EMA50","RSI14","Volume"] if c in g.columns]
            g.tail(180)[cols].to_csv(chart_dir / f"{sym}.csv", index=False)


def cache_exists():
    return FILES["radar"].exists() and FILES["meta"].exists()


def load_cache():
    if not cache_exists(): return None
    def read_csv(key, dates=None):
        p=FILES[key]
        if not p.exists(): return pd.DataFrame()
        try: return pd.read_csv(p, parse_dates=dates or [])
        except Exception: return pd.DataFrame()
    try: breadth=json.loads(FILES["breadth"].read_text(encoding="utf-8")) if FILES["breadth"].exists() else {}
    except Exception: breadth={}
    try: meta=json.loads(FILES["meta"].read_text(encoding="utf-8"))
    except Exception: meta={}
    try:
        with open(FILES["mf_details"],"rb") as f: mfd=pickle.load(f)
    except Exception: mfd={}
    return {
        "radar":read_csv("radar"), "breadth":breadth,
        "market_outlook":read_csv("market_outlook"), "market_proxy":read_csv("market_proxy",["Date"]),
        "mf":read_csv("mf"), "mf_details":mfd, "bonds":read_csv("bonds"), "meta":meta
    }


def load_chart(symbol):
    p=CACHE_DIR/"charts"/f"{str(symbol).upper()}.csv"
    if not p.exists(): return pd.DataFrame()
    try: return pd.read_csv(p,parse_dates=["Date"])
    except Exception: return pd.DataFrame()
