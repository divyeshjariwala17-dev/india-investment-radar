from __future__ import annotations
import numpy as np, pandas as pd

ACTION_RANK={'STRONG BUY':0,'BUY':1,'BUY ON PULLBACK':2,'WATCH':3,'AVOID':4}


def _num(v,default=np.nan):
    try:
        x=float(v);return x if np.isfinite(x) else default
    except Exception:return default


def money(v,dec=2):
    x=_num(v)
    if pd.isna(x):return '—'
    return f'₹{x:,.{dec}f}'


def pct(v,dec=1,sign=True):
    x=_num(v)
    if pd.isna(x):return '—'
    return f'{x:+.{dec}f}%' if sign else f'{x:.{dec}f}%'


def stock_rows(radar,top_n=5):
    if radar is None or radar.empty:return pd.DataFrame()
    x=radar.copy()
    if 'Eligibility' in x.columns:x=x[x.Eligibility.astype(str).eq('ELIGIBLE')]
    x=x[x.Signal.astype(str).isin(['STRONG BUY','BUY','BUY ON PULLBACK','WATCH'])].copy()
    if x.empty:return x
    x['_rank']=x.Signal.map(ACTION_RANK).fillna(9)
    x=x.sort_values(['_rank','Overall'],ascending=[True,False]).drop_duplicates('Symbol').head(top_n)
    rows=[]
    for _,r in x.iterrows():
        cur=_num(r.get('Current'));t1=_num(r.get('Target1'));t2=_num(r.get('Target2'));stop=_num(r.get('StopLoss'))
        rows.append({
            'Action':str(r.get('Signal','')),'Instrument':str(r.get('Symbol','')),'Company':str(r.get('Company','')),
            'Current':money(cur),'Entry':f"{money(r.get('EntryLow'))} – {money(r.get('EntryHigh'))}",
            'Target 1':money(t1),'T1 Gain ₹':money((t1-cur) if pd.notna(cur) and pd.notna(t1) else np.nan),'T1 Gain %':pct(r.get('Potential1%')),
            'Target 2':money(t2),'T2 Gain ₹':money((t2-cur) if pd.notna(cur) and pd.notna(t2) else np.nan),'T2 Gain %':pct(r.get('Potential2%')),
            'Stop':money(stop),'Downside ₹':money((stop-cur) if pd.notna(cur) and pd.notna(stop) else np.nan),
            'Downside %':pct(((stop-cur)/cur*100) if pd.notna(cur) and cur and pd.notna(stop) else np.nan),
            'R:R':round(_num(r.get('RR')),2) if pd.notna(_num(r.get('RR'))) else np.nan,
            'Duration':str(r.get('Duration','')),'Confidence':str(r.get('Confidence','')),'Score':_num(r.get('Overall')),
            'Market Intel':str(r.get('InstitutionalBias',''))+' / '+str(r.get('BreadthBias','')) if str(r.get('InstitutionalBias','')) else '',
            'Market Score':_num(r.get('MarketIntelligenceScore')),'Delivery %':_num(r.get('DeliveryPct')),
            'Surveillance':str(r.get('SurveillanceRisk','')),'Entry Status':str(r.get('EntryStatus','')),
        })
    return pd.DataFrame(rows)


def mf_rows(mf,top_n=3):
    if mf is None or mf.empty:return pd.DataFrame()
    x=mf[mf.Action.astype(str).isin(['INVEST / ACCUMULATE','WATCH'])].copy()
    if x.empty:return x
    x['_r']=x.Action.astype(str).map({'INVEST / ACCUMULATE':0,'WATCH':1}).fillna(9)
    x=x.sort_values(['_r','Overall'],ascending=[True,False]).head(top_n)
    rows=[]
    for _,r in x.iterrows():
        rows.append({'Action':str(r.get('Action','')),'Scheme':str(r.get('Scheme','')),'NAV':money(r.get('NAV'),4),'NAV Date':str(r.get('NAVDate','')),
                     '1Y':pct(r.get('1Y%')),'3Y CAGR':pct(r.get('3Y_CAGR%')),'5Y CAGR':pct(r.get('5Y_CAGR%')),
                     'Max Drawdown':pct(r.get('MaxDrawdown%')),'Risk':str(r.get('Risk','')),'Confidence':str(r.get('Confidence','')),'Score':_num(r.get('Overall'))})
    return pd.DataFrame(rows)


def fixed_rows(bonds,top_n=3):
    if bonds is None or bonds.empty:return pd.DataFrame()
    x=bonds[bonds.Action.astype(str).isin(['CONSIDER','WATCH'])].copy()
    if x.empty:return x
    x['_r']=x.Action.astype(str).map({'CONSIDER':0,'WATCH':1}).fillna(9)
    x=x.sort_values(['_r','Overall'],ascending=[True,False],na_position='last').head(top_n)
    rows=[]
    for _,r in x.iterrows():
        y=_num(r.get('Yield%'));mat=_num(r.get('MaturityYears'))
        rows.append({'Action':str(r.get('Action','')),'Instrument':str(r.get('Instrument','')),'Yield/YTM':pct(y,2,False),'Maturity':f'{mat:.2f}Y' if pd.notna(mat) else '—',
                     'Expected to Maturity':pct(r.get('ExpectedToMaturity%'),2,True),'Risk':str(r.get('Risk','')),'Credit':str(r.get('CreditRisk','')),'Liquidity':str(r.get('Liquidity','')),'Score':_num(r.get('Overall'))})
    return pd.DataFrame(rows)


def ipo_rows(ipos,top_n=3):
    if ipos is None or ipos.empty:return pd.DataFrame()
    x=ipos[ipos.Decision.astype(str).isin(['STRONG APPLY','APPLY','WATCH'])].head(top_n)
    rows=[]
    for _,r in x.iterrows():
        lo=_num(r.get('PriceLow₹'));hi=_num(r.get('PriceHigh₹'));lot=_num(r.get('LotSize'));cost=_num(r.get('OneLotCost₹'))
        rows.append({'Action':str(r.get('Decision','')),'Company':str(r.get('Company','')),'Board':str(r.get('Board','')),
                     'Price Band':f'{money(lo)} – {money(hi)}','Lot Size':int(lot) if pd.notna(lot) else '—','One Lot Cost':money(cost,0),
                     'Listing Score':_num(r.get('ListingScore')),'Long-Term Score':_num(r.get('LongTermScore')),'Risk':str(r.get('Risk','')),'Confidence':str(r.get('Confidence',''))})
    return pd.DataFrame(rows)


def overall_action_status(data_health):
    if data_health is None or data_health.empty:return 'REVIEW REQUIRED','Data health unavailable'
    critical=data_health[data_health.Data.isin(['NSE price history','Corporate events','Corporate announcements','Mutual Fund universe / NAV'])]
    if critical.empty:return 'REVIEW REQUIRED','Critical-source status unavailable'
    bad=critical[critical.Status.astype(str).isin(['MISSING','OLD'])]
    stale=critical[critical.Status.astype(str).isin(['STALE'])]
    if not bad.empty:return 'DO NOT ACT','Critical data missing/old: '+', '.join(bad.Data.astype(str).tolist())
    if not stale.empty:return 'REVIEW REQUIRED','Critical data stale: '+', '.join(stale.Data.astype(str).tolist())
    return 'ACTIONABLE','Critical stored datasets are within configured freshness limits'
