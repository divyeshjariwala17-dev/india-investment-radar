from __future__ import annotations
from pathlib import Path
import json
from datetime import datetime
import numpy as np
import pandas as pd

BASE=Path(__file__).resolve().parent
STATE=BASE/"data"/"physical_metals_state.json"
AUTO=BASE/"data"/"physical_metals_auto.json"

def load_state():
    if STATE.exists():
        try:return json.loads(STATE.read_text(encoding="utf-8"))
        except Exception:pass
    return {
        "GOLD":{"quote":0.0,"premium_pct":0.0,"gst_pct":0.0,"amount":100000.0},
        "SILVER":{"quote":0.0,"premium_pct":0.0,"gst_pct":0.0,"amount":100000.0},
    }

def save_state(state):
    STATE.parent.mkdir(parents=True,exist_ok=True)
    STATE.write_text(json.dumps(state,indent=2),encoding="utf-8")

def effective_cost(base_rate,premium_pct=0.0,gst_pct=0.0):
    base=float(base_rate or 0)
    return base*(1+float(premium_pct or 0)/100)*(1+float(gst_pct or 0)/100)

def convert_proxy_level(level,proxy_current,physical_quote):
    if not proxy_current or proxy_current<=0 or not physical_quote or physical_quote<=0:return np.nan
    return float(physical_quote)*(float(level)/float(proxy_current))

def physical_card(asset_row,physical_quote):
    """Translate ETF/proxy percentage levels into physical-market rate levels."""
    if physical_quote<=0:return {}
    pc=float(asset_row.Current)
    conv=lambda x:convert_proxy_level(x,pc,physical_quote)
    return {
        "CurrentPhysical":round(float(physical_quote),2),
        "BuyLow":round(conv(asset_row.EntryLow),2),
        "BuyHigh":round(conv(asset_row.EntryHigh),2),
        "Support1":round(conv(asset_row.S1),2),
        "Support2":round(conv(asset_row.S2),2),
        "Target1":round(conv(asset_row.Target1),2),
        "Target2":round(conv(asset_row.Target2),2),
    }

def timing_decision(r):
    sig=str(r.Signal)
    es=str(r.EntryStatus)
    if sig=="STRONG BUY" and es=="ENTRY VALID":
        return "🔥 STRONG PHYSICAL BUY", "Buy in stages: 40% now, 30% near lower buy zone, keep 30% reserve."
    if sig in ("STRONG BUY","BUY") and es=="ENTRY VALID":
        return "🟢 BUY PHYSICAL IN PARTS", "Buy 30% now, 30% on a dip inside the buy zone, keep 40% reserve."
    if sig in ("STRONG BUY","BUY") and es=="WAIT FOR PULLBACK":
        return "🟡 WAIT FOR DIP", "Do not chase. Buy only when the physical price returns toward the displayed buy zone."
    if sig=="BUY":
        return "🟢 BUY IN STAGES", "Use staggered buying rather than one full purchase."
    if sig=="WATCH":
        return "👀 WAIT / WATCH", "Keep cash ready. Buy only if price reaches the buy zone and the signal remains valid."
    return "🔴 DO NOT BUY NOW", "No fresh physical purchase is suggested by the current rules."

def tranche_plan(amount,decision):
    amount=float(amount or 0)
    if "STRONG PHYSICAL BUY" in decision:
        pcts=[40,30,30]; labels=["Buy now","Buy near lower zone","Reserve"]
    elif "BUY PHYSICAL IN PARTS" in decision or "BUY IN STAGES" in decision:
        pcts=[30,30,40]; labels=["Buy now","Buy on dip","Reserve"]
    elif "WAIT FOR DIP" in decision:
        pcts=[0,40,60]; labels=["Buy now","Buy only in zone","Reserve"]
    else:
        pcts=[0,0,100]; labels=["Buy now","Planned buy","Keep cash"]
    return pd.DataFrame({"Stage":labels,"Allocation%":pcts,"Amount₹":[round(amount*p/100,2) for p in pcts]})

def rolling_scenarios(g):
    if g is None or g.empty or len(g)<90:return pd.DataFrame()
    s=g.sort_values("Date").set_index("Date")["Close"].astype(float)
    rows=[]
    for label,days in [("1 Week",7),("15 Days",15),("1 Month",30),("3 Months",91),("6 Months",182),("1 Year",365)]:
        vals=[]
        idx=s.index
        for i in range(len(s)):
            target=idx[i]+pd.Timedelta(days=days)
            j=idx.searchsorted(target)
            if j<len(s):
                vals.append((s.iloc[j]/s.iloc[i]-1)*100)
        x=pd.Series(vals,dtype=float).dropna()
        if len(x)<20:
            rows.append({"Duration":label,"ProbabilityPositive%":np.nan,"Low%":np.nan,"Median%":np.nan,"High%":np.nan,"Samples":len(x)})
            continue
        rows.append({
            "Duration":label,
            "ProbabilityPositive%":round((x>0).mean()*100,1),
            "Low%":round(x.quantile(.20),2),
            "Median%":round(x.median(),2),
            "High%":round(x.quantile(.80),2),
            "Samples":len(x)
        })
    return pd.DataFrame(rows)

def scenario_prices(scenarios,current_quote):
    if scenarios is None or scenarios.empty or current_quote<=0:return pd.DataFrame()
    x=scenarios.copy()
    for c,new in [("Low%","LowPrice₹"),("Median%","MedianPrice₹"),("High%","HighPrice₹")]:
        x[new]=(current_quote*(1+x[c]/100)).round(2)
    return x


def automatic_reference_from_macro(macro_df):
    """Best-effort India converted reference from global futures + USD/INR.
    This is NOT a local retail quote and intentionally excludes import duty, GST, dealer premium and making charges.
    Returns per 10g for Gold and per kg for Silver.
    """
    if macro_df is None or macro_df.empty:
        return {}
    try:
        m={str(r.Indicator):r for _,r in macro_df.iterrows()}
        fx=float(m['USD/INR']['Latest'])
        gold=float(m['Global Gold']['Latest'])
        silver=float(m['Global Silver']['Latest'])
        oz_g=31.1034768
        return {
            'GOLD':{
                'rate':round(gold*fx/oz_g*10,2),
                'unit':'10 grams',
                'basis':'Global Gold futures × USD/INR converted to INR/10g; excludes India retail taxes/premium',
                'date':str(m['Global Gold'].get('Date',''))
            },
            'SILVER':{
                'rate':round(silver*fx/oz_g*1000,2),
                'unit':'1 kg',
                'basis':'Global Silver futures × USD/INR converted to INR/kg; excludes India retail taxes/premium',
                'date':str(m['Global Silver'].get('Date',''))
            }
        }
    except Exception:
        return {}


def gold_purity_factor(purity):
    p=str(purity or '24K / 999').upper()
    if p.startswith('22K') or '916' in p:return 22/24
    if p.startswith('18K') or '750' in p:return 18/24
    return 1.0

def refresh_auto_rates(macro_df):
    refs=automatic_reference_from_macro(macro_df)
    if not refs:return {}
    out={}
    for asset,v in refs.items():
        x=dict(v);x['updated_at']=datetime.now().isoformat(timespec='seconds');x['source']='AUTO MARKET REFERENCE';x['status']='FRESH';out[asset]=x
    AUTO.parent.mkdir(parents=True,exist_ok=True);AUTO.write_text(json.dumps(out,indent=2),encoding='utf-8');return out

def load_auto_rates():
    if AUTO.exists():
        try:return json.loads(AUTO.read_text(encoding='utf-8'))
        except Exception:pass
    return {}

def get_auto_rate(asset,macro_df=None,purity='24K / 999',local_adjustment_pct=0.0):
    asset=str(asset).upper();refs={}
    if macro_df is not None and not getattr(macro_df,'empty',True):
        refs=automatic_reference_from_macro(macro_df)
        if refs:
            try:refresh_auto_rates(macro_df)
            except Exception:pass
    if not refs:refs=load_auto_rates()
    r=dict(refs.get(asset,{}) or {});base=float(r.get('rate',0) or 0)
    if asset=='GOLD':base*=gold_purity_factor(purity)
    base*=1+float(local_adjustment_pct or 0)/100
    r['rate']=round(base,2);r['purity']=purity if asset=='GOLD' else '999';r['local_adjustment_pct']=float(local_adjustment_pct or 0);return r
