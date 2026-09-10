from __future__ import annotations
from pathlib import Path
import json, time
import requests, pandas as pd, numpy as np

BASE=Path(__file__).resolve().parent
DIR=BASE/'data'/'macro';DIR.mkdir(parents=True,exist_ok=True)
SUMMARY=DIR/'summary.csv';META=DIR/'meta.json'

SERIES={
    'Nifty 50':'^NSEI','Bank Nifty':'^NSEBANK','India VIX':'^INDIAVIX','USD/INR':'INR=X','Crude Oil':'CL=F',
    'Global Gold':'GC=F','Global Silver':'SI=F','S&P 500':'^GSPC','Nasdaq':'^IXIC'
}


def _fetch(symbol,timeout=10):
    url=f'https://query1.finance.yahoo.com/v8/finance/chart/{symbol}'
    r=requests.get(url,params={'range':'6mo','interval':'1d','events':'history'},headers={'User-Agent':'Mozilla/5.0'},timeout=timeout)
    r.raise_for_status();j=r.json()['chart']['result'][0]
    ts=j.get('timestamp') or [];q=(j.get('indicators',{}).get('quote') or [{}])[0]
    close=q.get('close') or []
    rows=[]
    for t,c in zip(ts,close):
        if c is not None:rows.append([pd.to_datetime(t,unit='s'),float(c)])
    return pd.DataFrame(rows,columns=['Date','Close']).drop_duplicates('Date').sort_values('Date')


def refresh(status_cb=None):
    rows=[];errors={}
    for i,(name,sym) in enumerate(SERIES.items()):
        if status_cb:status_cb(f'Macro {i+1}/{len(SERIES)}: {name}')
        try:
            d=_fetch(sym)
            if d.empty:raise RuntimeError('no data')
            d.to_csv(DIR/(name.replace('/','_').replace(' ','_')+'.csv'),index=False)
            s=d.Close;ema21=s.ewm(span=21,adjust=False).mean().iloc[-1]
            r1=(s.iloc[-1]/s.iloc[-2]-1)*100 if len(s)>1 else np.nan
            r5=(s.iloc[-1]/s.iloc[-6]-1)*100 if len(s)>5 else np.nan
            r21=(s.iloc[-1]/s.iloc[-22]-1)*100 if len(s)>21 else np.nan
            trend='BULLISH' if s.iloc[-1]>ema21 and (pd.isna(r21) or r21>=0) else ('BEARISH' if s.iloc[-1]<ema21 and (pd.isna(r21) or r21<0) else 'MIXED')
            rows.append({'Indicator':name,'Symbol':sym,'Latest':s.iloc[-1],'Date':d.Date.iloc[-1].date(),'1D%':round(r1,2),'1W%':round(r5,2),'1M%':round(r21,2),'Trend':trend})
        except Exception as e:errors[name]=str(e)
        time.sleep(.05)
    out=pd.DataFrame(rows)
    if not out.empty:out.to_csv(SUMMARY,index=False)
    META.write_text(json.dumps({'updated_at':pd.Timestamp.now().isoformat(timespec='seconds'),'ok':len(rows),'failed':len(errors),'errors':errors},indent=2),encoding='utf-8')
    return out


def load():
    if not SUMMARY.exists():return pd.DataFrame()
    try:return pd.read_csv(SUMMARY)
    except Exception:return pd.DataFrame()


def meta():
    if not META.exists():return {}
    try:return json.loads(META.read_text(encoding='utf-8'))
    except Exception:return {}


def india_context(df=None):
    d=load() if df is None else df
    if d is None or d.empty:return {'Context':'UNAVAILABLE','Score':np.nan,'Reasons':[]}
    m={str(r.Indicator):r for _,r in d.iterrows()}
    score=50;reasons=[]
    for key,wt in [('Nifty 50',12),('Bank Nifty',8),('S&P 500',5),('Nasdaq',4)]:
        r=m.get(key)
        if r is not None:
            if r.Trend=='BULLISH':score+=wt;reasons.append(key+' supportive')
            elif r.Trend=='BEARISH':score-=wt;reasons.append(key+' weak')
    usd=m.get('USD/INR')
    if usd is not None and pd.notna(usd.get('1M%')):
        if float(usd['1M%'])>2:score-=4;reasons.append('INR weakness is a risk')
        elif float(usd['1M%'])<-1:score+=2;reasons.append('INR strengthening is mildly supportive')
    crude=m.get('Crude Oil')
    if crude is not None and pd.notna(crude.get('1M%')):
        if float(crude['1M%'])>8:score-=5;reasons.append('Crude rise is a macro risk for India')
        elif float(crude['1M%'])<-5:score+=3;reasons.append('Lower crude is supportive for India')
    score=max(0,min(100,score))
    context='SUPPORTIVE' if score>=65 else ('RISK-OFF' if score<=40 else 'MIXED')
    return {'Context':context,'Score':round(score,1),'Reasons':reasons}
