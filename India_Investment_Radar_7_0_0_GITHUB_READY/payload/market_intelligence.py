from __future__ import annotations
from pathlib import Path
from datetime import datetime
import json, time, urllib.parse, xml.etree.ElementTree as ET
import requests, pandas as pd, numpy as np

BASE=Path(__file__).resolve().parent
DIR=BASE/'data'/'market_intelligence';DIR.mkdir(parents=True,exist_ok=True)
FLOWS=DIR/'fii_dii.csv'; NEWS=DIR/'market_news.csv'; META=DIR/'meta.json'
HEADERS={
    'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36',
    'Accept':'application/json,text/plain,*/*','Referer':'https://www.nseindia.com/reports/fii-dii'
}
DEFAULT_NEWS_TOPICS=[
    'India stock market Nifty Sensex','RBI India interest rates inflation','India rupee crude oil market',
    'India mutual funds AMFI','India IPO market','India gold silver prices'
]
NEG=('CRASH','FRAUD','DEFAULT','INSOLVENCY','NCLT','WAR','SANCTION','DOWNGRADE','PLUNGE','SELL-OFF','SELL OFF','RECESSION','RAID','PENALTY','BAN')
POS=('RECORD HIGH','UPGRADE','BEATS ESTIMATES','STRONG GROWTH','RATE CUT','INFLOW','RALLY','SURGE','EXPANSION')

def _num(v):
    try:return float(str(v).replace(',','').replace('₹','').strip())
    except Exception:return np.nan

def _date(v):
    try:return pd.to_datetime(v,dayfirst=True,errors='coerce').date().isoformat()
    except Exception:return ''

def _session():
    s=requests.Session()
    try:s.get('https://www.nseindia.com/',headers=HEADERS,timeout=12)
    except Exception:pass
    return s

def refresh_fii_dii(status_cb=None):
    """Fetch official NSE provisional FII/FPI & DII cash-market activity and append daily history.
    NSE notes that same-day figures are provisional; final FPI figures are referenced to NSDL/CDSL.
    """
    if status_cb:status_cb('FII/DII: initializing NSE session...')
    errors=[];rows=[]
    try:
        s=_session();
        if status_cb:status_cb('FII/DII: downloading official NSE institutional activity...')
        r=s.get('https://www.nseindia.com/api/fiidiiTradeReact',headers=HEADERS,timeout=25)
        r.raise_for_status(); data=r.json()
        if isinstance(data,dict): data=data.get('data') or data.get('records') or [data]
        if not isinstance(data,list):data=[]
        for x in data:
            if not isinstance(x,dict):continue
            # Current NSE schema generally returns one row per category.
            cat=str(x.get('category') or x.get('Category') or x.get('clientType') or '').strip().upper()
            dt=_date(x.get('date') or x.get('Date') or x.get('tradeDate'))
            buy=_num(x.get('buyValue') or x.get('buyvalue') or x.get('buy'))
            sell=_num(x.get('sellValue') or x.get('sellvalue') or x.get('sell'))
            net=_num(x.get('netValue') or x.get('netvalue') or x.get('net'))
            if cat:
                if pd.isna(net) and pd.notna(buy) and pd.notna(sell):net=buy-sell
                rows.append({'Date':dt,'Category':cat,'Buy₹Cr':buy,'Sell₹Cr':sell,'Net₹Cr':net,'Status':'PROVISIONAL','Source':'NSE FII/DII'})
            else:
                # Defensive support for APIs that return FII/DII fields in a single day record.
                for label,prefix in [('FII/FPI','fii'),('DII','dii')]:
                    b=_num(x.get(prefix+'buy') or x.get(prefix+'Buy'));se=_num(x.get(prefix+'sell') or x.get(prefix+'Sell'));n=_num(x.get(prefix+'net') or x.get(prefix+'Net'))
                    if pd.notna(n) or pd.notna(b) or pd.notna(se):
                        if pd.isna(n) and pd.notna(b) and pd.notna(se):n=b-se
                        rows.append({'Date':dt,'Category':label,'Buy₹Cr':b,'Sell₹Cr':se,'Net₹Cr':n,'Status':'PROVISIONAL','Source':'NSE FII/DII'})
        new=pd.DataFrame(rows)
        if new.empty:raise RuntimeError('NSE returned no parseable FII/DII rows')
        old=load_fii_dii()
        out=pd.concat([old,new],ignore_index=True) if not old.empty else new
        out['Date']=out['Date'].astype(str);out['Category']=out['Category'].astype(str).str.upper()
        out=out.drop_duplicates(['Date','Category'],keep='last').sort_values(['Date','Category'])
        out.to_csv(FLOWS,index=False)
        return {'ok':True,'count':len(new),'message':f'FII/DII refreshed: {len(new)} official NSE row(s); same-day values are provisional.'}
    except Exception as e:
        errors.append(str(e))
        return {'ok':False,'count':0,'message':'FII/DII refresh unavailable: '+str(e)+'; last verified cache preserved.'}

def load_fii_dii():
    if FLOWS.exists():
        try:return pd.read_csv(FLOWS)
        except Exception:pass
    return pd.DataFrame(columns=['Date','Category','Buy₹Cr','Sell₹Cr','Net₹Cr','Status','Source'])

def institutional_summary(df=None):
    d=load_fii_dii() if df is None else df
    if d is None or d.empty:return {'Bias':'UNAVAILABLE','LatestDate':'','FIINet₹Cr':np.nan,'DIINet₹Cr':np.nan,'FII5D₹Cr':np.nan,'DII5D₹Cr':np.nan,'FII20D₹Cr':np.nan,'DII20D₹Cr':np.nan,'Score':np.nan}
    x=d.copy();x['Net₹Cr']=pd.to_numeric(x['Net₹Cr'],errors='coerce');x['DateParsed']=pd.to_datetime(x['Date'],errors='coerce');x=x.dropna(subset=['DateParsed'])
    if x.empty:return {'Bias':'UNAVAILABLE','LatestDate':''}
    piv=x.pivot_table(index='DateParsed',columns='Category',values='Net₹Cr',aggfunc='last').sort_index()
    fii_col=next((c for c in piv.columns if 'FII' in str(c) or 'FPI' in str(c)),None);dii_col=next((c for c in piv.columns if 'DII' in str(c)),None)
    fii=piv[fii_col] if fii_col else pd.Series(dtype=float); dii=piv[dii_col] if dii_col else pd.Series(dtype=float)
    latest=piv.index.max();fn=float(fii.dropna().iloc[-1]) if not fii.dropna().empty else np.nan;dn=float(dii.dropna().iloc[-1]) if not dii.dropna().empty else np.nan
    f5=float(fii.tail(5).sum()) if not fii.empty else np.nan;d5=float(dii.tail(5).sum()) if not dii.empty else np.nan;f20=float(fii.tail(20).sum()) if not fii.empty else np.nan;d20=float(dii.tail(20).sum()) if not dii.empty else np.nan
    score=50
    if pd.notna(fn):score+=8 if fn>0 else -8
    if pd.notna(f5):score+=12 if f5>0 else -12
    if pd.notna(f20):score+=10 if f20>0 else -10
    if pd.notna(d5):score+=4 if d5>0 else -4
    score=max(0,min(100,score));bias='SUPPORTIVE' if score>=62 else ('RISK-OFF' if score<=38 else 'MIXED')
    return {'Bias':bias,'LatestDate':latest.date().isoformat(),'FIINet₹Cr':round(fn,2) if pd.notna(fn) else np.nan,'DIINet₹Cr':round(dn,2) if pd.notna(dn) else np.nan,
            'FII5D₹Cr':round(f5,2) if pd.notna(f5) else np.nan,'DII5D₹Cr':round(d5,2) if pd.notna(d5) else np.nan,'FII20D₹Cr':round(f20,2) if pd.notna(f20) else np.nan,'DII20D₹Cr':round(d20,2) if pd.notna(d20) else np.nan,'Score':score}

def _news_risk(title):
    t=str(title).upper()
    if any(k in t for k in NEG):return 'RISK'
    if any(k in t for k in POS):return 'POSITIVE'
    return 'NEUTRAL'

def _rss(query,limit=20):
    u='https://news.google.com/rss/search?q='+urllib.parse.quote(query)+'&hl=en-IN&gl=IN&ceid=IN:en'
    r=requests.get(u,headers={'User-Agent':'Mozilla/5.0'},timeout=20);r.raise_for_status()
    root=ET.fromstring(r.content);rows=[]
    for item in root.findall('.//item')[:limit]:
        src=item.find('source')
        rows.append({'Published':item.findtext('pubDate') or '', 'Title':item.findtext('title') or '', 'Source':src.text if src is not None else '', 'Link':item.findtext('link') or '', 'Query':query})
    return rows

def refresh_market_news(topics=None,status_cb=None):
    topics=topics or DEFAULT_NEWS_TOPICS;rows=[];errors=[]
    for i,q in enumerate(topics,1):
        if status_cb:status_cb(f'Public market news {i}/{len(topics)}: {q}')
        try:rows.extend(_rss(q,15))
        except Exception as e:errors.append(f'{q}: {e}')
        time.sleep(.05)
    if rows:
        d=pd.DataFrame(rows);d['Risk']=d['Title'].map(_news_risk);d['FetchedAt']=pd.Timestamp.now().isoformat(timespec='seconds')
        d=d.drop_duplicates(['Title','Source'],keep='first')
        d.to_csv(NEWS,index=False)
    return {'ok':bool(rows),'count':len(rows),'message':f'Market news refreshed: {len(rows)} headline(s).' + (f' {len(errors)} topic(s) unavailable; last cache preserved for those.' if errors else '')}

def load_market_news():
    if NEWS.exists():
        try:return pd.read_csv(NEWS)
        except Exception:pass
    return pd.DataFrame(columns=['Published','Title','Source','Link','Query','Risk','FetchedAt'])

def refresh_stock_news(symbol,company='',status_cb=None):
    sym=str(symbol).strip().upper();company=str(company or '').strip();q=(company+' '+sym+' NSE India stock').strip()
    if status_cb:status_cb('Fetching public news context for '+sym+'...')
    try:
        rows=_rss(q,25);d=pd.DataFrame(rows);d['Risk']=d['Title'].map(_news_risk);d['FetchedAt']=pd.Timestamp.now().isoformat(timespec='seconds');d['Symbol']=sym
        out=DIR/'stock_news';out.mkdir(exist_ok=True);d.to_csv(out/f'{sym}.csv',index=False)
        return {'ok':True,'count':len(d),'message':f'{len(d)} public headlines cached for {sym}.'}
    except Exception as e:return {'ok':False,'count':0,'message':f'Public news unavailable for {sym}: {e}'}

def load_stock_news(symbol):
    p=DIR/'stock_news'/f'{str(symbol).strip().upper()}.csv'
    if p.exists():
        try:return pd.read_csv(p)
        except Exception:pass
    return pd.DataFrame()

def refresh_all(status_cb=None,news_topics=None):
    a=refresh_fii_dii(status_cb=status_cb);b=refresh_market_news(news_topics,status_cb=status_cb)
    meta={'updated_at':pd.Timestamp.now().isoformat(timespec='seconds'),'fii_dii':a,'news':b}
    META.write_text(json.dumps(meta,indent=2,default=str),encoding='utf-8')
    return {'ok':bool(a.get('ok') or b.get('ok')),'message':f"Institutional/news intelligence: FII-DII {'PASS' if a.get('ok') else 'WARN'}; News {'PASS' if b.get('ok') else 'WARN'}."}
