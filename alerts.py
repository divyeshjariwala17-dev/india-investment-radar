from __future__ import annotations
from pathlib import Path
from datetime import datetime
import pandas as pd

BASE=Path(__file__).resolve().parent
FILE=BASE/"data"/"alerts.csv"
STATE=BASE/"data"/"alert_state.csv"

def build_alerts(radar,tracked=None,previous_regime=None):
    rows=[];now=datetime.now().isoformat(timespec="seconds")
    if radar is not None and not radar.empty:
        regime=str(radar.iloc[0].get("MarketRegime",""))
        if previous_regime and regime!=previous_regime:
            rows.append({"Time":now,"Type":"MARKET REGIME","Symbol":"MARKET","Message":f"Market regime changed {previous_regime} → {regime}"})
        for _,r in radar.iterrows():
            sig=str(r.get("Signal",r.get("Recommendation","")))
            ent=str(r.get("EntryStatus",""))
            if sig=="STRONG BUY":rows.append({"Time":now,"Type":"STRONG BUY","Symbol":r.Symbol,"Message":f"{r.Category}: Strong Buy {r.Overall}/100, R:R {r.RR}, {ent}"})
            elif sig in ("BUY","BUY ON PULLBACK") and ent=="ENTRY VALID":rows.append({"Time":now,"Type":"ENTRY VALID","Symbol":r.Symbol,"Message":f"{r.Category}: entry is valid ₹{r.EntryLow}–₹{r.EntryHigh}"})
    # If a tracked allocation plan has reserve cash and a new valid Strong Buy appears,
    # surface a review alert instead of silently leaving the reserve idle.
    plans=BASE/'data'/'allocation_plans.csv'
    if radar is not None and not radar.empty and plans.exists():
        try:
            pp=pd.read_csv(plans)
            active=pp[(pp.get('Status','ACTIVE').astype(str).eq('ACTIVE')) & (pd.to_numeric(pp.get('ReserveRs',0),errors='coerce').fillna(0)>0)]
            top=radar[(radar.get('Signal','').astype(str).eq('STRONG BUY')) & (radar.get('EntryStatus','').astype(str).eq('ENTRY VALID'))].sort_values('Overall',ascending=False).head(1)
            if not active.empty and not top.empty:
                rr=top.iloc[0];reserve=float(pd.to_numeric(active.ReserveRs,errors='coerce').fillna(0).max())
                rows.append({'Time':now,'Type':'RESERVE OPPORTUNITY','Symbol':rr.Symbol,'Message':f'₹{reserve:,.0f} tracked reserve exists; {rr.Symbol} is a valid Strong Buy. Review the saved plan before deploying.'})
        except Exception:
            pass

    # Corporate-event alerts for recommendation candidates and owned securities.
    try:
        from nse_events import load_all_events, _parse_date
        from datetime import date as _date
        ev=load_all_events()
        watch=set()
        if radar is not None and not radar.empty:
            watch.update(radar[radar.get('Signal','').astype(str).isin(['STRONG BUY','BUY','BUY ON PULLBACK'])].Symbol.astype(str).str.upper().tolist())
        pf=BASE/'data'/'my_portfolio.csv'
        if pf.exists():
            try:
                ph=pd.read_csv(pf)
                if 'SymbolOrScheme' in ph.columns:watch.update(ph.SymbolOrScheme.astype(str).str.upper().tolist())
            except Exception:pass
        if not ev.empty and watch:
            for _,e in ev[ev.Symbol.astype(str).str.upper().isin(watch)].iterrows():
                d=None
                for c in ('EventDate','ExDate','RecordDate'):
                    d=_parse_date(e.get(c,''))
                    if d:break
                if not d:continue
                delta=(d-_date.today()).days
                if 0<=delta<=7 and str(e.get('Severity','INFO')).upper() in ('REVIEW','BLOCK'):
                    rows.append({'Time':now,'Type':'CORPORATE EVENT','Symbol':str(e.Symbol),'Message':f"{e.EventType} in {delta} day(s): {str(e.Subject)[:180]} — {e.SystemAction}"})
    except Exception:
        pass

    if tracked is not None and not tracked.empty and "Outcome" in tracked:
        for _,r in tracked.tail(50).iterrows():
            o=str(r.get("Outcome",""))
            if o in ("TARGET1","TARGET2","STOP","STOP_AMBIGUOUS"):
                rows.append({"Time":now,"Type":o,"Symbol":r.get("Symbol",""),"Message":f"{r.get('Category','')} recommendation outcome: {o}"})
    if not rows:return load_alerts()
    new=pd.DataFrame(rows).drop_duplicates(["Type","Symbol","Message"])
    if FILE.exists():
        try:old=pd.read_csv(FILE)
        except Exception:old=pd.DataFrame()
        allx=pd.concat([old,new],ignore_index=True).drop_duplicates(["Type","Symbol","Message"],keep="last").tail(500)
    else:allx=new
    allx.to_csv(FILE,index=False)
    return allx.sort_values("Time",ascending=False)

def load_alerts():
    if FILE.exists():
        try:return pd.read_csv(FILE).sort_values("Time",ascending=False)
        except Exception:pass
    return pd.DataFrame(columns=["Time","Type","Symbol","Message"])
