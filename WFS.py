"""
Adani Natural Resources — WIM (Weather Intelligence Mining)
v3.0 — Supabase DB integration, clock fix, sidebar redesign,
        hourly precipitation for all days, mining impact column
"""
import os, json, requests, collections, base64, concurrent.futures
import streamlit.components.v1 as components
from datetime import datetime, timedelta
import pytz
import streamlit as st

# ── Load .env for local development ──
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed — env vars must be set another way

# ── Supabase client (optional — falls back to JSON if not configured) ──
_supabase_client = None
def _get_supabase():
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_KEY", "")
    if not url or not key:
        return None
    try:
        from supabase import create_client
        _supabase_client = create_client(url, key)
        return _supabase_client
    except Exception:
        return None

st.set_page_config(
    page_title="WIM — Weather Intelligence Mining | Adani Natural Resources",
    page_icon="\U0001f326",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Load assets ──
def load_asset_b64(path):
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except Exception:
        return ""

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_CS_DIR     = "/workspaces/weather-forecast-mines"

def _asset_path(filename):
    for base in [_SCRIPT_DIR, _CS_DIR]:
        p = os.path.join(base, filename)
        if os.path.exists(p): return p
    return os.path.join(_SCRIPT_DIR, filename)

LOGO_PATH = _asset_path("Adani_2012_logo.png")
FONT_PATH = _asset_path("adani-regular.ttf")
LOGO_B64  = load_asset_b64(LOGO_PATH)
FONT_B64  = load_asset_b64(FONT_PATH)
_FONT_LOADED = bool(FONT_B64)
_LOGO_LOADED = bool(LOGO_B64)

LOGO_HTML  = f'<img src="data:image/png;base64,{LOGO_B64}" style="height:44px;display:block;" alt="Adani">' if LOGO_B64 else '<span style="font-size:1.6rem;font-weight:900;color:#0B74B0;">adani</span>'
_FONT_STACK = ("'AdaniFont', 'Helvetica Neue', Arial, sans-serif" if FONT_B64 else "'Helvetica Neue', Arial, sans-serif")
FONT_FACE  = f"@font-face{{font-family:'AdaniFont';src:url('data:font/truetype;base64,{FONT_B64}') format('truetype');font-weight:normal;font-style:normal;}}" if FONT_B64 else ""

_CSS = f"""<style>
{FONT_FACE}
*,*::before,*::after{{box-sizing:border-box;}}
html,body,[class*="css"],.stApp,.stApp *,[data-testid="stAppViewContainer"],[data-testid="stAppViewContainer"] *,.block-container,.block-container *{{font-family:{_FONT_STACK} !important;}}
.stApp{{background:#F8F9FA !important;color:#1A1A2E !important;}}
#MainMenu,footer{{visibility:hidden;}}
header[data-testid="stHeader"]{{background:transparent !important;z-index:999999 !important;}}
header[data-testid="stHeader"] button[kind="header"],header[data-testid="stHeader"] .stDeployButton,[data-testid="stToolbar"]{{display:none !important;}}
.block-container{{padding:0.25rem 2rem 2rem 2rem !important;max-width:1400px !important;margin:0 auto !important;}}
[data-testid="stAppViewContainer"]>.main{{background:#F8F9FA;padding-top:0 !important;}}
.wim-nav{{background:#FFFFFF;border-bottom:1px solid #E2E8F0;height:64px;display:flex;align-items:center;justify-content:space-between;position:fixed;top:0;left:0;right:0;z-index:9999;padding:0 2rem 0 2.5rem;box-shadow:0 1px 4px rgba(0,0,0,0.06);}}
.wim-nav-spacer{{height:56px;}}
.wim-nav-left{{display:flex;align-items:center;gap:16px;}}
.wim-nav-sep{{width:1px;height:28px;background:linear-gradient(180deg,#0B74B0,#16A34A);}}
.wim-nav-text{{line-height:1.25;}}
.wim-nav-title{{font-size:0.875rem;font-weight:700;background:linear-gradient(90deg,#0B74B0,#16A34A);-webkit-background-clip:text;background-clip:text;color:transparent;}}
.wim-nav-sub{{font-size:0.65rem;font-weight:500;color:#94A3B8;letter-spacing:0.1em;text-transform:uppercase;margin-top:1px;}}
.wim-page{{margin-top:0;padding-top:0;}}
.wim-site-row{{display:flex;align-items:baseline;gap:8px;margin:0 0 4px 0;}}
.wim-site-name{{font-size:1.375rem;font-weight:700;color:#1A1A2E;}}
.wim-site-coord{{font-size:0.75rem;color:#94A3B8;}}
.wim-alert{{border-radius:8px;padding:14px 18px;margin:14px 0;font-size:0.875rem;line-height:1.6;border:1px solid;border-left:5px solid;}}
.wim-alert-label{{font-size:0.65rem;font-weight:800;letter-spacing:0.12em;text-transform:uppercase;margin-bottom:6px;display:flex;align-items:center;gap:6px;}}
.wim-alert-label::before{{content:"";display:inline-block;width:8px;height:8px;border-radius:50%;flex-shrink:0;}}
.wim-alert-high{{background:#FFF1F2;border-color:#FECDD3;border-left-color:#DC2626;color:#881337;}}
.wim-alert-high .wim-alert-label::before{{background:#DC2626;}}
.wim-alert-moderate{{background:#FFFBEB;border-color:#FDE68A;border-left-color:#D97706;color:#78350F;}}
.wim-alert-moderate .wim-alert-label::before{{background:#D97706;}}
.wim-alert-low{{background:#F0FDF4;border-color:#BBF7D0;border-left-color:#16A34A;color:#14532D;}}
.wim-alert-low .wim-alert-label::before{{background:#16A34A;}}
.wim-alert-none{{background:#F8FAFC;border-color:#E2E8F0;border-left-color:#94A3B8;color:#475569;}}
.wim-alert-none .wim-alert-label::before{{background:#94A3B8;}}
.wim-section{{font-size:0.65rem;font-weight:800;letter-spacing:0.12em;text-transform:uppercase;color:#94A3B8;margin:8px 0 10px 0;padding-bottom:6px;border-bottom:1px solid #E2E8F0;}}
.wim-metric{{background:#FFFFFF;border:1px solid #E2E8F0;border-radius:10px;padding:16px 18px;height:100%;}}
.wim-metric-label{{font-size:0.65rem;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;color:#94A3B8;margin-bottom:6px;}}
.wim-metric-value{{font-size:1.375rem;font-weight:700;color:#1A1A2E;letter-spacing:-0.02em;line-height:1.2;}}
.wim-day{{background:#FFFFFF;border:1px solid #E2E8F0;border-radius:10px;padding:14px 10px;text-align:center;height:100%;}}
.wim-day-active{{border-color:#0B74B0;border-width:2px;}}
.wim-day-label{{font-size:0.65rem;font-weight:800;letter-spacing:0.1em;text-transform:uppercase;color:#94A3B8;}}
.wim-day-date{{font-size:0.68rem;color:#94A3B8;margin:2px 0 8px;}}
.wim-day-cond{{font-size:0.82rem;font-weight:600;color:#1A1A2E;margin-bottom:4px;}}
.wim-day-rain{{font-size:1.1rem;font-weight:700;color:#0B74B0;line-height:1.2;}}
.wim-day-temp{{font-size:0.7rem;color:#64748B;margin-top:4px;}}
.wim-day-flag{{display:inline-block;font-size:0.65rem;font-weight:700;border-radius:4px;padding:2px 8px;margin-top:6px;}}
.flag-clear{{background:#F0FDF4;color:#16A34A;}}
.flag-light{{background:#EFF6FF;color:#1D4ED8;}}
.flag-moderate{{background:#FFFBEB;color:#D97706;}}
.flag-heavy{{background:#FFF1F2;color:#DC2626;}}
.flag-drizzle{{background:#F0F9FF;color:#0EA5E9;}}
.flag-lightning{{background:#FEF3C7;color:#F59E0B;}}
.wim-accum{{background:#FFFFFF;border:1px solid #E2E8F0;border-radius:10px;padding:14px 10px;text-align:center;height:100%;}}
.wim-accum-period{{font-size:0.62rem;font-weight:800;letter-spacing:0.1em;text-transform:uppercase;color:#94A3B8;}}
.wim-accum-val{{font-size:1.35rem;font-weight:700;color:#1A1A2E;margin:4px 0 2px;}}
.wim-accum-pop{{font-size:0.7rem;color:#94A3B8;}}
.wim-accum-risk{{font-size:0.68rem;font-weight:700;margin-top:4px;}}
.risk-safe{{color:#16A34A;}}.risk-watch{{color:#D97706;}}.risk-high{{color:#DC2626;}}
.acc-safe{{border-top:3px solid #16A34A;}}.acc-watch{{border-top:3px solid #D97706;}}.acc-high{{border-top:3px solid #DC2626;}}
.wim-table{{width:100%;border-collapse:collapse;background:#FFFFFF;border:1px solid #E2E8F0;border-radius:10px;overflow:hidden;font-size:0.845rem;}}
.wim-table thead tr{{background:#F8FAFC;}}
.wim-table th{{padding:10px 16px;text-align:left;font-size:0.62rem;font-weight:800;letter-spacing:0.1em;text-transform:uppercase;color:#94A3B8;border-bottom:1px solid #E2E8F0;white-space:nowrap;}}
.wim-table td{{padding:11px 16px;border-bottom:1px solid #F1F5F9;color:#1A1A2E;font-weight:500;vertical-align:middle;}}
.wim-table tr:last-child td{{border-bottom:none;}}
.wim-table tr:hover td{{background:#FAFAFA;}}
.td-warn{{background:#FFFBEB !important;color:#92400E;font-weight:700;}}
.td-alert{{background:#FFF1F2 !important;color:#9F1239;font-weight:700;}}
.wim-badge{{display:inline-block;border-radius:4px;padding:2px 8px;font-size:0.68rem;font-weight:700;white-space:nowrap;}}
.b-none{{background:#F1F5F9;color:#64748B;}}.b-drizzle{{background:#EFF6FF;color:#1D4ED8;}}
.b-light{{background:#DBEAFE;color:#1E40AF;}}.b-moderate{{background:#BFDBFE;color:#1E40AF;}}
.b-heavy{{background:#FEF3C7;color:#D97706;}}.b-vheavy{{background:#FEE2E2;color:#DC2626;}}
.b-lightning{{background:#FFF1F2;color:#DC2626;}}
.b-stop{{background:#FEE2E2;color:#991B1B;}}.b-caution{{background:#FEF3C7;color:#92400E;}}
.b-monitor{{background:#BFDBFE;color:#1E40AF;}}.b-clear-ops{{background:#D1FAE5;color:#065F46;}}
.wim-mc{{background:#FFFFFF;border:1px solid #E2E8F0;border-radius:10px;padding:16px 18px;overflow-x:auto;}}
.wim-mc-title{{font-size:0.62rem;font-weight:800;letter-spacing:0.1em;text-transform:uppercase;color:#94A3B8;margin-bottom:10px;}}
hr.wim-hr{{border:none;border-top:1px solid #E2E8F0;margin:12px 0;}}
.stColumns{{gap:12px !important;}}
[data-testid="stHorizontalBlock"]{{gap:12px !important;}}
/* Sidebar CSS overrides removed to keep layout stable */
.stTabs [data-baseweb="tab-list"]{{gap:0;border-bottom:2px solid #E2E8F0;background:transparent;}}
.stTabs [data-baseweb="tab"]{{background:transparent !important;color:#64748B !important;font-size:0.82rem !important;font-weight:600 !important;padding:10px 18px !important;border:none !important;border-bottom:2px solid transparent !important;margin-bottom:-2px !important;opacity:1 !important;visibility:visible !important;}}
.stTabs [data-baseweb="tab"]:hover{{color:#0B74B0 !important;background:#F0F7FF !important;border-radius:6px 6px 0 0;}}
.stTabs [aria-selected="true"]{{color:#0B74B0 !important;border-bottom:2px solid #0B74B0 !important;background:transparent !important;font-weight:700 !important;}}
.stTabs [data-baseweb="tab-highlight"],.stTabs [data-baseweb="tab-border"]{{display:none !important;}}
.streamlit-expanderHeader{{font-size:0.82rem !important;font-weight:700 !important;color:#1A1A2E !important;background:#F8FAFC !important;border:1px solid #E2E8F0 !important;border-radius:8px !important;padding:10px 14px !important;}}
.streamlit-expanderContent{{border:1px solid #E2E8F0 !important;border-top:none !important;border-radius:0 0 8px 8px !important;padding:14px !important;}}
.hour-row-rain{{background:#EFF6FF;}}.hour-row-heavy{{background:#FFF7ED;}}.hour-row-alert{{background:#FFF1F2;}}
.db-badge-ok{{display:inline-block;background:#D1FAE5;color:#065F46;border-radius:4px;padding:2px 8px;font-size:0.65rem;font-weight:700;}}
.db-badge-local{{display:inline-block;background:#FEF3C7;color:#92400E;border-radius:4px;padding:2px 8px;font-size:0.65rem;font-weight:700;}}
/* Dropdown - Clean Minimal Design - FORCE DARK TEXT */
div[data-testid="stSelectbox"]{{margin-left:auto !important;max-width:180px !important;}}
div[data-testid="stSelectbox"] > div > div{{background:#FFFFFF !important;border:1px solid #6B7280 !important;border-radius:6px !important;}}
div[data-testid="stSelectbox"] > div > div:hover{{border-color:#374151 !important;}}
div[data-testid="stSelectbox"] *{{color:#000000 !important;}}
div[data-testid="stSelectbox"] [role="button"],div[data-testid="stSelectbox"] [role="button"] *,div[data-testid="stSelectbox"] input,div[data-testid="stSelectbox"] span{{color:#111827 !important;font-size:14px !important;font-weight:600 !important;}}
div[data-testid="stSelectbox"] [role="listbox"]{{background:#FFFFFF !important;border:1px solid #D1D5DB !important;border-radius:6px !important;box-shadow:0 4px 6px rgba(0,0,0,0.1) !important;}}
div[data-testid="stSelectbox"] [role="option"],div[data-testid="stSelectbox"] [role="option"] *{{color:#111827 !important;font-size:14px !important;}}
div[data-testid="stSelectbox"] [role="option"]:hover{{background:#F3F4F6 !important;}}
div[data-testid="stSelectbox"] [role="option"][aria-selected="true"],div[data-testid="stSelectbox"] [role="option"][aria-selected="true"] *{{background:#0B74B0 !important;color:#FFFFFF !important;font-weight:600 !important;}}

/* ══════════════════════════════════════════════════════════════
   RESPONSIVE STYLES - Mobile, Tablet, Desktop
   ══════════════════════════════════════════════════════════════ */

/* Large screens (1200px+) - Default styles apply */

/* Tablets and small laptops (768px - 1199px) */
@media (max-width: 1199px) {{
    .block-container{{padding:0.25rem 1.5rem 1.5rem 1.5rem !important;}}
    .wim-day{{padding:12px 8px;}}
    .wim-day-rain{{font-size:1rem;}}
    .wim-metric{{padding:14px 16px;}}
    .wim-metric-value{{font-size:1.25rem;}}
}}

/* Tablets portrait and large phones (576px - 767px) */
@media (max-width: 767px) {{
    .block-container{{padding:0.25rem 1rem 1rem 1rem !important;}}
    .wim-nav{{padding:0 1rem 0 1rem;height:56px;}}
    .wim-nav-spacer{{height:48px;}}
    .wim-nav-title{{font-size:0.8rem;}}
    .wim-nav-sub{{font-size:0.6rem;}}
    
    .wim-site-name{{font-size:1.25rem;}}
    .wim-site-coord{{font-size:0.7rem;}}
    
    div[data-testid="stSelectbox"]{{max-width:160px !important;}}
    
    .wim-day{{padding:10px 6px;border-radius:8px;}}
    .wim-day-label{{font-size:0.6rem;}}
    .wim-day-date{{font-size:0.65rem;}}
    .wim-day-cond{{font-size:0.75rem;}}
    .wim-day-rain{{font-size:0.95rem;}}
    .wim-day-temp{{font-size:0.65rem;}}
    .wim-day-flag{{font-size:0.6rem;padding:2px 6px;}}
    
    .wim-metric{{padding:12px 14px;border-radius:8px;}}
    .wim-metric-label{{font-size:0.6rem;}}
    .wim-metric-value{{font-size:1.1rem;}}
    
    .wim-section{{font-size:0.6rem;margin:6px 0 8px 0;}}
    
    .stTabs [data-baseweb="tab"]{{font-size:0.75rem !important;padding:8px 12px !important;}}
    
    .wim-table{{font-size:0.75rem;}}
    .wim-table th,.wim-table td{{padding:8px 10px;}}
}}

/* Phones (575px and below) */
@media (max-width: 575px) {{
    .block-container{{padding:0.25rem 0.75rem 0.75rem 0.75rem !important;}}
    
    .wim-nav{{padding:0 0.75rem 0 0.75rem;height:52px;}}
    .wim-nav-spacer{{height:44px;}}
    .wim-nav-sep{{height:24px;}}
    .wim-nav-title{{font-size:0.75rem;}}
    .wim-nav-sub{{font-size:0.55rem;}}
    .wim-nav-left{{gap:12px;}}
    
    .wim-site-row{{flex-direction:column;align-items:flex-start;gap:4px;margin:0 0 8px 0;}}
    .wim-site-name{{font-size:1.1rem;}}
    .wim-site-coord{{font-size:0.65rem;}}
    
    div[data-testid="stSelectbox"]{{max-width:140px !important;}}
    div[data-testid="stSelectbox"] [role="button"],div[data-testid="stSelectbox"] [role="button"] *{{font-size:13px !important;}}
    
    /* 7-day outlook - 2 rows on mobile */
    [data-testid="stHorizontalBlock"]>.element-container{{flex:0 0 calc(50% - 6px) !important;min-width:calc(50% - 6px) !important;}}
    
    .wim-day{{padding:10px 8px;margin-bottom:8px;}}
    .wim-day-label{{font-size:0.55rem;}}
    .wim-day-date{{font-size:0.6rem;}}
    .wim-day-cond{{font-size:0.7rem;}}
    .wim-day-rain{{font-size:0.9rem;}}
    .wim-day-temp{{font-size:0.6rem;}}
    
    /* KPI cards - 2 per row on mobile */
    .wim-metric{{padding:10px 12px;}}
    .wim-metric-label{{font-size:0.55rem;}}
    .wim-metric-value{{font-size:1rem;}}
    
    .wim-section{{font-size:0.55rem;margin:4px 0 6px 0;padding-bottom:4px;}}
    
    .wim-alert{{padding:12px 14px;font-size:0.8rem;}}
    .wim-alert-label{{font-size:0.6rem;}}
    
    /* Tables horizontal scroll */
    .wim-table{{font-size:0.7rem;min-width:600px;}}
    .wim-table th,.wim-table td{{padding:6px 8px;}}
    
    /* Accumulation cards */
    .wim-accum{{padding:10px 8px;}}
    .wim-accum-period{{font-size:0.55rem;}}
    .wim-accum-val{{font-size:1.1rem;}}
    .wim-accum-pop{{font-size:0.6rem;}}
    .wim-accum-risk{{font-size:0.6rem;}}
    
    /* Hourly graph bars */
    div[style*="min-width:36px"]{{min-width:32px !important;}}
    div[style*="font-size:0.65rem"]{{font-size:0.6rem !important;}}
    
    /* Hide some elements on very small screens */
    @media (max-width: 375px) {{
        .wim-nav-sub{{display:none;}}
        .wim-site-coord{{display:none;}}
    }}
}}

/* Very small phones (320px and below) */
@media (max-width: 320px) {{
    .block-container{{padding:0.25rem 0.5rem 0.5rem 0.5rem !important;}}
    .wim-site-name{{font-size:1rem;}}
    div[data-testid="stSelectbox"]{{max-width:120px !important;}}
}}

/* Landscape orientation on phones */
@media (max-width: 767px) and (orientation: landscape) {{
    .wim-nav-spacer{{height:40px;}}
    /* 7-day outlook - horizontal scroll in landscape */
    [data-testid="stHorizontalBlock"]>.element-container{{flex:0 0 calc(25% - 6px) !important;min-width:calc(25% - 6px) !important;}}
}}

/* Print styles */
@media print {{
    .wim-nav{{position:relative;box-shadow:none;border-bottom:1px solid #ccc;}}
    .wim-nav-spacer{{display:none;}}
    .wim-day{{break-inside:avoid;}}
    .wim-metric{{break-inside:avoid;}}
}}
</style>"""
st.markdown(_CSS, unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
# CONFIGURATION
# ══════════════════════════════════════════════════════════════
ACCUWEATHER_KEY = st.secrets.get("ACCUWEATHER_KEY", os.getenv("ACCUWEATHER_KEY", ""))
OPENWEATHER_KEY = st.secrets.get("OPENWEATHER_KEY", os.getenv("OPENWEATHER_KEY", ""))
TOMORROWIO_KEY  = st.secrets.get("TOMORROWIO_KEY", os.getenv("TOMORROWIO_KEY", ""))
ADMIN_PASSWORD  = os.getenv("ADMIN_PASSWORD", "Adani@2026#Mine")
SITES_FILE      = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mine_sites.json")

DEFAULT_SITES = [
    {"id": "builtin-suliyari",   "name": "Suliyari",         "lat": 23.941626, "lon": 82.331934, "type": "Coal Open Cast Mine", "builtin": True},
    {"id": "builtin-dhirauli",   "name": "Dhirauli",        "lat": 23.936440, "lon": 82.358836, "type": "Coal Open Cast Mine", "builtin": True},
    {"id": "builtin-parsa",      "name": "Parsa",           "lat": 22.824950, "lon": 82.804340, "type": "Coal Open Cast Mine", "builtin": True},
    {"id": "builtin-talabira",   "name": "Talabira",       "lat": 21.756317, "lon": 83.970446, "type": "Coal Open Cast Mine", "builtin": True},
    {"id": "builtin-gare-pelma", "name": "Gare Pelma",     "lat": 22.185835, "lon": 83.496813, "type": "Coal Open Cast Mine", "builtin": True},
    {"id": "builtin-kurmitra",   "name": "Kurmitra",       "lat": 21.754655, "lon": 85.161185, "type": "Iron Ore Mine", "builtin": True},
]
IST       = pytz.timezone('Asia/Kolkata')
UTC       = pytz.utc
TIMEOUT   = 20
RETRY_MAX = 3

WIND_CAUTION = 30
WIND_STOP    = 32
VIS_CAUTION  = 5.0  # 5km visibility is concerning
VIS_STOP     = 2.0  # 2km visibility is dangerous
RAIN_MOD     = 1.5
RAIN_HEAVY   = 5.0

API_WEIGHTS = {
    "accuweather": 0.40,  # Most reliable for rain type descriptions
    "open_meteo": 0.25,   # Good for overall patterns
    "openweather": 0.20,    # Moderate reliability
    "tomorrow_io": 0.10,    # Good for short-term
    "imd": 0.05             # Local but limited coverage
}

# ══════════════════════════════════════════════════════════════
# SITE MANAGEMENT — Supabase-first, JSON fallback
# ══════════════════════════════════════════════════════════════
def _using_supabase():
    return _get_supabase() is not None

def load_sites():
    """Load all sites. Custom sites from Supabase (or local JSON), always merged with DEFAULT_SITES."""
    custom = []
    sb = _get_supabase()
    if sb:
        try:
            res = sb.table("mine_sites").select("*").execute()
            custom = res.data or []
        except Exception:
            custom = _load_sites_json()
    else:
        custom = _load_sites_json()

    # Merge: built-ins first, then custom (skip if same name as builtin)
    result = list(DEFAULT_SITES)
    builtin_names = {s["name"] for s in DEFAULT_SITES}
    for s in custom:
        if s.get("name") not in builtin_names:
            result.append(s)
    return result

def _load_sites_json():
    if not os.path.exists(SITES_FILE): return []
    try:
        with open(SITES_FILE) as f: return json.load(f)
    except Exception: return []

def save_site(name, lat, lon):
    sb = _get_supabase()
    if sb:
        try:
            # upsert based on name
            sb.table("mine_sites").upsert(
                {"name": name, "lat": lat, "lon": lon, "builtin": False},
                on_conflict="name"
            ).execute()
            return
        except Exception: pass
    # fallback to JSON
    ex = _load_sites_json()
    ex = [s for s in ex if s["name"] != name]
    ex.append({"name": name, "lat": lat, "lon": lon, "builtin": False})
    with open(SITES_FILE, "w") as f: json.dump(ex, f, indent=2)

def update_site(old_name, new_name, lat, lon):
    sb = _get_supabase()
    if sb:
        try:
            sb.table("mine_sites").update(
                {"name": new_name.strip(), "lat": lat, "lon": lon}
            ).eq("name", old_name).execute()
            return
        except Exception: pass
    ex = _load_sites_json()
    for s in ex:
        if s["name"] == old_name:
            s["name"] = new_name.strip()
            s["lat"] = lat
            s["lon"] = lon
    with open(SITES_FILE, "w") as f: json.dump(ex, f, indent=2)

def delete_site(name):
    sb = _get_supabase()
    if sb:
        try:
            sb.table("mine_sites").delete().eq("name", name).execute()
            return
        except Exception: pass
    ex = _load_sites_json()
    ex = [s for s in ex if s["name"] != name]
    with open(SITES_FILE, "w") as f: json.dump(ex, f, indent=2)

def get_default_site():
    sb = _get_supabase()
    if sb:
        try:
            res = sb.table("app_settings").select("value").eq("key", "default_site").execute()
            if res.data: return res.data[0]["value"]
        except Exception: pass
    # fallback: local file
    _f = os.path.join(os.path.dirname(os.path.abspath(__file__)), "default_site.json")
    try:
        if os.path.exists(_f):
            with open(_f) as f: return json.load(f).get("name")
    except Exception: pass
    return None

def set_default_site(name):
    sb = _get_supabase()
    if sb:
        try:
            sb.table("app_settings").upsert(
                {"key": "default_site", "value": name},
                on_conflict="key"
            ).execute()
            return
        except Exception: pass
    _f = os.path.join(os.path.dirname(os.path.abspath(__file__)), "default_site.json")
    with open(_f, "w") as f: json.dump({"name": name}, f)

# ══════════════════════════════════════════════════════════════
# SESSION STATE INIT
# ══════════════════════════════════════════════════════════════
ALL_SITES = load_sites()
_names    = [s["name"] for s in ALL_SITES]

if "active_site" not in st.session_state:
    _def = get_default_site()
    st.session_state.active_site = _def if (_def and _def in _names) else (_names[0] if _names else None)

# ══════════════════════════════════════════════════════════════
# UTILITIES
# ══════════════════════════════════════════════════════════════
def now_ist(): return datetime.now(IST)
def utc_to_ist(dt):
    if dt.tzinfo is None: dt = UTC.localize(dt)
    return dt.astimezone(IST)

def rain_badge_html(mm):
    if mm == 0:     return '<span class="wim-badge b-none">0 mm</span>'
    elif mm < 0.3:  return f'<span class="wim-badge b-drizzle">{mm} mm · Drizzle</span>'
    elif mm < 1.5:  return f'<span class="wim-badge b-light">{mm} mm · Light</span>'
    elif mm < 5.0:  return f'<span class="wim-badge b-moderate">{mm} mm · Moderate</span>'
    else:           return f'<span class="wim-badge b-heavy">{mm} mm · Heavy</span>'

def mining_impact_html(mm, wind, vis, lightning):
    if lightning:
        return '<span class="wim-badge b-lightning">⚡ Stop — Lightning</span>'
    if mm >= RAIN_HEAVY or vis <= VIS_STOP or wind >= WIND_STOP:
        return '<span class="wim-badge b-stop">Stop Ops</span>'
    if mm >= RAIN_MOD or vis <= VIS_CAUTION or wind >= WIND_CAUTION:
        return '<span class="wim-badge b-caution">Caution</span>'
    if mm >= 0.3:
        return '<span class="wim-badge b-monitor">Monitor</span>'
    return '<span class="wim-badge b-clear-ops">Clear</span>'

def condition_str(total, descs, max_pop=0):
    # Smart logic: Consider both rainfall amount AND probability
    # Prioritize API weather descriptions for rain type
    
    # Analyze weather descriptions from multiple sources
    rain_types = []
    if descs:
        for desc in descs:
            desc_lower = desc.lower()
            if any(word in desc_lower for word in ["heavy", "torrential", "downpour", "storm", "thunderstorm"]):
                rain_types.append("heavy")
            elif any(word in desc_lower for word in ["moderate", "steady", "continuous"]):
                rain_types.append("moderate")
            elif any(word in desc_lower for word in ["light", "light rain", "shower", "showers"]):
                rain_types.append("light")
            elif any(word in desc_lower for word in ["drizzle", "mist", "sprinkle"]):
                rain_types.append("drizzle")
    
    # Get most common rain type from APIs
    api_rain_type = collections.Counter(rain_types).most_common(1)[0][0] if rain_types else None
    
    # High rainfall with decent probability
    if total >= 15 and max_pop >= 25: 
        return "Heavy Rain"
    # High rainfall but very low probability - downgrade
    elif total >= 15 and max_pop < 25: 
        return "Moderate Rain"
    # Moderate rainfall with decent probability
    elif total >= 5 and max_pop >= 35: 
        return "Moderate Rain"
    # Moderate rainfall but low probability - downgrade
    elif total >= 5 and max_pop < 35: 
        return "Light Rain"
    # Light rainfall with decent probability
    elif total >= 1.5 and max_pop >= 45: 
        return "Light Rain"
    # Light rainfall but low probability - downgrade to drizzle
    elif total >= 1.5 and max_pop < 45: 
        return "Drizzle"
    elif total > 0: 
        return "Drizzle"
    
    # Use API descriptions as primary source when no rain
    if api_rain_type:
        if api_rain_type == "heavy": return "Heavy Rain"
        if api_rain_type == "moderate": return "Moderate Rain"
        if api_rain_type == "light": return "Light Rain"
        if api_rain_type == "drizzle": return "Drizzle"
    
    return "Clear"

# ══════════════════════════════════════════════════════════════
# API FETCHES
# ══════════════════════════════════════════════════════════════
# OpenWeather API
@st.cache_data(ttl=1800)
def fetch_openweather(lat, lon):
    if not OPENWEATHER_KEY: return None, "no key"
    try:
        r = requests.get(
            f"https://api.openweathermap.org/data/3.0/onecall?lat={lat}&lon={lon}"
            f"&units=metric&exclude=minutely,daily,alerts&appid={OPENWEATHER_KEY}", timeout=TIMEOUT)
        r.raise_for_status(); data = r.json()
        
        for h in data.get("hourly", []):
            dt = datetime.fromtimestamp(h["dt"], tz=UTC)
            hk = utc_to_ist(dt).replace(minute=0, second=0, microsecond=0)
            add(hk, "openweather", h["temp"], 
                h.get("rain", {}).get("1h", 0), h.get("pop", 0) * 100,
                h["wind_speed"] * 3.6, h.get("visibility", 10000) / 1000 if h.get("visibility") != 10000 else 10,
                200 <= h.get("weather", [{}])[0].get("id", 0) < 300,
                h["weather"][0]["description"] if h.get("weather") else "",
                h.get("humidity", 0))
        return data, None
    except Exception as e: return None, str(e)

@st.cache_data(ttl=1800)
def fetch_open_meteo(lat, lon, days=7):
    url = (
        f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
        f"&hourly=temperature_2m,precipitation,weather_code,wind_speed_10m,"
        f"precipitation_probability,visibility,relative_humidity_2m,cloudcover"
        f"&forecast_days={days}&timezone=Asia%2FKolkata"
    )
    last_err = "unknown"
    for _ in range(RETRY_MAX):
        try:
            r = requests.get(url, timeout=TIMEOUT)
            r.raise_for_status()
            return r.json(), None
        except Exception as e:
            last_err = str(e)
    return None, f"Failed after {RETRY_MAX} attempts: {last_err}"

@st.cache_data(ttl=1800)
def fetch_tomorrow_io(lat, lon):
    if not TOMORROWIO_KEY: return None, "no key"
    try:
        r = requests.get(
            f"https://api.tomorrow.io/v4/weather/forecast?location={lat},{lon}"
            f"&units=metric&apikey={TOMORROWIO_KEY}", timeout=TIMEOUT)
        r.raise_for_status(); return r.json(), None
    except Exception as e: return None, str(e)

@st.cache_data(ttl=1800)
def fetch_accuweather_hourly(lat, lon):
    if not ACCUWEATHER_KEY: return None, "no key"
    try:
        lr = requests.get(
            f"https://dataservice.accuweather.com/locations/v1/cities/geoposition/search"
            f"?q={lat},{lon}&apikey={ACCUWEATHER_KEY}", timeout=TIMEOUT)
        lr.raise_for_status()
        key = lr.json().get("Key", "")
        if not key: return None, "no location key"
        fr = requests.get(
            f"https://dataservice.accuweather.com/forecasts/v1/hourly/12hour/{key}"
            f"?apikey={ACCUWEATHER_KEY}&details=true&metric=true", timeout=TIMEOUT)
        fr.raise_for_status(); return fr.json(), None
    except Exception as e: return None, str(e)

@st.cache_data(ttl=900)
def fetch_minutecast(lat, lon):
    if not ACCUWEATHER_KEY: return None, "no key"
    try:
        r = requests.get(
            f"https://dataservice.accuweather.com/forecasts/v1/minute"
            f"?q={lat},{lon}&apikey={ACCUWEATHER_KEY}&details=true", timeout=TIMEOUT)
        r.raise_for_status()
        out = []
        for m in r.json().get("Intervals", []):
            dbz  = m.get("Dbz", 0)
            mmhr = ((10 ** (dbz / 10.0)) / 200.0) ** (1 / 1.6) if dbz > 0 else 0.0
            out.append({"minute": m.get("StartMinute", 0), "mm_per_min": mmhr / 60.0,
                        "is_precip": m.get("HasPrecipitation", False), "dbz": dbz})
        return (out if out else None), None
    except Exception as e: return None, str(e)

@st.cache_data(ttl=1800)
def fetch_imd(lat, lon):
    """Fetch nowcast from India Meteorological Department."""
    try:
        r = requests.get(
            f"https://mausam.imd.gov.in/api/nowcast_district_api.php"
            f"?lat={lat}&lon={lon}",
            timeout=TIMEOUT)
        r.raise_for_status()
        return r.json(), None
    except Exception as e: return None, str(e)

# ══════════════════════════════════════════════════════════════
# ENSEMBLE
# ══════════════════════════════════════════════════════════════
def build_forecast(lat, lon, days=7):
    # Fetch all providers concurrently to reduce overall load time.
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        futs = {
            "ow": ex.submit(fetch_openweather, lat, lon),
            "om": ex.submit(fetch_open_meteo, lat, lon, days),
            "tm": ex.submit(fetch_tomorrow_io, lat, lon),
            "aw": ex.submit(fetch_accuweather_hourly, lat, lon),
            "mc": ex.submit(fetch_minutecast, lat, lon),
            "imd": ex.submit(fetch_imd, lat, lon),
        }
        ow, ow_err   = futs["ow"].result()
        om, om_err   = futs["om"].result()
        tm, tm_err   = futs["tm"].result()
        aw, aw_err   = futs["aw"].result()
        mc, mc_err   = futs["mc"].result()
        imd, imd_err = futs["imd"].result()

    src_status = {
        "Open-Meteo":  "ok" if om else str(om_err),
        "AccuWeather": "ok" if aw else str(aw_err),
        "MinuteCast":  "ok" if mc else str(mc_err),
        "OpenWeather": "ok" if ow else str(ow_err),
        "Tomorrow.io": "ok" if tm else str(tm_err),
        "IMD": "ok" if imd else str(imd_err),
    }

    now_h  = now_ist().replace(minute=0, second=0, microsecond=0)
    cutoff = now_h + timedelta(days=days)
    raw    = {}

    def add(hk, src, temp, rain, pop, wind, vis, lightning, desc, hum=0, cloud=0):
        if hk < now_h - timedelta(hours=1) or hk > cutoff: return
        raw.setdefault(hk, {})
        raw[hk][src] = dict(temp=temp, rain=max(0.0, float(rain or 0)),
                            pop=float(pop or 0), wind=float(wind or 0),
                            vis=float(vis or 10), lightning=bool(lightning),
                            desc=str(desc or ""), hum=float(hum or 0), cloud=float(cloud or 0))

    if imd:
        try:
            now_h = now_ist().replace(minute=0, second=0, microsecond=0)
            rain = imd.get("rainfall", 0) if isinstance(imd, dict) else 0

            add(now_h, "imd",
                temp=0,
                rain=rain,
                pop=80 if rain > 0 else 20,
                wind=0,
                vis=10.0,
                lightning=False,
                desc="IMD Nowcast",
                hum=0
            )
        except:
            pass

    if ow and "hourly" in ow:
        for e in ow["hourly"]:
            hk  = utc_to_ist(datetime.fromtimestamp(e["dt"], tz=UTC)).replace(minute=0, second=0, microsecond=0)
            wid = e["weather"][0]["id"] if e.get("weather") else 0
            add(hk, "openweather", e["temp"],
                e.get("rain", {}).get("1h", 0), e.get("pop", 0) * 100,
                e["wind_speed"] * 3.6, e.get("visibility", 10000) / 1000,
                200 <= wid < 300,
                e["weather"][0]["description"] if e.get("weather") else "",
                e.get("humidity", 0))

    if om and "hourly" in om:
        h   = om["hourly"]
        vis = h.get("visibility", [])
        hum = h.get("relative_humidity_2m", [])
        cloud = h.get("cloudcover", [])
        for i, ts in enumerate(h["time"]):
            hk = datetime.fromisoformat(ts).replace(tzinfo=IST).replace(minute=0, second=0, microsecond=0)
            add(hk, "open_meteo", h["temperature_2m"][i],
                h["precipitation"][i], h["precipitation_probability"][i],
                h["wind_speed_10m"][i],
                vis[i] / 1000 if i < len(vis) and vis[i] is not None else 10,
                False, "", hum[i] if i < len(hum) else 0, cloud[i] if i < len(cloud) else 0)

    if tm and "timelines" in tm and "hourly" in tm["timelines"]:
        for iv in tm["timelines"]["hourly"]:
            try: dt_utc = UTC.localize(datetime.strptime(iv["time"], '%Y-%m-%dT%H:%M:%SZ'))
            except: continue
            hk = utc_to_ist(dt_utc).replace(minute=0, second=0, microsecond=0)
            v  = iv["values"]
            add(hk, "tomorrow_io", v.get("temperature", 0),
                v.get("precipitationIntensity", 0), v.get("precipitationProbability", 0),
                v.get("windSpeed", 0) * 3.6, 
                v.get("visibility", 10000) / 1000 if v.get("visibility") not in [None, 10000] else 10,
                v.get("lightningStrikeCount", 0) > 0 or v.get("weatherCode") == 8000, "",
                v.get("humidity", 0))

    if aw:
        for e in aw:
            try:
                dt = datetime.fromisoformat(e.get("DateTime", ""))
                if dt.tzinfo is None: dt = UTC.localize(dt)
                hk = dt.astimezone(IST).replace(minute=0, second=0, microsecond=0)
            except: continue
            add(hk, "accuweather",
                e.get("Temperature", {}).get("Value", 0),
                e.get("Rain", {}).get("Value", 0) + e.get("Snow", {}).get("Value", 0),
                e.get("PrecipitationProbability", 0),
                e.get("Wind", {}).get("Speed", {}).get("Value", 0),
                e.get("Visibility", {}).get("Metric", {}).get("Value", 10.0),
                e.get("ThunderstormProbability", 0) > 30,
                e.get("IconPhrase", ""), e.get("RelativeHumidity", 0))

    if mc:
        now_t = now_ist()
        mc_h  = collections.defaultdict(float)
        for m in mc:
            hk = (now_t + timedelta(minutes=m["minute"])).replace(minute=0, second=0, microsecond=0)
            mc_h[hk] += m["mm_per_min"]
        for hk, mm in mc_h.items():
            raw.setdefault(hk, {})
            raw[hk]["minutecast"] = dict(temp=0, rain=mm, pop=100 if mm > 0.05 else 0,
                                          wind=0, vis=10.0, lightning=False, desc="", hum=0)

    final = []
    for hk in sorted(raw.keys()):
        srcs = raw[hk]
        def wavg(field):
            total_weight = sum(API_WEIGHTS.get(src, 0) for src in srcs.keys())
            if total_weight == 0:
                vals = [d[field] for d in srcs.values()]
                return sum(vals) / len(vals) if vals else 0
            
            weighted_sum = sum(d[field] * API_WEIGHTS.get(src, 0) for src, d in srcs.items())
            return weighted_sum / total_weight
        
        def wavg_vis():
            # Only filter out obviously wrong values (0km during day)
            current_hour = now_ist().hour
            valid_vis = [(d["vis"], API_WEIGHTS.get(src, 0)) for src, d in srcs.items() 
                       if d["vis"] > 0 or (d["vis"] == 0 and 20 <= current_hour <= 6)]  # Allow 0vis for night 8PM-6AM
            if not valid_vis:
                return 10  # Default visibility
            
            weighted_sum = sum(vis * weight for vis, weight in valid_vis)
            total_weight = sum(weight for _, weight in valid_vis)
            return weighted_sum / total_weight

        rain_vals = [d["rain"] for d in srcs.values()]
        if len(rain_vals) >= 2:
            rain_out = sorted(rain_vals)[len(rain_vals)//2]
        elif len(rain_vals) == 1:
            rain_out = rain_vals[0]
        else:
            rain_out = 0.0
        pop_raw = wavg("pop")
        pop_out = pop_raw
        
        descs = [d["desc"] for d in srcs.values() if d["desc"]]
        best_desc = ""
        if descs:
            if "accuweather" in srcs and srcs["accuweather"]["desc"]:
                best_desc = srcs["accuweather"]["desc"]
            else:
                best_desc = collections.Counter(descs).most_common(1)[0][0]
        
        final.append((hk, {
            "temp": round(wavg("temp"), 1), "rain_mm": round(rain_out, 2),
            "pop": round(pop_out, 1), "wind_kmh": round(wavg("wind"), 1),
            "vis_km": round(wavg_vis(), 1), "humidity": round(wavg("hum"), 1),
            "cloud": round(wavg("cloud"), 0),
            "lightning": any(d["lightning"] for d in srcs.values()),
            "desc": best_desc, "n_sources": len(srcs)}))

    by_day = collections.defaultdict(list)
    for hk, d in final: by_day[hk.date()].append((hk, d))
    
    for date_key in by_day:
        seen = set()
        deduplicated = []
        for hk, d in by_day[date_key]:
            if hk not in seen:
                seen.add(hk)
                deduplicated.append((hk, d))
        by_day[date_key] = deduplicated
    
    return dict(by_day), mc, src_status

# ══════════════════════════════════════════════════════════════
# SLAB BUILDER
# ══════════════════════════════════════════════════════════════
SLABS = [
    (0, 2, "12:30 AM – 2:30 AM"), (2, 4, "2:30 AM – 4:30 AM"),
    (4, 6, "4:30 AM – 6:30 AM"),  (6, 8, "6:30 AM – 8:30 AM"),
    (8, 10, "8:30 AM – 10:30 AM"), (10, 12, "10:30 AM – 12:30 PM"),
    (12, 14, "12:30 PM – 2:30 PM"), (14, 16, "2:30 PM – 4:30 PM"),
    (16, 18, "4:30 PM – 6:30 PM"), (18, 20, "6:30 PM – 8:30 PM"),
    (20, 22, "8:30 PM – 10:30 PM"), (22, 2, "10:30 PM – 12:30 AM"),
]
def hour_to_slab(h):
    for s, e, n in SLABS:
        if s == 22 and h in (22, 23): return (s, e, n)
        elif s < e and s <= h < e:    return (s, e, n)
    return None

# TRULY DYNAMIC 2-HOUR SLABS - aligns with current time
def generate_dynamic_slabs():
    """Generate 2-hour slabs aligned to next 30-min boundary from current time"""
    now = now_ist()
    current_hour = now.hour
    current_min = now.minute
    
    # Determine next 30-min boundary
    if current_min < 30:
        start_hour = current_hour
        start_min = 30
    else:
        start_hour = current_hour + 1
        start_min = 0
    
    # Handle day wrap
    if start_hour >= 24:
        start_hour = 0
    
    slabs = []
    for i in range(6):  # Generate 6 slabs (12 hours of coverage)
        s_hour = (start_hour + i * 2) % 24
        e_hour = (s_hour + 2) % 24
        
        # Format times
        s_label = f"{s_hour % 12 or 12}:{start_min:02d} {'AM' if s_hour < 12 else 'PM'}"
        e_min = start_min
        e_label = f"{e_hour % 12 or 12}:{e_min:02d} {'AM' if e_hour < 12 else 'PM'}"
        
        # Handle overnight wrap
        if s_hour > e_hour:  # Overnight
            full_label = f"{s_label} – {e_label} (next day)"
        else:
            full_label = f"{s_label} – {e_label}"
        
        slabs.append((s_hour, e_hour, full_label, start_min))
    
    return slabs

def hour_to_slab(h, slabs):
    """Map hour to dynamic slab"""
    for s, e, n, m in slabs:
        if s <= h < e or (s > e and (h >= s or h < e)):  # Handle overnight
            return (s, e, n, m)
    return None

def build_slabs(hourly):
    # Generate dynamic slabs based on current time
    dynamic_slabs = generate_dynamic_slabs()
    
    raw = collections.defaultdict(lambda: dict(rain=0, pop=[], wind=[], vis=[], lightning=[], hum=[], count=0))
    for hk, d in hourly:
        sk = hour_to_slab(hk.hour, dynamic_slabs)
        if not sk: continue
        r = raw[sk]
        r["rain"] += d["rain_mm"]; r["pop"].append(d["pop"])
        r["wind"].append(d["wind_kmh"]); r["vis"].append(d["vis_km"])
        r["lightning"].append(d["lightning"]); r["hum"].append(d["humidity"]); r["count"] += 1
    slabs = []
    for sk, r in raw.items():
        if not r["count"]: continue
        avg = lambda lst: sum(lst) / len(lst) if lst else 0
        slabs.append(dict(label=sk[2], sort=sk[0], mm=round(r["rain"], 1),
            pop=int(round(avg(r["pop"]), 0)), wind=round(avg(r["wind"]), 1),
            vis=round(avg(r["vis"]), 1), hum=round(avg(r["hum"]), 1),
            lightning=any(r["lightning"])))
    slabs.sort(key=lambda x: x["sort"])
    return slabs

def day_summary(hourly, mine_type="Coal Open Cast Mine"):
    if not hourly:
        return dict(max_temp="—", min_temp="—", total_rain=0, max_pop=0,
                    condition="—", humidity=0, slabs=[], max_wind=0, min_vis=10)
    
    # Mine-specific validation
    is_iron_ore = "Iron Ore" in mine_type
    
    temps  = [d["temp"] for _, d in hourly]
    rains  = [d["rain_mm"] for _, d in hourly]
    pops   = [d["pop"] for _, d in hourly]
    winds  = [d["wind_kmh"] for _, d in hourly]
    viss   = [d["vis_km"] for _, d in hourly]
    hums   = [d["humidity"] for _, d in hourly]
    clouds = [d.get("cloud", 0) for _, d in hourly if d.get("cloud", 0) > 0]
    
    total  = round(sum(rains), 1)
    descs  = [d["desc"] for _, d in hourly if d["desc"]]
    
    return dict(
        max_temp=round(max(temps), 1) if temps else "—", 
        min_temp=round(min(temps), 1) if temps else "—",
        total_rain=total, 
        max_pop=int(round(sorted(pops)[int(len(pops)*0.75)] if pops else 0, 0)),  # Use 75th percentile instead of max
        condition=condition_str(total, descs, max(pops) if pops else 0),
        humidity=round(sum(hums) / len(hums), 1) if hums else 0,
        cloud=round(sum(clouds) / len(clouds), 0) if clouds else None,
        avg_wind=round(sum(winds) / len(winds), 1) if winds else 0, 
        min_vis=round(min(viss), 1) if viss else 10,
        slabs=build_slabs(hourly))

# ══════════════════════════════════════════════════════════════
# SMART RECOMMENDATION
# ══════════════════════════════════════════════════════════════
def smart_rec(ds, slabs, target_day, mine_type="Coal Open Cast Mine"):
    rain = ds["total_rain"]; mwind = ds.get("max_wind", ds.get("avg_wind", 0))
    mvis = ds["min_vis"]; pop = ds["max_pop"]
    has_l   = any(s["lightning"] for s in slabs)
    rain_sl = [s for s in slabs if s["mm"] > 0]
    heavy_sl = [s for s in slabs if s["mm"] >= RAIN_HEAVY]
    mod_sl   = [s for s in slabs if RAIN_MOD <= s["mm"] < RAIN_HEAVY]
    today  = now_ist().date()
    dlabel = "Today" if target_day == today else target_day.strftime("%A")
    parts  = []

    # Mine-specific wind thresholds
    if "Iron Ore" in mine_type:
        WIND_CAUTION_MINE = 25  # Lower threshold for iron ore operations
        WIND_STOP_MINE = 28      # Lower threshold for iron ore operations
    else:
        WIND_CAUTION_MINE = WIND_CAUTION  # 30 km/h for coal
        WIND_STOP_MINE = WIND_STOP       # 32 km/h for coal

    if rain == 0 and pop < 25:
        if "Coal" in mine_type:
            parts.append(f"{dlabel} is forecast to be completely dry. All open-cast operations including OB removal, drilling, blasting, and coal dispatch can proceed normally.")
        else:
            parts.append(f"{dlabel} is forecast to be completely dry. All open-cast operations including OB removal, drilling, blasting, and ore dispatch can proceed normally.")
    elif rain == 0 and pop >= 25:
        parts.append(f"{dlabel} is likely dry with a {pop}% chance of isolated showers. Schedule blasting in morning hours and monitor sky conditions before afternoon shift.")
    elif heavy_sl:
        hw = heavy_sl[0]["label"]
        parts.append(f"Heavy rainfall totalling {rain} mm is expected {dlabel.lower()}, peaking around {hw}.")
        if "Coal" in mine_type:
            parts.append("Pit drainage must be inspected before morning shift. Bench and haul road surfaces will be severely impacted — mandatory post-rain ground assessment required before resuming OB removal, shovel, and dozer work. Deploy coal stockpile covers.")
        else:
            parts.append("Pit drainage must be inspected before morning shift. Bench and haul road surfaces will be severely impacted — mandatory post-rain ground assessment required before resuming OB removal, shovel, and dozer work. Deploy ore stockpile covers.")
    elif mod_sl:
        first = rain_sl[0]["label"]; last = rain_sl[-1]["label"]
        parts.append(f"Moderate rainfall of {rain} mm is forecast from {first} through {last}.")
        if "Coal" in mine_type:
            parts.append("Plan coal loading and dispatch in the pre-rain dry window. Allow 1–2 hours post-rain drainage assessment before resuming heavy equipment on active benches. Check blast hole integrity before charging.")
        else:
            parts.append("Plan ore loading and dispatch in the pre-rain dry window. Allow 1–2 hours post-rain drainage assessment before resuming heavy equipment on active benches. Check blast hole integrity before charging.")
    elif rain_sl:
        first = rain_sl[0]["label"]; last = rain_sl[-1]["label"]
        parts.append(f"Light rainfall of {rain} mm is expected between {first} and {last}.")
        parts.append("Operational impact is minimal. Inspect blast area for surface water before charging holes.")

    if has_l:
        lt = [s["label"] for s in slabs if s["lightning"]]
        parts.append(f"Lightning forecast around {lt[0]}. All blasting, drilling, and work near tall equipment (shovels, conveyors) must halt 30 minutes before the storm and resume only after 30 clear minutes.")

    if mwind >= WIND_STOP_MINE:
        if "Coal" in mine_type:
            parts.append(f"Wind gusts of {mwind} km/h exceed the DGMS blasting limit ({WIND_STOP} km/h). Defer all blasting. Extend flyrock exclusion zones and confirm with safety officer before resuming.")
        else:
            parts.append(f"Wind gusts of {mwind} km/h exceed safe blasting limits for iron ore operations ({WIND_STOP_MINE} km/h). Defer all blasting. Extend flyrock exclusion zones and confirm with safety officer before resuming.")
    elif mwind >= WIND_CAUTION_MINE:
        if "Coal" in mine_type:
            parts.append(f"Wind speeds up to {mwind} km/h will increase coal dust dispersal. Activate dust suppression and verify flyrock zones before each blast.")
        else:
            parts.append(f"Wind speeds up to {mwind} km/h will increase ore dust dispersal. Activate dust suppression and verify flyrock zones before each blast.")

    if mvis <= VIS_STOP and mvis > 0:
        parts.append(f"Visibility forecast to drop to {mvis} km. Restrict all haul truck and heavy equipment movement. Deploy flagmen at road intersections.")
    elif mvis <= VIS_CAUTION and mvis > 0:
        parts.append(f"Reduced visibility of {mvis} km expected. Enforce lower truck speeds on haul roads and deploy additional spotters on active benches.")

    return " ".join(parts) if parts else f"{dlabel} presents no significant weather concerns. All planned operations can proceed as scheduled."

# ══════════════════════════════════════════════════════════════
# RAIN ACCUMULATION
# ══════════════════════════════════════════════════════════════
def rain_accum(hourly, target_day=None):
    ist_now = now_ist()
    today_d = ist_now.date()
    if target_day is None or target_day == today_d:
        anchor = ist_now.replace(minute=0, second=0, microsecond=0)
    else:
        anchor = IST.localize(datetime(target_day.year, target_day.month, target_day.day, 0, 0, 0))
    out = {}
    for h in (2, 4, 6, 12, 24):
        seg = [(dt, d) for dt, d in hourly if anchor <= dt < anchor + timedelta(hours=h)]
        mm  = round(sum(d["rain_mm"] for _, d in seg), 1)
        # Use 75th percentile for probability (not max) to avoid inflated values
        pops = [d["pop"] for _, d in seg if d["pop"] > 0]
        pop = int(sorted(pops)[int(len(pops)*0.75)] if pops else 0)
        out[h] = (mm, pop)
    return out

# ══════════════════════════════════════════════════════════════
# MINUTECAST
# ══════════════════════════════════════════════════════════════
def render_mc(mc):
    if not mc: return
    now = now_ist(); max_dbz = max((m["dbz"] for m in mc), default=1) or 1
    bars = ""
    for m in mc:
        dbz = m["dbz"]; t = (now + timedelta(minutes=m["minute"])).strftime("%H:%M")
        c = ("#F1F5F9" if dbz == 0 or not m["is_precip"] else
             "#BFDBFE" if dbz < 15 else "#3B82F6" if dbz < 25 else
             "#1D4ED8" if dbz < 35 else "#D97706" if dbz < 45 else "#DC2626")
        ht = max(4, int(28 * dbz / max_dbz))
        bars += f'<span style="display:inline-block;width:4px;height:{ht}px;background:{c};border-radius:1px;margin-right:1px;vertical-align:bottom;" title="{t}"></span>'
    lbls = ""
    for m in mc:
        if m["minute"] % 30 == 0:
            t = (now + timedelta(minutes=m["minute"])).strftime("%H:%M")
            lbls += f'<span style="display:inline-block;width:120px;font-size:0.65rem;color:#94A3B8;">{t}</span>'
    st.markdown(f"""<div class="wim-mc">
        <div class="wim-mc-title">Minute-by-Minute Precipitation — Next 2 Hours (AccuWeather Radar)</div>
        <div style="white-space:nowrap;display:flex;align-items:flex-end;gap:0;">{bars}</div>
        <div style="white-space:nowrap;margin-top:6px;">{lbls}</div>
        <div style="margin-top:8px;font-size:0.65rem;color:#94A3B8;display:flex;gap:12px;flex-wrap:wrap;">
            <span><span style="display:inline-block;width:8px;height:8px;background:#BFDBFE;border-radius:1px;margin-right:3px;vertical-align:middle;"></span>Light</span>
            <span><span style="display:inline-block;width:8px;height:8px;background:#3B82F6;border-radius:1px;margin-right:3px;vertical-align:middle;"></span>Moderate</span>
            <span><span style="display:inline-block;width:8px;height:8px;background:#1D4ED8;border-radius:1px;margin-right:3px;vertical-align:middle;"></span>Heavy</span>
            <span><span style="display:inline-block;width:8px;height:8px;background:#DC2626;border-radius:1px;margin-right:3px;vertical-align:middle;"></span>Very Heavy</span>
        </div></div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
# HOURLY PRECIPITATION TABLE (all days)
# ══════════════════════════════════════════════════════════════
def render_hourly_table(hourly, target_day):
    if not hourly:
        st.markdown('<div class="wim-alert wim-alert-none">No hourly data available.</div>', unsafe_allow_html=True)
        return

    today     = now_ist().date()
    ist_now_h = now_ist().replace(minute=0, second=0, microsecond=0)
    rows      = ""
    seen_hours = set()

    for hk, d in sorted(hourly, key=lambda x: x[0]):
        h_key = hk.strftime("%Y-%m-%d %H:00")
        if h_key in seen_hours:
            continue
        seen_hours.add(h_key)
        if target_day == today and hk < ist_now_h: continue
        mm    = d["rain_mm"]; wind = d["wind_kmh"]; vis = d["vis_km"]
        pop   = d["pop"]; temp = d["temp"]; hum = d["humidity"]; light = d["lightning"]; cloud = d.get("cloud", 0)
        h_lbl = hk.strftime("%I:%M %p")

        if light or mm >= RAIN_HEAVY or vis <= VIS_STOP or wind >= WIND_STOP:
            row_cls = ' class="hour-row-alert"'
        elif mm >= RAIN_MOD or vis <= VIS_CAUTION or wind >= WIND_CAUTION:
            row_cls = ' class="hour-row-heavy"'
        elif mm > 0:
            row_cls = ' class="hour-row-rain"'
        else:
            row_cls = ''

        wind_td = f'<td class="td-alert">{wind} km/h</td>' if wind >= WIND_STOP else (f'<td class="td-warn">{wind} km/h</td>' if wind >= WIND_CAUTION else f'<td>{wind} km/h</td>')
        vis_td  = f'<td class="td-alert">{vis} km</td>' if vis <= VIS_STOP else (f'<td class="td-warn">{vis} km</td>' if vis <= VIS_CAUTION else f'<td>{vis} km</td>')
        pop_td  = f'<td class="td-alert">{pop}%</td>' if pop >= 70 else (f'<td class="td-warn">{pop}%</td>' if pop >= 40 else f'<td>{pop}%</td>')
        cloud_td = f'<td style="color:#64748B;">{int(cloud)}%</td>' if cloud else '<td style="color:#94A3B8;">—</td>'
        l_td    = '<td class="td-alert"><span class="wim-badge b-lightning">⚡ Alert</span></td>' if light else '<td style="color:#94A3B8;">—</td>'
        impact  = mining_impact_html(mm, wind, vis, light)

        rows += (f"<tr{row_cls}><td style='font-weight:700;color:#334155;white-space:nowrap;'>{h_lbl}</td>"
                 f"<td>{rain_badge_html(mm)}</td>{pop_td}<td>{temp}°C</td><td>{hum}%</td>{cloud_td}"
                 f"{wind_td}{vis_td}{l_td}<td>{impact}</td></tr>")

    if not rows:
        st.markdown('<div class="wim-alert wim-alert-none">No upcoming hourly data for this day.</div>', unsafe_allow_html=True)
        return

    st.markdown(
        '<div style="overflow-x:auto;">'
        '<table class="wim-table"><thead><tr>'
        '<th>Hour</th><th>Rainfall</th><th>Rain Prob.</th><th>Temp</th><th>Humidity</th><th>Cloud</th>'
        '<th>Wind</th><th>Visibility</th><th>Lightning</th><th>Mining Impact</th>'
        '</tr></thead><tbody>' + rows + '</tbody></table></div>',
        unsafe_allow_html=True)

    st.markdown(
        '<div style="margin-top:8px;display:flex;gap:16px;flex-wrap:wrap;font-size:0.68rem;color:#64748B;">'
        '<span style="display:flex;align-items:center;gap:5px;"><span style="width:10px;height:10px;border-radius:2px;background:#FFF1F2;border:1px solid #FECDD3;display:inline-block;"></span>Stop operations</span>'
        '<span style="display:flex;align-items:center;gap:5px;"><span style="width:10px;height:10px;border-radius:2px;background:#FFF7ED;border:1px solid #FDE68A;display:inline-block;"></span>Caution / monitor</span>'
        '<span style="display:flex;align-items:center;gap:5px;"><span style="width:10px;height:10px;border-radius:2px;background:#EFF6FF;border:1px solid #BFDBFE;display:inline-block;"></span>Rain present, ops normal</span>'
        '</div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
# HOURLY TEMPERATURE & PRECIPITATION GRAPH
# ══════════════════════════════════════════════════════════════
def render_hourly_graph(hourly, target_day):
    """Render hourly temperature and precipitation graph with mining status."""
    if not hourly:
        return
    
    today = now_ist().date()
    ist_now_h = now_ist().replace(minute=0, second=0, microsecond=0)
    
    # Filter and prepare data
    data = []
    seen_hours = set()
    
    for hk, d in sorted(hourly, key=lambda x: x[0]):
        h_key = hk.strftime("%Y-%m-%d %H:00")
        if h_key in seen_hours:
            continue
        seen_hours.add(h_key)
        if target_day == today and hk < ist_now_h:
            continue
        
        mm = d["rain_mm"]
        wind = d["wind_kmh"]
        vis = d["vis_km"]
        temp = d["temp"]
        pop = d["pop"]
        light = d["lightning"]
        
        # Determine operation status
        if light or mm >= RAIN_HEAVY or vis <= VIS_STOP or wind >= WIND_STOP:
            status = "stop"
            status_color = "#DC2626"
            status_bg = "#FFF1F2"
        elif mm >= RAIN_MOD or vis <= VIS_CAUTION or wind >= WIND_CAUTION:
            status = "caution"
            status_color = "#D97706"
            status_bg = "#FFF7ED"
        else:
            status = "safe"
            status_color = "#16A34A"
            status_bg = "#F0FDF4"
        
        data.append({
            "hour": hk.strftime("%H:%M"),
            "hour_12": hk.strftime("%I %p").lstrip("0"),
            "temp": temp,
            "rain": mm,
            "pop": pop,
            "status": status,
            "status_color": status_color,
            "status_bg": status_bg,
            "wind": wind,
            "vis": vis
        })
    
    if not data:
        return
    
    # Build HTML graph
    max_rain = max(d["rain"] for d in data) or 1
    max_temp = max(d["temp"] for d in data)
    min_temp = min(d["temp"] for d in data)
    temp_range = max_temp - min_temp or 1
    
    bars = ""
    for d in data:
        # Calculate heights
        rain_height = min((d["rain"] / max_rain) * 60, 60) if max_rain > 0 else 0
        temp_height = ((d["temp"] - min_temp) / temp_range) * 40 if temp_range > 0 else 20
        
        # Status indicator
        status_dot = '<div style="width:8px;height:8px;border-radius:50%;background:' + d["status_color"] + ';margin:4px auto;"></div>'
        
        hour_label = d["hour_12"].replace(" ","")
        
        bars += '<div style="flex:1;min-width:36px;display:flex;flex-direction:column;align-items:center;gap:4px;padding:8px 2px;border-radius:6px;background:' + d["status_bg"] + ';margin:0 2px;position:relative;" title="' + d["hour"] + ' - Temp: ' + str(d["temp"]) + '°C, Rain: ' + str(d["rain"]) + 'mm, Status: ' + d["status"].upper() + '">' + \
            '<div style="font-size:0.65rem;font-weight:600;color:#64748B;">' + hour_label + '</div>' + \
            '<div style="display:flex;align-items:flex-end;gap:2px;height:70px;">' + \
                '<div style="width:14px;background:linear-gradient(180deg,#0B74B0,#60A5FA);border-radius:3px 3px 0 0;height:' + str(rain_height) + 'px;min-height:2px;" title="Rain: ' + str(d["rain"]) + 'mm"></div>' + \
                '<div style="width:14px;background:linear-gradient(180deg,#F59E0B,#FCD34D);border-radius:3px 3px 0 0;height:' + str(temp_height) + 'px;min-height:2px;" title="Temp: ' + str(d["temp"]) + '°C"></div>' + \
            '</div>' + \
            status_dot + \
            '<div style="font-size:0.6rem;font-weight:700;color:' + d["status_color"] + ';text-transform:uppercase;">' + d["status"][:1] + '</div>' + \
        '</div>'
    
    # Legend
    legend = '<div style="display:flex;gap:20px;flex-wrap:wrap;margin-top:16px;padding-top:12px;border-top:1px solid #E2E8F0;">' + \
        '<div style="display:flex;align-items:center;gap:6px;">' + \
            '<div style="width:14px;height:14px;background:linear-gradient(180deg,#0B74B0,#60A5FA);border-radius:3px;"></div>' + \
            '<span style="font-size:0.75rem;color:#475569;">Precipitation (mm)</span>' + \
        '</div>' + \
        '<div style="display:flex;align-items:center;gap:6px;">' + \
            '<div style="width:14px;height:14px;background:linear-gradient(180deg,#F59E0B,#FCD34D);border-radius:3px;"></div>' + \
            '<span style="font-size:0.75rem;color:#475569;">Temperature (°C)</span>' + \
        '</div>' + \
        '<div style="display:flex;align-items:center;gap:6px;">' + \
            '<div style="width:8px;height:8px;border-radius:50%;background:#16A34A;"></div>' + \
            '<span style="font-size:0.75rem;color:#475569;">Safe Operations</span>' + \
        '</div>' + \
        '<div style="display:flex;align-items:center;gap:6px;">' + \
            '<div style="width:8px;height:8px;border-radius:50%;background:#D97706;"></div>' + \
            '<span style="font-size:0.75rem;color:#475569;">Caution</span>' + \
        '</div>' + \
        '<div style="display:flex;align-items:center;gap:6px;">' + \
            '<div style="width:8px;height:8px;border-radius:50%;background:#DC2626;"></div>' + \
            '<span style="font-size:0.75rem;color:#475569;">Stop Operations</span>' + \
        '</div>' + \
    '</div>'
    
    st.markdown(
        f'<div style="overflow-x:auto;"><div style="display:flex;min-width:100%;padding:4px;">{bars}</div></div>{legend}',
        unsafe_allow_html=True
    )

# ══════════════════════════════════════════════════════════════
# 7-DAY STRIP
# ══════════════════════════════════════════════════════════════
def render_weekly(by_day, days, site_type="Coal Open Cast Mine"):
    today = now_ist().date()
    cols  = st.columns(min(days, 7))
    for i in range(min(days, 7)):
        d   = today + timedelta(days=i)
        lbl = "Today" if i == 0 else ("Tomorrow" if i == 1 else d.strftime("%a"))
        if d not in by_day:
            cols[i].markdown(f'<div class="wim-day"><div class="wim-day-label">{lbl}</div><div class="wim-day-date">{d.strftime("%d %b")}</div><div style="color:#94A3B8;font-size:0.75rem;margin-top:8px;">No data</div></div>', unsafe_allow_html=True)
            continue
        s    = day_summary(by_day[d], site_type); sl = s["slabs"]
        rain = s["total_rain"]; has_l = any(x["lightning"] for x in sl)
        max_pop = s["max_pop"]
        mine_type_current = site_type  # Use the passed site_type for consistency
        
        # Use smart rain classification with probability (same as condition_str logic)
        if rain >= 15 and max_pop >= 25:             flag, fcss = "Heavy Rain", "flag-heavy"
        elif rain >= 15 and max_pop < 25:           flag, fcss = "Moderate Risk", "flag-moderate"
        elif rain >= 5 and max_pop >= 35:            flag, fcss = "Moderate Risk", "flag-moderate"
        elif rain >= 5 and max_pop < 35:              flag, fcss = "Light Rain", "flag-light"
        elif rain >= 1.5 and max_pop >= 45:          flag, fcss = "Light Rain", "flag-light"
        elif rain >= 1.5 and max_pop < 45:           flag, fcss = "Drizzle", "flag-drizzle"
        elif rain > 0:                                flag, fcss = "Drizzle", "flag-drizzle"
        elif has_l:                                  flag, fcss = "Lightning Risk", "flag-lightning"
        else:                                         flag, fcss = "Clear", "flag-clear"
        day_css = "wim-day wim-day-active" if i == 0 else "wim-day"
        cols[i].markdown(f"""<div class="{day_css}">
            <div class="wim-day-label">{lbl}</div>
            <div class="wim-day-date">{d.strftime('%d %b')}</div>
            <div class="wim-day-cond">{s['condition']}</div>
            <div class="wim-day-rain">{rain} mm{f" · {s['max_pop']}%" if rain > 0 else ""}</div>
            <div class="wim-day-temp">{s['max_temp']}° / {s['min_temp']}°C</div>
            <span class="wim-day-flag {fcss}">{flag}</span>
        </div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
# SIDEBAR — redesigned with Supabase status indicator
# ══════════════════════════════════════════════════════════════
def render_sidebar():
    sites = load_sites()
    names = [s["name"] for s in sites]
    _SH   = 'font-size:0.7rem;font-weight:800;letter-spacing:0.1em;text-transform:uppercase;color:#94A3B8;'
    _HR   = '<hr style="border:none;border-top:1px solid #E2E8F0;margin:14px 0;">'

    # DB status badge
    db_badge = '<span class="db-badge-ok">Supabase ✓</span>' if _using_supabase() else '<span class="db-badge-local">Local JSON</span>'
    st.markdown(f'<div style="margin-bottom:12px;">{db_badge}</div>', unsafe_allow_html=True)

    # ── Mine Sites List ──
    st.markdown(f'<p style="{_SH}margin:0 0 8px 0;">Mine Sites</p>', unsafe_allow_html=True)
    for site in sites:
        is_active = site["name"] == st.session_state.active_site
        label     = f"{'●' if is_active else '○'} {site['name']}  —  {site['lat']:.3f}°N, {site['lon']:.3f}°E"
        btn_type  = "primary" if is_active else "secondary"
        if st.button(label, key=f"site_sel_{site['name']}", use_container_width=True, type=btn_type):
            st.session_state.active_site = site["name"]
            st.rerun()

    st.markdown(_HR, unsafe_allow_html=True)

    # ── Forecast Range ──
    st.markdown(f'<p style="{_SH}margin:0 0 6px 0;">Forecast Range</p>', unsafe_allow_html=True)
    days = st.slider("Forecast days", 2, 7, 7, label_visibility="collapsed")
    st.markdown(_HR, unsafe_allow_html=True)

    # ── Edit Site ──
    active_obj = next((s for s in sites if s["name"] == st.session_state.active_site), None)
    with st.expander("✏️  Edit selected site", expanded=False):
        if active_obj and active_obj.get("builtin"):
            st.info("Suliyari is a built-in site and cannot be edited.")
        elif active_obj:
            with st.form("edit_site_form"):
                e_name = st.text_input("Name", value=active_obj["name"])
                ec1, ec2 = st.columns(2)
                e_lat = ec1.number_input("Lat", value=float(active_obj["lat"]), format="%.6f")
                e_lon = ec2.number_input("Lon", value=float(active_obj["lon"]), format="%.6f")
                e_pwd = st.text_input("Admin password", type="password", placeholder="Password")
                if st.form_submit_button("Save changes", use_container_width=True):
                    if e_pwd != ADMIN_PASSWORD:
                        st.error("Incorrect password.")
                    elif not e_name.strip():
                        st.error("Name required.")
                    else:
                        update_site(active_obj["name"], e_name.strip(), e_lat, e_lon)
                        st.session_state.active_site = e_name.strip()
                        st.cache_data.clear()
                        st.success("Updated.")
                        st.rerun()

    # ── Add Site ──
    with st.expander("＋  Add new site", expanded=False):
        with st.form("site_add_form"):
            nm = st.text_input("Site name", placeholder="e.g. Gorbi Mine")
            ac1, ac2 = st.columns(2)
            lt = ac1.number_input("Lat", value=0.0, format="%.6f")
            ln = ac2.number_input("Lon", value=0.0, format="%.6f")
            pw = st.text_input("Admin password", type="password", placeholder="Password")
            if st.form_submit_button("Add site", use_container_width=True):
                if pw != ADMIN_PASSWORD:   st.error("Incorrect password.")
                elif not nm.strip():       st.error("Name required.")
                elif abs(lt) < 0.001 and abs(ln) < 0.001: st.error("Enter valid coordinates.")
                else:
                    save_site(nm.strip(), lt, ln)
                    st.session_state.active_site = nm.strip()
                    st.cache_data.clear()
                    st.success(f"'{nm}' added.")
                    st.rerun()

    # ── Remove Site ──
    custom = [s for s in sites if not s.get("builtin")]
    if custom:
        with st.expander("🗑️  Remove site", expanded=False):
            with st.form("site_del_form"):
                td   = st.selectbox("Site to remove", [s["name"] for s in custom])
                dpwd = st.text_input("Admin password", type="password", key="del_pwd")
                if st.form_submit_button("Remove", use_container_width=True):
                    if dpwd != ADMIN_PASSWORD:
                        st.error("Incorrect password.")
                    else:
                        delete_site(td)
                        if st.session_state.active_site == td:
                            st.session_state.active_site = names[0] if names else None
                        st.cache_data.clear()
                        st.success(f"'{td}' removed.")
                        st.rerun()

    # ── Set Default ──
    with st.expander("⭐  Set default site on load", expanded=False):
        with st.form("set_default_form"):
            saved = get_default_site()
            idx   = names.index(saved) if saved in names else 0
            pick  = st.selectbox("Default", names, index=idx, label_visibility="collapsed")
            dpwd2 = st.text_input("Admin password", type="password", key="def_pwd")
            if st.form_submit_button("Set as default", use_container_width=True):
                if dpwd2 != ADMIN_PASSWORD: st.error("Incorrect password.")
                else:
                    set_default_site(pick)
                    st.success(f"'{pick}' is now the default.")

    st.markdown(_HR, unsafe_allow_html=True)
    st.caption(f"Font: {'ok' if _FONT_LOADED else 'missing'} | Logo: {'ok' if _LOGO_LOADED else 'missing'}")
    return days

# ══════════════════════════════════════════════════════════════
# Sidebar removed (site management moved to code/mine_sites.json)
days = 7

# ══════════════════════════════════════════════════════════════
# MAIN UI
# ══════════════════════════════════════════════════════════════

# ── Navbar ──
st.markdown(
    '<div class="wim-nav">'
    '  <div class="wim-nav-left">'
    + LOGO_HTML +
    '    <div class="wim-nav-sep"></div>'
    '    <div class="wim-nav-text">'
    '      <div class="wim-nav-title">Adani Natural Resources</div>'
    '      <div class="wim-nav-sub">WIM — Weather Intelligence Mining</div>'
    '    </div>'
    '  </div>'
    '  <div id="wim-clock" style="font-size:0.75rem;color:#94A3B8;">' + now_ist().strftime("%d %B %Y") + '</div>'
    '</div>'
    '<div class="wim-nav-spacer"></div>',
    unsafe_allow_html=True)

# ── Real-time clock via components (JS runs in iframe) ──
components.html("""
<style>body{margin:0;padding:0;overflow:hidden;} #clk{position:fixed;top:22px;right:2.5rem;font-size:0.75rem;color:#94A3B8;font-family:'Helvetica Neue',Arial,sans-serif;z-index:99999;}</style>
<div id="clk"></div>
<script>
(function(){
  var mo=["January","February","March","April","May","June","July","August","September","October","November","December"];
  function tick(){
    var d=new Date(),h=d.getHours(),ampm=h<12?"AM":"PM",h12=(h%12)||12;
    var txt=d.getDate()+" "+mo[d.getMonth()]+" "+d.getFullYear()+", "+String(h12).padStart(2,"0")+":"+String(d.getMinutes()).padStart(2,"0")+":"+String(d.getSeconds()).padStart(2,"0")+" "+ampm+" IST";
    document.getElementById("clk").textContent=txt;
    try{var el=window.parent.document.getElementById("wim-clock");if(el)el.textContent=txt;}catch(e){}
  }
  tick();setInterval(tick,1000);
})();
</script>""", height=0)

# ── Page ──
st.markdown('<div class="wim-page">', unsafe_allow_html=True)

# ── Per-browser default site (localStorage -> query param) ──
components.html("""
<script>
(function(){
  try{
    const key = 'wim_active_site';
    const stored = window.localStorage.getItem(key);
    if(!stored) return;
    const params = new URLSearchParams(window.location.search);
    if(!params.get('site')){
      params.set('site', stored);
      const newUrl = window.location.pathname + '?' + params.toString();
      window.location.replace(newUrl);
    }
  }catch(e){}
})();
</script>
""", height=0)

# ── Site selection (sidebar removed; keep UI minimal) ──
_site_names = [s["name"] for s in ALL_SITES]
_qp = st.query_params if hasattr(st, "query_params") else {}
_site_param = _qp.get("site") if _qp else None

_options = ["Select site"] + _site_names
_default_idx = (_site_names.index(_site_param) + 1) if (_site_param in _site_names) else 0

_col_left, _col_picker = st.columns([5, 1])
with _col_picker:
    _pick = st.selectbox(
        "Select site",
        _options,
        index=_default_idx,
        label_visibility="collapsed",
        key="site_picker"
    )

if _pick == "Select site":
    st.markdown('<div class="wim-alert wim-alert-none"><div class="wim-alert-label">Select site</div>Please choose which mine you want to view predictions for.</div>', unsafe_allow_html=True)
    st.stop()

# Check if session state is available
if not hasattr(st, 'session_state') or st.session_state is None:
    st.markdown('<div class="wim-alert wim-alert-none"><div class="wim-alert-label">Error</div>Please run with: streamlit run WFS.py</div>', unsafe_allow_html=True)
    st.stop()

st.session_state.active_site = _pick

# Save selection for this browser
components.html(
    f"""
<script>
  try{{ window.localStorage.setItem('wim_active_site', {json.dumps(_pick)}); }}catch(e){{}}
</script>
""",
    height=0
)

site = next((s for s in ALL_SITES if s["name"] == st.session_state.active_site), None)
if not site:
    st.markdown('<div class="wim-alert wim-alert-none"><div class="wim-alert-label">Site not found</div>Please select another site.</div>', unsafe_allow_html=True)
    st.stop()

with _col_left:
    st.markdown(f"""<div class="wim-site-row">
        <div class="wim-site-name">{site['name']}</div>
        <div class="wim-site-coord">{site['lat']}° N, {site['lon']}° E</div>
    </div>""", unsafe_allow_html=True)

_loading = st.empty()
_loading.caption(f"Fetching forecast for {site['name']}…")
by_day, mc_data, src_status = build_forecast(site["lat"], site["lon"], days)
_loading.empty()

if not by_day:
    _ok    = [s for s, v in src_status.items() if v == "ok"]
    _fail  = {s: v for s, v in src_status.items() if v != "ok"}
    _hint  = ""
    if any("401" in str(v) or "Unauthorized" in str(v) for v in _fail.values()):
        _hint += " AccuWeather free-tier quota exhausted — resets 05:30 AM IST."
    if any("timeout" in str(v).lower() for v in _fail.values()):
        _hint += " Open-Meteo timeout — network issue. Try Retry."
    _msg  = ("Partial failure. Online: " + ", ".join(_ok) + ".") if _ok else "All sources unreachable."
    _diag = "".join(f"<br><b>{s}:</b> {'Quota exhausted' if '401' in v else 'Timeout' if 'timeout' in v.lower() else 'No key' if 'no key' in v else v}" for s, v in _fail.items())
    st.markdown(f'<div class="wim-alert wim-alert-high"><div class="wim-alert-label">Data Unavailable</div>{_msg}{_hint}{_diag}</div>', unsafe_allow_html=True)
    if st.button("Retry"):
        st.cache_data.clear(); st.rerun()
    st.stop()

today   = now_ist().date()
today_h = by_day.get(today, [])

# ── 7-Day Outlook ──
st.markdown('<div class="wim-section">7-Day Outlook</div>', unsafe_allow_html=True)
render_weekly(by_day, days, site.get("type", "Coal Open Cast Mine"))
st.markdown('<hr class="wim-hr">', unsafe_allow_html=True)

# ── Day-wise tabs ──
st.markdown('<div class="wim-section">Day-wise Weather Conditions</div>', unsafe_allow_html=True)
tab_lbls = ["Today" if i == 0 else ("Tomorrow" if i == 1 else (today + timedelta(days=i)).strftime("%a, %d %b")) for i in range(min(days, 7))]
tab_days = [today + timedelta(days=i) for i in range(min(days, 7))]

for tab, tday in zip(st.tabs(tab_lbls), tab_days):
    with tab:
        dh = by_day.get(tday, [])
        if not dh:
            st.markdown('<div class="wim-alert wim-alert-none">No forecast data for this day.</div>', unsafe_allow_html=True)
            continue

        ds = day_summary(dh, site.get("type", "Coal Open Cast Mine")); sl = ds["slabs"]

        # Forecast Advisory
        mine_type = site.get("type", "Coal Open Cast Mine")
        rec = smart_rec(ds, sl, tday, mine_type)
        rain_t = ds["total_rain"]; has_l = any(s["lightning"] for s in sl); hi_w = ds["avg_wind"] >= WIND_CAUTION
        acss = ("wim-alert-high" if rain_t >= 15 or has_l else
                "wim-alert-moderate" if rain_t >= 5 or hi_w else
                "wim-alert-low" if rain_t > 0 else "wim-alert-none")
        st.markdown(f'<div class="wim-alert {acss}"><div class="wim-alert-label">Forecast Advisory</div>{rec}</div>', unsafe_allow_html=True)

        # Summary Metrics
        mcols = st.columns(7)
        cloud_val = f"{int(ds['cloud'])}%" if ds.get('cloud') else "—"
        for col, (lbl, val) in zip(mcols, [
            ("Condition", ds["condition"]), ("Max Temp", f"{ds['max_temp']}°C"),
            ("Min Temp", f"{ds['min_temp']}°C"), ("Total Rain", f"{ds['total_rain']} mm"),
            ("Rain Prob.", f"{ds['max_pop']}%"), ("Wind", f"{ds['avg_wind']} km/h"),
            ("Cloud Cover", cloud_val),
        ]):
            col.markdown(f'<div class="wim-metric"><div class="wim-metric-label">{lbl}</div><div class="wim-metric-value">{val}</div></div>', unsafe_allow_html=True)

        # MinuteCast (today only)
        if tday == today and mc_data:
            st.markdown('<div class="wim-section">Radar — Next 2 Hours (MinuteCast)</div>', unsafe_allow_html=True)
            render_mc(mc_data)

        # Rain Accumulation - only show if there's precipitation expected
        acc = rain_accum(dh, target_day=tday)
        pfx = "Next" if tday == today else "First"
        
        # Check if any accumulation has rain
        has_rain = any(acc[h][0] > 0 for h in [2, 4, 6, 12, 24])
        
        if has_rain:
            st.markdown(f'<div class="wim-section">Rainfall Accumulation{"" if tday == today else " — From Midnight"}</div>', unsafe_allow_html=True)
            acols = st.columns(5)
            for idx, h in enumerate([2, 4, 6, 12, 24]):
                mm, pop = acc[h]
                css, risk, rc = (("acc-high", "High Risk", "risk-high") if mm >= 15 else
                                 ("acc-watch", "Monitor", "risk-watch") if mm >= 5 else
                                 ("acc-safe", "Safe", "risk-safe"))
                acols[idx].markdown(
                    f'<div class="wim-accum {css}"><div class="wim-accum-period">{pfx} {h}h</div>'
                    f'<div class="wim-accum-val">{mm} mm</div>'
                    f'<div class="wim-accum-pop">{pop}% probability</div>'
                    f'<div class="wim-accum-risk {rc}">{risk}</div></div>', unsafe_allow_html=True)

        # 2-Hour Slab Windows
        st.markdown('<div class="wim-section">2-Hour Precipitation Windows</div>', unsafe_allow_html=True)
        if sl:
            rows = ""
            for s in sl:
                mm = s["mm"]
                rain_td = f'<td class="td-alert">{rain_badge_html(mm)}</td>' if mm >= RAIN_HEAVY else (f'<td class="td-warn">{rain_badge_html(mm)}</td>' if mm >= RAIN_MOD else f'<td>{rain_badge_html(mm)}</td>')
                w = s["wind"]
                wind_td = f'<td class="td-alert">{w} km/h</td>' if w >= WIND_STOP else (f'<td class="td-warn">{w} km/h</td>' if w >= WIND_CAUTION else f'<td>{w} km/h</td>')
                v = s["vis"]
                vis_td  = f'<td class="td-alert">{v} km</td>' if v <= VIS_STOP else (f'<td class="td-warn">{v} km</td>' if v <= VIS_CAUTION else f'<td>{v} km</td>')
                l_td    = '<td class="td-alert"><span class="wim-badge b-lightning">Alert</span></td>' if s["lightning"] else '<td style="color:#94A3B8;">—</td>'
                impact  = mining_impact_html(mm, w, v, s["lightning"])
                rows   += f"<tr><td style='font-weight:600;color:#334155;'>{s['label']}</td>{rain_td}<td style='color:#64748B;'>{s['pop']}%</td>{wind_td}{vis_td}{l_td}<td>{impact}</td></tr>"
            st.markdown(
                '<div style="overflow-x:auto;"><table class="wim-table"><thead><tr>'
                '<th>Time Window</th><th>Rainfall</th><th>Probability</th>'
                '<th>Wind Speed</th><th>Visibility</th><th>Lightning</th><th>Mining Impact</th>'
                '</tr></thead><tbody>' + rows + '</tbody></table></div>', unsafe_allow_html=True)

        # Hourly Temperature & Precipitation Graph
        st.markdown('<div class="wim-section">Hourly Operations Timeline</div>', unsafe_allow_html=True)
        render_hourly_graph(dh, tday)

st.markdown('<hr class="wim-hr"></div>', unsafe_allow_html=True)

# ── Footer ──
srcs = ["Open-Meteo (ECMWF)"]
if ACCUWEATHER_KEY: srcs = ["AccuWeather", "MinuteCast (radar)"] + srcs
if OPENWEATHER_KEY: srcs.append("OpenWeather")
if TOMORROWIO_KEY:  srcs.append("Tomorrow.io")
st.markdown(
    f'<p style="font-size:0.68rem;color:#94A3B8;text-align:center;padding:0.5rem 0 2rem;">'
    f'Sources: {" · ".join(srcs)} &nbsp;|&nbsp; Rain confirmed across ≥2 sources &nbsp;|&nbsp; '
    f'Adani Natural Resources © {now_ist().year}</p>', unsafe_allow_html=True)
