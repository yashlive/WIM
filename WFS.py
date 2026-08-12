"""
Adani Natural Resources — WIM (Weather Intelligence Mining)
v7.0 — Dashboard-only runtime, background weather ingestion,
append-only forecast history in Supabase, no provider API calls from Streamlit
"""
import os, json, requests, collections, base64, concurrent.futures, hashlib, math
import streamlit.components.v1 as components
from datetime import datetime, timedelta
import pytz
import streamlit as st

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

st.set_page_config(
    page_title="WIM — Weather Intelligence Mining | Adani Natural Resources",
    page_icon="\U0001f326",
    layout="wide",
    initial_sidebar_state="expanded"
)

def load_asset_b64(path):
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except Exception:
        return ""

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_CS_DIR = "/workspaces/weather-forecast-mines"

def _asset_path(filename):
    for base in [_SCRIPT_DIR, _CS_DIR]:
        p = os.path.join(base, filename)
        if os.path.exists(p):
            return p
    return os.path.join(_SCRIPT_DIR, filename)

LOGO_PATH = _asset_path("Adani_2012_logo.png")
FONT_PATH = _asset_path("adani-regular.ttf")
LOGO_B64 = load_asset_b64(LOGO_PATH)
FONT_B64 = load_asset_b64(FONT_PATH)
_FONT_LOADED = bool(FONT_B64)
_LOGO_LOADED = bool(LOGO_B64)

LOGO_HTML = f'<img src="data:image/png;base64,{LOGO_B64}" style="height:44px;display:block;" alt="Adani">' if LOGO_B64 else '<span style="font-size:1.6rem;font-weight:900;color:#0B74B0;">adani</span>'
_FONT_STACK = ("'AdaniFont', 'Helvetica Neue', Arial, sans-serif" if FONT_B64 else "'Helvetica Neue', Arial, sans-serif")
FONT_FACE = f"@font-face{{font-family:'AdaniFont';src:url('data:font/truetype;base64,{FONT_B64}') format('truetype');font-weight:normal;font-style:normal;}}" if FONT_B64 else ""

_CSS = f"""<style>
{FONT_FACE}
*,*::before,*::after{{box-sizing:border-box;}}
html,body,[class*="css"],.stApp,.stApp *,[data-testid="stAppViewContainer"],[data-testid="stAppViewContainer"] *,.block-container,.block-container *{{font-family:{_FONT_STACK} !important;}}
[data-testid="stIconMaterial"],
[data-testid="stIconMaterial"] *,
span[data-testid="stIconMaterial"],
.material-icons,
[class*="MaterialIcon"],
i.material-icons{{
    font-family:"Material Symbols Rounded","Material Icons" !important;
    -webkit-text-fill-color:initial !important;
}}
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
.stTabs [data-baseweb="tab-list"]{{gap:0;border-bottom:2px solid #E2E8F0;background:transparent;}}
.stTabs [data-baseweb="tab"], .stTabs [role="tab"]{{
    background:transparent !important;border:none !important;
    border-bottom:2px solid transparent !important;margin-bottom:-2px !important;
    opacity:1 !important;visibility:visible !important;padding:10px 18px !important;
}}
.stTabs [data-baseweb="tab"] p, .stTabs [data-baseweb="tab"] div, .stTabs [data-baseweb="tab"] span,
.stTabs [role="tab"] p, .stTabs [role="tab"] div, .stTabs [role="tab"] span{{
    color:#64748B !important; font-size:0.82rem !important; font-weight:600 !important;
    -webkit-text-fill-color:#64748B !important; opacity:1 !important;
}}
.stTabs [data-baseweb="tab"]:hover, .stTabs [role="tab"]:hover{{
    background:#F0F7FF !important;border-radius:6px 6px 0 0;
}}
.stTabs [data-baseweb="tab"]:hover p, .stTabs [data-baseweb="tab"]:hover div, .stTabs [data-baseweb="tab"]:hover span,
.stTabs [role="tab"]:hover p, .stTabs [role="tab"]:hover div, .stTabs [role="tab"]:hover span{{
    color:#0B74B0 !important; -webkit-text-fill-color:#0B74B0 !important;
}}
.stTabs [aria-selected="true"]{{border-bottom:2px solid #0B74B0 !important;background:transparent !important;}}
.stTabs [aria-selected="true"] p, .stTabs [aria-selected="true"] div, .stTabs [aria-selected="true"] span{{
    color:#0B74B0 !important; font-weight:700 !important; -webkit-text-fill-color:#0B74B0 !important;
}}
.stTabs [data-baseweb="tab-highlight"]{{background:#0B74B0 !important;height:2px !important;}}
.stTabs [data-baseweb="tab-border"]{{display:none !important;}}
.streamlit-expanderHeader{{font-size:0.82rem !important;font-weight:700 !important;color:#1A1A2E !important;background:#F8FAFC !important;border:1px solid #E2E8F0 !important;border-radius:8px !important;padding:10px 14px !important;}}
.streamlit-expanderContent{{border:1px solid #E2E8F0 !important;border-top:none !important;border-radius:0 0 8px 8px !important;padding:14px !important;}}
div[data-testid="stExpander"] summary{{display:flex !important;align-items:center !important;gap:8px !important;padding:10px 14px !important;}}
div[data-testid="stExpander"] summary p{{margin:0 !important;flex:1 1 auto !important;order:1 !important;}}
div[data-testid="stExpander"] summary [data-testid="stIconMaterial"]{{order:2 !important;flex:0 0 auto !important;position:static !important;margin-left:auto !important;}}
div[data-testid="stExpander"] details summary{{list-style:none !important;}}
div[data-testid="stExpander"] details summary::-webkit-details-marker{{display:none !important;}}
.db-badge-ok{{display:inline-block;background:#D1FAE5;color:#065F46;border-radius:4px;padding:2px 8px;font-size:0.65rem;font-weight:700;}}
.db-badge-local{{display:inline-block;background:#FEF3C7;color:#92400E;border-radius:4px;padding:2px 8px;font-size:0.65rem;font-weight:700;}}
div[data-testid="stSelectbox"]{{margin-left:auto !important;max-width:180px !important;}}
div[data-testid="stSelectbox"] > div > div{{background:#FFFFFF !important;border:1px solid #6B7280 !important;border-radius:6px !important;}}
div[data-testid="stSelectbox"] > div > div:hover{{border-color:#374151 !important;}}
div[data-testid="stSelectbox"] *{{color:#000000 !important;}}
div[data-testid="stSelectbox"] [role="button"],div[data-testid="stSelectbox"] [role="button"] *,div[data-testid="stSelectbox"] input,div[data-testid="stSelectbox"] span{{color:#111827 !important;font-size:14px !important;font-weight:600 !important;}}
div[data-testid="stSelectbox"] [role="listbox"]{{background:#FFFFFF !important;border:1px solid #D1D5DB !important;border-radius:6px !important;box-shadow:0 4px 6px rgba(0,0,0,0.1) !important;}}
div[data-testid="stSelectbox"] [role="option"],div[data-testid="stSelectbox"] [role="option"] *{{color:#111827 !important;font-size:14px !important;}}
div[data-testid="stSelectbox"] [role="option"]:hover{{background:#F3F4F6 !important;}}
div[data-testid="stSelectbox"] [role="option"][aria-selected="true"],div[data-testid="stSelectbox"] [role="option"][aria-selected="true"] *{{background:#0B74B0 !important;color:#FFFFFF !important;font-weight:600 !important;}}
@media (max-width: 1199px) {{
    .block-container{{padding:0.25rem 1.5rem 1.5rem 1.5rem !important;}}
    .wim-day{{padding:12px 8px;}}
    .wim-day-rain{{font-size:1rem;}}
    .wim-metric{{padding:14px 16px;}}
    .wim-metric-value{{font-size:1.25rem;}}
}}
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
    [data-testid="stHorizontalBlock"]>.element-container{{flex:0 0 calc(50% - 6px) !important;min-width:calc(50% - 6px) !important;}}
    .wim-day{{padding:10px 8px;margin-bottom:8px;}}
    .wim-day-label{{font-size:0.55rem;}}
    .wim-day-date{{font-size:0.6rem;}}
    .wim-day-cond{{font-size:0.7rem;}}
    .wim-day-rain{{font-size:0.9rem;}}
    .wim-day-temp{{font-size:0.6rem;}}
    .wim-metric{{padding:10px 12px;}}
    .wim-metric-label{{font-size:0.55rem;}}
    .wim-metric-value{{font-size:1rem;}}
    .wim-section{{font-size:0.55rem;margin:4px 0 6px 0;padding-bottom:4px;}}
    .wim-alert{{padding:12px 14px;font-size:0.8rem;}}
    .wim-alert-label{{font-size:0.6rem;}}
    .wim-table{{font-size:0.7rem;min-width:600px;}}
    .wim-table th,.wim-table td{{padding:6px 8px;}}
    .wim-accum{{padding:10px 8px;}}
    .wim-accum-period{{font-size:0.55rem;}}
    .wim-accum-val{{font-size:1.1rem;}}
    .wim-accum-pop{{font-size:0.6rem;}}
    .wim-accum-risk{{font-size:0.6rem;}}
    div[style*="min-width:36px"]{{min-width:32px !important;}}
    div[style*="font-size:0.65rem"]{{font-size:0.6rem !important;}}
    @media (max-width: 375px) {{
        .wim-nav-sub{{display:none;}}
        .wim-site-coord{{display:none;}}
    }}
}}
@media (max-width: 320px) {{
    .block-container{{padding:0.25rem 0.5rem 0.5rem 0.5rem !important;}}
    .wim-site-name{{font-size:1rem;}}
    div[data-testid="stSelectbox"]{{max-width:120px !important;}}
}}
@media (max-width: 767px) and (orientation: landscape) {{
    .wim-nav-spacer{{height:40px;}}
    [data-testid="stHorizontalBlock"]>.element-container{{flex:0 0 calc(25% - 6px) !important;min-width:calc(25% - 6px) !important;}}
}}
@media print {{
    .wim-nav{{position:relative;box-shadow:none;border-bottom:1px solid #ccc;}}
    .wim-nav-spacer{{display:none;}}
    .wim-day{{break-inside:avoid;}}
    .wim-metric{{break-inside:avoid;}}
}}
</style>"""
st.markdown(_CSS, unsafe_allow_html=True)

# CONFIGURATION
def _secret(name, default=""):
    try:
        value = st.secrets.get(name, None)
    except Exception:
        value = None
    if value is None or value == "":
        value = os.getenv(name, default)
    # Streamlit TOML values occasionally end up with copied spaces/newlines.
    # Trim string secrets so a valid provider key is not rejected as invalid.
    return value.strip() if isinstance(value, str) else value

def _secret_bool(name, default=False):
    value = _secret(name, str(default))
    return str(value).strip().lower() in {"1", "true", "yes", "on"}

ACCUWEATHER_KEY = _secret("ACCUWEATHER_KEY")
OPENWEATHER_KEY = _secret("OPENWEATHER_KEY")
TOMORROWIO_KEY = _secret("TOMORROWIO_KEY")
WEATHERSTACK_KEY = _secret("WEATHERSTACK_KEY")
IMD_API_KEY = _secret("IMD_API_KEY")
IMD_AUTH_HEADER = _secret("IMD_AUTH_HEADER", "Authorization")
IMD_AUTH_PREFIX = _secret("IMD_AUTH_PREFIX", "Bearer ")
SUPABASE_URL = str(_secret("SUPABASE_URL")).rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = _secret("SUPABASE_SERVICE_ROLE_KEY")
# If an OpenWeather key exists, try One Call 4.0 by default. Set false explicitly
# in Streamlit secrets if the One Call by Call product has not been activated.
OPENWEATHER_ONECALL_ENABLED = _secret_bool("OPENWEATHER_ONECALL_ENABLED", bool(OPENWEATHER_KEY))
# Weatherstack free/current plans are too small for continuous mine operations.
WEATHERSTACK_ENABLED = _secret_bool("WEATHERSTACK_ENABLED", False)
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "Adani@2026#Mine")
SITES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mine_sites.json")

# Persistent API-cache policy. Values are intentionally conservative so a
# Streamlit restart/redeploy does not immediately burn vendor quotas again.
ACCUWEATHER_LOCATION_TTL_MIN = 30 * 24 * 60
ACCUWEATHER_HOURLY_TTL_MIN = 90
# MinuteCast free trial is only 50 requests / rolling 24h. With 12 mine
# sites, a six-hour refresh cadence is at most 48 successful attempts/day.
# IMPORTANT: MinuteCast itself only predicts the next ~120 minutes, so cached
# data is never shifted forward or reused outside its original forecast horizon.
MINUTECAST_TTL_MIN = 6 * 60
MINUTECAST_SOFT_LIMIT_24H = 48
PROVIDER_BACKOFF_TTL_MIN = 6 * 60
WEATHERSTACK_TTL_MIN = 60
TOMORROW_TTL_MIN = 30
OPENWEATHER_TTL_MIN = 60
IMD_TTL_MIN = 30

DEFAULT_SITES = [
    {"id": "builtin-suliyari",   "name": "Suliyari",         "lat": 23.941626, "lon": 82.331934, "type": "Coal Open Cast Mine", "imd_subdivision": "East Madhya Pradesh", "builtin": True},
    {"id": "builtin-dhirauli",   "name": "Dhirauli",        "lat": 23.936440, "lon": 82.358836, "type": "Coal Open Cast Mine", "imd_subdivision": "East Madhya Pradesh", "builtin": True},
    {"id": "builtin-parsa",      "name": "Parsa",           "lat": 22.824950, "lon": 82.804340, "type": "Coal Open Cast Mine", "imd_subdivision": "Chhattisgarh", "builtin": True},
    {"id": "builtin-talabira",   "name": "Talabira",        "lat": 21.756317, "lon": 83.970446, "type": "Coal Open Cast Mine", "imd_subdivision": "Odisha", "builtin": True},
    {"id": "builtin-gare-pelma", "name": "Gare Pelma III",  "lat": 22.105303, "lon": 83.292822, "type": "Coal Open Cast Mine", "imd_subdivision": "Chhattisgarh", "builtin": True},
    {"id": "builtin-gp-ii",      "name": "Gare Pelma II",   "lat": 22.160838, "lon": 83.472457, "type": "Coal Open Cast Mine", "imd_subdivision": "Chhattisgarh", "builtin": True},
    {"id": "builtin-pcb",        "name": "PCB",             "lat": 22.854601, "lon": 82.763414, "type": "Coal Open Cast Mine", "imd_subdivision": "Chhattisgarh", "builtin": True},
    {"id": "builtin-pekb",       "name": "PEKB",            "lat": 22.823873, "lon": 82.805322, "type": "Coal Open Cast Mine", "imd_subdivision": "Chhattisgarh", "builtin": True},
    {"id": "builtin-kurmitar",   "name": "Kurmitar",        "lat": 21.749766, "lon": 85.167471, "type": "Iron Ore Mine", "imd_subdivision": "Odisha", "builtin": True},
    {"id": "builtin-taldih",     "name": "Taldih",          "lat": 21.910560, "lon": 85.180140, "type": "Iron Ore Mine", "imd_subdivision": "Odisha", "builtin": True},
    {"id": "builtin-gondbahera-ujheni", "name": "Gondbahera Ujheni", "lat": 24.175830, "lon": 82.369544, "type": "Underground Mine (Incline/Shaft — Greenfield)", "imd_subdivision": "East Madhya Pradesh", "builtin": True},
    {"id": "builtin-gondkhari",  "name": "Gondkhari",       "lat": 21.143326, "lon": 78.934850, "type": "Underground Mine (Incline/Shaft — Greenfield)", "imd_subdivision": "Vidarbha", "builtin": True},
]
IST = pytz.timezone('Asia/Kolkata')
UTC = pytz.utc
TIMEOUT = 20
RETRY_MAX = 3

WIND_CAUTION = 30
WIND_STOP = 32
VIS_CAUTION = 5.0
VIS_STOP = 2.0
RAIN_MOD = 1.5
RAIN_HEAVY = 5.0

def load_sites():
    custom = _load_sites_json()
    result = list(DEFAULT_SITES)
    builtin_names = {s["name"] for s in DEFAULT_SITES}
    for s in custom:
        if s.get("name") not in builtin_names:
            result.append(s)
    return result

def _load_sites_json():
    if not os.path.exists(SITES_FILE): return []
    try:
        with open(SITES_FILE) as f:
            return json.load(f)
    except Exception:
        return []

def save_site(name, lat, lon):
    ex = _load_sites_json()
    ex = [s for s in ex if s["name"] != name]
    ex.append({"name": name, "lat": lat, "lon": lon, "builtin": False})
    with open(SITES_FILE, "w") as f:
        json.dump(ex, f, indent=2)

def update_site(old_name, new_name, lat, lon):
    ex = _load_sites_json()
    for s in ex:
        if s["name"] == old_name:
            s["name"] = new_name.strip()
            s["lat"] = lat
            s["lon"] = lon
    with open(SITES_FILE, "w") as f:
        json.dump(ex, f, indent=2)

def delete_site(name):
    ex = _load_sites_json()
    ex = [s for s in ex if s["name"] != name]
    with open(SITES_FILE, "w") as f:
        json.dump(ex, f, indent=2)

def get_default_site():
    _f = os.path.join(os.path.dirname(os.path.abspath(__file__)), "default_site.json")
    try:
        if os.path.exists(_f):
            with open(_f) as f:
                return json.load(f).get("name")
    except Exception:
        pass
    return None

def set_default_site(name):
    _f = os.path.join(os.path.dirname(os.path.abspath(__file__)), "default_site.json")
    with open(_f, "w") as f:
        json.dump({"name": name}, f)

ALL_SITES = load_sites()
_names = [s["name"] for s in ALL_SITES]

if "active_site" not in st.session_state:
    _def = get_default_site()
    st.session_state.active_site = _def if (_def and _def in _names) else (_names[0] if _names else None)

def now_ist():
    return datetime.now(IST)

def utc_to_ist(dt):
    if dt.tzinfo is None:
        dt = UTC.localize(dt)
    return dt.astimezone(IST)

def rain_badge_html(mm):
    if mm == 0:
        return '<span class="wim-badge b-none">0 mm</span>'
    elif mm < 0.3:
        return f'<span class="wim-badge b-drizzle">{mm} mm · Drizzle</span>'
    elif mm < 1.5:
        return f'<span class="wim-badge b-light">{mm} mm · Light</span>'
    elif mm < 5.0:
        return f'<span class="wim-badge b-moderate">{mm} mm · Moderate</span>'
    else:
        return f'<span class="wim-badge b-heavy">{mm} mm · Heavy</span>'

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
    if total < 0.5:
        return "Clear"
    rain_types = []
    if descs and total >= 0.5:
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
    api_rain_type = collections.Counter(rain_types).most_common(1)[0][0] if rain_types else None
    if total >= 15 and max_pop >= 25:
        return "Heavy Rain"
    elif total >= 15 and max_pop < 25:
        return "Moderate Rain"
    elif total >= 5 and max_pop >= 35:
        return "Moderate Rain"
    elif total >= 5 and max_pop < 35:
        return "Light Rain"
    elif total >= 1.5 and max_pop >= 45:
        return "Light Rain"
    elif total >= 1.5 and max_pop < 45:
        return "Drizzle"
    elif total >= 0.5:
        return "Drizzle"
    if api_rain_type and total >= 0.5:
        if api_rain_type == "heavy": return "Heavy Rain"
        if api_rain_type == "moderate": return "Moderate Rain"
        if api_rain_type == "light": return "Light Rain"
        if api_rain_type == "drizzle": return "Drizzle"
    return "Clear"

def _coord_cache_key(lat, lon):
    # Six decimals keeps every configured mine coordinate in a distinct cache key.
    return f"{float(lat):.6f},{float(lon):.6f}"

def _credential_fp(secret):
    return hashlib.sha256(str(secret or "").encode("utf-8")).hexdigest()[:10]

def _haversine_km(lat1, lon1, lat2, lon2):
    try:
        r = 6371.0088
        p1, p2 = math.radians(float(lat1)), math.radians(float(lat2))
        dp = math.radians(float(lat2) - float(lat1))
        dl = math.radians(float(lon2) - float(lon1))
        a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
        return r * 2 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1 - a)))
    except Exception:
        return None


def _supabase_enabled():
    return bool(SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY)


def _supabase_headers(extra=None):
    headers = {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
    }
    if extra:
        headers.update(extra)
    return headers


@st.cache_data(ttl=300)
def db_health_check():
    if not _supabase_enabled():
        return False, "not configured"
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/weather_api_cache",
            headers=_supabase_headers(),
            params={"select": "source", "limit": "1"},
            timeout=8,
        )
        r.raise_for_status()
        return True, None
    except Exception as e:
        return False, _safe_error(e) if "_safe_error" in globals() else str(e)


def db_cache_get(source, cache_key):
    """Return unexpired JSON payload from Supabase, or None when unavailable."""
    if not _supabase_enabled():
        return None
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/weather_api_cache",
            headers=_supabase_headers(),
            params={
                "select": "payload,expires_at",
                "source": f"eq.{source}",
                "cache_key": f"eq.{cache_key}",
                "order": "fetched_at.desc",
                "limit": "1",
            },
            timeout=8,
        )
        r.raise_for_status()
        rows = r.json()
        if not rows:
            return None
        expires = rows[0].get("expires_at")
        if expires:
            exp_dt = datetime.fromisoformat(str(expires).replace("Z", "+00:00"))
            if exp_dt <= datetime.now(UTC):
                return None
        return rows[0].get("payload")
    except Exception:
        # DB cache must never take the weather app down.
        return None


def db_cache_get_record(source, cache_key):
    """Return cache payload plus timestamps. Used when forecast age matters."""
    if not _supabase_enabled():
        return None
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/weather_api_cache",
            headers=_supabase_headers(),
            params={
                "select": "payload,fetched_at,expires_at",
                "source": f"eq.{source}",
                "cache_key": f"eq.{cache_key}",
                "order": "fetched_at.desc",
                "limit": "1",
            },
            timeout=8,
        )
        r.raise_for_status()
        rows = r.json()
        if not rows:
            return None
        expires = rows[0].get("expires_at")
        if expires:
            exp_dt = datetime.fromisoformat(str(expires).replace("Z", "+00:00"))
            if exp_dt <= datetime.now(UTC):
                return None
        return rows[0]
    except Exception:
        return None


def db_cache_set(source, cache_key, payload, ttl_minutes):
    if not _supabase_enabled() or payload is None:
        return False
    try:
        now_utc = datetime.now(UTC)
        body = {
            "source": source,
            "cache_key": cache_key,
            "payload": payload,
            "fetched_at": now_utc.isoformat(),
            "expires_at": (now_utc + timedelta(minutes=ttl_minutes)).isoformat(),
        }
        r = requests.post(
            f"{SUPABASE_URL}/rest/v1/weather_api_cache",
            headers=_supabase_headers({"Prefer": "resolution=merge-duplicates,return=minimal"}),
            params={"on_conflict": "source,cache_key"},
            json=body,
            timeout=8,
        )
        r.raise_for_status()
        return True
    except Exception:
        return False


def _provider_backoff_key(provider):
    # Key-specific backoff: replacing a bad API key immediately gets a fresh
    # attempt instead of inheriting the previous key's six-hour lockout.
    secret = {
        "accuweather_core": ACCUWEATHER_KEY,
        "accuweather_minutecast": ACCUWEATHER_KEY,
        "tomorrow_io": TOMORROWIO_KEY,
        "weatherstack": WEATHERSTACK_KEY,
        "openweather": OPENWEATHER_KEY,
        "imd": IMD_API_KEY,
    }.get(provider, "")
    fingerprint = hashlib.sha256(str(secret).encode("utf-8")).hexdigest()[:10] if secret else "nokey"
    return f"{provider}|{fingerprint}"


def provider_backoff_get(provider):
    payload = db_cache_get("provider_backoff", _provider_backoff_key(provider))
    if isinstance(payload, dict):
        return payload.get("message")
    return None


def provider_backoff_set(provider, message, ttl_minutes=PROVIDER_BACKOFF_TTL_MIN):
    # Prevent every Streamlit rerun / every mine from hammering a provider that
    # has already told us the key is invalid, the plan is blocked, or quota is hit.
    db_cache_set("provider_backoff", _provider_backoff_key(provider), {"message": str(message)}, ttl_minutes)


def _iso_dt(value):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = UTC.localize(dt)
        return dt.astimezone(UTC)
    except Exception:
        return None


def _active_minutecast_intervals(mc_payload):
    """Return only MinuteCast points whose original forecast time is still relevant."""
    if not mc_payload:
        return []
    if isinstance(mc_payload, list):
        # Legacy cache format cannot safely be time-anchored; don't shift stale
        # minute offsets forward. Force it to age out rather than fabricate nowcast.
        return []
    intervals = mc_payload.get("intervals", []) if isinstance(mc_payload, dict) else []
    fetched_at = _iso_dt(mc_payload.get("fetched_at")) if isinstance(mc_payload, dict) else None
    if not fetched_at:
        return []
    now_utc = datetime.now(UTC)
    active = []
    for m in intervals:
        minute = int(m.get("minute", 0) or 0)
        event_utc = fetched_at + timedelta(minutes=minute)
        # Keep a tiny past tolerance so the current hour aggregates correctly.
        if event_utc < now_utc - timedelta(minutes=5) or event_utc > fetched_at + timedelta(minutes=125):
            continue
        item = dict(m)
        item["forecast_time"] = event_utc.astimezone(IST).isoformat()
        active.append(item)
    return active


def _minutecast_status(mc_payload, mc_err):
    if not mc_payload:
        return str(mc_err)
    if isinstance(mc_payload, dict):
        fetched = _iso_dt(mc_payload.get("fetched_at"))
        if fetched:
            age_min = max(0, (datetime.now(UTC) - fetched).total_seconds() / 60)
            active = _active_minutecast_intervals(mc_payload)
            if active:
                return f"ok — {int(age_min)} min old; next API refresh at 6h"
            remaining = max(0, MINUTECAST_TTL_MIN - age_min)
            return f"standby — 2h nowcast horizon ended; next API refresh in ~{int(remaining)} min"
    return "cached"


def db_usage_count_24h(source):
    """Conservative rolling-24h count used to protect tiny trial quotas."""
    if not _supabase_enabled():
        return None
    try:
        since = (datetime.now(UTC) - timedelta(hours=24)).isoformat()
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/weather_api_usage",
            headers=_supabase_headers({"Prefer": "count=exact", "Range-Unit": "items", "Range": "0-0"}),
            params={"select": "id", "source": f"eq.{source}", "called_at": f"gte.{since}"},
            timeout=8,
        )
        r.raise_for_status()
        content_range = r.headers.get("Content-Range", "")
        if "/" in content_range:
            total = content_range.rsplit("/", 1)[-1]
            if total.isdigit():
                return int(total)
        return len(r.json())
    except Exception:
        return None


def db_usage_record(source):
    if not _supabase_enabled():
        return
    try:
        requests.post(
            f"{SUPABASE_URL}/rest/v1/weather_api_usage",
            headers=_supabase_headers({"Prefer": "return=minimal"}),
            json={"source": source, "called_at": datetime.now(UTC).isoformat()},
            timeout=8,
        ).raise_for_status()
    except Exception:
        pass


def _safe_error(err):
    text = str(err)
    for secret in [ACCUWEATHER_KEY, OPENWEATHER_KEY, TOMORROWIO_KEY, WEATHERSTACK_KEY, IMD_API_KEY, SUPABASE_SERVICE_ROLE_KEY]:
        if secret:
            text = text.replace(str(secret), "***")
    return text


def _weatherstack_error(data):
    if isinstance(data, dict) and data.get("error"):
        err = data["error"]
        if isinstance(err, dict):
            return err.get("info") or err.get("type") or str(err)
        return str(err)
    return None


def _decode_background_forecast(payload, days=7):
    """Convert the JSON snapshot written by weather_worker.py back into WIM's UI shape."""
    if not isinstance(payload, dict):
        return {}, [], {}, None
    by_day = {}
    today = now_ist().date()
    cutoff = today + timedelta(days=max(1, int(days)))
    for day_str, rows in (payload.get("by_day") or {}).items():
        try:
            day_key = datetime.fromisoformat(str(day_str)).date()
        except Exception:
            try:
                day_key = datetime.strptime(str(day_str), "%Y-%m-%d").date()
            except Exception:
                continue
        if day_key < today or day_key >= cutoff:
            continue
        decoded = []
        for row in rows or []:
            try:
                dt = datetime.fromisoformat(str(row.get("time", "")))
                if dt.tzinfo is None:
                    dt = IST.localize(dt)
                else:
                    dt = dt.astimezone(IST)
            except Exception:
                continue
            decoded.append((dt, row.get("data") or {}))
        by_day[day_key] = decoded
    return (
        by_day,
        payload.get("mc_data") or [],
        payload.get("source_status") or {},
        payload.get("imd_advisory"),
    )


def load_background_forecast(site_id, days=7):
    """Read the latest precomputed mine forecast. No weather API is called here."""
    if not _supabase_enabled():
        return {}, [], {
            "Background ingestion": "not configured — add SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY",
            "Supabase cache": "not configured",
        }, None
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/weather_latest",
            headers=_supabase_headers(),
            params={
                "select": "forecast_payload,fetched_at,run_id",
                "site_id": f"eq.{site_id}",
                "limit": "1",
            },
            timeout=10,
        )
        r.raise_for_status()
        rows = r.json()
        if not rows:
            return {}, [], {
                "Background ingestion": "no snapshot yet — run weather_worker.py once",
                "Supabase cache": "ok",
            }, None
        record = rows[0]
        payload = record.get("forecast_payload") or {}
        by_day, mc_data, src_status, imd = _decode_background_forecast(payload, days=days)
        fetched_at = _iso_dt(record.get("fetched_at") or payload.get("generated_at"))
        if fetched_at:
            age_min = max(0, (datetime.now(UTC) - fetched_at).total_seconds() / 60.0)
            if age_min <= 75:
                bg_status = f"ok — refreshed {int(age_min)} min ago"
            else:
                bg_status = f"stale — last successful background refresh was {int(age_min)} min ago"
        else:
            bg_status = "snapshot loaded — refresh timestamp unavailable"
        src_status = dict(src_status)
        src_status["Background ingestion"] = bg_status
        src_status["Supabase cache"] = "ok"
        return by_day, mc_data, src_status, imd
    except Exception as e:
        return {}, [], {
            "Background ingestion": f"read failed — {_safe_error(e)}",
            "Supabase cache": "read failed",
        }, None


def generate_fixed_slabs():
    slabs = []
    for i in range(12):
        s_hour = i * 2
        e_hour = (i + 1) * 2
        s_label = f"{s_hour % 12 or 12}:00 {'AM' if s_hour < 12 else 'PM'}"
        e_label = f"{e_hour % 12 or 12}:00 {'AM' if e_hour < 12 else 'PM'}"
        if e_hour >= 24:
            e_hour = 0
            e_label = "12:00 AM (next day)"
        full_label = f"{s_label} – {e_label}"
        slabs.append((s_hour, e_hour, full_label, 0))
    return slabs

def hour_to_slab(h, slabs):
    for s, e, n, m in slabs:
        if s <= h < e or (s > e and (h >= s or h < e)):
            return (s, e, n, m)
    return None

def build_slabs(hourly, is_today=False):
    slabs = generate_fixed_slabs()
    current_hour = now_ist().hour
    raw = collections.defaultdict(lambda: dict(rain=0, risk_rain=0, pop=[], wind=[], vis=[], lightning=[], lightning_prob=[], hum=[], confidence=[], count=0))
    for hk, d in hourly:
        sk = hour_to_slab(hk.hour, slabs)
        if not sk:
            continue
        if is_today:
            slab_start, slab_end, _, _ = sk
            if slab_start < slab_end:
                slab_finished = slab_end <= current_hour
            else:
                slab_finished = current_hour >= slab_end and current_hour < slab_start
            if slab_finished:
                continue
        r = raw[sk]
        r["rain"] += d["rain_mm"]
        r["risk_rain"] += d.get("risk_rain_mm", d["rain_mm"])
        r["pop"].append(d["pop"])
        r["wind"].append(d["wind_kmh"])
        r["vis"].append(d["vis_km"])
        r["lightning"].append(d["lightning"])
        r["lightning_prob"].append(d.get("lightning_prob", 100 if d["lightning"] else 0))
        r["hum"].append(d["humidity"])
        r["confidence"].append(d.get("confidence", 0))
        r["count"] += 1
    slabs_out = []
    for sk, r in raw.items():
        if not r["count"]:
            continue
        avg = lambda lst: sum(lst) / len(lst) if lst else 0
        pops = r["pop"]
        pop_val = int(sorted(pops)[int(len(pops) * 0.75)] if pops else 0)
        slabs_out.append(dict(label=sk[2], sort=sk[0], mm=round(r["rain"], 1),
                              risk_mm=round(r["risk_rain"], 1),
                              pop=pop_val, wind=round(avg(r["wind"]), 1),
                              vis=round(avg(r["vis"]), 1), hum=round(avg(r["hum"]), 1),
                              confidence=round(avg(r["confidence"]), 0),
                              lightning=any(r["lightning"]),
                              lightning_prob=round(max(r["lightning_prob"]) if r["lightning_prob"] else 0, 0)))
    slabs_out.sort(key=lambda x: x["sort"])
    return slabs_out

def day_summary(hourly, mine_type="Coal Open Cast Mine", target_day=None):
    if not hourly:
        return dict(max_temp="—", min_temp="—", total_rain=0, max_pop=0, condition="—", humidity=0, slabs=[], avg_wind=0, min_vis=10)
    today = now_ist().date()
    is_today = (target_day == today) if target_day else False
    temps = [d["temp"] for _, d in hourly]
    rains = [d["rain_mm"] for _, d in hourly]
    pops = [d["pop"] for _, d in hourly]
    winds = [d["wind_kmh"] for _, d in hourly]
    viss = [d["vis_km"] for _, d in hourly]
    hums = [d["humidity"] for _, d in hourly]
    clouds = [d.get("cloud", 0) for _, d in hourly if d.get("cloud", 0) > 0]
    total = round(sum(rains), 1)
    descs = [d["desc"] for _, d in hourly if d["desc"]]
    max_pop_val = int(round(sorted(pops)[int(len(pops) * 0.75)] if pops else 0, 0))
    return dict(
        max_temp=round(max(temps), 1) if temps else "—",
        min_temp=round(min(temps), 1) if temps else "—",
        total_rain=total,
        max_pop=max_pop_val,
        condition=condition_str(total, descs, max_pop_val),
        humidity=round(sum(hums) / len(hums), 1) if hums else 0,
        cloud=round(sum(clouds) / len(clouds), 0) if clouds else None,
        avg_wind=round(sum(winds) / len(winds), 1) if winds else 0,
        min_vis=round(min(viss), 1) if viss else 10,
        slabs=build_slabs(hourly, is_today=is_today))

def smart_rec(ds, slabs, target_day, mine_type="Coal Open Cast Mine"):
    rain = ds["total_rain"]; mwind = ds.get("max_wind", ds.get("avg_wind", 0))
    mvis = ds["min_vis"]; pop = ds["max_pop"]
    has_l = any(s["lightning"] for s in slabs)
    rain_sl = [s for s in slabs if s["mm"] > 0]
    heavy_sl = [s for s in slabs if s["mm"] >= RAIN_HEAVY]
    mod_sl = [s for s in slabs if RAIN_MOD <= s["mm"] < RAIN_HEAVY]
    today = now_ist().date()
    dlabel = "Today" if target_day == today else target_day.strftime("%A")
    parts = []
    if "Iron Ore" in mine_type:
        WIND_CAUTION_MINE = 25
        WIND_STOP_MINE = 28
    else:
        WIND_CAUTION_MINE = WIND_CAUTION
        WIND_STOP_MINE = WIND_STOP
    if rain == 0 and pop < 25:
        if "Coal" in mine_type:
            parts.append(f"{dlabel} is forecast to be completely dry. All open-cast operations including OB removal, drilling, blasting, and coal dispatch can proceed normally.")
        elif "Underground" in mine_type:
            parts.append(f"{dlabel} is forecast to be completely dry. Incline drivage and shaft sinking activities can proceed under standard protocols.")
        else:
            parts.append(f"{dlabel} is forecast to be completely dry. All open-cast operations including OB removal, drilling, blasting, and ore dispatch can proceed normally.")
    elif rain == 0 and pop >= 25:
        parts.append(f"{dlabel} is likely dry with a {pop}% chance of isolated showers. Schedule blasting in morning hours and monitor sky conditions before afternoon shift.")
    elif heavy_sl:
        hw = heavy_sl[0]["label"]; hp = heavy_sl[0]["pop"]
        parts.append(f"Heavy rainfall totaling {rain} mm is expected {dlabel.lower()}, peaking around {hw} ({hp}% probability).<br>")
        if pop < 50:
            parts.append(f"Despite moderate probability ({pop}%), rainfall intensity is high. Prepare drainage but consider proceeding with morning operations before {hw.split('–')[0].strip()}.")
        if "Coal" in mine_type:
            parts.append("Pit drainage must be inspected before morning shift. Bench and haul road surfaces will be severely impacted — mandatory post-rain ground assessment required before resuming OB removal, excavator, and dozer work. Deploy coal stockpile covers.")
        elif "Underground" in mine_type:
            parts.append("Incline mouth and shaft collar drainage must be inspected before morning shift. Verify dewatering pump capacity and berm integrity before resuming drilling, blasting, or hoisting operations.")
        else:
            parts.append("Pit drainage must be inspected before morning shift. Bench and haul road surfaces will be severely impacted — mandatory post-rain ground assessment required before resuming OB removal, excavator, and dozer work. Deploy ore stockpile covers.")
    elif mod_sl:
        first = rain_sl[0]["label"]; last = rain_sl[-1]["label"]; fp = rain_sl[0]["pop"]; lp = rain_sl[-1]["pop"]
        first_start = first.split('–')[0].strip() if '–' in first else first.split('-')[0].strip()
        last_end = last.split('–')[1].strip() if '–' in last else last.split('-')[1].strip()
        time_range = f"{first_start} – {last_end}"
        if pop >= 15:
            parts.append(f"Moderate rainfall of {rain} mm is forecast from {time_range} with probability ranging {fp}–{lp}%.<br>")
        else:
            parts.append(f"Moderate rainfall of {rain} mm is forecast from {time_range}.<br>")
        if pop < 15:
            parts.append("Intermittent showers expected. Surface impact minimal — operations can continue with standard wet-weather protocols.")
        elif pop < 40:
            parts.append(f"Lower probability ({pop}%) suggests showers may be scattered. Prioritize operations in drier morning window. Keep rain gear and drainage pumps on standby.")
        elif pop > 70:
            parts.append(f"High confidence ({pop}% probability) indicates that rain will occur. Shift high-precision blasting to alternate day if possible.")
        if "Coal" in mine_type:
            parts.append("Plan coal loading and dispatch in the pre-rain dry window. Allow 1–2 hours post-rain drainage assessment before resuming heavy equipment on active benches. Check blast hole integrity before charging.")
        elif "Underground" in mine_type:
            parts.append("Plan incline drilling/blasting and shaft concreting in the pre-rain dry window. Allow 1–2 hours post-rain assessment of berms, dewatering sumps, and shuttering before resuming.")
        else:
            parts.append("Plan ore loading and dispatch in the pre-rain dry window. Allow 1–2 hours post-rain drainage assessment before resuming heavy equipment on active benches. Check blast hole integrity before charging.")
    elif rain_sl and pop >= 15:
        first = rain_sl[0]["label"]; last = rain_sl[-1]["label"]; fp = rain_sl[0]["pop"]
        first_start = first.split('–')[0].strip() if '–' in first else first.split('-')[0].strip()
        last_end = last.split('–')[1].strip() if '–' in last else last.split('-')[1].strip()
        time_range = f"{first_start} – {last_end}"
        parts.append(f"Light rainfall of {rain} mm is expected {time_range} ({fp}% probability).<br>")
        if pop < 35:
            parts.append(f"Low probability ({pop}%) indicates intermittent drizzle. Surface impact minimal — operations can continue with standard wet-weather protocols.")
        elif pop > 60:
            parts.append(f"Moderate-to-high probability ({pop}%) suggests sustained light rain. Expect haul road surface degradation — deploy grader for maintenance.")
        else:
            parts.append("Operational impact is minimal. Inspect blast area for surface water before charging holes.")
    elif rain >= 0.5 and pop < 15:
        if rain_sl:
            first = rain_sl[0]["label"]; last = rain_sl[-1]["label"]
            first_start = first.split('–')[0].strip() if '–' in first else first.split('-')[0].strip()
            last_end = last.split('–')[1].strip() if '–' in last else last.split('-')[1].strip()
            time_range = f"{first_start} – {last_end}"
            parts.append(f"Light rainfall of {rain} mm is forecast {time_range}.<br>")
        else:
            parts.append(f"Light rainfall of {rain} mm is forecast {dlabel.lower()}.<br>")
        parts.append(f"Low probability ({pop}%) of {rain} mm precipitation. Standard operations with minimal rain gear standby recommended.")
    elif rain > 0 and rain < 0.5 and pop > 0 and pop < 15:
        parts.append(f"Trace precipitation ({rain} mm) may occur {dlabel.lower()} with only {pop}% probability. It may rain briefly or may remain completely dry.<br>")
        parts.append("Operational impact is expected to be negligible. Standard operations may proceed, with minimal rain gear standby as precaution.")
    elif pop >= 15 and not rain_sl:
        parts.append(f"{dlabel} is expected to remain largely dry, though there is a {pop}% chance of brief, isolated drizzle that may not register on gauges.<br>")
        parts.append("No operational impact anticipated. Proceed with standard protocols but monitor sky conditions.")
    if has_l:
        lt = [s["label"] for s in slabs if s["lightning"]]
        parts.append(f"Lightning forecast around {lt[0]}. All blasting, drilling, and work near tall equipment (excavators, conveyors, headgear) must halt 30 minutes before the storm and resume only after 30 clear minutes.")
    if mwind >= WIND_STOP_MINE:
        if "Coal" in mine_type:
            parts.append(f"Wind gusts of {mwind} km/h exceed the DGMS blasting limit ({WIND_STOP} km/h). Defer all blasting. Extend flyrock exclusion zones and confirm with safety officer before resuming.")
        elif "Underground" in mine_type:
            parts.append(f"Wind gusts of {mwind} km/h exceed the safe hoisting/crane limit ({WIND_STOP_MINE} km/h) at the shaft collar. Suspend headgear crane operations and confirm with safety officer before resuming.")
        else:
            parts.append(f"Wind gusts of {mwind} km/h exceed safe blasting limits for iron ore operations ({WIND_STOP_MINE} km/h). Defer all blasting. Extend flyrock exclusion zones and confirm with safety officer before resuming.")
    elif mwind >= WIND_CAUTION_MINE:
        if "Coal" in mine_type:
            parts.append(f"Wind speeds up to {mwind} km/h will increase coal dust dispersal. Activate dust suppression and verify flyrock zones before each blast.")
        elif "Underground" in mine_type:
            parts.append(f"Wind speeds up to {mwind} km/h — reduce hoisting speed and restrict crane slewing near the shaft collar.")
        else:
            parts.append(f"Wind speeds up to {mwind} km/h will increase ore dust dispersal. Activate dust suppression and verify flyrock zones before each blast.")
    if mvis <= VIS_STOP and mvis > 0:
        parts.append(f"Visibility forecast to drop to {mvis} km. Restrict all haul truck and heavy equipment movement. Deploy flagmen at road intersections.")
    elif mvis <= VIS_CAUTION and mvis > 0:
        parts.append(f"Reduced visibility of {mvis} km expected. Enforce lower truck speeds on haul roads and deploy additional spotters on active benches.")
    return " ".join(parts) if parts else f"{dlabel} presents no significant weather concerns. All planned operations may proceed as scheduled."

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
        mm = round(sum(d["rain_mm"] for _, d in seg), 1)
        pops = [d["pop"] for _, d in seg if d["pop"] > 0]
        pop = int(sorted(pops)[int(len(pops)*0.75)] if pops else 0)
        out[h] = (mm, pop)
    return out

def rain_intensity_trend(slabs, min_pop_threshold=40):
    rain_slabs = [s for s in slabs if s["mm"] >= 2.0 and s["pop"] >= min_pop_threshold]
    if len(rain_slabs) < 2:
        return None
    total_rain = sum(s["mm"] for s in rain_slabs)
    if total_rain < 5.0:
        return None
    first_mm = rain_slabs[0]["mm"]
    last_mm = rain_slabs[-1]["mm"]
    first_label = rain_slabs[0]["label"]
    last_label = rain_slabs[-1]["label"]
    first_pop = rain_slabs[0]["pop"]
    last_pop = rain_slabs[-1]["pop"]
    if last_mm > first_mm * 2.0 and last_pop >= min_pop_threshold:
        return f"Precipitation increasing throughout the day — peak intensity expected around {last_label.split('–')[0].strip()} ({last_mm:.1f} mm, {last_pop}% probability). Consider completing critical operations earlier."
    elif first_mm > last_mm * 2.0 and first_pop >= min_pop_threshold:
        return f"Precipitation decreasing throughout the day — conditions improving after {first_label.split('–')[0].strip()}. Operations may resume standard protocols once rainfall subsides."
    else:
        return None

def operational_window_optimizer(slabs, min_vis=5.0, max_wind=30, max_rain=1.0):
    safe_windows = []
    current_start = None
    current_duration = 0
    for s in slabs:
        is_safe = (s["vis"] >= min_vis and s["wind"] <= max_wind and s["mm"] <= max_rain and not s["lightning"])
        if is_safe:
            if current_start is None:
                current_start = s["label"]
                current_duration = 2
            else:
                current_duration += 2
        else:
            if current_start and current_duration >= 4:
                safe_windows.append((current_start, current_duration))
            current_start = None
            current_duration = 0
    if current_start and current_duration >= 4:
        safe_windows.append((current_start, current_duration))
    if not safe_windows:
        return "No continuous 4-hour safe windows identified. Consider shorter work cycles or deferring operations until conditions improve."
    best = safe_windows[0]
    return f"Optimal operational window: {best[0]} ({best[1]} hours continuous). Schedule precision activities (blasting, heavy lifts) during this period."

def equipment_specific_advisories(slabs, hourly=None, mine_type="Coal Open Cast Mine"):
    advisories = []
    max_wind = max((s["wind"] for s in slabs), default=0)
    max_rain = max((s["mm"] for s in slabs), default=0)
    min_vis = min((s["vis"] for s in slabs), default=10)
    has_lightning = any(s["lightning"] for s in slabs)
    if max_wind >= 25:
        advisories.append("HAUL TRUCKS: Crosswind alert at 25+ km/h. Reduce speed to 20 km/h on exposed haul roads. Increase following distance to 100m.")
    if has_lightning:
        advisories.append("EXCAVATORS/DOZERS: Lightning protocol active. Suspend all tall equipment operations. Ground crews must move to safe zones immediately.")
    elif max_rain >= 15:
        advisories.append("EXCAVATORS/DOZERS: Heavy rain expected. Park equipment on firm ground. Avoid bench edges — slope failure risk elevated.")
    elif max_rain >= 5:
        advisories.append("EXCAVATORS/DOZERS: Moderate rain — traction reduced by 30%. Reduce bucket loads, increase spotter visibility.")
    if max_rain >= 10:
        advisories.append("DRILLS: Hole collapse risk HIGH. Suspend drilling in friable formations. Protect charged holes with caps.")
    elif max_rain >= 5:
        advisories.append("DRILLS: Moderate hole collapse risk — monitor hole integrity before charging explosives.")
    if min_vis <= 2:
        advisories.append("DRILLS: Visibility STOP — drilling operations suspended. Dust suppression systems offline.")
    elif min_vis <= 5:
        advisories.append("DRILLS: Reduced visibility — deploy secondary spotters, use radio contact every 5 minutes.")
    if has_lightning:
        advisories.append("BLASTING: PROHIBITED — Lightning within 10km. 30-minute wait rule after last strike.")
    elif max_wind >= 32:
        advisories.append(f"BLASTING: Wind STOP ({max_wind} km/h) — exceeds DGMS flyrock limit. Defer all blasting operations.")
    elif max_rain >= 5:
        advisories.append("BLASTING: Rain protocol — check hole water levels. Use water-resistant explosives. Post-rain: 2-hour ground assessment.")
    return advisories if advisories else ["All equipment can operate under standard protocols."]

def underground_advisories(slabs, hourly=None, mine_type="Underground Mine (Incline/Shaft — Greenfield)"):
    advisories = []
    max_wind = max((s["wind"] for s in slabs), default=0)
    max_rain = max((s["mm"] for s in slabs), default=0)
    min_vis = min((s["vis"] for s in slabs), default=10)
    has_lightning = any(s["lightning"] for s in slabs)
    if has_lightning:
        advisories.append("INCLINE — JUMBO DRILL: Lightning risk active. De-energize and withdraw jumbo drill rigs from the incline mouth/surface pad. Ground crew to shelter — electrical drill gear is a high lightning-strike risk.")
    elif max_rain >= 15:
        advisories.append("INCLINE — DRILLING/BLASTING: Heavy rain forecast. Suspend collar drilling and blasting at the incline mouth — portal flooding likely. Re-inspect berms and diversion drains before resuming.")
    elif max_rain >= 5:
        advisories.append("INCLINE — DRILLING/BLASTING: Moderate rain expected. Cover explosive magazines and charged holes near the portal with waterproof sheeting; delay blasting until drainage is confirmed clear.")
    if max_rain >= 10:
        advisories.append("INCLINE — BERM & DEWATERING: Rain volume threatens incline-mouth berm integrity. Inspect berm height/compaction and activate standby dewatering pumps (primary + DG-backed backup) — confirm sump capacity ahead of inflow.")
    elif max_rain >= 5:
        advisories.append("INCLINE — DEWATERING PUMPS: Monitor sump levels every 2 hours; keep dewatering pumps on standby power in case of grid interruption during rain.")
    if max_wind >= 30:
        advisories.append("INCLINE — JUMBO DRILL MAST: Wind exceeds 30 km/h — retract/lower jumbo drill masts and secure surface stockpiles near the portal.")
    if has_lightning:
        advisories.append("SHAFT — MANPOWER PROTECTION: Lightning detected. Evacuate the shaft collar, halt headgear/hoist operations, and move all personnel to designated shelters. Resume only after 30 clear minutes.")
    elif max_wind >= 32:
        advisories.append("SHAFT — HOISTING/CRANE: Wind gusts exceed the safe hoisting limit (32 km/h). Suspend headgear crane and kibble/hoist operations at the shaft collar until winds subside.")
    elif max_wind >= 25:
        advisories.append("SHAFT — HOISTING/CRANE: Elevated wind (25+ km/h) — reduce hoisting speed and restrict crane slewing near the shaft collar.")
    if max_rain >= 10:
        advisories.append("SHAFT — SHUTTERING/CONCRETING: Heavy rain will compromise fresh concrete curing and shutter alignment at the shaft collar. Cover open shuttering, halt concrete pours, and reschedule curing-sensitive work.")
    elif max_rain >= 5:
        advisories.append("SHAFT — CONCRETING: Moderate rain — protect uncured concrete pours with tarpaulins; delay fresh pours until the rain window passes.")
    if min_vis <= 2:
        advisories.append("SHAFT — SURFACE OPS: Visibility STOP at shaft top — suspend material lowering/hoisting; deploy signalers with radio contact.")
    return advisories if advisories else ["Incline and shaft development work can proceed under standard protocols — no significant weather constraints identified."]

def dust_risk_index(slabs, hourly):
    if not slabs:
        return None
    avg_wind = sum(s["wind"] for s in slabs) / len(slabs)
    avg_hum = sum(s["hum"] for s in slabs) / len(slabs)
    total_rain = sum(s["mm"] for s in slabs)
    if avg_wind >= 25 and avg_hum < 40 and total_rain < 1:
        return f"HIGH DUST RISK: Wind {avg_wind:.0f} km/h with low humidity {avg_hum:.0f}% and no precipitation. Deploy water bowsers every 2 hours. Mandatory dust masks in exposed areas."
    elif avg_wind >= 20 and avg_hum < 50 and total_rain < 2:
        return f"MODERATE DUST RISK: Conditions favor dust dispersal. Increase water suppression on haul roads."
    elif total_rain >= 5 or avg_hum > 70:
        return f"LOW DUST RISK: Precipitation and humidity suppressing dust. Standard protocols sufficient."
    return None

def fog_dew_prediction(hourly, target_day):
    today = now_ist().date()
    if target_day != today:
        return None
    overnight = [(dt, d) for dt, d in hourly if 20 <= dt.hour <= 23 or 0 <= dt.hour <= 6]
    if not overnight:
        return None
    avg_hum = sum(d["humidity"] for _, d in overnight) / len(overnight)
    min_temp = min(d["temp"] for _, d in overnight)
    if avg_hum > 85 and min_temp < 15:
        return f"FOG ALERT: High overnight humidity ({avg_hum:.0f}%) with low temperature ({min_temp:.1f}°C) indicates dense fog likely. Reduce haul truck speed by 50%. Activate fog lights."
    elif avg_hum > 75 and min_temp < 18:
        return f"HEAVY DEW: Moderate fog or dew expected. Wet benches will reduce traction. Delay drilling until visibility improves."
    return None

def soil_moisture_forecast(slabs, past_rain_24h=0):
    total_rain = sum(s["mm"] for s in slabs)
    cumulative = past_rain_24h + total_rain
    if cumulative >= 25:
        return f"SATURATED GROUND: {cumulative:.1f}mm cumulative rain. Haul roads will likely be muddy. Use low gear, increase following distance. Slope stability concerns on high benches."
    elif cumulative >= 15:
        return f"SOFT GROUND: {cumulative:.1f}mm rain accumulation. Expect rutting on haul roads. Deploy motor grader. Reduced productivity 15-20%."
    elif cumulative >= 5:
        return f"DAMP GROUND: {cumulative:.1f}mm total moisture. Surface firm but monitor for soft spots. Standard precautions apply."
    return None

def worker_safety_index(hourly, slabs):
    temps = [d["temp"] for _, d in hourly]
    max_temp = max(temps) if temps else 35
    min_temp = min(temps) if temps else 25
    if max_temp >= 40:
        return f"HIGH HEAT ALERT: Maximum temperature {max_temp:.1f}°C. Ensure workers stay hydrated and rest shelters are available. Watch for heat exhaustion symptoms."
    elif max_temp >= 38:
        return f"HIGH HEAT: {max_temp:.1f}°C peak temperature. Ensure workers stay hydrated and rest shelters are available."
    elif max_temp <= 10:
        return f"COLD CONDITIONS: Low temperature {min_temp:.1f}°C. Hypothermia risk for night shift. Provide warming shelters."
    avg_hum = sum(s["hum"] for s in slabs) / len(slabs) if slabs else 50
    heat_index = max_temp + (avg_hum * 0.1)
    if heat_index >= 45:
        return f"DANGEROUS HEAT INDEX: Apparent temperature {heat_index:.1f}°C. Suspend non-essential outdoor work during peak heat hours."
    return None

def render_mc(mc):
    if not mc:
        return
    max_dbz = max((m.get("dbz", 0) for m in mc), default=1) or 1
    bars = ""
    for m in mc:
        dbz = m.get("dbz", 0)
        try:
            ft = datetime.fromisoformat(m.get("forecast_time", ""))
            t = ft.strftime("%H:%M")
        except Exception:
            t = ""
        c = ("#F1F5F9" if dbz == 0 or not m.get("is_precip") else "#BFDBFE" if dbz < 15 else "#3B82F6" if dbz < 25 else "#1D4ED8" if dbz < 35 else "#D97706" if dbz < 45 else "#DC2626")
        ht = max(4, int(28 * dbz / max_dbz))
        lightning = float(m.get("lightning_rate", 0) or 0) > 0
        title = f"{t}{' • lightning' if lightning else ''}"
        bars += f'<span style="display:inline-block;width:4px;height:{ht}px;background:{c};border-radius:1px;margin-right:1px;vertical-align:bottom;" title="{title}"></span>'
    lbls = ""
    for m in mc:
        if int(m.get("minute", 0) or 0) % 30 == 0:
            try:
                ft = datetime.fromisoformat(m.get("forecast_time", ""))
                t = ft.strftime("%H:%M")
            except Exception:
                t = ""
            lbls += f'<span style="display:inline-block;width:120px;font-size:0.65rem;color:#94A3B8;">{t}</span>'
    st.markdown(f"""<div class="wim-mc">
        <div class="wim-mc-title">Minute-by-Minute Precipitation — Active AccuWeather Nowcast</div>
        <div style="white-space:nowrap;display:flex;align-items:flex-end;gap:0;">{bars}</div>
        <div style="white-space:nowrap;margin-top:6px;">{lbls}</div>
        <div style="margin-top:8px;font-size:0.65rem;color:#94A3B8;">MinuteCast is refreshed per mine at most once every 6 hours to stay within the 50-request rolling-24h trial limit. Cached data is used only inside its original ~2-hour forecast horizon.</div>
        </div>""", unsafe_allow_html=True)


def render_hourly_graph(hourly, target_day):
    if not hourly:
        return
    today = now_ist().date()
    ist_now_h = now_ist().replace(minute=0, second=0, microsecond=0)
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
        if light or mm >= RAIN_HEAVY or vis <= VIS_STOP or wind >= WIND_STOP:
            status = "stop"; status_color = "#DC2626"; status_bg = "#FFF1F2"
        elif mm >= RAIN_MOD or vis <= VIS_CAUTION or wind >= WIND_CAUTION:
            status = "caution"; status_color = "#D97706"; status_bg = "#FFF7ED"
        else:
            status = "safe"; status_color = "#16A34A"; status_bg = "#F0FDF4"
        data.append({"hour": hk.strftime("%H:%M"), "hour_12": hk.strftime("%I %p").lstrip("0"), "temp": temp, "rain": mm, "pop": pop,
                     "status": status, "status_color": status_color, "status_bg": status_bg, "wind": wind, "vis": vis})
    if not data:
        return
    max_rain = max(d["rain"] for d in data) or 1
    max_temp = max(d["temp"] for d in data)
    min_temp = min(d["temp"] for d in data)
    temp_range = max_temp - min_temp or 1
    bars = ""
    for d in data:
        rain_height = min((d["rain"] / max_rain) * 60, 60) if max_rain > 0 else 0
        temp_height = ((d["temp"] - min_temp) / temp_range) * 40 if temp_range > 0 else 20
        status_dot = '<div style="width:8px;height:8px;border-radius:50%;background:' + d["status_color"] + ';margin:4px auto;"></div>'
        hour_label = d["hour_12"].replace(" ","")
        bars += '<div style="flex:1;min-width:36px;display:flex;flex-direction:column;align-items:center;gap:4px;padding:8px 2px;border-radius:6px;background:' + d["status_bg"] + ';margin:0 2px;position:relative;" title="' + d["hour"] + ' - Temp: ' + str(d["temp"]) + '°C, Rain: ' + str(d["rain"]) + 'mm, Status: ' + d["status"].upper() + '">' + \
            '<div style="font-size:0.65rem;font-weight:600;color:#64748B;">' + hour_label + '</div>' + \
            '<div style="display:flex;align-items:flex-end;gap:2px;height:70px;">' + \
                '<div style="width:14px;background:linear-gradient(180deg,#0B74B0,#60A5FA);border-radius:3px 3px 0 0;height:' + str(rain_height) + 'px;min-height:2px;"></div>' + \
                '<div style="width:14px;background:linear-gradient(180deg,#F59E0B,#FCD34D);border-radius:3px 3px 0 0;height:' + str(temp_height) + 'px;min-height:2px;"></div>' + \
            '</div>' + \
            status_dot + \
            '<div style="font-size:0.6rem;font-weight:700;color:' + d["status_color"] + ';text-transform:uppercase;">' + d["status"][:1] + '</div>' + \
        '</div>'
    legend = '<div style="display:flex;gap:20px;flex-wrap:wrap;margin-top:16px;padding-top:12px;border-top:1px solid #E2E8F0;">' + \
        '<div style="display:flex;align-items:center;gap:6px;"><div style="width:14px;height:14px;background:linear-gradient(180deg,#0B74B0,#60A5FA);border-radius:3px;"></div><span style="font-size:0.75rem;color:#475569;">Precipitation (mm)</span></div>' + \
        '<div style="display:flex;align-items:center;gap:6px;"><div style="width:14px;height:14px;background:linear-gradient(180deg,#F59E0B,#FCD34D);border-radius:3px;"></div><span style="font-size:0.75rem;color:#475569;">Temperature (°C)</span></div>' + \
        '<div style="display:flex;align-items:center;gap:6px;"><div style="width:8px;height:8px;border-radius:50%;background:#16A34A;"></div><span style="font-size:0.75rem;color:#475569;">Safe Operations</span></div>' + \
        '<div style="display:flex;align-items:center;gap:6px;"><div style="width:8px;height:8px;border-radius:50%;background:#D97706;"></div><span style="font-size:0.75rem;color:#475569;">Caution</span></div>' + \
        '<div style="display:flex;align-items:center;gap:6px;"><div style="width:8px;height:8px;border-radius:50%;background:#DC2626;"></div><span style="font-size:0.75rem;color:#475569;">Stop Operations</span></div>' + \
    '</div>'
    st.markdown(f'<div style="overflow-x:auto;"><div style="display:flex;min-width:100%;padding:4px;">{bars}</div></div>{legend}', unsafe_allow_html=True)

def render_weekly(by_day, days, site_type="Coal Open Cast Mine"):
    today = now_ist().date()
    cols = st.columns(min(days, 7))
    for i in range(min(days, 7)):
        d = today + timedelta(days=i)
        lbl = "Today" if i == 0 else ("Tomorrow" if i == 1 else d.strftime("%a"))
        if d not in by_day:
            cols[i].markdown(f'<div class="wim-day"><div class="wim-day-label">{lbl}</div><div class="wim-day-date">{d.strftime("%d %b")}</div><div style="color:#94A3B8;font-size:0.75rem;margin-top:8px;">No data</div></div>', unsafe_allow_html=True)
            continue
        s = day_summary(by_day[d], site_type, target_day=d); sl = s["slabs"]
        rain = s["total_rain"]; has_l = any(x["lightning"] for x in sl)
        max_pop = s["max_pop"]
        if rain >= 15 and max_pop >= 25:
            flag, fcss = "Heavy Rain", "flag-heavy"
        elif rain >= 15 and max_pop < 25:
            flag, fcss = "Moderate Risk", "flag-moderate"
        elif rain >= 5 and max_pop >= 35:
            flag, fcss = "Moderate Risk", "flag-moderate"
        elif rain >= 5 and max_pop < 35:
            flag, fcss = "Light Rain", "flag-light"
        elif rain >= 1.5 and max_pop >= 45:
            flag, fcss = "Light Rain", "flag-light"
        elif rain >= 1.5 and max_pop < 45:
            flag, fcss = "Drizzle", "flag-drizzle"
        elif rain >= 0.5:
            flag, fcss = "Drizzle", "flag-drizzle"
        elif has_l:
            flag, fcss = "Lightning Risk", "flag-lightning"
        else:
            flag, fcss = "Clear", "flag-clear"
        day_css = "wim-day wim-day-active" if i == 0 else "wim-day"
        cols[i].markdown(f"""<div class="{day_css}">
            <div class="wim-day-label">{lbl}</div>
            <div class="wim-day-date">{d.strftime('%d %b')}</div>
            <div class="wim-day-cond">{s['condition']}</div>
            <div class="wim-day-rain">{f"{rain} mm" if rain >= 0.5 else "0.0 mm"}{f" · {s['max_pop']}%" if rain >= 0.5 else ""}</div>
            <div class="wim-day-temp">{s['max_temp']}° / {s['min_temp']}°C</div>
            <span class="wim-day-flag {fcss}">{flag}</span>
        </div>""", unsafe_allow_html=True)

def render_sidebar():
    sites = load_sites()
    names = [s["name"] for s in sites]
    _SH = 'font-size:0.7rem;font-weight:800;letter-spacing:0.1em;text-transform:uppercase;color:#94A3B8;'
    _HR = '<hr style="border:none;border-top:1px solid #E2E8F0;margin:14px 0;">'
    st.markdown(f'<p style="{_SH}margin:0 0 8px 0;">Mine Sites</p>', unsafe_allow_html=True)
    for site in sites:
        is_active = site["name"] == st.session_state.active_site
        label = f"{'●' if is_active else '○'} {site['name']}  —  {site['lat']:.3f}°N, {site['lon']:.3f}°E"
        btn_type = "primary" if is_active else "secondary"
        if st.button(label, key=f"site_sel_{site['name']}", use_container_width=True, type=btn_type):
            st.session_state.active_site = site["name"]
            st.rerun()
    st.markdown(_HR, unsafe_allow_html=True)
    st.markdown(f'<p style="{_SH}margin:0 0 6px 0;">Forecast Range</p>', unsafe_allow_html=True)
    days = st.slider("Forecast days", 2, 7, 7, label_visibility="collapsed")
    st.markdown(_HR, unsafe_allow_html=True)
    active_obj = next((s for s in sites if s["name"] == st.session_state.active_site), None)
    with st.expander("✏️  Edit selected site", expanded=False):
        if active_obj and active_obj.get("builtin"):
            st.info(f"{active_obj['name']} is a built-in site and cannot be edited.")
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
    with st.expander("＋  Add new site", expanded=False):
        with st.form("site_add_form"):
            nm = st.text_input("Site name", placeholder="e.g. Gorbi Mine")
            ac1, ac2 = st.columns(2)
            lt = ac1.number_input("Lat", value=0.0, format="%.6f")
            ln = ac2.number_input("Lon", value=0.0, format="%.6f")
            pw = st.text_input("Admin password", type="password", placeholder="Password")
            if st.form_submit_button("Add site", use_container_width=True):
                if pw != ADMIN_PASSWORD:
                    st.error("Incorrect password.")
                elif not nm.strip():
                    st.error("Name required.")
                elif abs(lt) < 0.001 and abs(ln) < 0.001:
                    st.error("Enter valid coordinates.")
                else:
                    save_site(nm.strip(), lt, ln)
                    st.session_state.active_site = nm.strip()
                    st.cache_data.clear()
                    st.success(f"'{nm}' added.")
                    st.rerun()
    custom = [s for s in sites if not s.get("builtin")]
    if custom:
        with st.expander("🗑️  Remove site", expanded=False):
            with st.form("site_del_form"):
                td = st.selectbox("Site to remove", [s["name"] for s in custom])
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
    with st.expander("⭐  Set default site on load", expanded=False):
        with st.form("set_default_form"):
            saved = get_default_site()
            idx = names.index(saved) if saved in names else 0
            pick = st.selectbox("Default", names, index=idx, label_visibility="collapsed")
            dpwd2 = st.text_input("Admin password", type="password", key="def_pwd")
            if st.form_submit_button("Set as default", use_container_width=True):
                if dpwd2 != ADMIN_PASSWORD:
                    st.error("Incorrect password.")
                else:
                    set_default_site(pick)
                    st.success(f"'{pick}' is now the default.")
    st.markdown(_HR, unsafe_allow_html=True)
    st.caption(f"Font {'ok' if _FONT_LOADED else 'missing'} · Logo {'ok' if _LOGO_LOADED else 'missing'}")
    return days

days = 7
st.markdown(f"""<div class="wim-nav">
    <div class="wim-nav-left">
        {LOGO_HTML}
        <div class="wim-nav-sep"></div>
        <div class="wim-nav-text">
            <div class="wim-nav-title">Adani Natural Resources</div>
            <div class="wim-nav-sub">WIM — Weather Intelligence Mining</div>
        </div>
    </div>
    <div id="wim-clock" style="font-size:0.75rem;color:#94A3B8;">{now_ist().strftime('%d %b %Y')}</div>
</div><div class="wim-nav-spacer"></div>""", unsafe_allow_html=True)
components.html("""
<style>body{margin:0;padding:0;overflow:hidden;} #clk{position:fixed;top:22px;right:2.5rem;font-size:0.75rem;color:#94A3B8;font-family:'Helvetica Neue',Arial,sans-serif;z-index:99999;}</style>
<div id="clk"></div>
<script>
function tick(){
  var d=new Date(), h=d.getHours(), ampm=h>=12?'PM':'AM', h12=h%12||12;
  var mo=['January','February','March','April','May','June','July','August','September','October','November','December'];
  var txt=d.getDate()+' '+mo[d.getMonth()]+' '+d.getFullYear()+', '+String(h12).padStart(2,'0')+':'+String(d.getMinutes()).padStart(2,'0')+':'+String(d.getSeconds()).padStart(2,'0')+' '+ampm+' IST';
  document.getElementById('clk').textContent=txt;
  try{ var el=window.parent.document.getElementById('wim-clock'); if(el) el.textContent=txt; }catch(e){}
}
tick(); setInterval(tick,1000);
</script>
""", height=0)
st.markdown('<div class="wim-page">', unsafe_allow_html=True)
components.html("""
<script>
try{
  const key='wim_active_site';
  const stored=window.localStorage.getItem(key);
  if(stored){
    const params=new URLSearchParams(window.location.search);
    if(!params.get('site')){
      params.set('site', stored);
      const newUrl=window.location.pathname+'?'+params.toString();
      window.location.replace(newUrl);
    }
  }
}catch(e){}
</script>
""", height=0)
site_names = [s["name"] for s in ALL_SITES]
qp = st.query_params if hasattr(st, "query_params") else {}
site_param = qp.get("site") if qp else None
options = ["Select site"] + site_names
default_idx = site_names.index(site_param) + 1 if site_param in site_names else 0
col_left, col_picker = st.columns([5, 1])
with col_picker:
    pick = st.selectbox("Select site", options, index=default_idx, label_visibility="collapsed", key="site_picker")
if pick == "Select site":
    st.markdown('<div class="wim-alert wim-alert-none"><div class="wim-alert-label">Select site</div>Please choose which mine you want to view predictions for.</div>', unsafe_allow_html=True)
    st.stop()
if not hasattr(st, "session_state") or st.session_state is None:
    st.markdown('<div class="wim-alert wim-alert-none"><div class="wim-alert-label">Error</div>Please run with: streamlit run WFS.py</div>', unsafe_allow_html=True)
    st.stop()
st.session_state.active_site = pick
components.html(f"""
<script>
try{{ window.localStorage.setItem('wim_active_site', {json.dumps(pick)}); }}catch(e){{}}
</script>
""", height=0)
site = next((s for s in ALL_SITES if s["name"] == st.session_state.active_site), None)
if not site:
    st.markdown('<div class="wim-alert wim-alert-none"><div class="wim-alert-label">Site not found</div>Please select another site.</div>', unsafe_allow_html=True)
    st.stop()
with col_left:
    st.markdown(f'<div class="wim-site-row"><div class="wim-site-name">{site["name"]}</div><div class="wim-site-coord">{site["lat"]}°N, {site["lon"]}°E</div></div>', unsafe_allow_html=True)
loading = st.empty()
loading.caption(f"Loading latest forecast for {site['name']} from Supabase…")
by_day, mc_data, src_status, imd_advisory = load_background_forecast(
    site["id"], days
)
loading.empty()
if by_day:
    with st.expander("Data source health", expanded=False):
        status_cols = st.columns(2)
        for idx, (source_name, source_state) in enumerate(src_status.items()):
            ok_state = str(source_state).startswith("ok")
            label = ("✓ " + ("online" if source_state == "ok" else source_state)) if ok_state else source_state
            status_cols[idx % 2].caption(f"{source_name}: {label}")
        st.caption("Provider APIs are fetched by the background worker. This dashboard only reads the latest Supabase snapshot.")
# A mine-operations forecast should not look equally certain when only one
# weather provider is actually contributing. Surface this explicitly.
live_weather_sources = [
    s for s, v in src_status.items()
    if s not in {"IMD", "Supabase cache", "Weatherstack", "Background ingestion"} and str(v).startswith("ok")
]
if by_day and len(live_weather_sources) < 2:
    st.markdown(
        '<div class="wim-alert wim-alert-moderate"><div class="wim-alert-label">Reduced forecast confidence</div>'
        'Only one live numerical forecast source is currently contributing. WIM can still show planning guidance, but do not use it as the sole real-time stop-work/lightning safety signal until additional providers or mine-site observations are online.</div>',
        unsafe_allow_html=True,
    )

imd_warning, imd_color = _imd_today_warning(imd_advisory)
if imd_warning and imd_warning.lower() not in {"nil", "no warning", "no weather"}:
    wl = imd_warning.lower()
    severe = any(k in wl for k in ["thunder", "lightning", "very heavy", "extremely heavy", "hail", "squall"])
    css = "wim-alert-high" if severe else "wim-alert-moderate"
    st.markdown(
        f'<div class="wim-alert {css}"><div class="wim-alert-label">Official IMD Advisory — {site.get("imd_subdivision", "")}</div>{imd_warning}</div>',
        unsafe_allow_html=True,
    )

if not by_day:
    ok = [s for s, v in src_status.items() if str(v).startswith("ok")]
    fail = {s: v for s, v in src_status.items() if v != "ok"}
    hint = ""
    if any("401" in str(v) or "Unauthorized" in str(v) for v in fail.values()):
        hint = " One or more providers rejected authentication/quota. Check the Data source health details and provider subscription status."
    if any("timeout" in str(v).lower() for v in fail.values()):
        hint += " Open-Meteo timeout — network issue. Try Retry."
    msg = f"Partial failure. Online: {', '.join(ok)}." if ok else "All sources unreachable."
    diag = "<br>".join(f"• {s}: {'Quota exhausted' if '401' in v else ('Timeout' if 'timeout' in v.lower() else ('No key' if 'no key' in v else v))}" for s, v in fail.items())
    st.markdown(f'<div class="wim-alert wim-alert-high"><div class="wim-alert-label">Data Unavailable</div>{msg}{hint}<br>{diag}</div>', unsafe_allow_html=True)
    if st.button("Retry"):
        st.cache_data.clear()
        st.rerun()
    st.stop()

today = now_ist().date()
st.markdown('<div class="wim-section">7-Day Outlook</div>', unsafe_allow_html=True)
render_weekly(by_day, days, site.get("type", "Coal Open Cast Mine"))
st.markdown('<hr class="wim-hr">', unsafe_allow_html=True)

st.markdown('<div class="wim-section">Day-wise Weather Conditions</div>', unsafe_allow_html=True)
tab_lbls = ["Today" if i == 0 else ("Tomorrow" if i == 1 else (today + timedelta(days=i)).strftime("%a, %d %b")) for i in range(min(days, 7))]
tab_days = [today + timedelta(days=i) for i in range(min(days, 7))]
mine_type = site.get("type", "Coal Open Cast Mine")
for tab, tday in zip(st.tabs(tab_lbls), tab_days):
    with tab:
        dh = by_day.get(tday, [])
        if not dh:
            st.markdown('<div class="wim-alert wim-alert-none">No forecast data for this day.</div>', unsafe_allow_html=True)
            continue
        ds = day_summary(dh, mine_type, target_day=tday)
        sl = ds["slabs"]
        rain_t = ds["total_rain"]
        has_l = any(s["lightning"] for s in sl)
        hiw = ds["avg_wind"] >= WIND_CAUTION
        critical_html = ""
        safety = worker_safety_index(dh, sl)
        if safety:
            is_critical_heat = "DANGEROUS HEAT INDEX" in safety or "HIGH HEAT ALERT" in safety or "HIGH HEAT" in safety
            if is_critical_heat:
                critical_html += f'<div style="background:#FEE2E2;border:1px solid #DC2626;border-radius:6px;padding:10px 14px;margin-bottom:10px;font-size:0.85rem;color:#DC2626;font-weight:600;"><strong>CRITICAL ALERT:</strong> {safety}</div>'
        if has_l:
            lightning_msg = "Lightning detected in forecast. All blasting, drilling, and work near tall equipment must halt 30 minutes before the storm and resume only after 30 clear minutes."
            critical_html += f'<div style="background:#F3E8FF;border:1px solid #7C3AED;border-radius:6px;padding:10px 14px;margin-bottom:10px;font-size:0.85rem;color:#7C3AED;font-weight:600;"><strong>LIGHTNING WARNING:</strong> {lightning_msg}</div>'
        very_heavy_rain = rain_t >= 15 and ds["max_pop"] >= 50
        if very_heavy_rain:
            rain_msg = f"Very heavy rainfall of {rain_t} mm forecast with {ds['max_pop']}% probability. Operations will be severely impacted."
            critical_html += f'<div style="background:#FFF7ED;border:1px solid #EA580C;border-radius:6px;padding:10px 14px;margin-bottom:10px;font-size:0.85rem;color:#EA580C;font-weight:600;"><strong>SEVERE RAIN ALERT:</strong> {rain_msg}</div>'
        if critical_html:
            st.markdown(critical_html, unsafe_allow_html=True)
        rec = smart_rec(ds, sl, tday, mine_type)
        a_css = "wim-alert-high" if (rain_t >= 15 or has_l) else ("wim-alert-moderate" if (rain_t >= 5 or hiw) else "wim-alert-low")
        st.markdown(f'<div class="wim-alert {a_css}"><div class="wim-alert-label">Forecast Advisory</div>{rec}</div>', unsafe_allow_html=True)
        significant_weather = (ds["max_pop"] >= 50 or rain_t >= 5 or ds["avg_wind"] >= WIND_CAUTION or has_l or ds["min_vis"] <= VIS_CAUTION)
        insights_html = ""
        if significant_weather:
            trend = rain_intensity_trend(sl)
            if trend:
                insights_html += f'<div style="background:#F8FAFC;border:1px solid #E2E8F0;border-radius:8px;padding:12px 16px;margin-bottom:12px;font-size:0.85rem;color:#334155;">{trend}</div>'
        if significant_weather:
            window = operational_window_optimizer(sl, min_vis=VIS_CAUTION, max_wind=WIND_CAUTION, max_rain=RAIN_MOD)
            if "No continuous 4-hour safe windows" in window or "shorter work cycles" in window:
                insights_html += f'<div style="background:#FEF3C7;border:1px solid #FCD34D;border-radius:8px;padding:12px 16px;margin-bottom:12px;font-size:0.85rem;color:#92400E;">{window}</div>'
        if "Underground" in mine_type:
            equip_advisories = underground_advisories(sl, dh, mine_type)
            no_action_marker = "no significant weather constraints"
        else:
            equip_advisories = equipment_specific_advisories(sl, dh, mine_type)
            no_action_marker = "All equipment can operate"
        real_advisories = [adv for adv in equip_advisories if no_action_marker not in adv]
        if real_advisories:
            insights_html += '<div style="background:#FFFBEB;border:1px solid #FCD34D;border-radius:8px;padding:12px 16px;font-size:0.82rem;color:#92400E;margin-bottom:12px;">'
            insights_html += f'<div style="font-weight:700;margin-bottom:8px;color:#B45309;">{"Incline &amp; Shaft Advisories" if "Underground" in mine_type else "Equipment Advisories"}</div>'
            for adv in real_advisories:
                insights_html += f'<div style="margin:6px 0;padding-left:8px;border-left:3px solid #F59E0B;">{adv}</div>'
            insights_html += '</div>'
        dust_risk = dust_risk_index(sl, dh)
        if dust_risk and ("HIGH" in dust_risk or "MODERATE" in dust_risk):
            insights_html += f'<div style="background:#FEF3C7;border:1px solid #FCD34D;border-radius:8px;padding:10px 14px;margin-bottom:10px;font-size:0.8rem;color:#92400E;">{dust_risk}</div>'
        fog_dew = fog_dew_prediction(dh, tday)
        if fog_dew:
            insights_html += f'<div style="background:#E0F2FE;border:1px solid #7DD3FC;border-radius:8px;padding:10px 14px;margin-bottom:10px;font-size:0.8rem;color:#0369A1;">{fog_dew}</div>'
        soil = soil_moisture_forecast(sl)
        if soil and ("SATURATED" in soil or "SOFT" in soil):
            insights_html += f'<div style="background:#F3E8FF;border:1px solid #D8B4FE;border-radius:8px;padding:10px 14px;margin-bottom:10px;font-size:0.8rem;color:#7E22CE;">{soil}</div>'
        if insights_html:
            st.markdown(insights_html, unsafe_allow_html=True)
        m_cols = st.columns(7)
        cloud_val = f"{int(ds['cloud'])}%" if ds.get("cloud") else "—"
        show_rain_prob = rain_t > 0 and ds["max_pop"] >= 15
        for col, lbl, val in zip(m_cols,
                ["Condition", "Max Temp", "Min Temp", "Total Rain", "Rain Prob.", "Wind", "Cloud Cover"],
                [ds["condition"], f"{ds['max_temp']}°C", f"{ds['min_temp']}°C", f"{rain_t} mm",
                 f"{ds['max_pop']}%" if show_rain_prob else "—", f"{ds['avg_wind']} km/h", cloud_val]):
            col.markdown(f'<div class="wim-metric"><div class="wim-metric-label">{lbl}</div><div class="wim-metric-value">{val}</div></div>', unsafe_allow_html=True)
        if tday == today and mc_data:
            st.markdown('<div class="wim-section">Radar — Next 2 Hours (MinuteCast)</div>', unsafe_allow_html=True)
            render_mc(mc_data)
        acc = rain_accum(dh, target_day=tday)
        pfx = "Next" if tday == today else "First"
        has_rain = any(acc[h][0] > 0 for h in (2, 4, 6, 12, 24))
        if has_rain:
            st.markdown(f'<div class="wim-section">Rainfall Accumulation {"" if tday == today else "(From Midnight)"}</div>', unsafe_allow_html=True)
            a_cols = st.columns(5)
            for idx, h in enumerate((2, 4, 6, 12, 24)):
                mm, pop = acc[h]
                css, risk, rc = ("acc-high", "High Risk", "risk-high") if mm >= 15 else (("acc-watch", "Monitor", "risk-watch") if mm >= 5 else ("acc-safe", "Safe", "risk-safe"))
                a_cols[idx].markdown(
                    f'<div class="wim-accum {css}"><div class="wim-accum-period">{pfx} {h}H</div>'
                    f'<div class="wim-accum-val">{mm} mm</div>'
                    f'<div class="wim-accum-pop">{pop}% probability</div>'
                    f'<div class="wim-accum-risk {rc}">{risk}</div></div>', unsafe_allow_html=True)
        st.markdown('<div class="wim-section">2-Hour Precipitation Windows</div>', unsafe_allow_html=True)
        if sl:
            rows = ""
            for s in sl:
                mm = s["mm"]
                rain_td = f'<td class="td-alert">{rain_badge_html(mm)}</td>' if mm >= RAIN_HEAVY else (f'<td class="td-warn">{rain_badge_html(mm)}</td>' if mm >= RAIN_MOD else f'<td>{rain_badge_html(mm)}</td>')
                w = s["wind"]
                wind_td = f'<td class="td-alert">{w} km/h</td>' if w >= WIND_STOP else (f'<td class="td-warn">{w} km/h</td>' if w >= WIND_CAUTION else f'<td>{w} km/h</td>')
                v = s["vis"]
                vis_td = f'<td class="td-alert">{v} km</td>' if v <= VIS_STOP else (f'<td class="td-warn">{v} km</td>' if v <= VIS_CAUTION else f'<td>{v} km</td>')
                if s["lightning"]:
                    lp = int(s.get("lightning_prob", 0) or 0)
                    l_label = f"⚡ {lp}%" if 0 < lp < 100 else "⚡ Alert"
                    l_td = f'<td class="td-alert"><span class="wim-badge b-lightning">{l_label}</span></td>'
                else:
                    l_td = '<td style="color:#94A3B8;">—</td>'
                impact = mining_impact_html(max(mm, s.get("risk_mm", mm)), w, v, s["lightning"])
                rows += f'<tr><td style="font-weight:600;color:#334155;">{s["label"]}</td>{rain_td}<td style="color:#64748B;">{s["pop"] if mm > 0 else 0}%</td>{wind_td}{vis_td}{l_td}<td>{impact}</td></tr>'
            st.markdown('<div style="overflow-x:auto;"><table class="wim-table"><thead><tr><th>Time Window</th><th>Rainfall</th><th>Probability</th><th>Wind Speed</th><th>Visibility</th><th>Lightning</th><th>Mining Impact</th></tr></thead><tbody>' + rows + '</tbody></table></div>', unsafe_allow_html=True)
        st.markdown('<div class="wim-section">Hourly Operations Timeline</div>', unsafe_allow_html=True)
        render_hourly_graph(dh, tday)
online_footer_sources = [
    name for name, state in src_status.items()
    if name not in {"Supabase cache", "Background ingestion"} and str(state).startswith("ok")
]
footer_sources = " · ".join(online_footer_sources) if online_footer_sources else "No live provider snapshot"
st.markdown(f'<p style="font-size:0.68rem;color:#94A3B8;text-align:center;padding:0.5rem 0 2rem;">Background snapshot sources: {footer_sources} • Dashboard reads Supabase only • © Adani Natural Resources {now_ist().year}</p>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)
