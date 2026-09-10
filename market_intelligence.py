from __future__ import annotations

from pathlib import Path
from datetime import datetime, date, timedelta
from io import BytesIO, StringIO
from urllib.parse import urljoin
import json
import math
import re
import time
import urllib.parse
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd
import requests

BASE = Path(__file__).resolve().parent
DIR = BASE / 'data' / 'market_intelligence'
DIR.mkdir(parents=True, exist_ok=True)
RAW = DIR / 'raw'
RAW.mkdir(parents=True, exist_ok=True)

FLOWS = DIR / 'fii_dii.csv'
NEWS = DIR / 'market_news.csv'
META = DIR / 'meta.json'
DERIV_HISTORY = DIR / 'derivatives_history.csv'
DERIV_OI = DIR / 'participant_oi_latest.csv'
DERIV_VOL = DIR / 'participant_volume_latest.csv'
BREADTH_HISTORY = DIR / 'breadth_history.csv'
DELIVERY = DIR / 'delivery_latest.csv'
INDEX_VALUATION = DIR / 'index_valuation_latest.csv'
SURVEILLANCE = DIR / 'surveillance_latest.csv'
BULK_DEALS = DIR / 'bulk_deals_latest.csv'
BLOCK_DEALS = DIR / 'block_deals_latest.csv'
SHORT_SELLING = DIR / 'short_selling_latest.csv'
SECTOR_FPI = DIR / 'fpi_sector_latest.csv'
SIP_HISTORY = DIR / 'amfi_sip_history.csv'

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36',
    'Accept': 'application/json,text/plain,text/csv,*/*',
    'Referer': 'https://www.nseindia.com/'
}

DEFAULT_NEWS_TOPICS = [
    'India stock market Nifty Sensex',
    'RBI India interest rates inflation',
    'India rupee crude oil market',
    'India mutual funds AMFI',
    'India IPO market',
    'India gold silver prices'
]
NEG = ('CRASH', 'FRAUD', 'DEFAULT', 'INSOLVENCY', 'NCLT', 'WAR', 'SANCTION', 'DOWNGRADE', 'PLUNGE',
       'SELL-OFF', 'SELL OFF', 'RECESSION', 'RAID', 'PENALTY', 'BAN', 'PROBE', 'SEIZURE')
POS = ('RECORD HIGH', 'UPGRADE', 'BEATS ESTIMATES', 'STRONG GROWTH', 'RATE CUT', 'INFLOW', 'RALLY',
       'SURGE', 'EXPANSION', 'ORDER WIN', 'BUYBACK')


def _num(v):
    try:
        if v is None:
            return np.nan
        s = str(v).replace(',', '').replace('₹', '').replace('%', '').strip()
        if not s or s.lower() in ('nan', 'none', '-', '--', 'na', 'n/a'):
            return np.nan
        return float(s)
    except Exception:
        return np.nan


def _date(v):
    try:
        x = pd.to_datetime(v, dayfirst=True, errors='coerce')
        return '' if pd.isna(x) else x.date().isoformat()
    except Exception:
        return ''


def _session():
    s = requests.Session()
    try:
        s.get('https://www.nseindia.com/', headers=HEADERS, timeout=12)
    except Exception:
        pass
    return s


def _save_meta(key: str, result: dict):
    d = {}
    if META.exists():
        try:
            d = json.loads(META.read_text(encoding='utf-8'))
        except Exception:
            d = {}
    d['updated_at'] = pd.Timestamp.now().isoformat(timespec='seconds')
    d[key] = result
    try:
        META.write_text(json.dumps(d, indent=2, default=str), encoding='utf-8')
    except Exception:
        pass


def meta():
    if not META.exists():
        return {}
    try:
        return json.loads(META.read_text(encoding='utf-8'))
    except Exception:
        return {}


def _recent_weekdays(max_days=8):
    out = []
    d = date.today()
    for _ in range(max_days * 2):
        if d.weekday() < 5:
            out.append(d)
            if len(out) >= max_days:
                break
        d -= timedelta(days=1)
    return out


def _request_bytes(urls, timeout=25):
    errors = []
    for url in urls:
        try:
            r = requests.get(url, headers=HEADERS, timeout=timeout)
            if r.status_code == 200 and r.content and len(r.content) > 10:
                return r.content, url
            errors.append(f'{url}: HTTP {r.status_code}')
        except Exception as e:
            errors.append(f'{url}: {e}')
    raise RuntimeError(' | '.join(errors[-3:]) if errors else 'No source URL succeeded')


def _read_csv_loose(raw: bytes, skiprows_options=(0, 1, 2)):
    last = None
    for skip in skiprows_options:
        for enc in ('utf-8-sig', 'utf-8', 'latin1'):
            try:
                df = pd.read_csv(BytesIO(raw), skiprows=skip, encoding=enc, engine='python')
                if df is not None and not df.empty and len(df.columns) >= 2:
                    # Discard fully empty unnamed columns.
                    df = df.dropna(axis=1, how='all')
                    if len(df.columns) >= 2:
                        return df
            except Exception as e:
                last = e
    # Some NSE .DAT files are delimited text with a title row.
    try:
        text = raw.decode('latin1', errors='ignore')
        for sep in (',', '|', ';', '\t'):
            lines = [ln for ln in text.splitlines() if ln.strip()]
            for start in range(min(6, len(lines))):
                try:
                    df = pd.read_csv(StringIO('\n'.join(lines[start:])), sep=sep, engine='python')
                    df = df.dropna(axis=1, how='all')
                    if not df.empty and len(df.columns) >= 2:
                        return df
                except Exception:
                    pass
    except Exception:
        pass
    raise RuntimeError(f'Unable to parse downloaded table{": " + str(last) if last else ""}')


def _append_dedup(path: Path, new: pd.DataFrame, keys: list[str]):
    if new is None or new.empty:
        return pd.DataFrame()
    old = pd.DataFrame()
    if path.exists():
        try:
            old = pd.read_csv(path)
        except Exception:
            old = pd.DataFrame()
    out = pd.concat([old, new], ignore_index=True, sort=False) if not old.empty else new.copy()
    valid_keys = [k for k in keys if k in out.columns]
    if valid_keys:
        out = out.drop_duplicates(valid_keys, keep='last')
    out.to_csv(path, index=False)
    return out


# ---------------------------------------------------------------------------
# FII / FPI / DII cash market
# ---------------------------------------------------------------------------

def refresh_fii_dii(status_cb=None):
    """Fetch official NSE provisional FII/FPI & DII cash-market activity and append history.

    NSE states that same-day FII/FPI figures are provisional. We deliberately retain the
    PROVISIONAL label instead of presenting it as final depository-confirmed FPI data.
    """
    if status_cb:
        status_cb('FII/DII: initializing NSE session...')
    try:
        s = _session()
        if status_cb:
            status_cb('FII/DII: downloading official NSE institutional activity...')
        r = s.get('https://www.nseindia.com/api/fiidiiTradeReact', headers={**HEADERS, 'Referer': 'https://www.nseindia.com/reports/fii-dii'}, timeout=25)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, dict):
            data = data.get('data') or data.get('records') or [data]
        if not isinstance(data, list):
            data = []
        rows = []
        for x in data:
            if not isinstance(x, dict):
                continue
            cat = str(x.get('category') or x.get('Category') or x.get('clientType') or '').strip().upper()
            dt = _date(x.get('date') or x.get('Date') or x.get('tradeDate'))
            buy = _num(x.get('buyValue') or x.get('buyvalue') or x.get('buy'))
            sell = _num(x.get('sellValue') or x.get('sellvalue') or x.get('sell'))
            net = _num(x.get('netValue') or x.get('netvalue') or x.get('net'))
            if cat:
                if pd.isna(net) and pd.notna(buy) and pd.notna(sell):
                    net = buy - sell
                rows.append({'Date': dt, 'Category': cat, 'Buy₹Cr': buy, 'Sell₹Cr': sell, 'Net₹Cr': net,
                             'Status': 'PROVISIONAL', 'Source': 'NSE FII/DII'})
            else:
                for label, prefix in [('FII/FPI', 'fii'), ('DII', 'dii')]:
                    b = _num(x.get(prefix + 'buy') or x.get(prefix + 'Buy'))
                    se = _num(x.get(prefix + 'sell') or x.get(prefix + 'Sell'))
                    n = _num(x.get(prefix + 'net') or x.get(prefix + 'Net'))
                    if pd.notna(n) or pd.notna(b) or pd.notna(se):
                        if pd.isna(n) and pd.notna(b) and pd.notna(se):
                            n = b - se
                        rows.append({'Date': dt, 'Category': label, 'Buy₹Cr': b, 'Sell₹Cr': se, 'Net₹Cr': n,
                                     'Status': 'PROVISIONAL', 'Source': 'NSE FII/DII'})
        new = pd.DataFrame(rows)
        if new.empty:
            raise RuntimeError('NSE returned no parseable FII/DII rows')
        new['Date'] = new['Date'].astype(str)
        new['Category'] = new['Category'].astype(str).str.upper()
        out = _append_dedup(FLOWS, new, ['Date', 'Category']).sort_values(['Date', 'Category'])
        out.to_csv(FLOWS, index=False)
        res = {'ok': True, 'count': len(new), 'status': 'PROVISIONAL',
               'message': f'FII/DII refreshed: {len(new)} official NSE row(s); same-day FII/FPI values remain provisional.'}
    except Exception as e:
        res = {'ok': False, 'count': 0, 'status': 'FALLBACK' if FLOWS.exists() else 'MISSING',
               'message': 'FII/DII refresh unavailable: ' + str(e) + '; last verified cache preserved.'}
    _save_meta('fii_dii', res)
    return res


def load_fii_dii():
    if FLOWS.exists():
        try:
            return pd.read_csv(FLOWS)
        except Exception:
            pass
    return pd.DataFrame(columns=['Date', 'Category', 'Buy₹Cr', 'Sell₹Cr', 'Net₹Cr', 'Status', 'Source'])


def _flow_regime(v1, v5, v20, v60, who='FII'):
    vals = [x for x in (v1, v5, v20, v60) if pd.notna(x)]
    if not vals:
        return 'UNAVAILABLE'
    # Longer windows matter more than one-day noise.
    signs = 0
    for v, w in ((v1, 1), (v5, 2), (v20, 3), (v60, 3)):
        if pd.notna(v):
            signs += w if v > 0 else (-w if v < 0 else 0)
    if signs >= 6:
        return 'STRONG ACCUMULATION' if who == 'FII' else 'STRONG SUPPORT'
    if signs >= 2:
        return 'ACCUMULATION' if who == 'FII' else 'SUPPORTIVE'
    if signs <= -6:
        return 'STRONG DISTRIBUTION' if who == 'FII' else 'STRONG SELLING'
    if signs <= -2:
        return 'DISTRIBUTION' if who == 'FII' else 'SELLING'
    return 'NEUTRAL / MIXED'


def institutional_summary(df=None):
    d = load_fii_dii() if df is None else df
    empty = {'Bias': 'UNAVAILABLE', 'LatestDate': '', 'FIINet₹Cr': np.nan, 'DIINet₹Cr': np.nan,
             'FII5D₹Cr': np.nan, 'DII5D₹Cr': np.nan, 'FII20D₹Cr': np.nan, 'DII20D₹Cr': np.nan,
             'FII60D₹Cr': np.nan, 'DII60D₹Cr': np.nan, 'FIIRegime': 'UNAVAILABLE',
             'DIIRegime': 'UNAVAILABLE', 'Score': np.nan, 'Explanation': 'Institutional-flow history unavailable.'}
    if d is None or d.empty:
        return empty
    x = d.copy()
    x['Net₹Cr'] = pd.to_numeric(x.get('Net₹Cr'), errors='coerce')
    x['DateParsed'] = pd.to_datetime(x.get('Date'), errors='coerce')
    x = x.dropna(subset=['DateParsed'])
    if x.empty:
        return empty
    piv = x.pivot_table(index='DateParsed', columns='Category', values='Net₹Cr', aggfunc='last').sort_index()
    fii_col = next((c for c in piv.columns if 'FII' in str(c).upper() or 'FPI' in str(c).upper()), None)
    dii_col = next((c for c in piv.columns if 'DII' in str(c).upper()), None)
    fii = piv[fii_col] if fii_col is not None else pd.Series(dtype=float)
    dii = piv[dii_col] if dii_col is not None else pd.Series(dtype=float)

    def stats(s):
        z = s.dropna()
        if z.empty:
            return [np.nan] * 4
        return [float(z.iloc[-1]), float(z.tail(5).sum()), float(z.tail(20).sum()), float(z.tail(60).sum())]

    fn, f5, f20, f60 = stats(fii)
    dn, d5, d20, d60 = stats(dii)
    score = 50.0
    for val, wt in ((fn, 4), (f5, 8), (f20, 12), (f60, 10)):
        if pd.notna(val):
            score += wt if val > 0 else -wt
    for val, wt in ((dn, 2), (d5, 4), (d20, 5), (d60, 5)):
        if pd.notna(val):
            score += wt if val > 0 else -wt
    score = max(0, min(100, score))
    bias = 'SUPPORTIVE' if score >= 62 else ('RISK-OFF' if score <= 38 else 'MIXED')
    fr = _flow_regime(fn, f5, f20, f60, 'FII')
    dr = _flow_regime(dn, d5, d20, d60, 'DII')
    explanation = f'FII/FPI: {fr}; DII: {dr}. Institutional context is {bias.lower()}.'
    latest = piv.index.max()
    return {
        'Bias': bias, 'LatestDate': latest.date().isoformat(),
        'FIINet₹Cr': round(fn, 2) if pd.notna(fn) else np.nan,
        'DIINet₹Cr': round(dn, 2) if pd.notna(dn) else np.nan,
        'FII5D₹Cr': round(f5, 2) if pd.notna(f5) else np.nan,
        'DII5D₹Cr': round(d5, 2) if pd.notna(d5) else np.nan,
        'FII20D₹Cr': round(f20, 2) if pd.notna(f20) else np.nan,
        'DII20D₹Cr': round(d20, 2) if pd.notna(d20) else np.nan,
        'FII60D₹Cr': round(f60, 2) if pd.notna(f60) else np.nan,
        'DII60D₹Cr': round(d60, 2) if pd.notna(d60) else np.nan,
        'FIIRegime': fr, 'DIIRegime': dr, 'Score': round(score, 1), 'Explanation': explanation
    }


# ---------------------------------------------------------------------------
# NSE derivatives participant positioning
# ---------------------------------------------------------------------------

def _norm_col(c):
    return re.sub(r'[^a-z0-9]+', ' ', str(c).lower()).strip()


def _find_col(df, *needles):
    n = [_norm_col(x) for x in needles]
    for c in df.columns:
        cc = _norm_col(c)
        if all(x in cc for x in n):
            return c
    return None


def _participant_row(df, names=('FII', 'FPI')):
    if df is None or df.empty:
        return None
    first = df.columns[0]
    for _, r in df.iterrows():
        val = str(r.get(first, '')).upper().strip()
        if any(val == n or val.startswith(n + ' ') or n in val for n in names):
            return r
    return None


def _derivatives_urls(kind, d: date):
    ds = d.strftime('%d%m%Y')
    fn = f'fao_participant_{kind}_{ds}.csv'
    return [
        f'https://nsearchives.nseindia.com/content/nsccl/{fn}',
        f'https://archives.nseindia.com/content/nsccl/{fn}',
        f'https://www1.nseindia.com/content/nsccl/{fn}',
    ]


def refresh_derivatives_positioning(status_cb=None):
    last_err = []
    chosen = None
    oi = vol = None
    src_oi = src_vol = ''
    for d in _recent_weekdays(8):
        try:
            if status_cb:
                status_cb(f'Derivatives: participant OI {d.isoformat()}...')
            raw, src_oi = _request_bytes(_derivatives_urls('oi', d), timeout=20)
            oi = _read_csv_loose(raw, skiprows_options=(1, 0, 2))
            chosen = d
            try:
                RAW.joinpath(f'fao_participant_oi_{d:%Y%m%d}.csv').write_bytes(raw)
            except Exception:
                pass
            try:
                raw2, src_vol = _request_bytes(_derivatives_urls('vol', d), timeout=20)
                vol = _read_csv_loose(raw2, skiprows_options=(1, 0, 2))
                RAW.joinpath(f'fao_participant_vol_{d:%Y%m%d}.csv').write_bytes(raw2)
            except Exception as e:
                last_err.append(str(e))
            break
        except Exception as e:
            last_err.append(f'{d}: {e}')
    if oi is None or oi.empty or chosen is None:
        res = {'ok': False, 'status': 'FALLBACK' if DERIV_HISTORY.exists() else 'MISSING',
               'message': 'Participant derivatives positioning unavailable; cached history preserved. ' + (' | '.join(last_err[-2:]) if last_err else '')}
        _save_meta('derivatives', res)
        return res

    oi.to_csv(DERIV_OI, index=False)
    if vol is not None and not vol.empty:
        vol.to_csv(DERIV_VOL, index=False)
    fii = _participant_row(oi, ('FII', 'FPI'))
    if fii is None:
        res = {'ok': False, 'status': 'PARTIAL', 'message': 'Participant OI downloaded but FII/FPI row could not be identified; raw table saved.'}
        _save_meta('derivatives', res)
        return res

    fil = _find_col(oi, 'future', 'index', 'long')
    fis = _find_col(oi, 'future', 'index', 'short')
    cil = _find_col(oi, 'option', 'index', 'call', 'long')
    pil = _find_col(oi, 'option', 'index', 'put', 'long')
    cis = _find_col(oi, 'option', 'index', 'call', 'short')
    pis = _find_col(oi, 'option', 'index', 'put', 'short')
    future_long = _num(fii.get(fil)) if fil else np.nan
    future_short = _num(fii.get(fis)) if fis else np.nan
    fut_net = future_long - future_short if pd.notna(future_long) and pd.notna(future_short) else np.nan
    denom = future_long + future_short if pd.notna(future_long) and pd.notna(future_short) else np.nan
    long_pct = future_long / denom * 100 if pd.notna(denom) and denom else np.nan
    call_long = _num(fii.get(cil)) if cil else np.nan
    put_long = _num(fii.get(pil)) if pil else np.nan
    call_short = _num(fii.get(cis)) if cis else np.nan
    put_short = _num(fii.get(pis)) if pis else np.nan
    option_dir = np.nan
    if all(pd.notna(x) for x in (call_long, put_long, call_short, put_short)):
        # Supporting heuristic only: options are often hedges, so this receives low decision weight.
        option_dir = (call_long + put_short) - (put_long + call_short)

    score = 50.0
    if pd.notna(long_pct):
        score += max(-22, min(22, (long_pct - 50) * 1.6))
    if pd.notna(option_dir):
        scale = max(1.0, abs(call_long) + abs(put_long) + abs(call_short) + abs(put_short))
        score += max(-8, min(8, option_dir / scale * 100 * 0.8))
    score = max(0, min(100, score))
    bias = 'SUPPORTIVE' if score >= 60 else ('RISK-OFF' if score <= 40 else 'MIXED')
    row = pd.DataFrame([{
        'Date': chosen.isoformat(), 'FIIIndexFutureLong': future_long, 'FIIIndexFutureShort': future_short,
        'FIIIndexFutureNet': fut_net, 'FIIIndexFutureLongPct': round(long_pct, 2) if pd.notna(long_pct) else np.nan,
        'FIIOptionDirectionalNet': option_dir, 'Score': round(score, 1), 'Bias': bias,
        'Source': src_oi, 'VolumeSource': src_vol, 'Status': 'VERIFIED FILE'
    }])
    _append_dedup(DERIV_HISTORY, row, ['Date'])
    res = {'ok': True, 'status': 'FRESH', 'date': chosen.isoformat(), 'score': round(score, 1), 'bias': bias,
           'message': f'NSE participant OI loaded for {chosen.isoformat()}; FII index-futures positioning is {bias.lower()}.'}
    _save_meta('derivatives', res)
    return res


def load_derivatives_history():
    if DERIV_HISTORY.exists():
        try:
            return pd.read_csv(DERIV_HISTORY)
        except Exception:
            pass
    return pd.DataFrame()


def derivatives_summary():
    d = load_derivatives_history()
    if d.empty:
        return {'Bias': 'UNAVAILABLE', 'Score': np.nan, 'LatestDate': '', 'FIIIndexFutureNet': np.nan,
                'FIIIndexFutureLongPct': np.nan, 'Explanation': 'Participant derivatives positioning unavailable.'}
    r = d.sort_values('Date').iloc[-1]
    score = _num(r.get('Score'))
    bias = str(r.get('Bias', 'UNAVAILABLE'))
    net = _num(r.get('FIIIndexFutureNet'))
    lp = _num(r.get('FIIIndexFutureLongPct'))
    if pd.notna(lp):
        exp = f'FII index-futures long share is {lp:.1f}% with net position {net:+,.0f} contracts.' if pd.notna(net) else f'FII index-futures long share is {lp:.1f}%.'
    else:
        exp = 'FII derivatives data exists but directional fields are incomplete.'
    return {'Bias': bias, 'Score': score, 'LatestDate': str(r.get('Date', '')), 'FIIIndexFutureNet': net,
            'FIIIndexFutureLongPct': lp, 'Explanation': exp}


# ---------------------------------------------------------------------------
# Breadth from stored NSE EOD history (stable, reproducible, no extra endpoint)
# ---------------------------------------------------------------------------

def refresh_breadth(history: pd.DataFrame | None, status_cb=None):
    if history is None or history.empty or not {'Symbol', 'Date', 'Close'}.issubset(history.columns):
        res = {'ok': False, 'status': 'MISSING', 'message': 'Breadth not calculated because NSE history is unavailable.'}
        _save_meta('breadth', res)
        return res
    if status_cb:
        status_cb('Breadth: calculating from stored NSE EOD universe...')
    h = history.copy().sort_values(['Symbol', 'Date'])
    h['Prev'] = h.groupby('Symbol')['Close'].shift(1)
    h['Ret'] = h['Close'] / h['Prev'] - 1
    h['EMA21'] = h.groupby('Symbol')['Close'].transform(lambda s: s.ewm(span=21, adjust=False).mean())
    h['EMA50'] = h.groupby('Symbol')['Close'].transform(lambda s: s.ewm(span=50, adjust=False).mean())
    h['High252'] = h.groupby('Symbol')['Close'].transform(lambda s: s.rolling(252, min_periods=60).max())
    h['Low252'] = h.groupby('Symbol')['Close'].transform(lambda s: s.rolling(252, min_periods=60).min())
    latest_date = pd.to_datetime(h['Date']).max()
    x = h[pd.to_datetime(h['Date']).eq(latest_date)].copy()
    x = x[x['Prev'].notna()]
    if x.empty:
        res = {'ok': False, 'status': 'PARTIAL', 'message': 'Breadth could not be calculated for the latest stored date.'}
        _save_meta('breadth', res)
        return res
    adv = int((x.Ret > 0).sum()); dec = int((x.Ret < 0).sum()); unc = int((x.Ret == 0).sum()); n = len(x)
    a21 = float((x.Close > x.EMA21).mean() * 100)
    a50 = float((x.Close > x.EMA50).mean() * 100)
    advp = float(adv / n * 100) if n else np.nan
    nh = int((x.Close >= x.High252 * 0.999).sum()) if x.High252.notna().any() else 0
    nl = int((x.Close <= x.Low252 * 1.001).sum()) if x.Low252.notna().any() else 0
    adratio = float(adv / dec) if dec else np.nan
    score = 0.35 * a21 + 0.35 * a50 + 0.30 * advp
    score += max(-8, min(8, (nh - nl) / max(5, n) * 100))
    score = max(0, min(100, score))
    bias = 'STRONG' if score >= 65 else ('WEAK' if score <= 40 else 'MIXED')
    row = pd.DataFrame([{
        'Date': latest_date.date().isoformat(), 'Universe': n, 'Advances': adv, 'Declines': dec, 'Unchanged': unc,
        'AdvanceDeclineRatio': round(adratio, 3) if pd.notna(adratio) else np.nan,
        'PctAdvancers': round(advp, 2), 'PctAboveEMA21': round(a21, 2), 'PctAboveEMA50': round(a50, 2),
        'NewHighsApprox': nh, 'NewLowsApprox': nl, 'Score': round(score, 1), 'Bias': bias,
        'Source': 'Calculated from stored NSE EOD history', 'Status': 'CALCULATED'
    }])
    _append_dedup(BREADTH_HISTORY, row, ['Date'])
    res = {'ok': True, 'status': 'FRESH', 'date': latest_date.date().isoformat(), 'score': round(score, 1), 'bias': bias,
           'message': f'Breadth calculated for {n:,} stocks: {adv} advances / {dec} declines; {a50:.1f}% above EMA50.'}
    _save_meta('breadth', res)
    return res


def load_breadth_history():
    if BREADTH_HISTORY.exists():
        try:
            return pd.read_csv(BREADTH_HISTORY)
        except Exception:
            pass
    return pd.DataFrame()


def breadth_summary():
    d = load_breadth_history()
    if d.empty:
        return {'Bias': 'UNAVAILABLE', 'Score': np.nan, 'LatestDate': '', 'Explanation': 'Market breadth history unavailable.'}
    r = d.sort_values('Date').iloc[-1]
    return {
        'Bias': str(r.get('Bias', 'UNAVAILABLE')), 'Score': _num(r.get('Score')), 'LatestDate': str(r.get('Date', '')),
        'Advances': int(_num(r.get('Advances'))) if pd.notna(_num(r.get('Advances'))) else 0,
        'Declines': int(_num(r.get('Declines'))) if pd.notna(_num(r.get('Declines'))) else 0,
        'PctAdvancers': _num(r.get('PctAdvancers')), 'PctAboveEMA21': _num(r.get('PctAboveEMA21')),
        'PctAboveEMA50': _num(r.get('PctAboveEMA50')), 'NewHighsApprox': _num(r.get('NewHighsApprox')),
        'NewLowsApprox': _num(r.get('NewLowsApprox')),
        'Explanation': f"{_num(r.get('PctAdvancers')):.1f}% of the tracked universe advanced; {_num(r.get('PctAboveEMA50')):.1f}% is above EMA50." if pd.notna(_num(r.get('PctAdvancers'))) and pd.notna(_num(r.get('PctAboveEMA50'))) else 'Breadth data is partially available.'
    }


# ---------------------------------------------------------------------------
# Delivery, valuation, surveillance, deals and short-selling reports
# ---------------------------------------------------------------------------

def _dated_archive_download(pattern_urls, output_path: Path, status_cb=None, label='Report', parse=True):
    errs = []
    for d in _recent_weekdays(8):
        fmts = {
            'DDMMYYYY': d.strftime('%d%m%Y'), 'DDMMYY': d.strftime('%d%m%y'),
            'YYYYMMDD': d.strftime('%Y%m%d'), 'YYYY': d.strftime('%Y'), 'MON': d.strftime('%b').upper()
        }
        urls = []
        for p in pattern_urls:
            u = p
            for k, v in fmts.items():
                u = u.replace('{' + k + '}', v)
            urls.append(u)
        try:
            if status_cb:
                status_cb(f'{label}: trying {d.isoformat()}...')
            raw, src = _request_bytes(urls, timeout=20)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            RAW.joinpath(f'{output_path.stem}_{d:%Y%m%d}{output_path.suffix or ".dat"}').write_bytes(raw)
            if parse:
                df = _read_csv_loose(raw, skiprows_options=(0, 1, 2, 3, 4))
                df['RadarDate'] = d.isoformat()
                df['RadarSource'] = src
                df.to_csv(output_path.with_suffix('.csv'), index=False)
                return df, d, src
            output_path.write_bytes(raw)
            return pd.DataFrame(), d, src
        except Exception as e:
            errs.append(f'{d}: {e}')
    raise RuntimeError(' | '.join(errs[-2:]))


def refresh_delivery(status_cb=None):
    pats = [
        'https://nsearchives.nseindia.com/archives/equities/mto/MTO_{DDMMYYYY}.DAT',
        'https://archives.nseindia.com/archives/equities/mto/MTO_{DDMMYYYY}.DAT'
    ]
    try:
        df, d, src = _dated_archive_download(pats, DELIVERY.with_suffix('.DAT'), status_cb, 'Delivery positions', True)
        # Normalize common MTO column names where possible.
        ren = {}
        for c in df.columns:
            n = _norm_col(c)
            if n in ('name of security', 'symbol', 'security') or ('name' in n and 'security' in n):
                ren[c] = 'Symbol'
            elif 'deliverable' in n and ('percent' in n or '%' in str(c) or 'traded qty' in n):
                ren[c] = 'DeliveryPct'
            elif 'deliverable' in n and 'quantity' in n:
                ren[c] = 'DeliverableQty'
            elif 'traded' in n and 'quantity' in n:
                ren[c] = 'TradedQty'
        if ren:
            df = df.rename(columns=ren)
        df.to_csv(DELIVERY, index=False)
        res = {'ok': True, 'status': 'FRESH', 'date': d.isoformat(), 'rows': len(df), 'message': f'Security-wise delivery report loaded for {d.isoformat()}.'}
    except Exception as e:
        res = {'ok': False, 'status': 'FALLBACK' if DELIVERY.exists() else 'MISSING', 'message': f'Delivery report unavailable: {e}; cache preserved.'}
    _save_meta('delivery', res)
    return res


def load_delivery():
    if DELIVERY.exists():
        try:
            return pd.read_csv(DELIVERY)
        except Exception:
            pass
    return pd.DataFrame()


def delivery_map():
    d = load_delivery()
    if d.empty:
        return {}
    sym_col = next((c for c in d.columns if _norm_col(c) in ('symbol', 'name of security', 'security')), None)
    pct_col = next((c for c in d.columns if 'deliver' in _norm_col(c) and ('pct' in _norm_col(c) or 'percent' in _norm_col(c) or '%' in str(c))), None)
    if sym_col is None:
        sym_col = 'Symbol' if 'Symbol' in d.columns else None
    if pct_col is None:
        pct_col = 'DeliveryPct' if 'DeliveryPct' in d.columns else None
    if not sym_col or not pct_col:
        return {}
    out = {}
    for _, r in d.iterrows():
        s = str(r.get(sym_col, '')).strip().upper()
        v = _num(r.get(pct_col))
        if s and pd.notna(v):
            out[s] = v
    return out


def refresh_index_valuation(status_cb=None):
    pats = [
        'https://nsearchives.nseindia.com/archives/equities/mkt/PE_{DDMMYY}.csv',
        'https://archives.nseindia.com/archives/equities/mkt/PE_{DDMMYY}.csv'
    ]
    try:
        df, d, src = _dated_archive_download(pats, INDEX_VALUATION, status_cb, 'Index valuation', True)
        df.to_csv(INDEX_VALUATION, index=False)
        res = {'ok': True, 'status': 'FRESH', 'date': d.isoformat(), 'rows': len(df), 'message': f'NSE index valuation report loaded for {d.isoformat()}.'}
    except Exception as e:
        res = {'ok': False, 'status': 'FALLBACK' if INDEX_VALUATION.exists() else 'MISSING', 'message': f'Index valuation unavailable: {e}; cache preserved.'}
    _save_meta('index_valuation', res)
    return res


def load_index_valuation():
    if INDEX_VALUATION.exists():
        try:
            return pd.read_csv(INDEX_VALUATION)
        except Exception:
            pass
    return pd.DataFrame()


def refresh_surveillance(status_cb=None):
    all_frames = []
    used_date = None
    errs = []
    for prefix in ('REG_IND', 'REG1_IND'):
        pats = [
            f'https://nsearchives.nseindia.com/archives/equities/mkt/{prefix}' + '{DDMMYY}.csv',
            f'https://archives.nseindia.com/archives/equities/mkt/{prefix}' + '{DDMMYY}.csv'
        ]
        try:
            df, d, src = _dated_archive_download(pats, DIR / f'{prefix.lower()}_latest.csv', status_cb, f'Surveillance {prefix}', True)
            df['RadarReport'] = prefix
            all_frames.append(df); used_date = d
        except Exception as e:
            errs.append(f'{prefix}: {e}')
    if all_frames:
        out = pd.concat(all_frames, ignore_index=True, sort=False)
        out.to_csv(SURVEILLANCE, index=False)
        res = {'ok': True, 'status': 'FRESH' if len(all_frames) == 2 else 'PARTIAL', 'date': used_date.isoformat() if used_date else '', 'rows': len(out),
               'message': f'NSE surveillance indicator table(s) loaded ({len(all_frames)}/2).'}
    else:
        res = {'ok': False, 'status': 'FALLBACK' if SURVEILLANCE.exists() else 'MISSING', 'message': 'Surveillance reports unavailable; cache preserved. ' + ' | '.join(errs[-2:])}
    _save_meta('surveillance', res)
    return res


def load_surveillance():
    if SURVEILLANCE.exists():
        try:
            return pd.read_csv(SURVEILLANCE)
        except Exception:
            pass
    return pd.DataFrame()


def surveillance_map():
    d = load_surveillance()
    if d.empty:
        return {}
    sym_col = next((c for c in d.columns if _norm_col(c) in ('symbol', 'security symbol', 'symbol name')), None)
    if not sym_col:
        sym_col = next((c for c in d.columns if 'symbol' in _norm_col(c)), None)
    if not sym_col:
        return {}
    ignore = {'radardate', 'radarsource', 'radarreport'}
    out = {}
    for _, r in d.iterrows():
        s = str(r.get(sym_col, '')).strip().upper()
        if not s or s == 'NAN':
            continue
        flags = []
        for c in d.columns:
            if c == sym_col or _norm_col(c).replace(' ', '') in ignore:
                continue
            v = str(r.get(c, '')).strip()
            if v and v.lower() not in ('nan', 'none', 'no', '0', '-', 'na', 'n/a'):
                nc = _norm_col(c)
                if any(k in nc for k in ('gsm', 'asm', 'esm', 'surveillance', 'trade for trade', 'tft', 'stage', 'alert')):
                    flags.append(f'{c}: {v}')
        if flags:
            out[s] = {'severity': 'REVIEW', 'detail': '; '.join(flags[:6])}
    return out


def refresh_deals_short(status_cb=None):
    results = []
    # Bulk/block files are current snapshots on the official NSE archive endpoint.
    for label, url, path in [
        ('Bulk deals', 'https://nsearchives.nseindia.com/content/equities/bulk.csv', BULK_DEALS),
        ('Block deals', 'https://nsearchives.nseindia.com/content/equities/block.csv', BLOCK_DEALS),
    ]:
        try:
            if status_cb:
                status_cb(label + ': downloading...')
            raw, src = _request_bytes([url, url.replace('nsearchives.', 'archives.')], timeout=18)
            df = _read_csv_loose(raw)
            df['RadarFetchedAt'] = pd.Timestamp.now().isoformat(timespec='seconds')
            df['RadarSource'] = src
            df.to_csv(path, index=False)
            results.append((label, True, len(df)))
        except Exception:
            results.append((label, False, 0))
    try:
        pats = [
            'https://nsearchives.nseindia.com/archives/equities/shortSelling/shortselling_{DDMMYYYY}.csv',
            'https://archives.nseindia.com/archives/equities/shortSelling/shortselling_{DDMMYYYY}.csv'
        ]
        df, d, src = _dated_archive_download(pats, SHORT_SELLING, status_cb, 'Short selling', True)
        df.to_csv(SHORT_SELLING, index=False)
        results.append(('Short selling', True, len(df)))
    except Exception:
        results.append(('Short selling', False, 0))
    ok = sum(1 for _, yes, _ in results if yes)
    res = {'ok': ok > 0, 'status': 'FRESH' if ok == len(results) else ('PARTIAL' if ok else 'FALLBACK'),
           'message': 'Deals/short-selling: ' + ', '.join(f'{name} {"PASS" if yes else "WARN"}' for name, yes, _ in results)}
    _save_meta('deals_short', res)
    return res


def load_bulk_deals():
    try:
        return pd.read_csv(BULK_DEALS) if BULK_DEALS.exists() else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def load_block_deals():
    try:
        return pd.read_csv(BLOCK_DEALS) if BLOCK_DEALS.exists() else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def load_short_selling():
    try:
        return pd.read_csv(SHORT_SELLING) if SHORT_SELLING.exists() else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


# ---------------------------------------------------------------------------
# FPI sector flows (CDSL/NSDL public pages) and AMFI SIP trend
# ---------------------------------------------------------------------------

def _flatten_cols(df):
    if isinstance(df.columns, pd.MultiIndex):
        df = df.copy()
        df.columns = [' | '.join(str(x) for x in tup if str(x) != 'nan').strip(' |') for tup in df.columns]
    return df


def refresh_fpi_sector(status_cb=None):
    base = 'https://www.cdslindia.com/Publications/ForeignPortInvestor.html'
    try:
        if status_cb:
            status_cb('FPI sector: locating latest CDSL fortnightly sector table...')
        r = requests.get(base, headers=HEADERS, timeout=25)
        r.raise_for_status()
        hrefs = re.findall(r'href=["\']([^"\']*FortnightlySecWisePages/[^"\']+\.html)["\']', r.text, flags=re.I)
        if not hrefs:
            raise RuntimeError('Latest sector-wise link not found in CDSL page')
        # Page normally lists newest dates first. Deduplicate while preserving order.
        seen = set(); links = []
        for h in hrefs:
            u = urljoin(base, h)
            if u not in seen:
                seen.add(u); links.append(u)
        last = None
        for u in links[:8]:
            try:
                rr = requests.get(u, headers=HEADERS, timeout=25); rr.raise_for_status()
                tables = pd.read_html(StringIO(rr.text))
                cand = []
                for t in tables:
                    t = _flatten_cols(t)
                    if len(t.columns) >= 5 and any('sector' in _norm_col(c) for c in t.columns):
                        cand.append(t)
                if cand:
                    df = max(cand, key=lambda z: len(z.columns) * max(1, len(z)))
                    df['RadarSource'] = u
                    df['RadarFetchedAt'] = pd.Timestamp.now().isoformat(timespec='seconds')
                    df.to_csv(SECTOR_FPI, index=False)
                    res = {'ok': True, 'status': 'FRESH', 'rows': len(df), 'source': u,
                           'message': f'Latest public CDSL fortnightly FPI sector table cached ({len(df)} rows).'}
                    _save_meta('fpi_sector', res)
                    return res
            except Exception as e:
                last = e
        raise RuntimeError(str(last) if last else 'No parseable sector table')
    except Exception as e:
        res = {'ok': False, 'status': 'FALLBACK' if SECTOR_FPI.exists() else 'MISSING',
               'message': f'FPI sector flow refresh unavailable: {e}; last cache preserved.'}
        _save_meta('fpi_sector', res)
        return res


def load_fpi_sector():
    if SECTOR_FPI.exists():
        try:
            return pd.read_csv(SECTOR_FPI)
        except Exception:
            pass
    return pd.DataFrame()


def refresh_amfi_sip(status_cb=None):
    url = 'https://www.amfiindia.com/articles/mutual-fund'
    try:
        if status_cb:
            status_cb('AMFI SIP: reading latest official SIP contribution...')
        r = requests.get(url, headers=HEADERS, timeout=25)
        r.raise_for_status()
        txt = re.sub(r'\s+', ' ', re.sub('<[^>]+>', ' ', r.text))
        # Supports: "Total amount collected through SIP during July 2026 was ₹ 31,961 crore."
        m = re.search(r'Total amount collected through SIP during\s+([A-Za-z]+\s+20\d{2})\s+was\s*(?:₹|Rs\.?|INR)?\s*([0-9,]+(?:\.\d+)?)\s*crore', txt, flags=re.I)
        if not m:
            # The page may expose text via script/JSON; search the raw HTML too.
            m = re.search(r'Total amount collected through SIP during[^A-Za-z]+([A-Za-z]+\s+20\d{2}).{0,100}?([0-9,]+(?:\.\d+)?)\s*crore', r.text, flags=re.I | re.S)
        if not m:
            raise RuntimeError('Current SIP contribution text not found')
        period = m.group(1).strip(); amount = _num(m.group(2))
        dt = pd.to_datetime(period, format='%B %Y', errors='coerce')
        row = pd.DataFrame([{'Period': period, 'Date': dt.date().isoformat() if pd.notna(dt) else period,
                             'SIPContribution₹Cr': amount, 'Source': url, 'Status': 'OFFICIAL'}])
        _append_dedup(SIP_HISTORY, row, ['Period'])
        res = {'ok': True, 'status': 'FRESH', 'period': period, 'value': amount,
               'message': f'AMFI SIP contribution cached for {period}: ₹{amount:,.0f} Cr.'}
    except Exception as e:
        res = {'ok': False, 'status': 'FALLBACK' if SIP_HISTORY.exists() else 'MISSING', 'message': f'AMFI SIP trend unavailable: {e}; cache preserved.'}
    _save_meta('amfi_sip', res)
    return res


def load_amfi_sip():
    if SIP_HISTORY.exists():
        try:
            return pd.read_csv(SIP_HISTORY)
        except Exception:
            pass
    return pd.DataFrame()


# ---------------------------------------------------------------------------
# News context
# ---------------------------------------------------------------------------

def _news_risk(title):
    t = str(title).upper()
    if any(k in t for k in NEG):
        return 'RISK'
    if any(k in t for k in POS):
        return 'POSITIVE'
    return 'NEUTRAL'


def _rss(query, limit=20):
    u = 'https://news.google.com/rss/search?q=' + urllib.parse.quote(query) + '&hl=en-IN&gl=IN&ceid=IN:en'
    r = requests.get(u, headers={'User-Agent': 'Mozilla/5.0'}, timeout=20)
    r.raise_for_status()
    root = ET.fromstring(r.content)
    rows = []
    for item in root.findall('.//item')[:limit]:
        src = item.find('source')
        rows.append({'Published': item.findtext('pubDate') or '', 'Title': item.findtext('title') or '',
                     'Source': src.text if src is not None else '', 'Link': item.findtext('link') or '', 'Query': query})
    return rows


def refresh_market_news(topics=None, status_cb=None):
    topics = topics or DEFAULT_NEWS_TOPICS
    rows = []; errors = []
    for i, q in enumerate(topics, 1):
        if status_cb:
            status_cb(f'Public market news {i}/{len(topics)}: {q}')
        try:
            rows.extend(_rss(q, 15))
        except Exception as e:
            errors.append(f'{q}: {e}')
        time.sleep(.05)
    if rows:
        d = pd.DataFrame(rows)
        d['Risk'] = d['Title'].map(_news_risk)
        d['FetchedAt'] = pd.Timestamp.now().isoformat(timespec='seconds')
        d = d.drop_duplicates(['Title', 'Source'], keep='first')
        d.to_csv(NEWS, index=False)
    res = {'ok': bool(rows), 'count': len(rows), 'status': 'FRESH' if rows and not errors else ('PARTIAL' if rows else ('FALLBACK' if NEWS.exists() else 'MISSING')),
           'message': f'Market news refreshed: {len(rows)} headline(s).' + (f' {len(errors)} topic(s) unavailable; last cache preserved.' if errors else '')}
    _save_meta('news', res)
    return res


def load_market_news():
    if NEWS.exists():
        try:
            return pd.read_csv(NEWS)
        except Exception:
            pass
    return pd.DataFrame(columns=['Published', 'Title', 'Source', 'Link', 'Query', 'Risk', 'FetchedAt'])


def refresh_stock_news(symbol, company='', status_cb=None):
    sym = str(symbol).strip().upper(); company = str(company or '').strip(); q = (company + ' ' + sym + ' NSE India stock').strip()
    if status_cb:
        status_cb('Fetching public news context for ' + sym + '...')
    try:
        rows = _rss(q, 25); d = pd.DataFrame(rows); d['Risk'] = d['Title'].map(_news_risk)
        d['FetchedAt'] = pd.Timestamp.now().isoformat(timespec='seconds'); d['Symbol'] = sym
        out = DIR / 'stock_news'; out.mkdir(exist_ok=True); d.to_csv(out / f'{sym}.csv', index=False)
        return {'ok': True, 'count': len(d), 'message': f'{len(d)} public headlines cached for {sym}.'}
    except Exception as e:
        return {'ok': False, 'count': 0, 'message': f'Public news unavailable for {sym}: {e}'}


def load_stock_news(symbol):
    p = DIR / 'stock_news' / f'{str(symbol).strip().upper()}.csv'
    if p.exists():
        try:
            return pd.read_csv(p)
        except Exception:
            pass
    return pd.DataFrame()


# ---------------------------------------------------------------------------
# Unified market-intelligence context used by recommendations and forecasts
# ---------------------------------------------------------------------------

def market_context(history: pd.DataFrame | None = None):
    inst = institutional_summary()
    der = derivatives_summary()
    br = breadth_summary()
    try:
        from macro_intelligence import load as load_macro, india_context
        md = load_macro(); mac = india_context(md)
    except Exception:
        md = pd.DataFrame(); mac = {'Context': 'UNAVAILABLE', 'Score': np.nan, 'Reasons': []}

    components = []
    reasons = []
    if pd.notna(inst.get('Score', np.nan)):
        components.append(('Institutional', float(inst['Score']), 0.30)); reasons.append(inst.get('Explanation', ''))
    if pd.notna(der.get('Score', np.nan)):
        components.append(('Derivatives', float(der['Score']), 0.18)); reasons.append(der.get('Explanation', ''))
    if pd.notna(br.get('Score', np.nan)):
        components.append(('Breadth', float(br['Score']), 0.27)); reasons.append(br.get('Explanation', ''))
    if pd.notna(mac.get('Score', np.nan)):
        components.append(('Macro', float(mac['Score']), 0.20)); reasons.extend(mac.get('Reasons', [])[:4])

    vix = np.nan; vix_trend = ''
    if md is not None and not md.empty and 'Indicator' in md.columns:
        vv = md[md.Indicator.astype(str).eq('India VIX')]
        if not vv.empty:
            vix = _num(vv.iloc[-1].get('Latest')); vix_trend = str(vv.iloc[-1].get('Trend', ''))
    vix_score = np.nan
    if pd.notna(vix):
        # Low/moderate VIX is supportive; very high VIX caps risk appetite.
        vix_score = 70 if vix < 13 else (58 if vix < 17 else (45 if vix < 22 else (30 if vix < 30 else 15)))
        components.append(('VIX', vix_score, 0.05))
        reasons.append(f'India VIX {vix:.2f} ({"elevated risk" if vix >= 22 else "normal/moderate volatility"}).')

    if components:
        wsum = sum(w for _, _, w in components)
        score = sum(s * w for _, s, w in components) / wsum
    else:
        score = np.nan
    completeness = round(sum(w for _, _, w in components) / 1.0 * 100, 1)
    if pd.isna(score):
        regime = 'UNAVAILABLE'; cap = 'LOW'
    else:
        regime = 'SUPPORTIVE' if score >= 63 else ('RISK-OFF' if score <= 39 else 'MIXED')
        cap = 'HIGH' if completeness >= 80 and regime != 'RISK-OFF' else ('MEDIUM' if completeness >= 45 else 'LOW')
    return {
        'Score': round(float(score), 1) if pd.notna(score) else np.nan,
        'Regime': regime,
        'InstitutionalBias': inst.get('Bias', 'UNAVAILABLE'), 'InstitutionalScore': inst.get('Score', np.nan),
        'DerivativesBias': der.get('Bias', 'UNAVAILABLE'), 'DerivativesScore': der.get('Score', np.nan),
        'BreadthBias': br.get('Bias', 'UNAVAILABLE'), 'BreadthScore': br.get('Score', np.nan),
        'MacroContext': mac.get('Context', 'UNAVAILABLE'), 'MacroScore': mac.get('Score', np.nan),
        'IndiaVIX': round(vix, 2) if pd.notna(vix) else np.nan, 'VIXTrend': vix_trend,
        'DataCompleteness%': completeness, 'ConfidenceCap': cap,
        'Reasons': [str(x) for x in reasons if str(x).strip()][:10],
        'LatestDate': max([x for x in [inst.get('LatestDate', ''), der.get('LatestDate', ''), br.get('LatestDate', '')] if x] or [''])
    }


def context_explanation(ctx=None):
    ctx = market_context() if ctx is None else ctx
    if not ctx or ctx.get('Regime') == 'UNAVAILABLE':
        return 'Market-intelligence context is incomplete. The Radar will avoid using missing context as if it passed.'
    parts = [f"Overall market-intelligence regime: {ctx.get('Regime')} ({ctx.get('Score')}/100).",
             f"Institutional: {ctx.get('InstitutionalBias')}; derivatives: {ctx.get('DerivativesBias')}; breadth: {ctx.get('BreadthBias')}; macro: {ctx.get('MacroContext')}."]
    if pd.notna(ctx.get('IndiaVIX', np.nan)):
        parts.append(f"India VIX: {ctx.get('IndiaVIX')}.")
    if ctx.get('Reasons'):
        parts.append('Key context: ' + ' '.join(ctx['Reasons'][:4]))
    return ' '.join(parts)


def refresh_all(status_cb=None, news_topics=None, history=None):
    """Failure-tolerant refresh of the full free-first market-intelligence layer.

    Each dataset is independent: one source failure never erases previous valid cache or crashes the
    complete Daily Update. `history` should be the already-updated local NSE history so breadth is
    reproducible and network-independent.
    """
    tasks = [
        ('FII/DII', lambda: refresh_fii_dii(status_cb)),
        ('Derivatives', lambda: refresh_derivatives_positioning(status_cb)),
        ('Breadth', lambda: refresh_breadth(history, status_cb)),
        ('Delivery', lambda: refresh_delivery(status_cb)),
        ('Index valuation', lambda: refresh_index_valuation(status_cb)),
        ('Surveillance', lambda: refresh_surveillance(status_cb)),
        ('Deals/Short', lambda: refresh_deals_short(status_cb)),
        ('FPI sector', lambda: refresh_fpi_sector(status_cb)),
        ('AMFI SIP', lambda: refresh_amfi_sip(status_cb)),
        ('News', lambda: refresh_market_news(news_topics, status_cb)),
    ]
    results = {}
    for name, fn in tasks:
        try:
            results[name] = fn()
        except Exception as e:
            results[name] = {'ok': False, 'status': 'FAILED', 'message': str(e)}
    ok_count = sum(1 for r in results.values() if r.get('ok'))
    context = market_context(history)
    summary = {
        'updated_at': pd.Timestamp.now().isoformat(timespec='seconds'), 'results': results,
        'context': context, 'ok_count': ok_count, 'total': len(tasks)
    }
    try:
        META.write_text(json.dumps(summary, indent=2, default=str), encoding='utf-8')
    except Exception:
        pass
    return {
        'ok': ok_count > 0, 'count': ok_count,
        'message': f'Market intelligence: {ok_count}/{len(tasks)} dataset families refreshed or calculated; failed optional sources retained cached data.',
        'context': context, 'results': results
    }
