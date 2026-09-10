from __future__ import annotations
from datetime import date
import numpy as np
import pandas as pd

def _num(v,default=np.nan):
    try:return float(v)
    except Exception:return default

def _xnpv(rate,cashflows):
    if rate<=-0.999999:return np.inf
    d0=cashflows[0][0]
    return sum(v/((1+rate)**(((d-d0).days)/365.25)) for d,v in cashflows)

def _xirr(cashflows):
    cashflows=[(d,float(v)) for d,v in cashflows if pd.notna(v)]
    if len(cashflows)<2 or not any(v<0 for _,v in cashflows) or not any(v>0 for _,v in cashflows):return np.nan
    lo,hi=-0.9999,10.0;flo=_xnpv(lo,cashflows);fhi=_xnpv(hi,cashflows)
    for _ in range(20):
        if np.sign(flo)!=np.sign(fhi):break
        hi*=2;fhi=_xnpv(hi,cashflows)
        if hi>1000:return np.nan
    if np.sign(flo)==np.sign(fhi):return np.nan
    for _ in range(120):
        mid=(lo+hi)/2;fm=_xnpv(mid,cashflows)
        if abs(fm)<1e-7:return mid
        if np.sign(fm)==np.sign(flo):lo=mid;flo=fm
        else:hi=mid;fhi=fm
    return (lo+hi)/2

def portfolio_health(lots:pd.DataFrame):
    if lots is None or lots.empty:return {'summary':{},'allocation':pd.DataFrame(),'warnings':pd.DataFrame(),'profiles':pd.DataFrame()}
    x=lots.copy();qty=pd.to_numeric(x.get('Quantity'),errors='coerce').fillna(0);basis=pd.to_numeric(x.get('PriceBasisQty'),errors='coerce').replace(0,np.nan).fillna(1)
    invested=pd.to_numeric(x.get('InvestedAmount₹'),errors='coerce').fillna(0);curp=pd.to_numeric(x.get('CurrentPrice₹'),errors='coerce');cur=(qty/basis)*curp
    x['_Invested']=invested;x['_Current']=cur;total_inv=float(invested.sum());total_cur=float(cur.fillna(0).sum())
    pnl=total_cur-total_inv if total_cur>0 else np.nan;pnlpct=pnl/total_inv*100 if total_inv>0 and pd.notna(pnl) else np.nan
    alloc=x.assign(Value=x['_Current'].fillna(x['_Invested'])).groupby('AssetType',dropna=False)['Value'].sum().sort_values(ascending=False).reset_index();total=float(alloc.Value.sum());alloc['Weight%']=(alloc.Value/total*100).round(1) if total>0 else 0
    profiles=x.assign(Value=x['_Current'].fillna(x['_Invested']));profiles['Profile']=profiles.get('Account',pd.Series(['Default']*len(profiles))).astype(str).replace({'nan':'','None':''}).str.strip().replace('','Default');profiles=profiles.groupby('Profile')['Value'].sum().reset_index();pt=float(profiles.Value.sum());profiles['Weight%']=(profiles.Value/pt*100).round(1) if pt>0 else 0
    warns=[]
    for _,r in alloc.iterrows():
        w=float(r['Weight%'])
        if w>=50:warns.append({'Level':'HIGH','Item':str(r.AssetType),'Message':f'{w:.1f}% of portfolio is in one asset class.'})
        elif w>=35:warns.append({'Level':'REVIEW','Item':str(r.AssetType),'Message':f'{w:.1f}% concentration in one asset class.'})
    sx=x.assign(Value=x['_Current'].fillna(x['_Invested']));sy=sx.get('Symbol',pd.Series(['']*len(sx))).astype(str).str.strip();nm=sx.get('Name',pd.Series(['']*len(sx))).astype(str).str.strip();sx['_Key']=sy+' | '+nm
    h=sx.groupby('_Key')['Value'].sum().sort_values(ascending=False)
    if total>0:
        for k,v in h.head(10).items():
            w=float(v/total*100)
            if w>=25:warns.append({'Level':'HIGH','Item':k,'Message':f'{w:.1f}% in a single holding/product.'})
            elif w>=15:warns.append({'Level':'REVIEW','Item':k,'Message':f'{w:.1f}% in a single holding/product.'})
    cfs=[]
    for _,r in x.iterrows():
        dt=pd.to_datetime(r.get('PurchaseDate'),errors='coerce');amt=_num(r.get('InvestedAmount₹'),0)
        if pd.notna(dt) and amt>0:cfs.append((dt.date(),-amt))
    if total_cur>0:cfs.append((date.today(),total_cur))
    xir=_xirr(sorted(cfs,key=lambda z:z[0])) if cfs else np.nan
    summary={'Invested₹':round(total_inv,2),'CurrentValue₹':round(total_cur,2) if total_cur>0 else np.nan,'PnL₹':round(pnl,2) if pd.notna(pnl) else np.nan,'PnL%':round(pnlpct,2) if pd.notna(pnlpct) else np.nan,'ApproxXIRR%':round(xir*100,2) if pd.notna(xir) else np.nan,'AssetClasses':int(alloc.AssetType.nunique()) if not alloc.empty else 0,'Profiles':int(profiles.Profile.nunique()) if not profiles.empty else 0,'Health':'REVIEW' if any(w['Level']=='HIGH' for w in warns) else ('GOOD' if total_inv>0 else 'EMPTY')}
    return {'summary':summary,'allocation':alloc,'warnings':pd.DataFrame(warns),'profiles':profiles}
