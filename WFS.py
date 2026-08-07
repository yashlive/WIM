"""
Adani Natural Resources — WIM (Weather Intelligence Mining)
v3.4 — repaired full working file
"""

import os
import json
import requests
import collections
import base64
import concurrent.futures
from datetime import datetime, timedelta

import pytz
import streamlit as st
import streamlit.components.v1 as components

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

st.set_page_config(
    page_title="WIM — Weather Intelligence Mining | Adani Natural Resources",
    page_icon="🌦️",
    layout="wide",
    initial_sidebar_state="expanded",
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

LOGO_HTML = (
    f'<img src="data:image/png;base64,{LOGO_B64}" style="height:44px;display:block;" alt="Adani">'
    if LOGO_B64
    else '<span style="font-size:1.6rem;font-weight:900;color:#0B74B0;">adani</span>'
)
_FONT_STACK = (
    "'AdaniFont', 'Helvetica Neue', Arial, sans-serif"
    if FONT_B64
    else "'Helvetica Neue', Arial, sans-serif"
)
FONT_FACE = (
    f"@font-face{{font-family:'AdaniFont';src:url('data:font/truetype;base64,{FONT_B64}') format('truetype');font-weight:normal;font-style:normal;}}"
    if FONT_B64
    else ""
)

_CSS = f"""
{FONT_FACE}
*{{box-sizing:border-box}}
html,body,.stApp,[data-testid="stAppViewContainer"],.block-container{{font-family:{_FONT_STACK} !important;}}
.stApp{{background:#F8F9FA !important;color:#1A1A2E !important;}}
.block-container{{padding:0.25rem 2rem 2rem 2rem !important;max-width:1400px !important;margin:0 auto !important;}}
.wim-nav{{background:#fff;border-bottom:1px solid #E2E8F0;height:64px;display:flex;align-items:center;justify-content:space-between;position:fixed;top:0;left:0;right:0;z-index:9999;padding:0 2rem 0 2.5rem;box-shadow:0 1px 4px rgba(0,0,0,0.06);}}
.wim-nav-spacer{{height:56px;}}
.wim-nav-left{{display:flex;align-items:center;gap:16px;}}
.wim-nav-sep{{width:1px;height:28px;background:linear-gradient(180deg,#0B74B0,#16A34A);}}
.wim-nav-title{{font-size:0.875rem;font-weight:700;background:linear-gradient(90deg,#0B74B0,#16A34A);-webkit-background-clip:text;background-clip:text;color:transparent;}}
.wim-nav-sub{{font-size:0.65rem;font-weight:500;color:#94A3B8;letter-spacing:0.1em;text-transform:uppercase;}}
.wim-site-name{{font-size:1.375rem;font-weight:700;color:#1A1A2E;}}
.wim-site-coord{{font-size:0.75rem;color:#94A3B8;}}
.wim-section{{font-size:0.65rem;font-weight:800;letter-spacing:0.12em;text-transform:uppercase;color:#94A3B8;margin:8px 0 10px 0;padding-bottom:6px;border-bottom:1px solid #E2E8F0;}}
.wim-alert{{border-radius:8px;padding:14px 18px;margin:14px 0;font-size:0.875rem;line-height:1.6;border:1px solid;border-left:5px solid;}}
.wim-alert-none{{background:#F8FAFC;border-color:#E2E8F0;border-left-color:#94A3B8;color:#475569;}}
.wim-table{{width:100%;border-collapse:collapse;background:#fff;border:1px solid #E2E8F0;border-radius:10px;overflow:hidden;font-size:0.845rem;}}
.wim-table th,.wim-table td{{padding:10px 16px;border-bottom:1px solid #F1F5F9;}}
.wim-badge{{display:inline-block;border-radius:4px;padding:2px 8px;font-size:0.68rem;font-weight:700;white-space:nowrap;}}
"""

st.markdown(f"<style>{_CSS}</style>", unsafe_allow_html=True)

ACCUWEATHER_KEY = st.secrets.get("ACCUWEATHER_KEY", os.getenv("ACCUWEATHER_KEY", ""))
OPENWEATHER_KEY = st.secrets.get("OPENWEATHER_KEY", os.getenv("OPENWEATHER_KEY", ""))
TOMORROWIO_KEY = st.secrets.get("TOMORROWIO_KEY", os.getenv("TOMORROWIO_KEY", ""))
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "Adani@2026#Mine")
SITES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mine_sites.json")
DEFAULT_SITE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "default_site.json")

DEFAULT_SITES = [
    {"id": "builtin-suliyari", "name": "Suliyari", "lat": 23.941626, "lon": 82.331934, "type": "Coal Open Cast Mine", "builtin": True},
    {"id": "builtin-dhirauli", "name": "Dhirauli", "lat": 23.936440, "lon": 82.358836, "type": "Coal Open Cast Mine", "builtin": True},
    {"id": "builtin-parsa", "name": "Parsa", "lat": 22.824950, "lon": 82.804340, "type": "Coal Open Cast Mine", "builtin": True},
    {"id": "builtin-talabira", "name": "Talabira", "lat": 21.756317, "lon": 83.970446, "type": "Coal Open Cast Mine", "builtin": True},
    {"id": "builtin-gare-pelma", "name": "Gare Pelma III", "lat": 22.105303, "lon": 83.292822, "type": "Coal Open Cast Mine", "builtin": True},
    {"id": "builtin-gp-ii", "name": "Gare Pelma II", "lat": 22.160838, "lon": 83.472457, "type": "Coal Open Cast Mine", "builtin": True},
    {"id": "builtin-pcb", "name": "PCB", "lat": 22.854601, "lon": 82.763414, "type": "Coal Open Cast Mine", "builtin": True},
    {"id": "builtin-pekb", "name": "PEKB", "lat": 22.823873, "lon": 82.805322, "type": "Coal Open Cast Mine", "builtin": True},
    {"id": "builtin-kurmitar", "name": "Kurmitar", "lat": 21.749766, "lon": 85.167471, "type": "Iron Ore Mine", "builtin": True},
    {"id": "builtin-taldih", "name": "Taldih", "lat": 21.91056, "lon": 85.18014, "type": "Iron Ore Mine", "builtin": True},
    {"id": "builtin-gondbahera-ujheni", "name": "Gondbahera Ujheni", "lat": 24.175830, "lon": 82.369544, "type": "Underground Mine (Incline/Shaft — Greenfield)", "builtin": True},
    {"id": "builtin-gondkhari", "name": "Gondkhari", "lat": 21.143326, "lon": 78.934850, "type": "Underground Mine (Incline/Shaft — Greenfield)", "builtin": True},
]

IST = pytz.timezone("Asia/Kolkata")
UTC = pytz.utc
TIMEOUT = 20
RETRY_MAX = 3
WIND_CAUTION = 30
WIND_STOP = 32
VIS_CAUTION = 5.0
VIS_STOP = 2.0
RAIN_MOD = 1.5
RAIN_HEAVY = 5.0
API_WEIGHTS = {"accuweather": 0.40, "open_meteo": 0.25, "openweather": 0.20, "tomorrow_io": 0.10, "imd": 0.05}


def _load_sites_json():
    if not os.path.exists(SITES_FILE):
        return []
    try:
        with open(SITES_FILE) as f:
            return json.load(f)
    except Exception:
        return []


def load_sites():
    custom = _load_sites_json()
    result = list(DEFAULT_SITES)
    builtins = {s["name"] for s in DEFAULT_SITES}
    for s in custom:
        if s.get("name") not in builtins:
            result.append(s)
    return result


def save_site(name, lat, lon):
    ex = [s for s in _load_sites_json() if s.get("name") != name]
    ex.append({"name": name, "lat": lat, "lon": lon, "type": "Custom Site", "builtin": False})
    with open(SITES_FILE, "w") as f:
        json.dump(ex, f, indent=2)


def update_site(old_name, new_name, lat, lon):
    ex = _load_sites_json()
    for s in ex:
        if s.get("name") == old_name:
            s["name"] = new_name.strip()
            s["lat"] = lat
            s["lon"] = lon
    with open(SITES_FILE, "w") as f:
        json.dump(ex, f, indent=2)


def delete_site(name):
    ex = [s for s in _load_sites_json() if s.get("name") != name]
    with open(SITES_FILE, "w") as f:
        json.dump(ex, f, indent=2)


def get_default_site():
    try:
        if os.path.exists(DEFAULT_SITE_FILE):
            with open(DEFAULT_SITE_FILE) as f:
                return json.load(f).get("name")
    except Exception:
        pass
    return None


def set_default_site(name):
    with open(DEFAULT_SITE_FILE, "w") as f:
        json.dump({"name": name}, f)


ALL_SITES = load_sites()
SITE_NAMES = [s["name"] for s in ALL_SITES]

if "active_site" not in st.session_state:
    d = get_default_site()
    st.session_state.active_site = d if d in SITE_NAMES else (SITE_NAMES[0] if SITE_NAMES else None)


def now_ist():
    return datetime.now(IST)


def utc_to_ist(dt):
    if dt.tzinfo is None:
        dt = UTC.localize(dt)
    return dt.astimezone(IST)


def rain_badge_html(mm):
    if mm == 0:
        return f"{mm} mm"
    if mm < 0.3:
        return f"{mm} mm · Drizzle"
    if mm < 1.5:
        return f"{mm} mm · Light"
    if mm < 5.0:
        return f"{mm} mm · Moderate"
    return f"{mm} mm · Heavy"


def mining_impact_html(mm, wind, vis, lightning):
    if lightning:
        return "⚡ Stop — Lightning"
    if mm >= RAIN_HEAVY or vis <= VIS_STOP or wind >= WIND_STOP:
        return "Stop Ops"
    if mm >= RAIN_MOD or vis <= VIS_CAUTION or wind >= WIND_CAUTION:
        return "Caution"
    if mm >= 0.3:
        return "Monitor"
    return "Clear"


def condition_str(total, descs, max_pop=0):
    if total < 0.5:
        return "Clear"
    rain_types = []
    for desc in descs or []:
        d = desc.lower()
        if any(w in d for w in ["heavy", "torrential", "downpour", "storm", "thunderstorm"]):
            rain_types.append("heavy")
        elif any(w in d for w in ["moderate", "steady", "continuous"]):
            rain_types.append("moderate")
        elif any(w in d for w in ["light", "shower", "showers"]):
            rain_types.append("light")
        elif any(w in d for w in ["drizzle", "mist", "sprinkle"]):
            rain_types.append("drizzle")
    api_rain_type = collections.Counter(rain_types).most_common(1)[0][0] if rain_types else None
    if total >= 15 and max_pop >= 25:
        return "Heavy Rain"
    if total >= 15 and max_pop < 25:
        return "Moderate Rain"
    if total >= 5 and max_pop >= 35:
        return "Moderate Rain"
    if total >= 5 and max_pop < 35:
        return "Light Rain"
    if total >= 1.5 and max_pop >= 45:
        return "Light Rain"
    if total >= 1.5 and max_pop < 45:
        return "Drizzle"
    if total >= 0.5:
        return "Drizzle"
    if api_rain_type == "heavy":
        return "Heavy Rain"
    if api_rain_type == "moderate":
        return "Moderate Rain"
    if api_rain_type == "light":
        return "Light Rain"
    if api_rain_type == "drizzle":
        return "Drizzle"
    return "Clear"


@st.cache_data(ttl=1800)
def fetch_openweather(lat, lon):
    if not OPENWEATHER_KEY:
        return None, "no key"
    try:
        url = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&units=metric&appid={OPENWEATHER_KEY}"
        r = requests.get(url, timeout=TIMEOUT)
        r.raise_for_status()
        payload = r.json()
        hourly = []
        for item in payload.get("list", []):
            main = item.get("main", {})
            wind = item.get("wind", {})
            weather = item.get("weather", [{}])[0]
            rain = item.get("rain", {})
            rain_3h = float(rain.get("3h", 0) or 0)
            weather_id = int(weather.get("id", 0) or 0)
            hourly.append(
                {
                    "dt": item.get("dt"),
                    "temp": float(main.get("temp", 0) or 0),
                    "rain": {"1h": rain_3h / 3.0},
                    "pop": float(item.get("pop", 0) or 0),
                    "wind_speed": float(wind.get("speed", 0) or 0),
                    "visibility": float(item.get("visibility", 10000) or 10000),
                    "weather": [{"id": weather_id, "description": weather.get("description", "")}],
                    "humidity": float(main.get("humidity", 0) or 0),
                }
            )
        if not hourly:
            return None, "empty forecast response"
        return {"hourly": hourly, "source": "OpenWeather 5-day / 3-hour forecast"}, None
    except requests.HTTPError as exc:
        return None, f"HTTP {getattr(exc.response, 'status_code', 'unknown')}: {exc}"
    except requests.RequestException as exc:
        return None, f"network error: {exc}"
    except Exception as exc:
        return None, str(exc)


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
    if not TOMORROWIO_KEY:
        return None, "no key"
    try:
        r = requests.get(
            f"https://api.tomorrow.io/v4/weather/forecast?location={lat},{lon}&units=metric&apikey={TOMORROWIO_KEY}",
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        return r.json(), None
    except Exception as e:
        return None, str(e)


@st.cache_data(ttl=1800)
def fetch_accuweather_hourly(lat, lon):
    if not ACCUWEATHER_KEY:
        return None, "no key"
    try:
        lr = requests.get(
            f"https://dataservice.accuweather.com/locations/v1/cities/geoposition/search?q={lat},{lon}&apikey={ACCUWEATHER_KEY}",
            timeout=TIMEOUT,
        )
        lr.raise_for_status()
        key = lr.json().get("Key", "")
        if not key:
            return None, "no location key"
        fr = requests.get(
            f"https://dataservice.accuweather.com/forecasts/v1/hourly/12hour/{key}?apikey={ACCUWEATHER_KEY}&details=true&metric=true",
            timeout=TIMEOUT,
        )
        fr.raise_for_status()
        return fr.json(), None
    except Exception as e:
        return None, str(e)


@st.cache_data(ttl=900)
def fetch_minutecast(lat, lon):
    if not ACCUWEATHER_KEY:
        return None, "no key"
    try:
        r = requests.get(
            f"https://dataservice.accuweather.com/forecasts/v1/minute?q={lat},{lon}&apikey={ACCUWEATHER_KEY}&details=true",
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        out = []
        for m in r.json().get("Intervals", []):
            dbz = m.get("Dbz", 0)
            mmhr = ((10 ** (dbz / 10.0)) / 200.0) ** (1 / 1.6) if dbz > 0 else 0.0
            out.append({"minute": m.get("StartMinute", 0), "mm_per_min": mmhr / 60.0, "is_precip": m.get("HasPrecipitation", False), "dbz": dbz})
        return (out if out else None), None
    except Exception as e:
        return None, str(e)


@st.cache_data(ttl=1800)
def fetch_imd(lat, lon):
    try:
        r = requests.get(f"https://mausam.imd.gov.in/api/nowcast_district_api.php?lat={lat}&lon={lon}", timeout=TIMEOUT)
        r.raise_for_status()
        return r.json(), None
    except Exception as e:
        return None, str(e)


def build_forecast(lat, lon, days=7):
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        futs = {
            "ow": ex.submit(fetch_openweather, lat, lon),
            "om": ex.submit(fetch_open_meteo, lat, lon, days),
            "tm": ex.submit(fetch_tomorrow_io, lat, lon),
            "aw": ex.submit(fetch_accuweather_hourly, lat, lon),
            "mc": ex.submit(fetch_minutecast, lat, lon),
            "imd": ex.submit(fetch_imd, lat, lon),
        }
        ow, ow_err = futs["ow"].result()
        om, om_err = futs["om"].result()
        tm, tm_err = futs["tm"].result()
        aw, aw_err = futs["aw"].result()
        mc, mc_err = futs["mc"].result()
        imd, imd_err = futs["imd"].result()

    src_status = {
        "Open-Meteo": "ok" if om else str(om_err),
        "AccuWeather": "ok" if aw else str(aw_err),
        "MinuteCast": "ok" if mc else str(mc_err),
        "OpenWeather": "ok" if ow else str(ow_err),
        "Tomorrow.io": "ok" if tm else str(tm_err),
        "IMD": "ok" if imd else str(imd_err),
    }

    now_h = now_ist().replace(minute=0, second=0, microsecond=0)
    cutoff = now_h + timedelta(days=days)
    raw = {}

    def add(hk, src, temp, rain, pop, wind, vis, lightning, desc, hum=0, cloud=0):
        if hk < now_h - timedelta(hours=1) or hk > cutoff:
            return
        raw.setdefault(hk, {})
        raw[hk][src] = {
            "temp": float(temp or 0),
            "rain": max(0.0, float(rain or 0)),
            "pop": float(pop or 0),
            "wind": float(wind or 0),
            "vis": float(vis or 10),
            "lightning": bool(lightning),
            "desc": str(desc or ""),
            "hum": float(hum or 0),
            "cloud": float(cloud or 0),
        }

    if imd:
        try:
            rain = imd.get("rainfall", 0) if isinstance(imd, dict) else 0
            add(now_h, "imd", 0, rain, 80 if rain > 0 else 20, 0, 10.0, False, "IMD Nowcast", 0)
        except Exception:
            pass

    if ow and "hourly" in ow:
        for e in ow["hourly"]:
            hk = utc_to_ist(datetime.fromtimestamp(e["dt"], tz=UTC)).replace(minute=0, second=0, microsecond=0)
            wid = e["weather"][0]["id"] if e.get("weather") else 0
            add(
                hk,
                "openweather",
                e["temp"],
                e.get("rain", {}).get("1h", 0),
                e.get("pop", 0) * 100,
                e["wind_speed"] * 3.6,
                e.get("visibility", 10000) / 1000,
                200 <= wid < 300,
                e["weather"][0]["description"] if e.get("weather") else "",
                e.get("humidity", 0),
            )

    if om and "hourly" in om:
        h = om["hourly"]
        vis = h.get("visibility", [])
        hum = h.get("relative_humidity_2m", [])
        cloud = h.get("cloudcover", [])
        for i, ts in enumerate(h["time"]):
            hk = datetime.fromisoformat(ts).replace(tzinfo=IST).replace(minute=0, second=0, microsecond=0)
            add(
                hk,
                "open_meteo",
                h["temperature_2m"][i],
                h["precipitation"][i],
                h["precipitation_probability"][i],
                h["wind_speed_10m"][i],
                vis[i] / 1000 if i < len(vis) and vis[i] is not None else 10,
                False,
                "",
                hum[i] if i < len(hum) else 0,
                cloud[i] if i < len(cloud) else 0,
            )

    if tm and "timelines" in tm and "hourly" in tm["timelines"]:
        for iv in tm["timelines"]["hourly"]:
            try:
                dt_utc = UTC.localize(datetime.strptime(iv["time"], "%Y-%m-%dT%H:%M:%SZ"))
            except Exception:
                continue
            hk = utc_to_ist(dt_utc).replace(minute=0, second=0, microsecond=0)
            v = iv["values"]
            add(
                hk,
                "tomorrow_io",
                v.get("temperature", 0),
                v.get("precipitationIntensity", 0),
                v.get("precipitationProbability", 0),
                v.get("windSpeed", 0) * 3.6,
                v.get("visibility", 10000) / 1000 if v.get("visibility") not in [None, 10000] else 10,
                v.get("lightningStrikeCount", 0) > 0 or v.get("weatherCode") == 8000,
                "",
                v.get("humidity", 0),
            )

    if aw:
        for e in aw:
            try:
                dt = datetime.fromisoformat(e.get("DateTime", ""))
                if dt.tzinfo is None:
                    dt = UTC.localize(dt)
                hk = dt.astimezone(IST).replace(minute=0, second=0, microsecond=0)
            except Exception:
                continue
            add(
                hk,
                "accuweather",
                e.get("Temperature", {}).get("Value", 0),
                e.get("Rain", {}).get("Value", 0) + e.get("Snow", {}).get("Value", 0),
                e.get("PrecipitationProbability", 0),
                e.get("Wind", {}).get("Speed", {}).get("Value", 0),
                e.get("Visibility", {}).get("Metric", {}).get("Value", 10.0),
                e.get("ThunderstormProbability", 0) > 30,
                e.get("IconPhrase", ""),
                e.get("RelativeHumidity", 0),
            )

    if mc:
        now_t = now_ist()
        mc_h = collections.defaultdict(float)
        for m in mc:
            hk = (now_t + timedelta(minutes=m["minute"])).replace(minute=0, second=0, microsecond=0)
            mc_h[hk] += m["mm_per_min"]
        for hk, mm in mc_h.items():
            raw.setdefault(hk, {})
            raw[hk]["minutecast"] = {"temp": 0, "rain": mm, "pop": 100 if mm > 0.05 else 0, "wind": 0, "vis": 10.0, "lightning": False, "desc": "", "hum": 0, "cloud": 0}

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
            valid_vis = [(d["vis"], API_WEIGHTS.get(src, 0)) for src, d in srcs.items() if d["vis"] > 0]
            if not valid_vis:
                return 10
            weighted_sum = sum(vis * weight for vis, weight in valid_vis)
            total_weight = sum(weight for _, weight in valid_vis)
            return weighted_sum / total_weight

        rain_vals = [d["rain"] for d in srcs.values()]
        is_current_hour = hk == now_h
        has_imd_rain = "imd" in srcs and srcs["imd"]["rain"] > 0.1
        if is_current_hour and has_imd_rain:
            rain_out = max(rain_vals)
        elif len(rain_vals) >= 2:
            rain_out = sorted(rain_vals)[len(rain_vals) // 2]
        elif len(rain_vals) == 1:
            rain_out = rain_vals[0]
        else:
            rain_out = 0.0

        pop_out = wavg("pop")
        descs = [d["desc"] for d in srcs.values() if d["desc"]]
        best_desc = ""
        if descs:
            if "accuweather" in srcs and srcs["accuweather"]["desc"]:
                best_desc = srcs["accuweather"]["desc"]
            else:
                best_desc = collections.Counter(descs).most_common(1)[0][0]

        final.append(
            (
                hk,
                {
                    "temp": round(wavg("temp"), 1),
                    "rain_mm": round(rain_out, 2),
                    "pop": round(pop_out, 1),
                    "wind_kmh": round(wavg("wind"), 1),
                    "vis_km": round(wavg_vis(), 1),
                    "humidity": round(wavg("hum"), 1),
                    "cloud": round(wavg("cloud"), 0),
                    "lightning": any(d["lightning"] for d in srcs.values()),
                    "desc": best_desc,
                    "n_sources": len(srcs),
                },
            )
        )

    by_day = collections.defaultdict(list)
    for hk, d in final:
        by_day[hk.date()].append((hk, d))

    for date_key in by_day:
        seen = set()
        dedup = []
        for hk, d in by_day[date_key]:
            if hk not in seen:
                seen.add(hk)
                dedup.append((hk, d))
        by_day[date_key] = dedup

    return dict(by_day), mc, src_status


def generate_fixed_slabs():
    slabs = []
    for i in range(12):
        sh = i * 2
        eh = (i + 1) * 2
        slabel = f"{sh % 12 or 12}:00 {'AM' if sh < 12 else 'PM'}"
        elabel = f"{eh % 12 or 12}:00 {'AM' if eh < 12 else 'PM'}"
        if eh >= 24:
            eh = 0
            elabel = "12:00 AM (next day)"
        slabs.append((sh, eh, f"{slabel} – {elabel}", 0))
    return slabs


def hour_to_slab(h, slabs):
    for s, e, n, m in slabs:
        if s <= h < e or (s > e and (h >= s or h < e)):
            return s, e, n, m
    return None


def build_slabs(hourly, is_today=False):
    slabs = generate_fixed_slabs()
    current_hour = now_ist().hour
    raw = collections.defaultdict(lambda: {"rain": 0, "pop": [], "temp": [], "wind": [], "vis": [], "lightning": [], "hum": [], "cloud": [], "count": 0})
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
        r["pop"].append(d["pop"])
        r["temp"].append(d["temp"])
        r["wind"].append(d["wind_kmh"])
        r["vis"].append(d["vis_km"])
        r["lightning"].append(d["lightning"])
        r["hum"].append(d["humidity"])
        r["cloud"].append(d.get("cloud", 0))
        r["count"] += 1
    slabs_out = []
    for sk, r in raw.items():
        if not r["count"]:
            continue
        avg = lambda lst: sum(lst) / len(lst) if lst else 0
        pops = r["pop"]
        pop_val = int(sorted(pops)[int(len(pops) * 0.75)] if pops else 0)
        slabs_out.append(
            {
                "label": sk[2],
                "sort": sk[0],
                "mm": round(r["rain"], 1),
                "pop": pop_val,
                "temp": round(avg(r["temp"]), 1),
                "hum": round(avg(r["hum"]), 1),
                "cloud": round(avg(r["cloud"]), 0),
                "wind": round(avg(r["wind"]), 1),
                "vis": round(avg(r["vis"]), 1),
                "lightning": any(r["lightning"]),
            }
        )
    slabs_out.sort(key=lambda x: x["sort"])
    return slabs_out


def day_summary(hourly, mine_type="Coal Open Cast Mine", target_day=None):
    if not hourly:
        return {"max_temp": "—", "min_temp": "—", "total_rain": 0, "max_pop": 0, "condition": "—", "humidity": 0, "slabs": [], "avg_wind": 0, "min_vis": 10}
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
    return {
        "max_temp": round(max(temps), 1) if temps else "—",
        "min_temp": round(min(temps), 1) if temps else "—",
        "total_rain": total,
        "max_pop": max_pop_val,
        "condition": condition_str(total, descs, max_pop_val),
        "humidity": round(sum(hums) / len(hums), 1) if hums else 0,
        "cloud": round(sum(clouds) / len(clouds), 0) if clouds else None,
        "avg_wind": round(sum(winds) / len(winds), 1) if winds else 0,
        "min_vis": round(min(viss), 1) if viss else 10,
        "slabs": build_slabs(hourly, is_today=is_today),
    }


def smart_rec(ds, slabs, target_day, mine_type="Coal Open Cast Mine"):
    rain = ds["total_rain"]
    mwind = ds.get("max_wind", ds.get("avg_wind", 0))
    mvis = ds["min_vis"]
    pop = ds["max_pop"]
    has_l = any(s["lightning"] for s in slabs)
    rain_sl = [s for s in slabs if s["mm"] > 0]
    heavy_sl = [s for s in slabs if s["mm"] >= RAIN_HEAVY]
    mod_sl = [s for s in slabs if RAIN_MOD <= s["mm"] < RAIN_HEAVY]
    today = now_ist().date()
    dlabel = "Today" if target_day == today else target_day.strftime("A")
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
        hw = heavy_sl[0]["label"]
        hp = heavy_sl[0]["pop"]
        parts.append(f"Heavy rainfall totaling {rain} mm is expected {dlabel.lower()}, peaking around {hw} ({hp}% probability).")
        if pop < 50:
            parts.append(f"Despite moderate probability ({pop}%), rainfall intensity is high. Prepare drainage but consider proceeding with morning operations before {hw.split('–')[0].strip()}.")
        if "Coal" in mine_type:
            parts.append("Pit drainage must be inspected before morning shift. Bench and haul road surfaces will be severely impacted; mandatory post-rain ground assessment required before resuming OB removal, excavator, and dozer work. Deploy coal stockpile covers.")
        elif "Underground" in mine_type:
            parts.append("Incline mouth and shaft collar drainage must be inspected before morning shift. Verify dewatering pump capacity and berm integrity before resuming drilling, blasting, or hoisting operations.")
        else:
            parts.append("Pit drainage must be inspected before morning shift. Bench and haul road surfaces will be severely impacted; mandatory post-rain ground assessment required before resuming OB removal, excavator, and dozer work. Deploy ore stockpile covers.")
    elif mod_sl:
        first = rain_sl[0]["label"]
        last = rain_sl[-1]["label"]
        fp = rain_sl[0]["pop"]
        lp = rain_sl[-1]["pop"]
        first_start = first.split("–")[0].strip() if "–" in first else first.split("-")[0].strip()
        last_end = last.split("–")[1].strip() if "–" in last else last.split("-")[1].strip()
        time_range = f"{first_start} – {last_end}"
        if pop >= 15:
            parts.append(f"Moderate rainfall of {rain} mm is forecast from {time_range} with probability ranging {fp}–{lp}%.")
        else:
            parts.append(f"Moderate rainfall of {rain} mm is forecast from {time_range}.")
        if pop < 15:
            parts.append("Intermittent showers expected. Surface impact minimal; operations can continue with standard wet-weather protocols.")
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
        first = rain_sl[0]["label"]
        last = rain_sl[-1]["label"]
        fp = rain_sl[0]["pop"]
        first_start = first.split("–")[0].strip() if "–" in first else first.split("-")[0].strip()
        last_end = last.split("–")[1].strip() if "–" in last else last.split("-")[1].strip()
        time_range = f"{first_start} – {last_end}"
        parts.append(f"Light rainfall of {rain} mm is expected {time_range} ({fp}% probability).")
        if pop < 35:
            parts.append(f"Low probability ({pop}%) indicates intermittent drizzle. Surface impact minimal; operations can continue with standard wet-weather protocols.")
        elif pop > 60:
            parts.append(f"Moderate-to-high probability ({pop}%) suggests sustained light rain. Expect haul road surface degradation; deploy grader for maintenance.")
        else:
            parts.append("Operational impact is minimal. Inspect blast area for surface water before charging holes.")
    elif rain >= 0.5 and pop < 15:
        if rain_sl:
            first = rain_sl[0]["label"]
            last = rain_sl[-1]["label"]
            first_start = first.split("–")[0].strip() if "–" in first else first.split("-")[0].strip()
            last_end = last.split("–")[1].strip() if "–" in last else last.split("-")[1].strip()
            time_range = f"{first_start} – {last_end}"
            parts.append(f"Light rainfall of {rain} mm is forecast {time_range}.")
        else:
            parts.append(f"Light rainfall of {rain} mm is forecast {dlabel.lower()}.")
        parts.append(f"Low probability ({pop}%) of {rain} mm precipitation. Standard operations with minimal rain gear standby recommended.")
    elif rain > 0 and rain < 0.5 and pop > 0 and pop < 15:
        parts.append(f"Trace precipitation ({rain} mm) may occur {dlabel.lower()} with only {pop}% probability. It may rain briefly or may remain completely dry.")
        parts.append("Operational impact is expected to be negligible. Standard operations may proceed, with minimal rain gear standby as precaution.")
    elif pop >= 15 and not rain_sl:
        parts.append(f"{dlabel} is expected to remain largely dry, though there is a {pop}% chance of brief, isolated drizzle that may not register on gauges.")
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
            parts.append(f"Wind speeds up to {mwind} km/h will increase hoisting time and restrict crane slewing near the shaft collar.")
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
        pop = int(sorted(pops)[int(len(pops) * 0.75)] if pops else 0)
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
    return None


def operational_window_optimizer(slabs, min_vis=5.0, max_wind=30, max_rain=1.0):
    safe_windows = []
    current_start = None
    current_duration = 0
    for s in slabs:
        is_safe = s["vis"] >= min_vis and s["wind"] <= max_wind and s["mm"] <= max_rain and not s["lightning"]
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
    now = now_ist()
    max_dbz = max((m["dbz"] for m in mc), default=1) or 1
    bars = ""
    for m in mc:
        dbz = m["dbz"]
        t = (now + timedelta(minutes=m["minute"])).strftime("%H:%M")
        c = (
            "#F1F5F9"
            if dbz == 0 or not m["is_precip"]
            else "#BFDBFE"
            if dbz < 15
            else "#3B82F6"
            if dbz < 25
            else "#1D4ED8"
            if dbz < 35
            else "#D97706"
            if dbz < 45
            else "#DC2626"
        )
        ht = max(4, int(28 * dbz / max_dbz))
        bars += f'<div style="display:inline-block;width:4px;height:{ht}px;background:{c};border-radius:1px;margin-right:1px;vertical-align:bottom" title="{t} - {dbz} dBZ"></div>'
    lbls = ""
    for m in mc:
        if m["minute"] % 30 == 0:
            t = (now + timedelta(minutes=m["minute"])).strftime("%H:%M")
            lbls += f'<span style="display:inline-block;width:120px;font-size:0.65rem;color:#94A3B8">{t}</span>'
    st.markdown(
        f'<div class="wim-mc"><div class="wim-mc-title">Minute-by-Minute Precipitation — Next 2 Hours AccuWeather Radar</div><div style="white-space:nowrap;display:flex;align-items:flex-end;gap:0;">{bars}</div><div style="white-space:nowrap;margin-top:6px;">{lbls}</div></div>',
        unsafe_allow_html=True,
    )


def render_hourly_table(hourly, target_day):
    if not hourly:
        st.markdown('<div class="wim-alert wim-alert-none">No hourly data available.</div>', unsafe_allow_html=True)
        return
    today = now_ist().date()
    istnowh = now_ist().replace(minute=0, second=0, microsecond=0)
    rows = []
    seenhours = set()
    for hk, d in sorted(hourly, key=lambda x: x[0]):
        hkey = hk.strftime("%Y-%m-%d %H:00")
        if hkey in seenhours:
            continue
        seenhours.add(hkey)
        if target_day == today and hk < istnowh:
            continue
        mm = d["rain_mm"]
        wind = d["wind_kmh"]
        vis = d["vis_km"]
        pop = d["pop"]
        temp = d["temp"]
        hum = d["humidity"]
        light = d["lightning"]
        cloud = d.get("cloud", 0)
        hlbl = hk.strftime("%I:%M %p")
        if light or mm >= RAIN_HEAVY or vis <= VIS_STOP or wind >= WIND_STOP:
            rowcls = "hour-row-alert"
        elif mm >= RAIN_MOD or vis <= VIS_CAUTION or wind >= WIND_CAUTION:
            rowcls = "hour-row-heavy"
        elif mm > 0:
            rowcls = "hour-row-rain"
        else:
            rowcls = ""
        impact = mining_impact_html(mm, wind, vis, light)
        rows.append(
            f'<tr class="{rowcls}"><td style="font-weight:600;color:#334155;white-space:nowrap">{hlbl}</td><td>{rain_badge_html(mm)}</td><td>{pop:.0f}%</td><td>{temp}°C</td><td>{hum}%</td><td>{int(cloud)}%</td><td>{wind} km/h</td><td>{vis} km</td><td>{"Alert" if light else ""}</td><td>{impact}</td></tr>'
        )
    st.markdown(
        '<div style="overflow-x:auto"><table class="wim-table"><thead><tr><th>Hour</th><th>Rainfall</th><th>Rain Prob.</th><th>Temp</th><th>Humidity</th><th>Cloud</th><th>Wind</th><th>Visibility</th><th>Lightning</th><th>Mining Impact</th></tr></thead><tbody>' + "".join(rows) + "</tbody></table></div>",
        unsafe_allow_html=True,
    )


def render_weekly(by_day, days, site_type):
    today = now_ist().date()
    cols = st.columns(min(days, 7))
    for i in range(min(days, 7)):
        d = today + timedelta(days=i)
        lbl = "Today" if i == 0 else "Tomorrow" if i == 1 else d.strftime("%a")
        with cols[i]:
            if d not in by_day:
                st.markdown(f'<div class="wim-day"><div class="wim-day-label">{lbl}</div><div class="wim-day-date">{d.strftime("%d %b")}</div><div style="color:#94A3B8;font-size:0.75rem;margin-top:8px;">No data</div></div>', unsafe_allow_html=True)
                continue
            ds = day_summary(by_day[d], site_type, target_day=d)
            flag = "flag-clear"
            fcss = "Clear"
            rain = ds["total_rain"]
            hasl = any(x[1]["lightning"] for x in by_day[d])
            if rain >= 15:
                flag, fcss = "flag-heavy", "Heavy Rain"
            elif rain >= 5:
                flag, fcss = "flag-moderate", "Moderate Risk"
            elif rain >= 1.5:
                flag, fcss = "flag-light", "Light Rain"
            elif rain >= 0.5:
                flag, fcss = "flag-drizzle", "Drizzle"
            elif hasl:
                flag, fcss = "flag-lightning", "Lightning Risk"
            st.markdown(
                f'<div class="wim-day"><div class="wim-day-label">{lbl}</div><div class="wim-day-date">{d.strftime("%d %b")}</div><div class="wim-day-cond">{ds["condition"]}</div><div class="wim-day-rain">{rain:.1f} mm</div><div class="wim-day-temp">{ds["min_temp"]} / {ds["max_temp"]}°C</div><div class="wim-day-flag {flag}">{fcss}</div></div>',
                unsafe_allow_html=True,
            )


def render_sidebar(sites):
    names = [s["name"] for s in sites]
    st.markdown('<p style="font-size:0.7rem;font-weight:800;letter-spacing:0.1em;text-transform:uppercase;color:#94A3B8;">Mine Sites</p>', unsafe_allow_html=True)
    for site in sites:
        isactive = site["name"] == st.session_state.active_site
        label = f"{'●' if isactive else '○'} {site['name']} — {site['lat']:.3f}°N, {site['lon']:.3f}°E"
        btntype = "primary" if isactive else "secondary"
        if st.button(label, key=f"site_sel_{site['name']}", use_container_width=True, type=btntype):
            st.session_state.active_site = site["name"]
            st.rerun()
    st.markdown('<hr style="border:none;border-top:1px solid #E2E8F0;margin:14px 0;">', unsafe_allow_html=True)
    days = st.slider("Forecast days", 2, 7, 7, label_visibility="collapsed")
    st.markdown('<hr style="border:none;border-top:1px solid #E2E8F0;margin:14px 0;">', unsafe_allow_html=True)
    activeobj = next((s for s in sites if s["name"] == st.session_state.active_site), None)
    with st.expander("Edit selected site", expanded=False):
        if activeobj and activeobj.get("builtin"):
            st.info(f"{activeobj['name']} is a built-in site and cannot be edited.")
        elif activeobj:
            with st.form("edit_site_form"):
                ename = st.text_input("Name", value=activeobj["name"])
                ec1, ec2 = st.columns(2)
                elat = ec1.number_input("Lat", value=float(activeobj["lat"]), format="%.6f")
                elon = ec2.number_input("Lon", value=float(activeobj["lon"]), format="%.6f")
                epwd = st.text_input("Admin password", type="password", placeholder="Password")
                if st.form_submit_button("Save changes", use_container_width=True):
                    if epwd != ADMIN_PASSWORD:
                        st.error("Incorrect password.")
                    elif not ename.strip():
                        st.error("Name required.")
                    else:
                        update_site(activeobj["name"], ename.strip(), elat, elon)
                        st.session_state.active_site = ename.strip()
                        st.cache_data.clear()
                        st.success("Updated.")
                        st.rerun()
    with st.expander("＋ Add new site", expanded=False):
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
        with st.expander("🗑️ Remove site", expanded=False):
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
    with st.expander("⭐ Set default site on load", expanded=False):
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
    st.markdown('<hr style="border:none;border-top:1px solid #E2E8F0;margin:14px 0;">', unsafe_allow_html=True)
    st.caption(f"Font {'ok' if _FONT_LOADED else 'missing'} · Logo {'ok' if _LOGO_LOADED else 'missing'}")
    return days


st.markdown(
    f'<div class="wim-nav"><div class="wim-nav-left">{LOGO_HTML}<div class="wim-nav-sep"></div><div><div class="wim-nav-title">Adani Natural Resources</div><div class="wim-nav-sub">WIM — Weather Intelligence Mining</div></div></div><div style="font-size:0.75rem;color:#94A3B8;">{now_ist().strftime("%d %b %Y, %I:%M:%S %p IST")}</div></div><div class="wim-nav-spacer"></div>',
    unsafe_allow_html=True,
)

sites = load_sites()
site_names = [s["name"] for s in sites]
site_param = st.query_params.get("site") if hasattr(st, "query_params") else None
if isinstance(site_param, list):
    site_param = site_param[0]
if site_param in site_names:
    st.session_state.active_site = site_param
elif st.session_state.active_site not in site_names and site_names:
    st.session_state.active_site = site_names[0]

picker_col, main_col = st.columns([1, 5])
with picker_col:
    idx = site_names.index(st.session_state.active_site) if st.session_state.active_site in site_names else 0
    pick = st.selectbox("Select site", site_names, index=idx, label_visibility="collapsed", key="sitepicker")
    st.session_state.active_site = pick
    st.caption("Mine Sites")
    days = st.slider("Forecast days", 2, 7, 7)

active = next((s for s in sites if s["name"] == st.session_state.active_site), None)
if not active:
    st.error("Site not found.")
    st.stop()

with main_col:
    st.markdown(f'<div class="wim-site-name">{active["name"]}</div><div class="wim-site-coord">{active["lat"]:.6f}°N, {active["lon"]:.6f}°E</div>', unsafe_allow_html=True)

by_day, mc, src_status = build_forecast(active["lat"], active["lon"], days=days)

if not by_day:
    st.error("No forecast data could be loaded from any source.")
    st.stop()

st.markdown('<div class="wim-section">7-Day Outlook</div>', unsafe_allow_html=True)
render_weekly(by_day, days, active.get("type", "Coal Open Cast Mine"))

st.markdown('<div class="wim-section">Hourly Details</div>', unsafe_allow_html=True)
first_day = sorted(by_day.keys())[0]
render_hourly_table(by_day[first_day], first_day)

st.markdown('<div class="wim-section">Summary</div>', unsafe_allow_html=True)
summary = day_summary(by_day[first_day], active.get("type", "Coal Open Cast Mine"), target_day=first_day)
st.write(f"Condition: {summary['condition']}")
st.write(f"Total rain: {summary['total_rain']} mm")
st.write(f"Wind: {summary['avg_wind']} km/h")
st.write(f"Visibility: {summary['min_vis']} km")

slabs = summary["slabs"]
rec = smart_rec(summary, slabs, first_day, active.get("type", "Coal Open Cast Mine"))
st.markdown(f'<div class="wim-alert wim-alert-none">{rec}</div>', unsafe_allow_html=True)

if first_day == now_ist().date() and mc:
    st.markdown('<div class="wim-section">Radar Next 2 Hours</div>', unsafe_allow_html=True)
    render_mc(mc)

acc = rain_accum(by_day[first_day], target_day=first_day)
st.markdown('<div class="wim-section">Rainfall Accumulation</div>', unsafe_allow_html=True)
cols = st.columns(len(acc))
for c, (h, (mm, pop)) in zip(cols, acc.items()):
    with c:
        st.write(f"{h}h")
        st.write(f"{mm} mm")
        st.write(f"{pop}%")

trend = rain_intensity_trend(slabs)
if trend:
    st.markdown(f'<div class="wim-alert wim-alert-none">{trend}</div>', unsafe_allow_html=True)

opt = operational_window_optimizer(slabs)
st.markdown(f'<div class="wim-alert wim-alert-none">{opt}</div>', unsafe_allow_html=True)

site_type = active.get("type", "Coal Open Cast Mine")
if "Underground" in site_type:
    adv = underground_advisories(slabs, by_day[first_day], site_type)
else:
    adv = equipment_specific_advisories(slabs, by_day[first_day], site_type)
if adv:
    st.markdown('<div class="wim-section">Equipment Advisories</div>', unsafe_allow_html=True)
    for a in adv:
        st.markdown(f'<div class="wim-alert wim-alert-none">{a}</div>', unsafe_allow_html=True)

dust = dust_risk_index(slabs, by_day[first_day])
if dust:
    st.markdown(f'<div class="wim-alert wim-alert-none">{dust}</div>', unsafe_allow_html=True)

fog = fog_dew_prediction(by_day[first_day], first_day)
if fog:
    st.markdown(f'<div class="wim-alert wim-alert-none">{fog}</div>', unsafe_allow_html=True)

soil = soil_moisture_forecast(slabs)
if soil:
    st.markdown(f'<div class="wim-alert wim-alert-none">{soil}</div>', unsafe_allow_html=True)

worker = worker_safety_index(by_day[first_day], slabs)
if worker:
    st.markdown(f'<div class="wim-alert wim-alert-none">{worker}</div>', unsafe_allow_html=True)

st.markdown('<div class="wim-section">Day-wise Weather Conditions</div>', unsafe_allow_html=True)
render_weekly(by_day, days, active.get("type", "Coal Open Cast Mine"))

fail = {k: v for k, v in src_status.items() if v != "ok"}
if fail:
    st.info("Some sources were unavailable: " + ", ".join(fail.keys()))

st.caption(f"Sources: {' · '.join([k for k, v in src_status.items() if v == 'ok'])} • © Adani Natural Resources {now_ist().year}")
