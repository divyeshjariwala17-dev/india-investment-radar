from __future__ import annotations
from pathlib import Path
from io import StringIO
import math, json, re
import numpy as np
import pandas as pd
import requests

BASE=Path(__file__).resolve().parent
DATA=BASE/'data'
DATA.mkdir(parents=True,exist_ok=True)
IPO_FILE=DATA/'ipo_watchlist.csv'

IPO_COLUMNS=[
    'IPO_ID','Company','Symbol','IssueType','Board','Status','OpenDate','CloseDate',
    'PriceLow₹','PriceHigh₹','LotSize','IssueSizeCr','FreshIssueCr','OFSCr',
    'EPS₹','NAV₹','PE','IndustryPE','RevenueGrowth3Y%','ProfitGrowth3Y%','ROE%','DebtEquity',
    'QIBSub','NIISub','RetailSub','TotalSub','GMP%','PromoterHoldingPost%','UseOfFundsQuality',
    'GovernanceRisk','BusinessQuality','Notes','Source','UpdatedAt'
]

NUMERIC=[c for c in IPO_COLUMNS if c.endswith('₹') or c.endswith('Cr') or c.endswith('%') or c in ['LotSize','PE','IndustryPE','DebtEquity','QIBSub','NIISub','RetailSub','TotalSub','BusinessQuality']]


def _blank(): return pd.DataFrame(columns=IPO_COLUMNS)

def _id(company):
    s=re.sub(r'[^A-Z0-9]+','-',str(company).upper()).strip('-')[:45]
    return 'IPO-'+s if s else 'IPO-NEW'


def normalize(df:pd.DataFrame):
    if df is None or df.empty:return _blank()
    x=df.copy()
    aliases={
        'company name':'Company','company':'Company','symbol':'Symbol','security type':'IssueType','issue type':'IssueType',
        'issue start date':'OpenDate','start date':'OpenDate','open date':'OpenDate','issue end date':'CloseDate','end date':'CloseDate','close date':'CloseDate',
        'price low':'PriceLow₹','price high':'PriceHigh₹','floor price':'PriceLow₹','cap price':'PriceHigh₹','lot size':'LotSize',
        'issue size':'IssueSizeCr','fresh issue':'FreshIssueCr','ofs':'OFSCr','eps':'EPS₹','nav':'NAV₹','p/e':'PE','pe':'PE','industry pe':'IndustryPE',
        'qib':'QIBSub','nii':'NIISub','retail':'RetailSub','subscription':'TotalSub','total subscription':'TotalSub','gmp':'GMP%','gmp%':'GMP%',
        'status':'Status','board':'Board','notes':'Notes','source':'Source'
    }
    ren={}
    for c in x.columns:
        k=str(c).strip().lower()
        if k in aliases:ren[c]=aliases[k]
    x=x.rename(columns=ren)
    for c in IPO_COLUMNS:
        if c not in x.columns:x[c]=''
    x=x[IPO_COLUMNS].copy()
    for c in NUMERIC:x[c]=pd.to_numeric(x[c],errors='coerce')
    for c in ['OpenDate','CloseDate']:
        x[c]=pd.to_datetime(x[c],errors='coerce').dt.date
    x['IPO_ID']=x['IPO_ID'].fillna('').astype(str).str.strip()
    empty=x['IPO_ID'].eq('')|x['IPO_ID'].str.lower().isin(['nan','none'])
    x.loc[empty,'IPO_ID']=[_id(v) for v in x.loc[empty,'Company']]
    x['IssueType']=x['IssueType'].fillna('').astype(str).replace({'':'IPO'})
    x['Board']=x['Board'].fillna('').astype(str).replace({'':'MAINBOARD'})
    x['Status']=x['Status'].fillna('').astype(str).str.upper()
    x['UseOfFundsQuality']=x['UseOfFundsQuality'].fillna('').astype(str).str.upper()
    x['GovernanceRisk']=x['GovernanceRisk'].fillna('').astype(str).str.upper()
    x['UpdatedAt']=pd.Timestamp.now().isoformat(timespec='seconds')
    return x


def load():
    if IPO_FILE.exists():
        try:return normalize(pd.read_csv(IPO_FILE))
        except Exception:pass
    return _blank()


def save(df):
    x=normalize(df);x.to_csv(IPO_FILE,index=False);return x


def template():
    today=pd.Timestamp.now().date().isoformat()
    return normalize(pd.DataFrame([{
        'Company':'Example IPO Ltd','Symbol':'','IssueType':'IPO','Board':'MAINBOARD','Status':'UPCOMING',
        'OpenDate':today,'CloseDate':today,'PriceLow₹':100,'PriceHigh₹':110,'LotSize':100,'IssueSizeCr':500,
        'FreshIssueCr':350,'OFSCr':150,'EPS₹':5,'NAV₹':40,'PE':22,'IndustryPE':28,'RevenueGrowth3Y%':20,
        'ProfitGrowth3Y%':25,'ROE%':18,'DebtEquity':0.4,'QIBSub':0,'NIISub':0,'RetailSub':0,'TotalSub':0,
        'GMP%':0,'PromoterHoldingPost%':65,'UseOfFundsQuality':'GOOD','GovernanceRisk':'LOW','BusinessQuality':75,
        'Notes':'Replace this example with actual IPO data.','Source':'Manual / NSE / SEBI'
    }]))


def refresh_nse_current(status_cb=None):
    """Best-effort official NSE current-issues refresh. If NSE blocks automated HTML access,
    existing local data remains untouched. Official source link is still shown in the UI.
    """
    url='https://www.nseindia.com/market-data/all-upcoming-issues-ipo'
    headers={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122 Safari/537.36','Accept-Language':'en-US,en;q=0.9'}
    if status_cb:status_cb('Checking official NSE IPO/current-issues page...')
    try:
        s=requests.Session();s.get('https://www.nseindia.com',headers=headers,timeout=15)
        r=s.get(url,headers=headers,timeout=20);r.raise_for_status()
        tables=pd.read_html(StringIO(r.text))
        found=[]
        for t in tables:
            cols=' '.join(map(str,t.columns)).lower()
            if 'company' in cols and ('start' in cols or 'issue' in cols):
                found.append(t)
        if not found:
            return {'ok':False,'message':'NSE page opened but no machine-readable IPO table was found. Use manual/import mode; official links remain available.'}
        raw=pd.concat(found,ignore_index=True)
        # Flatten multi-index columns where necessary.
        raw.columns=[' '.join([str(x) for x in c if str(x)!='nan']).strip() if isinstance(c,tuple) else str(c) for c in raw.columns]
        out=normalize(raw)
        old=load()
        if not old.empty:
            # Preserve manual analytical fields by company name where possible.
            manual_cols=[c for c in IPO_COLUMNS if c not in ['Company','Symbol','IssueType','Status','OpenDate','CloseDate','Source','UpdatedAt']]
            old_map=old.set_index(old.Company.astype(str).str.upper())
            for i,row in out.iterrows():
                k=str(row.Company).upper()
                if k in old_map.index:
                    o=old_map.loc[k]
                    if isinstance(o,pd.DataFrame):o=o.iloc[-1]
                    for c in manual_cols:
                        if (pd.isna(out.at[i,c]) or str(out.at[i,c]).strip()=='') and c in o.index:out.at[i,c]=o[c]
        out['Source']='NSE official current-issues page'
        save(out)
        return {'ok':True,'message':f'Refreshed {len(out)} issue row(s) from the official NSE page.'}
    except Exception as e:
        return {'ok':False,'message':f'Official NSE automatic refresh was unavailable: {e}. Existing IPO data was not deleted.'}


def _score_row(r):
    # Separate listing-demand and long-term quality scores. Missing values do not get invented.
    financial=50.0
    if pd.notna(r.get('RevenueGrowth3Y%')):financial += np.clip((float(r['RevenueGrowth3Y%'])-10)*0.8,-15,15)
    if pd.notna(r.get('ProfitGrowth3Y%')):financial += np.clip((float(r['ProfitGrowth3Y%'])-10)*0.8,-15,15)
    if pd.notna(r.get('ROE%')):financial += np.clip((float(r['ROE%'])-12)*1.0,-12,15)
    if pd.notna(r.get('DebtEquity')):financial += 8 if r['DebtEquity']<=0.5 else (-8 if r['DebtEquity']>1.5 else 0)
    financial=float(np.clip(financial,0,100))

    valuation=50.0
    if pd.notna(r.get('PE')) and pd.notna(r.get('IndustryPE')) and float(r['IndustryPE'])>0:
        ratio=float(r['PE'])/float(r['IndustryPE'])
        valuation=85 if ratio<=0.75 else (72 if ratio<=1 else (55 if ratio<=1.25 else 35))
    elif pd.notna(r.get('PE')):
        valuation=60 if float(r['PE'])<=25 else (50 if float(r['PE'])<=40 else 35)

    demand=50.0
    vals=[]
    for c,w in [('QIBSub',0.45),('NIISub',0.25),('RetailSub',0.15),('TotalSub',0.15)]:
        if pd.notna(r.get(c)):
            v=float(r[c]); vals.append(w*(min(v,20)/20*100))
    if vals:demand=float(np.clip(sum(vals)/sum([w for c,w in [('QIBSub',0.45),('NIISub',0.25),('RetailSub',0.15),('TotalSub',0.15)] if pd.notna(r.get(c))]),0,100))

    structure=55.0
    issue=float(r.get('IssueSizeCr') or 0) if pd.notna(r.get('IssueSizeCr')) else 0
    fresh=float(r.get('FreshIssueCr') or 0) if pd.notna(r.get('FreshIssueCr')) else 0
    ofs=float(r.get('OFSCr') or 0) if pd.notna(r.get('OFSCr')) else 0
    if issue>0:
        fresh_pct=fresh/issue*100;ofs_pct=ofs/issue*100
        structure += 15 if fresh_pct>=60 else (5 if fresh_pct>=30 else -5)
        structure -= 10 if ofs_pct>=70 else 0
    u=str(r.get('UseOfFundsQuality','')).upper();structure += 10 if u=='GOOD' else (-10 if u=='POOR' else 0)
    structure=float(np.clip(structure,0,100))

    governance=70.0
    gr=str(r.get('GovernanceRisk','')).upper()
    if gr=='LOW':governance=85
    elif gr=='MEDIUM':governance=60
    elif gr=='HIGH':governance=30
    bq=float(r.get('BusinessQuality')) if pd.notna(r.get('BusinessQuality')) else 60.0

    gmp=float(r.get('GMP%')) if pd.notna(r.get('GMP%')) else 0.0
    gmp_score=float(np.clip(50+gmp*1.2,0,100))
    # GMP is intentionally tiny weight because it is unofficial/noisy.
    listing=0.28*demand+0.22*valuation+0.18*financial+0.17*structure+0.10*governance+0.05*gmp_score
    longterm=0.32*financial+0.25*bq+0.18*valuation+0.15*governance+0.10*structure
    overall=0.45*listing+0.55*longterm

    missing=sum(pd.isna(r.get(c)) for c in ['PE','RevenueGrowth3Y%','ProfitGrowth3Y%','ROE%','DebtEquity'])
    conf='HIGH' if missing<=1 and pd.notna(r.get('TotalSub')) else ('MEDIUM' if missing<=3 else 'LOW')
    risk='HIGH' if str(r.get('Board','')).upper()=='SME' or governance<50 else ('MEDIUM' if governance<70 or valuation<45 else 'LOW/MEDIUM')
    decision='STRONG APPLY' if overall>=82 and longterm>=78 and listing>=75 and conf!='LOW' else ('APPLY' if overall>=70 and longterm>=65 else ('WATCH' if overall>=55 else 'AVOID'))
    reasons=[]
    if financial>=70:reasons.append('Financial growth/return profile scores well')
    elif financial<45:reasons.append('Financial profile is weak or inconsistent')
    if valuation>=70:reasons.append('Valuation is reasonable versus available benchmark')
    elif valuation<45:reasons.append('Valuation looks demanding')
    if demand>=70:reasons.append('Subscription demand is strong, especially institutional demand where available')
    if structure>=70:reasons.append('Issue structure/fresh-capital use is supportive')
    if governance<50:reasons.append('Governance/risk flag is elevated')
    if gmp!=0:reasons.append('GMP is shown only as a low-weight unofficial sentiment input')
    if not reasons:reasons.append('Evidence is mixed or incomplete; avoid overconfidence')
    what=[]
    if decision in ('STRONG APPLY','APPLY'):
        what.append('Downgrade if valuation worsens, institutional demand is weak, governance risk rises or RHP/financial review reveals material concerns')
    else:
        what.append('Upgrade requires better verified financials/valuation, stronger demand and acceptable governance/use-of-funds evidence')
    return listing,longterm,overall,decision,risk,conf,' • '.join(reasons),' • '.join(what)


def analyze(df=None):
    x=normalize(df if df is not None else load())
    if x.empty:return x
    rows=[]
    for _,r in x.iterrows():
        listing,longterm,overall,decision,risk,conf,reason,what=_score_row(r)
        d=r.to_dict();d.update({
            'ListingScore':round(listing,1),'LongTermScore':round(longterm,1),'Overall':round(overall,1),
            'Decision':decision,'Risk':risk,'Confidence':conf,'Reason':reason,'WhatChanges':what
        })
        ph=float(r.get('PriceHigh₹')) if pd.notna(r.get('PriceHigh₹')) else np.nan
        lot=float(r.get('LotSize')) if pd.notna(r.get('LotSize')) else np.nan
        d['OneLotCost₹']=round(ph*lot,2) if pd.notna(ph) and pd.notna(lot) else np.nan
        rows.append(d)
    out=pd.DataFrame(rows)
    rank={'STRONG APPLY':0,'APPLY':1,'WATCH':2,'AVOID':3}
    out['_r']=out.Decision.map(rank).fillna(9)
    return out.sort_values(['_r','Overall'],ascending=[True,False]).drop(columns='_r')
