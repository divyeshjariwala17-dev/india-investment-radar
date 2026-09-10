from pathlib import Path
import json

BASE = Path(__file__).resolve().parent
CONFIG_PATH = BASE / "config.json"

if CONFIG_PATH.exists():
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
else:
    cfg = {}

cfg["app_version"] = "7.0.2 FULL COVERAGE — AMFI CURRENT + FD DIRECTORY + POST OFFICE"

cfg.setdefault("precious_assets", {
    "GOLD": {
        "name": "Gold market proxy",
        "symbols": ["GOLDBEES", "HDFCGOLD", "SETFGOLD", "KOTAKGOLD"]
    },
    "SILVER": {
        "name": "Silver market proxy",
        "symbols": ["SILVERBEES"]
    }
})

cfg.setdefault("ipo", {
    "official_nse_refresh": True,
    "gmp_weight": "LOW",
    "separate_listing_and_long_term_scores": True
})

cfg.setdefault("investment_universe", [
    "STOCKS",
    "ETF",
    "MUTUAL FUNDS",
    "BONDS/FIXED INCOME",
    "PHYSICAL GOLD",
    "PHYSICAL SILVER",
    "CRYPTO",
    "IPO/SME IPO",
    "REIT/INVIT",
    "FD/RD",
    "PPF/NSC/KVP/SCSS/SUKANYA/POST OFFICE",
    "NPS",
    "G-SEC/T-BILL/SDL",
    "INTERNATIONAL ETF/FUND",
    "SECONDARY GOLD BONDS",
    "REAL ESTATE",
    "PMS/AIF",
    "CASH/OTHER"
])

cfg.setdefault("crypto_symbols", [
    "BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "DOGE", "AVAX",
    "LINK", "DOT", "TRX", "LTC", "BCH", "XLM", "UNI"
])

cfg["optimizer"] = {
    "default_amount": 50000,
    "default_duration_days": 182,
    "default_risk": "AUTO",
    "minimum_reserve_pct": 5,
    "consider_existing_portfolio": True,
    "allow_hold_cash": True,
    "same_13_question_explanation": True,
    "exact_required_date_filter": True,
    "target_return_mode": True,
    "tax_inflation_assumptions_editable": True
}

cfg["segment_drilldown"] = {
    "enabled": True,
    "path": "segment -> category/product form -> exact product -> amount -> timing -> scenario -> explanation -> track",
    "recommended_choice_preselected": True
}

cfg["physical_reference"] = {
    "automatic_converted_reference": True,
    "method": "Global futures × USDINR conversion; local/dealer quote overrides",
    "not_retail_final_rate": True
}

cfg.setdefault("corporate_events_back_days", 45)
cfg.setdefault("corporate_events_forward_days", 120)
cfg.setdefault("mf_auto_segment_candidates", 30)
cfg.setdefault("mf_deep_filter_max", 40)
cfg["mutual_funds_full_universe"] = True
cfg["corporate_events_full"] = True

CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
print("Configuration updated to India Investment Radar 7.0.2.")
