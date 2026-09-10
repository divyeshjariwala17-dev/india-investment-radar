from __future__ import annotations
from pathlib import Path
import pandas as pd, numpy as np
from asset_radar import analyze_asset
from crypto_data import load as load_crypto, meta as crypto_meta, universe as crypto_universe
from physical_metals import timing_decision, load_state as load_metal_state

BASE=Path(__file__).resolve().parent
OUT=BASE/'data'/'cross_asset_opportunities.csv'
HISTORY=BASE/'data'/'cross_asset_history.csv'


def build(radar,mf,bonds,nse_history,cfg):
    rows=[]
    # Stocks: strict qualified first.
    if radar is not None and not radar.empty:
        r=radar.copy()
        if 'Eligibility' in r.columns:r=r[r.Eligibility.eq('ELIGIBLE')]
        pref={'STRONG BUY':0,'BUY':1,'BUY ON PULLBACK':2,'WATCH':3,'AVOID':4}
        r['_p']=r.Signal.map(pref).fillna(9)
        r=r.sort_values(['_p','Overall'],ascending=[True,False]).head(5)
        for _,x in r.iterrows():
            rows.append({'AssetClass':'Stock','Instrument':x.Symbol,'Decision':x.Signal,'Score':x.Overall,'Confidence':x.Confidence,'Risk':x.get('RiskLevel',''),'Horizon':x.Category,'Reason':f"Entry {x.get('EntryStatus','')} • R:R {x.get('RR','')}"})
    # Mutual funds.
    if mf is not None and not mf.empty:
        order={'INVEST / ACCUMULATE':0,'WATCH':1,'AVOID':2}
        m=mf.copy();m['_p']=m.Action.map(order).fillna(9);m=m.sort_values(['_p','Overall'],ascending=[True,False]).head(3)
        for _,x in m.iterrows():
            rows.append({'AssetClass':'Mutual Fund','Instrument':x.Scheme,'Decision':x.Action,'Score':x.Overall,'Confidence':x.Confidence,'Risk':x.Risk,'Horizon':'Long Term','Reason':f"3Y CAGR {x.get('3Y_CAGR%',np.nan)}% • Drawdown {x.get('MaxDrawdown%',np.nan)}%"})
    # Fixed income.
    if bonds is not None and not bonds.empty:
        order={'CONSIDER':0,'WATCH':1,'AVOID':2}
        b=bonds.copy();b['_p']=b.Action.map(order).fillna(9);b=b.sort_values(['_p','Overall'],ascending=[True,False]).head(3)
        for _,x in b.iterrows():
            rows.append({'AssetClass':'Fixed Income','Instrument':x.Instrument,'Decision':x.Action,'Score':x.Overall,'Confidence':x.get('Risk',''),'Risk':x.Risk,'Horizon':f"{x.get('MaturityYears','')}Y",'Reason':f"Yield/YTM {x.get('Yield%',np.nan)}% • Credit {x.get('CreditRisk','')}"})
    # Physical gold/silver using saved physical quote + proxy trend.
    state=load_metal_state()
    for metal in ['GOLD','SILVER']:
        q=float(state.get(metal,{}).get('quote',0) or 0)
        if q<=0:continue
        mcfg=cfg.get('precious_assets',{}).get(metal,{})
        proxy=None
        symbols=set(nse_history.Symbol.astype(str)) if nse_history is not None and not nse_history.empty else set()
        for s in mcfg.get('symbols',[]):
            if s in symbols:proxy=s;break
        if not proxy:continue
        g=nse_history[nse_history.Symbol.astype(str).eq(proxy)].copy()
        cards,_=analyze_asset(g,proxy,metal,'METAL','₹')
        if cards.empty:continue
        x=cards[cards.Category.eq('LONG')].iloc[0]
        dec,reason=timing_decision(x)
        rows.append({'AssetClass':f'Physical {metal.title()}','Instrument':metal,'Decision':dec,'Score':x.Overall,'Confidence':x.Confidence,'Risk':x.Risk,'Horizon':'6M–3Y','Reason':reason})
    # Crypto — cached data only; no network call here.
    cm=crypto_meta(); fx=float(cm.get('usd_inr') or 0)
    crypt=[]
    for sym,(name,pair) in crypto_universe().items():
        g=load_crypto(sym)
        if g is None or g.empty:continue
        cards,_=analyze_asset(g,sym,name,'CRYPTO','$')
        if cards.empty:continue
        x=cards[cards.Category.eq('SHORT')].iloc[0]
        crypt.append((x.Overall,sym,name,x))
    for _,sym,name,x in sorted(crypt,key=lambda t:t[0],reverse=True)[:3]:
        rows.append({'AssetClass':'Crypto','Instrument':sym,'Decision':x.Signal,'Score':x.Overall,'Confidence':x.Confidence,'Risk':x.Risk,'Horizon':'Short / Medium','Reason':x.Reason})
    out=pd.DataFrame(rows)
    if not out.empty:
        out['Score']=pd.to_numeric(out.Score,errors='coerce')
        out=out.sort_values('Score',ascending=False).reset_index(drop=True)
    return out


def save(df):
    OUT.parent.mkdir(parents=True,exist_ok=True)
    df.to_csv(OUT,index=False)
    if df is not None and not df.empty:
        h=df.copy();h['SnapshotAt']=pd.Timestamp.now().isoformat(timespec='seconds');h['SnapshotDate']=pd.Timestamp.now().date().isoformat()
        if HISTORY.exists():
            try:old=pd.read_csv(HISTORY)
            except Exception:old=pd.DataFrame()
            if not old.empty:
                key=set((old.SnapshotDate.astype(str)+'|'+old.AssetClass.astype(str)+'|'+old.Instrument.astype(str)).tolist()) if all(c in old.columns for c in ['SnapshotDate','AssetClass','Instrument']) else set()
                nk=h.SnapshotDate.astype(str)+'|'+h.AssetClass.astype(str)+'|'+h.Instrument.astype(str)
                h=h[~nk.isin(key)]
            if not h.empty:pd.concat([old,h],ignore_index=True,sort=False).to_csv(HISTORY,index=False)
        else:h.to_csv(HISTORY,index=False)


def load():
    if not OUT.exists():return pd.DataFrame()
    try:return pd.read_csv(OUT)
    except Exception:return pd.DataFrame()


def load_history():
    if not HISTORY.exists():return pd.DataFrame()
    try:return pd.read_csv(HISTORY)
    except Exception:return pd.DataFrame()
