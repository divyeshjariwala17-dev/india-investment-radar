from __future__ import annotations
from pathlib import Path
import ast, json, py_compile, sys, symtable, builtins
import pandas as pd, numpy as np
BASE=Path(__file__).resolve().parent

def top_names(path):
    t=ast.parse(path.read_text(encoding='utf-8'),filename=str(path));names=set();funcs={}
    for n in t.body:
        if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)):
            names.add(n.name);pos=list(n.args.posonlyargs)+list(n.args.args);req=len(pos)-len(n.args.defaults);funcs[n.name]=(req,[a.arg for a in pos])
        elif isinstance(n,ast.ClassDef):names.add(n.name)
        elif isinstance(n,ast.Assign):
            for x in n.targets:
                if isinstance(x,ast.Name):names.add(x.id)
        elif isinstance(n,ast.AnnAssign) and isinstance(n.target,ast.Name):names.add(n.target.id)
        elif isinstance(n,ast.Import):
            for a in n.names:names.add(a.asname or a.name.split('.')[0])
        elif isinstance(n,ast.ImportFrom):
            for a in n.names:names.add(a.asname or a.name)
    return names,funcs

def undefined_globals(path):
    ss=path.read_text(encoding='utf-8');st=symtable.symtable(ss,str(path),'exec')
    defs={n for n in st.get_identifiers() if st.lookup(n).is_assigned() or st.lookup(n).is_imported() or st.lookup(n).is_namespace()};bad=set()
    def walk(tab):
        for n in tab.get_identifiers():
            sy=tab.lookup(n)
            if tab.get_type()!='module' and sy.is_global() and sy.is_referenced() and n not in defs and not hasattr(builtins,n) and n!='__file__':bad.add(n)
        for c in tab.get_children():walk(c)
    walk(st)
    for n in st.get_identifiers():
        sy=st.lookup(n)
        if sy.is_referenced() and n not in defs and not hasattr(builtins,n) and n!='__file__':bad.add(n)
    return bad

def main():
    problems=[];files=list(BASE.glob('*.py'));mods={p.stem:p for p in files};cache={}
    for p in files:
        try:py_compile.compile(str(p),doraise=True)
        except Exception as e:problems.append(f'{p.name}: compile {e}')
        try:
            bad=undefined_globals(p)
            if bad:problems.append(f'{p.name}: undefined globals {sorted(bad)}')
        except Exception as e:problems.append(f'{p.name}: name audit {e}')
    for p in files:
        try:
            t=ast.parse(p.read_text(encoding='utf-8'),filename=str(p));imports={}
            for n in t.body:
                if isinstance(n,ast.ImportFrom) and n.level==0 and n.module in mods:
                    names,funcs=cache.setdefault(n.module,top_names(mods[n.module]))
                    for a in n.names:
                        if a.name!='*' and a.name not in names:problems.append(f'{p.name}:{n.lineno} missing {n.module}.{a.name}')
                        imports[a.asname or a.name]=(n.module,a.name)
            for n in ast.walk(t):
                if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id in imports:
                    mod,fn=imports[n.func.id];sig=cache[mod][1].get(fn)
                    if sig:
                        req,args=sig;pos=len(n.args);kw={k.arg for k in n.keywords if k.arg};missing=[]
                        for i,arg in enumerate(args[:req]):
                            if i<pos or arg in kw:continue
                            missing.append(arg)
                        if missing:problems.append(f'{p.name}:{n.lineno} {mod}.{fn} missing {missing}')
        except Exception as e:problems.append(f'{p.name}: contract audit {e}')
    try:
        cfg=json.loads((BASE/'config.json').read_text(encoding='utf-8'))
        if not str(cfg.get('app_version','')).startswith(('7.0.0','7.0.1')):problems.append('wrong version')
    except Exception as e:problems.append(f'config {e}')
    try:
        src=(BASE/'app.py').read_text(encoding='utf-8');t=ast.parse(src)
        if "tabs=st.tabs(['💰 Best Use of My Money'" in src:problems.append('old 21-tab main navigation still present')
        for n in ast.walk(t):
            if isinstance(n,ast.IfExp):
                seg=ast.get_source_segment(src,n) or ''
                if any(x in seg for x in ('st.success(','st.warning(','st.error(','st.info(','st.markdown(','st.write(')):
                    problems.append(f'app.py:{n.lineno} risky Streamlit conditional expression')
    except Exception as e:problems.append(f'UI audit {e}')
    try:
        src=(BASE/'app.py').read_text(encoding='utf-8')
        for required in ('get_dashboard_cache_fast','Full Function Mode','optimizer_result_cache','segment_result_cache','Refresh current values','cached_history','cached_events','cached_mf_universe','cached_data_health','render_page_header','render_data_warning','PAGE_META','📣 Daily Recommendations','run_update_pipeline','build_ui_css','source_runtime_status','daily_money_result'):
            if required not in src:problems.append(f'performance UX missing: {required}')
        if "tracked=read_log();perf=performance_summary(tracked);segperf=segmented_performance(tracked)" not in src:
            problems.append('accuracy lazy-loading block missing')
        if "if active_page=='🏠 Home':" not in src or "alerts_home=load_alerts()" not in src:
            problems.append('Home-only daily center on-demand loading missing')
        # Ensure current portfolio prices are no longer refreshed automatically just by opening Portfolio.
        portfolio_pos=src.find("if active_page=='💼 My Portfolio':")
        if portfolio_pos>=0:
            portfolio_end=src.find("if active_page=='🥇 Gold / Silver':",portfolio_pos)
            pb=src[portfolio_pos:portfolio_end if portfolio_end>0 else None]
            if "for cs in crypto_universe():" in pb:problems.append('Portfolio still loops all crypto on page open')
    except Exception as e:problems.append(f'performance audit {e}')
    try:
        if str(BASE) not in sys.path:sys.path.insert(0,str(BASE))
        from portfolio_engine import read_portfolio,template_df,aggregate_holdings,PORTFOLIO_COLUMNS
        from portfolio_planner import future_value,goal_scenarios
        from money_optimizer import optimize_money
        from fixed_income import load as load_bonds,analyze as analyze_bonds
        from mutual_funds import load_universe,filter_universe
        from nse_events import load_all_events
        from news_gate import load_announcements
        from physical_metals import get_auto_rate
        from data_center import build_data_health
        from portfolio_analytics import portfolio_health
        from daily_decision import build_daily_actions
        from investment_options import load as load_options,rank as rank_options
        from ipo_engine import load as load_ipos,normalize as normalize_ipos
        from alerts import load_alerts
        from macro_intelligence import load as load_macro
        from asset_radar import analyze_asset
        from radar_engine import build_radar
        from daily_recommendations import stock_rows as daily_stock_rows, overall_action_status
        from ui_config import load_ui_settings, build_css
        from source_manager import load_registry, no_paid_usage_policy
        pf=read_portfolio();template_df();aggregate_holdings(pd.DataFrame(columns=PORTFOLIO_COLUMNS));future_value(10000,12,5);goal_scenarios(1e6,1e5,1e4,5,'MODERATE')
        opt=optimize_money(50000,182,'MODERATE');assert isinstance(opt,dict) and 'allocations' in opt
        analyze_bonds(load_bonds());load_universe();filter_universe('','All','All','All','All','All');load_all_events();load_announcements();get_auto_rate('GOLD',pd.DataFrame())
        dh,score=build_data_health();portfolio_health(pf);build_daily_actions(data_health=dh);oo=load_options();ranked_other=rank_options(oo,50000,.5,'MODERATE');load_ipos();normalize_ipos(pd.DataFrame());load_alerts();load_macro()
        assert len(oo)>=40, 'master investment universe unexpectedly small'
        assert 'ActiveStatus' in oo.columns and 'DataConfidence' in oo.columns
        assert not load_registry().empty and no_paid_usage_policy().get('SpendLimit₹')==0
        uis=load_ui_settings();assert 'radar-dynamic-theme' in build_css(uis)
        n=260;dates=pd.bdate_range('2025-01-01',periods=n);rows=[]
        for j,sym in enumerate(['AAA','BBB','CCC']):
            close=100+20*j+np.linspace(0,40,n)+np.sin(np.arange(n)/9+j)*2
            for i,d in enumerate(dates):
                c=float(close[i]);v=200000+j*50000;rows.append({'Date':d,'Symbol':sym,'Open':c*.995,'High':c*1.012,'Low':c*.988,'Close':c,'PrevClose':float(close[i-1]) if i else c,'Volume':v,'TradedValue':c*v})
        h=pd.DataFrame(rows);seed=pd.DataFrame([{'symbol':x,'company':x+' Ltd','sector':'Test','roce':20,'roe':18,'de':.2,'pe':22,'opm_pct':15,'profit_growth_5y':14,'sales_growth_3y':12,'fundamental_date':pd.Timestamp.today().strftime('%Y-%m-%d')} for x in ['AAA','BBB','CCC']])
        r,b,hists=build_radar(h,seed=seed,min_price=20,min_volume=100000,min_tv_cr=1);assert len(r)==9
        dr=daily_stock_rows(r,5);assert isinstance(dr,pd.DataFrame)
        ds,_reason=overall_action_status(dh);assert ds in ('ACTIONABLE','REVIEW REQUIRED','DO NOT ACT')
        cards,chart=analyze_asset(h[h.Symbol.eq('AAA')],'AAA','AAA Ltd','STOCK','₹');assert not cards.empty
    except Exception as e:problems.append(f'offline smoke {type(e).__name__}: {e}')
    if problems:
        print('VERIFY FAILED')
        for x in problems:print(' -',x)
        return 1
    print('VERIFY PASS — INDIA INVESTMENT RADAR 7.0.1 FULL RELIABILITY PREMIUM CLOUD-PERSISTENT')
    print(f'Python modules checked: {len(files)}')
    print('Undefined globals / local imports / required arguments: PASS')
    print('Premium navigation / Daily Recommendations / no-Delta UI audit: PASS')
    print('Portfolio / optimizer / full investment universe / MF / events / metals / data health: PASS')
    print('Synthetic stock radar + asset analysis: PASS')
    return 0
if __name__=='__main__':raise SystemExit(main())
