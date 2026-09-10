from __future__ import annotations

from io import StringIO
from pathlib import Path
import re
import requests
import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent
DATA = BASE / 'data'
DATA.mkdir(parents=True, exist_ok=True)
FILE = DATA / 'fd_rates.csv'

COLUMNS = [
    'Provider','BankType','Product','GeneralRate%','SeniorRate%','TenureYears',
    'Source','SourceURL','RateDate','DataConfidence','ActiveStatus','Notes'
]

# RBI-regulated retail bank universe used so a bank is not silently skipped merely
# because a comparison site did not publish a current rate row for it.
PUBLIC_BANKS = [
    'Bank of Baroda','Bank of India','Bank of Maharashtra','Canara Bank','Central Bank of India',
    'Indian Bank','Indian Overseas Bank','Punjab & Sind Bank','Punjab National Bank',
    'State Bank of India','UCO Bank','Union Bank of India'
]
PRIVATE_BANKS = [
    'Axis Bank','Bandhan Bank','CSB Bank','City Union Bank','DCB Bank','Dhanlaxmi Bank','Federal Bank',
    'HDFC Bank','ICICI Bank','IndusInd Bank','IDFC FIRST Bank','Jammu & Kashmir Bank','Karnataka Bank',
    'Karur Vysya Bank','Kotak Mahindra Bank','Nainital Bank','RBL Bank','South Indian Bank',
    'Tamilnad Mercantile Bank','YES Bank','IDBI Bank'
]
SFB_BANKS = [
    'AU Small Finance Bank','Capital Small Finance Bank','Equitas Small Finance Bank','ESAF Small Finance Bank',
    'Suryoday Small Finance Bank','Ujjivan Small Finance Bank','Utkarsh Small Finance Bank',
    'slice Small Finance Bank','Jana Small Finance Bank','Shivalik Small Finance Bank','Unity Small Finance Bank'
]
OTHER_RETAIL = ['DBS Bank India','HSBC India','Standard Chartered Bank India','SBM Bank India']

# Fresh public comparison snapshot available at build time (3-Sep-2026). It is used only
# as a breadth fallback if live refresh cannot be parsed; exact action still asks the user
# to re-verify the chosen bank's official page before placing money.
SNAPSHOT_DATE = '03-Sep-2026'
SNAPSHOT = {
    # bank: highest, 1y, 3y, 5y
    'Bank of Baroda':(6.75,6.25,6.25,6.30),'Bank of India':(6.85,6.50,6.70,6.00),
    'Bank of Maharashtra':(6.65,6.20,5.25,5.00),'Canara Bank':(6.60,6.25,6.25,6.25),
    'Central Bank of India':(6.75,6.10,6.00,6.00),'Indian Bank':(6.65,6.10,6.05,6.00),
    'Indian Overseas Bank':(6.60,6.50,6.10,6.10),'Punjab & Sind Bank':(6.85,5.85,5.85,5.95),
    'Punjab National Bank':(6.60,6.25,6.35,6.10),'State Bank of India':(6.45,6.25,6.30,6.05),
    'UCO Bank':(6.45,6.10,6.00,6.00),'Union Bank of India':(6.55,6.20,6.10,6.00),
    'Suryoday Small Finance Bank':(8.25,7.25,7.25,8.25),'Jana Small Finance Bank':(8.00,7.00,8.00,7.77),
    'ESAF Small Finance Bank':(8.00,6.00,6.00,5.75),'Utkarsh Small Finance Bank':(8.10,6.00,7.50,7.00),
    'Ujjivan Small Finance Bank':(7.80,7.25,7.25,7.20),'Shivalik Small Finance Bank':(8.00,6.00,7.50,6.25),
    'Equitas Small Finance Bank':(8.00,7.10,7.10,7.00),'Capital Small Finance Bank':(7.15,7.00,7.00,6.90),
    'AU Small Finance Bank':(7.40,6.35,7.40,6.75),'Unity Small Finance Bank':(7.50,7.50,6.75,6.75),
    'Bandhan Bank':(7.45,7.00,7.25,5.85),'DCB Bank':(7.50,6.90,7.00,7.50),
    'RBL Bank':(7.20,7.00,7.20,6.70),'YES Bank':(7.25,6.65,7.00,6.75),
    'IndusInd Bank':(7.00,6.75,7.00,6.65),'Federal Bank':(6.70,6.25,6.50,6.40),
    'SBM Bank India':(7.30,7.10,7.10,7.00),
}

SOURCE_URLS = [
    'https://www.paisabazaar.com/fixed-deposit/scheduled-banks-fd-interest-rates/',
    'https://www.paisabazaar.com/fixed-deposit/'
]


def _bank_type(bank:str)->str:
    if bank in PUBLIC_BANKS:return 'Public Sector Bank'
    if bank in PRIVATE_BANKS:return 'Private Sector Bank'
    if bank in SFB_BANKS:return 'Small Finance Bank'
    return 'Foreign / Other Retail Bank'


def _num(v):
    if v is None:return np.nan
    m=re.search(r'([0-9]+(?:\.[0-9]+)?)',str(v).replace(',',''))
    return float(m.group(1)) if m else np.nan


def _canonical_bank(name:str)->str:
    s=re.sub(r'\s+',' ',str(name)).strip()
    aliases={
        'SBI':'State Bank of India','State Bank of India (SBI)':'State Bank of India',
        'Induslnd Bank':'IndusInd Bank','AU SFB':'AU Small Finance Bank','Au Small Finance Bank':'AU Small Finance Bank',
        'Jana Small finance Bank':'Jana Small Finance Bank','Yes Bank':'YES Bank','Idbi Bank':'IDBI Bank',
        'Pnb':'Punjab National Bank','Boi':'Bank of India','Bob':'Bank of Baroda'
    }
    return aliases.get(s,s)


def _base_rows():
    rows=[]
    for bank in PUBLIC_BANKS+PRIVATE_BANKS+SFB_BANKS+OTHER_RETAIL:
        snap=SNAPSHOT.get(bank,(np.nan,np.nan,np.nan,np.nan))
        vals=[('Highest published slab',snap[0],1.0),('1 Year',snap[1],1.0),('3 Years',snap[2],3.0),('5 Years',snap[3],5.0)]
        for product,rate,ten in vals:
            conf='MEDIUM' if pd.notna(rate) else 'REVIEW'
            source='Paisabazaar public comparison snapshot; verify bank official page' if pd.notna(rate) else 'RBI bank universe; current rate not yet verified'
            rows.append({
                'Provider':bank,'BankType':_bank_type(bank),'Product':product,'GeneralRate%':rate,'SeniorRate%':np.nan,
                'TenureYears':ten,'Source':source,'SourceURL':'https://www.paisabazaar.com/fixed-deposit/',
                'RateDate':SNAPSHOT_DATE if pd.notna(rate) else '','DataConfidence':conf,'ActiveStatus':'ACTIVE',
                'Notes':'Final deposit rate depends on exact tenure/slab/customer category. Reverify the chosen FD on the bank official page before booking.'
            })
    return pd.DataFrame(rows,columns=COLUMNS)


def ensure():
    if not FILE.exists():
        _base_rows().to_csv(FILE,index=False)


def load():
    ensure()
    try:
        x=pd.read_csv(FILE)
        for c in COLUMNS:
            if c not in x.columns:x[c]=''
        return x[COLUMNS]
    except Exception:
        return _base_rows()


def _flatten_cols(df):
    if isinstance(df.columns,pd.MultiIndex):
        df=df.copy();df.columns=[' '.join([str(y) for y in x if str(y)!='nan']).strip() for x in df.columns]
    else:
        df=df.copy();df.columns=[str(x) for x in df.columns]
    return df


def _extract_from_table(df):
    df=_flatten_cols(df)
    cols={c.lower():c for c in df.columns}
    bank_col=next((c for c in df.columns if 'bank' in c.lower() and ('name' in c.lower() or len(c)<30)),None)
    if bank_col is None:return []
    def find_col(*words):
        for c in df.columns:
            lc=c.lower().replace('–','-')
            if all(w in lc for w in words):return c
        return None
    high_col=find_col('highest')
    y1=find_col('1','year') or find_col('1-year')
    y3=find_col('3','year') or find_col('3-year')
    y5=find_col('5','year') or find_col('5-year')
    if not any([high_col,y1,y3,y5]):return []
    out=[]
    for _,r in df.iterrows():
        bank=_canonical_bank(r.get(bank_col,''))
        if not bank or bank.lower()=='nan':continue
        vals=[('Highest published slab',high_col,1.0),('1 Year',y1,1.0),('3 Years',y3,3.0),('5 Years',y5,5.0)]
        for product,col,ten in vals:
            if not col:continue
            rate=_num(r.get(col))
            if pd.isna(rate):continue
            out.append((bank,product,ten,rate))
    return out


def refresh(status_cb=None,timeout=30):
    current=load();updates=[];last_err='';source_used=''
    for url in SOURCE_URLS:
        try:
            if status_cb:status_cb('Checking public FD comparison tables...')
            resp=requests.get(url,headers={'User-Agent':'Mozilla/5.0'},timeout=timeout);resp.raise_for_status()
            date_match=re.search(r'(?:as of|updated(?: as of)?)\s+([0-9]{1,2}\s+[A-Za-z]+\s+20[0-9]{2})',resp.text,re.I)
            rate_date=date_match.group(1) if date_match else pd.Timestamp.today().strftime('%d-%b-%Y')
            for t in pd.read_html(StringIO(resp.text)):
                updates.extend(_extract_from_table(t))
            if updates:
                source_used=url
                break
        except Exception as e:last_err=str(e)
    if updates:
        idx={(str(r.Provider),str(r.Product)):i for i,r in current.iterrows()}
        for bank,product,ten,rate in updates:
            key=(bank,product)
            if key in idx:
                i=idx[key];current.at[i,'GeneralRate%']=rate;current.at[i,'RateDate']=rate_date;current.at[i,'DataConfidence']='MEDIUM';current.at[i,'Source']='Public FD comparison refresh; verify bank official page';current.at[i,'SourceURL']=source_used
            else:
                current.loc[len(current)]={
                    'Provider':bank,'BankType':_bank_type(bank),'Product':product,'GeneralRate%':rate,'SeniorRate%':np.nan,
                    'TenureYears':ten,'Source':'Public FD comparison refresh; verify bank official page','SourceURL':source_used,
                    'RateDate':rate_date,'DataConfidence':'MEDIUM','ActiveStatus':'ACTIVE','Notes':'Verify exact tenure/slab/customer category on the bank official page.'
                }
        current.to_csv(FILE,index=False)
        return {'ok':True,'count':len(current),'verified_rows':len(updates),'source':source_used,'message':f'FD directory refreshed: {len(current):,} bank/tenure rows; {len(updates):,} rates parsed from free public comparison data.'}
    # Keep full universe visible even if external comparison blocks the request.
    current.to_csv(FILE,index=False)
    known=int(pd.to_numeric(current['GeneralRate%'],errors='coerce').notna().sum())
    return {'ok':True,'count':len(current),'verified_rows':known,'source':'cached breadth directory','message':f'FD directory kept complete ({len(current):,} bank/tenure rows). Live comparison refresh unavailable ({last_err or "no parsable table"}); {known} cached public rates retained and final bank verification remains required.'}


def as_investment_options(columns):
    x=load();rows=[]
    for _,r in x.iterrows():
        rate=pd.to_numeric(r.get('GeneralRate%'),errors='coerce')
        ten=pd.to_numeric(r.get('TenureYears'),errors='coerce')
        bank=str(r.get('Provider','')).strip();prod=str(r.get('Product','')).strip();typ=str(r.get('BankType',''))
        if not bank:continue
        risk='LOW/MEDIUM' if 'Small Finance' in typ else 'LOW'
        conf=str(r.get('DataConfidence','REVIEW')).upper()
        rows.append({
            'Option':f'{bank} FD — {prod}','Category':'BANK FD','Provider/Instrument':bank,
            'RateOrExpectedReturn%':rate,'TenureYears':ten if pd.notna(ten) else 1.0,'LockInYears':0.0,
            'Risk':risk,'Liquidity':'MEDIUM','TaxEfficiency':'LOW/MEDIUM','MinInvestment₹':1000,
            'Eligibility/Notes':str(r.get('Notes','')),'Source/Updated':f"{r.get('Source','')} | {r.get('RateDate','')}",
            'ActiveStatus':str(r.get('ActiveStatus','ACTIVE')),'RateDate':str(r.get('RateDate','')),
            'DataConfidence':'MEDIUM' if conf in ('HIGH','MEDIUM') and pd.notna(rate) else ('PARTIAL' if pd.notna(rate) else 'LOW'),
            'ProductNotes':'AUTO_FD_DIRECTORY — exact bank/tenure rate must be reverified before booking.'
        })
    return pd.DataFrame(rows,columns=columns)
