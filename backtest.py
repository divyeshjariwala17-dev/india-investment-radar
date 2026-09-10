
from __future__ import annotations
from pathlib import Path
import numpy as np, pandas as pd
from radar_engine import add_indicators, technical_score, momentum_score, trade_levels, combine, score_band
from performance import evaluate_trade

CACHE=Path(__file__).resolve().parent/"data"/"backtest_stats.csv"

def run_backtest(history, universe_size=250, status_cb=None):
    if history.empty:return pd.DataFrame()
    # Select liquid names using median traded value / volume from recent history.
    h=history.copy().sort_values(["Symbol","Date"])
    recent=h.groupby("Symbol").tail(60)
    if "TradedValue" in recent:
        liq=recent.groupby("Symbol").TradedValue.median().sort_values(ascending=False).head(universe_size).index
    else:
        liq=recent.groupby("Symbol").Volume.median().sort_values(ascending=False).head(universe_size).index
    records=[]
    syms=list(liq)
    for si,sym in enumerate(syms):
        if status_cb and si%10==0:status_cb(f"Backtesting {si+1}/{len(syms)} liquid stocks")
        g=h[h.Symbol==sym].sort_values("Date")
        if len(g)<150:continue
        eg=add_indicators(g).reset_index(drop=True)
        # Monthly-ish sampling reduces correlated duplicate signals and runtime.
        for i in range(80,len(eg)-25,5):
            r=eg.iloc[i]; past=eg.iloc[:i+1]
            ts=technical_score(r);ms=momentum_score(r)
            for cat in ["SWING","SHORT"]:
                ov=combine([(ts,.61),(ms,.39)]) if cat=="SWING" else combine([(ts,.60),(ms,.40)])
                if ov<64:continue
                lv=trade_levels(past,cat)
                if lv["rr"]<(1.7 if cat=="SWING" else 1.6):continue
                future=eg.iloc[i+1:]
                ev=evaluate_trade(future,lv["entry_low"],lv["entry_high"],lv["t1"],lv["t2"],lv["stop"],
                                  3 if cat=="SWING" else 5,25 if cat=="SWING" else 90)
                if ev["Outcome"] in ("NO_ENTRY","NO_DATA"):continue
                records.append({"Category":cat,"ScoreBand":score_band(ov),"Outcome":ev["Outcome"]})
    if not records:return pd.DataFrame()
    raw=pd.DataFrame(records);rows=[]
    for (cat,band),g in raw.groupby(["Category","ScoreBand"]):
        wins=g.Outcome.isin(["TARGET1","TARGET2"]).sum()
        losses=g.Outcome.isin(["STOP","STOP_AMBIGUOUS"]).sum()
        sample=wins+losses
        rows.append({"Category":cat,"ScoreBand":band,"Sample":int(sample),
                     "WinRate%":round(wins/sample*100,1) if sample else np.nan,
                     "Target2Rate%":round((g.Outcome=="TARGET2").sum()/max(len(g),1)*100,1),
                     "Expired":int((g.Outcome=="EXPIRED").sum())})
    out=pd.DataFrame(rows)
    out.to_csv(CACHE,index=False)
    return out

def load_backtest_stats():
    if CACHE.exists():
        try:return pd.read_csv(CACHE)
        except Exception:pass
    return pd.DataFrame()
