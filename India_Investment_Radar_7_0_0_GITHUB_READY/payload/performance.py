from __future__ import annotations
from pathlib import Path
import numpy as np,pandas as pd

def _entry_from_bar(bar,lo,hi):
    op,low,high=float(bar.Open),float(bar.Low),float(bar.High)
    if op>hi and low>hi:return None
    if high<lo:return None
    if lo<=op<=hi:return op
    if op<lo and high>=lo:return lo
    if op>hi and low<=hi:return hi
    return None

def evaluate_trade(future,entry_low,entry_high,target1,target2,stop,entry_window,horizon):
    future=future.head(horizon).copy()
    if future.empty:return {"Outcome":"NO_DATA"}
    entry_idx=None;entry=None
    for i,(_,bar) in enumerate(future.head(entry_window).iterrows()):
        px=_entry_from_bar(bar,entry_low,entry_high)
        if px is not None:entry_idx=i;entry=float(px);break
    if entry_idx is None:return {"Outcome":"NO_ENTRY"}
    post=future.iloc[entry_idx:];mfe=0.0;mae=0.0;t1_date=None
    for _,bar in post.iterrows():
        hi,lo=float(bar.High),float(bar.Low);mfe=max(mfe,(hi/entry-1)*100);mae=min(mae,(lo/entry-1)*100)
        hs=lo<=stop;h1=hi>=target1;h2=hi>=target2
        if hs and (h1 or h2):return {"Outcome":"STOP_AMBIGUOUS","Entry":entry,"MFE%":mfe,"MAE%":mae,"ExitDate":str(pd.to_datetime(bar.Date).date())}
        if hs:return {"Outcome":"STOP","Entry":entry,"MFE%":mfe,"MAE%":mae,"ExitDate":str(pd.to_datetime(bar.Date).date())}
        if h2:return {"Outcome":"TARGET2","Entry":entry,"MFE%":mfe,"MAE%":mae,"ExitDate":str(pd.to_datetime(bar.Date).date())}
        if h1 and t1_date is None:t1_date=bar.Date
    if t1_date is not None:return {"Outcome":"TARGET1","Entry":entry,"MFE%":mfe,"MAE%":mae,"ExitDate":str(pd.to_datetime(t1_date).date())}
    return {"Outcome":"EXPIRED","Entry":entry,"MFE%":mfe,"MAE%":mae,"ExitDate":str(pd.to_datetime(post.iloc[-1].Date).date())}

def update_saved_outcomes(log_path:Path,history:pd.DataFrame):
    if not log_path.exists():return pd.DataFrame()
    log=pd.read_csv(log_path)
    if log.empty:return log
    h=history.sort_values(["Symbol","Date"]).copy();results=[]
    for _,r in log.iterrows():
        row=r.to_dict()
        if str(row.get("Outcome","")).strip() in ("TARGET1","TARGET2","STOP","STOP_AMBIGUOUS"):results.append(row);continue
        sym=str(r["Symbol"]).upper();d=pd.to_datetime(r["DataDate"]);fut=h[(h.Symbol==sym)&(h.Date>d)].sort_values("Date");cat=str(r["Category"])
        ev=evaluate_trade(fut,float(r.EntryLow),float(r.EntryHigh),float(r.Target1),float(r.Target2),float(r.StopLoss),{"SWING":3,"SHORT":5,"LONG":20}.get(cat,3),{"SWING":25,"SHORT":90,"LONG":260}.get(cat,25))
        row.update(ev);results.append(row)
    out=pd.DataFrame(results);out.to_csv(log_path,index=False);return out

def performance_summary(log):
    if log is None or log.empty or "Outcome" not in log:return pd.DataFrame()
    rows=[]
    group_cols=["Category"]
    for cat,g in log.groupby("Category"):
        done=g[g.Outcome.isin(["TARGET1","TARGET2","STOP","STOP_AMBIGUOUS","EXPIRED"])]
        wins=done.Outcome.isin(["TARGET1","TARGET2"]).sum();losses=done.Outcome.isin(["STOP","STOP_AMBIGUOUS"]).sum();sample=wins+losses
        rows.append({"Category":cat,"Resolved":int(sample),"Wins":int(wins),"Stops":int(losses),"WinRate%":round(wins/sample*100,1) if sample else np.nan,
                     "Target2":int((done.Outcome=="TARGET2").sum()),"Expired":int((done.Outcome=="EXPIRED").sum()),
                     "AvgMFE%":round(pd.to_numeric(done.get("MFE%"),errors="coerce").mean(),1) if "MFE%" in done else np.nan,
                     "AvgMAE%":round(pd.to_numeric(done.get("MAE%"),errors="coerce").mean(),1) if "MAE%" in done else np.nan})
    return pd.DataFrame(rows)

def segmented_performance(log):
    if log is None or log.empty or "Outcome" not in log:return pd.DataFrame()
    dims=[c for c in ["Category","Signal","MarketRegime","Sector"] if c in log.columns]
    if not dims:return pd.DataFrame()
    rows=[]
    for dim in dims:
        for val,g in log.groupby(dim,dropna=False):
            done=g[g.Outcome.isin(["TARGET1","TARGET2","STOP","STOP_AMBIGUOUS"])]
            wins=done.Outcome.isin(["TARGET1","TARGET2"]).sum();losses=done.Outcome.isin(["STOP","STOP_AMBIGUOUS"]).sum();n=wins+losses
            if n<3:continue
            rows.append({"Dimension":dim,"Group":str(val),"Resolved":int(n),"WinRate%":round(wins/n*100,1),"Wins":int(wins),"Stops":int(losses)})
    return pd.DataFrame(rows).sort_values(["Dimension","WinRate%"],ascending=[True,False]) if rows else pd.DataFrame()
