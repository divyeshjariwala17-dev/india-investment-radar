from __future__ import annotations
import pandas as pd

def build_daily_actions(radar=None,alerts=None,events=None,portfolio_health=None,data_health=None,cross_asset=None):
    rows=[]
    if data_health is not None and not data_health.empty:
        for _,r in data_health[data_health.Status.isin(['MISSING','OLD'])].head(4).iterrows():rows.append({'Priority':1,'Type':'DATA','Item':r.Data,'Action':'REFRESH / REVIEW','Why':f"{r.Status}: {r.Detail or r.Source}"})
    if events is not None and not events.empty and 'Severity' in events.columns:
        ev=events.copy();rank={'BLOCK':0,'REVIEW':1,'INFO':2};ev['_rank']=ev.Severity.astype(str).map(rank).fillna(9);ev=ev.sort_values('_rank')
        for _,r in ev[ev.Severity.astype(str).isin(['BLOCK','REVIEW'])].head(5).iterrows():rows.append({'Priority':1 if str(r.get('Severity'))=='BLOCK' else 2,'Type':'EVENT','Item':str(r.get('Symbol','')),'Action':'BLOCK FRESH BUY' if str(r.get('Severity'))=='BLOCK' else 'REVIEW BEFORE BUY','Why':f"{r.get('EventType','')}: {r.get('Subject','')}"})
    if radar is not None and not radar.empty and 'Signal' in radar.columns:
        mask=radar.Signal.astype(str).eq('STRONG BUY') & radar.get('EntryStatus',pd.Series(['']*len(radar))).astype(str).eq('ENTRY VALID')
        for _,r in radar[mask].sort_values('Overall',ascending=False).drop_duplicates('Symbol').head(5).iterrows():rows.append({'Priority':2,'Type':'OPPORTUNITY','Item':str(r.Symbol),'Action':'STRONG BUY — REVIEW ENTRY','Why':f"{r.Category} • score {r.Overall}/100 • R:R {r.get('RR','')}"})
        if not mask.any():
            buys=radar[radar.Signal.astype(str).isin(['BUY','BUY ON PULLBACK'])].sort_values('Overall',ascending=False).drop_duplicates('Symbol').head(3)
            for _,r in buys.iterrows():rows.append({'Priority':3,'Type':'WATCH','Item':str(r.Symbol),'Action':str(r.Signal),'Why':f"{r.Category} • {r.get('EntryStatus','')} • score {r.Overall}/100"})
    if alerts is not None and not alerts.empty:
        for _,r in alerts.tail(10).iloc[::-1].head(4).iterrows():rows.append({'Priority':2,'Type':'ALERT','Item':str(r.get('Symbol','')),'Action':str(r.get('Type','')),'Why':str(r.get('Message',''))})
    if portfolio_health:
        w=portfolio_health.get('warnings')
        if w is not None and not w.empty:
            for _,r in w.head(4).iterrows():rows.append({'Priority':2 if r.Level=='HIGH' else 3,'Type':'PORTFOLIO','Item':str(r.Item),'Action':'REBALANCE REVIEW','Why':str(r.Message)})
    out=pd.DataFrame(rows)
    if out.empty:return pd.DataFrame([{'Priority':4,'Type':'NO ACTION','Item':'Today','Action':'DO NOTHING / KEEP PLAN','Why':'No urgent validated action was found. Do not force an investment.'}])
    return out.drop_duplicates(['Type','Item','Action']).sort_values(['Priority','Type']).reset_index(drop=True)

def headline(actions):
    if actions is None or actions.empty:return 'No urgent action'
    if (actions.Type=='DATA').any():return 'Data refresh/review needed before relying on new calls'
    if ((actions.Type=='OPPORTUNITY') & actions.Action.astype(str).str.contains('STRONG BUY')).any():return 'Qualified opportunity detected'
    if (actions.Type=='EVENT').any():return 'Corporate event review required'
    if (actions.Type=='PORTFOLIO').any():return 'Portfolio review suggested'
    return 'No urgent action — follow the existing plan'
