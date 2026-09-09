from __future__ import annotations

from pathlib import Path
from datetime import date, timedelta
import math
import numpy as np
import pandas as pd

from asset_radar import analyze_asset
from physical_metals import rolling_scenarios, timing_decision

BASE = Path(__file__).resolve().parent
PLANS = BASE / "data" / "allocation_plans.csv"
RISK_NUM = {"LOW": 1, "MODERATE": 2, "HIGH": 3, "VERY HIGH": 4}


def _num(v, default=np.nan):
    try:
        x = float(v)
        return x if np.isfinite(x) else default
    except Exception:
        return default


def _txt(v, default=""):
    if v is None:
        return default
    try:
        if pd.isna(v):
            return default
    except Exception:
        pass
    return str(v)


def _risk_num(v):
    s = _txt(v).upper()
    if "VERY HIGH" in s:
        return 4
    if "HIGH" in s:
        return 3
    if "MODERATE" in s or "MEDIUM" in s:
        return 2
    return 1


def horizon_days_from_choice(choice: str, exact_date=None, today=None) -> int:
    today = today or date.today()
    if choice == "Exact Required Date":
        if exact_date is None:
            return 180
        if hasattr(exact_date, "date"):
            exact_date = exact_date.date()
        return max(1, int((exact_date - today).days))
    return {
        "7 Days": 7, "15 Days": 15, "1 Month": 30, "45 Days": 45,
        "3 Months": 91, "6 Months": 182, "9 Months": 274, "1 Year": 365,
        "2 Years": 730, "3 Years": 1095, "5 Years": 1825, "10+ Years": 3650,
    }.get(choice, 182)


def human_horizon(days: int) -> str:
    d = max(1, int(days))
    if d < 31:
        return f"{d} days"
    if d < 365:
        return f"{round(d/30.44,1):g} months"
    return f"{round(d/365.25,1):g} years"


def auto_risk(horizon_days: int, liquidity_need="Normal", essential_money=False, mode="ONE-TIME") -> str:
    d = int(horizon_days)
    if essential_money:
        return "LOW" if d <= 730 else "MODERATE"
    if str(liquidity_need).upper().startswith("HIGH"):
        return "LOW" if d <= 365 else "MODERATE"
    if d <= 90:
        return "LOW"
    if d <= 1095:
        return "MODERATE"
    if d >= 1825 and str(mode).upper().startswith("MONTH"):
        return "HIGH"
    return "MODERATE"


def required_return_for_target(amount, target_gain=None, target_pct=None, horizon_days=365):
    amount = max(float(amount or 0), 1.0)
    if target_pct is None and target_gain is not None:
        target_pct = float(target_gain) / amount * 100
    if target_pct is None:
        return None
    years = max(horizon_days / 365.25, 1 / 365.25)
    annual = ((1 + float(target_pct) / 100) ** (1 / years) - 1) * 100 if float(target_pct) > -100 else np.nan
    return {"TargetPct": round(float(target_pct), 2), "RequiredAnnualizedPct": round(annual, 2) if pd.notna(annual) else np.nan}


def _fit_horizon(min_days, max_days, horizon_days):
    min_days = int(min_days or 0); max_days = int(max_days or 36500); h = int(horizon_days)
    if h < min_days:
        return max(0.0, 100 - 130 * ((min_days - h) / max(min_days, 1)))
    if h > max_days:
        return max(35.0, 100 - 40 * min((h - max_days) / max(max_days, 1), 1.5))
    return 100.0


def _fit_risk(candidate_risk, profile):
    a = _risk_num(candidate_risk); b = RISK_NUM.get(str(profile).upper(), 2)
    if a <= b:
        return 100 - max(0, b - a - 1) * 4
    return max(0, 100 - 42 * (a - b))


def _compound_pct(annual_pct, days):
    if pd.isna(annual_pct):
        return np.nan
    years = max(days / 365.25, 1 / 365.25)
    return ((1 + float(annual_pct) / 100) ** years - 1) * 100


def _scenario_values(amount, down_pct, base_pct, up_pct):
    amount = float(amount)
    def v(p):
        return round(amount * (1 + float(p) / 100), 2) if pd.notna(p) else np.nan
    return {
        "DownsideValueRs": v(down_pct), "BaseValueRs": v(base_pct), "UpsideValueRs": v(up_pct),
        "BaseGainRs": round(amount * float(base_pct) / 100, 2) if pd.notna(base_pct) else np.nan,
    }


def _candidate(**kw):
    base = {
        "AssetClass": "Other", "Category": "", "Instrument": "", "Decision": "WATCH",
        "Score": 50.0, "Risk": "MODERATE", "Confidence": "LOW", "Timing": "WAIT",
        "MinHorizonDays": 0, "MaxHorizonDays": 36500, "LockInDays": 0,
        "MinInvestmentRs": 1000.0, "DownsidePct": np.nan, "BasePct": np.nan, "UpsidePct": np.nan,
        "ProbabilityPositivePct": np.nan, "Sample": np.nan, "Reason": "", "WhatChanges": "",
        "DataStatus": "FRESH", "Source": "", "ProductKey": "", "Conditional": False,
    }
    base.update(kw)
    return base


def _stock_candidates(radar: pd.DataFrame, horizon_days: int):
    if radar is None or radar.empty:
        return []
    wanted = ["SWING"] if horizon_days <= 45 else (["SHORT", "SWING"] if horizon_days <= 240 else ["LONG", "SHORT"])
    x = radar[radar.Category.astype(str).isin(wanted)].copy()
    if "Eligibility" in x.columns:
        x = x[x.Eligibility.astype(str).eq("ELIGIBLE")]
    rank = {"STRONG BUY": 0, "BUY": 1, "BUY ON PULLBACK": 2, "WATCH": 3, "AVOID": 4}
    x["_sig"] = x.Signal.map(rank).fillna(9)
    x = x.sort_values(["_sig", "Overall"], ascending=[True, False]).drop_duplicates("Symbol").head(30)
    out=[]
    for _,r in x.iterrows():
        sig=_txt(r.get("Signal"),"WATCH"); es=_txt(r.get("EntryStatus"),"")
        timing="INVEST NOW" if es=="ENTRY VALID" and sig in ("STRONG BUY","BUY") else ("BUY ON DIP" if "PULLBACK" in es or sig=="BUY ON PULLBACK" else "WAIT")
        riskpct=abs(_num(r.get("Risk%"),np.nan))
        if pd.isna(riskpct):
            cur=_num(r.get("Current"),np.nan); stop=_num(r.get("StopLoss"),np.nan)
            riskpct=abs((cur-stop)/cur*100) if pd.notna(cur) and cur else 8
        basep=_num(r.get("Potential1%"),6); upp=_num(r.get("Potential2%"),max(basep*1.6,basep+3)); downp=-max(2,min(25,riskpct))
        prob=_num(r.get("WalkForwardWinRate%"),_num(r.get("BacktestWinRate%"),np.nan)); sample=_num(r.get("WalkForwardSample"),_num(r.get("BacktestSample"),np.nan))
        cat=_txt(r.get("Category")); min_d=7 if cat=="SWING" else (21 if cat=="SHORT" else 180); max_d=60 if cat=="SWING" else (365 if cat=="SHORT" else 3650)
        out.append(_candidate(
            AssetClass="Stocks",Category=cat,Instrument=_txt(r.get("Symbol")),Decision=sig,Score=_num(r.get("Overall"),50),
            Risk=_txt(r.get("RiskLevel"),"HIGH"),Confidence=_txt(r.get("Confidence"),"LOW"),Timing=timing,
            MinHorizonDays=min_d,MaxHorizonDays=max_d,DownsidePct=downp,BasePct=basep,UpsidePct=upp,
            ProbabilityPositivePct=prob,Sample=sample,
            Reason=f"{_txt(r.get('Company'))} • {_txt(r.get('Reason')) or 'Stock score, trend, momentum, entry and risk/reward were evaluated.'}",
            WhatChanges=_txt(r.get("WhatChanges")) or "Entry leaves the valid zone, trend/momentum weakens, event risk rises or risk/reward deteriorates.",
            Source="NSE EOD + local validation",ProductKey=f"STOCK:{_txt(r.get('Symbol'))}",Conditional=timing!="INVEST NOW"
        ))
    return out


def _mf_candidates(mf: pd.DataFrame, horizon_days: int, monthly=False):
    if mf is None or mf.empty:return []
    out=[]
    for _,r in mf.copy().sort_values("Overall",ascending=False).head(40).iterrows():
        cat=_txt(r.get("Category")).upper(); name=_txt(r.get("Scheme")); text=cat+" "+name.upper()
        eq=any(k in text for k in ["EQUITY","FLEXI","MID","SMALL","LARGE","INDEX","BLUECHIP","ELSS"])
        debt=any(k in text for k in ["DEBT","LIQUID","OVERNIGHT","MONEY MARKET","CORPORATE BOND","SHORT TERM","ULTRA SHORT"])
        hybrid="HYBRID" in text or "BALANCED" in text
        min_d=1095 if eq else (365 if hybrid else (30 if debt else 365))
        risk=_txt(r.get("Risk"),"MODERATE"); action=_txt(r.get("Action"),"WATCH")
        base_ann=_num(r.get("3Y_CAGR%"),_num(r.get("5Y_CAGR%"),_num(r.get("1Y%"),np.nan)))
        vol=abs(_num(r.get("Volatility%"),12 if eq else 5)); hyears=max(horizon_days/365.25,1/12)
        basep=_compound_pct(base_ann,horizon_days) if pd.notna(base_ann) else np.nan; vol_h=vol*math.sqrt(hyears)
        downp=basep-vol_h if pd.notna(basep) else (-18 if eq else -5); upp=basep+0.75*vol_h if pd.notna(basep) else (18 if eq else 8)
        dd=_num(r.get("MaxDrawdown%"),np.nan)
        if pd.notna(dd) and dd<0:downp=min(downp,dd)
        timing="SIP" if monthly else ("STAGGER" if eq and horizon_days>=365 else "INVEST NOW")
        out.append(_candidate(
            AssetClass="Mutual Funds",Category=_txt(r.get("Category")),Instrument=name,Decision=action,Score=_num(r.get("Overall"),50),Risk=risk,
            Confidence=_txt(r.get("Confidence"),"MEDIUM"),Timing=timing,MinHorizonDays=min_d,DownsidePct=round(downp,2) if pd.notna(downp) else np.nan,
            BasePct=round(basep,2) if pd.notna(basep) else np.nan,UpsidePct=round(upp,2) if pd.notna(upp) else np.nan,
            ProbabilityPositivePct=_num(r.get("PositiveMonths%"),np.nan),Reason=_txt(r.get("Reason")),WhatChanges=_txt(r.get("WhatChanges")),
            Source=f"MF NAV cache {_txt(r.get('NAVDate'))}",ProductKey=f"MF:{_txt(r.get('Code')) or name}"
        ))
    return out


def _bond_candidates(bonds: pd.DataFrame, horizon_days: int):
    if bonds is None or bonds.empty:return []
    out=[]
    for _,r in bonds.iterrows():
        ytm=_num(r.get("Yield%"),np.nan)
        if pd.isna(ytm):continue
        maty=max(_num(r.get("MaturityYears"),1),0.01); days=int(maty*365.25); basep=_compound_pct(ytm,min(horizon_days,days))
        risk=_txt(r.get("Risk"),"LOW"); rn=_risk_num(risk); downp=basep-{1:.5,2:2,3:5,4:8}.get(rn,2); upp=basep+{1:.4,2:1.5,3:3,4:5}.get(rn,1.5)
        score=_num(r.get("Overall"),60)-min(20,abs(days-horizon_days)/max(horizon_days,1)*10)
        out.append(_candidate(
            AssetClass="Fixed Income",Category=_txt(r.get("Type")),Instrument=_txt(r.get("Instrument")),Decision=_txt(r.get("Action"),"WATCH"),
            Score=max(0,score),Risk=risk,Confidence="HIGH" if rn==1 else "MEDIUM",Timing="INVEST NOW",MinHorizonDays=max(7,int(days*.25)),MaxHorizonDays=max(days*2,90),
            DownsidePct=round(downp,2),BasePct=round(basep,2),UpsidePct=round(upp,2),Reason=_txt(r.get("Reason")),WhatChanges=_txt(r.get("WhatChanges")),
            Source="User-entered/verified current YTM",ProductKey=f"BOND:{_txt(r.get('Instrument'))}"
        ))
    return out


def _other_candidates(opts: pd.DataFrame, horizon_days: int):
    if opts is None or opts.empty:return []
    out=[]; years=horizon_days/365.25
    for _,r in opts.iterrows():
        active=_txt(r.get("ActiveStatus"),"ACTIVE").upper()
        if active not in ("ACTIVE","NEW INVESTMENT ALLOWED",""):
            continue
        rate=_num(r.get("RateOrExpectedReturn%"),np.nan); lock_y=max(_num(r.get("LockInYears"),0),0); ten_y=max(_num(r.get("TenureYears"),max(years,1)),.01)
        mininv=max(_num(r.get("MinInvestment₹"),1000),0); risk=_txt(r.get("Risk"),"MODERATE"); rn=_risk_num(risk)
        basep=_compound_pct(rate,horizon_days) if pd.notna(rate) else np.nan; spread={1:.5,2:4,3:10,4:18}.get(rn,4)*math.sqrt(max(years,.08))
        downp=basep-spread if pd.notna(basep) else np.nan; upp=basep+spread*.75 if pd.notna(basep) else np.nan
        option=_txt(r.get("Option")); cat=_txt(r.get("Category"))
        if option.upper() in ("REIT / INVIT","INTERNATIONAL ETF / FUND"):min_d=1095
        elif "PPF" in option.upper() or "NPS" in option.upper():min_d=max(365,int(lock_y*365.25))
        else:min_d=max(1,int(min(lock_y if lock_y>0 else .25,ten_y)*365.25))
        out.append(_candidate(
            AssetClass="Other Investments",Category=cat,Instrument=option,Decision="CONSIDER" if pd.notna(rate) else "INPUT REQUIRED",Score=62 if pd.notna(rate) else 42,
            Risk=risk,Confidence="MEDIUM" if pd.notna(rate) else "LOW",Timing="INVEST NOW" if pd.notna(rate) and lock_y<=years else "WAIT / REVIEW",
            MinHorizonDays=min_d,MaxHorizonDays=max(int(ten_y*365.25*1.5),min_d),LockInDays=int(lock_y*365.25),MinInvestmentRs=mininv,
            DownsidePct=downp,BasePct=basep,UpsidePct=upp,Reason=_txt(r.get("Eligibility/Notes")),
            WhatChanges="Update the current official/product rate, eligibility, liquidity, tax treatment or holding period assumptions.",
            DataStatus=("FRESH" if pd.notna(rate) and _txt(r.get("DataConfidence"),"PARTIAL").upper() in ("HIGH","MEDIUM") else "PARTIAL"),
            Source=_txt(r.get("Source/Updated")),ProductKey=f"OTHER:{option}"
        ))
    return out


def _metal_candidates(history: pd.DataFrame, radar: pd.DataFrame, cfg: dict, state: dict, horizon_days: int):
    if history is None or history.empty or radar is None or radar.empty:return []
    out=[]; available=set(radar.Symbol.astype(str))
    for metal in ("GOLD","SILVER"):
        mc=cfg.get("precious_assets",{}).get(metal,{}); proxy=next((s for s in mc.get("symbols",[]) if s in available),None)
        if not proxy:continue
        g=history[history.Symbol.astype(str).eq(proxy)].copy(); cards,chart=analyze_asset(g,proxy,mc.get("name",metal),"METAL","₹")
        if cards.empty:continue
        cat="SWING" if horizon_days<=45 else ("SHORT" if horizon_days<=180 else "LONG"); rr=cards[cards.Category.eq(cat)]; r=(rr.iloc[0] if not rr.empty else cards.iloc[-1])
        metal_state=(state or {}).get(metal,{})
        quote=_num(metal_state.get("quote"),0); quote_source=_txt(metal_state.get('quote_source'),'LOCAL')
        decision,action=timing_decision(r); sc=rolling_scenarios(chart)
        nearest=min([(7,"1 Week"),(15,"15 Days"),(30,"1 Month"),(91,"3 Months"),(182,"6 Months"),(365,"1 Year")],key=lambda t:abs(t[0]-horizon_days))[1]
        sr=sc[sc.Duration.eq(nearest)] if not sc.empty else pd.DataFrame()
        if not sr.empty:
            s=sr.iloc[0];downp=_num(s.get("Low%"),-8);basep=_num(s.get("Median%"),5);upp=_num(s.get("High%"),12);prob=_num(s.get("ProbabilityPositive%"),np.nan);sample=_num(s.get("Samples"),np.nan)
        else:
            downp=-abs(_num(r.get("Risk%"),8));basep=_num(r.get("Potential1%"),6);upp=_num(r.get("Potential2%"),12);prob=_num(r.get("WinRate%"),np.nan);sample=_num(r.get("HistoricalSignals"),np.nan)
        timing="INVEST NOW" if "BUY" in decision and "WAIT" not in decision and "DO NOT" not in decision else ("BUY ON DIP" if "DIP" in decision else "WAIT")
        reason=_txt(r.get("Reason"));
        if quote<=0:reason=(reason+" • Local physical quote is not entered; exact ₹ buy zones require it.").strip(" •")
        out.append(_candidate(
            AssetClass=f"Physical {metal.title()}",Category="PHYSICAL",Instrument=f"Physical {metal.title()}",Decision=decision,Score=_num(r.get("Overall"),50),
            Risk=_txt(r.get("Risk"),"MODERATE"),Confidence=_txt(r.get("Confidence"),"LOW"),Timing=timing,MinHorizonDays=30,
            DownsidePct=downp,BasePct=basep,UpsidePct=upp,ProbabilityPositivePct=prob,Sample=sample,Reason=reason+" • "+action,
            WhatChanges=_txt(r.get("WhatChanges")),DataStatus=("PARTIAL" if quote_source=='AUTO_REFERENCE' else ("FRESH" if quote>0 else "PARTIAL")),
            Source=(f"NSE {proxy} trend proxy + automatic converted reference (not local retail)" if quote_source=='AUTO_REFERENCE' else f"NSE {proxy} trend proxy + local physical quote"),
            ProductKey=f"PHYSICAL:{metal}",Conditional=timing!="INVEST NOW"
        ))
    return out


def _crypto_candidates(crypto_loader, cfg:dict, horizon_days:int):
    if crypto_loader is None:return []
    out=[]; cat="SWING" if horizon_days<=45 else ("SHORT" if horizon_days<=240 else "LONG")
    for sym in cfg.get("crypto_symbols",[]):
        try:
            g=crypto_loader(sym)
            if g is None or g.empty:continue
            cards,_=analyze_asset(g,sym,sym,"CRYPTO","USDT"); rr=cards[cards.Category.eq(cat)]
            if rr.empty:continue
            r=rr.iloc[0]; sig=_txt(r.Signal); timing="INVEST NOW" if sig in ("STRONG BUY","BUY") and _txt(r.EntryStatus)=="ENTRY VALID" else ("BUY ON DIP" if "PULLBACK" in _txt(r.EntryStatus) else "WAIT")
            out.append(_candidate(
                AssetClass="Crypto",Category=cat,Instrument=sym,Decision=sig,Score=_num(r.Overall,50),Risk=_txt(r.Risk,"VERY HIGH"),Confidence=_txt(r.Confidence,"LOW"),Timing=timing,
                MinHorizonDays=30,DownsidePct=-abs(_num(r.get("Risk%"),15)),BasePct=_num(r.get("Potential1%"),10),UpsidePct=_num(r.get("Potential2%"),20),
                ProbabilityPositivePct=_num(r.get("WinRate%"),np.nan),Sample=_num(r.get("HistoricalSignals"),np.nan),Reason=_txt(r.Reason),WhatChanges=_txt(r.WhatChanges),
                Source="Crypto daily market history",ProductKey=f"CRYPTO:{sym}",Conditional=timing!="INVEST NOW"
            ))
        except Exception:continue
    return out


def _ipo_candidates(ipos: pd.DataFrame):
    if ipos is None or ipos.empty:return []
    out=[]
    for _,r in ipos.head(20).iterrows():
        dec=_txt(r.get("Decision"),"WATCH")
        if dec not in ("STRONG APPLY","APPLY","WATCH"):continue
        out.append(_candidate(
            AssetClass="IPO",Category=_txt(r.get("Board")),Instrument=_txt(r.get("Company")),Decision=dec,Score=_num(r.get("Overall"),50),
            Risk=_txt(r.get("Risk"),"HIGH"),Confidence=_txt(r.get("Confidence"),"LOW"),Timing="APPLY DURING ISSUE WINDOW",MinHorizonDays=30,
            Reason=_txt(r.get("Reason")),WhatChanges=_txt(r.get("WhatChanges")),Source="NSE current issue + verified IPO inputs",
            ProductKey=f"IPO:{_txt(r.get('IPO_ID')) or _txt(r.get('Company'))}",Conditional=True
        ))
    return out


def portfolio_exposure(holdings: pd.DataFrame):
    if holdings is None or holdings.empty:return {}
    x=holdings.copy(); val=pd.to_numeric(x.get("CurrentValue₹"),errors="coerce") if "CurrentValue₹" in x else pd.Series(dtype=float); inv=pd.to_numeric(x.get("Invested₹"),errors="coerce") if "Invested₹" in x else pd.Series(dtype=float)
    x["_value"]=val.where(val.notna() & (val>0),inv).fillna(0); total=float(x._value.sum())
    if total<=0:return {}
    mapping={"STOCK":"Stocks","ETF":"ETFs","MUTUAL FUND":"Mutual Funds","GOLD PHYSICAL":"Physical Gold","SILVER PHYSICAL":"Physical Silver","CRYPTO":"Crypto","BOND / FIXED INCOME":"Fixed Income","FD":"Fixed Income","RD":"Fixed Income","IPO":"IPO","CASH":"Reserve"}
    x["_class"]=x.AssetType.astype(str).str.upper().map(mapping).fillna("Other Investments")
    return {k:round(float(v)/total*100,1) for k,v in x.groupby("_class")._value.sum().items()}


def collect_candidates(radar=None,mf=None,bonds=None,ipos=None,opts=None,history=None,cfg=None,metal_state=None,crypto_loader=None,horizon_days=182,monthly=False):
    cfg=cfg or {}; rows=[]
    rows+=_stock_candidates(radar,horizon_days); rows+=_mf_candidates(mf,horizon_days,monthly); rows+=_bond_candidates(bonds,horizon_days)
    rows+=_metal_candidates(history,radar,cfg,metal_state or {},horizon_days); rows+=_crypto_candidates(crypto_loader,cfg,horizon_days); rows+=_ipo_candidates(ipos); rows+=_other_candidates(opts,horizon_days)
    return pd.DataFrame(rows)


def _asset_caps(profile,horizon_days):
    p=str(profile).upper()
    if p=="LOW":caps={"Stocks":5,"Mutual Funds":20,"Physical Gold":15,"Physical Silver":5,"Crypto":0,"IPO":0,"Fixed Income":75,"Other Investments":60}
    elif p=="HIGH":caps={"Stocks":35,"Mutual Funds":45,"Physical Gold":20,"Physical Silver":10,"Crypto":12,"IPO":10,"Fixed Income":40,"Other Investments":35}
    else:caps={"Stocks":20,"Mutual Funds":40,"Physical Gold":18,"Physical Silver":8,"Crypto":5,"IPO":5,"Fixed Income":55,"Other Investments":45}
    if horizon_days<=30:caps.update({"Stocks":0,"Mutual Funds":15,"Physical Gold":5,"Physical Silver":0,"Crypto":0,"IPO":0,"Fixed Income":85,"Other Investments":80})
    elif horizon_days<=90:caps.update({"Stocks":8 if p!="LOW" else 0,"Mutual Funds":20,"Physical Gold":10,"Physical Silver":4,"Crypto":0,"IPO":0,"Fixed Income":75,"Other Investments":70})
    elif horizon_days<=365:
        caps["Crypto"]=0 if p!="HIGH" else 5; caps["IPO"]=0 if p=="LOW" else 5
    return caps


def score_candidates(candidates: pd.DataFrame, amount: float, horizon_days: int, risk_profile: str, existing_exposure=None, include_existing=True, exclusions=None):
    if candidates is None or candidates.empty:return pd.DataFrame(),pd.DataFrame()
    exclusions=set(exclusions or []); exposure=existing_exposure or {}; eligible=[]; rejected=[]
    for _,r in candidates.iterrows():
        cls=_txt(r.AssetClass); reasons=[]; mininv=_num(r.get("MinInvestmentRs"),1000); lock=int(_num(r.get("LockInDays"),0))
        if cls in exclusions:reasons.append("Excluded by user")
        if mininv>amount:reasons.append(f"Minimum investment ₹{mininv:,.0f} exceeds available amount")
        if lock>horizon_days:reasons.append("Lock-in exceeds the required money-back period")
        hfit=_fit_horizon(_num(r.get("MinHorizonDays"),0),_num(r.get("MaxHorizonDays"),36500),horizon_days)
        if hfit<45:reasons.append("Recommended holding period does not fit your duration")
        rfit=_fit_risk(r.get("Risk"),risk_profile)
        if rfit<25:reasons.append(f"Risk is too high for {risk_profile} profile")
        if _txt(r.get("Decision")).upper() in ("AVOID","DO NOT BUY NOW","INPUT REQUIRED"):reasons.append("Current product call is not investable")
        if _txt(r.get("DataStatus")).upper() in ("FAILED","STALE"):reasons.append("Required data is stale/failed")
        timing=_txt(r.get("Timing"),"WAIT"); timing_fit=100 if timing in ("INVEST NOW","BUY NOW","SIP") else (80 if timing in ("STAGGER","BUY ON DIP","APPLY DURING ISSUE WINDOW") else 55)
        datafit=100 if _txt(r.get("DataStatus"),"FRESH").upper()=="FRESH" else 65; current_exposure=float(exposure.get(cls,0)) if include_existing else 0; concentration_penalty=max(0,current_exposure-25)*.6
        final=.42*_num(r.get("Score"),50)+.22*hfit+.18*rfit+.10*timing_fit+.08*datafit-concentration_penalty
        d=r.to_dict();d["DurationFit"]=round(hfit,1);d["RiskFit"]=round(rfit,1);d["OptimizerScore"]=round(max(0,min(100,final)),1);d["ExistingExposurePct"]=current_exposure
        if reasons:d["RejectReason"]=" • ".join(reasons);rejected.append(d)
        else:d["RejectReason"]="";eligible.append(d)
    e=pd.DataFrame(eligible);rj=pd.DataFrame(rejected)
    if not e.empty:e=e.sort_values("OptimizerScore",ascending=False).reset_index(drop=True)
    if not rj.empty:rj=rj.sort_values("OptimizerScore",ascending=False).reset_index(drop=True)
    return e,rj


def build_plan(candidates: pd.DataFrame, amount: float, horizon_days: int, risk_profile: str, min_reserve_pct=None, essential_money=False, monthly=False):
    amount=float(amount)
    if candidates is None or candidates.empty or amount<=0:return {"allocations":pd.DataFrame(),"summary":{},"why":[],"warnings":["No eligible investment has enough validated data for this request."]}
    caps=_asset_caps(risk_profile,horizon_days); reserve=35 if essential_money and horizon_days<=365 else (25 if horizon_days<=30 else (18 if horizon_days<=180 else (10 if risk_profile!="HIGH" else 5)))
    if min_reserve_pct is not None:reserve=max(reserve,float(min_reserve_pct));reserve=min(max(reserve,0),80)
    investable=amount*(1-reserve/100); selected=[];used=set()
    for _,r in candidates.iterrows():
        cls=_txt(r.AssetClass)
        if cls in used or caps.get(cls,30)<=0:continue
        selected.append(r);used.add(cls)
        if len(selected)>=4:break
    scores=np.array([max(_num(r.get("OptimizerScore"),50)-45,5) for r in selected],dtype=float); weights=scores/scores.sum() if len(scores) else np.array([])
    rows=[];remaining=investable
    for i,r in enumerate(selected):
        cls=_txt(r.AssetClass);cap_amt=amount*caps.get(cls,30)/100;alloc=min(investable*weights[i],cap_amt,remaining);mininv=_num(r.get("MinInvestmentRs"),1000)
        if alloc<mininv and remaining>=mininv:alloc=min(mininv,cap_amt,remaining)
        alloc=math.floor(max(0,alloc)/500)*500
        if alloc<=0:continue
        remaining-=alloc;row=r.to_dict();row["AllocationRs"]=round(alloc,2);row["AllocationPct"]=round(alloc/amount*100,1);row.update(_scenario_values(alloc,row.get("DownsidePct",np.nan),row.get("BasePct",np.nan),row.get("UpsidePct",np.nan)));rows.append(row)
    reserve_amt=amount-sum(x["AllocationRs"] for x in rows);plan=pd.DataFrame(rows)
    if reserve_amt>0:
        rr=_candidate(AssetClass="Reserve",Category="LIQUID",Instrument="Cash / Liquid Reserve",Decision="KEEP RESERVE",Score=100,Risk="LOW",Confidence="HIGH",Timing="HOLD RESERVE",DownsidePct=0,BasePct=0,UpsidePct=0,Reason="Reserve is deliberately kept available for liquidity, emergency need or a better qualified entry.",WhatChanges="Deploy only when a product enters a valid qualified zone and the plan still fits your required date.")
        rr["OptimizerScore"]=100;rr["AllocationRs"]=round(reserve_amt,2);rr["AllocationPct"]=round(reserve_amt/amount*100,1);rr.update(_scenario_values(reserve_amt,0,0,0));plan=pd.concat([plan,pd.DataFrame([rr])],ignore_index=True)
    down=base=up=0.0;vd=vb=vu=False
    for _,r in plan.iterrows():
        a=_num(r.get("AllocationRs"),0)
        for key,which in [("DownsidePct","d"),("BasePct","b"),("UpsidePct","u")]:
            p=_num(r.get(key),np.nan)
            if pd.notna(p):
                if which=="d":down+=a*p/100;vd=True
                elif which=="b":base+=a*p/100;vb=True
                else:up+=a*p/100;vu=True
    wait_share=float(plan.loc[plan.Timing.astype(str).isin(["WAIT","BUY ON DIP","HOLD RESERVE","APPLY DURING ISSUE WINDOW"]),"AllocationRs"].sum()/amount*100) if not plan.empty else 100
    action="STAGGER INVESTMENT" if wait_share>=25 else ("INVEST / SIP AS PLANNED" if monthly else "INVEST NOW WITH PLAN")
    why=[]
    if horizon_days<=90:why.append("Short duration gives priority to liquidity, capital preservation and duration-matched products.")
    elif horizon_days>=1095:why.append("Longer duration allows more growth assets because short-term volatility has more time to recover.")
    if reserve_amt>0:why.append(f"₹{reserve_amt:,.0f} is intentionally kept as reserve instead of forcing a weak or badly timed investment.")
    top=plan[plan.AssetClass.ne("Reserve")].head(1)
    if not top.empty:why.append(f"{top.iloc[0].Instrument} receives the strongest fit after score, risk, duration, timing and data-quality checks.")
    summary={"AmountRs":round(amount,2),"HorizonDays":int(horizon_days),"Horizon":human_horizon(horizon_days),"Risk":risk_profile,"PlanAction":action,"ReserveRs":round(reserve_amt,2),"DownsideValueRs":round(amount+down,2) if vd else np.nan,"BaseValueRs":round(amount+base,2) if vb else np.nan,"UpsideValueRs":round(amount+up,2) if vu else np.nan,"BaseGainRs":round(base,2) if vb else np.nan,"ReviewDate":str(date.today()+timedelta(days=max(14,min(90,horizon_days//4 or 14))))}
    return {"allocations":plan,"summary":summary,"why":why,"warnings":[]}


def build_why_not(rejected: pd.DataFrame, eligible: pd.DataFrame, selected: pd.DataFrame, max_rows=8):
    rows=[];selected_keys=set(selected.ProductKey.astype(str)) if selected is not None and not selected.empty and "ProductKey" in selected else set()
    if rejected is not None and not rejected.empty:
        for _,r in rejected.head(max_rows).iterrows():rows.append({"Option":r.get("Instrument",""),"AssetClass":r.get("AssetClass",""),"WhyNot":r.get("RejectReason","")})
    if eligible is not None and not eligible.empty and len(rows)<max_rows:
        for _,r in eligible.iterrows():
            if str(r.get("ProductKey","")) in selected_keys:continue
            why="Good alternative, but it ranked lower on duration/risk/timing fit." if str(r.get("Timing","")) not in ("WAIT","BUY ON DIP") else "Good product/setup, but current timing is not ideal for immediate deployment."
            rows.append({"Option":r.get("Instrument",""),"AssetClass":r.get("AssetClass",""),"WhyNot":why})
            if len(rows)>=max_rows:break
    return pd.DataFrame(rows)


def universal_explanation(row, allocation_amount, horizon_days, risk_profile, alternative_note=""):
    r=row if isinstance(row,dict) else row.to_dict();d=_num(r.get("DownsidePct"),np.nan);b=_num(r.get("BasePct"),np.nan);u=_num(r.get("UpsidePct"),np.nan);vals=_scenario_values(allocation_amount,d,b,u)
    return {
        "1. What should I do?": f"{_txt(r.get('Decision'))} — timing: {_txt(r.get('Timing'))}",
        "2. How much should I invest?": f"₹{float(allocation_amount):,.0f}",
        "3. For how long?": human_horizon(horizon_days),
        "4. When should I invest?": _txt(r.get("Timing"),"WAIT"),
        "5. What return range is reasonable?": f"Downside {d:+.1f}% / Base {b:+.1f}% / Upside {u:+.1f}%" if pd.notna(d) and pd.notna(b) and pd.notna(u) else "Not enough validated evidence for a numerical range.",
        "6. What is the downside?": f"About {d:+.1f}% scenario / ₹{vals['DownsideValueRs']:,.0f} value" if pd.notna(d) else "Product-specific downside is not reliably quantifiable from current data.",
        "7. What is the risk?": _txt(r.get("Risk"),risk_profile),
        "8. How confident is the system?": _txt(r.get("Confidence"),"LOW")+f" • Data: {_txt(r.get('DataStatus'),'PARTIAL')}",
        "9. Why is this recommended?": _txt(r.get("Reason"),"It scored best on suitability, timing and current evidence."),
        "10. Why not the other options?": alternative_note or "Other options ranked lower on duration fit, risk fit, timing, data quality or expected risk-adjusted outcome.",
        "11. What would change the recommendation?": _txt(r.get("WhatChanges"),"A material change in price/yield, trend, risk, data quality or required duration."),
        "12. When should I review it?": str(date.today()+timedelta(days=max(14,min(90,horizon_days//4 or 14)))),
        "13. What should I do next?": "Track the plan; execute only when the stated timing/entry condition is valid, then record the actual purchase lot in My Portfolio."
    }


def save_plan(summary: dict, allocations: pd.DataFrame, mode="ONE-TIME", note=""):
    PLANS.parent.mkdir(parents=True,exist_ok=True);pid=f"PLAN-{pd.Timestamp.now().strftime('%Y%m%d%H%M%S')}"
    row={"PlanID":pid,"CreatedAt":pd.Timestamp.now().isoformat(timespec="seconds"),"Mode":mode,"AmountRs":summary.get("AmountRs"),"HorizonDays":summary.get("HorizonDays"),"Horizon":summary.get("Horizon"),"Risk":summary.get("Risk"),"PlanAction":summary.get("PlanAction"),"ReserveRs":summary.get("ReserveRs"),"DownsideValueRs":summary.get("DownsideValueRs"),"BaseValueRs":summary.get("BaseValueRs"),"UpsideValueRs":summary.get("UpsideValueRs"),"ReviewDate":summary.get("ReviewDate"),"Status":"ACTIVE","Note":note,"LegsJSON":allocations.to_json(orient="records") if allocations is not None else "[]"}
    old=pd.read_csv(PLANS) if PLANS.exists() else pd.DataFrame();pd.concat([old,pd.DataFrame([row])],ignore_index=True).to_csv(PLANS,index=False);return pid


def load_plans():
    if not PLANS.exists():return pd.DataFrame()
    try:return pd.read_csv(PLANS)
    except Exception:return pd.DataFrame()


def segment_candidates(segment: str, amount: float, horizon_days: int, risk_profile: str, radar=None,mf=None,bonds=None,ipos=None,opts=None,history=None,cfg=None,metal_state=None,crypto_loader=None,seed=None,monthly=False):
    allc=collect_candidates(radar,mf,bonds,ipos,opts,history,cfg,metal_state,crypto_loader,horizon_days,monthly)
    if allc.empty:return pd.DataFrame(),pd.DataFrame()
    mapping={"Gold":["Physical Gold"],"Silver":["Physical Silver"],"Stocks":["Stocks"],"Mutual Funds":["Mutual Funds"],"Fixed Income / Bonds":["Fixed Income"],"IPO":["IPO"],"Crypto":["Crypto"],"Other Investments":["Other Investments"]}
    x=allc[allc.AssetClass.isin(mapping.get(str(segment),[]))].copy()
    if segment in ("Gold","Silver"):
        key=str(segment).upper();extra=[]
        if radar is not None and not radar.empty:
            syms=(cfg or {}).get("precious_assets",{}).get(key,{}).get("symbols",[]);rr=radar[radar.Symbol.astype(str).isin(syms)].copy()
            for _,r in rr.sort_values("Overall",ascending=False).drop_duplicates("Symbol").head(5).iterrows():
                extra.append(_candidate(AssetClass=f"{segment} Product",Category="ETF",Instrument=_txt(r.Symbol),Decision=_txt(r.Signal),Score=_num(r.Overall,50),Risk=_txt(r.get("RiskLevel"),"MODERATE"),Confidence=_txt(r.Confidence,"LOW"),Timing="INVEST NOW" if _txt(r.EntryStatus)=="ENTRY VALID" else "BUY ON DIP",MinHorizonDays=30,DownsidePct=-abs(_num(r.get("Risk%"),8)),BasePct=_num(r.get("Potential1%"),6),UpsidePct=_num(r.get("Potential2%"),12),Reason=f"Listed {segment} ETF; {_txt(r.get('Reason'))}",WhatChanges=_txt(r.get("WhatChanges")),Source="NSE ETF",ProductKey=f"ETF:{_txt(r.Symbol)}"))
        if mf is not None and not mf.empty:
            mm=mf[mf.Scheme.astype(str).str.upper().str.contains(key,na=False)]
            for _,r in mm.sort_values("Overall",ascending=False).head(5).iterrows():
                extra.append(_candidate(AssetClass=f"{segment} Product",Category="MUTUAL FUND",Instrument=_txt(r.Scheme),Decision=_txt(r.Action),Score=_num(r.Overall,50),Risk=_txt(r.Risk,"MODERATE"),Confidence=_txt(r.Confidence,"LOW"),Timing="SIP" if monthly else "STAGGER",MinHorizonDays=365,BasePct=_compound_pct(_num(r.get("3Y_CAGR%"),_num(r.get("1Y%"),np.nan)),horizon_days),Reason=_txt(r.Reason),WhatChanges=_txt(r.WhatChanges),Source="MF NAV",ProductKey=f"MF:{_txt(r.get('Code')) or _txt(r.Scheme)}"))
        if opts is not None and not opts.empty and segment=="Gold":
            oo=opts[opts.Option.astype(str).str.upper().str.contains("GOLD",na=False)];gg=_other_candidates(oo,horizon_days)
            for e in gg:e["AssetClass"]="Gold Product"
            extra+=gg
        if extra:x=pd.concat([x,pd.DataFrame(extra)],ignore_index=True)
    if segment=="Stocks" and not x.empty and seed is not None and not seed.empty and "symbol" in seed.columns:
        mp={str(r.symbol).upper():_txt(r.get("sector"),"Unknown") for _,r in seed.drop_duplicates("symbol").iterrows()};x["Category"]=x.Instrument.astype(str).str.upper().map(mp).fillna(x.Category)
    # Product-class aliases for gold/silver need to pass through scoring.
    if segment in ("Gold","Silver") and not x.empty:x["AssetClass"]=x.AssetClass.replace({f"{segment} Product":f"Physical {segment}"})
    return score_candidates(x,amount,horizon_days,risk_profile,{},False,[])


def optimize_money(amount: float, horizon_days: int, risk_profile: str, radar=None, mf=None, bonds=None, ipos=None, opts=None, history=None, cfg=None, metal_state=None, crypto_loader=None, existing_exposure=None, include_existing=True, exclusions=None, min_reserve_pct=None, essential_money=False, monthly=False):
    """Compatibility wrapper for the money optimizer pipeline.
    Returns a dict with candidates, rejected, allocations, summary, why, warnings, and why_not.
    """
    candidates = collect_candidates(
        radar=radar, mf=mf, bonds=bonds, ipos=ipos, opts=opts, history=history,
        cfg=cfg, metal_state=metal_state, crypto_loader=crypto_loader,
        horizon_days=horizon_days, monthly=monthly,
    )
    eligible, rejected = score_candidates(
        candidates=candidates, amount=amount, horizon_days=horizon_days,
        risk_profile=risk_profile, existing_exposure=existing_exposure,
        include_existing=include_existing, exclusions=exclusions,
    )
    plan = build_plan(
        candidates=eligible, amount=amount, horizon_days=horizon_days,
        risk_profile=risk_profile, min_reserve_pct=min_reserve_pct,
        essential_money=essential_money, monthly=monthly,
    )
    selected = plan.get('allocations')
    why_not = build_why_not(rejected, eligible, selected if selected is not None else pd.DataFrame())
    plan['candidates'] = eligible
    plan['rejected'] = rejected
    plan['why_not'] = why_not
    return plan
