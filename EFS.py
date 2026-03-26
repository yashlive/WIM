import os
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
import pytz
import collections
import streamlit as st
import pandas as pd

# Load environment variables from .env file
load_dotenv()

# Page configuration
st.set_page_config(
    page_title="Mining Weather Forecast",
    page_icon="⛏️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .mine-name {
        font-size: 1.8rem;
        font-weight: bold;
        color: #2c3e50;
        margin-top: 1rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
    .alert-high {
        background-color: #ffebee;
        border-left: 5px solid #f44336;
        padding: 1rem;
        margin: 0.5rem 0;
    }
    .alert-moderate {
        background-color: #fff3e0;
        border-left: 5px solid #ff9800;
        padding: 1rem;
        margin: 0.5rem 0;
    }
    .alert-low {
        background-color: #e8f5e9;
        border-left: 5px solid #4caf50;
        padding: 1rem;
        margin: 0.5rem 0;
    }
    .slab-card {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        border-radius: 0.5rem;
        padding: 1rem;
        margin: 0.5rem 0;
    }
</style>
""", unsafe_allow_html=True)

# API Keys
OPENWEATHER_KEY = os.getenv("OPENWEATHER_API_KEY")
OPENMETEO_KEY = os.getenv("OPENMETEO_API_KEY")
TOMORROWIO_KEY = os.getenv("TOMORROW_API_KEY")
ACCUWEATHER_KEY = os.getenv("ACCUWEATHER_API_KEY")

# Mine locations with coordinates and AccuWeather location keys
MINE_LOCATIONS = [
    {"name": os.getenv("NAME1"), "lat": float(os.getenv("LAT1")), "lon": float(os.getenv("LON1")), 
     "accuweather_location_key": os.getenv("LOCATION_KEY1")},
    {"name": os.getenv("NAME2"), "lat": float(os.getenv("LAT2")), "lon": float(os.getenv("LON2")), 
     "accuweather_location_key": os.getenv("LOCATION_KEY2")},
    {"name": os.getenv("NAME3"), "lat": float(os.getenv("LAT3")), "lon": float(os.getenv("LON3")), 
     "accuweather_location_key": os.getenv("LOCATION_KEY3")},
    {"name": os.getenv("NAME4"), "lat": float(os.getenv("LAT4")), "lon": float(os.getenv("LON4")), 
     "accuweather_location_key": os.getenv("LOCATION_KEY4")},
    {"name": os.getenv("NAME5"), "lat": float(os.getenv("LAT5")), "lon": float(os.getenv("LON5")), 
     "accuweather_location_key": os.getenv("LOCATION_KEY5")},
]

# Timezone definitions
IST = pytz.timezone('Asia/Kolkata')
UTC = pytz.utc
REQUEST_TIMEOUT = 10

# Threshold values for alerts
WIND_ALERT_THRESHOLD_KMH = 30
VISIBILITY_ALERT_THRESHOLD_KM = 1.0
MIN_RAINFALL_FOR_SLAB_DISPLAY_MM = 0.6
MAX_SLABS_TO_SHOW = 6


def get_rain_type(mm, is_2hr_slab=False, overall_description=None):
    """Categorize rainfall amount into descriptive types with icons"""
    if is_2hr_slab:
        if mm >= 8: return "very heavy rain (torrential)"
        elif mm >= 5: return "heavy rain"
        elif mm >= 1.5: return "moderate rain"
        elif mm >= 0.3: return "light rain"
        elif mm > 0: return "drizzle"
        else: return "no rain"
    else:
        if mm >= 25: return "Very Heavy Rain & Storm ⛈️"
        elif mm >= 15: return "Heavy Rain 🌧️"
        elif mm >= 5: return "Moderate Rain ☔"
        elif mm >= 1: return "Light Rain 🌦️"
        elif mm > 0: return "Drizzle 💧"
        else:
            if overall_description:
                desc_lower = overall_description.lower()
                if "clear" in desc_lower or "sun" in desc_lower: return "Sunny ☀️"
                elif "cloud" in desc_lower or "overcast" in desc_lower: return "Cloudy ☁️"
                elif "fog" in desc_lower or "mist" in desc_lower: return "Foggy 🌫️"
                elif "thunderstorm" in desc_lower or "storm" in desc_lower: return "Thunderstorm ⚡"
                elif "rain" in desc_lower: return "Rainy ☔"
            return "No Rain ☀️"


def get_production_status(total_rain_mm, slabs):
    """Determine mining production impact based on rainfall and hazardous conditions"""
    impact_level = "Low"
    status_msg = "Normal operations, minor impact possible"
    
    if total_rain_mm >= 15:
        impact_level = "High"
        status_msg = "Production may be significantly impacted due to heavy rainfall."
    elif total_rain_mm >= 5:
        impact_level = "Moderate"
        status_msg = "Proceed with caution, production may be impacted due to moderate rainfall."
    
    has_lightning = False
    has_high_wind = False
    has_low_visibility = False
    
    for slab in slabs:
        if slab['lightning']:
            has_lightning = True
        if slab['wind_speed'] >= WIND_ALERT_THRESHOLD_KMH:
            has_high_wind = True
        if slab['visibility_km'] <= VISIBILITY_ALERT_THRESHOLD_KM:
            has_low_visibility = True
    
    if has_lightning:
        if impact_level != "High":
            impact_level = "High"
            status_msg = "Blasting/open-pit operations likely impacted due to lightning."
        else:
            status_msg += " Additionally, lightning expected."
    
    if has_high_wind:
        if impact_level == "Low":
            impact_level = "Moderate"
            status_msg = "Caution advised due to high winds, potential dust/equipment issues."
        elif "wind" not in status_msg.lower():
            status_msg += " High winds also expected."
    
    if has_low_visibility:
        if impact_level == "Low":
            impact_level = "Moderate"
            status_msg = "Caution advised due to low visibility, impacting vehicle movement."
        elif "visibility" not in status_msg.lower():
            status_msg += " Low visibility also expected."
    
    return (impact_level, status_msg)


def utc_to_ist(utc_dt):
    """Convert UTC datetime to IST timezone"""
    if utc_dt.tzinfo is None:
        utc_dt = UTC.localize(utc_dt)
    return utc_dt.astimezone(IST)


def get_weather_description_from_wmo_open_meteo(code):
    """Map Open-Meteo WMO weather codes to readable descriptions"""
    weather_codes = {
        0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
        45: "Fog", 48: "Depositing rime fog",
        51: "Drizzle: Light", 53: "Drizzle: Moderate", 55: "Drizzle: Dense",
        56: "Freezing Drizzle: Light", 57: "Freezing Drizzle: Dense",
        61: "Rain: Light", 63: "Rain: Moderate", 65: "Rain: Heavy",
        66: "Freezing Rain: Light", 67: "Freezing Rain: Heavy",
        71: "Snow fall: Slight", 73: "Snow fall: Moderate", 75: "Snow fall: Heavy",
        77: "Snow grains",
        80: "Rain showers: Slight", 81: "Rain showers: Moderate", 82: "Rain showers: Violent",
        85: "Snow showers: Slight", 86: "Snow showers: Heavy",
        95: "Thunderstorm: Slight or moderate",
        96: "Thunderstorm with slight hail", 99: "Thunderstorm with heavy hail"
    }
    return weather_codes.get(code, "Unknown")


def get_weather_description_from_wmo_tomorrow_io(code):
    """Map Tomorrow.io weather codes to readable descriptions"""
    tomorrow_io_weather_codes = {
        0: "Unknown", 1000: "Clear, Sunny", 1001: "Cloudy", 1100: "Mostly Clear",
        1101: "Partly Cloudy", 1102: "Mostly Cloudy", 2000: "Fog", 2100: "Light Fog",
        3000: "Light Wind", 3001: "Wind", 3002: "Strong Wind", 4000: "Drizzle",
        4001: "Rain", 4200: "Light Rain", 4201: "Heavy Rain", 5000: "Light Snow",
        5001: "Snow", 5100: "Heavy Snow", 5101: "Freezing Drizzle",
        6000: "Freezing Drizzle", 6001: "Freezing Rain", 6200: "Light Freezing Rain",
        6201: "Heavy Freezing Rain", 7000: "Light Ice Pellets", 7001: "Ice Pellets",
        7100: "Heavy Ice Pellets", 8000: "Thunderstorm"
    }
    return tomorrow_io_weather_codes.get(code, "Unknown")


@st.cache_data(ttl=1800)
def fetch_openweather_forecast(lat, lon):
    """Fetch hourly weather forecast from OpenWeatherMap (cached for 30 min)"""
    if not OPENWEATHER_KEY:
        return None
    
    try:
        url = (f"https://api.openweathermap.org/data/3.0/onecall?lat={lat}&lon={lon}"
               f"&units=metric&exclude=minutely,daily,alerts&appid={OPENWEATHER_KEY}")
        response = requests.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException:
        return None


@st.cache_data(ttl=1800)
def fetch_open_meteo_forecast(lat, lon):
    """Fetch hourly weather forecast from Open-Meteo (cached for 30 min)"""
    try:
        url = (f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
               f"&hourly=temperature_2m,precipitation,weather_code,wind_speed_10m,precipitation_probability,visibility"
               f"&forecast_days=2&timezone=Asia%2FKolkata")
        response = requests.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException:
        return None


@st.cache_data(ttl=1800)
def fetch_tomorrow_io_forecast(lat, lon):
    """Fetch weather forecast from Tomorrow.io (cached for 30 min)"""
    if not TOMORROWIO_KEY:
        return None
    
    try:
        url = (f"https://api.tomorrow.io/v4/weather/forecast?location={lat},{lon}"
               f"&units=metric&apikey={TOMORROWIO_KEY}")
        response = requests.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException:
        return None


@st.cache_data(ttl=1800)
def fetch_accuweather_daily_forecast(location_key):
    """Fetch daily weather forecast from AccuWeather (cached for 30 min)"""
    if not ACCUWEATHER_KEY or not location_key:
        return None
    
    try:
        url = f"https://dataservice.accuweather.com/forecasts/v1/daily/5day/{location_key}?apikey={ACCUWEATHER_KEY}&details=true&metric=true"
        response = requests.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException:
        return None


def get_daily_summary_and_slabs(hourly_data_list):
    """Process hourly data to generate daily summary and 2-hour precipitation slabs"""
    if not hourly_data_list:
        return {"max_temp": "N/A", "min_temp": "N/A", "total_rain": 0, "total_rain_pop": 0, 
                "weather_desc": "N/A", "slabs": []}
    
    max_temp = float("-inf")
    min_temp = float("inf")
    total_rain_overall = 0
    all_weather_descs = []
    all_hourly_pops = []
    
    SLAB_DEFINITIONS = [
        (0, 2, "12:30 AM to 02:30 AM"), (2, 4, "02:30 AM to 04:30 AM"),
        (4, 6, "04:30 AM to 06:30 AM"), (6, 8, "06:30 AM to 08:30 AM"),
        (8, 10, "08:30 AM to 10:30 AM"), (10, 12, "10:30 AM to 12:30 PM"),
        (12, 14, "12:30 PM to 02:30 PM"), (14, 16, "02:30 PM to 04:30 PM"),
        (16, 18, "04:30 PM to 06:30 PM"), (18, 20, "06:30 PM to 08:30 PM"),
        (20, 22, "08:30 PM to 10:30 PM"), (22, 2, "10:30 PM to 12:30 AM (Next Day)"),
    ]
    
    slabs_data_raw = collections.defaultdict(lambda: {
        "rain_mm": 0, "pop": [], "wind_speed": [], "visibility_km": [], 
        "lightning": [], "descs": [], "hours_covered": 0
    })
    
    for dt_ist, data in hourly_data_list:
        max_temp = max(max_temp, data['temp'])
        min_temp = min(min_temp, data['temp'])
        total_rain_overall += data['rain_mm']
        all_weather_descs.append(data['description'])
        all_hourly_pops.append(data['pop'])
        
        hour_in_day = dt_ist.hour
        slab_key = None
        
        for start_h, end_h, display_name in SLAB_DEFINITIONS:
            if start_h == 22 and end_h == 2:
                if hour_in_day == 22 or hour_in_day == 23:
                    slab_key = (start_h, end_h, display_name)
                    break
            elif start_h < end_h:
                if hour_in_day >= start_h and hour_in_day < end_h:
                    slab_key = (start_h, end_h, display_name)
                    break
        
        if slab_key:
            slabs_data_raw[slab_key]["rain_mm"] += data['rain_mm']
            slabs_data_raw[slab_key]["pop"].append(data['pop'])
            slabs_data_raw[slab_key]["wind_speed"].append(data['wind_speed'])
            slabs_data_raw[slab_key]["visibility_km"].append(data.get('visibility_km', 10))
            slabs_data_raw[slab_key]["descs"].append(data['description'])
            slabs_data_raw[slab_key]["lightning"].append(data['lightning'])
            slabs_data_raw[slab_key]["hours_covered"] += 1
    
    candidate_slabs = []
    for slab_key, slab_data in slabs_data_raw.items():
        if slab_data["hours_covered"] > 0:
            avg_pop = sum(slab_data["pop"]) / len(slab_data["pop"]) if slab_data["pop"] else 0
            avg_wind = sum(slab_data["wind_speed"]) / len(slab_data["wind_speed"]) if slab_data["wind_speed"] else 0
            avg_vis = sum(slab_data["visibility_km"]) / len(slab_data["visibility_km"]) if slab_data["visibility_km"] else 10.0
            main_desc = collections.Counter(slab_data["descs"]).most_common(1)[0][0] if slab_data["descs"] else get_rain_type(slab_data["rain_mm"], is_2hr_slab=True)
            explicit_lightning_in_desc = any("thunder" in d.lower() or "lightning" in d.lower() for d in slab_data["descs"])
            
            if slab_data["rain_mm"] >= MIN_RAINFALL_FOR_SLAB_DISPLAY_MM:
                candidate_slabs.append({
                    "time_range": slab_key[2],
                    "sort_key": slab_data["rain_mm"] + (avg_pop / 100),
                    "prob": int(round(avg_pop, 0)),
                    "mm": round(slab_data["rain_mm"], 1),
                    "type": get_rain_type(slab_data["rain_mm"], is_2hr_slab=True),
                    "wind_speed": round(avg_wind, 1),
                    "visibility_km": round(avg_vis, 1),
                    "lightning": any(slab_data["lightning"]) or explicit_lightning_in_desc,
                    "description": main_desc
                })
    
    candidate_slabs.sort(key=lambda x: (-x["sort_key"], x["time_range"]))
    
    final_slabs = []
    seen_time_ranges = set()
    for slab in candidate_slabs:
        if slab["time_range"] not in seen_time_ranges:
            final_slabs.append(slab)
            seen_time_ranges.add(slab["time_range"])
            if len(final_slabs) >= MAX_SLABS_TO_SHOW:
                break
    
    slab_order_map = {s[2]: idx for idx, s in enumerate(SLAB_DEFINITIONS)}
    final_slabs.sort(key=lambda x: slab_order_map.get(x["time_range"], float('inf')))
    
    overall_raw_desc = collections.Counter(all_weather_descs).most_common(1)[0][0] if all_weather_descs else "N/A"
    overall_weather_desc_with_icon = get_rain_type(total_rain_overall, is_2hr_slab=False, overall_description=overall_raw_desc)
    max_hourly_pop = max(all_hourly_pops) if all_hourly_pops else 0
    
    return {
        "max_temp": round(max_temp, 1) if max_temp != float("-inf") else "N/A",
        "min_temp": round(min_temp, 1) if min_temp != float("inf") else "N/A",
        "total_rain": round(total_rain_overall, 1),
        "total_rain_pop": int(round(max_hourly_pop, 0)),
        "weather_desc": overall_weather_desc_with_icon,
        "slabs": final_slabs
    }


def fetch_consolidated_forecast(lat, lon, mine_name, accuweather_location_key):
    """Fetch and consolidate weather data from multiple APIs"""
    ow_data = fetch_openweather_forecast(lat, lon)
    om_data = fetch_open_meteo_forecast(lat, lon)
    tm_data = fetch_tomorrow_io_forecast(lat, lon)
    
    if not any([ow_data, om_data, tm_data]):
        return None
    
    hourly_consolidated = {}
    
    # Process OpenWeatherMap hourly data
    if ow_data and "hourly" in ow_data:
        for entry in ow_data["hourly"]:
            dt_utc = datetime.fromtimestamp(entry["dt"], tz=UTC)
            dt_ist = utc_to_ist(dt_utc)
            hour_key = dt_ist.replace(minute=0, second=0, microsecond=0)
            
            if hour_key < datetime.now(IST).replace(minute=0, second=0, microsecond=0) - timedelta(hours=1) or \
               hour_key > datetime.now(IST).replace(minute=0, second=0, microsecond=0) + timedelta(hours=48):
                continue
            
            hourly_consolidated.setdefault(hour_key, {
                'temp': [], 'rain_mm': [], 'pop': [], 'wind_speed': [],
                'visibility_km': [], 'description': [], 'lightning': []
            })
            
            hourly_consolidated[hour_key]['temp'].append(entry["temp"])
            rain_mm = entry.get("rain", {}).get("1h", 0)
            snow_mm = entry.get("snow", {}).get("1h", 0)
            hourly_consolidated[hour_key]['rain_mm'].append(rain_mm + snow_mm)
            hourly_consolidated[hour_key]['pop'].append(entry.get("pop", 0) * 100)
            hourly_consolidated[hour_key]['wind_speed'].append(entry["wind_speed"] * 3.6)
            hourly_consolidated[hour_key]['visibility_km'].append(entry.get("visibility", 10000) / 1000)
            
            if entry.get("weather"):
                hourly_consolidated[hour_key]['description'].append(entry["weather"][0]["description"])
                if 200 <= entry["weather"][0]["id"] < 300:
                    hourly_consolidated[hour_key]['lightning'].append(True)
                else:
                    hourly_consolidated[hour_key]['lightning'].append(False)
            else:
                hourly_consolidated[hour_key]['description'].append("N/A")
                hourly_consolidated[hour_key]['lightning'].append(False)
    
    # Process Open-Meteo hourly data
    if om_data and "hourly" in om_data:
        times = om_data["hourly"]["time"]
        temps = om_data["hourly"]["temperature_2m"]
        precipitations = om_data["hourly"]["precipitation"]
        weather_codes = om_data["hourly"]["weather_code"]
        wind_speeds = om_data["hourly"]["wind_speed_10m"]
        pops = om_data["hourly"]["precipitation_probability"]
        visibilities = om_data["hourly"].get("visibility", [])
        
        for i, time_str in enumerate(times):
            dt_ist = datetime.fromisoformat(time_str).replace(tzinfo=IST)
            hour_key = dt_ist.replace(minute=0, second=0, microsecond=0)
            
            if hour_key < datetime.now(IST).replace(minute=0, second=0, microsecond=0) - timedelta(hours=1) or \
               hour_key > datetime.now(IST).replace(minute=0, second=0, microsecond=0) + timedelta(hours=48):
                continue
            
            hourly_consolidated.setdefault(hour_key, {
                'temp': [], 'rain_mm': [], 'pop': [], 'wind_speed': [],
                'visibility_km': [], 'description': [], 'lightning': []
            })
            
            hourly_consolidated[hour_key]['temp'].append(temps[i])
            hourly_consolidated[hour_key]['rain_mm'].append(precipitations[i])
            hourly_consolidated[hour_key]['pop'].append(pops[i])
            hourly_consolidated[hour_key]['wind_speed'].append(wind_speeds[i])
            hourly_consolidated[hour_key]['visibility_km'].append(visibilities[i]/1000 if visibilities else 10)
            hourly_consolidated[hour_key]['description'].append(get_weather_description_from_wmo_open_meteo(weather_codes[i]))
            
            if weather_codes[i] in [95, 96, 99]:
                hourly_consolidated[hour_key]['lightning'].append(True)
            else:
                hourly_consolidated[hour_key]['lightning'].append(False)
    
    # Process Tomorrow.io hourly data
    if tm_data and "timelines" in tm_data and "hourly" in tm_data["timelines"]:
        for interval in tm_data["timelines"]["hourly"]:
            dt_iso_str = interval["time"]
            dt_utc_naive = datetime.strptime(dt_iso_str, '%Y-%m-%dT%H:%M:%SZ')
            dt_utc_aware = UTC.localize(dt_utc_naive)
            dt_ist = dt_utc_aware.astimezone(IST)
            hour_key = dt_ist.replace(minute=0, second=0, microsecond=0)
            
            if hour_key < datetime.now(IST).replace(minute=0, second=0, microsecond=0) - timedelta(hours=1) or \
               hour_key > datetime.now(IST).replace(minute=0, second=0, microsecond=0) + timedelta(hours=48):
                continue
            
            values = interval["values"]
            
            hourly_consolidated.setdefault(hour_key, {
                'temp': [], 'rain_mm': [], 'pop': [], 'wind_speed': [],
                'visibility_km': [], 'description': [], 'lightning': []
            })
            
            hourly_consolidated[hour_key]['temp'].append(values.get("temperature", 0))
            hourly_consolidated[hour_key]['rain_mm'].append(values.get("precipitationIntensity", 0))
            hourly_consolidated[hour_key]['pop'].append(values.get("precipitationProbability", 0))
            hourly_consolidated[hour_key]['wind_speed'].append(values.get("windSpeed", 0) * 3.6)
            hourly_consolidated[hour_key]['visibility_km'].append(values.get("visibility", 10000) / 1000)
            
            tm_weather_code = values.get("weatherCode")
            if tm_weather_code is not None:
                hourly_consolidated[hour_key]['description'].append(get_weather_description_from_wmo_tomorrow_io(tm_weather_code))
            else:
                hourly_consolidated[hour_key]['description'].append("N/A")
            
            if values.get("lightningStrikeCount", 0) > 0 or tm_weather_code == 8000:
                hourly_consolidated[hour_key]['lightning'].append(True)
            else:
                hourly_consolidated[hour_key]['lightning'].append(False)
    
    # Aggregate consolidated hourly data
    final_hourly_data = []
    sorted_hour_keys = sorted(hourly_consolidated.keys())
    
    for hour_key in sorted_hour_keys:
        aggregated_data = hourly_consolidated[hour_key]
        
        avg_temp = sum(aggregated_data['temp']) / len(aggregated_data['temp']) if aggregated_data['temp'] else 0
        avg_rain = sum(aggregated_data['rain_mm']) / len(aggregated_data['rain_mm']) if aggregated_data['rain_mm'] else 0
        avg_pop = sum(aggregated_data['pop']) / len(aggregated_data['pop']) if aggregated_data['pop'] else 0
        avg_wind_speed = sum(aggregated_data['wind_speed']) / len(aggregated_data['wind_speed']) if aggregated_data['wind_speed'] else 0
        avg_visibility_km = sum(aggregated_data['visibility_km']) / len(aggregated_data['visibility_km']) if aggregated_data['visibility_km'] else 10.0
        
        most_common_desc = collections.Counter(aggregated_data['description']).most_common(1)
        hourly_description = most_common_desc[0][0] if most_common_desc else "N/A"
        has_lightning = any(aggregated_data['lightning'])
        
        final_hourly_data.append((
            hour_key,
            {
                'temp': avg_temp,
                'rain_mm': avg_rain,
                'pop': avg_pop,
                'wind_speed': avg_wind_speed,
                'visibility_km': avg_visibility_km,
                'description': hourly_description,
                'lightning': has_lightning
            }
        ))
    
    # Group hourly data by day
    forecast_by_day = collections.defaultdict(list)
    for dt_ist, data in final_hourly_data:
        day_key = dt_ist.date()
        forecast_by_day[day_key].append((dt_ist, data))
    
    return forecast_by_day


def main():
    """Main Streamlit application"""
    st.markdown('<div class="main-header">⛏️ Mining Weather Forecast Dashboard</div>', unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ Settings")
        
        mine_names = [mine["name"] for mine in MINE_LOCATIONS if mine["name"]]
        selected_mines = st.multiselect(
            "Select Mine Locations",
            mine_names,
            default=mine_names[:1] if mine_names else []
        )
        
        st.markdown("---")
        st.markdown("### 📊 Forecast Info")
        st.info("Data aggregated from:\n- OpenWeatherMap\n- Open-Meteo\n- Tomorrow.io\n- AccuWeather")
        
        if st.button("🔄 Refresh Data"):
            st.cache_data.clear()
            st.rerun()
    
    if not selected_mines:
        st.warning("⚠️ Please select at least one mine location from the sidebar.")
        return
    
    # Display forecast for each selected mine
    for mine_name in selected_mines:
        mine = next((m for m in MINE_LOCATIONS if m["name"] == mine_name), None)
        if not mine:
            continue
        
        st.markdown(f'<div class="mine-name">📍 {mine_name}</div>', unsafe_allow_html=True)
        st.markdown(f"**Coordinates:** Lat {mine['lat']}, Lon {mine['lon']}")
        
        with st.spinner(f"Fetching forecast for {mine_name}..."):
            forecast_by_day = fetch_consolidated_forecast(
                mine["lat"], mine["lon"], mine["name"], mine["accuweather_location_key"]
            )
        
        if not forecast_by_day:
            st.error("❌ Unable to fetch forecast data. Please check API keys and network connectivity.")
            continue
        
        current_date_ist = datetime.now(IST).date()
        
        # Create tabs for Today and Tomorrow
        tab1, tab2 = st.tabs(["📅 Today", "📅 Tomorrow"])
        
        for idx, (tab, day_offset) in enumerate([(tab1, 0), (tab2, 1)]):
            target_day = current_date_ist + timedelta(days=day_offset)
            
            with tab:
                if target_day not in forecast_by_day:
                    st.warning(f"No forecast data available for {target_day.strftime('%d %B, %Y')}")
                    continue
                
                day_hourly_data = forecast_by_day[target_day]
                day_summary = get_daily_summary_and_slabs(day_hourly_data)
                
                st.markdown(f"### {target_day.strftime('%d %B, %Y')}")
                
                # Display metrics in columns
                col1, col2, col3, col4, col5 = st.columns(5)
                
                with col1:
                    st.metric("Weather", day_summary['weather_desc'])
                
                with col2:
                    st.metric("Max Temp", f"{day_summary['max_temp']}°C")
                
                with col3:
                    st.metric("Min Temp", f"{day_summary['min_temp']}°C")
                
                with col4:
                    st.metric("Total Rainfall", f"{day_summary['total_rain']} mm")
                
                with col5:
                    st.metric("Rain Probability", f"{day_summary['total_rain_pop']}%")
                
                # Production Impact Alert
                impact_level, status_msg = get_production_status(day_summary['total_rain'], day_summary['slabs'])
                
                if impact_level == "High":
                    st.markdown(f'<div class="alert-high"><strong>🚨 High Impact:</strong> {status_msg}</div>', unsafe_allow_html=True)
                elif impact_level == "Moderate":
                    st.markdown(f'<div class="alert-moderate"><strong>⚠️ Moderate Impact:</strong> {status_msg}</div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="alert-low"><strong>✅ Low Impact:</strong> {status_msg}</div>', unsafe_allow_html=True)
                
                # Precipitation Slabs
                if day_summary['slabs']:
                    st.markdown("### 🌧️ Precipitation Windows")
                    
                    for slab in day_summary['slabs']:
                        alerts = []
                        if slab['lightning']:
                            alerts.append("⚡ Lightning")
                        if slab['wind_speed'] >= WIND_ALERT_THRESHOLD_KMH:
                            alerts.append(f"💨 High Wind ({slab['wind_speed']} km/h)")
                        if slab['visibility_km'] <= VISIBILITY_ALERT_THRESHOLD_KM:
                            alerts.append(f"👁️ Low Visibility ({slab['visibility_km']} km)")
                        
                        alert_str = " | ".join(alerts) if alerts else "No alerts"
                        
                        st.markdown(f"""
                        <div class="slab-card">
                            <strong>{slab['time_range']}</strong><br>
                            🌧️ {slab['mm']} mm ({slab['type']}) - {slab['prob']}% probability<br>
                            <span style="color: {'#f44336' if alerts else '#4caf50'};">{alert_str}</span>
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    st.info("No significant precipitation expected.")
                
                # Temperature Chart
                if day_hourly_data:
                    st.markdown("### 🌡️ Temperature Trend")
                    temp_data = pd.DataFrame([
                        {"Time": dt.strftime("%H:%M"), "Temperature (°C)": data['temp']}
                        for dt, data in day_hourly_data
                    ])
                    st.line_chart(temp_data.set_index("Time"))
                
                st.markdown("---")
    
    # Footer
    st.markdown("---")
    st.caption(f"Last updated: {datetime.now(IST).strftime('%d %B %Y, %I:%M %p IST')}")


if __name__ == "__main__":
    main()

