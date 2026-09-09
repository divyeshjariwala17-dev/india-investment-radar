from __future__ import annotations
from pathlib import Path
from datetime import datetime
import zipfile, shutil

BASE=Path(__file__).resolve().parent
DATA=BASE/'data'
BACKUPS=BASE/'backups'
BACKUPS.mkdir(exist_ok=True)

# User-created/important state. Large downloadable market history is deliberately not required
# for recovery because it can be refreshed from the source.
KEEP_FILES=['config.json','fundamentals_seed.csv','.env']
KEEP_DATA=[
    'recommendation_history.csv','backtest_stats.csv','walk_forward_stats.csv','alpha_fundamentals.csv',
    'corporate_actions.csv','corporate_announcements.csv','fixed_income_watchlist.csv','my_portfolio.csv',
    'portfolio_goals.csv','allocation_plans.csv','investment_options.csv','ipo_watchlist.csv','physical_metals_state.json',
    'alerts.csv','cross_asset.csv','cross_asset_history.csv'
]
KEEP_DIRS=['dashboard_cache','mutual_funds','crypto','macro']


def create_backup(keep=12):
    stamp=datetime.now().strftime('%Y%m%d_%H%M%S')
    out=BACKUPS/f'radar_backup_{stamp}.zip'
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        for name in KEEP_FILES:
            p=BASE/name
            if p.exists():z.write(p,p.relative_to(BASE))
        for name in KEEP_DATA:
            p=DATA/name
            if p.exists():z.write(p,p.relative_to(BASE))
        for name in KEEP_DIRS:
            d=DATA/name
            if d.exists():
                for p in d.rglob('*'):
                    if p.is_file():z.write(p,p.relative_to(BASE))
    old=sorted(BACKUPS.glob('radar_backup_*.zip'),reverse=True)
    for p in old[int(keep):]:
        try:p.unlink()
        except Exception:pass
    return out


def latest_backup():
    xs=sorted(BACKUPS.glob('radar_backup_*.zip'),reverse=True)
    return xs[0] if xs else None


def restore_backup(path=None):
    src=Path(path) if path else latest_backup()
    if src is None or not src.exists():
        return {'ok':False,'message':'No backup file is available.'}
    # Safety backup before restore.
    try:create_backup()
    except Exception:pass
    with zipfile.ZipFile(src,'r') as z:
        z.extractall(BASE)
    return {'ok':True,'message':f'Restored {src.name}','path':str(src)}
