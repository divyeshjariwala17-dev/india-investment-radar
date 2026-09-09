from __future__ import annotations
from pathlib import Path
import pandas as pd, numpy as np
BASE=Path(__file__).resolve().parent;FILE=BASE/'data'/'fixed_income_watchlist.csv'
DEFAULT=[
 {'Instrument':'91-Day T-Bill','Type':'Government','Yield%':None,'MaturityYears':0.25,'CreditRisk':'VERY LOW','Liquidity':'HIGH','SourceNote':'Enter current RBI auction/market yield before use'},
 {'Instrument':'182-Day T-Bill','Type':'Government','Yield%':None,'MaturityYears':0.50,'CreditRisk':'VERY LOW','Liquidity':'HIGH','SourceNote':'Enter current RBI auction/market yield before use'},
 {'Instrument':'364-Day T-Bill','Type':'Government','Yield%':None,'MaturityYears':1.00,'CreditRisk':'VERY LOW','Liquidity':'HIGH','SourceNote':'Enter current RBI auction/market yield before use'},
 {'Instrument':'2Y G-Sec','Type':'Government','Yield%':None,'MaturityYears':2.0,'CreditRisk':'VERY LOW','Liquidity':'HIGH','SourceNote':'Replace with exact current security/YTM before use'},
 {'Instrument':'5Y G-Sec','Type':'Government','Yield%':None,'MaturityYears':5.0,'CreditRisk':'VERY LOW','Liquidity':'HIGH','SourceNote':'Replace with exact current security/YTM before use'},
 {'Instrument':'10Y G-Sec','Type':'Government','Yield%':None,'MaturityYears':10.0,'CreditRisk':'VERY LOW','Liquidity':'HIGH','SourceNote':'Replace with exact current benchmark/current security YTM before use'},
 {'Instrument':'Long-Duration G-Sec','Type':'Government','Yield%':None,'MaturityYears':20.0,'CreditRisk':'VERY LOW','Liquidity':'MEDIUM/HIGH','SourceNote':'Use exact security and current YTM; duration risk is high despite sovereign credit quality'},
 {'Instrument':'SDL — Exact State Security','Type':'State Government','Yield%':None,'MaturityYears':10.0,'CreditRisk':'VERY LOW','Liquidity':'MEDIUM','SourceNote':'Replace with exact SDL and current market/auction YTM'},
 {'Instrument':'RBI Floating Rate Savings Bond / Current Equivalent','Type':'Government Savings','Yield%':None,'MaturityYears':7.0,'CreditRisk':'VERY LOW','Liquidity':'LOW','SourceNote':'Verify current availability, reset formula, lock-in and eligibility from official terms'},
 {'Instrument':'AAA PSU / Corporate Bond','Type':'Corporate','Yield%':None,'MaturityYears':3.0,'CreditRisk':'LOW','Liquidity':'MEDIUM','SourceNote':'Replace with exact security, rating, YTM, call/put terms and liquidity'},
 {'Instrument':'AA Corporate Bond / NCD','Type':'Corporate','Yield%':None,'MaturityYears':3.0,'CreditRisk':'MEDIUM','Liquidity':'LOW/MEDIUM','SourceNote':'Higher credit risk; use exact security/rating/current YTM and concentration limits'},
 {'Instrument':'Outstanding Tax-Free Bond','Type':'Corporate / PSU','Yield%':None,'MaturityYears':5.0,'CreditRisk':'LOW','Liquidity':'LOW/MEDIUM','SourceNote':'Only if an exact outstanding listed bond is available; compare post-tax YTM and liquidity'}
]
def ensure_file():
    FILE.parent.mkdir(parents=True,exist_ok=True)
    if not FILE.exists():pd.DataFrame(DEFAULT).to_csv(FILE,index=False)
def load():ensure_file();return pd.read_csv(FILE)
def save(df):df.to_csv(FILE,index=False)
def analyze(df):
    x=df.copy();x['Yield%']=pd.to_numeric(x['Yield%'],errors='coerce');x['MaturityYears']=pd.to_numeric(x['MaturityYears'],errors='coerce')
    x['Expected1Y%']=x['Yield%'];x['ExpectedToMaturity%']=((1+x['Yield%']/100)**x['MaturityYears']-1)*100
    x['InterestRateRisk']=x['MaturityYears'].apply(lambda y:'HIGH' if pd.notna(y) and y>=7 else ('MEDIUM' if pd.notna(y) and y>=3 else 'LOW'))
    def score(r):
        if pd.isna(r['Yield%']):return np.nan
        s=50+min(20,max(-10,(r['Yield%']-5)*5));cr=str(r['CreditRisk']).upper();liq=str(r['Liquidity']).upper()
        s+=15 if cr=='VERY LOW' else (8 if cr=='LOW' else (-15 if cr=='HIGH' else 0));s+=8 if liq=='HIGH' else (-5 if liq=='LOW' else 0)
        return max(0,min(100,s))
    x['Overall']=x.apply(score,axis=1).round(1)
    x['Action']=x['Overall'].apply(lambda s:'INPUT REQUIRED' if pd.isna(s) else ('CONSIDER' if s>=70 else ('WATCH' if s>=58 else 'AVOID')))
    x['Risk']=x.apply(lambda r:'UNKNOWN' if pd.isna(r['Yield%']) else ('LOW' if str(r.CreditRisk).upper()=='VERY LOW' and r.InterestRateRisk=='LOW' else ('HIGH' if str(r.CreditRisk).upper()=='HIGH' or r.InterestRateRisk=='HIGH' else 'MEDIUM')),axis=1)
    def why(r):
        if pd.isna(r['Yield%']): return 'Current Yield/YTM is missing, so a recommendation is intentionally not produced.'
        parts=[f"Current Yield/YTM input is {r['Yield%']:.2f}%"]
        parts.append(f"Credit risk is {str(r['CreditRisk']).upper()}")
        parts.append(f"Interest-rate risk is {r['InterestRateRisk']} for {r['MaturityYears']:.2f}-year maturity")
        parts.append(f"Liquidity is {str(r['Liquidity']).upper()}")
        if pd.notna(r['ExpectedToMaturity%']): parts.append(f"Estimated compounded return to maturity is about {r['ExpectedToMaturity%']:.2f}% before tax/costs")
        return ' • '.join(parts)
    def changes(r):
        if pd.isna(r['Yield%']): return 'Enter the exact current Yield/YTM for the specific instrument to enable scoring.'
        if r['Action']=='CONSIDER': return 'The recommendation can weaken if market YTM falls materially, credit quality worsens, liquidity deteriorates, or the holding period no longer matches maturity.'
        if r['Action']=='WATCH': return 'Upgrade needs a better current YTM and/or lower credit, duration or liquidity risk for the selected holding period.'
        return 'Upgrade needs a more attractive current YTM with acceptable credit quality, liquidity and maturity risk.'
    x['Reason']=x.apply(why,axis=1)
    x['WhatChanges']=x.apply(changes,axis=1)
    return x.sort_values('Overall',ascending=False,na_position='last')
