import os
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
import pytz
import collections

# Load environment variables from a .env file.
# This allows you to keep sensitive API keys and location data out of your main script.
load_dotenv()

# ------------------ API KEYS ------------------
# Retrieve API keys from environment variables.
OPENWEATHER_KEY = os.getenv("OPENWEATHER_API_KEY")
OPENMETEO_KEY = os.getenv("OPENMETEO_API_KEY") # Open-Meteo typically doesn't need a key for basic forecasts
TOMORROWIO_KEY = os.getenv("TOMORROW_API_KEY")
ACCUWEATHER_KEY = os.getenv("ACCUWEATHER_API_KEY")

# ------------------ MINE LOCATIONS ------------------
# Define mine locations and their corresponding API-specific identifiers.
# 'accuweather_location_key' is crucial for AccuWeather API calls.
MINE_LOCATIONS = [
    {"name": os.getenv("NAME1"), "lat": float(os.getenv("LAT1")), "lon": float(os.getenv("LON1")), "accuweather_location_key": os.getenv("LOCATION_KEY1")},
    {"name": os.getenv("NAME2"), "lat": float(os.getenv("LAT2")), "lon": float(os.getenv("LON2")), "accuweather_location_key": os.getenv("LOCATION_KEY2")},
    {"name": os.getenv("NAME3"), "lat": float(os.getenv("LAT3")), "lon": float(os.getenv("LON3")), "accuweather_location_key": os.getenv("LOCATION_KEY3")},
    {"name": os.getenv("NAME4"), "lat": float(os.getenv("LAT4")), "lon": float(os.getenv("LON4")), "accuweather_location_key": os.getenv("LOCATION_KEY4")},
    {"name": os.getenv("NAME5"), "lat": float(os.getenv("LAT5")), "lon": float(os.getenv("LON5")), "accuweather_location_key": os.getenv("LOCATION_KEY5")},
]

# ------------------ CONSTANTS ------------------
# Define timezones for consistent time handling.
IST = pytz.timezone('Asia/Kolkata') # Indian Standard Time
UTC = pytz.utc # Coordinated Universal Time

REQUEST_TIMEOUT = 10 # Seconds to wait for an API response before timing out.

# Alert thresholds for operational warnings.
WIND_ALERT_THRESHOLD_KMH = 30 # Wind speed in kilometers per hour.
VISIBILITY_ALERT_THRESHOLD_KM = 1.0 # Visibility in kilometers (1 km = 1000 meters).

# Minimum rainfall (mm) for a 2-hour slab to be considered meaningful enough to display.
MIN_RAINFALL_FOR_SLAB_DISPLAY_MM = 0.6 # Slabs with less than this amount will not be shown.
# Maximum number of precipitation slabs to display for readability.
MAX_SLABS_TO_SHOW = 6 

# ------------------ UTILITIES ------------------
def get_rain_type(mm, is_2hr_slab=False, overall_description=None):
    """
    Categorizes rainfall amount into descriptive types (e.g., light, moderate, heavy)
    and adds appropriate icons for display.
    Adjusts categorization based on whether it's for a 2-hour slab or overall daily total.
    """
    if is_2hr_slab:
        # Thresholds for 2-hour precipitation slabs
        if mm >= 8: return "very heavy rain (torrential)"
        elif mm >= 5: return "heavy rain"
        elif mm >= 1.5: return "moderate rain"
        elif mm >= 0.3: return "light rain"
        elif mm > 0: return "drizzle"
        else: return "no rain"
    else:
        # Thresholds and descriptions for overall daily precipitation
        if mm >= 25: return "Very Heavy Rain & Storm ⛈️"
        elif mm >= 15: return "Heavy Rain 🌧️"
        elif mm >= 5: return "Moderate Rain ☔"
        elif mm >= 1: return "Light Rain 🌦️"
        elif mm > 0: return "Drizzle 💧"
        else:
            # If no significant rain, use the most common general weather description for the day.
            if overall_description:
                desc_lower = overall_description.lower()
                if "clear" in desc_lower or "sun" in desc_lower: return "Sunny ☀️"
                elif "cloud" in desc_lower or "overcast" in desc_lower: return "Cloudy ☁️"
                elif "fog" in desc_lower or "mist" in desc_lower: return "Foggy 🌫️"
                elif "thunderstorm" in desc_lower or "storm" in desc_lower: return "Thunderstorm ⚡"
                elif "rain" in desc_lower: return "Rainy ☔" # Fallback for minor rain not caught by higher thresholds
            return "No Rain ☀️" # Default if no rain and no clear description

def get_production_status(total_rain_mm, slabs):
    """
    Determines the potential impact on mining production based on total daily rainfall,
    and also considering high winds, low visibility, and lightning from slabs.
    """
    impact_level = "Low"
    status_msg = "Normal operations, minor impact possible"

    # Rule 1: Impact based on total rainfall
    if total_rain_mm >= 15:
        impact_level = "High"
        status_msg = "Production may be significantly impacted due to heavy rainfall."
    elif total_rain_mm >= 5:
        impact_level = "Moderate"
        status_msg = "Proceed with caution, production may be impacted due to moderate rainfall."

    # Rule 2: Overlay impacts from critical hourly conditions (lightning, high wind, low visibility)
    # Iterate through slabs to find critical conditions
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
            
    # Adjust impact level and message based on critical conditions
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
        elif impact_level == "Moderate" and "wind" not in status_msg.lower():
            status_msg += " High winds also expected."
        elif impact_level == "High" and "wind" not in status_msg.lower():
            status_msg += " High winds also expected."

    if has_low_visibility:
        if impact_level == "Low":
            impact_level = "Moderate"
            status_msg = "Caution advised due to low visibility, impacting vehicle movement."
        elif impact_level == "Moderate" and "visibility" not in status_msg.lower():
            status_msg += " Low visibility also expected."
        elif impact_level == "High" and "visibility" not in status_msg.lower():
            status_msg += " Low visibility also expected."

    return (impact_level, status_msg)


def utc_to_ist(utc_dt):
    """Converts a UTC datetime object to an IST timezone-aware datetime object."""
    if utc_dt.tzinfo is None:
        utc_dt = UTC.localize(utc_dt) # Localize if not already timezone-aware
    return utc_dt.astimezone(IST)

def get_weather_description_from_wmo_open_meteo(code):
    """Maps Open-Meteo WMO weather codes to human-readable descriptions."""
    # This dictionary maps numerical weather codes to clear descriptions.
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
    return weather_codes.get(code, "Unknown Open-Meteo code")

def get_weather_description_from_wmo_tomorrow_io(code):
    """Maps Tomorrow.io weather codes to human-readable descriptions."""
    # This dictionary maps numerical weather codes specific to Tomorrow.io.
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
    return tomorrow_io_weather_codes.get(code, "Unknown Tomorrow.io code")

# ------------------ API FETCH FUNCTIONS ------------------

def fetch_openweather_forecast(lat, lon):
    """Fetches hourly weather forecast data from OpenWeatherMap's One Call API 3.0."""
    if not OPENWEATHER_KEY:
        print("  OpenWeatherMap API Key not set in .env. Skipping OpenWeatherMap data.")
        return None
    try:
        # Uses the One Call API 3.0 endpoint for comprehensive hourly data.
        url = (f"https://api.openweathermap.org/data/3.0/onecall?lat={lat}&lon={lon}"
               f"&units=metric&exclude=minutely,daily,alerts&appid={OPENWEATHER_KEY}")
        response = requests.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status() # Raises an HTTPError for bad responses (4xx or 5xx)
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"  OpenWeatherMap One Call API 3.0 Error for ({lat},{lon}): {e}")
        return None

def fetch_open_meteo_forecast(lat, lon):
    """Fetches hourly weather forecast data from Open-Meteo."""
    try:
        # Corrected: Ensure 'Asia/Kolkata' is spelled correctly without typos.
        url = (f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
               f"&hourly=temperature_2m,precipitation,weather_code,wind_speed_10m,precipitation_probability,visibility"
               f"&forecast_days=2&timezone=Asia%2FKolkata") # Corrected timezone parameter
        response = requests.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"  Open-Meteo API Error for ({lat},{lon}): {e}")
        return None

def fetch_tomorrow_io_forecast(lat, lon):
    """
    Fetches weather forecast data from Tomorrow.io's /weather/forecast endpoint.
    This endpoint is used as /timelines was causing 400 errors.
    """
    if not TOMORROWIO_KEY:
        print("  Tomorrow.io API Key not set in .env. Skipping Tomorrow.io data.")
        return None
    try:
        # Using the /weather/forecast endpoint as it was confirmed working for your key.
        # This endpoint returns data in 'timelines' format within its response.
        url = (f"https://api.tomorrow.io/v4/weather/forecast?location={lat},{lon}"
               f"&units=metric&apikey={TOMORROWIO_KEY}") # No explicit timesteps/fields here, it returns a default set

        response = requests.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"  Tomorrow.io API Error for ({lat},{lon}): {e}")
        return None

def fetch_accuweather_daily_forecast(location_key):
    """
    Fetches DAILY weather forecast data from AccuWeather's /daily/5day endpoint.
    This is used as the hourly endpoint was causing 401 Unauthorized errors.
    """
    if not ACCUWEATHER_KEY:
        print("  AccuWeather API Key not set in .env. Skipping AccuWeather data.")
        return None
    if not location_key:
        print("  AccuWeather Location Key not provided in .env. Skipping AccuWeather data.")
        return None
    try:
        # Using the /daily/5day endpoint. IMPORTANT: Check your AccuWeather API key's product access.
        # This will contribute to daily summaries, not hourly consolidation.
        url = f"https://dataservice.accuweather.com/forecasts/v1/daily/5day/{location_key}?apikey={ACCUWEATHER_KEY}&details=true&metric=true"
        response = requests.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"  AccuWeather Daily Forecast API Error for Location Key {location_key}: {e}")
        return None

# ------------------ DATA PROCESSING AND AGGREGATION ------------------

def get_daily_summary_and_slabs(hourly_data_list):
    """
    Aggregates a list of consolidated hourly forecast data points into:
    - Daily summary metrics (max/min temp, total rain, overall description)
    - Key 2-hour precipitation slabs for detailed alerts.
    """
    if not hourly_data_list:
        return {"max_temp": "N/A", "min_temp": "N/A", "total_rain": 0, "total_rain_pop": 0, "weather_desc": "N/A", "slabs": []}

    max_temp = float("-inf")
    min_temp = float("inf")
    total_rain_overall = 0 # Sum of averaged hourly rains for the day
    all_weather_descs = [] # Collect all hourly descriptions for daily consensus
    all_hourly_pops = [] # Collect all hourly PoPs for daily average PoP
    
    # Corrected SLAB_DEFINITIONS: Ensure chronological order and the "Next Day" slab is last for sorting.
    SLAB_DEFINITIONS = [
        # Night/Early Morning
        (0, 2, "12:30 AM to 02:30 AM"),
        (2, 4, "02:30 AM to 04:30 AM"),
        (4, 6, "04:30 AM to 06:30 AM"),
        # Morning
        (6, 8, "06:30 AM to 08:30 AM"),
        (8, 10, "08:30 AM to 10:30 AM"),
        (10, 12, "10:30 AM to 12:30 PM"),
        # Afternoon
        (12, 14, "12:30 PM to 02:30 PM"),
        (14, 16, "02:30 PM to 04:30 PM"),
        (16, 18, "04:30 PM to 06:30 PM"),
        # Evening/Night
        (18, 20, "06:30 PM to 08:30 PM"),
        (20, 22, "08:30 PM to 10:30 PM"),
        # This special slab is moved to the end to ensure it sorts last chronologically
        (22, 2, "10:30 PM to 12:30 AM (Next Day)"), 
    ]

    slabs_data_raw = collections.defaultdict(lambda: {
        "rain_mm": 0, "pop": [], "wind_speed": [], "visibility_km": [], "lightning": [], "descs": [], "hours_covered": 0
    })

    # Iterate through each hour of consolidated data to build daily summaries and slab data.
    for dt_ist, data in hourly_data_list:
        max_temp = max(max_temp, data['temp'])
        min_temp = min(min_temp, data['temp'])
        total_rain_overall += data['rain_mm'] # Summing the *averaged* hourly rain for the daily total
        all_weather_descs.append(data['description'])
        all_hourly_pops.append(data['pop']) # Collect hourly PoPs

        hour_in_day = dt_ist.hour
        
        slab_key = None
        for start_h, end_h, display_name in SLAB_DEFINITIONS:
            # Special handling for the cross-midnight slab definition (start_h > end_h)
            # When processing current day's data, it can only cover current day's hours 22 and 23.
            if start_h == 22 and end_h == 2: # This condition specifically matches the "Next Day" slab
                if hour_in_day == 22 or hour_in_day == 23:
                    slab_key = (start_h, end_h, display_name)
                    break
            # For all other standard slabs within the same day (start_h < end_h)
            elif start_h < end_h:
                if hour_in_day >= start_h and hour_in_day < end_h:
                    slab_key = (start_h, end_h, display_name)
                    break
        
        # Aggregate data for the identified slab.
        if slab_key:
            slabs_data_raw[slab_key]["rain_mm"] += data['rain_mm'] # Sum averaged hourly rains within the slab
            slabs_data_raw[slab_key]["pop"].append(data['pop'])
            slabs_data_raw[slab_key]["wind_speed"].append(data['wind_speed'])
            slabs_data_raw[slab_key]["visibility_km"].append(data.get('visibility_km', 10))
            slabs_data_raw[slab_key]["descs"].append(data['description'])
            slabs_data_raw[slab_key]["lightning"].append(data['lightning'])
            slabs_data_raw[slab_key]["hours_covered"] += 1

    candidate_slabs = []
    # Process raw slab data into final, summarized slab entries.
    for slab_key, slab_data in slabs_data_raw.items():
        if slab_data["hours_covered"] > 0:
            avg_pop = sum(slab_data["pop"]) / len(slab_data["pop"]) if slab_data["pop"] else 0
            avg_wind = sum(slab_data["wind_speed"]) / len(slab_data["wind_speed"]) if slab_data["wind_speed"] else 0
            avg_vis = sum(slab_data["visibility_km"]) / len(slab_data["visibility_km"]) if slab_data["visibility_km"] else 10.0
            
            main_desc = collections.Counter(slab_data["descs"]).most_common(1)[0][0] if slab_data["descs"] else get_rain_type(slab_data["rain_mm"], is_2hr_slab=True)
            explicit_lightning_in_desc = any("thunder" in d.lower() or "lightning" in d.lower() for d in slab_data["descs"])

            # Only include slabs if rain_mm meets the "meaningful" threshold.
            if slab_data["rain_mm"] >= MIN_RAINFALL_FOR_SLAB_DISPLAY_MM: 
                candidate_slabs.append({
                    "time_range": slab_key[2],
                    "sort_key": slab_data["rain_mm"] + (avg_pop / 100), # Used for sorting: prioritize rain amount then PoP
                    "prob": int(round(avg_pop, 0)),
                    "mm": round(slab_data["rain_mm"], 1),
                    "type": get_rain_type(slab_data["rain_mm"], is_2hr_slab=True),
                    "wind_speed": round(avg_wind, 1),
                    "visibility_km": round(avg_vis, 1),
                    "lightning": any(slab_data["lightning"]) or explicit_lightning_in_desc, # True if any source in slab predicted lightning or description indicated it
                    "description": main_desc # Add the main description for the slab
                })

    # Sort all relevant candidate slabs to prioritize those with higher expected rain, then by time.
    candidate_slabs.sort(key=lambda x: (-x["sort_key"], x["time_range"]))

    final_slabs = []
    seen_time_ranges = set()
    # Apply the limit of MAX_SLABS_TO_SHOW
    for slab in candidate_slabs:
        if slab["time_range"] not in seen_time_ranges: # Ensure uniqueness, important if sort_key leads to non-unique order
            final_slabs.append(slab)
            seen_time_ranges.add(slab["time_range"])
            if len(final_slabs) >= MAX_SLABS_TO_SHOW: # Apply the limit here
                break
    
    # Sort the selected slabs chronologically for better readability in the output.
    # The SLAB_DEFINITIONS list order is crucial for this sorting.
    slab_order_map = {s[2]: idx for idx, s in enumerate(SLAB_DEFINITIONS)}
    final_slabs.sort(key=lambda x: slab_order_map.get(x["time_range"], float('inf')))

    # Determine the overall weather description for the day.
    overall_raw_desc = collections.Counter(all_weather_descs).most_common(1)[0][0] if all_weather_descs else "N/A"
    overall_weather_desc_with_icon = get_rain_type(total_rain_overall, is_2hr_slab=False, overall_description=overall_raw_desc)

    # Calculate Maximum Hourly PoP for the day for "real chance"
    max_hourly_pop = max(all_hourly_pops) if all_hourly_pops else 0

    return {
        "max_temp": round(max_temp, 1) if max_temp != float("-inf") else "N/A",
        "min_temp": round(min_temp, 1) if min_temp != float("inf") else "N/A",
        "total_rain": round(total_rain_overall, 1),
        "total_rain_pop": int(round(max_hourly_pop, 0)), # This is the "real chance" (max hourly PoP)
        "weather_desc": overall_weather_desc_with_icon,
        "slabs": final_slabs
    }


def fetch_and_print_forecast(lat, lon, mine_name, accuweather_location_key):
    """
    Main function to fetch, process, and print the weather forecast for a single mine location,
    consolidating data from multiple weather APIs.
    """
    print(f"\n✨ Fetching detailed forecast for {mine_name} (Lat: {lat}, Lon: {lon})...")

    # --- Fetch Raw Data from APIs ---
    # Attempt to get data from each configured API. Errors are caught and printed within each fetch function.
    ow_data = fetch_openweather_forecast(lat, lon)
    om_data = fetch_open_meteo_forecast(lat, lon)
    tm_data = fetch_tomorrow_io_forecast(lat, lon)
    # AccuWeather daily data is fetched but not explicitly printed in the final output.
    aw_daily_data = fetch_accuweather_daily_forecast(accuweather_location_key)

    # Check if any data was retrieved
    if not any([ow_data, om_data, tm_data]): # Only check primary hourly sources for overall data availability
        print(f"📍 {mine_name} - ⚠️ No primary forecast data available from OpenWeatherMap, Open-Meteo, or Tomorrow.io. Please check API keys and network connectivity.")
        print(f"\n{'-'*60}")
        return

    # Dictionary to hold consolidated hourly data.
    # Key: datetime object (IST hour), Value: dict of lists of metrics from different APIs for that hour.
    hourly_consolidated = {}
    # AccuWeather daily data is stored here but not used for printing in this output format.
    accuweather_daily_consolidated = {} # Kept for potential future use, not printed in this version.

    # --- Process and Consolidate Data from Each API ---

    # OpenWeatherMap data processing (hourly)
    if ow_data and "hourly" in ow_data:
        for entry in ow_data["hourly"]:
            dt_utc = datetime.fromtimestamp(entry["dt"], tz=UTC)
            dt_ist = utc_to_ist(dt_utc)
            hour_key = dt_ist.replace(minute=0, second=0, microsecond=0)

            # Filter data to a relevant forecast window (e.g., current hour + next 48 hours).
            if hour_key < datetime.now(IST).replace(minute=0, second=0, microsecond=0) - timedelta(hours=1) or \
               hour_key > datetime.now(IST).replace(minute=0, second=0, microsecond=0) + timedelta(hours=48):
                continue

            hourly_consolidated.setdefault(hour_key, {
                'temp': [], 'rain_mm': [], 'pop': [], 'wind_speed': [],
                'visibility_km': [], 'description': [], 'lightning': []
            })
            
            hourly_consolidated[hour_key]['temp'].append(entry["temp"])
            rain_mm = entry.get("rain", {}).get("1h", 0) # OpenWeatherMap often reports rain in 'rain' dict.
            snow_mm = entry.get("snow", {}).get("1h", 0) # Include snow in total precipitation.
            hourly_consolidated[hour_key]['rain_mm'].append(rain_mm + snow_mm) 
            hourly_consolidated[hour_key]['pop'].append(entry.get("pop", 0) * 100) # Convert probability to percentage.
            hourly_consolidated[hour_key]['wind_speed'].append(entry["wind_speed"] * 3.6) # Convert m/s to km/h.
            hourly_consolidated[hour_key]['visibility_km'].append(entry.get("visibility", 10000) / 1000) # Convert meters to km, default to 10km.
            
            if entry.get("weather"):
                hourly_consolidated[hour_key]['description'].append(entry["weather"][0]["description"])
                # Check for thunderstorm weather codes.
                if 200 <= entry["weather"][0]["id"] < 300:
                    hourly_consolidated[hour_key]['lightning'].append(True)
                else:
                    hourly_consolidated[hour_key]['lightning'].append(False)
            else:
                hourly_consolidated[hour_key]['description'].append("N/A")
                hourly_consolidated[hour_key]['lightning'].append(False)

    # Open-Meteo data processing (hourly)
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
            if weather_codes[i] in [95, 96, 99]: # Thunderstorm codes
                hourly_consolidated[hour_key]['lightning'].append(True)
            else:
                hourly_consolidated[hour_key]['lightning'].append(False)

    # Tomorrow.io data processing (hourly from /weather/forecast -> timelines)
    if tm_data and "timelines" in tm_data and "hourly" in tm_data["timelines"]:
        for interval in tm_data["timelines"]["hourly"]:
            dt_iso_str = interval["time"] # Note: 'time' instead of 'startTime' for this endpoint's hourly data
            
            # Use strptime for robust ISO 8601 parsing with 'Z'
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
            hourly_consolidated[hour_key]['wind_speed'].append(values.get("windSpeed", 0) * 3.6) # Convert m/s to km/h.
            hourly_consolidated[hour_key]['visibility_km'].append(values.get("visibility", 10000) / 1000) # Convert meters to km.
            tm_weather_code = values.get("weatherCode")
            if tm_weather_code is not None:
                hourly_consolidated[hour_key]['description'].append(get_weather_description_from_wmo_tomorrow_io(tm_weather_code))
            else:
                hourly_consolidated[hour_key]['description'].append("N/A")
            if values.get("lightningStrikeCount", 0) > 0 or tm_weather_code == 8000: # Lightning or thunderstorm code.
                hourly_consolidated[hour_key]['lightning'].append(True)
            else:
                hourly_consolidated[hour_key]['lightning'].append(False)

    # AccuWeather data processing (DAILY forecast) - data is fetched but not used in the final print format
    if aw_daily_data and "DailyForecasts" in aw_daily_data:
        for daily_entry in aw_daily_data["DailyForecasts"]:
            dt_epoch = daily_entry["EpochDate"]
            dt_utc = datetime.fromtimestamp(dt_epoch, tz=UTC)
            dt_ist = utc_to_ist(dt_utc)
            day_key = dt_ist.date() # Key by date for daily data

            # Only consider data for today and tomorrow
            current_date_ist = datetime.now(IST).date()
            if day_key < current_date_ist or day_key > current_date_ist + timedelta(days=1):
                continue

            # This data is stored but not directly used in the print loop below
            accuweather_daily_consolidated.setdefault(day_key, {
                'min_temp': [], 'max_temp': [], 'total_rain': [], 'description': []
            })

            accuweather_daily_consolidated[day_key]['min_temp'].append(daily_entry["Temperature"]["Minimum"]["Value"])
            accuweather_daily_consolidated[day_key]['max_temp'].append(daily_entry["Temperature"]["Maximum"]["Value"])
            accuweather_daily_consolidated[day_key]['total_rain'].append(daily_entry["Day"]["TotalLiquid"]["Value"])
            accuweather_daily_consolidated[day_key]['description'].append(daily_entry["Day"]["IconPhrase"])


    # --- Aggregate and Process Consolidated Hourly Data ---
    final_hourly_data = []
    # Sort hourly data by time to ensure correct chronological order.
    sorted_hour_keys = sorted(hourly_consolidated.keys())
    
    for hour_key in sorted_hour_keys:
        aggregated_data = hourly_consolidated[hour_key]
        
        # Calculate averages for each metric from all available API contributions.
        # Handles cases where a specific metric list might be empty.
        avg_temp = sum(aggregated_data['temp']) / len(aggregated_data['temp']) if aggregated_data['temp'] else 0
        
        # CRITICAL: AVERAGE RAIN_MM from all sources for a single hour.
        # This prevents overestimation by summing individual API predictions for the same event.
        avg_rain = sum(aggregated_data['rain_mm']) / len(aggregated_data['rain_mm']) if aggregated_data['rain_mm'] else 0
        
        avg_pop = sum(aggregated_data['pop']) / len(aggregated_data['pop']) if aggregated_data['pop'] else 0
        avg_wind_speed = sum(aggregated_data['wind_speed']) / len(aggregated_data['wind_speed']) if aggregated_data['wind_speed'] else 0
        avg_visibility_km = sum(aggregated_data['visibility_km']) / len(aggregated_data['visibility_km']) if aggregated_data['visibility_km'] else 10.0 # Default to 10 km.
        
        # Determine the most common weather description for the hour from all sources.
        most_common_desc = collections.Counter(aggregated_data['description']).most_common(1)
        hourly_description = most_common_desc[0][0] if most_common_desc else "N/A"

        # If any API predicted lightning, mark it as true for the hour. Prioritize safety.
        has_lightning = any(aggregated_data['lightning'])

        final_hourly_data.append((
            hour_key, # The timestamp for this consolidated hour
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

    # Group the final hourly data by day (IST) for daily summaries and slab generation.
    forecast_by_day = collections.defaultdict(list)
    for dt_ist, data in final_hourly_data:
        day_key = dt_ist.date()
        forecast_by_day[day_key].append((dt_ist, data))

    # Sort days to ensure the output is chronological.
    sorted_days = sorted(forecast_by_day.keys())

    # --- Print Daily Summaries and Slabs ---
    current_date_ist = datetime.now(IST).date()

    for day in sorted_days:
        # Only display forecasts for today and tomorrow.
        if day < current_date_ist or day > current_date_ist + timedelta(days=1):
            continue

        day_hourly_data = forecast_by_day[day]
        day_summary = get_daily_summary_and_slabs(day_hourly_data)
        
        day_label = "Today" if day == current_date_ist else "Tomorrow"
        date_str = day.strftime("%d %B, %Y") # e.g., "17 July, 2025"

        print(f"\n📍 {mine_name} - Forecast for {day_label}, {date_str}")
        
        # Print consolidated hourly summary in the requested format
        print(f"\t• Weather: {day_summary['weather_desc']}")
        print(f"\t• Max Temp: {day_summary['max_temp']}°C")
        print(f"\t• Min Temp: {day_summary['min_temp']}°C")
        # Separate lines for total rain mm and total rain probability %
        print(f"\t• Total Expected Rainfall: {day_summary['total_rain']} mm")
        print(f"\t• Rainfall probability: {day_summary['total_rain_pop']}%") # Uses Max Hourly PoP
        
        # Display detailed precipitation slabs if available and have rain.
        if day_summary['slabs']:
            print("\n\tPrecipitation Info:")
            for slab in day_summary['slabs']:
                # Determine if any alerts should be shown for this slab.
                wind_alert = " ⚠️" if slab['wind_speed'] >= WIND_ALERT_THRESHOLD_KMH else ""
                visibility_alert = " ⚠️" if slab['visibility_km'] <= VISIBILITY_ALERT_THRESHOLD_KM else ""
                
                print(f"\t• {slab['time_range']} - {slab['prob']}%, {slab['mm']} mm ({slab['type']})")
                
                alerts = []
                if slab['lightning']:
                    alerts.append("⚡ Lightning expected")
                if wind_alert:
                    alerts.append(f"{wind_alert} High Wind ({slab['wind_speed']} km/h)")
                if visibility_alert:
                    alerts.append(f"{visibility_alert} Low Visibility ({slab['visibility_km']} km)")
                
                if alerts:
                    print(f"\t  {' | '.join(alerts)}") # Print all applicable alerts on a new line.

        else: # Now it explicitly says "No meaningful precipitation slabs"
            print("\n\tNo meaningful precipitation slabs predicted.")

        # Display production impact status based on total daily rainfall.
        impact_level, status_msg = get_production_status(day_summary['total_rain'], day_summary['slabs'])
        print(f"\n\t• Rain Impact: {impact_level}")
        print(f"\t• Production Status: {status_msg}")
        
        print(f"\n{'-'*60}") # Separator for readability between mine forecasts.

# ------------------ MAIN EXECUTION ------------------

def main():
    """
    The entry point of the script. Iterates through all configured mine locations
    and calls the fetch and print function for each.
    """
    print("Starting weather forecast retrieval for all mines...")
    for mine in MINE_LOCATIONS:
        fetch_and_print_forecast(mine["lat"], mine["lon"], mine["name"], mine["accuweather_location_key"])
    print("\nAll forecasts processed. Enjoy your day!")

if __name__ == "__main__":
    main() 
