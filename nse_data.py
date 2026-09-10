
from __future__ import annotations
import io, zipfile, time
from pathlib import Path
from datetime import date, timedelta
import requests
import pandas as pd

BASE = Path(__file__).resolve().parent
BHAV_DIR = BASE / "data" / "bhavcopy"
BHAV_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
    "Accept": "*/*",
    "Referer": "https://www.nseindia.com/all-reports/",
}

KEEP = ["TradDt","TckrSymb","SctySrs","OpnPric","HghPric","LwPric","ClsPric",
        "PrvsClsgPric","TtlTradgVol","TtlTrfVal","TtlNbOfTxsExctd"]

def _urls(d: date):
    ds = d.strftime("%Y%m%d")
    fn = f"BhavCopy_NSE_CM_0_0_0_{ds}_F_0000.csv.zip"
    return [
        f"https://nsearchives.nseindia.com/content/cm/{fn}",
        f"https://nsearchives.nseindia.com/content/equities/{fn}",
    ]

def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [str(c).strip() for c in df.columns]
    if "TckrSymb" not in df.columns:
        raise ValueError("Unexpected NSE bhavcopy format: TckrSymb column missing.")
    if "SctySrs" in df.columns:
        df = df[df["SctySrs"].astype(str).str.strip().isin(["EQ"])]
    if "FinInstrmTp" in df.columns:
        # Keep normal stocks when instrument type is supplied.
        st = df["FinInstrmTp"].astype(str).str.strip()
        df = df[(st.isin(["STK","ETF"])) | (st == "")]
    cols = [c for c in KEEP if c in df.columns]
    df = df[cols].copy()
    rename = {
        "TradDt":"Date","TckrSymb":"Symbol","SctySrs":"Series",
        "OpnPric":"Open","HghPric":"High","LwPric":"Low","ClsPric":"Close",
        "PrvsClsgPric":"PrevClose","TtlTradgVol":"Volume",
        "TtlTrfVal":"TradedValue","TtlNbOfTxsExctd":"Trades"
    }
    df = df.rename(columns=rename)
    for c in ["Open","High","Low","Close","PrevClose","Volume","TradedValue","Trades"]:
        if c in df:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df["Symbol"] = df["Symbol"].astype(str).str.strip().str.upper()
    return df.dropna(subset=["Date","Symbol","Close"]).drop_duplicates(["Date","Symbol"])

def download_day(d: date, timeout=20) -> Path | None:
    out = BHAV_DIR / f"{d.isoformat()}.csv"
    if out.exists() and out.stat().st_size > 100:
        return out
    if d.weekday() >= 5:
        return None
    s = requests.Session()
    for url in _urls(d):
        try:
            r = s.get(url, headers=HEADERS, timeout=timeout)
            if r.status_code != 200 or len(r.content) < 1000:
                continue
            with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                names = [n for n in z.namelist() if n.lower().endswith(".csv")]
                if not names:
                    continue
                with z.open(names[0]) as f:
                    raw = pd.read_csv(f)
            df = _normalize(raw)
            if len(df) < 100:
                continue
            df.to_csv(out, index=False)
            return out
        except Exception:
            continue
    return None

def update_history(target_sessions=90, lookback_calendar_days=170, status_cb=None):
    existing = sorted(BHAV_DIR.glob("*.csv"))
    today = date.today()
    success_dates = {p.stem for p in existing}
    # Reuse cache; fetch missing days backwards until target count is reached.
    attempts = 0
    d = today
    while len(success_dates) < target_sessions and attempts < lookback_calendar_days:
        if status_cb:
            status_cb(f"Checking NSE data for {d.isoformat()} — {len(success_dates)}/{target_sessions} sessions cached")
        p = download_day(d)
        if p:
            success_dates.add(p.stem)
        d -= timedelta(days=1)
        attempts += 1
        time.sleep(0.03)
    # Also refresh the most recent 8 calendar days in case a new session is available.
    for i in range(0, 8):
        d2 = today - timedelta(days=i)
        if status_cb:
            status_cb(f"Refreshing latest NSE session: {d2.isoformat()}")
        p = download_day(d2)
        if p:
            success_dates.add(p.stem)

    # Keep the configured rolling history bounded. These files are downloadable cache, not user data.
    # This prevents PC/Supabase storage from growing forever while preserving the full 420-session model window.
    files = sorted(BHAV_DIR.glob('*.csv'))
    if target_sessions and len(files) > int(target_sessions):
        for old in files[:-int(target_sessions)]:
            try: old.unlink()
            except Exception: pass
    return len(list(BHAV_DIR.glob('*.csv')))

def load_history(max_sessions=120) -> pd.DataFrame:
    files = sorted(BHAV_DIR.glob("*.csv"))
    if not files:
        return pd.DataFrame()
    files = files[-max_sessions:]
    frames = []
    for p in files:
        try:
            frames.append(pd.read_csv(p, parse_dates=["Date"]))
        except Exception:
            pass
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)
    return df.sort_values(["Symbol","Date"]).drop_duplicates(["Symbol","Date"], keep="last")

def cache_status():
    files = sorted(BHAV_DIR.glob("*.csv"))
    return {
        "sessions": len(files),
        "first": files[0].stem if files else None,
        "last": files[-1].stem if files else None
    }
