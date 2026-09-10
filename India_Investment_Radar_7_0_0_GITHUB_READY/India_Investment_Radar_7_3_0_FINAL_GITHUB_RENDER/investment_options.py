from __future__ import annotations
from pathlib import Path
import numpy as np
import pandas as pd
from small_savings import apply_to_options as apply_small_savings
from deposit_rates import as_investment_options as fd_investment_options

BASE=Path(__file__).resolve().parent
FILE=BASE/'data'/'investment_options.csv'

COLUMNS=['Option','Category','Provider/Instrument','RateOrExpectedReturn%','TenureYears','LockInYears','Risk','Liquidity','TaxEfficiency','MinInvestment₹','Eligibility/Notes','Source/Updated','ActiveStatus','RateDate','DataConfidence','ProductNotes']


def _r(option,category,provider,tenure,lock,risk,liq,tax,mininv,notes,source='Official/public source or manual verified input',active='ACTIVE',confidence='PARTIAL',product_notes=''):
    return {'Option':option,'Category':category,'Provider/Instrument':provider,'RateOrExpectedReturn%':np.nan,'TenureYears':tenure,'LockInYears':lock,'Risk':risk,'Liquidity':liq,'TaxEfficiency':tax,'MinInvestment₹':mininv,'Eligibility/Notes':notes,'Source/Updated':source,'ActiveStatus':active,'RateDate':'','DataConfidence':confidence,'ProductNotes':product_notes}

DEFAULT=[
 # Cash / deposits
 _r('Savings Account / Cash','CASH & PARKING','Bank savings account',0.01,0,'LOW','HIGH','LOW',0,'Emergency liquidity / immediate access.','Bank official rate / user verified','ACTIVE','PARTIAL'),
 _r('Sweep FD','FIXED RETURN','Bank sweep / auto-sweep deposit',0.5,0,'LOW','HIGH','LOW/MEDIUM',1000,'Useful for cash parking if your bank offers sweep-in/out.','Bank official rate / user verified'),
 _r('Bank FD — General','FIXED RETURN','Scheduled commercial bank FD',1,0.5,'LOW','MEDIUM','LOW/MEDIUM',1000,'Compare exact bank, tenure, premature withdrawal and deposit-insurance exposure.','Bank official rate / user verified'),
 _r('Bank FD — Senior Citizen','FIXED RETURN','Scheduled commercial bank senior-citizen FD',1,0.5,'LOW','MEDIUM','LOW/MEDIUM',1000,'Eligibility required; compare extra senior rate and premature withdrawal terms.','Bank official rate / user verified'),
 _r('Small Finance Bank FD','FIXED RETURN','Eligible SFB fixed deposit',1,0.5,'LOW/MEDIUM','MEDIUM','LOW/MEDIUM',1000,'Higher rates may carry higher institution concentration risk; verify deposit-insurance coverage and limits.','SFB official rate / user verified'),
 _r('NBFC / Corporate FD','FIXED RETURN','Rated NBFC/company deposit',1,1,'MEDIUM','LOW/MEDIUM','LOW',1000,'Verify issuer rating, liquidity, premature withdrawal and concentration risk.','Issuer official rate / verified document'),
 _r('Tax-Saving Bank FD','FIXED RETURN','5-year tax-saving bank FD',5,5,'LOW','LOW','MEDIUM',1000,'Lock-in applies; tax treatment depends on current law.','Bank official rate / user verified'),
 _r('Recurring Deposit — Bank','FIXED RETURN','Bank recurring deposit',2,1,'LOW','MEDIUM','LOW/MEDIUM',100,'For disciplined monthly saving; use exact institution rate and tenure.','Bank official rate / user verified'),
 _r('Recurring Deposit — Post Office','GOVT SAVINGS','Post Office RD',5,5,'LOW','LOW/MEDIUM','MEDIUM',100,'Use current official Post Office rate/rules.','Government / India Post official update'),
 # Post office / small savings
 _r('Post Office Savings Account','GOVT SAVINGS','Post Office Savings Account',0.01,0,'LOW','HIGH','MEDIUM',500,'Liquidity product, not a high-return investment.','Government / India Post official update'),
 _r('Post Office Time Deposit — 1Y','GOVT SAVINGS','Post Office TD 1 Year',1,1,'LOW','LOW/MEDIUM','MEDIUM',1000,'Use current official tenure-specific rate.','Government / India Post official update'),
 _r('Post Office Time Deposit — 2Y','GOVT SAVINGS','Post Office TD 2 Years',2,2,'LOW','LOW/MEDIUM','MEDIUM',1000,'Use current official tenure-specific rate.','Government / India Post official update'),
 _r('Post Office Time Deposit — 3Y','GOVT SAVINGS','Post Office TD 3 Years',3,3,'LOW','LOW/MEDIUM','MEDIUM',1000,'Use current official tenure-specific rate.','Government / India Post official update'),
 _r('Post Office Time Deposit — 5Y','GOVT SAVINGS','Post Office TD 5 Years',5,5,'LOW','LOW/MEDIUM','MEDIUM/HIGH',1000,'Use current official tenure-specific rate and current tax rules.','Government / India Post official update'),
 _r('Post Office MIS','GOVT SAVINGS','Monthly Income Scheme',5,5,'LOW','LOW/MEDIUM','MEDIUM',1000,'Eligibility/deposit limits and premature closure rules apply.','Government / India Post official update'),
 _r('PPF','GOVT SAVINGS','Public Provident Fund',15,15,'LOW','LOW','HIGH',500,'Long-term government savings; contribution/withdrawal/tax rules apply.','Government official-rate update'),
 _r('NSC','GOVT SAVINGS','National Savings Certificate',5,5,'LOW','LOW','MEDIUM/HIGH',1000,'Use current official rate and tax rules.','Government / India Post official update'),
 _r('KVP','GOVT SAVINGS','Kisan Vikas Patra',10,2.5,'LOW','LOW/MEDIUM','MEDIUM',1000,'Maturity period/rate can change; use current official terms.','Government / India Post official update'),
 _r('SCSS','GOVT SAVINGS','Senior Citizens Savings Scheme',5,5,'LOW','LOW/MEDIUM','MEDIUM',1000,'Eligibility and maximum deposit limits apply.','Government / India Post official update'),
 _r('Sukanya Samriddhi','GOVT SAVINGS','Sukanya Samriddhi Account',21,21,'LOW','LOW','HIGH',250,'Eligibility and contribution/withdrawal rules apply.','Government / India Post official update'),
 # Sovereign / debt
 _r('91-Day T-Bill','SOVEREIGN DEBT','Government Treasury Bill',0.25,0,'LOW','HIGH','MEDIUM',1000,'Use current auction/market yield; detailed analysis in Fixed Income.','RBI/NSE official current yield'),
 _r('182-Day T-Bill','SOVEREIGN DEBT','Government Treasury Bill',0.5,0,'LOW','HIGH','MEDIUM',1000,'Use current auction/market yield; detailed analysis in Fixed Income.','RBI/NSE official current yield'),
 _r('364-Day T-Bill','SOVEREIGN DEBT','Government Treasury Bill',1,0,'LOW','HIGH','MEDIUM',1000,'Use current auction/market yield; detailed analysis in Fixed Income.','RBI/NSE official current yield'),
 _r('Dated G-Sec','SOVEREIGN DEBT','Government of India dated security',5,0,'LOW','MEDIUM/HIGH','MEDIUM',1000,'Use exact security, current YTM, maturity and duration risk.','RBI/NSE official market data'),
 _r('SDL','SOVEREIGN DEBT','State Development Loan',5,0,'LOW','MEDIUM','MEDIUM',1000,'Use exact state security, current YTM and maturity.','RBI/NSE official market data'),
 _r('RBI Floating Rate Savings Bond','GOVT SAVINGS','RBI Floating Rate Savings Bond / current equivalent',7,7,'LOW','LOW','MEDIUM',1000,'Availability/rate reset/lock-in/eligibility must be verified from current official terms.','RBI/Government official terms'),
 _r('AAA / High-Grade Corporate Bond','CORPORATE DEBT','Exact listed corporate bond/NCD',3,0,'LOW/MEDIUM','MEDIUM','MEDIUM',1000,'Verify issuer, rating, security, YTM, call/put terms and liquidity.','Exchange/issuer official data'),
 _r('Corporate NCD','CORPORATE DEBT','Exact listed NCD',3,0,'MEDIUM','MEDIUM','MEDIUM',1000,'Credit and liquidity risk vary materially; verify exact issue/security.','Exchange/issuer official data'),
 _r('Target Maturity Debt Fund / ETF','DEBT FUND','Exact target-maturity fund/ETF',5,0,'LOW/MEDIUM','HIGH','MEDIUM',500,'Use exact scheme portfolio, maturity, YTM, expense ratio and tracking error.','AMFI/NSE verified data'),
 # Retirement / pension
 _r('NPS Tier I','RETIREMENT','National Pension System Tier I',15,15,'MEDIUM','LOW','HIGH',500,'Market-linked; allocation, withdrawal, annuity and tax rules apply.','NPS Trust official data'),
 _r('NPS Tier II','RETIREMENT','National Pension System Tier II',5,0,'MEDIUM','MEDIUM/HIGH','VARIES',250,'Market-linked; availability/tax rules depend on subscriber situation.','NPS Trust official data'),
 _r('EPF / VPF','RETIREMENT','Employee Provident Fund / Voluntary PF',10,0,'LOW','LOW/MEDIUM','HIGH',0,'Only where eligible through employment; contribution/withdrawal rules apply.','EPFO/Government official terms'),
 _r('Immediate / Deferred Annuity','RETIREMENT INCOME','Insurer annuity product',10,5,'LOW/MEDIUM','LOW','VARIES',10000,'Compare guaranteed payout, return of purchase price, inflation risk and insurer terms.','Insurer official illustration/terms'),
 # Listed income / alternatives
 _r('REIT','LISTED INCOME','Select listed REIT',5,0,'MEDIUM','HIGH','MEDIUM',1000,'Analyze market price, NAV/valuation, distributions, leverage and occupancy.','NSE/BSE + issuer filings'),
 _r('InvIT','LISTED INCOME','Select listed InvIT',5,0,'MEDIUM','HIGH','MEDIUM',1000,'Analyze distribution yield, leverage, asset quality and project risks.','NSE/BSE + issuer filings'),
 _r('International ETF / Fund','INTERNATIONAL','Exact international ETF/FoF/fund available to investor',5,0,'MEDIUM/HIGH','MEDIUM/HIGH','MEDIUM',1000,'Currency, overseas-market, tax and availability risks apply.','NSE/AMFI first; public reference fallback'),
 _r('Secondary-Market Sovereign Gold Bond','GOLD INCOME','Exact listed sovereign-gold instrument if available',5,0,'LOW/MEDIUM','LOW/MEDIUM','MEDIUM/HIGH',1000,'Secondary-market price/liquidity and exact security terms must be verified.','Exchange/RBI historical security data'),
 _r('Physical Gold','REAL ASSET','Physical gold / coin / bar',3,0,'MEDIUM','MEDIUM','MEDIUM',1000,'Use Gold/Silver specialist page for quote, buy zones, GST/premium/making-cost logic.','Dealer quote + market benchmark/proxy'),
 _r('Physical Silver','REAL ASSET','Physical silver / bar',3,0,'MEDIUM/HIGH','MEDIUM','MEDIUM',1000,'Use Gold/Silver specialist page for quote, buy zones and market proxy.','Dealer quote + market benchmark/proxy'),
 _r('Real Estate','REAL ASSET','Direct property',7,5,'MEDIUM','LOW','MEDIUM',100000,'Manual valuation, rent, vacancy, transaction costs, taxes and legal due diligence required.','Manual verified property inputs'),
 _r('PMS','ALTERNATIVE','Portfolio Management Service',5,3,'HIGH','LOW/MEDIUM','VARIES',0,'Eligibility/minimum ticket, fees, drawdown and strategy history must be verified.','Provider/SEBI official documents'),
 _r('AIF','ALTERNATIVE','Alternative Investment Fund',5,3,'HIGH','LOW','VARIES',0,'Eligibility/minimum ticket, fees, liquidity and strategy risks vary.','Fund/SEBI official documents'),
 _r('SIF / Specialized Fund','ALTERNATIVE','Eligible specialized regulated fund',5,0,'HIGH','MEDIUM','VARIES',0,'Only where legally/operationally available; verify product rules and minimums.','Official scheme documents'),
 _r('Unlisted / Pre-IPO Equity','MANUAL REVIEW','Exact unlisted company/security',5,3,'VERY HIGH','LOW','VARIES',0,'No automatic actionable call unless reliable valuation, financials and transaction terms are verified.','Manual official/company documents','ACTIVE','LOW'),
 _r('P2P / Private Credit','MANUAL REVIEW','Regulated platform / exact private credit product',3,1,'HIGH','LOW','LOW/MEDIUM',0,'Credit/default/platform/liquidity risk; manual/reduced-confidence analysis only.','Provider/regulatory documents','ACTIVE','LOW'),
 _r('Insurance-Linked Investment','MANUAL REVIEW','ULIP/endowment/money-back exact product',10,5,'MEDIUM','LOW','VARIES',0,'Evaluate actual IRR, charges, surrender value and insurance need; do not treat illustrations as guaranteed investment returns.','Insurer official benefit illustration','ACTIVE','LOW'),
 _r('Collectibles / Other Alternative','MANUAL REVIEW','Exact asset',7,5,'VERY HIGH','LOW','VARIES',0,'Track only with independent valuation and liquidity evidence.','Manual verified valuation','ACTIVE','LOW'),
]


def _normalize(df):
    x=df.copy()
    for c in COLUMNS:
        if c not in x.columns:x[c]=''
    return x[COLUMNS]


def ensure():
    FILE.parent.mkdir(parents=True,exist_ok=True)
    defaults=pd.DataFrame(DEFAULT,columns=COLUMNS)
    if not FILE.exists():
        defaults.to_csv(FILE,index=False);return
    try:old=_normalize(pd.read_csv(FILE))
    except Exception:
        defaults.to_csv(FILE,index=False);return
    # Preserve user edits and add newly introduced master-universe rows without deleting anything.
    key=lambda d:(d['Option'].astype(str).str.strip().str.upper()+'|'+d['Provider/Instrument'].astype(str).str.strip().str.upper())
    existing=set(key(old).tolist())
    add=defaults[~key(defaults).isin(existing)]
    if not add.empty:pd.concat([old,add],ignore_index=True).to_csv(FILE,index=False)


def load():
    ensure()
    try:base=_normalize(pd.read_csv(FILE))
    except Exception:base=pd.DataFrame(DEFAULT,columns=COLUMNS)
    # Apply the latest government small-savings rates to the permanent master rows.
    base=apply_small_savings(base)
    # Append the complete bank-FD directory (all RBI-listed PSB/private/SFB providers,
    # with current public-comparison rates where available). Missing rates stay visible
    # as REVIEW rather than making the bank disappear from the universe.
    try:fd=fd_investment_options(COLUMNS)
    except Exception:fd=pd.DataFrame(columns=COLUMNS)
    if not fd.empty:
        out=pd.concat([base,fd],ignore_index=True)
        out=out.drop_duplicates(['Option','Provider/Instrument'],keep='last')
        return _normalize(out)
    return _normalize(base)


def save(df):
    x=_normalize(df)
    # Dynamic FD-directory rows live in data/fd_rates.csv and are rebuilt/refreshed
    # automatically. Do not duplicate them into the user's editable master file.
    auto= x['ProductNotes'].astype(str).str.contains('AUTO_FD_DIRECTORY',case=False,na=False)
    x.loc[~auto].to_csv(FILE,index=False)


def _risk_num(s):
    s=str(s).upper()
    if s.startswith('VERY HIGH'):return 4
    return 1 if s.startswith('LOW') else (2 if s.startswith('MEDIUM') else 3)

def _liq_num(s):
    s=str(s).upper()
    return 3 if 'HIGH' in s else (2 if 'MEDIUM' in s else 1)

def _tax_num(s):
    s=str(s).upper()
    return 3 if 'HIGH' in s else (2 if 'MEDIUM' in s else 1)


def rank(df,amount=100000,horizon_years=5,risk_profile='MODERATE'):
    x=_normalize(df)
    # Do not recommend closed/discontinued products to new money; keep visible for portfolio/history.
    if 'ActiveStatus' in x.columns:
        active=x.ActiveStatus.astype(str).str.upper().isin(['ACTIVE','NEW INVESTMENT ALLOWED',''])
        x=x[active].copy()
    for c in ['RateOrExpectedReturn%','TenureYears','LockInYears','MinInvestment₹']:
        x[c]=pd.to_numeric(x[c],errors='coerce')
    target={'LOW':1,'MODERATE':2,'HIGH':3}.get(str(risk_profile).upper(),2)
    rows=[]
    for _,r in x.iterrows():
        risk=_risk_num(r.Risk);liq=_liq_num(r.Liquidity);tax=_tax_num(r.TaxEfficiency)
        riskfit=max(0,100-30*abs(risk-target))
        lock=float(r.LockInYears) if pd.notna(r.LockInYears) else 0
        horizonfit=100 if lock<=horizon_years else max(0,100-(lock-horizon_years)*20)
        mininv=float(r['MinInvestment₹']) if pd.notna(r['MinInvestment₹']) else 0
        budgetfit=100 if mininv<=amount else max(0,100-(mininv-amount)/max(amount,1)*100)
        returnscore=50
        if pd.notna(r['RateOrExpectedReturn%']):returnscore=float(np.clip(30+float(r['RateOrExpectedReturn%'])*5,0,100))
        confidence=str(r.get('DataConfidence','PARTIAL')).upper();confscore={'HIGH':100,'MEDIUM':80,'PARTIAL':55,'LOW':35}.get(confidence,55)
        fit=0.25*riskfit+0.22*horizonfit+0.13*budgetfit+0.11*(liq/3*100)+0.10*(tax/3*100)+0.09*returnscore+0.10*confscore
        d=r.to_dict();d['FitScore']=round(fit,1)
        d['Fit']='STRONG FIT' if fit>=80 else ('GOOD FIT' if fit>=68 else ('POSSIBLE' if fit>=55 else 'LOW FIT'))
        reasons=[]
        reasons.append('Risk profile fits' if riskfit>=80 else 'Risk level is not an ideal match')
        reasons.append('Lock-in fits selected horizon' if horizonfit>=80 else 'Lock-in exceeds selected horizon')
        if mininv>amount:reasons.append('Minimum investment exceeds entered budget')
        if pd.isna(r['RateOrExpectedReturn%']):reasons.append('Current verified rate/return input is required before return comparison')
        if confidence in ('LOW','PARTIAL'):reasons.append('Data confidence is reduced until current product/rate data is verified')
        d['Reason']=' • '.join(reasons)
        rows.append(d)
    return pd.DataFrame(rows).sort_values('FitScore',ascending=False) if rows else pd.DataFrame(columns=COLUMNS+['FitScore','Fit','Reason'])
