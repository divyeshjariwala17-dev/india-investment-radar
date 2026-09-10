from __future__ import annotations
import numpy as np, pandas as pd

HORIZONS = [("Next Day",1),("1 Week",5),("15 Days",10),("1 Month",21),("3 Months",63)]

def _ema(s,n): return s.ewm(span=n,adjust=False).mean()

def _rsi(s,n=14):
    d=s.diff(); up=d.clip(lower=0).rolling(n).mean(); dn=(-d.clip(upper=0)).rolling(n).mean()
    rs=up/dn.replace(0,np.nan)
    return (100-100/(1+rs)).fillna(50)

def build_market_proxy(history: pd.DataFrame, universe_size=200):
    if history.empty: return pd.DataFrame()
    h=history.copy().sort_values(["Symbol","Date"])
    recent=h.groupby("Symbol").tail(60)
    if "TradedValue" in recent and recent["TradedValue"].notna().any():
        liquid=recent.groupby("Symbol")["TradedValue"].median().sort_values(ascending=False).head(universe_size).index
    else:
        liquid=recent.groupby("Symbol")["Volume"].median().sort_values(ascending=False).head(universe_size).index
    h=h[h.Symbol.isin(liquid)].copy()
    h["Ret"]=h.groupby("Symbol").Close.pct_change()
    daily=h.groupby("Date").agg(
        ProxyRet=("Ret","median"),
        Advancers=("Ret",lambda x:(x>0).mean()*100),
        Count=("Symbol","nunique")
    ).reset_index().sort_values("Date")
    daily["ProxyRet"]=daily.ProxyRet.fillna(0)
    daily["Proxy"]=100*(1+daily.ProxyRet).cumprod()
    daily["EMA21"]=_ema(daily.Proxy,21); daily["EMA50"]=_ema(daily.Proxy,50); daily["RSI14"]=_rsi(daily.Proxy)
    daily["Mom5"]=daily.Proxy.pct_change(5)*100; daily["Mom21"]=daily.Proxy.pct_change(21)*100
    daily["Vol21"]=daily.ProxyRet.rolling(21).std()*np.sqrt(252)*100
    daily["Regime"]=np.select(
        [(daily.Proxy>daily.EMA21)&(daily.EMA21>daily.EMA50)&(daily.Advancers>=50),
         (daily.Proxy<daily.EMA21)&(daily.EMA21<daily.EMA50)&(daily.Advancers<45)],
        ["BULLISH","WEAK"],default="CAUTIOUS")
    return daily

def outlook(history: pd.DataFrame, universe_size=200, market_context=None):
    d=build_market_proxy(history,universe_size)
    if len(d)<120: return pd.DataFrame(), d
    cur=d.iloc[-1]
    cand=d.iloc[:-65].copy(); cand=cand[cand.Regime==cur.Regime]
    if len(cand)>=30: cand=cand[(cand.Advancers-cur.Advancers).abs()<=18]
    if len(cand)>=30 and pd.notna(cur.Mom21): cand=cand[(cand.Mom21-cur.Mom21).abs()<=8]
    if len(cand)<20:
        cand=d.iloc[:-65].copy(); cand=cand[cand.Regime==cur.Regime]
    rows=[]
    for label,n in HORIZONS:
        vals=[]
        for idx in cand.index:
            try:
                pos=d.index.get_loc(idx)
                a=float(d.iloc[pos].Proxy); b=float(d.iloc[pos+n].Proxy)
                vals.append((b/a-1)*100)
            except Exception: pass
        s=pd.Series(vals,dtype=float).dropna()
        if s.empty:
            rows.append({"Horizon":label,"Sessions":n,"Bias":"UNAVAILABLE","ProbabilityPositive%":np.nan,"BaseProbabilityPositive%":np.nan,"ContextAdjustmentPP":0.0,"ContextRegime":str((market_context or {}).get('Regime','UNAVAILABLE')) if isinstance(market_context,dict) else 'UNAVAILABLE',"MedianReturn%":np.nan,"RangeLow%":np.nan,"RangeHigh%":np.nan,"Sample":0,"Confidence":"LOW","ForecastMethod":"Insufficient historical analogue sample"}); continue
        base_pp=(s>0).mean()*100; med=s.median(); lo=s.quantile(.20); hi=s.quantile(.80)
        # Historical analogue probability is the base. Current intelligence can only make a small, transparent
        # context adjustment because FII/derivatives history is not assumed to exist for every historical sample.
        ctx_score=np.nan; ctx_regime='UNAVAILABLE'; ctx_adj=0.0
        if isinstance(market_context,dict):
            try:ctx_score=float(market_context.get('Score',np.nan))
            except Exception:ctx_score=np.nan
            ctx_regime=str(market_context.get('Regime','UNAVAILABLE'))
        if pd.notna(ctx_score):
            decay={1:1.0,5:.8,10:.65,21:.45,63:.25}.get(n,.4)
            ctx_adj=max(-7.0,min(7.0,(ctx_score-50.0)*0.20*decay))
        pp=max(5.0,min(95.0,base_pp+ctx_adj))
        bias="BULLISH" if pp>=60 and med>0 else ("BEARISH" if pp<=40 and med<0 else "SIDEWAYS / MIXED")
        edge=abs(pp-50); conf="HIGH" if len(s)>=80 and edge>=15 else ("MEDIUM" if len(s)>=35 and edge>=8 else "LOW")
        if ctx_regime=='RISK-OFF' and conf=='HIGH':conf='MEDIUM'
        rows.append({"Horizon":label,"Sessions":n,"Bias":bias,"ProbabilityPositive%":round(pp,1),
                     "BaseProbabilityPositive%":round(base_pp,1),"ContextAdjustmentPP":round(ctx_adj,1),"ContextRegime":ctx_regime,
                     "MedianReturn%":round(med,2),"RangeLow%":round(lo,2),"RangeHigh%":round(hi,2),"Sample":len(s),"Confidence":conf,
                     "ForecastMethod":"Historical analogue + bounded current market-intelligence adjustment"})
    return pd.DataFrame(rows),d
