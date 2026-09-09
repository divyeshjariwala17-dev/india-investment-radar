from __future__ import annotations
from pathlib import Path
from datetime import date,timedelta,datetime
import json,re,requests,pandas as pd

BASE=Path(__file__).resolve().parent
DATA=BASE/'data';DATA.mkdir(parents=True,exist_ok=True)
CACHE=DATA/'corporate_events_all.csv'
ACTIONS_CACHE=DATA/'corporate_actions.csv'
HEADERS={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36',
         'Accept':'application/json,text/plain,*/*','Referer':'https://www.nseindia.com/companies-listing/corporate-filings-application'}

def _fmt(d):return d.strftime('%d-%m-%Y')
def _first(x,*keys):
    for k in keys:
        v=x.get(k)
        if v not in (None,''):return v
    return ''
def _norm_symbol(x):return str(x or '').strip().upper()
def _parse_date(x):
    if x in (None,'') or pd.isna(x):return None
    s=str(x).strip().replace('  ',' ')
    for fmt in ('%d-%b-%Y','%d-%m-%Y','%Y-%m-%d','%d-%b-%y','%d %b %Y','%d/%m/%Y','%d-%b-%Y %H:%M:%S','%d-%m-%Y %H:%M:%S'):
        try:return datetime.strptime(s,fmt).date()
        except Exception:pass
    try:return pd.to_datetime(s,dayfirst=True,errors='coerce').date()
    except Exception:return None

def _session():
    s=requests.Session()
    try:s.get('https://www.nseindia.com/',headers=HEADERS,timeout=12)
    except Exception:pass
    return s

def _get(s,url,params=None,timeout=30):
    r=s.get(url,params=params or {},headers=HEADERS,timeout=timeout);r.raise_for_status();return r.json()

def _impact(subject,event_type,event_date=None):
    t=(str(event_type)+' '+str(subject)).upper()
    block=('FRAUD','INSOLVENCY','NCLT','DEFAULT','BANKRUPTCY','WINDING UP','DELISTING','SUSPENSION OF TRADING','FORENSIC AUDIT')
    review=('FINANCIAL RESULT','RESULTS','BOARD MEETING','RIGHTS','RIGHT ISSUE','BUYBACK','MERGER','DEMERGER','AMALGAMATION','SCHEME OF ARRANGEMENT','ACQUISITION','DISPOSAL','FUND RAISING','QIP','PREFERENTIAL','RATING DOWNGRADE','PLEDGE','RESIGNATION','AUDITOR','LITIGATION','PENALTY','SHOW CAUSE','SEBI ORDER','MANAGEMENT CHANGE')
    adjust=('BONUS','SPLIT','SUB-DIVISION','SUB DIVISION','CONSOLIDATION','FACE VALUE','RIGHTS')
    info=('DIVIDEND','AGM','EGM','ANALYST','INVESTOR MEET','ANNUAL REPORT')
    sev='INFO';action='Review for information; no automatic block.'
    if any(k in t for k in block):sev='BLOCK';action='Do not issue a fresh high-confidence Buy until the event is reviewed and cleared.'
    elif any(k in t for k in adjust):sev='REVIEW';action='Corporate action can mechanically change price/quantity. Rebuild technical levels after the ex/effective date.'
    elif any(k in t for k in review):sev='REVIEW';action='Pause/verify before a fresh high-confidence entry; event can materially change risk or valuation.'
    elif any(k in t for k in info):sev='INFO';action='Informational/event timing only; check details if you hold the security.'
    if event_date:
        d=_parse_date(event_date)
        if d:
            delta=(d-date.today()).days
            if event_type in ('FINANCIAL RESULTS','BOARD MEETING') and 0<=delta<=3 and sev!='BLOCK':
                sev='REVIEW';action='Event is within 3 days. Avoid forcing a fresh Strong Buy before the event unless explicitly overridden.'
    return sev,action

def _event_row(symbol,company,event_type,subject,event_date='',announcement_date='',record_date='',ex_date='',source='NSE',raw=None):
    sev,action=_impact(subject,event_type,event_date or ex_date)
    return {'Symbol':_norm_symbol(symbol),'Company':str(company or ''),'EventType':event_type,'Subject':str(subject or ''),
            'EventDate':str(event_date or ''),'AnnouncementDate':str(announcement_date or ''),'RecordDate':str(record_date or ''),'ExDate':str(ex_date or ''),
            'Severity':sev,'SystemAction':action,'Source':source,'Raw':json.dumps(raw,default=str)[:1800] if isinstance(raw,(dict,list)) else str(raw or '')[:1800]}

def refresh_all_events(days_back=45,days_forward=120,status_cb=None):
    today=date.today();frm=today-timedelta(days=days_back);to=today+timedelta(days=days_forward);s=_session();rows=[];errors=[]
    # 1) Corporate actions
    try:
        if status_cb:status_cb('Corporate events 1/5: NSE corporate actions...')
        data=_get(s,'https://www.nseindia.com/api/corporates-corporateActions',{'index':'equities','from_date':_fmt(frm),'to_date':_fmt(to)})
        action_rows=[]
        for x in data or []:
            row=_event_row(_first(x,'symbol','sm_symbol'),_first(x,'comp','companyName'),'CORPORATE ACTION',_first(x,'subject','purpose'),
                           _first(x,'exDate','ex_date'),_first(x,'an_dt','announcementDate'),_first(x,'recDate','recordDate'),_first(x,'exDate','ex_date'),'NSE Corporate Actions',x)
            rows.append(row);action_rows.append({'symbol':row['Symbol'],'company':row['Company'],'purpose':row['Subject'],'ex_date':row['ExDate'],'record_date':row['RecordDate']})
        if action_rows:pd.DataFrame(action_rows).to_csv(ACTIONS_CACHE,index=False)
    except Exception as e:errors.append('actions: '+str(e))
    # 2) Board meetings
    try:
        if status_cb:status_cb('Corporate events 2/5: NSE board meetings...')
        data=_get(s,'https://www.nseindia.com/api/corporate-board-meetings',{'index':'equities','from_date':_fmt(frm),'to_date':_fmt(to)})
        for x in data or []:
            rows.append(_event_row(_first(x,'symbol','sm_symbol'),_first(x,'company','companyName','sm_name'),'BOARD MEETING',
                                   _first(x,'purpose','bm_purpose','desc','subject'),_first(x,'bm_date','meetingDate','date'),_first(x,'bm_timestamp','announcementDate','an_dt'),source='NSE Board Meetings',raw=x))
    except Exception as e:errors.append('board meetings: '+str(e))
    # 3) Announcements
    try:
        if status_cb:status_cb('Corporate events 3/5: NSE announcements...')
        data=_get(s,'https://www.nseindia.com/api/corporate-announcements',{'index':'equities','from_date':_fmt(frm),'to_date':_fmt(today)})
        for x in data or []:
            rows.append(_event_row(_first(x,'symbol','sm_name'),_first(x,'companyName'),'ANNOUNCEMENT',
                                   _first(x,'desc','subject','attchmntText'),_first(x,'an_dt','sort_date','date'),_first(x,'an_dt','sort_date','date'),source='NSE Announcements',raw=x))
    except Exception as e:errors.append('announcements: '+str(e))
    # 4) Financial results filings: quarterly, annual, half-yearly, others
    if status_cb:status_cb('Corporate events 4/5: NSE financial-results filings...')
    for period in ('Quarterly','Annual','Half-Yearly','Others'):
        try:
            data=_get(s,'https://www.nseindia.com/api/corporates-financial-results',{'index':'equities','period':period,'from_date':_fmt(frm),'to_date':_fmt(today)})
            for x in data or []:
                subj=f"{period} financial results" + (f" — {_first(x,'relatingTo','rel_to')}" if _first(x,'relatingTo','rel_to') else '')
                rows.append(_event_row(_first(x,'symbol','sm_symbol'),_first(x,'companyName','company','sm_name'),'FINANCIAL RESULTS',subj,
                                       _first(x,'broadCastDate','filingDate','toDate','date'),_first(x,'broadCastDate','filingDate'),source='NSE Financial Results',raw=x))
        except Exception as e:errors.append(f'{period} results: {e}')
    # 5) General event calendar (upcoming events/results etc.)
    try:
        if status_cb:status_cb('Corporate events 5/5: NSE event calendar...')
        data=_get(s,'https://www.nseindia.com/api/event-calendar')
        items=data if isinstance(data,list) else (data.get('data',[]) if isinstance(data,dict) else [])
        for x in items or []:
            rows.append(_event_row(_first(x,'symbol','sm_symbol'),_first(x,'company','companyName','sm_name'),'EVENT CALENDAR',
                                   _first(x,'purpose','event','subject','desc'),_first(x,'date','eventDate','bm_date'),_first(x,'announcementDate','an_dt'),source='NSE Event Calendar',raw=x))
    except Exception as e:errors.append('event calendar: '+str(e))
    df=pd.DataFrame(rows)
    if not df.empty:
        df=df[df.Symbol.astype(str).str.len()>0].copy()
        df=df.drop_duplicates(['Symbol','EventType','Subject','EventDate','ExDate'],keep='last')
        df.to_csv(CACHE,index=False)
    return {'ok':not df.empty,'count':len(df),'errors':errors,'message':f'Corporate events refreshed: {len(df):,} rows across actions, board meetings, announcements, financial results and event calendar.' + ((' Partial source issues: '+'; '.join(errors[:3])) if errors else '')}

def refresh_corporate_actions(days_back=30,days_forward=45,status_cb=None):
    # Backward-compatible call: unified refresh is safer and covers all event families.
    return refresh_all_events(days_back,days_forward,status_cb)

def load_all_events():
    if CACHE.exists():
        try:return pd.read_csv(CACHE,dtype={'Symbol':str})
        except Exception:pass
    return pd.DataFrame(columns=['Symbol','Company','EventType','Subject','EventDate','AnnouncementDate','RecordDate','ExDate','Severity','SystemAction','Source','Raw'])

def load_actions():
    if ACTIONS_CACHE.exists():
        try:return pd.read_csv(ACTIONS_CACHE)
        except Exception:pass
    return pd.DataFrame()

def _distance_days(row):
    for c in ('EventDate','ExDate','RecordDate','AnnouncementDate'):
        d=_parse_date(row.get(c,''))
        if d:return (d-date.today()).days,d
    return 9999,None

def event_risk_map(block_days=10):
    df=load_all_events();out={}
    if df.empty:return out
    rank={'BLOCK':3,'REVIEW':2,'INFO':1,'NONE':0}
    for _,r in df.iterrows():
        sym=_norm_symbol(r.get('Symbol'));sev=str(r.get('Severity','INFO')).upper();delta,d=_distance_days(r)
        if not sym:continue
        # Old announcements remain useful for 30-45d, but direct recommendation gating focuses on near events.
        near=(-max(block_days,3)<=delta<=max(block_days,3)) or sev=='BLOCK'
        if not near:continue
        item={'purpose':f"{r.get('EventType','')}: {r.get('Subject','')}", 'ex_date':d.isoformat() if d else '', 'severity':sev,
              'system_action':str(r.get('SystemAction','')),'event_type':str(r.get('EventType','')),'source':str(r.get('Source',''))}
        prev=out.get(sym)
        if prev is None or rank.get(sev,1)>rank.get(prev.get('severity','INFO'),1):out[sym]=item
        elif rank.get(sev,1)==rank.get(prev.get('severity','INFO'),1) and abs(delta)<abs(( _parse_date(prev.get('ex_date'))-date.today()).days if _parse_date(prev.get('ex_date')) else 9999):out[sym]=item
    return out

def action_risk_map(block_days=10):return event_risk_map(block_days)

def events_for_symbol(symbol,days_back=90,days_forward=180):
    df=load_all_events();sym=_norm_symbol(symbol)
    if df.empty:return df
    x=df[df.Symbol.astype(str).str.upper().eq(sym)].copy();today=date.today()
    keep=[]
    for i,r in x.iterrows():
        delta,_=_distance_days(r)
        if -days_back<=delta<=days_forward:keep.append(i)
    return x.loc[keep] if keep else x.iloc[0:0]
