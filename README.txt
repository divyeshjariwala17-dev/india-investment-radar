INDIA INVESTMENT RADAR — SMART UPDATE v4
========================================

THIS UPDATE IS FOR YOUR ALREADY-WORKING APP.
It is designed to KEEP your existing NSE history, backtests, recommendation history,
portfolio file, Alpha Vantage settings and other data inside the existing data folder.

HOW TO UPDATE — ONE TIME ONLY
-----------------------------
1. CLOSE the currently running India Investment Radar browser tab and black command window.

2. Extract the SMART UPDATE ZIP.

3. Copy ALL files from the extracted update folder into your existing folder:

   C:\India_Investment_Radar

4. Windows will ask whether to Replace files with the same names.
   Choose: REPLACE THE FILES.

   IMPORTANT:
   Do NOT delete your existing data folder.
   This update does not require deleting your old market history.

5. Double-click:

   UPDATE_AND_START.bat

6. When the app opens, click once:

   🧠 BUILD ALL VALIDATION (ONE TIME)

   This builds the normal backtest + stricter walk-forward evidence.
   It can take several minutes. Let it finish.

7. Then click:

   ⚡ REBUILD DASHBOARD ONLY

8. Done.

NORMAL DAILY USE AFTER THIS
---------------------------
1. Double-click run.bat
2. The dashboard should open quickly from SAVED RESULTS.
3. After market close click DAILY UPDATE once.
4. Review ACTION BOARD first.
5. Then open Full Decision Card for anything you may consider.

NEW FEATURES
------------
1. FAST START
   The app opens from saved calculated results instead of recalculating the whole market every time.

2. STRONG BUY ACTION BOARD
   Signals are now:
   🔥 STRONG BUY
   🟢 BUY
   🟡 BUY ON PULLBACK
   👀 WATCH
   🔴 AVOID

   The software is allowed to show NO STRONG BUY TODAY.

3. ENTRY VALIDITY / DO NOT CHASE
   Every stock can show:
   ENTRY VALID
   WAIT FOR PULLBACK
   MISSED ENTRY / DON'T CHASE
   WAIT FOR CONFIRMATION
   SETUP INVALID

4. POSITION SIZE CALCULATOR
   Enter total capital + maximum risk per trade.
   It calculates quantity, capital required, maximum loss at stop and exposure.

5. MY PORTFOLIO
   Import a CSV/XLSX export from Dhan / Choice / Nuvama.
   No broker API is required.
   You can save the normalized portfolio locally.
   It shows model signal, P&L, HOLD/ADD/REDUCE/REVIEW logic and sector concentration.

6. NEWS / RESULTS SAFETY GATE
   DAILY UPDATE attempts to read recent official NSE corporate announcements.
   Serious event keywords can block a signal.
   If this source is unavailable, STRONG BUY is automatically capped rather than pretending the check passed.

7. BETTER ACCURACY DASHBOARD
   Tracks actual outcomes and shows results by category, signal, market regime and sector when enough results exist.

8. WALK-FORWARD VALIDATION
   Strong Buy for Swing/Short Term now requires both normal backtest evidence AND walk-forward evidence.
   This helps reduce over-optimistic backtests.

9. SMART ALERT CENTER
   Shows Strong Buy, valid entry, Target/Stop outcomes and market-regime changes after DAILY UPDATE.

10. DATA HEALTH + AUTOMATIC BACKUP
    System Check shows NSE, mutual funds, news gate, backtest, walk-forward and fast-cache status.
    DAILY UPDATE creates rotating local backups of important settings/history/results.

STRONG BUY GATE
---------------
A Swing/Short Strong Buy normally requires ALL of these:
- Overall >= 85
- Technical >= 80
- Momentum >= 80
- R:R >= 2.0
- Backtest sample >= 50
- Backtest win rate >= 60%
- Walk-forward sample >= 20 in the current market regime/score band
- Walk-forward win rate >= 55%
- Market not WEAK
- Entry still VALID
- No blocking corporate action
- NSE announcement safety gate PASS
- Confidence HIGH

Long-term Strong Buy uses fresh/high-quality fundamentals instead of forcing a short-term trade backtest logic.

WHY CONFIDENCE MAY STILL BE MEDIUM
----------------------------------
MEDIUM is not a software error.
The system will only show HIGH when its evidence gate is strong enough.
Do not change thresholds just to create more HIGH-confidence results.

PERMANENT USE
-------------
Yes. This remains in your local app folder and does not expire.
Your saved data remains as long as you keep the folder and its data subfolder.
External NSE/MF data formats can change in future; if that happens, only that connector may need an update.

SECURITY
--------
Do not use the Alpha Vantage key previously pasted into ChatGPT.
If you use Alpha Vantage, regenerate the key and enter the NEW key only inside your local Settings page.

IMPORTANT
---------
This is a research/decision-support system. No stock-market model can guarantee future returns.
Its confidence and performance should be judged by measured backtest/walk-forward/forward results.
