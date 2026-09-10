from __future__ import annotations
import pandas as pd


def allocation(amount,risk,horizon_years,base_allocs):
    risk=risk.upper(); a=dict(base_allocs[risk])
    if horizon_years<1:
        moved=max(0,a['Stocks']-5)+max(0,a['Equity Mutual Funds']-10)
        a['Stocks']=min(a['Stocks'],5); a['Equity Mutual Funds']=min(a['Equity Mutual Funds'],10)
        a['Fixed Income']+=moved*.8; a['Cash']+=moved*.2
    elif horizon_years<3:
        moved=max(0,a['Stocks']-15); a['Stocks']=min(a['Stocks'],15); a['Fixed Income']+=moved
    return pd.DataFrame([{'Asset Class':k,'Allocation%':round(v,1),'Amount₹':round(amount*v/100,2)} for k,v in a.items()])


def scenario_value(amount, annual_return, years):
    return amount*((1+annual_return/100)**years)


def future_value(lump_sum=0, monthly=0, annual_return=10, years=5):
    years=float(years); r=float(annual_return)/100/12; n=max(0,int(round(years*12)))
    lump=float(lump_sum)*(1+r)**n
    if r==0: sip=float(monthly)*n
    else: sip=float(monthly)*(((1+r)**n-1)/r)*(1+r)
    return lump+sip


def required_monthly_sip(target,current,annual_return,years):
    years=float(years); r=float(annual_return)/100/12; n=max(1,int(round(years*12)))
    current_fv=float(current)*(1+r)**n
    gap=max(0,float(target)-current_fv)
    if r==0:return gap/n
    factor=(((1+r)**n-1)/r)*(1+r)
    return gap/factor if factor else gap/n


def goal_scenarios(target,current,monthly,years,risk='MODERATE'):
    rates={'LOW':(5,7,9),'MODERATE':(6,10,13),'HIGH':(4,12,17)}.get(str(risk).upper(),(6,10,13))
    rows=[]
    for label,rate in zip(['Conservative','Base','Optimistic'],rates):
        fv=future_value(current,monthly,rate,years)
        rows.append({'Scenario':label,'AnnualReturnAssumption%':rate,'ProjectedValue₹':round(fv,2),'GoalGap₹':round(fv-float(target),2),'GoalStatus':'ON TRACK' if fv>=target else 'SHORTFALL'})
    return pd.DataFrame(rows)
