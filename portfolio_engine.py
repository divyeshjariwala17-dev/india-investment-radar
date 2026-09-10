from __future__ import annotations
import io, re, uuid
from pathlib import Path
import pandas as pd, numpy as np

ASSET_TYPES=[
    'STOCK','ETF','MUTUAL FUND','GOLD PHYSICAL','SILVER PHYSICAL',
    'CRYPTO','BOND / FIXED INCOME','FD','RD','IPO','REIT / INVIT','NPS','PPF / GOVT SAVINGS','INTERNATIONAL','REAL ESTATE','PMS / AIF','CASH','OTHER'
]

PORTFOLIO_COLUMNS=[
    'InvestmentID','AssetType','Symbol','Name','PurchaseDate','Quantity','Unit','PriceBasisQty',
    'BuyPrice₹','InvestedAmount₹','CurrentPrice₹','BrokerSource','Account','Goal','Strategy','Notes','UpdatedAt'
]

SYMBOL_ALIASES=['symbol','tradingsymbol','trading symbol','scrip','security','stock','instrument','ticker','nse symbol','scheme code','code']
QTY_ALIASES=['qty','quantity','net qty','net quantity','holding qty','total qty','units','unit balance']
AVG_ALIASES=['avg price','average price','avg cost','average cost','buy avg','cost price','average buy price','purchase price','nav']
LTP_ALIASES=['ltp','last price','current price','market price','close','current nav']
DATE_ALIASES=['purchase date','buy date','date','investment date','trade date']
NAME_ALIASES=['name','company','security name','scheme name','instrument name']
AMOUNT_ALIASES=['invested amount','invested amount₹','amount','cost value','investment value','buy value']
TYPE_ALIASES=['asset type','assettype','type','category']
BROKER_ALIASES=['broker','broker source','brokersource','platform','source']
ACCOUNT_ALIASES=['account','account name','folio','folio no','folio number','demat']
GOAL_ALIASES=['goal','investment goal']
STRATEGY_ALIASES=['strategy','horizon','purpose']
NOTES_ALIASES=['notes','remark','remarks','comment']
ID_ALIASES=['investmentid','investment id','id','lot id','transaction id']
BASIS_ALIASES=['price basis qty','pricebasisqty','basis qty','price unit qty']
UNIT_ALIASES=['unit','units type','quantity unit']


def _find_col(cols,aliases):
    norm={str(c).strip().lower():c for c in cols}
    for a in aliases:
        if a in norm:return norm[a]
    for c0,c in norm.items():
        if any(a in c0 for a in aliases):return c
    return None


def _clean_asset_type(v):
    s=str(v or '').strip().upper().replace('_',' ')
    aliases={
        'EQUITY':'STOCK','SHARE':'STOCK','SHARES':'STOCK','STOCKS':'STOCK',
        'MF':'MUTUAL FUND','MUTUAL FUND':'MUTUAL FUND','MUTUAL FUNDS':'MUTUAL FUND',
        'GOLD':'GOLD PHYSICAL','PHYSICAL GOLD':'GOLD PHYSICAL',
        'SILVER':'SILVER PHYSICAL','PHYSICAL SILVER':'SILVER PHYSICAL',
        'CRYPTOCURRENCY':'CRYPTO','COIN':'CRYPTO',
        'BOND':'BOND / FIXED INCOME','FIXED INCOME':'BOND / FIXED INCOME','DEBT':'BOND / FIXED INCOME',
        'FIXED DEPOSIT':'FD','BANK FD':'FD','RECURRING DEPOSIT':'RD','RD':'RD','IPO':'IPO','REIT':'REIT / INVIT','INVIT':'REIT / INVIT','REIT / INVIT':'REIT / INVIT','NPS':'NPS','PPF':'PPF / GOVT SAVINGS','GOVT SAVINGS':'PPF / GOVT SAVINGS','INTERNATIONAL':'INTERNATIONAL','FOREIGN':'INTERNATIONAL','REAL ESTATE':'REAL ESTATE','PMS':'PMS / AIF','AIF':'PMS / AIF','CASH':'CASH','ETF':'ETF'
    }
    return aliases.get(s,s if s in ASSET_TYPES else 'STOCK')


def _default_unit(asset_type):
    return {
        'STOCK':'Shares','ETF':'Units','MUTUAL FUND':'Units','GOLD PHYSICAL':'grams',
        'SILVER PHYSICAL':'kg','CRYPTO':'Coins','BOND / FIXED INCOME':'Units',
        'FD':'Deposit','RD':'Deposit','IPO':'Shares','REIT / INVIT':'Units','NPS':'Units','PPF / GOVT SAVINGS':'Account','INTERNATIONAL':'Units','REAL ESTATE':'Property','PMS / AIF':'Units','CASH':'₹','OTHER':'Units'
    }.get(asset_type,'Units')


def _default_basis(asset_type):
    if asset_type=='GOLD PHYSICAL':return 10.0
    return 1.0


def _new_id():
    return 'INV-'+uuid.uuid4().hex[:10].upper()


def normalize_portfolio(df: pd.DataFrame, default_asset_type='STOCK'):
    if df is None or df.empty:return pd.DataFrame(columns=PORTFOLIO_COLUMNS)
    x=df.copy()
    # If already in canonical format, preserve everything and add missing columns.
    if 'AssetType' in x.columns or 'InvestmentID' in x.columns:
        out=x.copy()
    else:
        out=pd.DataFrame(index=x.index)
        sc=_find_col(x.columns,SYMBOL_ALIASES); qc=_find_col(x.columns,QTY_ALIASES); ac=_find_col(x.columns,AVG_ALIASES)
        lc=_find_col(x.columns,LTP_ALIASES); dc=_find_col(x.columns,DATE_ALIASES); nc=_find_col(x.columns,NAME_ALIASES)
        amc=_find_col(x.columns,AMOUNT_ALIASES); tc=_find_col(x.columns,TYPE_ALIASES); bc=_find_col(x.columns,BROKER_ALIASES)
        acc=_find_col(x.columns,ACCOUNT_ALIASES); gc=_find_col(x.columns,GOAL_ALIASES); stc=_find_col(x.columns,STRATEGY_ALIASES)
        noc=_find_col(x.columns,NOTES_ALIASES); ic=_find_col(x.columns,ID_ALIASES); basc=_find_col(x.columns,BASIS_ALIASES); uc=_find_col(x.columns,UNIT_ALIASES)
        if sc is None and nc is None:
            raise ValueError('Could not identify an investment Symbol/Name column.')
        out['InvestmentID']=x[ic].astype(str) if ic else ''
        out['AssetType']=x[tc].astype(str) if tc else default_asset_type
        out['Symbol']=x[sc].astype(str) if sc else x[nc].astype(str)
        out['Name']=x[nc].astype(str) if nc else out['Symbol']
        out['PurchaseDate']=x[dc] if dc else pd.NaT
        out['Quantity']=pd.to_numeric(x[qc],errors='coerce') if qc else np.nan
        out['Unit']=x[uc].astype(str) if uc else ''
        out['PriceBasisQty']=pd.to_numeric(x[basc],errors='coerce') if basc else np.nan
        out['BuyPrice₹']=pd.to_numeric(x[ac],errors='coerce') if ac else np.nan
        out['InvestedAmount₹']=pd.to_numeric(x[amc],errors='coerce') if amc else np.nan
        out['CurrentPrice₹']=pd.to_numeric(x[lc],errors='coerce') if lc else np.nan
        out['BrokerSource']=x[bc].astype(str) if bc else ''
        out['Account']=x[acc].astype(str) if acc else ''
        out['Goal']=x[gc].astype(str) if gc else ''
        out['Strategy']=x[stc].astype(str) if stc else ''
        out['Notes']=x[noc].astype(str) if noc else ''
        out['UpdatedAt']=''

    for c in PORTFOLIO_COLUMNS:
        if c not in out.columns:out[c]=np.nan if c in ['Quantity','PriceBasisQty','BuyPrice₹','InvestedAmount₹','CurrentPrice₹'] else ''

    out=out[PORTFOLIO_COLUMNS].copy()
    out['AssetType']=out['AssetType'].fillna(default_asset_type).map(_clean_asset_type)
    out['Symbol']=out['Symbol'].fillna('').astype(str).str.upper().str.strip().str.replace(r'-(EQ|BE)$','',regex=True)
    out['Name']=out['Name'].fillna('').astype(str).str.strip()
    out.loc[out['Name'].eq(''),'Name']=out.loc[out['Name'].eq(''),'Symbol']
    out['PurchaseDate']=pd.to_datetime(out['PurchaseDate'],errors='coerce').dt.date
    for c in ['Quantity','PriceBasisQty','BuyPrice₹','InvestedAmount₹','CurrentPrice₹']:
        out[c]=pd.to_numeric(out[c],errors='coerce')
    out['PriceBasisQty']=out.apply(lambda r: _default_basis(r.AssetType) if pd.isna(r['PriceBasisQty']) or r['PriceBasisQty']<=0 else r['PriceBasisQty'],axis=1)
    out['Unit']=out.apply(lambda r: _default_unit(r.AssetType) if not str(r.Unit or '').strip() else str(r.Unit).strip(),axis=1)
    # Compute missing amount from quantity / price basis * buy price.
    calc=(out['Quantity']/out['PriceBasisQty'])*out['BuyPrice₹']
    out['InvestedAmount₹']=out['InvestedAmount₹'].where(out['InvestedAmount₹'].notna(),calc)
    out['InvestmentID']=out['InvestmentID'].fillna('').astype(str).str.strip()
    empty=out['InvestmentID'].eq('') | out['InvestmentID'].str.lower().isin(['nan','none'])
    out.loc[empty,'InvestmentID']=[_new_id() for _ in range(int(empty.sum()))]
    out['UpdatedAt']=pd.Timestamp.now().isoformat(timespec='seconds')
    # Keep rows that identify something and have some economic value.
    valid=(out['Symbol'].ne('')|out['Name'].ne('')) & (out['Quantity'].fillna(0).ne(0)|out['InvestedAmount₹'].fillna(0).ne(0))
    return out[valid].reset_index(drop=True)


def read_portfolio(uploaded=None):
    """Read saved portfolio when called with no argument, or an uploaded CSV/XLSX when supplied."""
    if uploaded is None:
        saved_path=Path(__file__).resolve().parent/'data'/'my_portfolio.csv'
        if not saved_path.exists():
            return pd.DataFrame(columns=PORTFOLIO_COLUMNS)
        try:
            df=pd.read_csv(saved_path)
        except Exception:
            return pd.DataFrame(columns=PORTFOLIO_COLUMNS)
        if df is None or df.empty:
            return pd.DataFrame(columns=PORTFOLIO_COLUMNS)
        return normalize_portfolio(df)

    name=str(getattr(uploaded,'name','')).lower()
    if name.endswith('.xlsx') or name.endswith('.xls'):
        df=pd.read_excel(uploaded)
    else:
        df=pd.read_csv(uploaded)
    return normalize_portfolio(df)


def template_df():
    today=pd.Timestamp.now().date().isoformat()
    return pd.DataFrame([
        {'InvestmentID':'','AssetType':'STOCK','Symbol':'RELIANCE','Name':'','PurchaseDate':today,'Quantity':10,'Unit':'Shares','PriceBasisQty':1,'BuyPrice₹':0,'InvestedAmount₹':'','CurrentPrice₹':'','BrokerSource':'Dhan','Account':'Main','Goal':'Wealth','Strategy':'Long Term','Notes':'','UpdatedAt':''},
        {'InvestmentID':'','AssetType':'MUTUAL FUND','Symbol':'','Name':'Your Scheme Name / Code','PurchaseDate':today,'Quantity':0,'Unit':'Units','PriceBasisQty':1,'BuyPrice₹':0,'InvestedAmount₹':50000,'CurrentPrice₹':'','BrokerSource':'AMC/Platform','Account':'Folio','Goal':'Retirement','Strategy':'5+ Years','Notes':'','UpdatedAt':''},
        {'InvestmentID':'','AssetType':'GOLD PHYSICAL','Symbol':'GOLD','Name':'24K Gold Coin/Bar','PurchaseDate':today,'Quantity':10,'Unit':'grams','PriceBasisQty':10,'BuyPrice₹':0,'InvestedAmount₹':'','CurrentPrice₹':'','BrokerSource':'Dealer','Account':'Physical','Goal':'Wealth','Strategy':'3+ Years','Notes':'BuyPrice is rate per 10g'},
        {'InvestmentID':'','AssetType':'SILVER PHYSICAL','Symbol':'SILVER','Name':'Silver Bar','PurchaseDate':today,'Quantity':1,'Unit':'kg','PriceBasisQty':1,'BuyPrice₹':0,'InvestedAmount₹':'','CurrentPrice₹':'','BrokerSource':'Dealer','Account':'Physical','Goal':'Wealth','Strategy':'3+ Years','Notes':'BuyPrice is rate per kg','UpdatedAt':''},
        {'InvestmentID':'','AssetType':'CRYPTO','Symbol':'BTC','Name':'Bitcoin','PurchaseDate':today,'Quantity':0.01,'Unit':'Coins','PriceBasisQty':1,'BuyPrice₹':0,'InvestedAmount₹':'','CurrentPrice₹':'','BrokerSource':'Exchange','Account':'Main','Goal':'High Growth','Strategy':'High Risk','Notes':'','UpdatedAt':''},
    ])[PORTFOLIO_COLUMNS]


def merge_portfolio(existing,incoming,mode='MERGE / UPDATE'):
    old=normalize_portfolio(existing) if existing is not None and not existing.empty else pd.DataFrame(columns=PORTFOLIO_COLUMNS)
    new=normalize_portfolio(incoming) if incoming is not None and not incoming.empty else pd.DataFrame(columns=PORTFOLIO_COLUMNS)
    if mode.upper().startswith('REPLACE'):
        return new.reset_index(drop=True)
    if old.empty:return new.reset_index(drop=True)
    if new.empty:return old.reset_index(drop=True)
    # InvestmentID is primary key. Same ID updates; new ID adds a lot.
    old=old.set_index('InvestmentID',drop=False)
    for _,r in new.iterrows():
        old.loc[r.InvestmentID]=r
    return old.reset_index(drop=True)[PORTFOLIO_COLUMNS]


def aggregate_holdings(lots:pd.DataFrame):
    if lots is None or lots.empty:return pd.DataFrame()
    x=lots.copy()
    keys=['AssetType','Symbol','Name','Unit','PriceBasisQty']
    rows=[]
    for kvals,g in x.groupby(keys,dropna=False):
        if not isinstance(kvals,tuple):kvals=(kvals,)
        base=dict(zip(keys,kvals))
        qty=pd.to_numeric(g.Quantity,errors='coerce').fillna(0).sum()
        invested=pd.to_numeric(g['InvestedAmount₹'],errors='coerce').fillna(0).sum()
        basis=float(base.get('PriceBasisQty') or 1)
        avg=(invested*basis/qty) if qty else np.nan
        cp=pd.to_numeric(g['CurrentPrice₹'],errors='coerce').dropna()
        current=cp.iloc[-1] if len(cp) else np.nan
        cv=(qty/basis)*current if pd.notna(current) else np.nan
        dates=pd.to_datetime(g.PurchaseDate,errors='coerce')
        base.update({
            'Quantity':qty,'AvgPrice₹':avg,'Invested₹':invested,'CurrentPrice₹':current,
            'CurrentValue₹':cv,'PnL₹':cv-invested if pd.notna(cv) else np.nan,
            'PnL%':((cv/invested)-1)*100 if pd.notna(cv) and invested else np.nan,
            'Lots':len(g),'FirstPurchase':dates.min().date() if dates.notna().any() else None,
            'LastPurchase':dates.max().date() if dates.notna().any() else None,
            'Goal':', '.join(sorted(set(str(v) for v in g.Goal if str(v).strip() and str(v).lower()!='nan'))),
            'Account':', '.join(sorted(set(str(v) for v in g.Account if str(v).strip() and str(v).lower()!='nan'))),
        })
        rows.append(base)
    return pd.DataFrame(rows)


def enrich_current_prices(lots,radar=None,mf=None,metal_state=None,crypto_prices=None,bonds=None):
    if lots is None or lots.empty:return lots
    x=lots.copy()
    # Build lookup dictionaries.
    stock={}
    if radar is not None and not radar.empty:
        rr=radar.sort_values(['Symbol','Category']).drop_duplicates('Symbol')
        stock={str(r.Symbol).upper():float(r.Current) for _,r in rr.iterrows() if pd.notna(r.Current)}
    mf_code={}; mf_name={}
    if mf is not None and not mf.empty:
        for _,r in mf.iterrows():
            if pd.notna(r.get('Code')):mf_code[str(r.get('Code')).strip().upper()]=float(r.NAV)
            mf_name[str(r.get('Scheme','')).strip().upper()]=float(r.NAV)
    crypto_prices=crypto_prices or {}
    metal_state=metal_state or {}
    bond_lookup={}
    if bonds is not None and not bonds.empty:
        for _,r in bonds.iterrows(): bond_lookup[str(r.get('Instrument','')).strip().upper()]=r
    for i,r in x.iterrows():
        at=r.AssetType; sym=str(r.Symbol).upper(); name=str(r.Name).upper(); cp=np.nan
        if at in ('STOCK','ETF'):
            cp=stock.get(sym,np.nan)
        elif at=='MUTUAL FUND':
            cp=mf_code.get(sym,mf_name.get(name,np.nan))
        elif at=='GOLD PHYSICAL':
            cp=float(metal_state.get('GOLD',{}).get('quote',0) or 0) or np.nan
            if pd.isna(r['PriceBasisQty']) or r['PriceBasisQty']<=0:x.at[i,'PriceBasisQty']=10
        elif at=='SILVER PHYSICAL':
            cp=float(metal_state.get('SILVER',{}).get('quote',0) or 0) or np.nan
        elif at=='CRYPTO':
            cp=crypto_prices.get(sym,np.nan)
        elif at in ('BOND / FIXED INCOME','FD','RD','IPO','REIT / INVIT','NPS','PPF / GOVT SAVINGS','INTERNATIONAL','REAL ESTATE','PMS / AIF','CASH','OTHER'):
            cp=r.get('CurrentPrice₹',np.nan)
        if pd.notna(cp):x.at[i,'CurrentPrice₹']=cp
    return x


def analyse_portfolio(holdings,radar,mf=None,bonds=None):
    if holdings is None or holdings.empty:return holdings
    x=holdings.copy()
    # Stock/ETF recommendation map (prefer LONG for holdings review)
    rec={}
    if radar is not None and not radar.empty:
        rank={'LONG':0,'SHORT':1,'SWING':2}
        rr=radar.copy();rr['_cat']=rr.Category.map(rank).fillna(9);rr=rr.sort_values(['Symbol','_cat']).drop_duplicates('Symbol')
        rec={str(r.Symbol).upper():r for _,r in rr.iterrows()}
    mfmap={}
    if mf is not None and not mf.empty:
        for _,r in mf.iterrows():
            if pd.notna(r.get('Code')):mfmap[str(r.get('Code')).upper()]=r
            mfmap[str(r.get('Scheme','')).upper()]=r
    bondmap={}
    if bonds is not None and not bonds.empty:
        bondmap={str(r.get('Instrument','')).upper():r for _,r in bonds.iterrows()}

    actions=[];signals=[];scores=[];conf=[];reasons=[]
    for _,r in x.iterrows():
        at=r.AssetType;sym=str(r.Symbol).upper();name=str(r.Name).upper()
        action='REVIEW'; sig=''; score=np.nan; cf=''; reason=''
        if at in ('STOCK','ETF') and sym in rec:
            q=rec[sym];sig=str(q.get('Signal',q.get('Recommendation','')));score=q.get('Overall',np.nan);cf=str(q.get('Confidence',''))
            if sig=='STRONG BUY':action='ADD / HOLD' if str(q.get('EntryStatus',''))=='ENTRY VALID' else 'HOLD / ADD ON VALID ENTRY'
            elif sig in ('BUY','BUY ON PULLBACK'):action='HOLD / ADD ON VALID ENTRY'
            elif sig=='WATCH':action='HOLD / REVIEW'
            elif sig in ('AVOID','WEAK'):action='REDUCE / REVIEW EXIT'
            reason=f"{sig}; entry {q.get('EntryStatus','')}; overall {q.get('Overall','')}"
        elif at=='MUTUAL FUND':
            q=mfmap.get(sym,mfmap.get(name))
            if q is not None:
                sig=str(q.get('Action',''));score=q.get('Overall',np.nan);cf=str(q.get('Confidence',''))
                action='HOLD / CONTINUE SIP' if sig.startswith('INVEST') else ('HOLD / REVIEW' if sig=='WATCH' else 'REVIEW / CONSIDER SWITCH')
                reason=f"{sig}; risk {q.get('Risk','')}; score {q.get('Overall','')}"
        elif at in ('GOLD PHYSICAL','SILVER PHYSICAL'):
            action='REVIEW IN GOLD / SILVER TAB';sig='PHYSICAL HOLDING';reason='Use current physical buy-timing signal and staged accumulation zones.'
        elif at=='CRYPTO':
            action='REVIEW IN CRYPTO TAB';sig='CRYPTO HOLDING';reason='Use current crypto trend/structure card; crypto risk is higher.'
        elif at=='BOND / FIXED INCOME':
            q=bondmap.get(name,bondmap.get(sym))
            if q is not None:
                sig=str(q.get('Action',''));score=q.get('Overall',np.nan);cf=str(q.get('Risk',''))
                action='HOLD / CONSIDER' if sig=='CONSIDER' else ('HOLD / REVIEW' if sig=='WATCH' else 'REVIEW')
                reason=f"{sig}; yield {q.get('Yield%',np.nan)}%; credit {q.get('CreditRisk','')}"
        elif at=='FD': action='HOLD / REVIEW AT MATURITY';sig='FIXED RETURN';reason='Compare renewal rate and post-tax return at maturity.'
        elif at=='RD': action='CONTINUE / REVIEW RATE';sig='FIXED SAVING';reason='Review current rate, tenure and goal fit.'
        elif at=='IPO': action='TRACK LISTING / LONG-TERM REVIEW';sig='IPO ALLOTMENT';reason='Review listing performance and then move to normal Stock Radar after listing.'
        elif at=='REIT / INVIT': action='HOLD / REVIEW YIELD & PRICE';sig='LISTED INCOME';reason='Review market trend, distribution yield, leverage and asset quality.'
        elif at=='NPS': action='CONTINUE / REBALANCE';sig='RETIREMENT';reason='Review asset allocation, horizon and retirement goal rather than short-term price.'
        elif at=='PPF / GOVT SAVINGS': action='HOLD / CONTINUE';sig='GOVT SAVINGS';reason='Review current official rate, lock-in, tax treatment and goal fit.'
        elif at=='INTERNATIONAL': action='HOLD / REVIEW';sig='INTERNATIONAL';reason='Review global-market trend, currency risk and allocation limits.'
        elif at=='REAL ESTATE': action='HOLD / MANUAL REVIEW';sig='REAL ASSET';reason='Review current valuation, rent yield, costs, debt and liquidity manually.'
        elif at=='PMS / AIF': action='HOLD / MANAGER REVIEW';sig='ALTERNATIVE';reason='Review official statements, fees, drawdown and benchmark-relative performance.'
        elif at=='CASH': action='KEEP / DEPLOY WHEN QUALIFIED';sig='LIQUID';reason='Available for opportunities and emergency allocation.'
        actions.append(action);signals.append(sig);scores.append(score);conf.append(cf);reasons.append(reason)
    x['PortfolioAction']=actions;x['CurrentSignal']=signals;x['CurrentScore']=scores;x['CurrentConfidence']=conf;x['ReviewReason']=reasons
    return x


def position_size(capital,risk_pct,entry,stop,max_position_pct=25):
    capital=float(capital);risk_pct=float(risk_pct);entry=float(entry);stop=float(stop)
    risk_per_share=max(entry-stop,0);risk_budget=capital*risk_pct/100
    if risk_per_share<=0:return {'Quantity':0,'CapitalRequired₹':0,'MaxLoss₹':0,'PortfolioExposure%':0}
    qty_by_risk=int(risk_budget//risk_per_share);qty_by_cap=int((capital*max_position_pct/100)//entry)
    qty=max(0,min(qty_by_risk,qty_by_cap))
    return {'Quantity':qty,'CapitalRequired₹':round(qty*entry,2),'MaxLoss₹':round(qty*risk_per_share,2),'PortfolioExposure%':round(qty*entry/capital*100,1) if capital else 0}
