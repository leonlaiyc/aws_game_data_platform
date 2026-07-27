"""Static configuration for the Aurora Games event simulator.

All entity names are generic on purpose (see README) - this is a fictional
B2B gaming data platform with no relation to any real company.
"""
from datetime import date

SEED = 42
START_DATE = date(2026, 5, 1)
NUM_DAYS = 60
NUM_PLAYERS = 5000

# A client_site is a B2B operator that embeds our games/platform on their own site.
# Region and settlement currency are fixed per site - a real platform would support
# per-transaction FX, but a static rate table (see fx.py) is enough for this project.
CLIENT_SITES = {
    "site_a": {"region": "sea", "currency": "USD"},
    "site_b": {"region": "latam", "currency": "BRL"},
    "site_c": {"region": "eu", "currency": "EUR"},
}

GAMES = {
    "game_01": "slots",
    "game_02": "slots",
    "game_03": "slots",
    "game_04": "table",
    "game_05": "table",
    "game_06": "live",
    "game_07": "live",
    "game_08": "sports",
}

# Each site only enables a subset of the catalog - realistic for a B2B platform
# where operators pick which games to integrate.
SITE_GAME_CATALOG = {
    "site_a": ["game_01", "game_02", "game_04", "game_06", "game_08"],
    "site_b": ["game_01", "game_03", "game_05", "game_06", "game_07"],
    "site_c": ["game_02", "game_03", "game_04", "game_07", "game_08"],
}

PLATFORM_WEIGHTS = {"web": 0.45, "android": 0.4, "ios": 0.15}
AUTH_METHODS = ["password", "sso", "otp"]
PAYMENT_METHODS = ["card", "bank_transfer", "e_wallet"]
BONUS_POOL = ["welcome_bonus", "reload_10", "cashback_5", "vip_reload"]
ACQUISITION_CHANNELS = ["organic", "affiliate", "paid_social", "cross_promo"]

# --- Scenario hooks (ground truth is written to scenario_manifest.json) ---

# 1. Retention/revenue drop: a systemic issue (e.g. a broken payment provider)
#    depresses activity and bet volume for one site, for one week.
RETENTION_DROP_SITE = "site_b"
RETENTION_DROP_START_DAY = 40  # 0-indexed day offset from START_DATE
RETENTION_DROP_END_DAY = 46
RETENTION_DROP_ACTIVITY_FACTOR = 0.5
RETENTION_DROP_BET_FACTOR = 0.6

# 2. Arbitrage ring: N accounts sharing device/IP fingerprints, cycling
#    deposit -> minimal play -> withdrawal far faster and more completely
#    than genuine players.
ARBITRAGE_RING_SITE = "site_a"
ARBITRAGE_RING_SIZE = 6
ARBITRAGE_RING_REGISTRATION_DAY = 20
ARBITRAGE_RING_START_DAY = 25
ARBITRAGE_RING_END_DAY = 35
