from pathlib import Path
from io import BytesIO
import json
import re
import pandas as pd
import numpy as np
import streamlit as st

from nse_data import update_history, load_history, cache_status
from radar_engine import build_radar
from backtest import run_backtest, load_backtest_stats
from walk_forward import run_walk_forward, load_walk_forward
from performance import update_saved_outcomes, performance_summary, segmented_performance
from alpha_vantage import load_local_api_key, save_local_api_key, refresh_fundamentals, load_auto_fundamentals
from nse_events import refresh_all_events, refresh_corporate_actions, action_risk_map, load_all_events, events_for_symbol
from news_gate import refresh_announcements, risk_map as news_risk_map, load_announcements
from market_outlook import outlook
from mutual_funds import refresh as refresh_mf, analyze_cached, refresh_universe as refresh_mf_universe, load_universe as load_mf_universe, filter_universe as filter_mf_universe, refresh_scheme_code as refresh_mf_scheme, refresh_filtered as refresh_mf_filtered, refresh_recommended_for_horizon as refresh_mf_for_horizon, universe_summary as mf_universe_summary
from fixed_income import load as load_bonds, save as save_bonds, analyze as analyze_bonds
from portfolio_planner import allocation, scenario_value, future_value, required_monthly_sip, goal_scenarios
from portfolio_engine import read_portfolio, analyse_portfolio, position_size, template_df, merge_portfolio, normalize_portfolio, aggregate_holdings, enrich_current_prices, PORTFOLIO_COLUMNS, ASSET_TYPES
from diagnostics import run as run_diagnostics
from dashboard_cache import save_cache, load_cache, cache_exists, load_chart
from backup_manager import create_backup, latest_backup, restore_backup
from alerts import build_alerts, load_alerts
from asset_radar import analyze_asset
from crypto_data import refresh as refresh_crypto, load as load_crypto, meta as crypto_meta, universe as crypto_universe
from physical_metals import load_state as load_metal_state, save_state as save_metal_state, effective_cost, physical_card, timing_decision, tranche_plan, rolling_scenarios, scenario_prices, automatic_reference_from_macro, refresh_auto_rates, load_auto_rates, get_auto_rate
from cross_asset import build as build_cross_asset, save as save_cross_asset, load as load_cross_asset, load_history as load_cross_asset_history
from macro_intelligence import refresh as refresh_macro, load as load_macro, meta as macro_meta, india_context
from ipo_engine import load as load_ipos, save as save_ipos, analyze as analyze_ipos, template as ipo_template, refresh_nse_current as refresh_nse_ipos, normalize as normalize_ipos
from investment_options import load as load_investment_options, save as save_investment_options, rank as rank_investment_options
from deposit_rates import load as load_fd_rates, refresh as refresh_fd_rates
from small_savings import load as load_small_savings, refresh as refresh_small_savings
from money_optimizer import horizon_days_from_choice, human_horizon, auto_risk, required_return_for_target, collect_candidates, score_candidates, build_plan, build_why_not, universal_explanation, portfolio_exposure, save_plan, load_plans, segment_candidates
from data_center import build_data_health, action_needed as data_action_needed
from portfolio_analytics import portfolio_health
from daily_decision import build_daily_actions, headline as daily_headline
from daily_recommendations import stock_rows as daily_stock_rows, mf_rows as daily_mf_rows, fixed_rows as daily_fixed_rows, ipo_rows as daily_ipo_rows, overall_action_status as daily_action_status
from ui_config import load_ui_settings, save_ui_settings, reset_ui_settings, save_background, clear_background, build_css as build_ui_css, PRESETS as UI_PRESETS
from source_manager import load_registry as load_source_registry, save_registry as save_source_registry, runtime_status as source_runtime_status, no_paid_usage_policy, record_success as source_success, record_failure as source_failure
from cloud_sync import pull_once as cloud_pull_once, push_changed as cloud_push_changed, status as cloud_status, pull_full_if_needed as cloud_pull_full_if_needed, pull_full_data as cloud_pull_full_data, push_full_data as cloud_push_full_data, full_status as cloud_full_status, test_connection as cloud_test_connection
from market_intelligence import (refresh_all as refresh_market_intelligence, load_fii_dii, institutional_summary, load_market_news, refresh_stock_news, load_stock_news, derivatives_summary, load_derivatives_history, breadth_summary as intel_breadth_summary, load_breadth_history, load_delivery, delivery_map, load_index_valuation, load_surveillance, surveillance_map, load_bulk_deals, load_block_deals, load_short_selling, load_fpi_sector, load_amfi_sip, market_context, context_explanation)
from data_vault import (inventory as data_vault_inventory, stock_excel as data_vault_stock_excel, category_excel as data_vault_category_excel, complete_archive as data_vault_complete_archive, archive_daily_snapshot, snapshot_index, instrument_snapshot_history)
from google_archive import (status as google_status, save_settings as save_google_settings, test_connection as google_test_connection, archive_bytes as google_archive_bytes, update_sheet_index as google_update_sheet_index, auto_after_update as google_auto_after_update)

BASE=Path(__file__).resolve().parent
CFG=json.loads((BASE/'config.json').read_text(encoding='utf-8'))
cloud_pull_once(BASE/'data')
# On ephemeral cloud hosts, automatically restore the last verified full market-data snapshot
# before deciding that First Setup is required. On a ready PC this is a no-op.
try:
    cloud_pull_full_if_needed(BASE/'data',min_sessions=CFG.get('min_history_for_radar',90))
except Exception:
    pass
UI_SETTINGS=load_ui_settings()
SEED=BASE/'fundamentals_seed.csv'
LOG=BASE/'data'/'recommendation_history.csv'

st.set_page_config(page_title='India Investment Radar',page_icon='🇮🇳',layout='wide',initial_sidebar_state='expanded')

def cloud_rerun():
    try: cloud_push_changed(BASE/'data')
    except Exception: pass
    st.rerun()



st.markdown('''<style>
:root{
  --radar-navy:#0A1426;
  --radar-navy-2:#12213A;
  --radar-gold:#C7A552;
  --radar-gold-soft:#F7F0DD;
  --radar-ink:#172033;
  --radar-muted:#667085;
  --radar-line:#E5EAF1;
  --radar-bg:#F4F7FB;
  --radar-card:#FFFFFF;
  --radar-success:#177245;
  --radar-warning:#A15C00;
  --radar-danger:#B42318;
}
.stApp{background:linear-gradient(180deg,#F7F9FC 0%,var(--radar-bg) 100%);color:var(--radar-ink)}
.block-container{padding-top:1rem;padding-bottom:3rem;max-width:1500px}
header[data-testid="stHeader"]{background:transparent}
[data-testid="stToolbar"],#MainMenu,footer{visibility:hidden;height:0}
[data-testid="stSidebar"]{background:linear-gradient(180deg,var(--radar-navy) 0%,#101A2E 100%);border-right:1px solid #22304A}
[data-testid="stSidebar"] h1,[data-testid="stSidebar"] h2,[data-testid="stSidebar"] h3,[data-testid="stSidebar"] label,[data-testid="stSidebar"] p{color:#F8FAFC}
[data-testid="stSidebar"] .stCaptionContainer p{color:#AAB5C7!important}
[data-testid="stSidebar"] hr{border-color:#26334B}
[data-testid="stSidebar"] [role="radiogroup"] label{padding:.25rem .2rem;border-radius:10px}
[data-testid="stSidebar"] [role="radiogroup"] label:hover{background:#FFFFFF0B}
[data-testid="stSidebar"] div[data-baseweb="select"]>div{background:#14223A;border-color:#2A3955;color:#F8FAFC}
[data-testid="stSidebar"] .stButton>button{background:#16243C;color:#F8FAFC;border:1px solid #2A3A55}
[data-testid="stSidebar"] .stButton>button[kind="primary"]{background:linear-gradient(135deg,#D5B866,#C7A552);color:#101827;border-color:#D5B866}
[data-testid="stSidebar"] .stButton>button:hover{border-color:#E6CC83;color:#FFF}
[data-testid="stMetric"]{background:var(--radar-card);border:1px solid var(--radar-line);padding:14px 16px;border-radius:15px;box-shadow:0 5px 18px rgba(15,23,42,.045)}
[data-testid="stMetricLabel"]{color:var(--radar-muted);font-weight:650}
[data-testid="stMetricValue"]{font-size:1.28rem;font-weight:800;color:var(--radar-ink)}
.stButton>button{border-radius:11px;min-height:42px;font-weight:720;border:1px solid #D7DEE8;box-shadow:0 1px 2px rgba(16,24,40,.03)}
.stButton>button[kind="primary"]{background:linear-gradient(135deg,var(--radar-navy),#172B4D);border-color:var(--radar-navy);color:white}
.stButton>button:hover{border-color:var(--radar-gold);color:var(--radar-navy)}
div[data-baseweb="select"]>div,div[data-baseweb="input"]>div{border-radius:10px!important}
[data-testid="stDataFrame"]{border:1px solid var(--radar-line);border-radius:13px;overflow:hidden;background:white;box-shadow:0 2px 10px rgba(15,23,42,.025)}
[data-testid="stExpander"]{border:1px solid var(--radar-line);border-radius:13px;background:white;box-shadow:0 3px 12px rgba(15,23,42,.03)}
.stTabs [data-baseweb="tab-list"]{gap:5px;border-bottom:1px solid var(--radar-line)}
.stTabs [data-baseweb="tab"]{height:41px;border-radius:9px 9px 0 0;padding-left:14px;padding-right:14px;font-weight:680}
.premium-hero{background:linear-gradient(135deg,#0A1426 0%,#142441 72%,#243555 100%);border:1px solid #263A5A;border-radius:20px;padding:25px 28px;margin:0 0 18px 0;box-shadow:0 12px 32px rgba(10,20,38,.14)}
.premium-kicker{font-size:.7rem;letter-spacing:.17em;text-transform:uppercase;color:#E4CB82;font-weight:850;margin-bottom:8px}
.premium-title{font-size:2rem;line-height:1.12;color:#FFF;font-weight:850;margin:0}
.premium-sub{color:#C7D0E0;margin-top:9px;font-size:.95rem;max-width:980px;line-height:1.5}
.premium-pill{display:inline-block;margin-top:14px;margin-right:7px;padding:6px 10px;border-radius:999px;background:#FFFFFF0D;border:1px solid #FFFFFF1E;color:#E9EEF7;font-size:.75rem;font-weight:680}
.page-head{background:white;border:1px solid var(--radar-line);border-radius:17px;padding:18px 21px;margin:0 0 14px 0;box-shadow:0 5px 18px rgba(15,23,42,.04)}
.page-kicker{font-size:.7rem;text-transform:uppercase;letter-spacing:.13em;font-weight:800;color:#9A7624;margin-bottom:5px}
.page-title{font-size:1.55rem;font-weight:840;color:var(--radar-ink);margin:0}
.page-sub{font-size:.9rem;color:var(--radar-muted);line-height:1.5;margin-top:5px}
.status-row{display:flex;flex-wrap:wrap;gap:7px;margin-top:11px}
.status-chip{display:inline-flex;align-items:center;gap:5px;padding:5px 9px;border-radius:999px;border:1px solid #E3E8EF;background:#FAFBFC;color:#475467;font-size:.72rem;font-weight:700}
.status-chip.good{background:#ECFDF3;border-color:#ABEFC6;color:#067647}
.status-chip.warn{background:#FFFAEB;border-color:#FEDF89;color:#B54708}
.status-chip.bad{background:#FEF3F2;border-color:#FECDCA;color:#B42318}
.section-title{font-size:1.32rem;font-weight:830;color:var(--radar-ink);margin:.35rem 0 .1rem}
.section-sub{color:var(--radar-muted);margin-bottom:.9rem;font-size:.9rem}
.quick-card{background:white;border:1px solid var(--radar-line);border-radius:15px;padding:17px 18px;min-height:116px;box-shadow:0 5px 18px rgba(15,23,42,.035)}
.quick-card .qtitle{font-size:1rem;font-weight:800;color:var(--radar-ink);margin-bottom:6px}
.quick-card .qtext{font-size:.87rem;color:var(--radar-muted);line-height:1.5}
.side-brand{padding:9px 2px 3px}.side-brand .name{font-size:1.08rem;font-weight:830;color:white}.side-brand .ver{font-size:.71rem;color:#D8BE74;margin-top:3px;line-height:1.35}
.soft-note{background:#FFF;border:1px solid var(--radar-line);border-left:4px solid var(--radar-gold);border-radius:12px;padding:12px 14px;color:#475467;margin:.4rem 0 .9rem}
</style>''',unsafe_allow_html=True)



NAV_GROUPS={
    '📣 Today':['📣 Daily Recommendations','🏠 Home'],
    '💰 Plan & Invest':['💰 Best Use of My Money','🎯 Go by Segment','🔥 ACTION BOARD','🚀 IPO / New Issues','🧭 Other Investments'],
    '📈 Markets':['🌍 Market Outlook','🏦 Market Intelligence','⚡ Stocks','🪙 ETFs','💰 Mutual Funds','🥇 Gold / Silver','₿ Crypto','🏦 Fixed Income','📅 Corporate Events'],
    '💼 Portfolio':['💼 My Portfolio','🧮 Position Size','🔔 Alerts'],
    '🧠 Research':['📊 Accuracy','🧪 Validation'],
    '⚙️ System':['🧠 Auto Data Center','🗄️ Data Vault','🔄 Sync Center','🩺 System Check','⚙️ Settings'],
}

PAGE_META={
    '📣 Daily Recommendations':('TODAY','Daily Recommendations','One place for today’s best validated opportunities, price/entry/target information where applicable, portfolio actions and the fastest money-allocation decision.'),
    '🏠 Home':('CONTROL CENTER','Home','Today’s decisions, portfolio context, market condition and the fastest routes into every major function.'),
    '💰 Best Use of My Money':('PLAN & INVEST','Best Use of My Money','Tell the Radar your amount, duration and risk. It compares suitable investments and builds an explained allocation plan.'),
    '🎯 Go by Segment':('PLAN & INVEST','Go by Segment','Choose Gold, Mutual Funds, Stocks, Bonds, IPO, Crypto or another segment and drill down to the exact product.'),
    '🔥 ACTION BOARD':('PLAN & INVEST','Action Board','See the strongest qualified opportunities already calculated in the saved daily dashboard.'),
    '🚀 IPO / New Issues':('PLAN & INVEST','IPO / New Issues','Evaluate current issues using valuation, growth, issue structure, subscription, risk and separate listing/long-term views.'),
    '🧭 Other Investments':('PLAN & INVEST','Other Investments','Compare government savings, NPS, FD/RD, REIT/InvIT, international and other products by goal, duration, liquidity and risk.'),
    '🌍 Market Outlook':('MARKETS','Market Outlook','Read the current market regime, institutional flow and macro evidence before acting on individual opportunities.'),
    '🏦 Market Intelligence':('MARKETS','Market Intelligence','FII/FPI & DII flows, market breadth, India VIX/macro context and public-news context in one evidence screen.'),
    '⚡ Stocks':('MARKETS','Stocks — All NSE','Search and analyze available NSE EQ stocks with full technical, fundamental, entry, risk and validation evidence.'),
    '🪙 ETFs':('MARKETS','ETFs','Review listed ETF opportunities with the same disciplined entry, risk and evidence framework.'),
    '💰 Mutual Funds':('MARKETS','Mutual Funds','Search the current AMFI universe, filter by category/plan/option and analyze exact schemes with return and risk evidence.'),
    '🥇 Gold / Silver':('MARKETS','Gold / Silver','Use physical-buy timing as the main view, with automatic reference rates, dealer override, zones, tranches and market-proxy evidence.'),
    '₿ Crypto':('MARKETS','Crypto','Analyze supported crypto assets with conservative technical, market-structure, risk and timing logic.'),
    '🏦 Fixed Income':('MARKETS','Fixed Income','Compare bonds and yield-based products by maturity, YTM, risk, liquidity and duration fit.'),
    '📅 Corporate Events':('MARKETS','Corporate Events','Review NSE actions, board meetings, results and announcements that can change or block a recommendation.'),
    '💼 My Portfolio':('PORTFOLIO','My Portfolio','Maintain purchase lots, import/update holdings, review allocation and P&L, and connect new decisions to what you already own.'),
    '🧮 Position Size':('PORTFOLIO','Position Size','Convert risk tolerance and stop-loss distance into a disciplined quantity and capital-at-risk decision.'),
    '🔔 Alerts':('PORTFOLIO','Alerts','Review generated alerts for entries, exits, events, portfolio risk and recommendation changes.'),
    '📊 Accuracy':('RESEARCH','Accuracy','Measure resolved recommendation outcomes, win rate and segment-level reliability instead of relying on labels alone.'),
    '🧪 Validation':('RESEARCH','Validation','Build and inspect backtest and walk-forward evidence used to keep confidence conservative.'),
    '🧠 Auto Data Center':('SYSTEM','Auto Data Center','See source freshness, trust, fallbacks and exactly which data needs attention before you rely on a recommendation.'),
    '🗄️ Data Vault':('SYSTEM','Data Vault','Search historical data, export an individual stock to Excel, browse dated recommendation snapshots and create a complete verified data archive.'),
    '🔄 Sync Center':('SYSTEM','Sync Center','See PC/cloud persistence, Supabase sync and Google Drive/Sheets archive status in one place.'),
    '🩺 System Check':('SYSTEM','System Check','Run diagnostics, backup/restore checks and confirm the local installation is healthy.'),
    '⚙️ Settings':('SYSTEM','Settings','Control optional providers and review the permanent recommendation rules without changing normal day-to-day operation.'),
}

DATA_PAGE_SOURCES={
    '📣 Daily Recommendations':['NSE price history','Corporate events','Corporate announcements','Mutual Fund universe / NAV','Physical Gold/Silver auto reference','IPO / new issues'],
    '🏠 Home':['NSE price history','Corporate events','Mutual Fund universe / NAV','Macro context'],
    '🔥 ACTION BOARD':['NSE price history','Corporate events','Corporate announcements'],
    '🌍 Market Outlook':['NSE price history','Macro context','FII / DII institutional flow','F&O participant positioning','Market breadth history','Market news context'],
    '🏦 Market Intelligence':['NSE price history','Macro context','FII / DII institutional flow','F&O participant positioning','Market breadth history','Security delivery data','Index valuation','Surveillance indicators','FPI sector allocation/flow','AMFI SIP flow','Market news context'],
    '⚡ Stocks':['NSE price history','Corporate events','Corporate announcements','Auto fundamentals','FII / DII institutional flow','F&O participant positioning','Security delivery','Surveillance'],
    '🪙 ETFs':['NSE price history'],
    '💰 Mutual Funds':['Mutual Fund universe / NAV','MF deep histories'],
    '🥇 Gold / Silver':['Physical Gold/Silver auto reference','NSE price history','Macro context'],
    '₿ Crypto':['Crypto prices'],
    '🏦 Fixed Income':['Fixed-income yields'],
    '🚀 IPO / New Issues':['IPO / new issues'],
    '📅 Corporate Events':['Corporate events','Corporate announcements'],
    '💼 My Portfolio':['Portfolio'],
}


def seed_data():
    return pd.read_csv(SEED) if SEED.exists() else pd.DataFrame()


def read_log():
    if LOG.exists():
        try:return pd.read_csv(LOG)
        except Exception:pass
    return pd.DataFrame()


@st.cache_data(show_spinner=False,ttl=300)
def cached_history(max_sessions):
    return load_history(max_sessions=max_sessions)

@st.cache_data(show_spinner=False,ttl=180)
def cached_events():
    return load_all_events()

@st.cache_data(show_spinner=False,ttl=300)
def cached_mf_universe():
    return load_mf_universe()

@st.cache_data(show_spinner=False,ttl=300)
def cached_mf_analysis():
    return analyze_cached()

@st.cache_data(show_spinner=False,ttl=300)
def cached_data_health():
    return build_data_health()

@st.cache_data(show_spinner=False,ttl=300)
def cached_cross_asset():
    return load_cross_asset()

@st.cache_data(show_spinner=False,ttl=300)
def cached_ipos_analyzed():
    return analyze_ipos(load_ipos())

@st.cache_data(show_spinner=False,ttl=300)
def cached_other_options():
    return load_investment_options()

def clear_runtime_caches():
    st.cache_data.clear()
    invalidate_fast_cache()

def render_page_header(page,meta=None):
    kicker,title,sub=PAGE_META.get(page,('INDIA INVESTMENT RADAR',page,''))
    chips=[]
    if meta:
        d=meta.get('data_date')
        if d: chips.append(('good',f'Data {d}'))
        r=meta.get('market_regime')
        if r: chips.append(('good' if str(r)=='BULLISH' else ('warn' if str(r)=='CAUTIOUS' else 'bad'),f'Market {r}'))
    try:
        dh,score=cached_data_health()
        cls='good' if score>=80 else ('warn' if score>=60 else 'bad')
        chips.append((cls,f'Data health {score:.0f}%'))
        wanted=DATA_PAGE_SOURCES.get(page,[])
        if wanted and dh is not None and not dh.empty:
            rel=dh[dh.Data.isin(wanted)]
            bad=rel[rel.Status.isin(['MISSING','STALE','OLD'])]
            if bad.empty: chips.append(('good','Sources ready'))
            else: chips.append(('warn',f'{len(bad)} source(s) need attention'))
    except Exception:
        pass
    chip_html=''.join([f'<span class="status-chip {c}">{t}</span>' for c,t in chips])
    st.markdown(f'<div class="page-head"><div class="page-kicker">{kicker}</div><div class="page-title">{title}</div><div class="page-sub">{sub}</div><div class="status-row">{chip_html}</div></div>',unsafe_allow_html=True)

def render_data_warning(page):
    wanted=DATA_PAGE_SOURCES.get(page,[])
    if not wanted: return
    try:
        dh,_=cached_data_health()
        if dh is None or dh.empty: return
        rel=dh[dh.Data.isin(wanted)]
        bad=rel[rel.Status.isin(['MISSING','STALE','OLD'])]
        if not bad.empty:
            st.warning('Data attention: '+', '.join((bad.Data.astype(str)+' ['+bad.Status.astype(str)+']').tolist())+'. High-confidence calls should be treated conservatively until refreshed.')
    except Exception:
        pass

def dataframe_to_xlsx_bytes(df):
    bio=BytesIO()
    with pd.ExcelWriter(bio,engine='openpyxl') as writer:
        df.to_excel(writer,index=False,sheet_name='Portfolio')
    return bio.getvalue()


def get_dashboard_cache_fast():
    """Load dashboard cache once per Streamlit session."""
    if '_dashboard_cache_obj' not in st.session_state:
        st.session_state['_dashboard_cache_obj']=load_cache() if cache_exists() else None
    return st.session_state.get('_dashboard_cache_obj')


def invalidate_fast_cache():
    st.session_state.pop('_dashboard_cache_obj',None)


def refresh_saved_portfolio_prices(radar_df=None,mf_df=None,bonds_df=None):
    """Refresh current values only on Daily Update or explicit Portfolio refresh."""
    portfolio_file=BASE/'data'/'my_portfolio.csv'
    if not portfolio_file.exists():return {'ok':True,'message':'No saved portfolio to refresh.'}
    try:
        lots=read_portfolio()
        if lots is None or lots.empty:return {'ok':True,'message':'No saved portfolio to refresh.'}
        c=get_dashboard_cache_fast() or {}
        radar_df=radar_df if radar_df is not None else c.get('radar',pd.DataFrame())
        mf_df=mf_df if mf_df is not None else c.get('mf',pd.DataFrame())
        bonds_df=bonds_df if bonds_df is not None else c.get('bonds',pd.DataFrame())
        cryptop={};cm=crypto_meta();fx=float(cm.get('usd_inr') or 0)
        if fx>0:
            for cs in crypto_universe():
                cg=load_crypto(cs)
                if cg is not None and not cg.empty:cryptop[cs]=float(cg.iloc[-1].Close)*fx
        enriched=enrich_current_prices(lots,radar_df,mf_df,load_metal_state(),cryptop,bonds_df)
        enriched.to_csv(portfolio_file,index=False)
        return {'ok':True,'message':f'Portfolio current values refreshed for {len(enriched)} lot(s).'}
    except Exception as e:return {'ok':False,'message':'Portfolio refresh skipped: '+str(e)}


def auto_track(radar):
    if radar is None or radar.empty:return
    keep=radar[radar.Signal.isin(['STRONG BUY','BUY','BUY ON PULLBACK','WATCH'])].copy()
    top=pd.concat([keep[keep.Category==c].head(CFG['top_n']) for c in ['SWING','SHORT','LONG']],ignore_index=True)
    if top.empty:return
    top['SavedAt']=pd.Timestamp.now().isoformat(timespec='seconds')
    if LOG.exists():
        try:old=pd.read_csv(LOG)
        except Exception:old=pd.DataFrame()
        if not old.empty:
            oldkey=set((old.Category.astype(str)+'|'+old.Symbol.astype(str)+'|'+old.DataDate.astype(str)).tolist())
            key=top.Category.astype(str)+'|'+top.Symbol.astype(str)+'|'+top.DataDate.astype(str)
            top=top[~key.isin(oldkey)]
            if top.empty:return
        pd.concat([old,top],ignore_index=True,sort=False).to_csv(LOG,index=False)
    else:top.to_csv(LOG,index=False)


def recalc_and_save(status_cb=None):
    def msg(x):
        if status_cb:status_cb(x)
    msg('Loading local NSE history...')
    h=load_history(max_sessions=CFG['history_sessions'])
    s=seed_data();auto=load_auto_fundamentals();acts=action_risk_map(CFG['corporate_action_block_days']);bt=load_backtest_stats();wfstats=load_walk_forward()
    news_available=not load_announcements().empty
    nmap=news_risk_map() if news_available else {}
    mctx=market_context(h); dmap=delivery_map(); smap=surveillance_map()
    msg('Calculating stock and ETF radar with market-intelligence context...')
    radar,breadth,hists=build_radar(h,s,auto,acts,bt,wfstats,nmap,news_available,
                                    CFG['min_price'],CFG['min_latest_volume'],CFG['min_median_traded_value_cr'],
                                    CFG['fundamental_max_age_days'],CFG.get('strong_buy'),market_context=mctx,delivery_map=dmap,surveillance_map=smap)
    msg('Calculating probability-based market outlook...')
    mout,proxy=outlook(h,200,market_context=mctx)
    msg('Calculating mutual-fund and fixed-income dashboards...')
    mf,mfd=analyze_cached();bonds=analyze_bonds(load_bonds())
    msg('Building across-asset opportunity snapshot...')
    try:
        save_cross_asset(build_cross_asset(radar,mf,bonds,h,CFG))
    except Exception as e:
        msg('Across-asset snapshot kept optional: '+str(e))
    prev=load_cache() if cache_exists() else None
    prev_reg=(prev or {}).get('meta',{}).get('market_regime') if prev else None
    meta={
        'calculated_at':pd.Timestamp.now().isoformat(timespec='seconds'),
        'data_date':radar.DataDate.iloc[0] if not radar.empty else None,
        'market_regime':radar.MarketRegime.iloc[0] if not radar.empty else None,
        'news_gate_available':news_available,
        'app_version':CFG.get('app_version'),
        'market_intelligence_score':mctx.get('Score'),
        'market_intelligence_regime':mctx.get('Regime'),
        'market_data_completeness':mctx.get('DataCompleteness%')
    }
    save_cache(radar,breadth,mout,proxy,mf,mfd,bonds,meta,hists)
    msg('Archiving the actual dated recommendation/intelligence snapshot...')
    try:
        archive_daily_snapshot(meta.get('data_date') or pd.Timestamp.now(),radar,breadth,mout,mf,bonds,analyze_ipos(load_ipos()),mctx,{
            'fii_dii':load_fii_dii(),'derivatives':load_derivatives_history(),'breadth_history':load_breadth_history(),
            'delivery':load_delivery(),'index_valuation':load_index_valuation(),'surveillance':load_surveillance(),
            'fpi_sector':load_fpi_sector(),'amfi_sip':load_amfi_sip()})
    except Exception as e:
        msg('Dated Data Vault snapshot warning: '+str(e))
    auto_track(radar)
    tracked=update_saved_outcomes(LOG,h) if LOG.exists() else pd.DataFrame()
    build_alerts(radar,tracked,prev_reg)
    create_backup(CFG.get('backup_keep',12))
    msg('Dashboard saved. Future starts will open from cache immediately.')
    return radar


def run_update_pipeline(full=False):
    """One visible, failure-tolerant update pipeline used by Daily Update and First Setup.
    Critical failures are reported instead of leaving the UI looking frozen. Existing verified cache is preserved.
    """
    steps=[]
    target=CFG['history_sessions']
    steps.append(('NSE price history','NSE / market history',lambda cb:update_history(target_sessions=target,lookback_calendar_days=650,status_cb=cb)))
    steps.append(('Corporate events','Corporate Events',lambda cb:refresh_all_events(CFG.get('corporate_events_back_days',45),CFG.get('corporate_events_forward_days',120),status_cb=cb)))
    steps.append(('Corporate announcements','Corporate Announcements',lambda cb:refresh_announcements(CFG.get('news_lookback_days',10),status_cb=cb)))
    steps.append(('Mutual Fund universe / NAV','Mutual Funds — AMFI universe',lambda cb:refresh_mf_universe(status_cb=cb)))
    steps.append(('Mutual Fund selected histories','Mutual Funds — ranked/history cache',lambda cb:refresh_mf(CFG['mutual_fund_searches'],status_cb=cb)))
    steps.append(('Crypto prices','Crypto market cache',lambda cb:refresh_crypto(CFG.get('crypto_symbols'),status_cb=cb)))
    def _macro(cb):
        macro_now=refresh_macro(status_cb=cb)
        if macro_now is not None and not macro_now.empty:refresh_auto_rates(macro_now)
        return {'ok':True,'message':'Macro, India VIX/global context and Gold/Silver automatic reference checked.'}
    steps.append(('Macro / Gold Silver','Macro + India VIX + Gold/Silver reference',_macro))
    steps.append(('FII / DII institutional flow','Institutional + Derivatives + Breadth Intelligence',lambda cb:refresh_market_intelligence(status_cb=cb,news_topics=CFG.get('market_news_topics'),history=load_history(max_sessions=CFG['history_sessions']))))
    steps.append(('IPO / new issues','IPO / SME IPO current issues',lambda cb:refresh_nse_ipos(status_cb=cb)))
    steps.append(('Bank FD / deposit directory','FD / RD bank rates',lambda cb:refresh_fd_rates(status_cb=cb)))
    steps.append(('Post Office / small savings','Post Office / Govt small-savings rates',lambda cb:refresh_small_savings(status_cb=cb)))

    _gstat=google_status();_google_auto=bool(_gstat.get('configured') and (_gstat.get('auto_archive_after_update') or _gstat.get('auto_update_sheet_index')))
    total=len(steps)+2+(1 if cloud_status().get('enabled') else 0)+(1 if _google_auto else 0)
    prog=st.progress(0,text='Preparing update...')
    detail=st.empty();logbox=st.container()
    rows=[]
    started=pd.Timestamp.now()
    def _cb(label):
        return lambda msg: detail.caption(f'🔄 {label}: {msg}')
    for idx,(source_key,label,fn) in enumerate(steps,1):
        prog.progress(int((idx-1)/total*100),text=f'{idx}/{total} — {label}')
        detail.caption(f'🔄 Working: {label}')
        t0=pd.Timestamp.now()
        ok=True;message='Complete'
        try:
            res=fn(_cb(label))
            if isinstance(res,dict):
                ok=bool(res.get('ok',True));message=str(res.get('message') or res.get('source') or 'Complete')
            elif res is not None:message=str(res)[:220]
            if ok:source_success(source_key,message)
            else:source_failure(source_key,message,15,'limit' in message.lower() or '429' in message.lower())
        except Exception as e:
            ok=False;message=f'{type(e).__name__}: {e}'
            source_failure(source_key,message,15,'429' in message or 'rate limit' in message.lower())
        elapsed=(pd.Timestamp.now()-t0).total_seconds()
        rows.append({'Step':label,'Status':'PASS' if ok else 'WARNING','Seconds':round(elapsed,1),'Detail':message})
        if ok:detail.caption(f'✅ {label}: {message}')
        else:detail.caption(f'⚠ {label}: {message} — preserved last verified cache where available.')

    idx=len(steps)+1
    prog.progress(int((idx-1)/total*100),text=f'{idx}/{total} — Rebuilding verified recommendations')
    t0=pd.Timestamp.now();ok=True;message='Dashboard/recommendations rebuilt.'
    try:
        recalc_and_save(lambda x:detail.caption('🔄 Recommendation engine: '+str(x)))
        clear_runtime_caches();source_success('Recommendation engine',message)
    except Exception as e:
        ok=False;message=f'{type(e).__name__}: {e}';source_failure('Recommendation engine',message)
    rows.append({'Step':'Recommendation engine','Status':'PASS' if ok else 'FAIL','Seconds':round((pd.Timestamp.now()-t0).total_seconds(),1),'Detail':message})

    idx+=1
    prog.progress(int((idx-1)/total*100),text=f'{idx}/{total} — Refreshing portfolio')
    t0=pd.Timestamp.now();ok=True
    try:
        fresh=get_dashboard_cache_fast() or {};pres=refresh_saved_portfolio_prices(fresh.get('radar'),fresh.get('mf'),fresh.get('bonds'));ok=bool(pres.get('ok',True));message=pres.get('message','Portfolio checked.')
    except Exception as e:
        ok=False;message=f'{type(e).__name__}: {e}'
    rows.append({'Step':'Portfolio current values','Status':'PASS' if ok else 'WARNING','Seconds':round((pd.Timestamp.now()-t0).total_seconds(),1),'Detail':message})

    # Persist both personal state and the FULL verified market/calculation dataset when Supabase is configured.
    # This is essential on free cloud hosts such as Render because their local filesystem is ephemeral.
    if cloud_status().get('enabled'):
        idx+=1
        prog.progress(int((idx-1)/total*100),text=f'{idx}/{total} — Saving verified data to Supabase')
        t0=pd.Timestamp.now(); ok=True
        try:
            cloud_push_changed(BASE/'data')
            cres=cloud_push_full_data(BASE/'data',status_cb=lambda x:detail.caption('☁️ '+str(x)))
            ok=bool(cres.get('ok',False));message=str(cres.get('message','Cloud data sync complete.'))
        except Exception as e:
            ok=False;message=f'{type(e).__name__}: {e}'
        rows.append({'Step':'Cloud full-data persistence','Status':'PASS' if ok else 'WARNING','Seconds':round((pd.Timestamp.now()-t0).total_seconds(),1),'Detail':message})

    if _google_auto:
        idx+=1
        prog.progress(int((idx-1)/total*100),text=f'{idx}/{total} — Google archive / index')
        t0=pd.Timestamp.now();ok=True
        try:
            gres=google_auto_after_update(lambda:data_vault_complete_archive(BASE/'data'),data_vault_inventory(BASE/'data'),snapshot_index())
            ok=all(bool(x.get('ok',False)) for x in gres) if gres else True
            message=' | '.join(str(x.get('message','')) for x in gres) if gres else 'Google automatic actions not requested.'
        except Exception as e:
            ok=False;message=f'{type(e).__name__}: {e}'
        rows.append({'Step':'Google archive / Sheet index','Status':'PASS' if ok else 'WARNING','Seconds':round((pd.Timestamp.now()-t0).total_seconds(),1),'Detail':message})

    prog.progress(100,text='Update cycle complete')
    total_sec=(pd.Timestamp.now()-started).total_seconds()
    report=pd.DataFrame(rows)
    failures=int((report.Status=='FAIL').sum()) if not report.empty else 0
    warnings=int((report.Status=='WARNING').sum()) if not report.empty else 0
    if failures:detail.error(f'Update finished with {failures} critical failure(s) and {warnings} warning(s). Review the report before acting.')
    elif warnings:detail.warning(f'Update finished in {total_sec:.0f}s with {warnings} warning(s). The system preserved verified fallbacks/caches.')
    else:detail.success(f'Update complete in {total_sec:.0f}s. All update steps passed.')
    with logbox.expander('Update report',expanded=bool(failures or warnings)):
        st.dataframe(report,use_container_width=True,hide_index=True)
    st.session_state['last_update_report']=report
    st.session_state['last_update_summary']={'finished':pd.Timestamp.now().isoformat(timespec='seconds'),'seconds':round(total_sec,1),'failures':failures,'warnings':warnings}
    return report


# Apply the user-selected default landing page without removing any function.
default_page=str(UI_SETTINGS.get('default_page','📣 Daily Recommendations'))
if 'premium_nav_group' not in st.session_state:
    for _g,_pages in NAV_GROUPS.items():
        if default_page in _pages:
            st.session_state['premium_nav_group']=_g
            st.session_state[f'premium_nav_page_{_g}']=default_page
            break

status=cache_status()
cache=get_dashboard_cache_fast()
with st.sidebar:
    st.markdown(f'''<div class="side-brand"><div class="name">🇮🇳 Investment Radar</div><div class="ver">{CFG.get("app_version","SMART")}</div></div>''',unsafe_allow_html=True)
    st.markdown('### Workspace')
    nav_group=st.radio('Workspace',list(NAV_GROUPS),label_visibility='collapsed',key='premium_nav_group')
    active_page=st.selectbox('Function',NAV_GROUPS[nav_group],label_visibility='collapsed',key=f'premium_nav_page_{nav_group}')
    st.divider()
    st.caption(f"NSE: {status['sessions']} sessions • Latest: {status['last'] or 'None'}")
    if cache:st.caption('Dashboard: '+str(cache.get('meta',{}).get('calculated_at','saved')))
    if st.button('🔄 DAILY UPDATE',type='primary',use_container_width=True):
        run_update_pipeline(full=False)
        st.cache_data.clear();cloud_rerun()
    _lus=st.session_state.get('last_update_summary')
    _lur=st.session_state.get('last_update_report')
    if _lus:
        icon='✅' if not _lus.get('failures') and not _lus.get('warnings') else ('⚠' if not _lus.get('failures') else '🔴')
        st.caption(f"{icon} Last update: {_lus.get('finished','')} • {_lus.get('seconds',0):.0f}s • {_lus.get('warnings',0)} warning(s) • {_lus.get('failures',0)} failure(s)")
        if isinstance(_lur,pd.DataFrame):
            with st.expander('Last update report',expanded=bool(_lus.get('warnings') or _lus.get('failures'))):st.dataframe(_lur,use_container_width=True,hide_index=True)
    with st.expander('🛠 Maintenance — occasional',expanded=False):
        st.caption('Not needed for normal daily use.')
        if st.button('⚡ Rebuild saved dashboard',use_container_width=True):
            box=st.empty();recalc_and_save(lambda x:box.caption(x));clear_runtime_caches();box.success('Dashboard rebuilt.');cloud_rerun()
        if st.button('📥 Full Data Setup / Repair',use_container_width=True):
            if cloud_status().get('enabled'):
                box=st.empty();box.caption('☁️ Checking Supabase for an existing full-data snapshot...')
                try:
                    rr=cloud_pull_full_data(BASE/'data',force=False,status_cb=lambda x:box.caption('☁️ '+str(x)),min_sessions=CFG.get('min_history_for_radar',90))
                    box.caption(str(rr.get('message','')))
                except Exception as e:box.warning('Cloud restore check skipped: '+str(e))
            run_update_pipeline(full=True)
            st.cache_data.clear();cloud_rerun()
        st.divider()
        st.caption('☁️ Full Data Cloud Sync — keeps downloaded market data available after cloud restart and shares it with your PC.')
        _cs=cloud_status(); _cfs=cloud_full_status(BASE/'data')
        if _cs.get('enabled'):
            st.caption('Cloud: CONNECTED • '+str(_cfs.get('message') or _cs.get('full_message') or _cs.get('message','')))
            csa,csb=st.columns(2)
            with csa:
                if st.button('☁️ Save FULL data',use_container_width=True):
                    b=st.empty();r=cloud_push_full_data(BASE/'data',status_cb=lambda x:b.caption('☁️ '+str(x)));
                    (b.success if r.get('ok') else b.warning)(r.get('message','Cloud sync finished.'))
            with csb:
                if st.button('☁️ Restore FULL data',use_container_width=True):
                    b=st.empty();r=cloud_pull_full_data(BASE/'data',force=True,status_cb=lambda x:b.caption('☁️ '+str(x)),min_sessions=CFG.get('min_history_for_radar',90));
                    (b.success if r.get('ok') else b.warning)(r.get('message','Cloud restore finished.'));st.cache_data.clear();invalidate_fast_cache()
        else:
            st.caption('Cloud: NOT CONFIGURED. Online Render can still run, but downloaded files will not survive a restart until Supabase is connected.')
        if st.button('🧠 Build all validation',use_container_width=True):
            box=st.empty();h=load_history(max_sessions=CFG['history_sessions'])
            with st.spinner('Building validation evidence...'):
                run_backtest(h,CFG['backtest_universe_size'],lambda x:box.caption('Backtest: '+x));run_walk_forward(h,CFG['backtest_universe_size'],lambda x:box.caption('Walk-forward: '+x));recalc_and_save(lambda x:box.caption(x));clear_runtime_caches()
            box.success('Validation ready.');cloud_rerun()
    st.caption('⚡ Full Function Mode — all modules available; heavy work runs only when requested.')

# Apply the saved theme/background after navigation is known. Analysis pages default to a cleaner background unless enabled in Settings.
_analysis_pages={'🏦 Market Intelligence','⚡ Stocks','🪙 ETFs','💰 Mutual Funds','🥇 Gold / Silver','₿ Crypto','🏦 Fixed Income','📊 Accuracy','🧪 Validation','🧠 Auto Data Center','🗄️ Data Vault','🔄 Sync Center','🩺 System Check'}
st.markdown(build_ui_css(UI_SETTINGS,analysis_page=active_page in _analysis_pages),unsafe_allow_html=True)

_core_required_pages={'📣 Daily Recommendations','🏠 Home','💰 Best Use of My Money','🎯 Go by Segment','🔥 ACTION BOARD','🌍 Market Outlook','🏦 Market Intelligence','⚡ Stocks','🪙 ETFs','🥇 Gold / Silver','₿ Crypto','💼 My Portfolio','🧮 Position Size','🔔 Alerts','📊 Accuracy','🧪 Validation','📅 Corporate Events'}
_core_ready=status['sessions']>=CFG['min_history_for_radar']
if not _core_ready and active_page in _core_required_pages:
    st.warning('Core market data is not ready yet. Use **Maintenance → Full Data Setup / Repair**. If Supabase already has a full-data snapshot, Radar restores it first instead of downloading everything again.')
    cst=cloud_status();cfs=cloud_full_status(BASE/'data')
    st.caption(('☁️ '+str(cfs.get('message') or cst.get('message',''))) if cst.get('enabled') else '☁️ Supabase full-data sync is not configured on this device.')
    st.dataframe(run_diagnostics(),use_container_width=True,hide_index=True);st.stop()

cache=get_dashboard_cache_fast()
if cache is None and active_page in _core_required_pages:
    st.info('NSE history exists but the saved recommendation dashboard is missing. Use **Rebuild saved dashboard** once.')
    st.dataframe(run_diagnostics(),use_container_width=True,hide_index=True);st.stop()

# Independent pages (Mutual Funds, Fixed Income, IPO, Other Investments, Data Center, System Check, Settings)
# remain usable even before NSE First Setup completes.
if cache is None:
    cache={'radar':pd.DataFrame(),'breadth':{},'market_outlook':pd.DataFrame(),'market_proxy':pd.DataFrame(),'mf':pd.DataFrame(),'mf_details':{},'bonds':pd.DataFrame(),'meta':{}}
radar=cache.get('radar',pd.DataFrame());breadth=cache.get('breadth',{});mout=cache.get('market_outlook',pd.DataFrame());proxy=cache.get('market_proxy',pd.DataFrame());mf=cache.get('mf',pd.DataFrame());mfd=cache.get('mf_details',{});bonds=cache.get('bonds',pd.DataFrame());meta=cache.get('meta',{})
if radar is not None and not radar.empty:
    reg=str(radar.MarketRegime.iloc[0]) if 'MarketRegime' in radar.columns else 'UNKNOWN'
    total_symbols=int(radar.Symbol.nunique()) if 'Symbol' in radar.columns else 0
    eligible_symbols=int(radar.loc[radar.Eligibility.eq('ELIGIBLE'),'Symbol'].nunique()) if 'Eligibility' in radar.columns and 'Symbol' in radar.columns else total_symbols
else:
    reg='SETUP REQUIRED';total_symbols=0;eligible_symbols=0
ico={'BULLISH':'🟢','CAUTIOUS':'🟡','WEAK':'🔴'}.get(reg,'⚪')

if active_page=='🏠 Home':
    st.markdown(f'''<div class="premium-hero"><div class="premium-kicker">INDIA INVESTMENT RADAR</div><div class="premium-title">All functions. Fast when you need them. Evidence before action.</div><div class="premium-sub">One permanent workspace for Stocks, Mutual Funds, Gold/Silver, Fixed Income, IPOs, Crypto, portfolio decisions, validation and data health. Heavy calculations run on demand or during Daily Update; saved evidence opens quickly.</div><span class="premium-pill">{CFG.get('app_version','SMART')}</span><span class="premium-pill">Full Function Mode</span><span class="premium-pill">On-demand Heavy Work</span><span class="premium-pill">Freshness & Validation Gates</span></div>''',unsafe_allow_html=True)
elif active_page!='📣 Daily Recommendations':
    render_page_header(active_page,meta)
render_data_warning(active_page)

if active_page in ('📣 Daily Recommendations','🏠 Home','🔥 ACTION BOARD','🌍 Market Outlook'):
    c1,c2,c3,c4,c5,c6,c7=st.columns(7)
    c1.metric('Market',f'{ico} {reg}');c2.metric('Above EMA21',f"{breadth.get('pct_above_ema21',0):.1f}%");c3.metric('Above EMA50',f"{breadth.get('pct_above_ema50',0):.1f}%");c4.metric('Advancers',f"{breadth.get('pct_advancers',0):.1f}%");c5.metric('All NSE EQ',f'{total_symbols:,}');c6.metric('Eligible',f'{eligible_symbols:,}');c7.metric('Data Date',str(meta.get('data_date','')))
    _inst=institutional_summary()
    if _inst.get('Bias')!='UNAVAILABLE':
        i1,i2,i3,i4=st.columns(4)
        i1.metric('Institutional Flow',_inst.get('Bias','—'));i2.metric('FII/FPI latest',f"₹{_inst.get('FIINet₹Cr',0):+,.0f} Cr" if pd.notna(_inst.get('FIINet₹Cr',np.nan)) else '—');i3.metric('DII latest',f"₹{_inst.get('DIINet₹Cr',0):+,.0f} Cr" if pd.notna(_inst.get('DIINet₹Cr',np.nan)) else '—');i4.metric('FII 5 sessions',f"₹{_inst.get('FII5D₹Cr',0):+,.0f} Cr" if pd.notna(_inst.get('FII5D₹Cr',np.nan)) else '—')
        st.caption('NSE same-day FII/FPI & DII cash-market data is provisional. Institutional flow is supporting context, not a standalone Buy/Sell trigger.')

if active_page=='📣 Daily Recommendations':
    try:_ddh,_dscore=cached_data_health()
    except Exception:_ddh,_dscore=pd.DataFrame(),0.0
    _action_status,_action_reason=daily_action_status(_ddh)
    _stocks=daily_stock_rows(radar,5)
    _mfs=daily_mf_rows(mf,3)
    _fixed=daily_fixed_rows(bonds,3)
    try:_ipos=daily_ipo_rows(cached_ipos_analyzed(),3)
    except Exception:_ipos=pd.DataFrame()
    _cross=cached_cross_asset()
    _strong=int((radar.Signal.astype(str)=='STRONG BUY').sum()) if not radar.empty else 0
    _buy=int(radar.Signal.astype(str).isin(['BUY','BUY ON PULLBACK']).sum()) if not radar.empty else 0
    _review=int((_ddh.Status.astype(str).isin(['MISSING','OLD','STALE'])).sum()) if _ddh is not None and not _ddh.empty else 0

    st.markdown(f'''<div class="premium-hero"><div class="premium-kicker">DAILY RECOMMENDATIONS</div><div class="premium-title">What deserves your attention today — in one place.</div><div class="premium-sub">Only validated decisions are promoted. Open any specialist page for deeper evidence; nothing is removed from the full system.</div><span class="premium-pill">{_action_status}</span><span class="premium-pill">Data health {_dscore:.0f}%</span><span class="premium-pill">Market {reg}</span><span class="premium-pill">Data {meta.get('data_date','—')}</span></div>''',unsafe_allow_html=True)
    if _action_status=='DO NOT ACT':st.error(_action_reason)
    elif _action_status=='REVIEW REQUIRED':st.warning(_action_reason)
    else:st.success('✅ Critical stored datasets are within the configured freshness window. Final market outcomes remain probabilistic.')

    a,b,c,d=st.columns(4)
    a.metric('🔥 Strong Buy',_strong)
    b.metric('🟢 Buy / Pullback',_buy)
    c.metric('⚠ Data items to review',_review)
    d.metric('Overall data health',f'{_dscore:.0f}%')

    st.markdown('### 🏆 Today’s best opportunities')
    if _cross is None or _cross.empty:
        st.info('Across-asset snapshot is not ready. Run DAILY UPDATE once.')
    else:
        x=_cross.copy().head(12)
        if 'Score' in x.columns:x['Score']=pd.to_numeric(x['Score'],errors='coerce').round(1)
        st.dataframe(x[[c for c in ['AssetClass','Instrument','Decision','Score','Confidence','Risk','Horizon','Reason'] if c in x.columns]],use_container_width=True,hide_index=True)

    st.markdown('### 📈 Stocks — actionable price plan')
    if _stocks.empty:st.info('No stock currently qualifies for the Daily actionable shortlist. The full Stocks page still shows the entire NSE universe.')
    else:st.dataframe(_stocks,use_container_width=True,hide_index=True)

    cMF,cFI=st.columns(2)
    with cMF:
        st.markdown('### 💰 Mutual Funds')
        if _mfs.empty:st.info('No analyzed Mutual Fund currently qualifies for INVEST/WATCH. Refresh the MF universe/history or open Mutual Funds.')
        else:st.dataframe(_mfs,use_container_width=True,hide_index=True)
    with cFI:
        st.markdown('### 🏦 Fixed Income')
        if _fixed.empty:st.info('No verified current Yield/YTM is available for a qualified Fixed-Income call. Enter/refresh exact yields in Fixed Income.')
        else:st.dataframe(_fixed,use_container_width=True,hide_index=True)

    st.markdown('### 🏦 FD / Post Office / Government Savings')
    try:
        _sopts=load_investment_options();_sr=rank_investment_options(_sopts,100000,5,'LOW')
        _sr=_sr[_sr.Category.astype(str).isin(['BANK FD','FIXED RETURN','GOVT SAVINGS'])].copy()
        _show=[c for c in ['Option','Provider/Instrument','RateOrExpectedReturn%','TenureYears','LockInYears','RateDate','DataConfidence','Fit'] if c in _sr.columns]
        if _sr.empty:st.info('No current verified deposit/small-savings rows are ready yet. Run Daily Update.')
        else:st.dataframe(_sr[_show].head(10),use_container_width=True,hide_index=True)
    except Exception as _e:st.info('Deposit / small-savings directory is not ready yet: '+str(_e))

    cMET,cIPO=st.columns(2)
    with cMET:
        st.markdown('### 🥇 Gold / Silver / Crypto')
        if _cross is None or _cross.empty:st.info('Run Daily Update to prepare cross-asset signals.')
        else:
            xm=_cross[_cross.AssetClass.astype(str).str.contains('Gold|Silver|Crypto',case=False,regex=True,na=False)].copy()
            if xm.empty:st.info('No currently cached metal/crypto recommendation is available.')
            else:
                st.dataframe(xm[[c for c in ['AssetClass','Instrument','Decision','Score','Confidence','Risk','Horizon','Reason'] if c in xm.columns]].head(8),use_container_width=True,hide_index=True)
                st.caption('Physical Gold/Silver exact ₹ buy zones depend on the latest stored physical/reference quote; open Gold / Silver for the specialist rate card.')
    with cIPO:
        st.markdown('### 🚀 IPO / SME IPO')
        if _ipos.empty:st.info('No current IPO qualifies for APPLY/WATCH from the verified cache.')
        else:st.dataframe(_ipos,use_container_width=True,hide_index=True)

    st.markdown('### 💰 I HAVE MONEY TODAY')
    with st.form('daily_money_form',clear_on_submit=False):
        q1,q2,q3,q4=st.columns(4)
        d_amt=q1.number_input('Amount ₹',min_value=1000.0,value=50000.0,step=5000.0,key='daily_money_amt')
        d_dur=q2.selectbox('Duration',['1 Month','3 Months','6 Months','1 Year','3 Years','5 Years','10+ Years'],index=2,key='daily_money_duration')
        d_days={'1 Month':30,'3 Months':91,'6 Months':182,'1 Year':365,'3 Years':1096,'5 Years':1826,'10+ Years':3652}[d_dur]
        d_risk=q3.selectbox('Risk',['AUTO','LOW','MODERATE','HIGH'],key='daily_money_risk')
        d_port=q4.checkbox('Consider my portfolio',value=True,key='daily_money_portfolio')
        d_go=st.form_submit_button('🔎 FIND BEST USE',type='primary',use_container_width=True)
    if d_go:
        drisk=auto_risk(d_days) if d_risk=='AUTO' else d_risk
        with st.spinner('Comparing the complete eligible investment universe...'):
            hist_opt=cached_history(CFG['history_sessions']);ipos_opt=cached_ipos_analyzed();opts_opt=cached_other_options();metal_opt=load_metal_state();auto_refs=automatic_reference_from_macro(load_macro())
            for mk,mv in auto_refs.items():
                if float(metal_opt.get(mk,{}).get('quote',0) or 0)<=0:metal_opt.setdefault(mk,{})['quote']=float(mv.get('rate',0) or 0);metal_opt[mk]['quote_source']='AUTO_REFERENCE'
            exposure_opt={}
            if d_port:
                try:
                    lots=read_portfolio()
                    if lots is not None and not lots.empty:
                        lots_en=enrich_current_prices(lots,radar,mf,metal_opt,{},bonds);exposure_opt=portfolio_exposure(aggregate_holdings(lots_en))
                except Exception:exposure_opt={}
            cands=collect_candidates(radar,mf,bonds,ipos_opt,opts_opt,hist_opt,CFG,metal_opt,load_crypto,d_days,False)
            elig,rej=score_candidates(cands,d_amt,d_days,drisk,exposure_opt,d_port,[])
            pres=build_plan(elig,d_amt,d_days,drisk,5.0,False,False,market_context=market_context())
            st.session_state['daily_money_result']={'eligible':elig,'rejected':rej,'planres':pres,'amount':d_amt,'days':d_days,'risk':drisk}
    _dm=st.session_state.get('daily_money_result')
    if _dm:
        pl=_dm.get('planres',{}).get('allocations',pd.DataFrame());sm=_dm.get('planres',{}).get('summary',{})
        if pl is None or pl.empty:st.warning('No reliable allocation plan can be produced from the currently verified data. Keeping money uncommitted is safer than forcing a recommendation.')
        else:
            st.success(f"{sm.get('PlanAction','PLAN')} • Risk {_dm.get('risk')} • Review {sm.get('ReviewDate','—')}")
            pv=pl[[c for c in ['AssetClass','Instrument','Decision','AllocationRs','AllocationPct','Timing','Risk','Confidence','DownsidePct','BasePct','UpsidePct','ProbabilityPositivePct'] if c in pl.columns]].copy()
            pv=pv.rename(columns={'AllocationRs':'Allocation ₹','AllocationPct':'Allocation %','DownsidePct':'Downside %','BasePct':'Base %','UpsidePct':'Upside %','ProbabilityPositivePct':'Probability Positive %'})
            st.dataframe(pv,use_container_width=True,hide_index=True)
            z1,z2,z3,z4=st.columns(4)
            z1.metric('Downside scenario',f"₹{sm.get('DownsideValueRs',np.nan):,.0f}" if pd.notna(sm.get('DownsideValueRs',np.nan)) else '—')
            z2.metric('Base scenario',f"₹{sm.get('BaseValueRs',np.nan):,.0f}" if pd.notna(sm.get('BaseValueRs',np.nan)) else '—')
            z3.metric('Upside scenario',f"₹{sm.get('UpsideValueRs',np.nan):,.0f}" if pd.notna(sm.get('UpsideValueRs',np.nan)) else '—')
            z4.metric('Base gain',f"₹{sm.get('BaseGainRs',np.nan):,.0f}" if pd.notna(sm.get('BaseGainRs',np.nan)) else '—')
            st.caption('Use Best Use of My Money for the full why / why-not / target / tax / inflation / tracked-plan workflow.')

    st.markdown('### 💼 My holdings — action required')
    try:
        pf=read_portfolio();ph=portfolio_health(pf)
        warns=ph.get('warnings',pd.DataFrame())
        if pf is None or pf.empty:st.caption('No portfolio has been saved yet.')
        elif warns is None or warns.empty:st.success('✅ No portfolio concentration/risk warning requires action from the current saved holdings.')
        else:st.dataframe(warns.head(10),use_container_width=True,hide_index=True)
    except Exception as e:st.warning('Portfolio summary unavailable: '+str(e))

    st.markdown('### ⚠ Events that can change a recommendation')
    try:
        ev=cached_events();top_syms=set(_stocks.Instrument.astype(str)) if not _stocks.empty else set()
        if ev is None or ev.empty:st.caption('No cached event data. Run Daily Update.')
        else:
            e=ev[ev.Severity.astype(str).isin(['BLOCK','REVIEW'])].copy() if 'Severity' in ev.columns else pd.DataFrame()
            if top_syms and not e.empty:e=e[e.Symbol.astype(str).str.upper().isin({x.upper() for x in top_syms})]
            if e.empty:st.success('✅ No BLOCK/REVIEW corporate event is currently attached to today’s shortlisted stocks in the cached event data.')
            else:st.dataframe(e[[c for c in ['Symbol','Company','EventType','Subject','EventDate','Severity','SystemAction'] if c in e.columns]].head(20),use_container_width=True,hide_index=True)
    except Exception as e:st.caption('Event summary unavailable: '+str(e))

if active_page=='🏠 Home':
    try:alerts_home=load_alerts()
    except Exception:alerts_home=pd.DataFrame()
    try:_dh,_health_score=cached_data_health()
    except Exception:_dh,_health_score=pd.DataFrame(),0.0
    try:_pf_saved=read_portfolio();_pf_health=portfolio_health(_pf_saved)
    except Exception:_pf_health={'summary':{},'allocation':pd.DataFrame(),'warnings':pd.DataFrame(),'profiles':pd.DataFrame()}
    try:_ev_all=cached_events()
    except Exception:_ev_all=pd.DataFrame()
    try:_ca=cached_cross_asset()
    except Exception:_ca=pd.DataFrame()
    _daily=build_daily_actions(radar,alerts_home,_ev_all,_pf_health,_dh,_ca)
    with st.expander('🏠 DAILY DECISION CENTER — today at a glance',expanded=True):
        h1,h2,h3,h4=st.columns(4);h1.metric('Today',daily_headline(_daily));h2.metric('Data health',f'{_health_score:.0f}%');phs=_pf_health.get('summary',{});h3.metric('Portfolio health',str(phs.get('Health','NO PORTFOLIO')));urgent=int((_daily.Priority<=2).sum()) if not _daily.empty else 0;h4.metric('Actions needing review',urgent)
        st.dataframe(_daily[[c for c in ['Priority','Type','Item','Action','Why'] if c in _daily.columns]].head(10),use_container_width=True,hide_index=True)
        if not _dh.empty:
            bad=_dh[_dh.Status.isin(['MISSING','OLD','STALE'])]
            if not bad.empty:st.caption('Data warning: '+', '.join((bad.Data.astype(str)+' ['+bad.Status.astype(str)+']').head(5).tolist()))
        st.caption('This summary runs only on Home. Other pages stay focused and fast.')

# Premium navigation shows one focused primary page at a time.
if active_page=='🏠 Home':
    st.markdown('<div class="section-title">Start here</div><div class="section-sub">Use the optimizer when you have money to invest, or go directly to a market/product when you already know the segment.</div>',unsafe_allow_html=True)
    q1,q2,q3=st.columns(3)
    with q1:
        st.markdown('<div class="quick-card"><div class="qtitle">💰 Best Use of My Money</div><div class="qtext">Enter amount + duration + risk. The Radar compares suitable asset classes, keeps reserve when appropriate and explains the plan.</div></div>',unsafe_allow_html=True)
    with q2:
        st.markdown('<div class="quick-card"><div class="qtitle">🎯 Go by Segment</div><div class="qtext">Already want Gold, Mutual Funds, Stocks, Bonds, IPO or Crypto? Drill down to category and exact product with reasons.</div></div>',unsafe_allow_html=True)
    with q3:
        st.markdown('<div class="quick-card"><div class="qtitle">💼 Review My Portfolio</div><div class="qtext">Maintain purchase lots, import Excel/CSV, review allocation and P&L, and connect new decisions to what you already own.</div></div>',unsafe_allow_html=True)
    st.info('Choose **Plan & Invest**, **Markets**, **Portfolio**, **Research**, or **System** from the left navigation. All existing functions remain available.')

# ----------------- Best Use of My Money -----------------
if active_page=='💰 Best Use of My Money':
    st.caption('Enter only the money and duration. The system compares suitable investments, respects your existing portfolio if selected, keeps reserve when needed, and never forces a weak recommendation.')

    q1,q2,q3,q4=st.columns(4)
    opt_amount=q1.number_input('Amount ₹',min_value=1000.0,value=50000.0,step=5000.0,key='opt_amount')
    opt_mode=q2.selectbox('Investment type',['ONE-TIME','MONTHLY'],key='opt_mode')
    opt_duration=q3.selectbox('Duration',['7 Days','15 Days','1 Month','45 Days','3 Months','6 Months','9 Months','1 Year','2 Years','3 Years','5 Years','10+ Years','Exact Required Date'],index=5,key='opt_duration')
    opt_risk_choice=q4.selectbox('Risk',['AUTO','LOW','MODERATE','HIGH'],key='opt_risk')
    opt_exact=None
    if opt_duration=='Exact Required Date':
        opt_exact=st.date_input('I need this money back by',value=(pd.Timestamp.today()+pd.Timedelta(days=182)).date(),min_value=(pd.Timestamp.today()+pd.Timedelta(days=1)).date(),key='opt_exact_date')
    opt_days=horizon_days_from_choice(opt_duration,opt_exact)

    with st.expander('More Options — optional'):
        aa,bb,cc=st.columns(3)
        opt_liquidity=aa.selectbox('Liquidity need',['Normal','High — may need money anytime','Low — can keep invested'],key='opt_liquidity')
        opt_essential=bb.checkbox('This is essential money / capital protection is important',value=False,key='opt_essential')
        opt_existing=cc.checkbox('Consider my existing portfolio before allocating',value=True,key='opt_existing')
        dd,ee,ff=st.columns(3)
        opt_reserve=dd.number_input('Minimum cash reserve %',min_value=0.0,max_value=80.0,value=5.0,step=5.0,key='opt_reserve')
        opt_tax=ee.number_input('Effective tax on gains assumption %',min_value=0.0,max_value=60.0,value=0.0,step=.5,key='opt_tax')
        opt_inflation=ff.number_input('Inflation assumption %',min_value=0.0,max_value=20.0,value=5.0,step=.25,key='opt_inflation')
        opt_exclude=st.multiselect('Exclude investment classes', ['Stocks','Mutual Funds','Fixed Income','Physical Gold','Physical Silver','Crypto','IPO','Other Investments'],key='opt_exclude')
        t1,t2=st.columns(2)
        opt_target_on=t1.checkbox('I have a target return',value=False,key='opt_target_on')
        opt_target_pct=t2.number_input('Target return % for this duration',min_value=-50.0,max_value=500.0,value=10.0,step=1.0,key='opt_target_pct',disabled=not opt_target_on)

    resolved_risk=auto_risk(opt_days,opt_liquidity,opt_essential,opt_mode) if opt_risk_choice=='AUTO' else opt_risk_choice
    st.info(f'**Resolved duration:** {human_horizon(opt_days)} • **Risk used:** {resolved_risk}'+(' (AUTO)' if opt_risk_choice=='AUTO' else ''))

    if st.button('🔎 FIND BEST USE OF MY MONEY',type='primary',use_container_width=True,key='run_money_optimizer'):
        st.session_state['last_optimizer_request']={
            'amount':opt_amount,'mode':opt_mode,'days':opt_days,'risk':resolved_risk,'liquidity':opt_liquidity,
            'essential':opt_essential,'existing':opt_existing,'reserve':opt_reserve,'tax':opt_tax,'inflation':opt_inflation,
            'exclude':opt_exclude,'target_on':opt_target_on,'target_pct':opt_target_pct
        }
        st.session_state['optimizer_needs_run']=True

    req=st.session_state.get('last_optimizer_request')
    if req:
        if st.session_state.get('optimizer_needs_run',False) or 'optimizer_result_cache' not in st.session_state:
            with st.spinner('Comparing suitable investments once...'):
                hist_opt=cached_history(CFG['history_sessions'])
                ipos_opt=cached_ipos_analyzed();opts_opt=cached_other_options();metal_opt=load_metal_state();auto_metal_refs=automatic_reference_from_macro(load_macro())
                for mk,mv in auto_metal_refs.items():
                    if float(metal_opt.get(mk,{}).get('quote',0) or 0)<=0:metal_opt.setdefault(mk,{})['quote']=float(mv.get('rate',0) or 0);metal_opt[mk]['quote_source']='AUTO_REFERENCE'
                lots_opt=read_portfolio();exposure_opt={}
                if req.get('existing') and lots_opt is not None and not lots_opt.empty:
                    try:
                        cryptop={}
                        for cs in CFG.get('crypto_symbols',[]):
                            cg=load_crypto(cs)
                            if cg is not None and not cg.empty:cryptop[cs]=float(cg.Close.iloc[-1])
                        lots_en=enrich_current_prices(lots_opt,radar,mf,metal_opt,cryptop,bonds);exposure_opt=portfolio_exposure(aggregate_holdings(lots_en))
                    except Exception:exposure_opt={}
                cands=collect_candidates(radar,mf,bonds,ipos_opt,opts_opt,hist_opt,CFG,metal_opt,load_crypto,req['days'],req['mode']=='MONTHLY');elig,rej=score_candidates(cands,req['amount'],req['days'],req['risk'],exposure_opt,req.get('existing',True),req.get('exclude',[]));planres=build_plan(elig,req['amount'],req['days'],req['risk'],req.get('reserve'),req.get('essential',False),req['mode']=='MONTHLY',market_context=market_context())
                st.session_state['optimizer_result_cache']={'request':dict(req),'eligible':elig,'rejected':rej,'planres':planres};st.session_state['optimizer_needs_run']=False
        _oc=st.session_state.get('optimizer_result_cache',{});req=_oc.get('request',req);elig=_oc.get('eligible',pd.DataFrame());rej=_oc.get('rejected',pd.DataFrame());planres=_oc.get('planres',{});plan=planres.get('allocations',pd.DataFrame());summ=planres.get('summary',{})
        if plan.empty:
            st.warning('No reliable investment plan can be produced from the current validated data and your constraints. Keeping the money uncommitted is safer until data/fit improves.')
            if not rej.empty:st.dataframe(rej[['AssetClass','Instrument','RejectReason']].head(15),use_container_width=True,hide_index=True)
        else:
            st.markdown(f"## {summ.get('PlanAction','PLAN')}")
            a,b,c,d,e=st.columns(5)
            a.metric('Available / Monthly ₹',f"₹{summ.get('AmountRs',0):,.0f}")
            b.metric('Duration',summ.get('Horizon',''))
            c.metric('Risk',summ.get('Risk',''))
            d.metric('Reserve',f"₹{summ.get('ReserveRs',0):,.0f}")
            e.metric('Review',summ.get('ReviewDate',''))
            show=plan[['AssetClass','Instrument','Decision','AllocationRs','AllocationPct','Timing','Risk','Confidence','DownsidePct','BasePct','UpsidePct','ProbabilityPositivePct','OptimizerScore']].copy()
            show=show.rename(columns={'AllocationRs':'Allocation ₹','AllocationPct':'Allocation %','DownsidePct':'Downside %','BasePct':'Base %','UpsidePct':'Upside %','ProbabilityPositivePct':'Probability Positive %','OptimizerScore':'Fit Score'})
            st.markdown('### Recommended Plan')
            st.dataframe(show,use_container_width=True,hide_index=True)
            s1,s2,s3,s4=st.columns(4)
            s1.metric('Downside scenario',f"₹{summ.get('DownsideValueRs',np.nan):,.0f}" if pd.notna(summ.get('DownsideValueRs',np.nan)) else 'N/A')
            s2.metric('Base scenario',f"₹{summ.get('BaseValueRs',np.nan):,.0f}" if pd.notna(summ.get('BaseValueRs',np.nan)) else 'N/A')
            s3.metric('Upside scenario',f"₹{summ.get('UpsideValueRs',np.nan):,.0f}" if pd.notna(summ.get('UpsideValueRs',np.nan)) else 'N/A')
            s4.metric('Base gain',f"₹{summ.get('BaseGainRs',np.nan):,.0f}" if pd.notna(summ.get('BaseGainRs',np.nan)) else 'N/A')
            if pd.notna(summ.get('BaseValueRs',np.nan)):
                pret=max(0,summ['BaseValueRs']-req['amount']); tax=pret*req.get('tax',0)/100;post=summ['BaseValueRs']-tax;years=max(req['days']/365.25,1/365.25);real=post/((1+req.get('inflation',0)/100)**years)
                st.caption(f"Planning view: estimated post-tax base value ₹{post:,.0f}; inflation-adjusted value ₹{real:,.0f}. Tax/inflation are your assumptions, not legal/guaranteed calculations.")
            if req.get('target_on'):
                tr=required_return_for_target(req['amount'],target_pct=req.get('target_pct'),horizon_days=req['days'])
                if tr:
                    st.info(f"Your target requires about **{tr['TargetPct']:.1f}%** over this period / **{tr['RequiredAnnualizedPct']:.1f}% annualized equivalent**. Compare this with the scenario range above; the app will not force extra risk just to chase the target.")
            st.markdown('### Why this plan?')
            for z in planres.get('why',[]):st.write('• '+z)
            why_not=build_why_not(rej,elig,plan)
            st.markdown('### Why not the other options?')
            if why_not.empty:st.caption('No materially different rejected option is available from the current data.')
            else:st.dataframe(why_not,use_container_width=True,hide_index=True)
            st.markdown('### Go Deeper into any recommended leg')
            detail_rows=plan[plan.AssetClass.ne('Reserve')]
            if not detail_rows.empty:
                labels=[f"{r.Instrument} — {r.AssetClass}" for _,r in detail_rows.iterrows()]
                chosen=st.selectbox('Select recommendation to explain',labels,key='optimizer_deeper')
                rr=detail_rows.iloc[labels.index(chosen)]
                alt_note='Alternatives were rejected or ranked lower because of duration, risk, timing, data quality, concentration or expected risk-adjusted outcome.'
                explain=universal_explanation(rr,float(rr.AllocationRs),req['days'],req['risk'],alt_note)
                with st.expander('WHY THIS? — full 13-question explanation',expanded=True):
                    for q,ans in explain.items():st.markdown(f'**{q}**  \n{ans}')
            ctrack1,ctrack2=st.columns(2)
            if ctrack1.button('📌 TRACK THIS PLAN',use_container_width=True,key='track_optimizer_plan'):
                pid=save_plan(summ,plan,req['mode'])
                st.success(f'Plan saved locally as {pid}. Record actual purchases later in My Portfolio.')
            if ctrack2.button('🧹 Clear this optimizer result',use_container_width=True,key='clear_optimizer'):
                st.session_state.pop('last_optimizer_request',None);st.session_state.pop('optimizer_result_cache',None);st.session_state.pop('optimizer_needs_run',None);cloud_rerun()
            saved_plans=load_plans()
            if not saved_plans.empty:
                with st.expander('Tracked allocation plans'):
                    cols=[c for c in ['PlanID','CreatedAt','Mode','AmountRs','Horizon','Risk','PlanAction','ReserveRs','BaseValueRs','ReviewDate','Status'] if c in saved_plans.columns]
                    st.dataframe(saved_plans[cols].sort_values('CreatedAt',ascending=False),use_container_width=True,hide_index=True)

# ----------------- Go by Segment -----------------
if active_page=='🎯 Go by Segment':
    st.caption('Choose the investment segment you already want. The app ranks the category first, then the exact product, then explains amount, timing, duration, scenarios, why, why-not and what changes the call.')
    s1,s2,s3,s4=st.columns(4)
    seg=s1.selectbox('Segment',['Gold','Silver','Stocks','Mutual Funds','Fixed Income / Bonds','IPO','Crypto','Other Investments'],key='seg_name')
    seg_amount=s2.number_input('Amount ₹',min_value=1000.0,value=50000.0,step=5000.0,key='seg_amount')
    seg_dur=s3.selectbox('Duration',['7 Days','15 Days','1 Month','45 Days','3 Months','6 Months','9 Months','1 Year','2 Years','3 Years','5 Years','10+ Years','Exact Required Date'],index=7,key='seg_duration')
    seg_risk_choice=s4.selectbox('Risk',['AUTO','LOW','MODERATE','HIGH'],key='seg_risk')
    seg_exact=None
    if seg_dur=='Exact Required Date':seg_exact=st.date_input('Required money-back date',value=(pd.Timestamp.today()+pd.Timedelta(days=365)).date(),min_value=(pd.Timestamp.today()+pd.Timedelta(days=1)).date(),key='seg_exact')
    seg_days=horizon_days_from_choice(seg_dur,seg_exact);seg_risk=auto_risk(seg_days) if seg_risk_choice=='AUTO' else seg_risk_choice
    seg_mode=st.radio('Contribution',['ONE-TIME','MONTHLY'],horizontal=True,key='seg_mode')
    if st.button('🎯 FIND BEST IN THIS SEGMENT',type='primary',use_container_width=True,key='run_segment'):
        if seg=='Mutual Funds':
            with st.spinner('Preparing exact Mutual Fund choices for your duration and risk...'):
                prep=refresh_mf_for_horizon(seg_days,seg_risk,max_funds=CFG.get('mf_auto_segment_candidates',30))
            if prep.get('message'):st.caption(prep.get('message'))
        st.session_state['last_segment_request']={'segment':seg,'amount':seg_amount,'days':seg_days,'risk':seg_risk,'mode':seg_mode}
        st.session_state['segment_needs_run']=True
    srq=st.session_state.get('last_segment_request')
    if srq:
        if st.session_state.get('segment_needs_run',False) or 'segment_result_cache' not in st.session_state:
            with st.spinner('Ranking this segment once...'):
                hist_seg=cached_history(CFG['history_sessions']);ipos_seg=cached_ipos_analyzed();opts_seg=cached_other_options();metal_seg=load_metal_state();auto_seg_refs=automatic_reference_from_macro(load_macro())
                for mk,mv in auto_seg_refs.items():
                    if float(metal_seg.get(mk,{}).get('quote',0) or 0)<=0:metal_seg.setdefault(mk,{})['quote']=float(mv.get('rate',0) or 0);metal_seg[mk]['quote_source']='AUTO_REFERENCE'
                mf_seg=cached_mf_analysis()[0] if srq['segment']=='Mutual Funds' else mf;seg_e,seg_r=segment_candidates(srq['segment'],srq['amount'],srq['days'],srq['risk'],radar,mf_seg,bonds,ipos_seg,opts_seg,hist_seg,CFG,metal_seg,load_crypto,seed_data(),srq['mode']=='MONTHLY')
                st.session_state['segment_result_cache']={'request':dict(srq),'eligible':seg_e,'rejected':seg_r};st.session_state['segment_needs_run']=False
        _sc=st.session_state.get('segment_result_cache',{});srq=_sc.get('request',srq);seg_e=_sc.get('eligible',pd.DataFrame());seg_r=_sc.get('rejected',pd.DataFrame())
        if seg_e.empty:
            st.warning('No reliable product in this segment currently passes your amount, duration, risk and data requirements.')
            if not seg_r.empty:st.dataframe(seg_r[['Category','Instrument','RejectReason']].head(20),use_container_width=True,hide_index=True)
        else:
            st.success(f"Recommended first choice: **{seg_e.iloc[0].Instrument}** • Fit {seg_e.iloc[0].OptimizerScore:.0f}/100")
            cats=seg_e.groupby('Category',dropna=False).agg(BestFit=('OptimizerScore','max'),BestProduct=('Instrument','first'),Products=('Instrument','count')).reset_index().sort_values('BestFit',ascending=False)
            st.markdown('### Level 1 — Best category / product form')
            st.dataframe(cats,use_container_width=True,hide_index=True)
            cat_options=cats.Category.astype(str).tolist();chosen_cat=st.selectbox('Category / product form',cat_options,index=0,key='seg_cat')
            products=seg_e[seg_e.Category.astype(str).eq(chosen_cat)].sort_values('OptimizerScore',ascending=False)
            st.markdown('### Level 2 — Exact products')
            pshow=products[['Instrument','Decision','Timing','Risk','Confidence','OptimizerScore','DownsidePct','BasePct','UpsidePct','ProbabilityPositivePct','Reason']].copy()
            pshow=pshow.rename(columns={'OptimizerScore':'Fit Score','DownsidePct':'Downside %','BasePct':'Base %','UpsidePct':'Upside %','ProbabilityPositivePct':'Probability Positive %'})
            st.dataframe(pshow,use_container_width=True,hide_index=True)
            names=products.Instrument.astype(str).tolist();chosen_product=st.selectbox('Exact product',names,index=0,key='seg_product');r=products[products.Instrument.astype(str).eq(chosen_product)].iloc[0]
            single_pct=25 if srq['segment'] in ('Stocks','Crypto','IPO') else (50 if srq['segment']=='Mutual Funds' else 100)
            suggested=max(1000,round(srq['amount']*single_pct/100/500)*500);suggested=min(srq['amount'],suggested)
            st.markdown('### Level 3 — Exact action')
            a,b,c,d=st.columns(4);a.metric('Suggested amount',f'₹{suggested:,.0f}');b.metric('Timing',r.Timing);c.metric('Risk',r.Risk);d.metric('Confidence',r.Confidence)
            why_alt=products[products.Instrument.astype(str).ne(chosen_product)].head(3)
            alt_note='; '.join([f"{x.Instrument}: lower fit ({x.OptimizerScore:.0f}/100) or less suitable timing" for _,x in why_alt.iterrows()]) or 'No close same-category alternative currently ranks better.'
            exp=universal_explanation(r,suggested,srq['days'],srq['risk'],alt_note)
            st.markdown('### Full Explanation — same standard for every segment')
            for q,ans in exp.items():st.markdown(f'**{q}**  \n{ans}')
            if not seg_r.empty:
                with st.expander('Rejected products / why not'):
                    st.dataframe(seg_r[['Category','Instrument','RejectReason']].head(20),use_container_width=True,hide_index=True)
            st.info('Use the dedicated asset tab for its full specialist card (stock levels, physical metal buy zones, MF statistics, bond YTM, IPO details, crypto levels, etc.). This segment flow is the simple path to the exact product and explanation.')

# ----------------- Action Board -----------------

if active_page=='🔥 ACTION BOARD':
    st.caption('Strong Buy is deliberately strict. If none qualify, the app says so instead of forcing a pick.')
    sb=radar[(radar.Signal=='STRONG BUY') & (radar.get('Eligibility','ELIGIBLE')=='ELIGIBLE')].copy()
    if sb.empty:st.warning('🔥 NO STRONG BUY TODAY')
    else:
        st.success(f'🔥 {len(sb)} STRONG BUY setup(s) passed every strict gate.')
        st.dataframe(sb[['Category','Symbol','Company','Signal','EntryStatus','Overall','Current','EntryLow','EntryHigh','Target1','Potential1%','Target2','Potential2%','StopLoss','RR','RiskLevel','Confidence','BacktestSample','BacktestWinRate%','WalkForwardSample','WalkForwardWinRate%','MarketIntelligenceScore','MarketContext','InstitutionalBias','DerivativesBias','BreadthBias','DeliveryPct','SurveillanceRisk','NewsRisk']],use_container_width=True,hide_index=True)
    for sig,label in [('BUY','🟢 BUY'),('BUY ON PULLBACK','🟡 BUY ON PULLBACK'),('WATCH','👀 WATCH')]:
        x=radar[radar.Signal==sig].sort_values('Overall',ascending=False).head(12)
        if not x.empty:
            st.markdown(f'### {label}')
            st.dataframe(x[['Category','Symbol','Company','Signal','EntryStatus','Overall','Current','EntryLow','EntryHigh','Target1','Potential1%','StopLoss','RR','Confidence']],use_container_width=True,hide_index=True)

    st.markdown('### 🌐 Best Opportunities Across Asset Classes')
    cross=load_cross_asset()
    if cross.empty:
        st.info('This snapshot will populate after the next DAILY UPDATE / REBUILD DASHBOARD.')
    else:
        st.dataframe(cross.head(15),use_container_width=True,hide_index=True)
        st.caption('This compares model scores across stocks, funds, fixed income, physical metals and cached crypto. Score scales are comparable for ranking assistance, not a guarantee that one asset class will outperform another.')

    ipo_now=analyze_ipos(load_ipos())
    if not ipo_now.empty:
        current_ipo=ipo_now[ipo_now.Decision.isin(['STRONG APPLY','APPLY'])].head(5)
        if not current_ipo.empty:
            st.markdown('### 🚀 IPO / New Issue Opportunities')
            st.dataframe(current_ipo[['Company','Board','Status','ListingScore','LongTermScore','Overall','Decision','Risk','Confidence']],use_container_width=True,hide_index=True)

if active_page=='🌍 Market Outlook':
    macro=load_macro();mctx=india_context(macro)
    if not macro.empty:
        mc1,mc2=st.columns(2)
        mc1.metric('Macro Context',mctx.get('Context','UNAVAILABLE'))
        mc2.metric('Macro Score',f"{mctx.get('Score','—')}/100" if pd.notna(mctx.get('Score',np.nan)) else '—')
        st.dataframe(macro,use_container_width=True,hide_index=True)
        if mctx.get('Reasons'):st.caption('Macro reasons: '+' • '.join(mctx['Reasons']))
        st.caption('Optional context from Nifty/Bank Nifty, USD/INR, crude and major global markets. If the public macro feed is unavailable, the core NSE radar continues normally.')
    _inst=institutional_summary();_news=load_market_news()
    if _inst.get('Bias')!='UNAVAILABLE':
        a,b,c,d=st.columns(4);a.metric('Institutional bias',_inst.get('Bias'));b.metric('FII 5D',f"₹{_inst.get('FII5D₹Cr',0):+,.0f} Cr" if pd.notna(_inst.get('FII5D₹Cr',np.nan)) else '—');c.metric('DII 5D',f"₹{_inst.get('DII5D₹Cr',0):+,.0f} Cr" if pd.notna(_inst.get('DII5D₹Cr',np.nan)) else '—');d.metric('Institutional score',f"{_inst.get('Score',0):.0f}/100" if pd.notna(_inst.get('Score',np.nan)) else '—')
    if _news is not None and not _news.empty:
        with st.expander('Latest public market-news context',expanded=False):st.dataframe(_news[[c for c in ['Published','Title','Source','Risk','Query'] if c in _news.columns]].head(20),use_container_width=True,hide_index=True)
    st.warning('Probability ranges from historically similar market states — not guaranteed forecasts.')
    if mout.empty:st.info('Not enough history for market outlook.')
    else:
        st.dataframe(mout[[c for c in ['Horizon','Bias','ProbabilityPositive%','BaseProbabilityPositive%','ContextAdjustmentPP','MedianReturn%','RangeLow%','RangeHigh%','Sample','Confidence','ContextRegime','ForecastMethod'] if c in mout.columns]],use_container_width=True,hide_index=True)
        for _,r in mout.iterrows():
            st.markdown(f"**{r.Horizon}: {r.Bias}** • Positive {r['ProbabilityPositive%']}% • Median {r['MedianReturn%']:+.2f}% • Range {r['RangeLow%']:+.2f}% to {r['RangeHigh%']:+.2f}% • {r.Confidence}")
            if 'ContextAdjustmentPP' in r.index: st.caption(f"Market-intelligence adjustment: {r.get('ContextAdjustmentPP',0):+.1f} pp • {r.get('ContextRegime','MIXED')} • probability-based scenario, not a guaranteed target.")
    if not proxy.empty and 'Date' in proxy:st.line_chart(proxy.tail(160).set_index('Date')[['Proxy','EMA21','EMA50']])

if active_page=='🏦 Market Intelligence':
    st.caption('One connected evidence screen. Institutional/derivatives/breadth/macro data modifies regime and confidence; official exchange/company filings remain the stronger company-specific safety gate.')
    _flows=load_fii_dii();_inst=institutional_summary(_flows);_der=derivatives_summary();_br=intel_breadth_summary();_mctx=market_context(cached_history(CFG['history_sessions']) if _core_ready else None);_news=load_market_news();_macro=load_macro()
    a,b,c,d,e,f=st.columns(6)
    a.metric('Market Intel',_mctx.get('Regime','UNAVAILABLE'))
    b.metric('Intel Score',f"{_mctx.get('Score',0):.0f}/100")
    c.metric('FII/FPI Latest',f"₹{_inst.get('FIINet₹Cr',0):+,.0f} Cr" if pd.notna(_inst.get('FIINet₹Cr',np.nan)) else '—')
    d.metric('DII Latest',f"₹{_inst.get('DIINet₹Cr',0):+,.0f} Cr" if pd.notna(_inst.get('DIINet₹Cr',np.nan)) else '—')
    e.metric('FII 20D',f"₹{_inst.get('FII20D₹Cr',0):+,.0f} Cr" if pd.notna(_inst.get('FII20D₹Cr',np.nan)) else '—')
    f.metric('FII 60D',f"₹{_inst.get('FII60D₹Cr',0):+,.0f} Cr" if pd.notna(_inst.get('FII60D₹Cr',np.nan)) else '—')
    st.info(context_explanation(_mctx))
    tabs=st.tabs(['FII / DII','Derivatives','Breadth','Delivery & Risk','Sector / SIP','Macro / Valuation','News'])
    with tabs[0]:
        st.write(f"**FII regime:** {_inst.get('FIIRegime','UNAVAILABLE')} • **DII regime:** {_inst.get('DIIRegime','UNAVAILABLE')} • **Combined:** {_inst.get('Bias','UNAVAILABLE')}")
        cols=['Date','FII Buy₹Cr','FII Sell₹Cr','FII Net₹Cr','DII Buy₹Cr','DII Sell₹Cr','DII Net₹Cr','Status','Source']
        st.dataframe(_flows[[x for x in cols if x in _flows.columns]].sort_values('Date',ascending=False).head(120) if not _flows.empty else _flows,use_container_width=True,hide_index=True)
    with tabs[1]:
        x=load_derivatives_history();st.write(f"**Derivatives view:** {_der.get('Bias','UNAVAILABLE')} • Score {_der.get('Score','—')}")
        st.write(_der.get('Explanation','Participant-wise derivatives data is supporting evidence, not a standalone BUY trigger.'))
        if x.empty:st.info('No derivatives cache yet. Run DAILY UPDATE; source fallback/status will remain visible if NSE archive format changes.')
        else:st.dataframe(x.sort_values('Date',ascending=False).head(90),use_container_width=True,hide_index=True)
    with tabs[2]:
        st.write(f"**Breadth view:** {_br.get('Bias','UNAVAILABLE')} • Score {_br.get('Score','—')}")
        bb=load_breadth_history();
        if bb.empty:st.info('Breadth history will build automatically from stored NSE EOD history.')
        else:st.dataframe(bb.sort_values('Date',ascending=False).head(120),use_container_width=True,hide_index=True)
    with tabs[3]:
        dl=load_delivery();sv=load_surveillance();bulk=load_bulk_deals();block=load_block_deals();short=load_short_selling()
        st.markdown('#### Security-wise delivery')
        if not dl.empty: st.dataframe(dl.head(300),use_container_width=True,hide_index=True)
        else: st.info('Delivery data unavailable/cached source not ready.')
        st.markdown('#### Surveillance / restrictions')
        if not sv.empty: st.dataframe(sv.head(300),use_container_width=True,hide_index=True)
        else: st.info('No surveillance cache currently available.')
        c1,c2,c3=st.columns(3);c1.metric('Bulk-deal rows',len(bulk));c2.metric('Block-deal rows',len(block));c3.metric('Short-selling rows',len(short))
        with st.expander('Deals / short-selling details'):
            if not bulk.empty:st.markdown('**Bulk deals**');st.dataframe(bulk.head(250),use_container_width=True,hide_index=True)
            if not block.empty:st.markdown('**Block deals**');st.dataframe(block.head(250),use_container_width=True,hide_index=True)
            if not short.empty:st.markdown('**Short selling**');st.dataframe(short.head(250),use_container_width=True,hide_index=True)
    with tabs[4]:
        fs=load_fpi_sector();sip=load_amfi_sip();st.markdown('#### FPI sector allocation / flow reference')
        if not fs.empty: st.dataframe(fs.head(300),use_container_width=True,hide_index=True)
        else: st.info('Sector-wise FPI table not currently available; Radar keeps status rather than inventing it.')
        st.markdown('#### AMFI SIP / domestic-flow reference')
        if not sip.empty: st.dataframe(sip.head(120),use_container_width=True,hide_index=True)
        else: st.info('AMFI SIP cache not currently available.')
    with tabs[5]:
        iv=load_index_valuation();st.markdown('#### Macro / global context')
        if not _macro.empty: st.dataframe(_macro,use_container_width=True,hide_index=True)
        else: st.info('Macro cache unavailable.')
        st.markdown('#### Index valuation')
        if not iv.empty: st.dataframe(iv.head(200),use_container_width=True,hide_index=True)
        else: st.info('Index valuation cache unavailable.')
    with tabs[6]:
        if _news.empty:st.info('No public-news cache yet. Run DAILY UPDATE.')
        else:
            risk=st.multiselect('News filter',['RISK','NEUTRAL','POSITIVE'],default=['RISK','NEUTRAL','POSITIVE'],key='intel_news_filter')
            _nv=_news[_news.Risk.astype(str).isin(risk)] if 'Risk' in _news.columns else _news
            st.dataframe(_nv[[c for c in ['Published','Title','Source','Risk','Query'] if c in _nv.columns]].head(100),use_container_width=True,hide_index=True)
    st.caption('Interpretation rule: company evidence is primary; sector evidence is confirmation; institutional/derivatives/breadth/macro is a regime/confidence modifier; critical event/surveillance/data-quality failures are safety gates.')

if active_page=='⚡ Stocks':
    sub=st.tabs(['Today\'s Ranking — ALL NSE','Qualified Picks','Full Stock Card'])
    with sub[0]:
        st.subheader('ALL NSE EQ Stock Ranking')
        st.caption('Every NSE EQ symbol found in your downloaded bhavcopy is shown here. Recommendation eligibility is separate from visibility.')
        cat=st.radio('Ranking horizon',['SWING','SHORT','LONG'],horizontal=True,key='all_rank_cat')
        x=radar[radar.Category==cat].copy()
        total=int(x.Symbol.nunique()); eligible=int(x.loc[x.Eligibility.eq('ELIGIBLE'),'Symbol'].nunique()) if 'Eligibility' in x else total
        m1,m2,m3=st.columns(3);m1.metric('Total NSE stocks in local data',f'{total:,}');m2.metric('Eligible for recommendations',f'{eligible:,}');m3.metric('Visible but filtered',f'{max(0,total-eligible):,}')
        q=st.text_input('Search symbol / company',placeholder='Example: RELIANCE, TCS, INFY',key='all_rank_search').strip().upper()
        if q:
            x=x[x.Symbol.astype(str).str.upper().str.contains(q,na=False)|x.Company.astype(str).str.upper().str.contains(q,na=False)]
        view=st.selectbox('Show',['ALL NSE STOCKS','ELIGIBLE ONLY','NOT ELIGIBLE / INSUFFICIENT HISTORY'],key='all_rank_view')
        if view=='ELIGIBLE ONLY':x=x[x.Eligibility=='ELIGIBLE']
        elif view=='NOT ELIGIBLE / INSUFFICIENT HISTORY':x=x[x.Eligibility!='ELIGIBLE']
        rank={'STRONG BUY':0,'BUY':1,'BUY ON PULLBACK':2,'WATCH':3,'AVOID':4}
        x['_rank']=x.Signal.map(rank).fillna(9)
        x=x.sort_values(['Eligibility','_rank','Overall'],ascending=[True,True,False],na_position='last').drop(columns='_rank')
        cols=['Symbol','Company','Eligibility','EligibilityReason','HistorySessions','Signal','EntryStatus','Confidence','Overall','Current','EntryLow','EntryHigh','Target1','Potential1%','Target2','Potential2%','StopLoss','RR','RiskLevel','Technical','Fundamental','Momentum','BacktestSample','BacktestWinRate%','WalkForwardSample','WalkForwardWinRate%','MarketIntelligenceScore','MarketContext','InstitutionalBias','DerivativesBias','BreadthBias','DeliveryPct','SurveillanceRisk','NewsRisk']
        cols=[c for c in cols if c in x.columns]
        st.dataframe(x[cols],use_container_width=True,hide_index=True,height=600)
        st.info('A stock can have a high technical score but still be NOT ELIGIBLE because of liquidity, price or insufficient history. It will not be promoted to BUY until those safety gates pass.')

    with sub[1]:
        st.subheader('Qualified Picks Only')
        for cat,label in [('SWING','⚡ SWING'),('SHORT','📈 SHORT TERM'),('LONG','💎 LONG TERM')]:
            st.markdown(f'### {label}')
            x=radar[(radar.Category==cat)&(radar.Eligibility=='ELIGIBLE')&(radar.Signal!='AVOID')].copy()
            if x.empty:st.warning('NO RELIABLE SETUP passed.')
            else:
                st.dataframe(x[['Symbol','Company','Signal','EntryStatus','Confidence','Overall','Current','EntryLow','EntryHigh','Target1','Potential1%','Target2','Potential2%','StopLoss','RR','Duration','Technical','Fundamental','Momentum','BacktestSample','BacktestWinRate%','WalkForwardSample','WalkForwardWinRate%','MarketIntelligenceScore','MarketContext','InstitutionalBias','DerivativesBias','BreadthBias','DeliveryPct','SurveillanceRisk','NewsRisk']].head(50),use_container_width=True,hide_index=True)

    with sub[2]:
        st.subheader('Full Stock Card — ALL NSE')
        all_syms=sorted(radar.Symbol.astype(str).unique().tolist())
        sym=st.selectbox('Search / select any NSE stock',all_syms,key='stock_sym')
        cat=st.radio('Style',['SWING','SHORT','LONG'],horizontal=True,key='stock_cat')
        rr=radar[(radar.Symbol==sym)&(radar.Category==cat)]
        if rr.empty:
            st.error('This symbol is not available in the local NSE data.')
        else:
            r=rr.iloc[0]
            if int(r.get('HistorySessions',0))<20 or pd.isna(r.get('EntryLow',np.nan)):
                st.warning(f"{sym} is present in NSE data but has only {int(r.get('HistorySessions',0))} local sessions. It is shown, but a reliable full price-plan is not created yet.")
                a,b,c=st.columns(3);a.metric('Current',f'₹{r.Current:,.2f}');b.metric('Eligibility',r.Eligibility);c.metric('Confidence',r.Confidence)
                st.write('**Reason:** '+str(r.EligibilityReason))
            else:
                em={'STRONG BUY':'🔥','BUY':'🟢','BUY ON PULLBACK':'🟡','WATCH':'👀','AVOID':'🔴'}.get(r.Signal,'⚪')
                st.markdown(f'## {em} {r.Signal} — {r.Company} ({sym})')
                if r.Eligibility!='ELIGIBLE':
                    st.warning(f'VISIBLE BUT NOT RECOMMENDATION-ELIGIBLE: {r.EligibilityReason}')
                a,b,c,d,e,f=st.columns(6);a.metric('Signal',r.Signal);b.metric('Entry',r.EntryStatus);c.metric('Current',f'₹{r.Current:,.2f}');d.metric('Overall',f'{r.Overall:.0f}/100' if pd.notna(r.Overall) else 'N/A');e.metric('R:R',f'{r.RR:.2f}');f.metric('Confidence',r.Confidence)
                L,R=st.columns(2)
                with L:
                    st.markdown('#### Price Plan')
                    st.write(f'**Current:** ₹{r.Current:,.2f}');st.write(f'**Entry:** ₹{r.EntryLow:,.2f} – ₹{r.EntryHigh:,.2f}')
                    st.write(f'**Support:** S1 ₹{r.S1:,.2f} • S2 ₹{r.S2:,.2f}');st.write(f'**Resistance:** R1 ₹{r.R1:,.2f} • R2 ₹{r.R2:,.2f}')
                    st.write(f"**🎯 Target 1:** ₹{r.Target1:,.2f} • {r['Potential1%']:+.1f}%");st.write(f"**🚀 Target 2:** ₹{r.Target2:,.2f} • {r['Potential2%']:+.1f}%")
                    st.write(f"**🛑 Stop Loss:** ₹{r.StopLoss:,.2f} • Risk {r['Risk%']:+.1f}%");st.write(f'**⚖️ Risk:Reward:** {r.RR:.2f}');st.write(f'**⏳ Duration:** {r.Duration}')
                with R:
                    st.markdown('#### Scores & Evidence')
                    if pd.notna(r.Technical):st.progress(int(min(r.Technical,100)),text=f'Technical {r.Technical:.0f}/100')
                    if pd.notna(r.Fundamental):st.progress(int(min(r.Fundamental,100)),text=f'Fundamental {r.Fundamental:.0f}/100')
                    else:st.info('Fundamental score unavailable')
                    if pd.notna(r.Momentum):st.progress(int(min(r.Momentum,100)),text=f'Momentum {r.Momentum:.0f}/100')
                    st.write(f"**Overall:** {r.Overall:.0f}/100" if pd.notna(r.Overall) else '**Overall:** N/A')
                    st.write(f'**Historical Signals:** {int(r.BacktestSample)}')
                    st.write(f"**Backtest Win Rate:** {r['BacktestWinRate%']}%" if pd.notna(r['BacktestWinRate%']) else '**Backtest Win Rate:** not established')
                    st.write(f"**Walk-Forward Win Rate:** {r['WalkForwardWinRate%']}% over {int(r.WalkForwardSample)} signals" if pd.notna(r['WalkForwardWinRate%']) else '**Walk-Forward:** not established')
                    st.write(f'**Risk:** {r.RiskLevel}');st.write(f'**Confidence:** {r.Confidence}')
                    st.write(f'**Eligibility:** {r.Eligibility}');st.write(f'**Eligibility reason:** {r.EligibilityReason}')
                    st.write(f'**News / Results gate:** {r.NewsRisk}');st.write(f'**Corporate/Event gate:** {r.CorporateActionRisk}')
                st.markdown('#### Reason')
                reasons=[]
                if r.Eligibility=='ELIGIBLE':reasons.append('Passes price, liquidity and history eligibility gates')
                else:reasons.append('Not recommendation-eligible: '+str(r.EligibilityReason))
                if r.Technical>=80:reasons.append('Technical strength is high')
                elif r.Technical>=70:reasons.append('Trend / technical structure passes')
                if r.Momentum>=80:reasons.append('Momentum is strong')
                elif r.Momentum>=70:reasons.append('Momentum passes')
                if pd.notna(r.Fundamental) and r.Fundamental>=75:reasons.append('Fundamental quality passes')
                if r.RR>=2:reasons.append('Risk : Reward is 2.0 or better')
                elif r.RR>=1.7:reasons.append('Risk : Reward passes minimum rule')
                if reg!='WEAK':reasons.append('Market regime is acceptable')
                if r.NewsRisk=='PASS':reasons.append('No blocking recent NSE announcement detected')
                if r.CorporateActionRisk=='NONE':reasons.append('No blocking corporate action detected')
                if r.EntryStatus=='ENTRY VALID':reasons.append('Current price is inside the valid entry zone')
                for z in reasons or ['Insufficient evidence for a stronger rating']:st.write('• '+z)
                st.markdown('#### What would change this recommendation?')
                if r.Signal=='STRONG BUY': st.write('• It can be downgraded if price leaves the valid entry zone, market turns WEAK, R:R falls below 2.0, news/corporate-action risk appears, or validation/confidence weakens.')
                elif r.Signal in ('BUY','BUY ON PULLBACK'): st.write('• It can improve with stronger score/validation and a valid entry; it can weaken if price becomes stretched, market/news risk worsens or R:R falls below the rule.')
                elif r.Signal=='WATCH': st.write('• Upgrade requires stronger technical/momentum/fundamental evidence, acceptable market/news gates and a valid entry zone.')
                else: st.write('• Upgrade requires material improvement in trend, momentum, fundamentals/quality, R:R and safety gates.')
                chart=load_chart(sym)
                if not chart.empty:st.line_chart(chart.set_index('Date')[[c for c in ['Close','EMA10','EMA21','EMA50'] if c in chart.columns]])
                else:st.caption('Detailed chart cache is stored mainly for qualified/high-priority stocks to keep the app fast. The decision card above is still calculated for this symbol.')
                st.markdown('#### Public News Context')
                if st.button('🔄 Refresh public news for '+sym,key='stock_news_'+sym):
                    _nb=st.empty();_nr=refresh_stock_news(sym,str(r.Company),status_cb=lambda x:_nb.caption(str(x)));(_nb.success if _nr.get('ok') else _nb.warning)(_nr.get('message',''))
                _sn=load_stock_news(sym)
                if _sn is not None and not _sn.empty:st.dataframe(_sn[[c for c in ['Published','Title','Source','Risk'] if c in _sn.columns]].head(20),use_container_width=True,hide_index=True)
                else:st.caption('No cached public-news context for this stock. Official NSE announcement/event gates above remain active.')

if active_page=='🧮 Position Size':
    capital=st.number_input('Total trading/investment capital ₹',min_value=1000.0,value=500000.0,step=10000.0)
    risk_pct=st.number_input('Maximum risk per trade %',min_value=.1,max_value=5.0,value=float(CFG.get('position_risk_default_pct',1.0)),step=.1)
    max_pos=st.number_input('Maximum capital in one stock %',min_value=5.0,max_value=100.0,value=25.0,step=5.0)
    candidates=radar[(radar.Signal.isin(['STRONG BUY','BUY','BUY ON PULLBACK','WATCH'])) & (radar.get('Eligibility','ELIGIBLE')=='ELIGIBLE')]
    psym=st.selectbox('Select stock',candidates.Symbol.drop_duplicates().tolist() if not candidates.empty else radar.Symbol.drop_duplicates().tolist(),key='pos_sym')
    pcat=st.radio('Horizon',['SWING','SHORT','LONG'],horizontal=True,key='pos_cat')
    pr=radar[(radar.Symbol==psym)&(radar.Category==pcat)].iloc[0]
    entry=(pr.EntryLow+pr.EntryHigh)/2
    pos=position_size(capital,risk_pct,entry,pr.StopLoss,max_pos)
    q1,q2,q3,q4=st.columns(4);q1.metric('Suggested max quantity',pos['Quantity']);q2.metric('Capital required',f"₹{pos['CapitalRequired₹']:,.0f}");q3.metric('Max loss at stop',f"₹{pos['MaxLoss₹']:,.0f}");q4.metric('Portfolio exposure',f"{pos['PortfolioExposure%']}%")
    st.caption(f'Model entry midpoint ₹{entry:,.2f} • Stop ₹{pr.StopLoss:,.2f}. Position size is constrained by both risk budget and max-position limit.')

if active_page=='💼 My Portfolio':
    st.caption('Keep every purchase lot. The app combines them automatically into average cost, current value, P&L and review actions.')
    portfolio_file=BASE/'data'/'my_portfolio.csv'
    goals_file=BASE/'data'/'investment_goals.csv'

    try:
        saved_lots=pd.read_csv(portfolio_file) if portfolio_file.exists() else pd.DataFrame(columns=PORTFOLIO_COLUMNS)
        saved_lots=normalize_portfolio(saved_lots) if not saved_lots.empty else pd.DataFrame(columns=PORTFOLIO_COLUMNS)
    except Exception:
        saved_lots=pd.DataFrame(columns=PORTFOLIO_COLUMNS)

    # Fast mode: opening Portfolio uses saved values only. Daily Update refreshes current prices automatically.
    pfast1,pfast2=st.columns([1,3])
    if pfast1.button('🔄 Refresh current values',use_container_width=True,key='portfolio_refresh_prices'):
        with st.spinner('Refreshing current values from downloaded market data...'):pres=refresh_saved_portfolio_prices(radar,mf,bonds)
        if pres.get('ok'):st.success(pres.get('message'));cloud_rerun()
        else:st.warning(pres.get('message'))
    pfast2.caption('Fast opening: no full market/crypto scan is performed just by entering this page.')

    ptab=st.tabs(['📊 Summary / Review','➕ Manual Entry','📥 Import / Update','✏️ Edit / Export','🎯 Goals'])

    with ptab[0]:
        if saved_lots.empty:
            st.info('No investments saved yet. Use Manual Entry or Import / Update.')
        else:
            agg=aggregate_holdings(saved_lots)
            review=analyse_portfolio(agg,radar,mf,bonds)
            inv=float(pd.to_numeric(review.get('Invested₹'),errors='coerce').fillna(0).sum()) if not review.empty else 0
            cur=float(pd.to_numeric(review.get('CurrentValue₹'),errors='coerce').fillna(0).sum()) if not review.empty else 0
            pnl=cur-inv
            m1,m2,m3,m4=st.columns(4)
            m1.metric('Total invested',f'₹{inv:,.0f}')
            m2.metric('Current value',f'₹{cur:,.0f}' if cur else 'Needs current prices')
            m3.metric('Overall P&L',f'₹{pnl:,.0f}' if cur else '—')
            m4.metric('Purchase lots',len(saved_lots))
            st.markdown('#### Combined holdings & current action')
            show=[c for c in ['AssetType','Symbol','Name','Quantity','Unit','AvgPrice₹','Invested₹','CurrentPrice₹','CurrentValue₹','PnL₹','PnL%','Lots','FirstPurchase','LastPurchase','CurrentSignal','CurrentScore','CurrentConfidence','PortfolioAction','ReviewReason','Goal'] if c in review.columns]
            st.dataframe(review[show],use_container_width=True,hide_index=True)
            if cur>0:
                alloc=review.groupby('AssetType',dropna=False)['CurrentValue₹'].sum().sort_values(ascending=False).reset_index()
                alloc['Weight%']=(alloc['CurrentValue₹']/cur*100).round(1)
                st.markdown('#### Asset allocation')
                st.dataframe(alloc,use_container_width=True,hide_index=True)
            try:
                ph=portfolio_health(saved_lots);ps=ph.get('summary',{})
                st.markdown('#### Portfolio Health')
                p1,p2,p3,p4=st.columns(4);p1.metric('Health',str(ps.get('Health','—')))
                p2.metric('P&L %',f"{ps.get('PnL%',np.nan):.2f}%" if pd.notna(ps.get('PnL%',np.nan)) else '—')
                p3.metric('Approx. XIRR',f"{ps.get('ApproxXIRR%',np.nan):.2f}%" if pd.notna(ps.get('ApproxXIRR%',np.nan)) else 'Needs current values')
                p4.metric('Portfolio profiles',ps.get('Profiles',0))
                if ph.get('warnings') is not None and not ph['warnings'].empty:
                    st.warning('Concentration review suggested.');st.dataframe(ph['warnings'],use_container_width=True,hide_index=True)
                if ph.get('profiles') is not None and not ph['profiles'].empty and len(ph['profiles'])>1:
                    st.markdown('#### Portfolio / account profiles');st.dataframe(ph['profiles'],use_container_width=True,hide_index=True)
                st.caption('Approx. XIRR uses saved purchase-lot cash outflows and today’s current portfolio value as the closing value. It is not a tax calculation and does not invent missing dividends/redemptions.')
            except Exception as e:st.caption('Portfolio-health analytics unavailable: '+str(e))
            goals=saved_lots.copy()
            goals['CurrentValue₹']=(pd.to_numeric(goals.Quantity,errors='coerce')/pd.to_numeric(goals.PriceBasisQty,errors='coerce'))*pd.to_numeric(goals['CurrentPrice₹'],errors='coerce')
            if goals.Goal.astype(str).str.strip().ne('').any():
                gsum=goals[goals.Goal.astype(str).str.strip().ne('')].groupby('Goal')['CurrentValue₹'].sum().reset_index()
                st.markdown('#### Current value by goal')
                st.dataframe(gsum,use_container_width=True,hide_index=True)
            missing=int(saved_lots['CurrentPrice₹'].isna().sum())
            if missing:st.warning(f'{missing} purchase lot(s) do not have an automatic current price. Enter/update CurrentPrice₹ for FD, some bonds or Other assets when needed.')

    with ptab[1]:
        st.markdown('### Add one purchase / investment lot')
        st.caption('Buying the same investment again on another date creates another lot. The Summary combines them automatically.')
        at=st.selectbox('Asset type',ASSET_TYPES,key='manual_asset_type')
        sym='';name=''
        if at in ('STOCK','ETF'):
            syms=sorted(radar.Symbol.astype(str).unique().tolist())
            sym=st.selectbox('Select NSE symbol',syms,key='manual_stock_symbol')
            rr=radar[radar.Symbol.eq(sym)]
            name=str(rr.iloc[0].get('Company',sym)) if not rr.empty else sym
            st.text_input('Name',value=name,disabled=True,key='manual_stock_name')
        elif at=='MUTUAL FUND':
            opts=['Other / Enter manually']
            if not mf.empty:
                opts += [f"{str(r.get('Code',''))} | {str(r.get('Scheme',''))}" for _,r in mf.iterrows()]
            sel=st.selectbox('Select mutual fund',opts,key='manual_mf')
            if sel=='Other / Enter manually':
                sym=st.text_input('Scheme code / symbol',key='manual_mf_sym');name=st.text_input('Scheme name',key='manual_mf_name')
            else:
                sym,name=sel.split(' | ',1)
        elif at=='GOLD PHYSICAL':
            sym='GOLD';name=st.text_input('Description',value='Physical Gold',key='manual_gold_name')
        elif at=='SILVER PHYSICAL':
            sym='SILVER';name=st.text_input('Description',value='Physical Silver',key='manual_silver_name')
        elif at=='CRYPTO':
            sym=st.selectbox('Crypto',sorted(crypto_universe().keys()),key='manual_crypto');name=crypto_universe()[sym][0]
        elif at=='BOND / FIXED INCOME':
            opts=['Other / Enter manually'] + (bonds.Instrument.astype(str).tolist() if bonds is not None and not bonds.empty else [])
            bsel=st.selectbox('Bond / instrument',opts,key='manual_bond')
            if bsel=='Other / Enter manually':
                name=st.text_input('Bond / fixed-income name',key='manual_bond_name');sym=st.text_input('ISIN / code (optional)',key='manual_bond_sym')
            else:
                name=bsel;sym=bsel
        else:
            sym=st.text_input('Symbol / short name',key='manual_other_sym');name=st.text_input('Investment name',key='manual_other_name')

        d1,d2,d3,d4=st.columns(4)
        pdate=d1.date_input('Purchase date',value=pd.Timestamp.now().date(),key='manual_date')
        qty=d2.number_input('Quantity',min_value=0.0,value=1.0,step=.01,key='manual_qty')
        default_unit={'STOCK':'Shares','ETF':'Units','MUTUAL FUND':'Units','GOLD PHYSICAL':'grams','SILVER PHYSICAL':'kg','CRYPTO':'Coins','BOND / FIXED INCOME':'Units','FD':'Deposit','CASH':'₹','OTHER':'Units'}.get(at,'Units')
        unit=d3.text_input('Quantity unit',value=default_unit,key='manual_unit')
        default_basis=10.0 if at=='GOLD PHYSICAL' else 1.0
        basis=d4.number_input('Price basis quantity',min_value=.000001,value=default_basis,step=1.0,key='manual_basis',help='Gold example: if price is ₹ per 10g, enter 10. Stocks/MF normally use 1.')
        b1,b2,b3=st.columns(3)
        buy=b1.number_input('Buy price ₹ (per price-basis quantity)',min_value=0.0,value=0.0,step=1.0,key='manual_buy')
        auto_amount=(qty/basis)*buy if basis else 0
        override=b2.number_input('Invested amount ₹ (0 = calculate automatically)',min_value=0.0,value=0.0,step=100.0,key='manual_amt')
        current=b3.number_input('Current price ₹ (optional; automatic where supported)',min_value=0.0,value=0.0,step=1.0,key='manual_current')
        st.caption(f'Calculated invested amount from quantity × price: **₹{auto_amount:,.2f}**')
        c1,c2,c3=st.columns(3)
        broker=c1.text_input('Broker / source / dealer',key='manual_broker')
        account=c2.text_input('Account / folio / location',key='manual_account')
        goal=c3.text_input('Goal (e.g. Retirement / Wealth / Education)',key='manual_goal')
        c4,c5=st.columns(2)
        strategy=c4.selectbox('Strategy / purpose',['Swing','Short Term','Long Term','SIP','Physical Investment','Income','Emergency','Other'],key='manual_strategy')
        notes=c5.text_input('Notes',key='manual_notes')
        if st.button('➕ ADD THIS INVESTMENT LOT',type='primary',key='manual_save'):
            amt=override if override>0 else auto_amount
            row=pd.DataFrame([{'InvestmentID':'','AssetType':at,'Symbol':sym,'Name':name,'PurchaseDate':pdate,'Quantity':qty,'Unit':unit,'PriceBasisQty':basis,'BuyPrice₹':buy,'InvestedAmount₹':amt,'CurrentPrice₹':current if current>0 else np.nan,'BrokerSource':broker,'Account':account,'Goal':goal,'Strategy':strategy,'Notes':notes,'UpdatedAt':''}])
            row=normalize_portfolio(row)
            merged=merge_portfolio(saved_lots,row,'MERGE / UPDATE')
            merged.to_csv(portfolio_file,index=False)
            create_backup(CFG.get('backup_keep',12))
            st.success('Investment lot saved. It is now part of your permanent local portfolio.')
            cloud_rerun()

    with ptab[2]:
        st.markdown('### Download format / import / update')
        tmpl=template_df()
        dc1,dc2=st.columns(2)
        dc1.download_button('⬇️ Download Portfolio Template CSV',tmpl.to_csv(index=False).encode('utf-8-sig'),'India_Investment_Radar_Portfolio_Template.csv','text/csv',use_container_width=True)
        dc2.download_button('⬇️ Download Portfolio Template Excel',dataframe_to_xlsx_bytes(tmpl),'India_Investment_Radar_Portfolio_Template.xlsx','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',use_container_width=True)
        st.info('For our template: keep InvestmentID when updating an existing lot. Blank InvestmentID creates a new lot. For a fresh broker holdings export, use REPLACE if you want the file to become the new stock-holdings base.')
        up=st.file_uploader('Upload portfolio / broker holdings CSV or Excel',type=['csv','xlsx','xls'],key='portfolio_import')
        mode=st.radio('Import method',['MERGE / UPDATE','REPLACE CURRENT PORTFOLIO'],horizontal=True,key='portfolio_import_mode')
        if up:
            try:
                incoming=read_portfolio(up)
                st.markdown('#### Import preview')
                st.dataframe(incoming,use_container_width=True,hide_index=True)
                if st.button('✅ IMPORT & SAVE',type='primary',key='portfolio_import_save'):
                    merged=merge_portfolio(saved_lots,incoming,mode)
                    merged.to_csv(portfolio_file,index=False)
                    create_backup(CFG.get('backup_keep',12))
                    st.success(f'Portfolio saved: {len(merged)} purchase lot(s).')
                    cloud_rerun()
            except Exception as e:st.error(f'Could not read the import file: {e}')

    with ptab[3]:
        if saved_lots.empty:st.info('No saved portfolio to edit yet.')
        else:
            st.markdown('### Edit saved lots directly')
            edited=st.data_editor(saved_lots,use_container_width=True,num_rows='dynamic',hide_index=True,key='portfolio_editor')
            b1,b2,b3=st.columns(3)
            if b1.button('💾 SAVE EDITED PORTFOLIO',type='primary',use_container_width=True):
                cleaned=normalize_portfolio(pd.DataFrame(edited))
                cleaned.to_csv(portfolio_file,index=False);create_backup(CFG.get('backup_keep',12));st.success('Edited portfolio saved.');cloud_rerun()
            b2.download_button('⬇️ Export current CSV',saved_lots.to_csv(index=False).encode('utf-8-sig'),'My_Investment_Portfolio.csv','text/csv',use_container_width=True)
            b3.download_button('⬇️ Export current Excel',dataframe_to_xlsx_bytes(saved_lots),'My_Investment_Portfolio.xlsx','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',use_container_width=True)
            st.caption('Delete a row in the editor and press SAVE to remove that purchase lot. Existing backups remain available in the app data folder.')

    with ptab[4]:
        st.markdown('### Goal-based Investment Planner')
        st.caption('Use your existing portfolio value plus future monthly investment to check whether a goal is on track.')
        existing_goals=[]
        if not saved_lots.empty:existing_goals=sorted([x for x in saved_lots.Goal.astype(str).unique().tolist() if x.strip() and x.lower()!='nan'])
        gname=st.text_input('Goal name',value=existing_goals[0] if existing_goals else 'Wealth Creation',key='goal_name')
        current_goal_value=0.0
        if not saved_lots.empty and gname:
            gx=saved_lots[saved_lots.Goal.astype(str).str.casefold().eq(gname.casefold())].copy()
            if not gx.empty:
                gx['CV']=(pd.to_numeric(gx.Quantity,errors='coerce')/pd.to_numeric(gx.PriceBasisQty,errors='coerce'))*pd.to_numeric(gx['CurrentPrice₹'],errors='coerce')
                current_goal_value=float(gx.CV.fillna(0).sum())
        g1,g2,g3,g4=st.columns(4)
        target=g1.number_input('Target amount ₹',min_value=10000.0,value=2500000.0,step=100000.0,key='goal_target')
        currentv=g2.number_input('Current amount for this goal ₹',min_value=0.0,value=float(current_goal_value),step=10000.0,key='goal_current')
        years=g3.number_input('Years remaining',min_value=.25,max_value=50.0,value=5.0,step=.25,key='goal_years')
        monthly=g4.number_input('Monthly contribution / SIP ₹',min_value=0.0,value=25000.0,step=1000.0,key='goal_monthly')
        risk=st.selectbox('Risk profile',['LOW','MODERATE','HIGH'],index=1,key='goal_risk')
        tx1,tx2=st.columns(2)
        effective_tax=tx1.number_input('Optional effective tax on gains %',min_value=0.0,max_value=60.0,value=0.0,step=.5,key='goal_tax',help='User-entered planning assumption only. The app does not hard-code Indian tax law.')
        inflation=tx2.number_input('Inflation assumption %',min_value=0.0,max_value=20.0,value=5.0,step=.25,key='goal_inflation')
        gs=goal_scenarios(target,currentv,monthly,years,risk)
        contributed=currentv+monthly*12*years
        gs['EstimatedTax₹']=((gs['ProjectedValue₹']-contributed).clip(lower=0)*effective_tax/100).round(2)
        gs['PostTaxValue₹']=(gs['ProjectedValue₹']-gs['EstimatedTax₹']).round(2)
        gs['InflationAdjustedValue₹']=(gs['PostTaxValue₹']/((1+inflation/100)**years)).round(2)
        st.dataframe(gs,use_container_width=True,hide_index=True)
        st.caption('Tax is an optional effective-rate planning assumption, not a legal tax calculation. Inflation-adjusted value shows purchasing-power context.')
        base_rate={'LOW':7,'MODERATE':10,'HIGH':12}[risk]
        req=required_monthly_sip(target,currentv,base_rate,years)
        st.metric('Estimated monthly investment needed for target (base assumption)',f'₹{req:,.0f}')
        st.markdown('#### Suggested asset allocation for this goal')
        st.dataframe(allocation(max(currentv+monthly*12,1000),risk,years,CFG['portfolio_allocations']),use_container_width=True,hide_index=True)
        if st.button('💾 Save / Update Goal',key='save_goal'):
            row={'Goal':gname,'TargetAmount₹':target,'CurrentAmount₹':currentv,'YearsRemaining':years,'MonthlyContribution₹':monthly,'Risk':risk,'EffectiveTaxAssumption%':effective_tax,'InflationAssumption%':inflation,'UpdatedAt':pd.Timestamp.now().isoformat(timespec='seconds')}
            old=pd.read_csv(goals_file) if goals_file.exists() else pd.DataFrame()
            if not old.empty and 'Goal' in old.columns:
                old=old[old.Goal.astype(str).str.casefold().ne(gname.casefold())]
            pd.concat([old,pd.DataFrame([row])],ignore_index=True).to_csv(goals_file,index=False)
            st.success('Goal saved locally.')
        if goals_file.exists():
            st.markdown('#### Saved goals')
            try:st.dataframe(pd.read_csv(goals_file),use_container_width=True,hide_index=True)
            except Exception:pass

if active_page=='🥇 Gold / Silver':
    st.caption('MAIN PURPOSE: tell you when to buy physical Gold or Silver. NSE Gold/Silver ETF data is used only as the market-trend proxy in the background.')

    mode=st.radio('Mode',['PHYSICAL BUY — MAIN','ETF / TRADING VIEW'],horizontal=True,key='metal_mode')
    metal=st.radio('Asset',['GOLD','SILVER'],horizontal=True,key='metal_asset')
    mcfg=CFG.get('precious_assets',{}).get(metal,{})
    proxy_sym=None
    available=set(radar.Symbol.astype(str))
    for s in mcfg.get('symbols',[]):
        if s in available:
            proxy_sym=s;break

    if not proxy_sym:
        st.warning(f'No {metal} market proxy is available in the current NSE local data. Run DAILY UPDATE.')
    else:
        hh=cached_history(CFG['history_sessions'])
        gg=hh[hh.Symbol.astype(str).eq(proxy_sym)].copy()
        cards,gchart=analyze_asset(gg,proxy_sym,mcfg.get('name',metal),'METAL','₹')
        if cards.empty:
            st.warning('Not enough history for this Gold/Silver timing model yet.')
        else:
            if mode=='PHYSICAL BUY — MAIN':
                unit='10 grams' if metal=='GOLD' else '1 kg'
                state=load_metal_state()
                saved=state.get(metal,{})
                auto_refs=automatic_reference_from_macro(load_macro())
                auto_ref=auto_refs.get(metal,{})

                st.markdown(f'### Automatic physical {metal.title()} reference')
                state=load_metal_state();saved=state.get(metal,{})
                auto_mode=st.toggle('Use automatic rate — recommended',value=bool(saved.get('auto_mode',True)),key=f'{metal}_auto_rate_mode')
                purity='999'
                if metal=='GOLD':
                    plist=['24K / 999','22K / 916','18K / 750'];pv=saved.get('purity','24K / 999');purity=st.selectbox('Gold purity',plist,index=plist.index(pv) if pv in plist else 0,key='gold_purity')
                local_adj=st.number_input('Local market adjustment % (optional)',min_value=-20.0,max_value=30.0,value=float(saved.get('local_adjustment_pct',0.0)),step=.1,key=f'{metal}_local_adj',help='Use only if your local/dealer base rate systematically differs from the automatic benchmark. Dealer premium and tax are entered separately below.')
                auto_ref=get_auto_rate(metal,load_macro(),purity,local_adj)
                if auto_ref and float(auto_ref.get('rate',0) or 0)>0:
                    st.success(f"Automatic market reference: **₹{float(auto_ref.get('rate',0)):,.2f} / {auto_ref.get('unit',unit)}** • {auto_ref.get('purity','')} • Date {auto_ref.get('date','')} • global bullion × USD/INR conversion.")
                    st.caption('Indicative investment benchmark, not a guaranteed jewellery-shop quote. Local dealer premium, making charge and tax can differ.')
                else:st.warning('Automatic rate is unavailable right now. The app will use the last saved reference if available; otherwise switch off Automatic Rate and enter your dealer/local base quote.')
                c1,c2,c3,c4=st.columns(4);auto_quote=float(auto_ref.get('rate',0) or 0) if auto_ref else 0.0;manual_default=float(saved.get('manual_quote',saved.get('quote',0.0)) or 0)
                if auto_mode and auto_quote>0:
                    quote=auto_quote;c1.metric(f'{metal.title()} base ₹ / {unit}',f'₹{quote:,.2f}')
                else:
                    quote=c1.number_input(f'Manual {metal.title()} rate ₹ / {unit}',min_value=0.0,value=manual_default,step=100.0 if metal=='GOLD' else 500.0,key=f'{metal}_physical_quote')
                amount=c2.number_input('Planned investment ₹',min_value=1000.0,value=float(saved.get('amount',100000.0)),step=10000.0,key=f'{metal}_physical_amount')
                premium=c3.number_input('Dealer / coin premium %',min_value=0.0,max_value=50.0,value=float(saved.get('premium_pct',0.0)),step=.1,key=f'{metal}_premium')
                gst=c4.number_input('Tax/GST % if NOT already included',min_value=0.0,max_value=30.0,value=float(saved.get('gst_pct',0.0)),step=.1,key=f'{metal}_gst')
                making=st.number_input('Making / fabrication charge % (optional)',min_value=0.0,max_value=50.0,value=float(saved.get('making_pct',0.0)),step=.1,key=f'{metal}_making')
                if st.button('💾 Save Physical Buy Settings',key=f'save_{metal}_physical'):
                    state[metal]={"quote":quote,"manual_quote":manual_default if auto_mode else quote,"amount":amount,"premium_pct":premium,"gst_pct":gst,"making_pct":making,"auto_mode":auto_mode,"purity":purity,"local_adjustment_pct":local_adj};save_metal_state(state);st.success('Saved locally. Automatic mode refreshes during DAILY UPDATE.')

                horizon=st.radio(
                    'Your intended holding period',
                    ['1 Month','3 Months','6–12 Months','1–3 Years'],
                    horizontal=True,key=f'{metal}_physical_horizon'
                )
                cat={'1 Month':'SWING','3 Months':'SHORT','6–12 Months':'LONG','1–3 Years':'LONG'}[horizon]
                r=cards[cards.Category==cat].iloc[0]
                decision,action=timing_decision(r)

                st.markdown(f'## {decision} — {metal}')
                a,b,c,d,e=st.columns(5)
                a.metric('Market Signal',r.Signal)
                b.metric('Overall',f'{r.Overall:.0f}/100')
                c.metric('Trend',f'{r.Technical:.0f}/100')
                d.metric('Risk',r.Risk)
                e.metric('Confidence',r.Confidence)

                st.markdown('### What should I do?')
                if 'BUY' in decision and 'DO NOT' not in decision:
                    st.success(action)
                else:
                    st.warning(action)

                if quote>0:
                    pc=physical_card(r,quote)
                    effective=effective_cost(quote,premium+making,gst)
                    st.markdown(f'### Physical {metal.title()} Price Plan — ₹ per {unit}')
                    L,R=st.columns(2)
                    with L:
                        st.write(f"**Today’s entered base rate:** ₹{quote:,.2f}")
                        if premium or gst:
                            st.write(f"**Estimated all-in acquisition rate:** ₹{effective:,.2f}")
                        st.write(f"**🟢 Preferred Buy Zone:** ₹{pc['BuyLow']:,.2f} – ₹{pc['BuyHigh']:,.2f}")
                        st.write(f"**🟡 Better Dip Zone:** around ₹{pc['Support1']:,.2f}")
                        st.write(f"**🟢 Deep Value / Support Zone:** around ₹{pc['Support2']:,.2f}")
                        st.write(f"**🎯 Scenario Target 1:** ₹{pc['Target1']:,.2f}")
                        st.write(f"**🚀 Scenario Target 2:** ₹{pc['Target2']:,.2f}")
                    with R:
                        st.write(f"**Entry status:** {r.EntryStatus}")
                        st.write(f"**Historical Signals:** {r.HistoricalSignals}")
                        st.write(f"**Win Rate:** {r['WinRate%']}%" if pd.notna(r['WinRate%']) else '**Win Rate:** not established')
                        st.write(f"**Technical:** {r.Technical:.0f}/100")
                        st.write(f"**Momentum:** {r.Momentum:.0f}/100")
                        st.write(f"**Market Structure:** {r.Structure:.0f}/100")
                        st.markdown('#### Why this physical-buy recommendation?')
                        for reason in str(r.Reason).split(' • '):
                            if reason.strip(): st.write('• '+reason.strip())
                        st.markdown('#### What would change this recommendation?')
                        if 'WAIT FOR DIP' in decision:
                            st.write(f"• A move back toward the preferred buy zone ₹{pc['BuyLow']:,.2f}–₹{pc['BuyHigh']:,.2f} with the signal still valid can upgrade the action to staged buying.")
                        elif 'DO NOT BUY' in decision or 'WAIT / WATCH' in decision:
                            st.write('• Upgrade requires stronger trend/momentum/structure and price moving into a better accumulation zone.')
                        else:
                            st.write(f"• If price rises materially above the buy zone ₹{pc['BuyLow']:,.2f}–₹{pc['BuyHigh']:,.2f}, do not chase; if trend/momentum weakens, the action can move back to WATCH.")

                    st.markdown('### Suggested staged purchase')
                    tp=tranche_plan(amount,decision)
                    st.dataframe(tp,use_container_width=True,hide_index=True)

                    if effective>0:
                        if metal=='GOLD':
                            qty=amount/effective*10
                            st.caption(f'At the current estimated all-in rate, ₹{amount:,.0f} equals approximately **{qty:,.2f} grams** before considering denomination availability.')
                        else:
                            qty=amount/effective
                            st.caption(f'At the current estimated all-in rate, ₹{amount:,.0f} equals approximately **{qty:,.3f} kg** before considering denomination availability.')

                    st.markdown('### Forward timing scenarios')
                    sc=rolling_scenarios(gchart)
                    sp=scenario_prices(sc,quote)
                    if not sp.empty:
                        st.dataframe(sp[['Duration','ProbabilityPositive%','Low%','Median%','High%','LowPrice₹','MedianPrice₹','HighPrice₹','Samples']],use_container_width=True,hide_index=True)
                        st.caption('These ranges come from historical rolling returns of the market proxy. They are scenarios, not guaranteed future prices.')

                    st.warning('For physical investment, the system does NOT force a trading-style stop loss. It focuses on buy timing, staged accumulation, price zones and review levels. Jewellery making charges can materially change investment economics; the premium field lets you account for extra purchase cost.')
                else:
                    st.warning(f'Enter today’s physical {metal.title()} rate above. Then the app will show the exact physical BUY / WAIT zones in ₹ per {unit}.')

                if not gchart.empty:
                    st.markdown('### Underlying market trend')
                    st.line_chart(gchart.tail(180).set_index('Date')[[c for c in ['Close','EMA21','EMA50'] if c in gchart.columns]])

            else:
                st.caption('ETF / Trading View keeps the original tradable market card.')
                cat=st.radio('Horizon',['SWING','SHORT','LONG'],horizontal=True,key='metal_cat')
                r=cards[cards.Category==cat].iloc[0]
                em={'STRONG BUY':'🔥','BUY':'🟢','WATCH':'👀','AVOID':'🔴'}.get(r.Signal,'⚪')
                st.markdown(f"## {em} {r.Signal} — {metal} ({proxy_sym})")
                a,b,c,d,e=st.columns(5)
                a.metric('Current',f"₹{r.Current:,.2f}");b.metric('Overall',f"{r.Overall:.0f}/100");c.metric('R:R',f"{r.RR:.2f}");d.metric('Risk',r.Risk);e.metric('Confidence',r.Confidence)
                L,R=st.columns(2)
                with L:
                    st.write(f"**Entry:** ₹{r.EntryLow:,.2f} – ₹{r.EntryHigh:,.2f}")
                    st.write(f"**Support:** S1 ₹{r.S1:,.2f} • S2 ₹{r.S2:,.2f}")
                    st.write(f"**Resistance:** R1 ₹{r.R1:,.2f} • R2 ₹{r.R2:,.2f}")
                    st.write(f"**🎯 Target 1:** ₹{r.Target1:,.2f} • {r['Potential1%']:+.1f}%")
                    st.write(f"**🚀 Target 2:** ₹{r.Target2:,.2f} • {r['Potential2%']:+.1f}%")
                    st.write(f"**🛑 Stop Loss:** ₹{r.StopLoss:,.2f} • Risk {r['Risk%']:+.1f}%")
                    st.write(f"**⚖️ R:R:** {r.RR:.2f} • **⏳ Duration:** {r.Duration}")
                with R:
                    st.progress(int(r.Technical),text=f"Technical {r.Technical:.0f}/100")
                    st.progress(int(r.Momentum),text=f"Momentum {r.Momentum:.0f}/100")
                    st.progress(int(r.Structure),text=f"Asset Structure {r.Structure:.0f}/100")
                    st.write('**Fundamental:** N/A — not faked for metals')
                    st.write(f"**Historical Signals:** {r.HistoricalSignals}")
                    st.write(f"**Win Rate:** {r['WinRate%']}%" if pd.notna(r['WinRate%']) else '**Win Rate:** not established')
                    st.write(f"**Risk:** {r.Risk} • **Confidence:** {r.Confidence}")
                    st.markdown('#### Reason')
                    for reason in str(r.Reason).split(' • '):
                        if reason.strip(): st.write('• '+reason.strip())
                    st.markdown('#### What would change this recommendation?')
                    st.write('• '+str(getattr(r,'WhatChanges','Trend, momentum, entry validity and Risk:Reward determine upgrades/downgrades.')))

if active_page=='₿ Crypto':
    st.warning('Crypto is a 24/7 market and materially more volatile than NSE equities. The radar can rank setups, but confidence is deliberately conservative and no return is guaranteed.')
    cm=crypto_meta();cu=crypto_universe()
    if cm:
        st.caption(f"Crypto cache: {cm.get('updated_at','')} • USD/INR reference: {cm.get('usd_inr','N/A')}")
    else:
        st.info('Crypto data is not downloaded yet. Click DAILY UPDATE once.')
    symbols=CFG.get('crypto_symbols',list(cu))
    csym=st.selectbox('Crypto',symbols,format_func=lambda s:f"{s} — {cu.get(s,(s,''))[0]}",key='crypto_sym')
    cdf=load_crypto(csym)
    if cdf.empty:
        st.warning('No cached data for this crypto yet. Click DAILY UPDATE. If the crypto data source is unavailable on your network, the rest of India Investment Radar will continue working normally.')
    else:
        cards,cchart=analyze_asset(cdf,csym,cu.get(csym,(csym,''))[0],'CRYPTO','USDT')
        if cards.empty:
            st.warning('Not enough crypto history yet.')
        else:
            cat=st.radio('Crypto horizon',['SWING','SHORT','LONG'],horizontal=True,key='crypto_cat')
            r=cards[cards.Category==cat].iloc[0];fx=cm.get('usd_inr') if cm else None
            em={'STRONG BUY':'🔥','BUY':'🟢','WATCH':'👀','AVOID':'🔴'}.get(r.Signal,'⚪')
            st.markdown(f"## {em} {r.Signal} — {r.Asset} ({csym})")
            a,b,c,d,e=st.columns(5)
            a.metric('Current',f"${r.Current:,.4f}");b.metric('Overall',f"{r.Overall:.0f}/100");c.metric('R:R',f"{r.RR:.2f}");d.metric('Risk',r.Risk);e.metric('Confidence',r.Confidence)
            if fx:
                st.caption(f"Approx current INR value: ₹{r.Current*float(fx):,.2f} using the latest cached USD/INR reference. Technical calculations use the USDT price series.")
            L,R=st.columns(2)
            with L:
                st.write(f"**Entry:** ${r.EntryLow:,.4f} – ${r.EntryHigh:,.4f}")
                st.write(f"**Support:** S1 ${r.S1:,.4f} • S2 ${r.S2:,.4f}")
                st.write(f"**Resistance:** R1 ${r.R1:,.4f} • R2 ${r.R2:,.4f}")
                st.write(f"**🎯 Target 1:** ${r.Target1:,.4f} • {r['Potential1%']:+.1f}%")
                st.write(f"**🚀 Target 2:** ${r.Target2:,.4f} • {r['Potential2%']:+.1f}%")
                st.write(f"**🛑 Stop Loss:** ${r.StopLoss:,.4f} • Risk {r['Risk%']:+.1f}%")
                st.write(f"**⚖️ R:R:** {r.RR:.2f} • **⏳ Duration:** {r.Duration}")
                st.write(f"**Entry status:** {r.EntryStatus}")
            with R:
                st.progress(int(r.Technical),text=f"Technical {r.Technical:.0f}/100")
                st.progress(int(r.Momentum),text=f"Momentum {r.Momentum:.0f}/100")
                st.progress(int(r.Structure),text=f"Market Structure {r.Structure:.0f}/100")
                st.write('**Fundamental:** N/A — not faked for crypto')
                st.write(f"**Historical Signals:** {r.HistoricalSignals}")
                st.write(f"**Win Rate:** {r['WinRate%']}%" if pd.notna(r['WinRate%']) else '**Win Rate:** not established')
                st.write(f"**Risk:** {r.Risk} • **Confidence:** {r.Confidence}")
                st.markdown('#### Reason')
                for reason in str(r.Reason).split(' • '):
                    if reason.strip(): st.write('• '+reason.strip())
                st.markdown('#### What would change this recommendation?')
                st.write('• '+str(getattr(r,'WhatChanges','Trend, momentum, market structure, entry validity and Risk:Reward determine upgrades/downgrades.')))
            if not cchart.empty:
                st.line_chart(cchart.tail(180).set_index('Date')[[c for c in ['Close','EMA21','EMA50'] if c in cchart.columns]])

if active_page=='🪙 ETFs':
    e=radar[radar.Symbol.isin(CFG['etf_symbols'])].copy()
    if e.empty:
        st.info('No configured ETF symbols are present in current local data.')
    else:
        cat=st.radio('ETF horizon',['SWING','SHORT','LONG'],horizontal=True,key='etfcat')
        ex=e[e.Category==cat].sort_values(['Signal','Overall'],ascending=[True,False])
        st.dataframe(ex[['Symbol','Signal','EntryStatus','Confidence','Overall','Current','EntryLow','EntryHigh','Target1','Potential1%','Target2','Potential2%','StopLoss','RR','Duration','Technical','Momentum']],use_container_width=True,hide_index=True)
        esym=st.selectbox('ETF full card',ex.Symbol.drop_duplicates().tolist(),key='etf_full_sym')
        er=ex[ex.Symbol==esym].iloc[0]
        st.markdown(f"### {er.Signal} — {esym}")
        a,b,c,d=st.columns(4);a.metric('Current',f'₹{er.Current:,.2f}');b.metric('Overall',f'{er.Overall:.0f}/100');c.metric('R:R',f'{er.RR:.2f}');d.metric('Confidence',er.Confidence)
        st.write(f"**Entry:** ₹{er.EntryLow:,.2f}–₹{er.EntryHigh:,.2f} • **T1:** ₹{er.Target1:,.2f} ({er['Potential1%']:+.1f}%) • **T2:** ₹{er.Target2:,.2f} ({er['Potential2%']:+.1f}%) • **Stop:** ₹{er.StopLoss:,.2f}")
        st.markdown('#### Reason')
        etf_reasons=[]
        if er.Technical>=80:etf_reasons.append('Technical trend is strong')
        elif er.Technical>=70:etf_reasons.append('Technical trend passes')
        if er.Momentum>=80:etf_reasons.append('Momentum is strong')
        elif er.Momentum>=70:etf_reasons.append('Momentum passes')
        if er.RR>=2:etf_reasons.append('Risk:Reward is 2.0 or better')
        if er.EntryStatus=='ENTRY VALID':etf_reasons.append('Current price is inside the valid entry zone')
        if er.BacktestSample>=20 and pd.notna(er['BacktestWinRate%']):etf_reasons.append(f"Historical evidence: {int(er.BacktestSample)} signals, {er['BacktestWinRate%']}% win rate")
        for reason in etf_reasons or ['Current evidence is insufficient for a stronger ETF rating']:st.write('• '+reason)
        st.markdown('#### What would change this recommendation?')
        st.write('• Stronger trend/momentum, valid entry and better R:R can upgrade it; stretched entry, weaker trend or poor validation can downgrade it.')

if active_page=='💰 Mutual Funds':
    st.caption('The universe screen covers every scheme returned by the current AMFI Complete NAV feed, including Direct/Regular and Growth/IDCW variants. Deep return/risk analysis is fetched and cached only for the exact funds/categories you inspect, so the app remains usable instead of downloading thousands of full histories every day.')
    us=mf_universe_summary();u=cached_mf_universe()
    m1,m2,m3,m4=st.columns(4);m1.metric('MF universe',f"{us.get('schemes',0):,}");m2.metric('Fund houses',f"{us.get('fund_houses',0):,}");m3.metric('AMFI categories',f"{us.get('categories',0):,}");m4.metric('Direct plans',f"{us.get('direct',0):,}")
    if st.button('🔄 Refresh ALL Mutual Fund Universe (AMFI)',use_container_width=True,key='refresh_all_mf_universe'):
        with st.spinner('Refreshing the complete AMFI NAV universe...'):
            res=refresh_mf_universe()
        if res.get('ok'):
            st.success(res.get('message','Refresh finished.'))
        else:
            st.warning(res.get('message','Refresh finished.'))
        cloud_rerun()
    if u.empty:
        st.warning('Complete Mutual Fund universe is not cached yet. Click the refresh button above or run DAILY UPDATE.')
    else:
        st.markdown('### Find any Mutual Fund')
        f1,f2,f3,f4,f5=st.columns(5)
        mf_search=f1.text_input('Search scheme',key='mf_all_search')
        groups=['All']+sorted([x for x in u.CategoryGroup.dropna().astype(str).unique() if x])
        mf_group=f2.selectbox('Broad category',groups,key='mf_group')
        houses=['All']+sorted([x for x in u.FundHouse.dropna().astype(str).unique() if x])
        mf_house=f3.selectbox('Fund house / AMC',houses,key='mf_house')
        mf_plan=f4.selectbox('Plan',['All','Direct','Regular','Unspecified'],index=0,key='mf_plan')
        mf_option=f5.selectbox('Option',['All','Growth','IDCW','Dividend/IDCW','Other/Unspecified'],index=0,key='mf_option')
        # Detailed AMFI category remains available but hidden behind a simple select.
        cats=['All']+sorted([x for x in u.Category.dropna().astype(str).unique() if x and (mf_group=='All' or x in u[u.CategoryGroup.eq(mf_group)].Category.astype(str).unique())])
        mf_cat=st.selectbox('Specific AMFI category — optional',cats,key='mf_exact_cat')
        fu=filter_mf_universe(mf_search,mf_house,mf_cat,mf_group,mf_plan,mf_option)
        st.caption(f'{len(fu):,} matching scheme/plan rows — complete AMFI universe, not a top-fund sample.')
        cols=[c for c in ['SchemeCode','SchemeName','FundHouse','CategoryGroup','Category','Plan','Option','NAV','NAVDate','Source'] if c in fu.columns]
        if not fu.empty:
            pg1,pg2=st.columns([1,1])
            mf_page_size=pg1.selectbox('Rows per page',[100,250,500,1000],index=1,key='mf_page_size')
            mf_pages=max(1,int(np.ceil(len(fu)/mf_page_size)))
            mf_page=pg2.number_input('Page',min_value=1,max_value=mf_pages,value=1,step=1,key='mf_page')
            _start=(int(mf_page)-1)*int(mf_page_size);_end=min(_start+int(mf_page_size),len(fu))
            st.caption(f'Showing {_start+1:,}–{_end:,} of {len(fu):,} matching rows')
            st.dataframe(fu.iloc[_start:_end][cols],use_container_width=True,hide_index=True)
        if not fu.empty:
            labels=(fu.SchemeName.astype(str)+'  ['+fu.SchemeCode.astype(str)+']').tolist()
            chosen=st.selectbox('Exact Mutual Fund product',labels,key='mf_exact_product')
            code=chosen.rsplit('[',1)[-1].rstrip(']')
            c1,c2=st.columns(2)
            if c1.button('🔬 Analyze this exact fund now',use_container_width=True,key='mf_analyze_one'):
                with st.spinner('Downloading full NAV history and calculating return/risk evidence...'):
                    res=refresh_mf_scheme(code)
                if res.get('ok'):st.success('Exact fund analysis updated.')
                else:st.warning('Could not update this fund: '+res.get('message',''))
            if c2.button('🧠 Rank matching funds in this category/filter',use_container_width=True,key='mf_rank_filter'):
                with st.spinner('Building exact-product evidence for the current filter. This is cached for future use...'):
                    res=refresh_mf_filtered(mf_search,mf_house,mf_cat,mf_group,mf_plan,mf_option,max_funds=CFG.get('mf_deep_filter_max',40))
                st.success(res.get('message','Analysis finished.'))

        live_mf,live_mfd=analyze_cached()
        st.markdown('### Deep-analyzed / ranked funds')
        if live_mf.empty:
            st.info('Select an exact fund above and click Analyze, or rank the current filter. The complete universe is still searchable even before deep histories are downloaded.')
        else:
            view=live_mf.copy()
            if mf_group!='All' and 'CategoryGroup' in view:view=view[view.CategoryGroup.astype(str).eq(mf_group)]
            if mf_plan!='All' and 'Plan' in view:view=view[view.Plan.astype(str).eq(mf_plan)]
            if mf_option!='All' and 'Option' in view:view=view[view.Option.astype(str).eq(mf_option)]
            showcols=[c for c in ['Scheme','FundHouse','CategoryGroup','Category','Plan','Option','Action','NAV','NAVDate','Overall','Risk','Confidence','1Y%','3Y_CAGR%','5Y_CAGR%','Volatility%','MaxDrawdown%','PositiveMonths%'] if c in view.columns]
            st.dataframe(view[showcols],use_container_width=True,hide_index=True)
            if not view.empty:
                codes=view.Code.astype(str).tolist();dcode=st.selectbox('Full evidence card',codes,key='mfcode_all');d=live_mfd.get(str(dcode))
                if d:
                    r=d['row'];sc=d['scenarios'];st.markdown(f"## {r['Action']} — {r['Scheme']}")
                    a,b,c,d1=st.columns(4);a.metric('NAV',f"₹{r['NAV']:,.4f}");b.metric('Overall',f"{r['Overall']:.0f}/100");c.metric('Risk',r['Risk']);d1.metric('Confidence',r['Confidence'])
                    st.write(f"**Category:** {r.get('Category','')} • **Plan:** {r.get('Plan','')} • **Option:** {r.get('Option','')}")
                    st.write(f"**1Y:** {r['1Y%']}% • **3Y CAGR:** {r['3Y_CAGR%']}% • **5Y CAGR:** {r['5Y_CAGR%']}%")
                    st.markdown('#### Why this recommendation?')
                    for reason in str(r.get('Reason','')).split(' • '):
                        if reason.strip():st.write('• '+reason.strip())
                    st.markdown('#### What would change it?');st.write('• '+str(r.get('WhatChanges','Rolling returns, drawdown, consistency and momentum determine upgrades/downgrades.')))
                    sr=[]
                    for lab,v in sc.items():sr.append({'Duration':lab,'Downside/Low%':round(v['low'],2) if pd.notna(v['low']) else np.nan,'Base/Median%':round(v['median'],2) if pd.notna(v['median']) else np.nan,'Upside/High%':round(v['high'],2) if pd.notna(v['high']) else np.nan,'HistoricalSamples':v['sample']})
                    st.dataframe(pd.DataFrame(sr),use_container_width=True,hide_index=True);st.line_chart(d['series'].tail(1200))
                    st.caption('Historical ranges are evidence/scenarios, not guaranteed future returns. Expense ratio/AUM/portfolio-holdings data should only be used when a verified source is available; the app does not invent them.')

if active_page=='🏦 Fixed Income':
    edit=st.data_editor(load_bonds(),use_container_width=True,num_rows='dynamic')
    if st.button('Save Fixed-Income Inputs'):save_bonds(edit);st.success('Saved. Run REBUILD DASHBOARD ONLY to refresh fixed-income cache.')
    bx=analyze_bonds(edit);st.dataframe(bx,use_container_width=True,hide_index=True)
    if not bx.empty:
        bins=st.selectbox('Fixed-income full card',bx.Instrument.astype(str).tolist(),key='bond_full_card')
        br=bx[bx.Instrument.astype(str)==str(bins)].iloc[0]
        st.markdown(f"### {br.Action} — {br.Instrument}")
        a,b,c,d=st.columns(4)
        a.metric('Yield / YTM',f"{br['Yield%']:.2f}%" if pd.notna(br['Yield%']) else 'INPUT REQUIRED')
        b.metric('Overall',f'{br.Overall:.0f}/100' if pd.notna(br.Overall) else 'N/A')
        c.metric('Risk',br.Risk);d.metric('Maturity',f'{br.MaturityYears:.2f} years' if pd.notna(br.MaturityYears) else 'N/A')
        st.markdown('#### Reason')
        for reason in str(br.get('Reason','')).split(' • '):
            if reason.strip(): st.write('• '+reason.strip())
        st.markdown('#### What would change this recommendation?')
        st.write('• '+str(br.get('WhatChanges','Current YTM, credit quality, maturity risk and liquidity determine upgrades/downgrades.')))

if active_page=='🚀 IPO / New Issues':
    st.caption('Mainboard IPO, SME IPO and other public/new issues. The system separates listing-demand potential from long-term business quality.')
    st.warning('IPO outcomes are uncertain. GMP, when entered, is treated as an unofficial LOW-WEIGHT sentiment input — never the main reason to apply.')
    c1,c2,c3=st.columns(3)
    if c1.button('🔄 Refresh official NSE current issues',use_container_width=True):
        with st.spinner('Checking official NSE current-issues page...'):
            res=refresh_nse_ipos()
        if res.get('ok'):
            st.success(res.get('message','Refresh finished.'))
        else:
            st.warning(res.get('message','Refresh finished.'))
    c2.markdown('[Open official NSE IPO/current issues](https://www.nseindia.com/market-data/all-upcoming-issues-ipo)')
    c3.markdown('[Open SEBI public-issue filings](https://www.sebi.gov.in/filings/public-issues.html)')

    ipos=load_ipos()
    itabs=st.tabs(['📋 IPO Ranking','🧾 Full IPO Card','✏️ Add / Edit / Import'])
    with itabs[0]:
        if ipos.empty:
            st.info('No IPO data saved yet. Use Refresh NSE or Add/Edit/Import. NSE refresh can populate current issue names/dates/subscription where the official page is machine-readable; financial/valuation fields still need verified RHP/DRHP data.')
        else:
            ia=analyze_ipos(ipos)
            f=st.selectbox('Show IPOs',['ALL','OPEN','UPCOMING','CLOSED / OTHER'],key='ipo_filter')
            if f=='OPEN': ia=ia[ia.Status.astype(str).str.contains('OPEN',case=False,na=False)]
            elif f=='UPCOMING': ia=ia[ia.Status.astype(str).str.contains('UPCOMING',case=False,na=False)]
            elif f=='CLOSED / OTHER': ia=ia[~ia.Status.astype(str).str.contains('OPEN|UPCOMING',case=False,regex=True,na=False)]
            cols=['Company','IssueType','Board','Status','OpenDate','CloseDate','PriceLow₹','PriceHigh₹','LotSize','OneLotCost₹','TotalSub','QIBSub','RetailSub','ListingScore','LongTermScore','Overall','Decision','Risk','Confidence']
            st.dataframe(ia[[c for c in cols if c in ia.columns]],use_container_width=True,hide_index=True,height=520)
    with itabs[1]:
        ia=analyze_ipos(ipos)
        if ia.empty:
            st.info('Add or refresh an IPO first.')
        else:
            sel=st.selectbox('Select IPO',ia.Company.astype(str).tolist(),key='ipo_card')
            r=ia[ia.Company.astype(str)==str(sel)].iloc[0]
            icon={'STRONG APPLY':'🔥','APPLY':'🟢','WATCH':'🟡','AVOID':'🔴'}.get(r.Decision,'⚪')
            st.markdown(f'## {icon} {r.Decision} — {r.Company}')
            a,b,c,d,e=st.columns(5)
            a.metric('Overall',f'{r.Overall:.0f}/100');b.metric('Listing',f'{r.ListingScore:.0f}/100');c.metric('Long Term',f'{r.LongTermScore:.0f}/100');d.metric('Risk',r.Risk);e.metric('Confidence',r.Confidence)
            L,R=st.columns(2)
            with L:
                st.markdown('#### Issue / Application')
                st.write(f"**Type/Board:** {r.IssueType} / {r.Board}")
                st.write(f"**Status:** {r.Status}")
                st.write(f"**Open–Close:** {r.OpenDate} → {r.CloseDate}")
                st.write(f"**Price band:** ₹{r['PriceLow₹']} – ₹{r['PriceHigh₹']}")
                st.write(f"**Lot size:** {r.LotSize}")
                st.write(f"**One lot:** ₹{r['OneLotCost₹']:,.0f}" if pd.notna(r['OneLotCost₹']) else '**One lot:** data required')
                st.write(f"**Total subscription:** {r.TotalSub}x" if pd.notna(r.TotalSub) else '**Total subscription:** unavailable')
                st.write(f"**QIB / NII / Retail:** {r.QIBSub}x / {r.NIISub}x / {r.RetailSub}x")
            with R:
                st.markdown('#### Financial / Valuation Evidence')
                st.write(f"**PE vs Industry PE:** {r.PE} vs {r.IndustryPE}")
                st.write(f"**Revenue growth 3Y:** {r['RevenueGrowth3Y%']}%")
                st.write(f"**Profit growth 3Y:** {r['ProfitGrowth3Y%']}%")
                st.write(f"**ROE:** {r['ROE%']}% • **Debt/Equity:** {r.DebtEquity}")
                st.write(f"**Fresh issue / OFS:** ₹{r.FreshIssueCr}Cr / ₹{r.OFSCr}Cr")
                st.write(f"**GMP:** {r['GMP%']}% (unofficial/low weight)" if pd.notna(r['GMP%']) else '**GMP:** not used')
            st.markdown('#### Why this recommendation?')
            for z in str(r.Reason).split(' • '):
                if z.strip():st.write('• '+z.strip())
            st.markdown('#### What would change it?')
            for z in str(r.WhatChanges).split(' • '):
                if z.strip():st.write('• '+z.strip())
            budget=st.number_input('IPO budget ₹',min_value=1000.0,value=100000.0,step=10000.0,key='ipo_budget')
            if pd.notna(r['OneLotCost₹']) and r['OneLotCost₹']>0:
                lots=int(budget//r['OneLotCost₹'])
                st.info(f'At the upper price band, your entered budget can fund up to **{lots} lot(s)** / approximately ₹{lots*r["OneLotCost₹"]:,.0f}. This is a budget calculation, not an allotment guarantee.')
    with itabs[2]:
        st.markdown('### Add / edit verified IPO information')
        edit=st.data_editor(ipos if not ipos.empty else ipo_template(),use_container_width=True,num_rows='dynamic',height=520,key='ipo_editor')
        c1,c2,c3=st.columns(3)
        if c1.button('💾 Save IPO Data',use_container_width=True):
            save_ipos(edit);st.success('IPO data saved locally.');cloud_rerun()
        csv=ipo_template().to_csv(index=False).encode('utf-8-sig')
        c2.download_button('⬇️ Download IPO CSV Template',csv,'IPO_IMPORT_TEMPLATE.csv','text/csv',use_container_width=True)
        up=c3.file_uploader('Import IPO CSV/XLSX',type=['csv','xlsx','xls'],key='ipo_import')
        if up is not None:
            try:
                inc=pd.read_excel(up) if str(up.name).lower().endswith(('xlsx','xls')) else pd.read_csv(up)
                inc=normalize_ipos(inc)
                old=load_ipos()
                combo=pd.concat([old,inc],ignore_index=True).drop_duplicates('IPO_ID',keep='last') if not old.empty else inc
                save_ipos(combo);st.success(f'Imported {len(inc)} IPO row(s).');cloud_rerun()
            except Exception as e:st.error('IPO import failed: '+str(e))

if active_page=='🧭 Other Investments':
    st.caption('Complete non-stock investment directory: exact bank FDs where current public rates are available, all RBI-listed bank providers kept visible even when a rate needs verification, and current Post Office / Government small-savings rates.')
    opts=load_investment_options()
    tab_best,tab_fd,tab_po,tab_all=st.tabs(['🏆 Best Fit','🏦 FD / RD Directory','🏤 Post Office / Govt Savings','📚 Full Other-Investment Universe'])
    with tab_best:
        a,b,c=st.columns(3)
        amount=a.number_input('Amount to invest ₹',min_value=1000.0,value=100000.0,step=10000.0,key='other_amt')
        horizon=b.selectbox('Horizon',['6 Months','1 Year','3 Years','5 Years','10 Years','15+ Years'],index=3,key='other_horizon')
        years={'6 Months':.5,'1 Year':1,'3 Years':3,'5 Years':5,'10 Years':10,'15+ Years':15}[horizon]
        risk=c.selectbox('Risk profile',['LOW','MODERATE','HIGH'],index=1,key='other_risk')
        ranked=rank_investment_options(opts,amount,years,risk)
        st.markdown('### Best fit for the selected amount / horizon / risk')
        st.dataframe(ranked[[c for c in ['Option','Category','Provider/Instrument','RateOrExpectedReturn%','TenureYears','LockInYears','Risk','Liquidity','TaxEfficiency','MinInvestment₹','ActiveStatus','RateDate','DataConfidence','FitScore','Fit','Reason'] if c in ranked.columns]].head(300),use_container_width=True,hide_index=True,height=560)
        st.info('A high Fit Score means the product characteristics fit the profile you entered. It is not a promise of future performance. Exact FD rates must still be checked on the chosen bank page before booking.')
    with tab_fd:
        fd=load_fd_rates()
        x1,x2,x3=st.columns(3)
        q=x1.text_input('Search bank',key='fd_search')
        types=['All']+sorted(fd.BankType.dropna().astype(str).unique().tolist()) if not fd.empty else ['All']
        typ=x2.selectbox('Bank type',types,key='fd_type')
        prod=x3.selectbox('Tenure',['All','Highest published slab','1 Year','3 Years','5 Years'],key='fd_tenure')
        f=fd.copy()
        if q:f=f[f.Provider.astype(str).str.contains(re.escape(q),case=False,regex=True,na=False)]
        if typ!='All':f=f[f.BankType.astype(str).eq(typ)]
        if prod!='All':f=f[f.Product.astype(str).eq(prod)]
        if not f.empty:
            f['GeneralRate%']=pd.to_numeric(f['GeneralRate%'],errors='coerce')
            f=f.sort_values(['GeneralRate%','Provider'],ascending=[False,True],na_position='last')
        c1,c2,c3=st.columns(3)
        c1.metric('Bank/tenure rows',f'{len(f):,}')
        c2.metric('Rates available',f"{int(pd.to_numeric(f['GeneralRate%'],errors='coerce').notna().sum()) if not f.empty else 0:,}")
        c3.metric('Providers',f"{f.Provider.nunique() if not f.empty else 0:,}")
        if st.button('🔄 Refresh FD directory / public comparison rates',use_container_width=True,key='refresh_fd_directory'):
            with st.spinner('Refreshing FD comparison data and preserving the complete RBI bank universe...'):
                rr=refresh_fd_rates()
            st.success(rr.get('message','FD refresh complete.'));cloud_rerun()
        st.dataframe(f[[c for c in ['Provider','BankType','Product','GeneralRate%','SeniorRate%','RateDate','DataConfidence','Source','Notes'] if c in f.columns]],use_container_width=True,hide_index=True,height=620)
        st.caption('Missing rate ≠ missing bank. The bank remains in the directory as REVIEW REQUIRED until a current rate is verified. Final chosen FD should be checked on the bank official page.')
    with tab_po:
        po=load_small_savings().copy()
        if st.button('🔄 Refresh Post Office / small-savings rates',use_container_width=True,key='refresh_small_savings'):
            with st.spinner('Checking Government / India Post sources...'):
                rr=refresh_small_savings()
            st.success(rr.get('message','Small-savings refresh complete.'));cloud_rerun()
        st.dataframe(po,use_container_width=True,hide_index=True)
        st.caption('Current quarter rate/date and validity are shown. When the validity period ends, confidence is automatically reduced until the new quarter is verified.')
    with tab_all:
        st.markdown('### Full master list')
        edit=st.data_editor(opts,use_container_width=True,num_rows='dynamic',height=520,key='other_options_editor')
        if st.button('💾 Save Investment Option Inputs'):
            save_investment_options(edit);st.success('Saved locally.');cloud_rerun()
        st.markdown('''#### Permanent Master Investment Universe
- All RBI-listed public-sector, private-sector and small-finance-bank FD providers remain visible; current public comparison rates are filled where available.
- Bank savings / sweep FD / general FD / senior-citizen FD / Small Finance Bank FD / NBFC & corporate FD / tax-saving FD / Bank & Post Office RD
- Post Office Savings, 1Y/2Y/3Y/5Y Time Deposits, MIS, PPF, NSC, KVP, SCSS, Sukanya Samriddhi
- 91D/182D/364D T-Bills, dated G-Sec, SDL, RBI/government savings bonds
- Corporate bonds/NCDs and target-maturity debt products
- NPS Tier I/Tier II, EPF/VPF and annuity/retirement-income products where eligible
- REIT, InvIT, international funds/ETFs, secondary-market sovereign-gold instruments
- Physical Gold/Silver, real estate, PMS, AIF, SIF/specialized funds, unlisted/pre-IPO equity, P2P/private credit, insurance-linked products and collectibles

**Permanent rule:** nothing disappears merely because a free live source lacks a current value. The product remains visible as `REVIEW REQUIRED`; only verified/current data can become an actionable recommendation.''')

if active_page=='🔔 Alerts':
    st.caption('Generated after DAILY UPDATE: Strong Buy, valid entry, target/stop outcomes and market-regime changes.')
    alerts_df=load_alerts()
    if alerts_df.empty:st.info('No alerts yet. Alerts appear after daily updates and tracked outcomes.')
    else:st.dataframe(alerts_df.head(100),use_container_width=True,hide_index=True)

if active_page=='📊 Accuracy':
    tracked=read_log();perf=performance_summary(tracked);segperf=segmented_performance(tracked)
    st.subheader('Real Accuracy Dashboard')
    st.caption('This is measured from recommendations actually saved by your radar — not an invented accuracy claim.')
    if perf.empty:st.info('Forward performance will populate as recommendations resolve.')
    else:st.dataframe(perf,use_container_width=True,hide_index=True)
    if not segperf.empty:
        st.markdown('#### Which setups actually work best?');st.dataframe(segperf,use_container_width=True,hide_index=True)
    if not tracked.empty:
        st.markdown('#### Recommendation history');st.dataframe(tracked.sort_values('SavedAt',ascending=False).head(250),use_container_width=True,hide_index=True)
    cah=load_cross_asset_history()
    if not cah.empty:
        st.markdown('#### Cross-asset recommendation lifecycle')
        st.dataframe(cah.sort_values('SnapshotAt',ascending=False).head(250),use_container_width=True,hide_index=True)
        st.caption('This keeps a dated history of the across-asset snapshot so you can see how decisions changed over time.')

if active_page=='🧪 Validation':
    bt=load_backtest_stats();wf=load_walk_forward()
    st.subheader('Validation — Backtest + Walk-Forward')
    c1,c2=st.columns(2)
    with c1:
        st.markdown('#### Historical Backtest')
        if bt.empty:st.warning('Not built yet.')
        else:st.dataframe(bt,use_container_width=True,hide_index=True)
        if st.button('🧪 BUILD / REFRESH BACKTEST'):
            box=st.empty();h=load_history(max_sessions=CFG['history_sessions']);run_backtest(h,CFG['backtest_universe_size'],lambda x:box.caption(x));box.success('Backtest complete. Rebuild dashboard to apply new confidence evidence.')
    with c2:
        st.markdown('#### Walk-Forward Validation')
        if wf.empty:st.warning('Not built yet. This is stricter and can take several minutes.')
        else:st.dataframe(wf,use_container_width=True,hide_index=True)
        if st.button('🧭 BUILD WALK-FORWARD VALIDATION'):
            box=st.empty();h=load_history(max_sessions=CFG['history_sessions']);run_walk_forward(h,CFG['backtest_universe_size'],lambda x:box.caption(x));box.success('Walk-forward validation complete.')
    st.info('Walk-forward uses only information available at each historical signal date for indicators/liquidity, then evaluates future outcomes. This helps reduce misleading backtest optimism.')

if active_page=='🔄 Sync Center':
    st.caption('Current working data stays in the Radar/Supabase; Google Drive/Sheets is an optional archive/index layer. Secrets are never written to GitHub.')
    cs=cloud_status();cfs=cloud_full_status(BASE/'data');gs=google_status()
    a,b,c,d=st.columns(4);a.metric('Supabase','CONNECTED' if cs.get('enabled') else 'NOT CONFIGURED');b.metric('Cloud full data',str(cfs.get('status') or cfs.get('Status') or '—'));c.metric('Google archive','CONFIGURED' if gs.get('configured') else 'OPTIONAL');d.metric('Data Vault snapshots',len(snapshot_index()))
    st.markdown('### Supabase — PC + Cloud synchronization')
    st.write('Use the same SUPABASE_URL, SUPABASE_SECRET_KEY and SUPABASE_BUCKET on PC and Render. Never commit the secret key to GitHub.')
    s1,s2,s3=st.columns(3)
    if s1.button('Test Supabase',use_container_width=True,key='sync_test_supabase'):
        r=cloud_test_connection();(st.success if r.get('ok') else st.error)(r.get('message',str(r)))
    if s2.button('Upload full verified data',use_container_width=True,key='sync_push_full'):
        with st.spinner('Compressing and uploading changed data packs...'):
            r=cloud_push_full_data(BASE/'data',status_cb=lambda x:st.caption(str(x)))
        (st.success if r.get('ok') else st.warning)(r.get('message',str(r)))
    if s3.button('Download latest verified cloud data',use_container_width=True,key='sync_pull_full'):
        with st.spinner('Downloading and validating cloud data packs...'):
            r=cloud_pull_full_data(BASE/'data',force=True,status_cb=lambda x:st.caption(str(x)))
        (st.success if r.get('ok') else st.warning)(r.get('message',str(r)));clear_runtime_caches()
    st.markdown('### Google Drive archive + Google Sheet Data Index')
    st.info('PC easiest mode: select a Google Drive for Desktop synced folder. Cloud mode: use a Google service account and Render environment secrets. Google is archive/index — Supabase remains the live synchronization layer.')
    with st.form('google_sync_settings'):
        lc=st.text_input('Google Drive Desktop folder (PC mode)',value=gs.get('local_folder',''),placeholder=r'Example: G:\My Drive')
        df=st.text_input('Google Drive folder ID (API/cloud mode)',value=gs.get('drive_folder_id',''))
        sh=st.text_input('Google Sheet ID (optional; blank allows API mode to create one)',value=gs.get('sheet_id',''))
        sa=st.text_input('Service-account JSON file path (PC only)',value='',placeholder=r'Example: C:\Secure\radar-google.json')
        em=st.text_input('Share created Sheet with email (optional)',value='')
        ca=st.checkbox('Automatically archive complete data ZIP after Daily Update',value=bool(gs.get('auto_archive_after_update')))
        ci=st.checkbox('Automatically refresh Google Sheet Data Index after Daily Update',value=bool(gs.get('auto_update_sheet_index')))
        saveg=st.form_submit_button('Save Google archive settings',use_container_width=True)
    if saveg:
        vals={'local_drive_folder':lc,'drive_folder_id':df,'sheet_id':sh,'auto_archive_after_update':ca,'auto_update_sheet_index':ci}
        if sa.strip():vals['service_account_file']=sa.strip()
        if em.strip():vals['share_email']=em.strip()
        save_google_settings(vals);st.success('Google archive settings saved locally. No secret JSON was stored in GitHub.')
    g1,g2,g3=st.columns(3)
    if g1.button('Test Google connection',use_container_width=True,key='test_google_conn'):
        r=google_test_connection();(st.success if r.get('ok') else st.error)(r.get('message',str(r)))
    if g2.button('Archive complete data ZIP to Google',use_container_width=True,key='google_archive_now'):
        with st.spinner('Creating full verified data archive...'):
            z=data_vault_complete_archive(BASE/'data');r=google_archive_bytes('India_Investment_Radar_COMPLETE_DATA_'+pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')+'.zip',z,'application/zip')
        (st.success if r.get('ok') else st.error)(r.get('message',str(r)))
    if g3.button('Update Google Sheet Data Index',use_container_width=True,key='google_index_now'):
        r=google_update_sheet_index(data_vault_inventory(BASE/'data'),snapshot_index());(st.success if r.get('ok') else st.error)(r.get('message',str(r)))
    st.caption('Cloud secret option: set GOOGLE_SERVICE_ACCOUNT_JSON in Render as a private environment variable; also set GOOGLE_DRIVE_FOLDER_ID and optionally GOOGLE_SHEET_ID. Never put the JSON secret in the repository.')

if active_page=='🩺 System Check':
    st.dataframe(run_diagnostics(),use_container_width=True,hide_index=True)
    lb=latest_backup();st.write(f"**Latest local backup:** {lb.name if lb else 'Not created yet'}")
    st.write(f"**News gate:** {'AVAILABLE' if meta.get('news_gate_available') else 'UNAVAILABLE — Strong Buy is capped automatically'}")
    b1,b2=st.columns(2)
    if b1.button('💾 CREATE BACKUP NOW',use_container_width=True,key='backup_now'):
        try:
            bp=create_backup(CFG.get('backup_keep',12));st.success(f'Backup created: {bp.name}')
        except Exception as e:st.error('Backup failed: '+str(e))
    if b2.button('♻️ RESTORE LATEST BACKUP',use_container_width=True,key='restore_latest'):
        st.session_state['confirm_restore_backup']=True
    if st.session_state.get('confirm_restore_backup'):
        st.warning('Restore replaces saved user settings/data with the latest backup copy. A safety backup is attempted first.')
        r1,r2=st.columns(2)
        if r1.button('YES — RESTORE',use_container_width=True,key='restore_yes'):
            res=restore_backup();st.session_state['confirm_restore_backup']=False
            if res.get('ok'):st.success(res.get('message'));st.cache_data.clear();cloud_rerun()
            else:st.error(res.get('message'))
        if r2.button('Cancel',use_container_width=True,key='restore_no'):
            st.session_state['confirm_restore_backup']=False;cloud_rerun()
    st.caption('For dependency/shortcut repair, run REPAIR_INSTALLATION.bat from the final setup package. It does not delete your data.')

if active_page=='⚙️ Settings':
    st.success('⚡ Full Function + Fast Runtime is ON. Appearance, background and default landing page are no-code configurable.')

    st.markdown('### 🎨 Appearance & UI Configuration')
    cur=load_ui_settings()
    c1,c2,c3=st.columns(3)
    ui_preset=c1.selectbox('Theme preset',list(UI_PRESETS.keys()),index=max(0,list(UI_PRESETS.keys()).index(cur.get('theme_preset','Professional Navy'))) if cur.get('theme_preset') in UI_PRESETS else 0,key='ui_theme_preset')
    ui_bg=c2.selectbox('Background',['Abstract Market','Gradient','Solid','Custom Image','None'],index=['Abstract Market','Gradient','Solid','Custom Image','None'].index(cur.get('background_mode','Abstract Market')) if cur.get('background_mode') in ['Abstract Market','Gradient','Solid','Custom Image','None'] else 0,key='ui_bg_mode')
    ui_density=c3.selectbox('Density',['Compact','Comfortable','Spacious'],index=['Compact','Comfortable','Spacious'].index(cur.get('density','Comfortable')) if cur.get('density') in ['Compact','Comfortable','Spacious'] else 1,key='ui_density')
    d1,d2,d3,d4=st.columns(4)
    ui_scale=d1.slider('Font scale',0.85,1.25,float(cur.get('font_scale',1.0)),0.05,key='ui_font_scale')
    ui_radius=d2.slider('Card / button roundness',6,28,int(cur.get('radius',14)),1,key='ui_radius')
    ui_card=d3.slider('Card opacity',0.75,1.0,float(cur.get('card_opacity',0.97)),0.01,key='ui_card_opacity')
    ui_analysis_bg=d4.checkbox('Show decorative background on analysis pages',value=bool(cur.get('show_background_on_analysis_pages',False)),key='ui_analysis_bg')
    ui_default=st.selectbox('Default page when Radar opens',['📣 Daily Recommendations','🏠 Home','💰 Best Use of My Money','💼 My Portfolio','🔥 ACTION BOARD'],index=['📣 Daily Recommendations','🏠 Home','💰 Best Use of My Money','💼 My Portfolio','🔥 ACTION BOARD'].index(cur.get('default_page','📣 Daily Recommendations')) if cur.get('default_page') in ['📣 Daily Recommendations','🏠 Home','💰 Best Use of My Money','💼 My Portfolio','🔥 ACTION BOARD'] else 0,key='ui_default_page')

    if ui_bg=='Custom Image':
        uploaded_bg=st.file_uploader('Upload background image (PNG/JPG/WEBP)',type=['png','jpg','jpeg','webp'],key='ui_bg_upload')
        b1,b2,b3=st.columns(3)
        ui_overlay=b1.slider('Dark overlay',0.0,0.85,float(cur.get('background_overlay',0.0)),0.05,key='ui_bg_overlay')
        ui_blur=b2.slider('Card/background blur',0,12,int(cur.get('background_blur',0)),1,key='ui_bg_blur')
        ui_opacity=b3.slider('Background visual strength',0.02,0.50,float(cur.get('background_opacity',0.12)),0.02,key='ui_bg_opacity')
    else:
        uploaded_bg=None;ui_overlay=float(cur.get('background_overlay',0.0));ui_blur=int(cur.get('background_blur',0));ui_opacity=float(cur.get('background_opacity',0.12))

    if ui_preset=='Custom':
        base=dict(UI_PRESETS.get('Professional Navy',{}));base.update(cur.get('custom_colors') or {})
        st.caption('Custom colours apply instantly after Save UI Settings.')
        cc1,cc2,cc3,cc4=st.columns(4)
        cp=cc1.color_picker('Primary',base.get('primary','#0A1426'),key='ui_cp_primary')
        ca=cc2.color_picker('Accent',base.get('accent','#C7A552'),key='ui_cp_accent')
        cb=cc3.color_picker('Background',base.get('app_bg','#F4F7FB'),key='ui_cp_bg')
        ci=cc4.color_picker('Text',base.get('ink','#172033'),key='ui_cp_ink')
        custom_colors=dict(base);custom_colors.update({'primary':cp,'primary2':cp,'accent':ca,'app_bg':cb,'ink':ci})
    else:custom_colors=cur.get('custom_colors') or {}

    s1,s2=st.columns(2)
    if s1.button('💾 SAVE UI SETTINGS',type='primary',use_container_width=True,key='save_ui_settings_btn'):
        new=dict(cur);new.update({'theme_preset':ui_preset,'background_mode':ui_bg,'density':ui_density,'font_scale':ui_scale,'radius':ui_radius,'card_opacity':ui_card,'show_background_on_analysis_pages':ui_analysis_bg,'default_page':ui_default,'background_overlay':ui_overlay,'background_blur':ui_blur,'background_opacity':ui_opacity,'custom_colors':custom_colors})
        if uploaded_bg is not None:new['background_path']=save_background(uploaded_bg)
        save_ui_settings(new);st.success('UI settings saved. They will persist after restart/update.');cloud_rerun()
    if s2.button('↩ RESET PROFESSIONAL DEFAULT',use_container_width=True,key='reset_ui_settings_btn'):
        clear_background();reset_ui_settings();st.success('Professional default restored.');cloud_rerun()

    with st.expander('Optional Fundamentals Provider — Advanced',expanded=False):
        key=load_local_api_key()
        if key:
            st.success('Alpha Vantage key is stored locally.')
            if st.button('Refresh fundamentals for leading stocks'):
                syms=radar.sort_values('Overall',ascending=False).Symbol.unique().tolist();st.write(refresh_fundamentals(syms,key,CFG['alpha_refresh_symbols_per_run']));st.info('Then use Maintenance → Rebuild saved dashboard.')
        else:st.info('Alpha Vantage is optional. The core Radar does not require a paid AI/API subscription.')
        nk=st.text_input('NEW Alpha Vantage key (local PC only)',type='password')
        if st.button('Save NEW key locally') and nk.strip():save_local_api_key(nk.strip());st.success('Saved locally.')

    with st.expander('Recommendation Rules — Read Only',expanded=False):
        st.markdown('''**Strong Buy strict gate**
- Overall ≥ 85 • Technical ≥ 80 • Momentum ≥ 80 • R:R ≥ 2.0
- Historical + walk-forward evidence passes
- Long-term calls require fresh quality fundamentals
- Market not WEAK • entry valid • event/news gates pass • confidence HIGH

If a gate fails, the system downgrades rather than forcing Strong Buy.''')

    with st.expander('Free-first / no-surprise-charge policy',expanded=False):
        st.json(no_paid_usage_policy())
        st.caption('A third-party provider can change its free plan later. The Radar is designed to preserve local data and allow source/server replacement instead of silently buying a paid plan.')

    with st.expander('Performance behaviour',expanded=False):
        st.write('• All functions remain available; saved dashboard data is reused instead of recalculating on every click.')
        st.write('• Daily Update shows each running step and preserves last verified cache when an optional source fails.')
        st.write('• Money Optimizer and Go by Segment calculate only when Find is pressed, then reuse the result.')
        st.write('• Portfolio prices refresh on Daily Update or the explicit refresh button.')
        st.write('• Analysis pages can keep a clean background while Daily/Home uses the premium visual background.')


# ----------------- Corporate Events -----------------
if active_page=='📅 Corporate Events':
    st.caption('Combines official NSE corporate actions, board meetings, corporate announcements, financial-result filings and the NSE event calendar. Events are classified as INFO / REVIEW / BLOCK and fed back into stock recommendation safety.')
    if st.button('🔄 Refresh ALL Corporate Events',use_container_width=True,key='refresh_all_corp_events'):
        with st.spinner('Refreshing all NSE corporate-event families...'):
            res=refresh_all_events(CFG.get('corporate_events_back_days',45),CFG.get('corporate_events_forward_days',120))
        if res.get('ok'):
            st.success(res.get('message','Refresh finished.'))
        else:
            st.warning(res.get('message','Refresh finished.'))
        cloud_rerun()
    ev=cached_events()
    if ev.empty:
        st.warning('Corporate-event cache is empty. Click refresh above or run DAILY UPDATE.')
    else:
        # Add one normalized date for filtering/sorting.
        evx=ev.copy()
        def _evdate(r):
            for c in ['EventDate','ExDate','RecordDate','AnnouncementDate']:
                x=pd.to_datetime(r.get(c,''),dayfirst=True,errors='coerce')
                if pd.notna(x):return x
            return pd.NaT
        evx['_Date']=evx.apply(_evdate,axis=1)
        today=pd.Timestamp.today().normalize();evx['_Days']=(evx['_Date']-today).dt.days
        a,b,c,d=st.columns(4)
        a.metric('Cached events',f'{len(evx):,}');b.metric('Next 7 days',f"{int(((evx._Days>=0)&(evx._Days<=7)).sum()):,}")
        c.metric('Review',f"{int(evx.Severity.astype(str).eq('REVIEW').sum()):,}");d.metric('Block/Critical',f"{int(evx.Severity.astype(str).eq('BLOCK').sum()):,}")
        q1,q2,q3,q4=st.columns(4)
        symq=q1.text_input('Symbol/company search',key='event_symbol_search').strip().upper()
        types=['All']+sorted(evx.EventType.dropna().astype(str).unique().tolist());etype=q2.selectbox('Event type',types,key='event_type_filter')
        sev=q3.selectbox('Severity',['All','BLOCK','REVIEW','INFO'],key='event_sev_filter')
        window=q4.selectbox('Window',['Upcoming 7 Days','Upcoming 30 Days','Upcoming 120 Days','Past 30 Days','All Cached'],index=1,key='event_window')
        f=evx.copy()
        if symq:f=f[f.Symbol.astype(str).str.upper().str.contains(re.escape(symq),regex=True,na=False)|f.Company.astype(str).str.upper().str.contains(re.escape(symq),regex=True,na=False)]
        if etype!='All':f=f[f.EventType.astype(str).eq(etype)]
        if sev!='All':f=f[f.Severity.astype(str).eq(sev)]
        if window=='Upcoming 7 Days':f=f[(f._Days>=0)&(f._Days<=7)]
        elif window=='Upcoming 30 Days':f=f[(f._Days>=0)&(f._Days<=30)]
        elif window=='Upcoming 120 Days':f=f[(f._Days>=0)&(f._Days<=120)]
        elif window=='Past 30 Days':f=f[(f._Days<0)&(f._Days>=-30)]
        f=f.sort_values(['_Date','Severity'],ascending=[True,True],na_position='last')
        show=[c for c in ['Symbol','Company','EventType','Subject','EventDate','ExDate','RecordDate','AnnouncementDate','Severity','SystemAction','Source'] if c in f.columns]
        st.dataframe(f[show].head(2000),use_container_width=True,hide_index=True)
        # Holdings/recommendation impact
        owned=set()
        try:
            pf=read_portfolio()
            if not pf.empty and 'SymbolOrScheme' in pf.columns:owned=set(pf.SymbolOrScheme.astype(str).str.upper())
        except Exception:pass
        recsyms=set(radar[radar.Signal.astype(str).isin(['STRONG BUY','BUY','BUY ON PULLBACK'])].Symbol.astype(str).str.upper())
        impacted=f[f.Symbol.astype(str).str.upper().isin(owned|recsyms)] if (owned or recsyms) else f.iloc[0:0]
        if not impacted.empty:
            st.markdown('### Events affecting your holdings / current Buy candidates')
            st.dataframe(impacted[show].head(100),use_container_width=True,hide_index=True)
        st.markdown('### How the event gate is used')
        st.write('• **BLOCK** — serious adverse/regulatory/default-type event: fresh Buy is blocked until reviewed.')
        st.write('• **REVIEW** — results, important board meeting, rights/buyback/merger/demerger, major management/auditor/rating/pledge/legal event, or price-adjusting corporate action: Strong Buy is suppressed and the user is told to review/rebuild levels as applicable.')
        st.write('• **INFO** — routine dividend/meeting/filing information: shown for awareness without automatically treating it as bad news.')
        st.caption('NSE filing endpoints can change. Data-health messages remain visible and stale/missing event data is never silently treated as current.')


# ----------------- Data Vault -----------------
if active_page=='🗄️ Data Vault':
    st.caption('Historical/reference export center. Secrets are deliberately excluded from downloadable archives.')
    inv=data_vault_inventory(BASE/'data')
    a,b,c=st.columns(3);a.metric('Saved data files',f'{len(inv):,}');b.metric('Saved size',f"{inv.Bytes.sum()/1024/1024:.1f} MB" if not inv.empty else '0 MB');c.metric('Cloud full-data', 'CONNECTED' if cloud_status().get('enabled') else 'LOCAL ONLY')
    with st.expander('Saved data inventory',expanded=False):
        if inv.empty:st.info('No saved datasets yet.')
        else:st.dataframe(inv,use_container_width=True,hide_index=True,height=500)
    st.markdown('### Individual NSE stock — Excel')
    _h=cached_history(CFG['history_sessions']) if _core_ready else pd.DataFrame();_syms=sorted(_h.Symbol.astype(str).unique()) if not _h.empty and 'Symbol' in _h.columns else []
    if _syms:
        _sym=st.selectbox('Stock',_syms,key='vault_stock')
        _ev=cached_events();_an=load_announcements();_pn=load_stock_news(_sym)
        _xlsx=data_vault_stock_excel(_sym,_h,radar,_ev,_an,_pn)
        st.download_button('⬇ Download '+_sym+' complete Excel',data=_xlsx,file_name=f'{_sym}_Investment_Radar_History.xlsx',mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',use_container_width=True)
    else:st.info('NSE history is not ready yet. Run Full Data Setup / Repair.')
    st.markdown('### Reference tables — Excel')
    _sheets={'Current Stock Radar':radar,'Mutual Funds':load_mf_universe(),'FD Rates':load_fd_rates(),'Post Office Savings':load_small_savings(),'FII DII':load_fii_dii(),'Market News':load_market_news(),'Corporate Events':cached_events()}
    _ref=data_vault_category_excel(_sheets)
    st.download_button('⬇ Download current reference tables',data=_ref,file_name='India_Investment_Radar_Reference_Tables.xlsx',mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',use_container_width=True)
    st.markdown('### Complete Data Archive')
    st.warning('A full archive can be large because it contains the saved NSE/MF/history caches. Create it only when you actually need a full offline copy.')
    if st.button('📦 Prepare Complete Data Archive',use_container_width=True,key='prepare_vault_archive'):
        with st.spinner('Compressing verified Radar data...'):st.session_state['vault_archive']=data_vault_complete_archive(BASE/'data')
    if st.session_state.get('vault_archive'):
        st.download_button('⬇ Download Complete Radar Data ZIP',data=st.session_state['vault_archive'],file_name='India_Investment_Radar_COMPLETE_DATA.zip',mime='application/zip',use_container_width=True)
    st.caption('For anywhere viewing, use Radar itself. Excel is the portable/offline reference format; large raw history stays in the data archive/Supabase rather than being forced into one oversized Google Sheet.')
    st.markdown('### Dated Recommendation / Intelligence Snapshots')
    _snap=snapshot_index()
    if _snap.empty:st.info('No dated snapshot yet. The next successful recommendation rebuild will archive the actual known state automatically.')
    else:st.dataframe(_snap.head(400),use_container_width=True,hide_index=True)
    if _syms:
        _hist_snap=instrument_snapshot_history(_sym)
        with st.expander(f'{_sym} — what Radar actually knew/recommended on each saved date',expanded=False):
            if _hist_snap.empty:st.info('No dated snapshots for this instrument yet.')
            else:st.dataframe(_hist_snap,use_container_width=True,hide_index=True)

# ----------------- Auto Data Center -----------------
if active_page=='🧠 Auto Data Center':
    st.caption('See freshness, source hierarchy, fallback/cooldown state and exactly what can or cannot be trusted before relying on a recommendation.')
    dh,health_score=cached_data_health();a1,a2,a3,a4=st.columns(4);a1.metric('Overall data health',f'{health_score:.0f}%');a2.metric('Needs attention',int(dh.Status.isin(['MISSING','STALE','OLD','PARTIAL']).sum()) if not dh.empty else 0);a3.metric('Fresh / current',int(dh.Status.isin(['FRESH','MANUAL']).sum()) if not dh.empty else 0);a4.metric('Automatic paid usage','OFF')
    st.dataframe(dh,use_container_width=True,hide_index=True);need=data_action_needed(dh)
    if not need.empty:
        st.markdown('### What needs attention?');st.dataframe(need[['Data','Status','Age','Source','Fallback','Detail']],use_container_width=True,hide_index=True)
    st.markdown('### Source Registry — free first, replaceable')
    regdf=load_source_registry();st.dataframe(regdf,use_container_width=True,hide_index=True)
    with st.expander('Edit source priority/notes — advanced',expanded=False):
        regedit=st.data_editor(regdf,use_container_width=True,num_rows='dynamic',key='source_registry_editor')
        if st.button('💾 Save Source Registry',key='save_source_registry_btn'):
            save_source_registry(regedit);st.success('Source registry saved locally.');cloud_rerun()
    runtime=source_runtime_status()
    if runtime is not None and not runtime.empty:
        st.markdown('### Recent source attempts / cooldowns')
        st.dataframe(runtime,use_container_width=True,hide_index=True)
        st.caption('When a source is rate-limited or temporarily failing, the Radar stores the cooldown/failure state instead of repeatedly hammering the same source.')
    st.markdown('### Permanent trust rule');st.write('• Official/verified data is preferred whenever available.');st.write('• Free alternative / last verified cache is used when appropriate; paid usage is never started automatically.');st.write('• Market proxy / indicative data is clearly labelled and is not presented as an exact local transaction quote.');st.write('• Manual inputs remain only where a universal reliable live feed is not available.');st.write('• Stale/missing critical data must reduce recommendation confidence or block a high-confidence call.');st.write('• Last valid cache is preserved so a temporary source outage does not erase the system.');st.info('Use DAILY UPDATE for the normal refresh cycle. It now shows every running step, PASS/WARNING/FAIL status and preserves verified cache if an optional source fails.')


# Persist critical user-created state when cloud storage is configured.
try:
    cloud_push_changed(BASE/'data')
except Exception:
    pass
