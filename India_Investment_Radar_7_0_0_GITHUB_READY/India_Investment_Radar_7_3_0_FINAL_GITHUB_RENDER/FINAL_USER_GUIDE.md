# India Investment Radar 7.3.0 FINAL MASTER — Operating Guide

## Daily use
1. Open **India Investment Radar 7.3.0**.
2. Read **Daily Recommendations** first.
3. Check **Market Intelligence** and **Market Outlook** when making a new market decision.
4. Run **DAILY UPDATE — UPDATE EVERYTHING** once after the Indian market closes for normal EOD use.
5. If you have new money, open **Best Use of My Money**, enter amount + duration/exact date + risk, and review the exact allocation/timing/reserve explanation.
6. Open the exact instrument card before acting. Read Why / Why Not / What Changes the Call / data freshness / event risks.
7. Record executed investments in **My Portfolio** as individual purchase lots.
8. Check **Alerts** and **Corporate Events** for owned/considered investments.

## Recommendation philosophy
The Radar does not force a Buy. Valid outputs include Strong Buy, Buy, Buy on Pullback, Watch, Avoid, Invest, SIP, Stagger, Wait, Hold Reserve, Review Required, Hold, Add, Reduce, Exit, Switch or Rebalance depending on asset type.

Company evidence remains primary. Sector evidence confirms. FII/FPI-DII, derivatives, breadth, macro/VIX and global context modify regime/confidence. Critical corporate events, surveillance and broken data can cap/block fresh action.

## Market Intelligence
The connected Market Intelligence layer includes, where free/reliable data is available:
- FII/FPI and DII 1D/5D/20D/60D flow regimes.
- Participant-wise F&O positioning and derivatives context.
- Market breadth and participation.
- Security-wise delivery confirmation.
- India VIX/macro/global context.
- Index valuation reference.
- FPI sector allocation/flow reference.
- AMFI SIP/domestic-flow reference.
- Surveillance, bulk/block deals and short-selling reference.
- Public market/stock news context; official exchange filings remain the stronger company-event safety gate.

## Forecast / Market Outlook
Forecasts are probability-based scenario estimates, not guaranteed point predictions. The app shows horizon, bias, positive probability, historical-similar range/median, confidence and market-intelligence adjustment for Next Day, 1 Week, 15 Days, 1 Month and 3 Months where sufficient history exists.

## Data status meanings
- **FRESH / VERIFIED** — normal use.
- **PROVISIONAL** — current but officially provisional, e.g. same-day NSE FII/FPI.
- **FALLBACK** — safe backup/cached source used.
- **STALE / OLD** — refresh/review before relying on a new action.
- **MISSING / FAILED** — source is unavailable; confidence may be reduced or recommendation refused.
- **OPTIONAL** — feature/source is not required for core operation.

## Data Vault
Each successful recommendation rebuild stores a dated snapshot of the actual known/calculated state. Do not use later data to rewrite an old recommendation. You can browse snapshot dates and an instrument's historical Radar state from Data Vault.

## Backup / sync
- Local backup: System Check or `BACKUP_DATA_NOW.bat`.
- Supabase: System → Sync Center.
- Google Drive/Sheet archive: System → Sync Center.
- Complete export: System → Data Vault → Complete Data Archive.

## When something is wrong
1. Open **Auto Data Center** — find the exact source that is stale/missing/failed.
2. Run Daily Update once.
3. Open **System Check**.
4. On PC run `VERIFY_INSTALLATION.bat`.
5. If dependencies are damaged, run `REPAIR_INSTALLATION.bat`; it does not delete the data folder.
6. Do not reinstall random old versions for a single source failure.

## Security
Never expose Supabase secret keys, Google service-account JSON, broker credentials or other private keys in GitHub, screenshots, shared ZIPs or chat. This Radar does not need broker auto-order placement for its core research workflow.
