INDIA INVESTMENT RADAR 5.0 SMART — ALL NSE
============================================

WHAT THIS VERSION FIXES
-----------------------
The earlier radar used the recommendation/liquidity filter as the visible stock universe.
That could leave roughly a few hundred stocks visible even though NSE has many more EQ symbols.

Version 5.0 separates two things:

1. VISIBILITY / SCANNING
   Every NSE EQ symbol present in your downloaded NSE bhavcopy is shown in:
   Stocks > Today's Ranking — ALL NSE
   and in Full Stock Card.

2. RECOMMENDATION ELIGIBILITY
   Only stocks that pass minimum history, price, volume and traded-value rules can become
   STRONG BUY / BUY / BUY ON PULLBACK / WATCH recommendations.

This means the software does not hide illiquid/new/low-price stocks, but it also does not
pretend they are safe recommendation candidates.

IMPORTANT ABOUT "420"
---------------------
"NSE history days: 420" means 420 TRADING SESSIONS OF HISTORY.
It does NOT mean 420 stocks.

The top dashboard now separately shows:
- All NSE EQ = total different stocks/symbols in local NSE data
- Eligible = number passing recommendation eligibility rules

STOCKS PAGE
-----------
Today's Ranking — ALL NSE
- All symbols in local NSE EQ bhavcopy
- Search any symbol/company
- Filter: All / Eligible / Not Eligible
- Shows why a stock is not eligible

Qualified Picks
- Only actionable/qualified candidates
- This remains filtered intentionally

Full Stock Card
- Search/select any NSE symbol
- If enough history exists: Current, Entry, S1/S2, R1/R2, T1/T2, Stop, R:R,
  duration, Technical, Fundamental, Momentum, Overall, historical evidence,
  confidence, news/corporate-action gate and eligibility reason.
- Brand-new stocks with insufficient history remain visible but show INSUFFICIENT HISTORY.

SMART FEATURES INCLUDED
-----------------------
- Fast cached startup
- Strong Buy Action Board
- Entry validity / Don't Chase
- Position sizing
- Portfolio import
- News/results safety gate
- Backtest + walk-forward validation
- Accuracy dashboard
- Alerts
- Backups
- Market outlook
- ETFs / Gold
- Mutual funds
- Fixed income

INSTALL — SIMPLE
----------------
1. CLOSE the Radar browser and the black command window.
2. Extract this update ZIP anywhere.
3. Double-click INSTALL_SMART_ALL_NSE_UPDATE.bat
4. It looks first for C:\India_Investment_Radar.
5. If your Radar is elsewhere, the installer asks you for that folder.
6. Your existing DATA folder is NOT replaced.
7. After install, the app starts.
8. Click REBUILD DASHBOARD ONLY once.

After that, daily use is:
run.bat -> DAILY UPDATE -> ACTION BOARD / ALL NSE Ranking.

Your historical NSE files, recommendation history, portfolio and local settings remain in the existing app folder.
