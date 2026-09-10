from __future__ import annotations
from pathlib import Path
import numpy as np,pandas as pd
from radar_engine import add_indicators,technical_score,momentum_score,trade_levels,combine,score_band
from performance import evaluate_trade

CACHE=Path(__file__).resolve().parent/"data"/"walk_forward_stats.csv"
RAW=Path(__file__).resolve().parent/"data"/"walk_forward_raw.csv"

def _regime_at_frame(frame):
    if frame.empty:return "UNKNOWN"
    a21=(frame.Close>frame.EMA21).mean()*100;a50=(frame.Close>frame.EMA50).mean()*100
    adv=(frame.Close>frame.PrevClose).mean()*100 if "PrevClose" in frame else np.nan
    if a21>=60 and a50>=55 and (pd.isna(adv) or adv>=50):return "BULLISH"
    if a21<40 and a50<40:return "WEAK"
    return "CAUTIOUS"

def run_walk_forward(history,universe_size=220,status_cb=None):
    if history.empty:return pd.DataFrame()
    h=history.copy().sort_values(["Symbol","Date"])
    # Prepare indicators per symbol using only past/current values.
    enriched=[]
    for i,(sym,g) in enumerate(h.groupby("Symbol")):
        if len(g)<150:continue
        if status_cb and i%50==0:status_cb(f"Preparing walk-forward indicators: {i} symbols")
        enriched.append(add_indicators(g))
    if not enriched:return pd.DataFrame()
    allx=pd.concat(enriched,ignore_index=True).sort_values(["Date","Symbol"])
    dates=sorted(allx.Date.dropna().unique())
    # Sample every 10 sessions after warmup and leave enough future horizon.
    sample_dates=dates[100:-95:10]
    records=[]
    for di,d in enumerate(sample_dates):
        if status_cb and di%5==0:status_cb(f"Walk-forward {di+1}/{len(sample_dates)} dates")
        snap=allx[allx.Date==d].copy()
        if snap.empty:continue
        # Point-in-time liquidity only.
        snap=snap[(snap.Close>=20)&(snap.Volume>=100000)]
        if "TV20" in snap and snap.TV20.notna().any():snap=snap[(snap.TV20>=1.5)|snap.TV20.isna()]
        snap=snap.sort_values("Volume",ascending=False).head(universe_size)
        regime=_regime_at_frame(snap)
        for _,r in snap.iterrows():
            sym=r.Symbol;g=allx[(allx.Symbol==sym)&(allx.Date<=d)].sort_values("Date")
            if len(g)<80:continue
            ts=technical_score(r);ms=momentum_score(r)
            future=allx[(allx.Symbol==sym)&(allx.Date>d)].sort_values("Date")
            for cat in ["SWING","SHORT"]:
                ov=combine([(ts,.61),(ms,.39)]) if cat=="SWING" else combine([(ts,.60),(ms,.40)])
                if ov<64:continue
                lv=trade_levels(g,cat)
                minrr=1.7 if cat=="SWING" else 1.6
                if lv["rr"]<minrr:continue
                ev=evaluate_trade(future,lv["entry_low"],lv["entry_high"],lv["t1"],lv["t2"],lv["stop"],3 if cat=="SWING" else 5,25 if cat=="SWING" else 90)
                if ev["Outcome"] in ("NO_ENTRY","NO_DATA"):continue
                records.append({"SignalDate":str(pd.to_datetime(d).date()),"Symbol":sym,"Category":cat,"Regime":regime,
                                "ScoreBand":score_band(ov),"Overall":round(ov,1),"Outcome":ev["Outcome"]})
    if not records:return pd.DataFrame()
    raw=pd.DataFrame(records);raw.to_csv(RAW,index=False)
    rows=[]
    for keys,g in raw.groupby(["Category","Regime","ScoreBand"]):
        cat,reg,band=keys
        wins=g.Outcome.isin(["TARGET1","TARGET2"]).sum();losses=g.Outcome.isin(["STOP","STOP_AMBIGUOUS"]).sum();sample=wins+losses
        rows.append({"Category":cat,"Regime":reg,"ScoreBand":band,"Sample":int(sample),"Wins":int(wins),"Stops":int(losses),
                     "WinRate%":round(wins/sample*100,1) if sample else np.nan,"Target2":int((g.Outcome=="TARGET2").sum()),
                     "Expired":int((g.Outcome=="EXPIRED").sum())})
    out=pd.DataFrame(rows);out.to_csv(CACHE,index=False);return out

def load_walk_forward():
    if CACHE.exists():
        try:return pd.read_csv(CACHE)
        except Exception:pass
    return pd.DataFrame()
