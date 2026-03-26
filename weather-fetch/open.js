require('dotenv').config();
const axios = require('axios');

const lat = 24.1962;
const lon = 82.6692;
const apiKey = process.env.OPENWEATHER_API_KEY;

const units = 'metric';

const currentURL = `https://api.openweathermap.org/data/2.5/weather?lat=${lat}&lon=${lon}&units=${units}&appid=${apiKey}`;
const forecastURL = `https://api.openweathermap.org/data/2.5/forecast?lat=${lat}&lon=${lon}&units=${units}&appid=${apiKey}`;

function formatDate(d) {
  return d.toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
}

function shortStamp(d) {
  return d.toLocaleDateString("en-GB", { day: '2-digit', month: '2-digit', year: '2-digit', hour: '2-digit', minute: '2-digit', hour12: true });
}

async function fetchWeather() {
  try {
    const [currentRes, forecastRes] = await Promise.all([
      axios.get(currentURL),
      axios.get(forecastURL)
    ]);

    const now = new Date();
    const todayStr = formatDate(now);

    const current = currentRes.data;
    const forecast = forecastRes.data;

    const todayWeather = current.weather[0].main;
    const todayDesc = current.weather[0].description;
    const todayTemp = current.main.temp.toFixed(1);
    const windSpeed = current.wind.speed.toFixed(1);
    const visibility = (current.visibility / 1000).toFixed(1);

    // Group tomorrow's forecast
    const tmr = new Date();
    tmr.setDate(tmr.getDate() + 1);
    const tmrDateStr = tmr.toISOString().split('T')[0];

    const tmrForecasts = forecast.list.filter(item => item.dt_txt.startsWith(tmrDateStr));
    const temps = tmrForecasts.map(f => f.main.temp);
    const pops = tmrForecasts.map(f => ({ time: f.dt_txt.split(' ')[1].slice(0,5), pop: f.pop }));

    const maxTemp = Math.max(...temps).toFixed(1);
    const minTemp = Math.min(...temps).toFixed(1);

    const rainExpected = pops.some(p => p.pop > 0.1);
    const rainTimes = pops.filter(p => p.pop > 0.1).map(p => `${p.time} (${Math.round(p.pop * 100)}%)`);

    console.log(`[${shortStamp(now)}] Yash Saiwal: Output:\n`);
    console.log(`Suliyari Coal Mine - Weather Forecast for ${todayStr}\n`);
    console.log(`=== Today's Weather Forecast ===`);
    console.log(`Weather: ${todayDesc}`);
    console.log(`Temperature: ${todayTemp}°C\n`);

    console.log(`--- Precipitation Info ---`);
    console.log(`Precipitation Expected: No`); // No POP in current weather
    console.log(`Rain Alert: No rain expected`);
    console.log(`Production will not be impacted\n`);

    console.log(`--- Additional Info ---`);
    console.log(`Wind Speed: ${windSpeed} km/h`);
    console.log(`Visibility: ${visibility} km\n`);

    console.log(`Suliyari Coal Mine - Weather Forecast for ${formatDate(tmr)}\n`);
    console.log(`=== Tomorrow’s Weather Forecast ===\n`);
    console.log(`Max Temperature: ${maxTemp}°C`);
    console.log(`Min Temperature: ${minTemp}°C\n`);

    console.log(`--- Precipitation Info ---`);
    console.log(`Precipitation Expected: ${rainExpected ? 'Yes' : 'No'}`);
    console.log(`Rain Alert: ${rainExpected ? 'Rain expected' : 'No rain expected'}`);
    console.log(`${rainExpected ? '⚠️ Production may be impacted' : 'Production will not be impacted'}`);
    if (rainExpected) {
      console.log(`Rain Probability Timeline: ${rainTimes.join(', ')}`);
    }

  } catch (err) {
    console.error("Error fetching weather data:", err.response?.data || err.message);
  }
}

fetchWeather();
