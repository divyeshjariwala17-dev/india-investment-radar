from __future__ import annotations

from pathlib import Path
import re
from datetime import date
import requests
import numpy as np
import pandas as pd

BASE=Path(__file__).resolve().parent
DATA=BASE/'data';DATA.mkdir(parents=True,exist_ok=True)
FILE=DATA/'small_savings_rates.csv'
INDIA_POST='https://www.indiapost.gov.in/banking-services/savings'
DEA='https://dea.gov.in/budget-division/475'

# Official Q2 FY 2026-27 rates effective 01-Jul-2026 to 30-Sep-2026.
# DEA's 30-Jun-2026 notification states the rates remain unchanged; India Post's
# current scheme page independently shows the headline rates for the major schemes.
SNAPSHOT=[
 ('Post Office Savings Account','Post Office Savings Account',4.0,0.01,0.0,500,'HIGH'),
 ('Recurring Deposit — Post Office','Post Office RD',6.7,5.0,5.0,100,'HIGH'),
 ('Post Office Time Deposit — 1Y','Post Office TD 1 Year',6.9,1.0,1.0,1000,'HIGH'),
 ('Post Office Time Deposit — 2Y','Post Office TD 2 Years',7.0,2.0,2.0,1000,'HIGH'),
 ('Post Office Time Deposit — 3Y','Post Office TD 3 Years',7.1,3.0,3.0,1000,'HIGH'),
 ('Post Office Time Deposit — 5Y','Post Office TD 5 Years',7.5,5.0,5.0,1000,'HIGH'),
 ('Post Office MIS','Monthly Income Scheme',7.4,5.0,5.0,1000,'HIGH'),
 ('PPF','Public Provident Fund',7.1,15.0,15.0,500,'HIGH'),
 ('NSC','National Savings Certificate',7.7,5.0,5.0,1000,'HIGH'),
 ('KVP','Kisan Vikas Patra',7.5,115/12,2.5,1000,'HIGH'),
 ('SCSS','Senior Citizens Savings Scheme',8.2,5.0,5.0,1000,'HIGH'),
 ('Sukanya Samriddhi','Sukanya Samriddhi Account',8.2,21.0,21.0,250,'HIGH'),
]
COLS=['Option','Provider','Rate%','TenureYears','LockInYears','MinInvestment₹','RateDate','ValidThrough','Source','DataConfidence','Notes']


def _base():
    rows=[]
    for opt,provider,rate,ten,lock,mininv,conf in SNAPSHOT:
        rows.append({'Option':opt,'Provider':provider,'Rate%':rate,'TenureYears':ten,'LockInYears':lock,'MinInvestment₹':mininv,
                     'RateDate':'01-Jul-2026','ValidThrough':'30-Sep-2026','Source':'Government of India DEA Q2 FY2026-27 notification + India Post current scheme page',
                     'DataConfidence':conf,'Notes':'Government small-savings rate. Eligibility, contribution limits, premature closure and tax rules still apply.'})
    return pd.DataFrame(rows,columns=COLS)


def ensure():
    if not FILE.exists():_base().to_csv(FILE,index=False)


def load():
    ensure()
    try:
        x=pd.read_csv(FILE)
        for c in COLS:
            if c not in x.columns:x[c]=''
    except Exception:x=_base()
    # After the official validity window, do not silently call the snapshot fresh.
    vt=pd.to_datetime(x['ValidThrough'],dayfirst=True,errors='coerce')
    stale=vt.notna() & (vt.dt.date < date.today())
    x.loc[stale,'DataConfidence']='PARTIAL'
    x.loc[stale,'Notes']=x.loc[stale,'Notes'].astype(str)+' Rate period has ended; run Daily Update and verify the new quarter before acting.'
    return x[COLS]


def _extract_rate(text,label_patterns):
    for p in label_patterns:
        m=re.search(p+r'.{0,180}?Rate of Interest\s*:?\s*([0-9]+(?:\.[0-9]+)?)\s*%',text,re.I|re.S)
        if m:return float(m.group(1))
    return np.nan


def refresh(status_cb=None,timeout=25):
    x=_base();parsed=0;err=''
    try:
        if status_cb:status_cb('Checking India Post current savings-scheme page...')
        r=requests.get(INDIA_POST,headers={'User-Agent':'Mozilla/5.0'},timeout=timeout);r.raise_for_status();txt=re.sub(r'\s+',' ',r.text)
        patterns={
            'Post Office Savings Account':['Post Office Savings Account'],
            'Recurring Deposit — Post Office':['Recurring Deposit Account','Recurring Deposit'],
            'Post Office MIS':['Monthly Income Scheme'],
            'SCSS':['Senior Citizens Savings Scheme'],
            'PPF':['Public Provident Fund'],
            'Sukanya Samriddhi':['Sukanya Samriddhi'],
            'KVP':['Kisan Vikas Patra'],
        }
        for opt,pats in patterns.items():
            val=_extract_rate(txt,pats)
            if pd.notna(val):x.loc[x.Option.eq(opt),'Rate%']=val;parsed+=1
    except Exception as e:err=str(e)
    # Q2 notification is authoritative for current quarter. Keep it as the exact fallback.
    x.to_csv(FILE,index=False)
    return {'ok':True,'count':len(x),'parsed':parsed,'source':'DEA + India Post','message':f'Post Office / small-savings directory ready: {len(x)} schemes with current Q2 FY2026-27 rates. India Post live page confirmed {parsed} headline rate(s).'+(f' Live-page note: {err}' if err else '')}


def apply_to_options(opts:pd.DataFrame):
    rates=load();x=opts.copy()
    for c in ['Source/Updated','RateDate','DataConfidence','ProductNotes']:
        if c in x.columns:x[c]=x[c].astype(object)
    for _,r in rates.iterrows():
        m=x['Option'].astype(str).eq(str(r.Option)) if 'Option' in x.columns else pd.Series(False,index=x.index)
        if not m.any():continue
        x.loc[m,'RateOrExpectedReturn%']=pd.to_numeric(r['Rate%'],errors='coerce')
        x.loc[m,'TenureYears']=pd.to_numeric(r['TenureYears'],errors='coerce')
        x.loc[m,'LockInYears']=pd.to_numeric(r['LockInYears'],errors='coerce')
        x.loc[m,'MinInvestment₹']=pd.to_numeric(r['MinInvestment₹'],errors='coerce')
        x.loc[m,'Source/Updated']=str(r['Source'])
        x.loc[m,'RateDate']=str(r['RateDate'])
        x.loc[m,'DataConfidence']=str(r['DataConfidence'])
        note=str(r.get('Notes',''))
        if note:x.loc[m,'ProductNotes']=note
    return x
