
from __future__ import annotations
from datetime import date, datetime
import numpy as np, pandas as pd

def ema(s, span): return s.ewm(span=span, adjust=False).mean()

def rsi(close, period=14):
    d=close.diff(); gain=d.clip(lower=0).rolling(period).mean()
    loss=(-d.clip(upper=0)).rolling(period).mean()
    rs=gain/loss.replace(0,np.nan)
    return (100-(100/(1+rs))).fillna(50)

def atr(df, period=14):
    prev=df["Close"].shift(1)
    tr=pd.concat([df["High"]-df["Low"],(df["High"]-prev).abs(),(df["Low"]-prev).abs()],axis=1).max(axis=1)
    return tr.rolling(period).mean()

def macd(close):
    m=ema(close,12)-ema(close,26); return m,ema(m,9)

def add_indicators(g):
    g=g.sort_values("Date").copy()
    g["EMA10"]=ema(g.Close,10); g["EMA21"]=ema(g.Close,21); g["EMA50"]=ema(g.Close,50)
    g["RSI14"]=rsi(g.Close); g["ATR14"]=atr(g); g["MACD"],g["MACDSignal"]=macd(g.Close)
    g["VolMA20"]=g.Volume.rolling(20).mean(); g["VolRatio"]=g.Volume/g.VolMA20.replace(0,np.nan)
    g["Ret5"]=g.Close.pct_change(5)*100; g["Ret20"]=g.Close.pct_change(20)*100; g["Ret60"]=g.Close.pct_change(60)*100
    g["High60"]=g.High.rolling(60).max(); g["Low60"]=g.Low.rolling(60).min()
    if "TradedValue" in g:
        g["TV20"]=g.TradedValue.rolling(20).median()/1e7
    else: g["TV20"]=np.nan
    return g

def clamp(x,lo=0,hi=100):
    try:return float(max(lo,min(hi,x)))
    except:return np.nan

def technical_score(r):
    s=0
    s+=18 if r.Close>r.EMA10 else 0; s+=18 if r.Close>r.EMA21 else 0; s+=15 if r.Close>r.EMA50 else 0
    s+=12 if r.EMA10>r.EMA21>r.EMA50 else 0; s+=12 if r.MACD>r.MACDSignal else 0
    if 52<=r.RSI14<=68:s+=12
    elif 45<=r.RSI14<52 or 68<r.RSI14<=75:s+=7
    if pd.notna(r.High60) and r.High60>0:
        dist=(r.High60-r.Close)/r.High60*100
        if 0<=dist<=5:s+=8
        elif dist<=12:s+=5
    ap=(r.ATR14/r.Close*100) if pd.notna(r.ATR14) and r.Close else np.nan
    if pd.notna(ap):
        if 1<=ap<=4:s+=5
        elif ap<6:s+=2
    return clamp(s)

def momentum_score(r):
    s=0
    if pd.notna(r.Ret5):s+=clamp((r.Ret5+3)*2.5,0,20)
    if pd.notna(r.Ret20):s+=clamp((r.Ret20+5)*1.7,0,30)
    if pd.notna(r.Ret60):s+=clamp((r.Ret60+10)*.8,0,20)
    if pd.notna(r.VolRatio):s+=clamp((r.VolRatio-.7)*20,0,15)
    if r.MACD>r.MACDSignal:s+=10
    if 50<=r.RSI14<=72:s+=5
    return clamp(s)

def _n(v,scale=1):
    try:
        if v is None or pd.isna(v):return np.nan
        return float(v)*scale
    except:return np.nan

def fundamental_score(row):
    if row is None or len(row)==0:return np.nan,0
    roce=_n(row.get("roce")); roe=_n(row.get("roe")); de=_n(row.get("de")); pe=_n(row.get("pe"))
    opm=_n(row.get("opm_pct")); p5=_n(row.get("profit_growth_5y")); s3=_n(row.get("sales_growth_3y"))
    ey=_n(row.get("earnings_growth_yoy")); ry=_n(row.get("revenue_growth_yoy"))
    metrics=[roce,roe,de,pe,opm, p5 if pd.notna(p5) else ey, s3 if pd.notna(s3) else ry]
    av=sum(pd.notna(x) for x in metrics)
    if av<4:return np.nan,av/7
    s=0; weights=0
    if pd.notna(roce):s+=clamp((roce-10)/30*25,0,25);weights+=25
    if pd.notna(roe):s+=clamp((roe-8)/25*20,0,20);weights+=20
    if pd.notna(de):s+=clamp((.8-de)/.8*15,0,15);weights+=15
    if pd.notna(pe):
        x=15 if 8<=pe<=30 else (11 if (0<pe<8 or 30<pe<=45) else (6 if 45<pe<=65 else 2))
        s+=x;weights+=15
    growth=p5 if pd.notna(p5) else ey
    if pd.notna(growth):s+=clamp(growth/40*15,0,15);weights+=15
    rev=s3 if pd.notna(s3) else ry
    if pd.notna(rev):s+=clamp(rev/30*10,0,10);weights+=10
    return clamp(s/weights*100 if weights else np.nan),av/7

def merge_fundamentals(seed,auto):
    frames=[]
    if seed is not None and not seed.empty:
        x=seed.copy(); x["symbol"]=x.symbol.astype(str).str.upper(); frames.append(x)
    if auto is not None and not auto.empty:
        y=auto.copy(); y["symbol"]=y.symbol.astype(str).str.upper(); frames.append(y)
    if not frames:return pd.DataFrame()
    allc=pd.concat(frames,ignore_index=True,sort=False)
    # Auto fields should supplement/override older seed fields without discarding richer seed metrics.
    rows=[]
    for sym,g in allc.groupby("symbol"):
        rec={"symbol":sym}
        # Start from first records then overwrite with non-null later values.
        for _,r in g.iterrows():
            for k,v in r.items():
                if k=="symbol":continue
                if pd.notna(v) and str(v)!="":
                    rec[k]=v
        rows.append(rec)
    return pd.DataFrame(rows)

def market_regime(latest):
    a21=(latest.Close>latest.EMA21).mean()*100; a50=(latest.Close>latest.EMA50).mean()*100
    adv=(latest.Close>latest.PrevClose).mean()*100 if "PrevClose" in latest else np.nan
    if a21>=60 and a50>=55 and (pd.isna(adv) or adv>=50):reg="BULLISH"
    elif a21<40 and a50<40:reg="WEAK"
    else:reg="CAUTIOUS"
    return reg,{"pct_above_ema21":a21,"pct_above_ema50":a50,"pct_advancers":adv}

def _levels(vals,atrv,reverse=False):
    xs=sorted([float(x) for x in vals if pd.notna(x)],reverse=reverse);out=[];gap=max(atrv*.35,.001)
    for x in xs:
        if not out or all(abs(x-y)>=gap for y in out):out.append(x)
        if len(out)==2:break
    return out

def trade_levels(g,category="SWING"):
    window={"SWING":65,"SHORT":140,"LONG":220}.get(category,65)
    g=g.tail(window).copy();r=g.iloc[-1];cur=float(r.Close)
    av=float(r.ATR14) if pd.notna(r.ATR14) and r.ATR14>0 else cur*.025
    highs=[];lows=[];hs=g.High.values;ls=g.Low.values
    for i in range(2,len(g)-2):
        if hs[i]>=max(hs[i-2:i+3]):highs.append(hs[i])
        if ls[i]<=min(ls[i-2:i+3]):lows.append(ls[i])
    below=_levels([x for x in lows if x<cur],av,True);above=_levels([x for x in highs if x>cur],av,False)
    if len(below)<2:
        for x in [g.Low.tail(20).min(),g.Low.tail(60).min(),g.Low.min()]:
            if x<cur and all(abs(x-y)>av*.3 for y in below):below.append(float(x))
            if len(below)>=2:break
    if len(above)<2:
        for x in [g.High.tail(20).max(),g.High.tail(60).max(),g.High.max()]:
            if x>cur and all(abs(x-y)>av*.3 for y in above):above.append(float(x))
            if len(above)>=2:break
    s1=below[0] if below else cur-1.2*av;s2=below[1] if len(below)>1 else cur-2.2*av
    r1=above[0] if above else cur+1.8*av;r2=above[1] if len(above)>1 else cur+3*av
    if category=="SWING": el=max(min(float(r.EMA21),cur),cur-.65*av);eh=cur+.15*av; mult1,mult2=1.8,2.8
    elif category=="SHORT": el=max(min(float(r.EMA21),cur),cur*.97);eh=cur+.2*av; mult1,mult2=2.2,3.8
    else: el=max(min(float(r.EMA50),cur),cur*.94);eh=cur+.25*av; mult1,mult2=3.0,5.0
    if el>=eh:el=cur-.35*av
    mid=(el+eh)/2; raw=max(s2,s1-.35*av,mid-1.5*av);stop=min(raw,mid-.75*av);risk=max(mid-stop,.5*av)
    tc=[x for x in [r1,r2] if x>=mid+1.25*risk];t1=min(tc) if tc else mid+mult1*risk
    tc2=[x for x in [r1,r2] if x>=t1+.5*risk];t2=min(tc2) if tc2 else mid+mult2*risk
    rr=(t1-mid)/risk if risk else np.nan
    return {"current":cur,"entry_low":el,"entry_high":eh,"s1":s1,"s2":s2,"r1":r1,"r2":r2,
            "t1":t1,"t2":t2,"stop":stop,"rr":rr,"t1_pct":(t1/mid-1)*100,
            "t2_pct":(t2/mid-1)*100,"risk_pct":(stop/mid-1)*100,"atr_pct":av/cur*100}

def combine(parts):
    g=[(s,w) for s,w in parts if pd.notna(s)]
    return sum(s*w for s,w in g)/sum(w for _,w in g) if g else np.nan

def _freshness(r,max_age):
    ds=r.get("fundamental_date") or r.get("data_as_of")
    if not ds:return False
    try:return (date.today()-pd.to_datetime(ds).date()).days<=max_age
    except:return False

def score_band(s):
    if pd.isna(s):return "NA"
    if s>=85:return "85+"
    if s>=78:return "78-84"
    if s>=70:return "70-77"
    return "<70"

def classify_confidence(sample,winrate,fresh_fund,category,overall=np.nan,fund=np.nan,fund_completeness=0):
    # Swing/Short confidence is earned from resolved historical evidence.
    if category in ("SWING","SHORT"):
        if pd.isna(sample) or sample<30:return "UNVERIFIED"
        if pd.notna(winrate) and sample>=50 and winrate>=60:return "HIGH"
        if pd.notna(winrate) and winrate>=52:return "MEDIUM"
        return "LOW"
    # Long-term uses a different evidence base. HIGH requires fresh, broad fundamental coverage.
    if not fresh_fund:return "UNVERIFIED"
    if pd.notna(fund) and fund>=82 and pd.notna(overall) and overall>=85 and fund_completeness>=0.80:return "HIGH"
    return "MEDIUM"

def _entry_status(cur,lv):
    av=max(float(lv.get("atr_pct",2.5))*cur/100,cur*.005)
    if cur<=lv["stop"]:return "SETUP INVALID"
    if lv["entry_low"]<=cur<=lv["entry_high"]:return "ENTRY VALID"
    if cur>lv["entry_high"]:
        return "WAIT FOR PULLBACK" if cur<=lv["entry_high"]+.75*av else "MISSED ENTRY / DON'T CHASE"
    if cur<lv["entry_low"]:
        return "WAIT FOR CONFIRMATION"
    return "REVIEW"

def _risk_level(risk_pct):
    x=abs(float(risk_pct))
    return "HIGH" if x>=6 else ("MEDIUM" if x>=3 else "LOW")

def build_radar(history,seed=None,auto=None,action_map=None,backtest_stats=None,walk_forward_stats=None,news_map=None,news_available=False,
                min_price=20,min_volume=100000,min_tv_cr=1.5,fund_max_age=45,strong_cfg=None,
                market_context=None,delivery_map=None,surveillance_map=None):
    """Build the decision universe for ALL NSE EQ symbols present in local history.

    Important distinction:
    - Every locally available NSE EQ symbol is kept in the output.
    - Liquidity/price/history rules determine recommendation ELIGIBILITY, not visibility.
    - Ineligible names are still searchable/rankable for research but cannot become BUY/STRONG BUY.
    """
    if history.empty:return pd.DataFrame(),{},{}
    strong_cfg=strong_cfg or {"overall":85,"technical":80,"momentum":80,"fundamental_long":75,"rr":2.0,"signals":50,"winrate":60}
    history=history.copy().sort_values(["Symbol","Date"])
    counts=history.groupby("Symbol").size().to_dict()
    all_symbols=sorted(history.Symbol.astype(str).str.upper().unique())

    enriched=[]; short_hist={}
    for sym,g in history.groupby("Symbol"):
        g=g.sort_values("Date").copy()
        if len(g)>=20:
            enriched.append(add_indicators(g))
        else:
            short_hist[str(sym).upper()]=g
    allx=pd.concat(enriched,ignore_index=True) if enriched else pd.DataFrame()

    # Market regime is computed from the quality/liquid universe only, so tiny/illiquid names
    # do not distort breadth. Visibility remains ALL NSE.
    if not allx.empty:
        latest_all=allx.sort_values("Date").groupby("Symbol").tail(1).copy()
        latest_all["HistorySessions"]=latest_all.Symbol.map(counts).fillna(0).astype(int)
        liquid=(latest_all.HistorySessions>=80)&(latest_all.Close>=min_price)&(latest_all.Volume>=min_volume)
        if latest_all.TV20.notna().any():
            liquid &= ((latest_all.TV20>=min_tv_cr)|latest_all.TV20.isna())
        regime_base=latest_all[liquid].copy()
        if regime_base.empty:regime_base=latest_all.copy()
        regime,breadth=market_regime(regime_base)
    else:
        latest_all=pd.DataFrame();regime="CAUTIOUS";breadth={"pct_above_ema21":0,"pct_above_ema50":0,"pct_advancers":0}

    fund=merge_fundamentals(seed,auto);fdict={str(r.symbol).upper():r for _,r in fund.iterrows()} if not fund.empty else {}
    action_map=action_map or {}; stats=backtest_stats if backtest_stats is not None else pd.DataFrame(); wfstats=walk_forward_stats if walk_forward_stats is not None else pd.DataFrame(); news_map=news_map or {}
    market_context=market_context or {}; delivery_map=delivery_map or {}; surveillance_map=surveillance_map or {}
    market_score=market_context.get('Score',np.nan); market_intel_regime=str(market_context.get('Regime','UNAVAILABLE'))
    market_reason=' '.join(str(x) for x in market_context.get('Reasons',[])[:4])
    rows=[];histories={}

    def eligibility_for(r):
        reasons=[]
        hs=int(r.get("HistorySessions",0))
        if hs<80:reasons.append(f"History {hs}<80 sessions")
        if pd.notna(r.Close) and float(r.Close)<float(min_price):reasons.append(f"Price < ₹{min_price}")
        if pd.notna(r.Volume) and float(r.Volume)<float(min_volume):reasons.append(f"Volume < {int(min_volume):,}")
        if pd.notna(r.TV20) and float(r.TV20)<float(min_tv_cr):reasons.append(f"Median traded value < ₹{min_tv_cr:g} Cr")
        return (len(reasons)==0, "; ".join(reasons) if reasons else "Passes price/liquidity/history gates")

    for _,r in latest_all.iterrows():
        sym=str(r.Symbol).upper();g=allx[allx.Symbol==sym].sort_values("Date");f=fdict.get(sym,{})
        eligible,elig_reason=eligibility_for(r)
        fs,comp=fundamental_score(f) if len(f) else (np.nan,0);fresh=_freshness(f,fund_max_age) if len(f) else False
        ts=technical_score(r);ms=momentum_score(r)
        for cat in ["SWING","SHORT","LONG"]:
            lv=trade_levels(g,cat)
            base_ov=combine([(ts,.55),(ms,.35),(fs,.10)]) if cat=="SWING" else (
               combine([(ts,.45),(ms,.30),(fs,.25)]) if cat=="SHORT" else combine([(ts,.20),(ms,.15),(fs,.65)]))
            # Market intelligence is a bounded context modifier, never a replacement for company evidence.
            market_adj=0.0
            if pd.notna(market_score):
                raw=max(-5.0,min(5.0,(float(market_score)-50.0)/10.0))
                market_adj=raw*(1.0 if cat=="SWING" else (0.8 if cat=="SHORT" else 0.45))
            delivery_pct=delivery_map.get(sym,np.nan)
            delivery_adj=0.0
            if cat in ("SWING","SHORT") and pd.notna(delivery_pct):
                delivery_adj=1.25 if float(delivery_pct)>=50 else (-1.25 if float(delivery_pct)<20 else 0.0)
            ov=max(0,min(100,base_ov+market_adj+delivery_adj)) if pd.notna(base_ov) else base_ov
            band=score_band(ov);bt_sample=np.nan;bt_wr=np.nan;wf_sample=np.nan;wf_wr=np.nan
            if not stats.empty and "Category" in stats and "ScoreBand" in stats:
                m=stats[(stats.Category==cat)&(stats.ScoreBand==band)]
                if not m.empty: bt_sample=float(m.iloc[0].Sample);bt_wr=float(m.iloc[0]["WinRate%"])
            if not wfstats.empty and cat in ("SWING","SHORT") and all(c in wfstats.columns for c in ["Category","Regime","ScoreBand"]):
                wm=wfstats[(wfstats.Category==cat)&(wfstats.Regime==regime)&(wfstats.ScoreBand==band)]
                if not wm.empty: wf_sample=float(wm.iloc[0].Sample);wf_wr=float(wm.iloc[0]["WinRate%"])
            act=action_map.get(sym,{});blocked=act.get("severity")=="BLOCK"
            surv=surveillance_map.get(sym,{}) if isinstance(surveillance_map,dict) else {}
            surv_severity=str(surv.get('severity','NONE')).upper(); surv_blocked=surv_severity=='BLOCK'
            news=news_map.get(sym,{}) if news_available else {"status":"UNKNOWN","subject":"News gate unavailable","date":""}
            news_status=news.get("status","PASS") if news_available else "UNKNOWN";news_blocked=news_status=="BLOCK"

            rec="AVOID"
            if eligible:
                if cat=="SWING":
                    threshold=83 if regime=="WEAK" else (80 if regime=="CAUTIOUS" else 78)
                    if ov>=threshold and ts>=70 and lv["rr"]>=1.7 and not blocked and not news_blocked and not surv_blocked:
                        rec="BUY" if (pd.notna(bt_sample) and bt_sample>=30 and pd.notna(bt_wr) and bt_wr>=52) else "WATCH"
                    elif ov>=64 and not blocked and not news_blocked and not surv_blocked:rec="WATCH"
                elif cat=="SHORT":
                    if ov>=75 and ts>=64 and lv["rr"]>=1.6 and not blocked and not news_blocked and not surv_blocked:
                        rec="BUY" if (pd.notna(bt_sample) and bt_sample>=30 and pd.notna(bt_wr) and bt_wr>=52) else "WATCH"
                    elif ov>=62 and not blocked and not news_blocked and not surv_blocked:rec="WATCH"
                else:
                    if not fresh or pd.isna(fs):rec="WATCH" if ov>=60 and not blocked and not news_blocked else "AVOID"
                    elif ov>=78 and fs>=72 and not blocked and not news_blocked and not surv_blocked:rec="BUY"
                    elif ov>=62 and not blocked and not news_blocked and not surv_blocked:rec="WATCH"

            conf=classify_confidence(bt_sample,bt_wr,fresh,cat,ov,fs,comp) if eligible else "LOW"
            if rec=="AVOID":conf="LOW"
            # Context can cap confidence, but cannot manufacture HIGH confidence.
            if conf=="HIGH" and market_context:
                if market_intel_regime=="RISK-OFF" or float(market_context.get('DataCompleteness%',100) or 0)<45:
                    conf="MEDIUM"
            entry_status=_entry_status(float(lv["current"]),lv)
            hist_ok=(cat=="LONG") or (pd.notna(bt_sample) and bt_sample>=strong_cfg.get("signals",50) and pd.notna(bt_wr) and bt_wr>=strong_cfg.get("winrate",60))
            walk_ok=(cat=="LONG") or (pd.notna(wf_sample) and wf_sample>=strong_cfg.get("walkforward_signals",20) and pd.notna(wf_wr) and wf_wr>=strong_cfg.get("walkforward_winrate",55))
            fund_ok=(cat!="LONG") or (fresh and pd.notna(fs) and fs>=strong_cfg.get("fundamental_long",75))
            strong=(eligible and rec=="BUY" and ov>=strong_cfg.get("overall",85) and ts>=strong_cfg.get("technical",80) and
                    ms>=strong_cfg.get("momentum",80) and lv["rr"]>=strong_cfg.get("rr",2.0) and hist_ok and fund_ok and walk_ok and
                    regime!="WEAK" and market_intel_regime!="RISK-OFF" and not blocked and not surv_blocked and
                    act.get("severity","NONE") not in ("REVIEW","BLOCK") and surv_severity not in ("REVIEW","BLOCK") and
                    news_status=="PASS" and entry_status=="ENTRY VALID" and conf=="HIGH")
            if strong:signal="STRONG BUY"
            elif rec=="BUY" and entry_status=="ENTRY VALID":signal="BUY"
            elif rec=="BUY" and entry_status=="WAIT FOR PULLBACK":signal="BUY ON PULLBACK"
            elif rec=="BUY" and entry_status.startswith("MISSED"):signal="WATCH"
            elif rec=="WATCH":signal="WATCH"
            else:signal="AVOID"
            if news_status=="REVIEW" and signal=="STRONG BUY":signal="BUY"
            if act.get("severity") == "REVIEW" and signal=="STRONG BUY":signal="BUY"
            if surv_severity=="REVIEW" and signal=="STRONG BUY":signal="BUY"
            # Severe market risk can downgrade a fresh short-horizon BUY to WATCH, but never upgrades a stock.
            if cat in ("SWING","SHORT") and pd.notna(market_score) and float(market_score)<=28 and signal in ("BUY","BUY ON PULLBACK"):
                signal="WATCH"
            if blocked or news_blocked or surv_blocked or not eligible:signal="AVOID"
            rows.append({
              "Category":cat,"Symbol":sym,"Company":f.get("company_name",sym) if len(f) else sym,
              "Sector":f.get("sector","") if len(f) else "","Eligibility":"ELIGIBLE" if eligible else "NOT ELIGIBLE",
              "EligibilityReason":elig_reason,"HistorySessions":int(r.HistorySessions),
              "Recommendation":rec,"Signal":signal,"EntryStatus":entry_status,"Overall":round(ov,1),"BaseOverall":round(base_ov,1) if pd.notna(base_ov) else np.nan,
              "MarketAdjustment":round(market_adj+delivery_adj,2),"MarketIntelligenceScore":round(float(market_score),1) if pd.notna(market_score) else np.nan,
              "InstitutionalBias":market_context.get('InstitutionalBias','UNAVAILABLE'),"DerivativesBias":market_context.get('DerivativesBias','UNAVAILABLE'),
              "BreadthBias":market_context.get('BreadthBias','UNAVAILABLE'),"MacroContext":market_context.get('MacroContext','UNAVAILABLE'),
              "IndiaVIX":market_context.get('IndiaVIX',np.nan),"MarketContext":market_reason,"DeliveryPct":round(float(delivery_pct),2) if pd.notna(delivery_pct) else np.nan,
              "SurveillanceRisk":surv_severity,"SurveillanceDetail":str(surv.get('detail',''))[:300],"Technical":round(ts,1),"Momentum":round(ms,1),
              "Fundamental":round(fs,1) if pd.notna(fs) else np.nan,"FundamentalFresh":"YES" if fresh else "NO",
              "FundamentalCompleteness%":round(comp*100),"Confidence":conf,"ConfidenceBasis":"Historical outcomes" if cat in ("SWING","SHORT") else "Fresh fundamentals + model quality",
              "BacktestSample":int(bt_sample) if pd.notna(bt_sample) else 0,"BacktestWinRate%":round(bt_wr,1) if pd.notna(bt_wr) else np.nan,
              "WalkForwardSample":int(wf_sample) if pd.notna(wf_sample) else 0,"WalkForwardWinRate%":round(wf_wr,1) if pd.notna(wf_wr) else np.nan,
              "Current":round(lv["current"],2),"EntryLow":round(lv["entry_low"],2),"EntryHigh":round(lv["entry_high"],2),
              "S1":round(lv["s1"],2),"S2":round(lv["s2"],2),"R1":round(lv["r1"],2),"R2":round(lv["r2"],2),
              "Target1":round(lv["t1"],2),"Target2":round(lv["t2"],2),"Potential1%":round(lv["t1_pct"],1),
              "Potential2%":round(lv["t2_pct"],1),"StopLoss":round(lv["stop"],2),"Risk%":round(lv["risk_pct"],1),"RiskLevel":_risk_level(lv["risk_pct"]),
              "RR":round(lv["rr"],2),"Duration":"5–25 days" if cat=="SWING" else ("1–4 months" if cat=="SHORT" else "1–3 years"),
              "RSI14":round(float(r.RSI14),1),"VolRatio":round(float(r.VolRatio),2) if pd.notna(r.VolRatio) else np.nan,
              "Ret20%":round(float(r.Ret20),1) if pd.notna(r.Ret20) else np.nan,"ATRPct":round(float(lv["atr_pct"]),2),
              "DataDate":pd.to_datetime(r.Date).date().isoformat(),"MarketRegime":regime,
              "CorporateActionRisk":act.get("severity","NONE"),"CorporateAction":act.get("purpose",""),"CorporateActionDate":act.get("ex_date",""),
              "NewsRisk":news_status,"NewsHeadline":news.get("subject","")[:260],"NewsDate":news.get("date","")
            })
        histories[sym]=g

    # Include brand-new / very short-history NSE symbols so the user can see that they exist.
    for sym,g in short_hist.items():
        rr=g.sort_values("Date").iloc[-1];cur=float(rr.Close);hs=len(g)
        for cat in ["SWING","SHORT","LONG"]:
            rows.append({
                "Category":cat,"Symbol":sym,"Company":sym,"Sector":"","Eligibility":"INSUFFICIENT HISTORY",
                "EligibilityReason":f"Only {hs} sessions available; minimum 20 for price-plan calculations and 80 for recommendations",
                "HistorySessions":hs,"Recommendation":"AVOID","Signal":"AVOID","EntryStatus":"INSUFFICIENT HISTORY",
                "Overall":np.nan,"BaseOverall":np.nan,"MarketAdjustment":0.0,"MarketIntelligenceScore":round(float(market_score),1) if pd.notna(market_score) else np.nan,
                "InstitutionalBias":market_context.get('InstitutionalBias','UNAVAILABLE'),"DerivativesBias":market_context.get('DerivativesBias','UNAVAILABLE'),
                "BreadthBias":market_context.get('BreadthBias','UNAVAILABLE'),"MacroContext":market_context.get('MacroContext','UNAVAILABLE'),
                "IndiaVIX":market_context.get('IndiaVIX',np.nan),"MarketContext":market_reason,"DeliveryPct":np.nan,"SurveillanceRisk":"UNKNOWN","SurveillanceDetail":"",
                "Technical":np.nan,"Momentum":np.nan,"Fundamental":np.nan,"FundamentalFresh":"NO","FundamentalCompleteness%":0,
                "Confidence":"UNVERIFIED","ConfidenceBasis":"Insufficient price history","BacktestSample":0,"BacktestWinRate%":np.nan,
                "WalkForwardSample":0,"WalkForwardWinRate%":np.nan,"Current":round(cur,2),"EntryLow":np.nan,"EntryHigh":np.nan,
                "S1":np.nan,"S2":np.nan,"R1":np.nan,"R2":np.nan,"Target1":np.nan,"Target2":np.nan,"Potential1%":np.nan,"Potential2%":np.nan,
                "StopLoss":np.nan,"Risk%":np.nan,"RiskLevel":"UNVERIFIED","RR":np.nan,
                "Duration":"5–25 days" if cat=="SWING" else ("1–4 months" if cat=="SHORT" else "1–3 years"),
                "RSI14":np.nan,"VolRatio":np.nan,"Ret20%":np.nan,"ATRPct":np.nan,
                "DataDate":pd.to_datetime(rr.Date).date().isoformat(),"MarketRegime":regime,
                "CorporateActionRisk":"UNKNOWN","CorporateAction":"","CorporateActionDate":"","NewsRisk":"UNKNOWN","NewsHeadline":"","NewsDate":""
            })

    out=pd.DataFrame(rows)
    if not out.empty:
        er={"ELIGIBLE":0,"NOT ELIGIBLE":1,"INSUFFICIENT HISTORY":2};sr={"STRONG BUY":0,"BUY":1,"BUY ON PULLBACK":2,"WATCH":3,"AVOID":4}
        out["_e"]=out.Eligibility.map(er).fillna(9);out["_r"]=out.Signal.map(sr).fillna(9)
        out=out.sort_values(["Category","_e","_r","Overall"],ascending=[True,True,True,False],na_position="last").drop(columns=["_e","_r"])
    return out,breadth,histories
