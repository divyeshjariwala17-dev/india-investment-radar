from __future__ import annotations
from pathlib import Path
import json, time, re, requests, pandas as pd, numpy as np

BASE=Path(__file__).resolve().parent
DATA=BASE/'data'
DATA.mkdir(parents=True,exist_ok=True)
UNIVERSE_CACHE=DATA/'mf_universe.csv'
LEGACY_CACHE=DATA/'mf_cache.json'
HISTORY_DIR=DATA/'mf_histories'
HISTORY_DIR.mkdir(parents=True,exist_ok=True)
API='https://api.mfapi.in'
AMFI_NAV_ALL='https://www.amfiindia.com/spages/NAVAll.txt'
HEADERS={'User-Agent':'Mozilla/5.0','Accept':'text/plain,application/json,*/*'}

UNIVERSE_COLUMNS=['SchemeCode','SchemeName','NAV','NAVDate','FundHouse','SchemeType','Category','CategoryGroup','Plan','Option','ISIN1','ISIN2','Source']

def _plan(name):
    n=str(name).upper()
    return 'Direct' if 'DIRECT' in n else ('Regular' if 'REGULAR' in n else 'Unspecified')

def _option(name):
    n=str(name).upper()
    if 'GROWTH' in n:return 'Growth'
    if 'IDCW' in n:return 'IDCW'
    if 'DIVIDEND' in n:return 'Dividend/IDCW'
    return 'Other/Unspecified'

def _category_group(category,name=''):
    t=(str(category)+' '+str(name)).upper()
    if any(k in t for k in ['EQUITY','FLEXI','MULTI CAP','LARGE CAP','MID CAP','SMALL CAP','ELSS','VALUE','CONTRA','FOCUSED','DIVIDEND YIELD','SECTOR','THEMATIC']):return 'Equity'
    if any(k in t for k in ['DEBT','OVERNIGHT','LIQUID','MONEY MARKET','DURATION','CORPORATE BOND','CREDIT RISK','BANKING AND PSU','BANKING & PSU','GILT','FLOATER']):return 'Debt'
    if any(k in t for k in ['HYBRID','BALANCED','ARBITRAGE','EQUITY SAVINGS','MULTI ASSET']):return 'Hybrid'
    if any(k in t for k in ['RETIREMENT','CHILDREN','SOLUTION']):return 'Solution Oriented'
    if any(k in t for k in ['INDEX','ETF','FUND OF FUND','FOF','GOLD','INTERNATIONAL','OVERSEAS']):return 'Other / Index / FoF'
    return 'Other'

def _parse_amfi_nav_text(text):
    rows=[]; scheme_type=''; category=''; fund_house=''
    for raw in str(text).splitlines():
        line=raw.strip().lstrip('\ufeff')
        if not line:continue
        if line.lower().startswith('scheme code;'):continue
        if ';' not in line:
            up=line.upper()
            if 'SCHEMES' in up and ('OPEN ENDED' in up or 'CLOSE ENDED' in up or 'INTERVAL' in up):
                scheme_type=line.split('(')[0].strip(' -')
                m=re.search(r'\((.*?)\)',line)
                category=m.group(1).strip() if m else line
            elif 'MUTUAL FUND' in up and len(line)<160:
                fund_house=line
            continue
        parts=[x.strip() for x in line.split(';')]
        if len(parts)<6:continue
        try: code=str(int(float(parts[0])))
        except Exception:continue
        name=parts[3].strip(); nav=pd.to_numeric(parts[4],errors='coerce'); dt=parts[5].strip()
        rows.append({'SchemeCode':code,'SchemeName':name,'NAV':float(nav) if pd.notna(nav) else np.nan,'NAVDate':dt,
                     'FundHouse':fund_house,'SchemeType':scheme_type,'Category':category,'CategoryGroup':_category_group(category,name),
                     'Plan':_plan(name),'Option':_option(name),'ISIN1':parts[1] if len(parts)>1 else '',
                     'ISIN2':parts[2] if len(parts)>2 else '','Source':'AMFI Complete NAV'})
    df=pd.DataFrame(rows,columns=UNIVERSE_COLUMNS)
    if not df.empty:df=df.drop_duplicates('SchemeCode',keep='last').reset_index(drop=True)
    return df

def _fallback_mfapi_universe(timeout=25):
    r=requests.get(f'{API}/mf',headers=HEADERS,timeout=timeout);r.raise_for_status();data=r.json()
    rows=[]
    for x in data or []:
        code=str(x.get('schemeCode','')).strip();name=str(x.get('schemeName','')).strip()
        if not code or not name:continue
        rows.append({'SchemeCode':code,'SchemeName':name,'NAV':np.nan,'NAVDate':'','FundHouse':'','SchemeType':'','Category':'',
                     'CategoryGroup':_category_group('',name),'Plan':_plan(name),'Option':_option(name),'ISIN1':'','ISIN2':'','Source':'MFAPI universe fallback'})
    return pd.DataFrame(rows,columns=UNIVERSE_COLUMNS).drop_duplicates('SchemeCode') if rows else pd.DataFrame(columns=UNIVERSE_COLUMNS)

def refresh_universe(status_cb=None,timeout=30):
    if status_cb:status_cb('Refreshing ALL mutual-fund schemes from official AMFI NAV universe...')
    err=''
    try:
        r=requests.get(AMFI_NAV_ALL,headers=HEADERS,timeout=timeout);r.raise_for_status()
        df=_parse_amfi_nav_text(r.text)
        if len(df)>=500:
            df.to_csv(UNIVERSE_CACHE,index=False)
            return {'ok':True,'count':len(df),'source':'AMFI Complete NAV','message':f'All mutual-fund universe refreshed: {len(df):,} active NAV rows from AMFI.'}
        err=f'AMFI returned only {len(df)} parsed rows'
    except Exception as e:err=str(e)
    try:
        if status_cb:status_cb('AMFI universe unavailable; trying mutual-fund master fallback...')
        df=_fallback_mfapi_universe(timeout)
        if not df.empty:
            df.to_csv(UNIVERSE_CACHE,index=False)
            return {'ok':True,'count':len(df),'source':'MFAPI fallback','message':f'Mutual-fund universe refreshed via fallback: {len(df):,} schemes. AMFI issue: {err}'}
    except Exception as e2:
        return {'ok':False,'count':0,'source':'','message':f'Mutual-fund universe refresh unavailable. AMFI: {err}; fallback: {e2}'}
    return {'ok':False,'count':0,'source':'','message':f'Mutual-fund universe refresh unavailable: {err}'}

def load_universe():
    if UNIVERSE_CACHE.exists():
        try:
            df=pd.read_csv(UNIVERSE_CACHE,dtype={'SchemeCode':str})
            for c in UNIVERSE_COLUMNS:
                if c not in df.columns:df[c]=''
            return df[UNIVERSE_COLUMNS]
        except Exception:pass
    return pd.DataFrame(columns=UNIVERSE_COLUMNS)

def universe_summary():
    u=load_universe()
    return {'schemes':len(u),'fund_houses':u.FundHouse.replace('',np.nan).nunique() if not u.empty else 0,
            'categories':u.Category.replace('',np.nan).nunique() if not u.empty else 0,'direct':int((u.Plan=='Direct').sum()) if not u.empty else 0}

def _history_file(code):return HISTORY_DIR/f'{str(code).strip()}.json'

def _save_history(code,payload):
    obj={'fetched_at':pd.Timestamp.now().isoformat(),'payload':payload}
    _history_file(code).write_text(json.dumps(obj,ensure_ascii=False),encoding='utf-8')

def _load_history_obj(code):
    p=_history_file(code)
    if p.exists():
        try:return json.loads(p.read_text(encoding='utf-8'))
        except Exception:pass
    return None

def fetch_code(code,timeout=25):
    r=requests.get(f'{API}/mf/{str(code).strip()}',headers=HEADERS,timeout=timeout);r.raise_for_status();j=r.json()
    if not j or j.get('status')!='SUCCESS':return None
    return j

def refresh_scheme_code(code,status_cb=None,timeout=25):
    if status_cb:status_cb(f'Loading full NAV history for scheme {code}...')
    try:
        j=fetch_code(code,timeout)
        if not j:return {'ok':False,'code':str(code),'message':'No NAV history returned.'}
        _save_history(code,j)
        return {'ok':True,'code':str(code),'message':'Full NAV history saved.'}
    except Exception as e:return {'ok':False,'code':str(code),'message':str(e)}

def _word_score(name,query):
    n=str(name).lower();q=str(query).lower();score=0
    if q in n:score+=20
    for w in [x for x in re.split(r'\W+',q) if len(x)>2]:
        if w in n:score+=1
    if 'direct' in n:score+=4
    if 'growth' in n:score+=4
    return score

def _find_code_for_query(query):
    u=load_universe()
    if not u.empty:
        s=u.copy();s['_score']=s.SchemeName.map(lambda x:_word_score(x,query));s=s.sort_values('_score',ascending=False)
        if not s.empty and s.iloc[0]._score>0:return str(s.iloc[0].SchemeCode)
    try:
        r=requests.get(f'{API}/mf/search',params={'q':query},headers=HEADERS,timeout=20);r.raise_for_status();res=r.json()
        if res:return str(sorted(res,key=lambda x:_word_score(x.get('schemeName',''),query),reverse=True)[0].get('schemeCode'))
    except Exception:pass
    return None

def refresh(searches,max_funds=None,status_cb=None):
    # Compatibility: refresh starter/deep-analysis schemes; ALL schemes are handled by refresh_universe().
    updated=failed=0;use=list(searches or []);use=use[:max_funds] if max_funds else use
    for i,q in enumerate(use):
        if status_cb:status_cb(f'Mutual-fund deep history {i+1}/{len(use)}: {q}')
        code=_find_code_for_query(q)
        if code and refresh_scheme_code(code).get('ok'):updated+=1
        else:failed+=1
        time.sleep(.02)
    return {'updated':updated,'failed':failed}

def filter_universe(search='',fund_house='All',category='All',category_group='All',plan='All',option='All'):
    u=load_universe().copy()
    if u.empty:return u
    if search:
        q=str(search).lower();u=u[u.SchemeName.astype(str).str.lower().str.contains(re.escape(q),regex=True,na=False)]
    if fund_house!='All':u=u[u.FundHouse.astype(str).eq(str(fund_house))]
    if category!='All':u=u[u.Category.astype(str).eq(str(category))]
    if category_group!='All':u=u[u.CategoryGroup.astype(str).eq(str(category_group))]
    if plan!='All':u=u[u.Plan.astype(str).eq(str(plan))]
    if option!='All':u=u[u.Option.astype(str).eq(str(option))]
    return u.reset_index(drop=True)

def refresh_filtered(search='',fund_house='All',category='All',category_group='All',plan='Direct',option='Growth',max_funds=40,status_cb=None):
    u=filter_universe(search,fund_house,category,category_group,plan,option)
    if u.empty:return {'updated':0,'failed':0,'candidates':0,'message':'No schemes match this filter.'}
    # Prefer currently active rows with NAV, and avoid duplicate plan variants with same name fragments.
    u=u.sort_values(['NAV','SchemeName'],ascending=[False,True],na_position='last').head(max_funds)
    updated=failed=0
    for i,r in u.iterrows():
        if status_cb:status_cb(f"Analyzing MF {updated+failed+1}/{len(u)}: {r.SchemeName}")
        res=refresh_scheme_code(r.SchemeCode)
        if res.get('ok'):updated+=1
        else:failed+=1
        time.sleep(.02)
    return {'updated':updated,'failed':failed,'candidates':len(u),'message':f'Analyzed {updated} of {len(u)} matching schemes.'}

def _preferred_keywords(horizon_days,risk='MODERATE'):
    d=int(horizon_days);r=str(risk).upper()
    if d<=30:return ['OVERNIGHT','LIQUID','MONEY MARKET','ULTRA SHORT']
    if d<=90:return ['LIQUID','ULTRA SHORT','LOW DURATION','MONEY MARKET']
    if d<=365:return ['SHORT DURATION','CORPORATE BOND','BANKING AND PSU','BANKING & PSU','LOW DURATION','MONEY MARKET']
    if d<1095:return ['BALANCED ADVANTAGE','DYNAMIC ASSET ALLOCATION','CONSERVATIVE HYBRID','CORPORATE BOND','SHORT DURATION']
    if d<1825:return ['INDEX','LARGE CAP','FLEXI CAP','BALANCED ADVANTAGE','AGGRESSIVE HYBRID']
    if r=='HIGH':return ['FLEXI CAP','INDEX','LARGE CAP','LARGE & MID CAP','MID CAP','SMALL CAP','MULTI CAP']
    if r=='LOW':return ['INDEX','LARGE CAP','BALANCED ADVANTAGE','FLEXI CAP']
    return ['FLEXI CAP','INDEX','LARGE CAP','LARGE & MID CAP','BALANCED ADVANTAGE','MULTI CAP']

def refresh_recommended_for_horizon(horizon_days,risk='MODERATE',max_funds=30,status_cb=None):
    u=load_universe()
    if u.empty:
        res=refresh_universe(status_cb=status_cb)
        u=load_universe()
        if u.empty:return {'updated':0,'failed':0,'candidates':0,'message':res.get('message','No MF universe.')}
    x=u[(u.Plan.eq('Direct')) & (u.Option.eq('Growth'))].copy()
    kws=_preferred_keywords(horizon_days,risk)
    mask=pd.Series(False,index=x.index)
    text=(x.Category.astype(str)+' '+x.SchemeName.astype(str)).str.upper()
    for k in kws:mask|=text.str.contains(re.escape(k),regex=True,na=False)
    x=x[mask]
    if x.empty:x=u[(u.Plan.eq('Direct')) & (u.Option.eq('Growth'))].copy()
    # one plan per scheme code is already unique; keep manageable automatic batch
    x=x.sort_values(['NAV','SchemeName'],ascending=[False,True],na_position='last').head(max_funds)
    updated=failed=0
    for idx,(_,r) in enumerate(x.iterrows(),1):
        if status_cb:status_cb(f'Preparing exact MF options {idx}/{len(x)}: {r.SchemeName}')
        # Full histories do not need repeated same-day fetches.
        obj=_load_history_obj(r.SchemeCode)
        fresh=False
        if obj:
            try:fresh=(pd.Timestamp.now()-pd.to_datetime(obj.get('fetched_at'))).total_seconds()<86400
            except Exception:pass
        if fresh:updated+=1;continue
        res=refresh_scheme_code(r.SchemeCode)
        if res.get('ok'):updated+=1
        else:failed+=1
    return {'updated':updated,'failed':failed,'candidates':len(x),'message':f'Prepared {updated} exact Mutual Fund candidates for this duration/risk.'}

def _to_series(payload):
    rows=[]
    for x in payload.get('data',[]):
        try:rows.append((pd.to_datetime(x['date'],dayfirst=True),float(x['nav'])))
        except Exception:pass
    if not rows:return pd.Series(dtype=float)
    s=pd.Series({d:v for d,v in rows}).sort_index();return s[~s.index.duplicated(keep='last')]

def _ret_near(s,days):
    if len(s)<2:return np.nan
    target=s.index[-1]-pd.Timedelta(days=days);prior=s[s.index<=target]
    return (s.iloc[-1]/prior.iloc[-1]-1)*100 if not prior.empty else np.nan

def _cagr(s,years):
    if len(s)<2:return np.nan
    target=s.index[-1]-pd.Timedelta(days=int(365.25*years));prior=s[s.index<=target]
    if prior.empty:return np.nan
    actual=(s.index[-1]-prior.index[-1]).days/365.25
    return ((s.iloc[-1]/prior.iloc[-1])**(1/actual)-1)*100 if actual>=years*.75 else np.nan

def _max_dd(s):return (s/s.cummax()-1).min()*100 if not s.empty else np.nan

def _scenario(s,calendar_days):
    if len(s)<100:return (np.nan,np.nan,np.nan,0)
    vals=[];idx=s.index
    for i in range(len(s)):
        j=idx.searchsorted(idx[i]+pd.Timedelta(days=calendar_days))
        if j<len(s):vals.append((s.iloc[j]/s.iloc[i]-1)*100)
    x=pd.Series(vals,dtype=float).dropna()
    if len(x)<20:return (np.nan,np.nan,np.nan,len(x))
    return (x.quantile(.20),x.median(),x.quantile(.80),len(x))

def _analyze_payload(payload, fallback_code='', fallback_name=''):
    meta=payload.get('meta',{});s=_to_series(payload)
    if len(s)<60:return None
    daily=s.pct_change().dropna();vol=daily.std()*np.sqrt(252)*100 if len(daily)>30 else np.nan
    ret1y=_ret_near(s,365);c3=_cagr(s,3);c5=_cagr(s,5);dd=_max_dd(s);mom=_ret_near(s,90)
    try:positive_months=(s.resample('ME').last().pct_change().dropna()>0).mean()*100
    except Exception:
        try:positive_months=(s.resample('M').last().pct_change().dropna()>0).mean()*100
        except Exception:positive_months=np.nan
    score=50
    if pd.notna(c3):score+=max(-10,min(20,(c3-6)*1.5))
    elif pd.notna(ret1y):score+=max(-10,min(15,ret1y-5))
    if pd.notna(dd):score+=max(-15,min(10,(25+dd)*.5))
    if pd.notna(positive_months):score+=max(-8,min(10,(positive_months-50)*.4))
    if pd.notna(mom):score+=max(-8,min(10,mom*.3))
    score=max(0,min(100,score))
    risk='HIGH' if (pd.notna(vol) and vol>=18) or (pd.notna(dd) and dd<=-30) else ('MEDIUM' if (pd.notna(vol) and vol>=8) or (pd.notna(dd) and dd<=-12) else 'LOW')
    action='INVEST / ACCUMULATE' if score>=72 else ('WATCH' if score>=58 else 'AVOID')
    scenarios={}
    for lab,days in [('1 Month',30),('3 Months',91),('6 Months',182),('1 Year',365),('3 Years',1096),('5 Years',1826)]:
        lo,med,hi,n=_scenario(s,days);scenarios[lab]={'low':lo,'median':med,'high':hi,'sample':n}
    samples=[v['sample'] for v in scenarios.values() if v['sample']];conf='HIGH' if samples and max(samples)>=100 and len(s)>750 else ('MEDIUM' if len(s)>350 else 'LOW')
    code=str(meta.get('scheme_code') or fallback_code);name=meta.get('scheme_name') or fallback_name or code
    u=load_universe();urow=None
    if not u.empty and code:
        m=u[u.SchemeCode.astype(str).eq(code)]
        if not m.empty:urow=m.iloc[0]
    category=meta.get('scheme_category','') or (urow.Category if urow is not None else '')
    house=meta.get('fund_house','') or (urow.FundHouse if urow is not None else '')
    reasons=[]
    if pd.notna(c3):reasons.append(f"3Y CAGR is {c3:.1f}%"+(' and is strong' if c3>=12 else (' and is acceptable' if c3>=8 else ' and is modest')))
    elif pd.notna(ret1y):reasons.append(f'1Y return is {ret1y:.1f}%')
    if pd.notna(c5):reasons.append(f'5Y CAGR is {c5:.1f}%')
    if pd.notna(dd):reasons.append(f"Maximum historical drawdown is {dd:.1f}%"+(' (controlled)' if dd>-15 else (' (moderate)' if dd>-30 else ' (high)')))
    if pd.notna(positive_months):reasons.append(f'Positive-month consistency is {positive_months:.0f}%')
    if pd.notna(mom):reasons.append(f'Recent 3-month momentum is {mom:+.1f}%')
    if urow is not None:reasons.append(f"Plan/option: {urow.Plan} / {urow.Option}")
    if action=='INVEST / ACCUMULATE':change='Recommendation can weaken if rolling returns deteriorate, drawdown expands materially, or recent momentum/consistency turns negative.'
    elif action=='WATCH':change='Upgrade requires a stronger overall score, better rolling-return consistency and acceptable drawdown; deterioration can move it to AVOID.'
    else:change='Upgrade requires materially better returns/consistency with controlled drawdown and improving momentum.'
    row={'Scheme':name,'Code':code,'Category':category,'CategoryGroup':_category_group(category,name),'FundHouse':house,
         'Plan':_plan(name) if urow is None else urow.Plan,'Option':_option(name) if urow is None else urow.Option,
         'NAV':round(float(s.iloc[-1]),4),'NAVDate':str(s.index[-1].date()),'Action':action,'Overall':round(score,1),'Risk':risk,'Confidence':conf,
         '1Y%':round(ret1y,2) if pd.notna(ret1y) else np.nan,'3Y_CAGR%':round(c3,2) if pd.notna(c3) else np.nan,'5Y_CAGR%':round(c5,2) if pd.notna(c5) else np.nan,
         'Volatility%':round(vol,2) if pd.notna(vol) else np.nan,'MaxDrawdown%':round(dd,2) if pd.notna(dd) else np.nan,'PositiveMonths%':round(positive_months,1) if pd.notna(positive_months) else np.nan,
         'Momentum3M%':round(mom,2) if pd.notna(mom) else np.nan,'Reason':' • '.join(reasons),'WhatChanges':change}
    return row,{'series':s,'scenarios':scenarios,'row':row}

def analyze_scheme_code(code):
    obj=_load_history_obj(code)
    if not obj:return None
    return _analyze_payload(obj.get('payload',{}),str(code))

def analyze_cached():
    rows=[];details={};seen=set()
    for p in HISTORY_DIR.glob('*.json'):
        code=p.stem
        try:
            obj=json.loads(p.read_text(encoding='utf-8'));res=_analyze_payload(obj.get('payload',{}),code)
            if not res:continue
            row,d=res;rows.append(row);details[str(row['Code'])]=d;seen.add(str(row['Code']))
        except Exception:continue
    # Migrate/accept prior v6 caches so users do not lose previous analyzed funds.
    if LEGACY_CACHE.exists():
        try:
            legacy=json.loads(LEGACY_CACHE.read_text(encoding='utf-8'))
            for q,obj in legacy.items():
                p=obj.get('payload',{});code=str(p.get('meta',{}).get('scheme_code') or q)
                if code in seen:continue
                res=_analyze_payload(p,code,q)
                if not res:continue
                row,d=res;rows.append(row);details[str(row['Code'])]=d
        except Exception:pass
    out=pd.DataFrame(rows)
    if not out.empty:out=out.sort_values(['Overall','Scheme'],ascending=[False,True]).drop_duplicates('Code')
    return out,details
