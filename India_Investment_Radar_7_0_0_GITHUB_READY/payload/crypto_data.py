from __future__ import annotations
from pathlib import Path
import json, time
import requests, pandas as pd, numpy as np

BASE=Path(__file__).resolve().parent
DIR=BASE/'data'/'crypto';DIR.mkdir(parents=True,exist_ok=True)
META=DIR/'meta.json'

COINS={
 'BTC':('Bitcoin','BTCUSDT'),'ETH':('Ethereum','ETHUSDT'),'BNB':('BNB','BNBUSDT'),
 'SOL':('Solana','SOLUSDT'),'XRP':('XRP','XRPUSDT'),'ADA':('Cardano','ADAUSDT'),
 'DOGE':('Dogecoin','DOGEUSDT'),'AVAX':('Avalanche','AVAXUSDT'),'LINK':('Chainlink','LINKUSDT'),
 'DOT':('Polkadot','DOTUSDT'),'TRX':('TRON','TRXUSDT'),'LTC':('Litecoin','LTCUSDT'),
 'BCH':('Bitcoin Cash','BCHUSDT'),'XLM':('Stellar','XLMUSDT'),'UNI':('Uniswap','UNIUSDT')
}
BASE_URLS=['https://api.binance.com','https://api1.binance.com','https://api-gcp.binance.com']

def _fx_usdinr(timeout=8):
    try:
        r=requests.get('https://api.frankfurter.app/latest',params={'from':'USD','to':'INR'},timeout=timeout);r.raise_for_status()
        return float(r.json()['rates']['INR'])
    except Exception:return np.nan

def fetch_klines(pair,limit=500,timeout=12):
    err=None
    for base in BASE_URLS:
        try:
            r=requests.get(base+'/api/v3/klines',params={'symbol':pair,'interval':'1d','limit':limit},timeout=timeout)
            r.raise_for_status();j=r.json()
            rows=[]
            for x in j:
                rows.append([pd.to_datetime(int(x[0]),unit='ms',utc=True).tz_localize(None),float(x[1]),float(x[2]),float(x[3]),float(x[4]),float(x[5]),float(x[7])])
            df=pd.DataFrame(rows,columns=['Date','Open','High','Low','Close','Volume','TradedValue'])
            df['PrevClose']=df.Close.shift(1)
            return df
        except Exception as e:err=e
    raise RuntimeError(str(err) if err else 'Crypto market-data request failed')

def refresh(symbols=None,status_cb=None):
    syms=symbols or list(COINS)
    fx=_fx_usdinr();ok=fail=0;errors={}
    for i,s in enumerate(syms):
        name,pair=COINS[s]
        if status_cb:status_cb(f'Crypto {i+1}/{len(syms)}: {name}')
        try:
            df=fetch_klines(pair)
            df.to_csv(DIR/f'{s}.csv',index=False);ok+=1
        except Exception as e:fail+=1;errors[s]=str(e)
        time.sleep(.05)
    meta={'updated_at':pd.Timestamp.now().isoformat(timespec='seconds'),'usd_inr':None if pd.isna(fx) else fx,'ok':ok,'failed':fail,'errors':errors}
    META.write_text(json.dumps(meta,indent=2),encoding='utf-8')
    return meta

def load(symbol):
    p=DIR/f'{symbol}.csv'
    if not p.exists():return pd.DataFrame()
    try:
        df=pd.read_csv(p,parse_dates=['Date'])
        return df
    except Exception:return pd.DataFrame()

def meta():
    if META.exists():
        try:return json.loads(META.read_text(encoding='utf-8'))
        except Exception:pass
    return {}

def universe():return COINS.copy()
