from __future__ import annotations
from pathlib import Path
from datetime import date,timedelta,datetime
import requests,pandas as pd

BASE=Path(__file__).resolve().parent
CACHE=BASE/"data"/"corporate_announcements.csv"
HEADERS={
 "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
 "Accept":"application/json,text/plain,*/*",
 "Referer":"https://www.nseindia.com/companies-listing/corporate-filings-announcements"
}
BLOCK_WORDS=("FRAUD","INSOLVENCY","NCLT","DEFAULT","BANKRUPTCY","WINDING UP","SEARCH","RAID","FORENSIC AUDIT","SUSPENSION","DELISTING")
REVIEW_WORDS=("RESIGNATION","AUDITOR","PENALTY","SHOW CAUSE","SEBI","RATING DOWNGRADE","DOWNGRADE","PLEDGE","LOSS","LITIGATION","RESULT","FINANCIAL RESULTS","BOARD MEETING")

def refresh_announcements(days=10,status_cb=None):
    to=date.today();frm=to-timedelta(days=days)
    params={"index":"equities","from_date":frm.strftime("%d-%m-%Y"),"to_date":to.strftime("%d-%m-%Y")}
    url="https://www.nseindia.com/api/corporate-announcements"
    s=requests.Session()
    try:
        if status_cb:status_cb("Refreshing official NSE corporate announcements...")
        s.get("https://www.nseindia.com/",headers=HEADERS,timeout=12)
        r=s.get(url,params=params,headers=HEADERS,timeout=25);r.raise_for_status();data=r.json()
        rows=[]
        for x in data or []:
            sym=str(x.get("symbol") or x.get("sm_name") or "").strip().upper()
            subject=str(x.get("desc") or x.get("subject") or x.get("attchmntText") or x.get("an_dt") or "").strip()
            dt=x.get("an_dt") or x.get("sort_date") or x.get("date") or ""
            rows.append({"symbol":sym,"date":dt,"subject":subject,"raw":str(x)[:1000]})
        pd.DataFrame(rows).to_csv(CACHE,index=False)
        return {"count":len(rows),"message":"OK"}
    except Exception as e:
        return {"count":0,"message":f"Announcement refresh unavailable: {e}"}

def load_announcements():
    if CACHE.exists():
        try:return pd.read_csv(CACHE)
        except Exception:pass
    return pd.DataFrame()

def risk_map():
    df=load_announcements();out={}
    if df.empty:return out
    order={"PASS":0,"REVIEW":1,"BLOCK":2,"UNKNOWN":1}
    for _,r in df.iterrows():
        sym=str(r.get("symbol","")).upper().strip()
        if not sym:continue
        txt=(str(r.get("subject",''))+" "+str(r.get("raw",''))).upper()
        status="PASS"
        if any(w in txt for w in BLOCK_WORDS):status="BLOCK"
        elif any(w in txt for w in REVIEW_WORDS):status="REVIEW"
        item={"status":status,"subject":str(r.get("subject",''))[:260],"date":str(r.get("date",''))}
        if sym not in out or order[status]>order[out[sym]["status"]]:out[sym]=item
    return out
