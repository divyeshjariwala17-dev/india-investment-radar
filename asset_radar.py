from __future__ import annotations
import numpy as np, pandas as pd
from radar_engine import add_indicators, technical_score, momentum_score, trade_levels, clamp


def structure_score(r):
    """Non-company quality/market-structure score for metals/crypto.
    This intentionally replaces stock fundamentals for non-equity assets.
    """
    s=0.0
    if pd.notna(r.get('EMA21')) and pd.notna(r.get('EMA50')):
        s += 25 if r.Close > r.EMA21 > r.EMA50 else (15 if r.Close > r.EMA50 else 5)
    if pd.notna(r.get('Ret60')):
        s += clamp((r.Ret60 + 15) * 1.0, 0, 25)
    if pd.notna(r.get('VolRatio')):
        s += clamp((r.VolRatio - .5) * 16, 0, 15)
    if pd.notna(r.get('RSI14')):
        s += 15 if 48 <= r.RSI14 <= 70 else (8 if 40 <= r.RSI14 <= 78 else 2)
    if pd.notna(r.get('High60')) and r.High60:
        dist=(r.High60-r.Close)/r.High60*100
        s += 15 if 0 <= dist <= 10 else (8 if dist <= 20 else 2)
    ap=(r.ATR14/r.Close*100) if pd.notna(r.get('ATR14')) and r.Close else np.nan
    if pd.notna(ap):
        s += 5 if ap <= 4 else (3 if ap <= 8 else 1)
    return clamp(s)


def risk_level(g, asset_type='METAL'):
    if len(g)<30:return 'UNVERIFIED'
    rets=g.Close.pct_change().dropna()
    ann=rets.std()*np.sqrt(252)*100 if not rets.empty else np.nan
    atrp=(g.iloc[-1].ATR14/g.iloc[-1].Close*100) if pd.notna(g.iloc[-1].ATR14) else np.nan
    if asset_type=='CRYPTO':
        if (pd.notna(ann) and ann>=85) or (pd.notna(atrp) and atrp>=7):return 'VERY HIGH'
        if (pd.notna(ann) and ann>=55) or (pd.notna(atrp) and atrp>=4):return 'HIGH'
        return 'MEDIUM'
    else:
        if (pd.notna(ann) and ann>=35) or (pd.notna(atrp) and atrp>=4):return 'HIGH'
        if (pd.notna(ann) and ann>=18) or (pd.notna(atrp) and atrp>=2):return 'MEDIUM'
        return 'LOW'


def _backtest(g, category='SWING', min_score=72):
    if len(g)<140:return 0, np.nan
    horizon={'SWING':20,'SHORT':65,'LONG':126}.get(category,20)
    step={'SWING':5,'SHORT':10,'LONG':21}.get(category,5)
    wins=losses=0
    start=max(80, len(g)-360)
    for i in range(start, len(g)-horizon, step):
        sub=g.iloc[:i+1]
        r=sub.iloc[-1]
        t=technical_score(r);m=momentum_score(r);q=structure_score(r)
        w={'SWING':(.55,.35,.10),'SHORT':(.45,.35,.20),'LONG':(.35,.30,.35)}[category]
        overall=t*w[0]+m*w[1]+q*w[2]
        if overall<min_score:continue
        lv=trade_levels(sub,category)
        fut=g.iloc[i+1:i+1+horizon]
        hit_t=(fut.High>=lv['t1'])
        hit_s=(fut.Low<=lv['stop'])
        if not hit_t.any() and not hit_s.any():continue
        ti=hit_t.idxmax() if hit_t.any() else None
        si=hit_s.idxmax() if hit_s.any() else None
        # Conservative on ambiguity / same or earlier stop.
        if si is not None and (ti is None or si<=ti):losses+=1
        else:wins+=1
    n=wins+losses
    return n, round(wins/n*100,1) if n else np.nan


def analyze_asset(history: pd.DataFrame, symbol: str, name: str, asset_type='METAL', currency='₹'):
    if history is None or history.empty:return pd.DataFrame(), pd.DataFrame()
    g=history.copy().sort_values('Date')
    g=add_indicators(g)
    if len(g)<60:return pd.DataFrame(),g
    rows=[]
    for cat in ['SWING','SHORT','LONG']:
        need={'SWING':60,'SHORT':120,'LONG':180}[cat]
        if len(g)<need:continue
        r=g.iloc[-1]
        t=technical_score(r);m=momentum_score(r);q=structure_score(r)
        w={'SWING':(.55,.35,.10),'SHORT':(.45,.35,.20),'LONG':(.35,.30,.35)}[cat]
        overall=t*w[0]+m*w[1]+q*w[2]
        lv=trade_levels(g,cat)
        n,wr=_backtest(g,cat)
        risk=risk_level(g,asset_type)
        conf='HIGH' if n>=25 and pd.notna(wr) and wr>=60 else ('MEDIUM' if n>=12 and pd.notna(wr) and wr>=52 else 'LOW')
        if asset_type=='CRYPTO' and risk=='VERY HIGH' and conf=='HIGH':conf='MEDIUM'
        if overall>=85 and t>=80 and m>=80 and lv['rr']>=2 and n>=20 and pd.notna(wr) and wr>=60:
            sig='STRONG BUY'
        elif overall>=78 and lv['rr']>=1.7:
            sig='BUY'
        elif overall>=70:
            sig='WATCH'
        else:sig='AVOID'
        cur=lv['current'];est=lv['entry_high']
        if cur>est*1.025 and sig in ('STRONG BUY','BUY'):entry='WAIT FOR PULLBACK'
        elif lv['entry_low']<=cur<=est*1.01:entry='ENTRY VALID'
        else:entry='WATCH ENTRY'
        reasons=[]
        if t>=80:reasons.append('Technical trend is strong')
        elif t>=70:reasons.append('Technical trend passes')
        if m>=80:reasons.append('Momentum is strong')
        elif m>=70:reasons.append('Momentum passes')
        if q>=70:reasons.append('Market structure / asset trend passes')
        if lv['rr']>=2:reasons.append('Risk:Reward is 2.0 or better')
        if n>=20 and pd.notna(wr):reasons.append(f'Historical setup evidence: {n} signals, {wr}% win rate')
        if asset_type=='CRYPTO':reasons.append('Crypto trades 24/7 and carries higher gap/volatility risk')
        if not reasons:
            reasons.append('Current trend, momentum and structure do not provide enough evidence for a stronger rating')
        if sig=='STRONG BUY':
            change='Downgrade if price leaves the valid entry zone, trend/momentum weakens, Risk:Reward falls below 2.0, or historical evidence no longer meets the strict gate.'
        elif sig=='BUY':
            change='Upgrade needs stronger overall/technical/momentum evidence; downgrade if entry becomes stretched, trend weakens or Risk:Reward falls below the minimum.'
        elif sig=='WATCH':
            change='Upgrade requires price to enter a valid zone with stronger trend/momentum and acceptable Risk:Reward.'
        else:
            change='Upgrade requires a clear improvement in trend, momentum, market structure and Risk:Reward.'
        rows.append({
            'Asset':name,'Symbol':symbol,'AssetType':asset_type,'Category':cat,'Signal':sig,'EntryStatus':entry,
            'Current':round(cur,4),'EntryLow':round(lv['entry_low'],4),'EntryHigh':round(lv['entry_high'],4),
            'S1':round(lv['s1'],4),'S2':round(lv['s2'],4),'R1':round(lv['r1'],4),'R2':round(lv['r2'],4),
            'Target1':round(lv['t1'],4),'Target2':round(lv['t2'],4),'Potential1%':round(lv['t1_pct'],1),
            'Potential2%':round(lv['t2_pct'],1),'StopLoss':round(lv['stop'],4),'Risk%':round(lv['risk_pct'],1),
            'RR':round(lv['rr'],2),'Duration':{'SWING':'5–20 days','SHORT':'3–12 weeks','LONG':'6–24 months'}[cat],
            'Technical':round(t,1),'Momentum':round(m,1),'Structure':round(q,1),'Overall':round(overall,1),
            'HistoricalSignals':int(n),'WinRate%':wr,'Risk':risk,'Confidence':conf,'Currency':currency,
            'Reason':' • '.join(reasons),'WhatChanges':change,'DataDate':str(pd.to_datetime(r.Date).date())
        })
    return pd.DataFrame(rows),g
