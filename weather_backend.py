"""
WIM weather backend — headless provider + fusion layer.
Runs outside Streamlit and writes results to Supabase via weather_worker.py.
"""
import os, json, requests, collections, concurrent.futures, hashlib, math
from datetime import datetime, timedelta
import pytz

# CONFIGURATION
def _secret(name, default=""):
    value = os.getenv(name, default)
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

# Headless backend: site selection belongs to the Streamlit dashboard, not here.
ALL_SITES = load_sites()

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


def fetch_openweather(lat, lon):
    """OpenWeather One Call 4.0 hourly timeline, persisted for 60 minutes."""
    if not OPENWEATHER_KEY:
        return None, "no key"
    if not OPENWEATHER_ONECALL_ENABLED:
        return None, "disabled — set OPENWEATHER_ONECALL_ENABLED=true after activating One Call by Call"
    blocked = provider_backoff_get("openweather")
    if blocked:
        return None, f"backoff — {blocked}"
    cache_key = f"{_coord_cache_key(lat, lon)}|1h-v4"
    cached = db_cache_get("openweather_4_hourly", cache_key)
    if cached is not None:
        return cached, None
    try:
        r = requests.get(
            "https://api.openweathermap.org/data/4.0/onecall/timeline/1h",
            params={"lat": lat, "lon": lon, "units": "metric", "appid": OPENWEATHER_KEY},
            timeout=TIMEOUT,
        )
        if not r.ok:
            err = _provider_http_error(r)
            if r.status_code in (401, 403):
                provider_backoff_set("openweather", "One Call 4.0 is not authorized for this key")
            elif r.status_code == 429:
                provider_backoff_set("openweather", "rate limit reached")
            return None, err
        data = r.json()
        db_cache_set("openweather_4_hourly", cache_key, data, OPENWEATHER_TTL_MIN)
        return data, None
    except Exception as e:
        return None, _safe_error(e)


def fetch_open_meteo(lat, lon, days=7):
    # nearest prevents terrain-optimised snapping from unnecessarily selecting
    # a farther land grid cell for two very close mine coordinates.
    url = (
        f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
        f"&hourly=temperature_2m,precipitation,weather_code,wind_speed_10m,"
        f"precipitation_probability,visibility,relative_humidity_2m,cloud_cover"
        f"&forecast_days={days}&timezone=Asia%2FKolkata&cell_selection=nearest"
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


def fetch_tomorrow_io(lat, lon):
    # Use the same `apikey` query authentication shown by Tomorrow.io's dashboard.
    # Do not Streamlit-cache auth failures: replacing a key must take effect now.
    if not TOMORROWIO_KEY:
        return None, "no key"
    blocked = provider_backoff_get("tomorrow_io")
    if blocked:
        return None, f"backoff — {blocked}"
    cache_key = f"{_coord_cache_key(lat, lon)}|1h"
    cached = db_cache_get("tomorrow_forecast", cache_key)
    if cached is not None:
        return cached, None
    try:
        r = requests.get(
            "https://api.tomorrow.io/v4/weather/forecast",
            params={
                "location": f"{float(lat):.6f},{float(lon):.6f}",
                "units": "metric",
                "timesteps": "1h",
                "apikey": TOMORROWIO_KEY,
            },
            headers={"Accept": "application/json", "Accept-Encoding": "gzip, deflate"},
            timeout=TIMEOUT,
        )
        if not r.ok:
            try:
                body = r.json(); detail = body.get("message") or body.get("error") or body
            except Exception:
                detail = r.text[:300]
            msg = f"HTTP {r.status_code}: {detail}"
            if r.status_code in (401, 403):
                provider_backoff_set("tomorrow_io", "API key invalid/inactive or missing endpoint permission")
            elif r.status_code == 429:
                provider_backoff_set("tomorrow_io", "rate limit reached")
            return None, msg
        data = r.json()
        db_cache_set("tomorrow_forecast", cache_key, data, TOMORROW_TTL_MIN)
        return data, None
    except Exception as e:
        return None, _safe_error(e)


def fetch_weatherstack(lat, lon, days=7):
    if not WEATHERSTACK_ENABLED:
        return None, "disabled — optional provider; set WEATHERSTACK_ENABLED=true only with a suitable plan"
    if not WEATHERSTACK_KEY:
        return None, "no key"
    blocked = provider_backoff_get("weatherstack")
    if blocked:
        return None, f"backoff — {blocked}"
    cache_key = f"{_coord_cache_key(lat, lon)}|days={min(days, 7)}"
    cached = db_cache_get("weatherstack_forecast", cache_key)
    if cached is not None:
        return cached, None

    def _call(endpoint, params):
        r = requests.get(f"https://api.weatherstack.com/{endpoint}", params=params, timeout=TIMEOUT)
        try:
            data = r.json()
        except Exception:
            data = None
        api_err = _weatherstack_error(data) if data is not None else None
        if r.ok and not api_err:
            return data, None
        detail = api_err or (r.text[:300] if r.text else f"HTTP {r.status_code}")
        return None, f"HTTP {r.status_code}: {detail}"

    base = {"access_key": WEATHERSTACK_KEY, "query": f"{lat},{lon}", "units": "m"}
    forecast, forecast_err = _call("forecast", {
        **base,
        "forecast_days": min(days, 7),
        "hourly": 1,
        "interval": 1,
    })
    if forecast is not None:
        forecast["_wim_weatherstack_mode"] = "forecast"
        db_cache_set("weatherstack_forecast", cache_key, forecast, WEATHERSTACK_TTL_MIN)
        return forecast, None

    # Weatherstack forecast data is plan-gated. A free/current-only key is still
    # useful for hyperlocal present conditions, so degrade gracefully instead
    # of marking the entire provider dead.
    current, current_err = _call("current", base)
    if current is not None:
        current["_wim_weatherstack_mode"] = "current_only"
        current["_wim_forecast_error"] = forecast_err
        db_cache_set("weatherstack_forecast", cache_key, current, min(WEATHERSTACK_TTL_MIN, 30))
        return current, None

    combined_err = f"forecast failed ({forecast_err}); current failed ({current_err})"
    if "429" in combined_err:
        provider_backoff_set("weatherstack", "rate limit reached", ttl_minutes=12 * 60)
    return None, combined_err



def _accuweather_headers():
    # Current AccuWeather Developer API uses Bearer authentication.
    return {"Authorization": f"Bearer {ACCUWEATHER_KEY}", "Accept": "application/json"}

def _provider_http_error(response):
    try:
        body = response.json()
        if isinstance(body, dict):
            detail = body.get("message") or body.get("Message") or body.get("error") or body
        else:
            detail = body
    except Exception:
        detail = response.text[:300] if response.text else response.reason
    return f"HTTP {response.status_code}: {detail}"

def _fetch_accuweather_location(lat, lon):
    """Resolve AccuWeather's location key from the selected mine's exact lat/lon."""
    if not ACCUWEATHER_KEY:
        return None, "no key"
    blocked = provider_backoff_get("accuweather_core")
    if blocked:
        return None, f"backoff — {blocked}"
    cache_key = _coord_cache_key(lat, lon)
    cached = db_cache_get("accuweather_location_v2", cache_key)
    if isinstance(cached, dict) and cached.get("key"):
        return cached, None
    try:
        r = requests.get(
            "https://dataservice.accuweather.com/locations/v1/cities/geoposition/search",
            headers=_accuweather_headers(),
            params={"q": f"{float(lat):.6f},{float(lon):.6f}"},
            timeout=TIMEOUT,
        )
        if not r.ok:
            err = _provider_http_error(r)
            if r.status_code == 401:
                provider_backoff_set("accuweather_core", "API key is not authorized; verify the active Core Weather subscription/key")
            elif r.status_code == 403:
                provider_backoff_set("accuweather_core", "Core Weather subscription does not permit location lookup")
            elif r.status_code == 429:
                provider_backoff_set("accuweather_core", "Core Weather rate limit reached")
            return None, err
        data = r.json()
        key = str(data.get("Key") or "").strip()
        if not key:
            return None, "no location key returned"
        gp = data.get("GeoPosition") or {}
        rlat, rlon = gp.get("Latitude"), gp.get("Longitude")
        distance = _haversine_km(lat, lon, rlat, rlon) if rlat is not None and rlon is not None else None
        admin = data.get("AdministrativeArea") or {}
        country = data.get("Country") or {}
        meta = {
            "key": key,
            "requested_lat": float(lat), "requested_lon": float(lon),
            "resolved_lat": rlat, "resolved_lon": rlon,
            "distance_km": round(distance, 2) if distance is not None else None,
            "name": data.get("LocalizedName") or data.get("EnglishName") or "",
            "admin": admin.get("LocalizedName") or admin.get("EnglishName") or "",
            "country": country.get("LocalizedName") or country.get("EnglishName") or "",
        }
        db_cache_set("accuweather_location_v2", cache_key, meta, ACCUWEATHER_LOCATION_TTL_MIN)
        return meta, None
    except Exception as e:
        return None, _safe_error(e)


def fetch_accuweather_hourly(lat, lon):
    if not ACCUWEATHER_KEY:
        return None, "no key"
    cache_key = _coord_cache_key(lat, lon)
    cached = db_cache_get("accuweather_hourly_v2", cache_key)
    if isinstance(cached, dict) and "hours" in cached:
        return cached, None
    location, loc_err = _fetch_accuweather_location(lat, lon)
    if not location:
        return None, loc_err or "no location key"
    key = location["key"]
    try:
        fr = requests.get(
            f"https://dataservice.accuweather.com/forecasts/v1/hourly/12hour/{key}",
            headers=_accuweather_headers(),
            params={"details": "true", "metric": "true"}, timeout=TIMEOUT,
        )
        if not fr.ok:
            err = _provider_http_error(fr)
            if fr.status_code == 401:
                provider_backoff_set("accuweather_core", "API key is not authorized; verify the active Core Weather subscription/key")
            elif fr.status_code == 403:
                provider_backoff_set("accuweather_core", "Core Weather hourly forecast is not enabled for this key")
            elif fr.status_code == 429:
                provider_backoff_set("accuweather_core", "Core Weather rate limit reached")
            return None, err
        result = {"hours": fr.json(), "location": location}
        db_cache_set("accuweather_hourly_v2", cache_key, result, ACCUWEATHER_HOURLY_TTL_MIN)
        return result, None
    except Exception as e:
        return None, _safe_error(e)


def fetch_minutecast(lat, lon):
    """Call MinuteCast at most once per site per six-hour cache window.

    The payload keeps its fetch timestamp. We never reinterpret old minute
    offsets relative to the current time, which would create fake nowcasts.
    """
    if not ACCUWEATHER_KEY:
        return None, "no key"
    if not _supabase_enabled():
        return None, "disabled — configure Supabase cache first so the 50-request MinuteCast quota is protected"
    blocked = provider_backoff_get("accuweather_minutecast")
    if blocked:
        return None, f"backoff — {blocked}"

    cache_key = _coord_cache_key(lat, lon)
    cached_record = db_cache_get_record("accuweather_minutecast", cache_key)
    if cached_record is not None:
        payload = cached_record.get("payload")
        if payload is not None:
            return payload, None

    used = db_usage_count_24h("accuweather_minutecast")
    if used is not None and used >= MINUTECAST_SOFT_LIMIT_24H:
        return None, f"quota guard — {used} MinuteCast requests in rolling 24h; maximum configured is {MINUTECAST_SOFT_LIMIT_24H}"

    # Count attempts, not only successful responses. This is intentionally
    # conservative because provider quotas can include rejected requests.
    db_usage_record("accuweather_minutecast")
    fetched_at = datetime.now(UTC)
    try:
        r = requests.get(
            "https://dataservice.accuweather.com/forecasts/v1/minute",
            headers=_accuweather_headers(),
            params={"q": f"{lat},{lon}"},
            timeout=TIMEOUT,
        )
        if not r.ok:
            err = _provider_http_error(r)
            if r.status_code == 401:
                provider_backoff_set("accuweather_minutecast", "API key is not authorized for MinuteCast")
            elif r.status_code == 403:
                provider_backoff_set("accuweather_minutecast", "MinuteCast subscription/trial is not enabled for this key")
            elif r.status_code == 429:
                provider_backoff_set("accuweather_minutecast", "MinuteCast rate limit reached")
            return None, err

        payload = r.json()
        out = []
        for m in payload.get("Intervals", []):
            dbz = float(m.get("Dbz") or 0)
            mmhr = ((10 ** (dbz / 10.0)) / 200.0) ** (1 / 1.6) if dbz > 0 else 0.0
            minute = int(m.get("Minute") if m.get("Minute") is not None else m.get("StartMinute", 0))
            lightning_rate = float(m.get("LightningRate") or 0)
            out.append({
                "minute": minute,
                "mm_per_min": mmhr / 60.0,
                "is_precip": dbz > 0 or bool(m.get("PrecipitationType")),
                "dbz": dbz,
                "lightning_rate": lightning_rate,
            })
        result = {"fetched_at": fetched_at.isoformat(), "intervals": out}
        db_cache_set("accuweather_minutecast", cache_key, result, MINUTECAST_TTL_MIN)
        return result, None
    except Exception as e:
        return None, _safe_error(e)


def _imd_headers():
    headers = {"Accept": "application/json"}
    if IMD_API_KEY:
        header = str(IMD_AUTH_HEADER or "Authorization").strip()
        prefix = str(IMD_AUTH_PREFIX or "")
        headers[header] = f"{prefix}{IMD_API_KEY}"
    return headers

def fetch_imd_subdivision_warning(subdivision):
    """Official IMD subdivision warning overlay (not a numerical forecast weight)."""
    if not subdivision:
        return None, "no IMD subdivision mapped for this site"
    if not IMD_API_KEY:
        return None, "ready — add IMD_API_KEY after IMD API Management access is issued"
    blocked = provider_backoff_get("imd")
    if blocked:
        return None, f"backoff — {blocked}"
    data = db_cache_get("imd_subdivisionwarning", "all")
    if data is None:
        try:
            r = requests.get("https://api.imd.gov.in/api/v1/subdivisionwarning", headers=_imd_headers(), timeout=TIMEOUT)
            if not r.ok:
                err = _provider_http_error(r)
                if r.status_code in (401, 403):
                    provider_backoff_set("imd", "IMD API Management credential/auth scheme is not authorized")
                elif r.status_code == 429:
                    provider_backoff_set("imd", "IMD API rate limit reached")
                return None, err
            data = r.json(); db_cache_set("imd_subdivisionwarning", "all", data, IMD_TTL_MIN)
        except Exception as e:
            return None, _safe_error(e)
    rows = data.get("data", data) if isinstance(data, dict) else data
    if not isinstance(rows, list):
        return None, "unexpected IMD response format"
    target = str(subdivision).strip().lower()
    for row in rows:
        if not isinstance(row, dict): continue
        name = str(row.get("SUBDIV") or row.get("Subdivision") or row.get("subdivision") or "").strip()
        if name.lower() == target:
            return row, None
    return None, f"online but no warning record matched subdivision '{subdivision}'"

def _imd_today_warning(row):
    if not isinstance(row, dict):
        return "", ""
    warning = str(row.get("day1_warning") or row.get("Day_1_Warning") or row.get("Day_1") or "").strip()
    color = str(row.get("day1_color") or row.get("Day1_Color") or "").strip()
    return warning, color

LAST_PROVIDER_PAYLOADS = {}

def build_forecast(lat, lon, days=7, imd_subdivision=""):
    global LAST_PROVIDER_PAYLOADS
    # IMD is surfaced as an official safety advisory, not averaged into rain mm.
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        futs = {
            "ow": ex.submit(fetch_openweather, lat, lon),
            "om": ex.submit(fetch_open_meteo, lat, lon, days),
            "tm": ex.submit(fetch_tomorrow_io, lat, lon),
            "aw": ex.submit(fetch_accuweather_hourly, lat, lon),
            "mc": ex.submit(fetch_minutecast, lat, lon),
            "ws": ex.submit(fetch_weatherstack, lat, lon, days),
            "imd": ex.submit(fetch_imd_subdivision_warning, imd_subdivision),
        }
        ow, ow_err = futs["ow"].result()
        om, om_err = futs["om"].result()
        tm, tm_err = futs["tm"].result()
        aw, aw_err = futs["aw"].result()
        mc, mc_err = futs["mc"].result()
        ws, ws_err = futs["ws"].result()
        imd, imd_err = futs["imd"].result()

    LAST_PROVIDER_PAYLOADS = {
        "openweather": ow,
        "open_meteo": om,
        "tomorrow_io": tm,
        "accuweather": aw,
        "minutecast": mc,
        "weatherstack": ws,
        "imd": imd,
    }

    db_ok, db_err = db_health_check()

    aw_status = str(aw_err)
    if isinstance(aw, dict) and aw.get("hours") is not None:
        loc = aw.get("location") or {}
        parts = ["ok"]
        if loc.get("key"): parts.append(f"location key {loc['key']}")
        if loc.get("name"): parts.append(str(loc["name"]))
        if loc.get("distance_km") is not None: parts.append(f"mapped {loc['distance_km']} km from mine coordinates")
        aw_status = " — ".join(parts)
    imd_status = f"ok — {imd_subdivision} official warning layer" if imd else str(imd_err)
    src_status = {
        "Open-Meteo": "ok" if om else str(om_err),
        "Tomorrow.io": "ok" if tm else str(tm_err),
        "AccuWeather": aw_status,
        "MinuteCast": _minutecast_status(mc, mc_err),
        "OpenWeather": "ok — One Call 4.0 hourly (up to 20h)" if ow else str(ow_err),
        "IMD": imd_status,
        "Weatherstack": (("ok — current conditions only" if ws.get("_wim_weatherstack_mode") == "current_only" else "ok") if isinstance(ws, dict) else str(ws_err)),
        "Supabase cache": "ok" if db_ok else (db_err or "not configured — required for persistent quota-safe caching"),
    }

    now_h = now_ist().replace(minute=0, second=0, microsecond=0)
    cutoff = now_h + timedelta(days=days)
    raw = {}

    def add(hk, src, temp, rain, pop, wind, vis, lightning, desc, hum=0, cloud=0, lightning_prob=0):
        if hk < now_h - timedelta(hours=1) or hk > cutoff:
            return
        raw.setdefault(hk, {})
        raw[hk][src] = dict(
            temp=float(temp or 0),
            rain=max(0.0, float(rain or 0)),
            pop=float(pop or 0),
            wind=float(wind or 0),
            vis=float(vis if vis is not None else 10),
            lightning=bool(lightning),
            lightning_prob=max(0.0, min(100.0, float(lightning_prob or (100 if lightning else 0)))),
            desc=str(desc or ""),
            hum=float(hum or 0),
            cloud=float(cloud or 0),
        )

    if ow and isinstance(ow, dict):
        ow_hours = ow.get("data") or ow.get("hourly") or []
        for e in ow_hours:
            hk = utc_to_ist(datetime.fromtimestamp(e["dt"], tz=UTC)).replace(minute=0, second=0, microsecond=0)
            wid = e["weather"][0]["id"] if e.get("weather") else 0
            thunder = 200 <= int(wid or 0) < 300
            add(
                hk, "openweather", e.get("temp", 0), e.get("rain", {}).get("1h", 0), e.get("pop", 0) * 100,
                e.get("wind_speed", 0) * 3.6, e.get("visibility", 10000) / 1000,
                thunder, e["weather"][0]["description"] if e.get("weather") else "", e.get("humidity", 0),
                lightning_prob=100 if thunder else 0,
            )

    if om and "hourly" in om:
        h = om["hourly"]
        vis = h.get("visibility", [])
        hum = h.get("relative_humidity_2m", [])
        cloud = h.get("cloud_cover", h.get("cloudcover", []))
        weather_codes = h.get("weather_code", [])
        for i, ts in enumerate(h["time"]):
            hk = IST.localize(datetime.fromisoformat(ts)).replace(minute=0, second=0, microsecond=0)
            code = int(weather_codes[i] or 0) if i < len(weather_codes) else 0
            thunder = code in {95, 96, 99}
            add(
                hk, "open_meteo", h["temperature_2m"][i], h["precipitation"][i], h["precipitation_probability"][i],
                h["wind_speed_10m"][i], vis[i] / 1000 if i < len(vis) and vis[i] is not None else 10,
                thunder, "Thunderstorm" if thunder else "", hum[i] if i < len(hum) else 0,
                cloud[i] if i < len(cloud) else 0, lightning_prob=100 if thunder else 0,
            )

    if tm and "timelines" in tm and "hourly" in tm["timelines"]:
        for iv in tm["timelines"]["hourly"]:
            try:
                dt_utc = datetime.fromisoformat(str(iv["time"]).replace("Z", "+00:00"))
                if dt_utc.tzinfo is None:
                    dt_utc = UTC.localize(dt_utc)
            except Exception:
                continue
            hk = utc_to_ist(dt_utc).replace(minute=0, second=0, microsecond=0)
            v = iv.get("values", {})
            try:
                weather_code = int(v.get("weatherCode") or 0)
            except Exception:
                weather_code = 0
            flash_density = float(v.get("lightningFlashRateDensity") or 0)
            legacy_strikes = float(v.get("lightningStrikeCount") or 0)
            thunder_prob = float(v.get("thunderstormProbability") or 0)
            thunder = weather_code == 8000 or flash_density > 0 or legacy_strikes > 0 or thunder_prob >= 20
            add(
                hk, "tomorrow_io", v.get("temperature", 0), v.get("precipitationIntensity", 0), v.get("precipitationProbability", 0),
                v.get("windSpeed", 0) * 3.6, v.get("visibility", 10), thunder,
                "Thunderstorm" if weather_code == 8000 else "", v.get("humidity", 0), v.get("cloudCover", 0),
                lightning_prob=thunder_prob if thunder_prob > 0 else (100 if thunder else 0),
            )

    if ws and isinstance(ws, dict):
        forecasts = ws.get("forecast", {})
        for date_str, day in forecasts.items():
            for e in day.get("hourly", []) or []:
                try:
                    raw_time = str(e.get("time", "0")).zfill(4)
                    dt_local = datetime.strptime(f"{date_str} {raw_time}", "%Y-%m-%d %H%M")
                    hk = IST.localize(dt_local).replace(minute=0, second=0, microsecond=0)
                except Exception:
                    continue
                descs = e.get("weather_descriptions") or []
                desc = descs[0] if descs else ""
                try:
                    wcode = int(e.get("weather_code") or 0)
                except Exception:
                    wcode = 0
                thunder_prob = float(e.get("chanceofthunder") or e.get("chance_of_thunder") or 0)
                thunder = thunder_prob >= 20 or "thunder" in desc.lower() or wcode in {386, 389, 392, 395}
                add(
                    hk, "weatherstack", e.get("temperature", 0), e.get("precip", 0),
                    e.get("chanceofrain", e.get("chance_of_rain", 0)),
                    e.get("wind_speed", e.get("windspeed", 0)), e.get("visibility", 10), thunder, desc,
                    e.get("humidity", 0), e.get("cloudcover", e.get("cloud_cover", 0)),
                    lightning_prob=thunder_prob if thunder_prob > 0 else (100 if thunder else 0),
                )

        # Free/current-only Weatherstack accounts can still improve the present
        # hour without pretending to provide a multi-day forecast.
        if ws.get("_wim_weatherstack_mode") == "current_only" and isinstance(ws.get("current"), dict):
            e = ws["current"]
            descs = e.get("weather_descriptions") or []
            desc = descs[0] if descs else ""
            try:
                wcode = int(e.get("weather_code") or 0)
            except Exception:
                wcode = 0
            thunder = "thunder" in desc.lower() or wcode in {386, 389, 392, 395}
            add(
                now_h, "weatherstack", e.get("temperature", 0), e.get("precip", 0), 0,
                e.get("wind_speed", 0), e.get("visibility", 10), thunder, desc,
                e.get("humidity", 0), e.get("cloudcover", 0),
                lightning_prob=100 if thunder else 0,
            )

    if aw:
        aw_hours = aw.get("hours", []) if isinstance(aw, dict) else aw
        for e in aw_hours:
            try:
                dt = datetime.fromisoformat(e.get("DateTime", ""))
                if dt.tzinfo is None:
                    dt = UTC.localize(dt)
                hk = dt.astimezone(IST).replace(minute=0, second=0, microsecond=0)
            except Exception:
                continue
            thunder_prob = float(e.get("ThunderstormProbability") or 0)
            phrase = str(e.get("IconPhrase", ""))
            thunder = thunder_prob >= 20 or "thunder" in phrase.lower() or "t-storm" in phrase.lower()
            add(
                hk, "accuweather", e.get("Temperature", {}).get("Value", 0),
                e.get("Rain", {}).get("Value", 0) + e.get("Snow", {}).get("Value", 0),
                e.get("PrecipitationProbability", 0), e.get("Wind", {}).get("Speed", {}).get("Value", 0),
                e.get("Visibility", {}).get("Metric", {}).get("Value", 10.0), thunder, phrase,
                e.get("RelativeHumidity", 0), e.get("CloudCover", 0), lightning_prob=thunder_prob,
            )

    mc_active = _active_minutecast_intervals(mc)
    if mc_active:
        mc_h = collections.defaultdict(lambda: {"rain": 0.0, "lightning_rate": 0.0})
        for m in mc_active:
            try:
                event = datetime.fromisoformat(m["forecast_time"])
                if event.tzinfo is None:
                    event = IST.localize(event)
                hk = event.astimezone(IST).replace(minute=0, second=0, microsecond=0)
            except Exception:
                continue
            mc_h[hk]["rain"] += float(m.get("mm_per_min", 0) or 0)
            mc_h[hk]["lightning_rate"] = max(mc_h[hk]["lightning_rate"], float(m.get("lightning_rate", 0) or 0))
        for hk, vals in mc_h.items():
            mm = vals["rain"]
            lightning = vals["lightning_rate"] > 0
            raw.setdefault(hk, {})
            raw[hk]["minutecast"] = dict(
                temp=0, rain=mm, pop=100 if mm > 0.05 else 0, wind=0, vis=10.0,
                lightning=lightning, lightning_prob=100 if lightning else 0,
                desc="MinuteCast lightning" if lightning else "", hum=0, cloud=0,
            )

    final = []
    for hk in sorted(raw.keys()):
        srcs = raw[hk]
        lead_h = max(0.0, (hk - now_h).total_seconds() / 3600.0)

        def source_weight(src, field):
            # Horizon-aware fusion: short-range point/nowcast data gets more
            # influence close to now; global-model sources carry the long range.
            if src == "minutecast":
                return 0.90 if field in {"rain", "pop"} and lead_h <= 2.1 else 0.0
            if src == "accuweather":
                return 0.45 if lead_h <= 12 else 0.0
            if src == "tomorrow_io":
                return 0.32 if lead_h <= 48 else 0.28
            if src == "open_meteo":
                return 0.30 if lead_h <= 48 else 0.36
            if src == "weatherstack":
                return 0.30 if lead_h <= 1.5 else 0.12
            if src == "openweather":
                return 0.30 if lead_h <= 20 else 0.0
            return 0.0

        def wavg(field, default=0.0):
            valid = []
            for src, d in srcs.items():
                w = source_weight(src, field)
                if w <= 0:
                    continue
                value = d.get(field)
                if value is None:
                    continue
                valid.append((float(value), w))
            total_weight = sum(weight for _, weight in valid)
            if total_weight <= 0:
                return default
            return sum(value * weight for value, weight in valid) / total_weight

        # Keep the displayed rainfall as a best-estimate weighted blend. For
        # safety decisions we also preserve an upper credible estimate rather
        # than hiding disagreement between providers.
        rain_candidates = []
        for src, d in srcs.items():
            w = source_weight(src, "rain")
            if w > 0:
                rain_candidates.append((float(d.get("rain", 0) or 0), w, src))
        if rain_candidates:
            tw = sum(w for _, w, _ in rain_candidates)
            rain_out = sum(v * w for v, w, _ in rain_candidates) / tw if tw else 0.0
            risk_rain = max(v for v, _, _ in rain_candidates)
        else:
            rain_out = 0.0
            risk_rain = 0.0

        pop_out = wavg("pop", 0.0)
        vis_out = wavg("vis", 10.0)
        temp_out = wavg("temp", 0.0)
        wind_out = wavg("wind", 0.0)
        hum_out = wavg("hum", 0.0)
        cloud_out = wavg("cloud", 0.0)

        descs = [d["desc"] for d in srcs.values() if d.get("desc")]
        best_desc = ""
        if descs:
            if "accuweather" in srcs and srcs["accuweather"].get("desc"):
                best_desc = srcs["accuweather"]["desc"]
            else:
                best_desc = collections.Counter(descs).most_common(1)[0][0]

        lightning_prob = max((d.get("lightning_prob", 0) for d in srcs.values()), default=0)
        lightning_sources = [src for src, d in srcs.items() if d.get("lightning")]

        # Confidence rewards independent source coverage and agreement. It is
        # diagnostic only; it never suppresses a safety hazard.
        active_sources = [src for src in srcs if source_weight(src, "rain") > 0]
        coverage = min(1.0, len(active_sources) / 3.0)
        rain_values = [v for v, _, _ in rain_candidates]
        if len(rain_values) >= 2:
            mean_r = sum(rain_values) / len(rain_values)
            spread = max(rain_values) - min(rain_values)
            agreement = max(0.0, 1.0 - spread / max(1.0, mean_r + 0.5))
        else:
            agreement = 0.45 if rain_values else 0.0
        confidence = round(100 * (0.65 * coverage + 0.35 * agreement))

        final.append((hk, {
            "temp": round(temp_out, 1), "rain_mm": round(rain_out, 2),
            "risk_rain_mm": round(risk_rain, 2),
            "pop": round(pop_out, 1), "wind_kmh": round(wind_out, 1),
            "vis_km": round(vis_out, 1), "humidity": round(hum_out, 1),
            "cloud": round(cloud_out, 0),
            "lightning": bool(lightning_sources),
            "lightning_prob": round(lightning_prob, 0),
            "lightning_sources": lightning_sources,
            "confidence": confidence,
            "desc": best_desc, "n_sources": len(srcs),
        }))

    by_day = collections.defaultdict(list)
    for hk, d in final:
        by_day[hk.date()].append((hk, d))
    for date_key in by_day:
        seen = set()
        deduplicated = []
        for hk, d in by_day[date_key]:
            if hk not in seen:
                seen.add(hk)
                deduplicated.append((hk, d))
        by_day[date_key] = deduplicated

    return dict(by_day), mc_active, src_status, imd
