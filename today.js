import dotenv from 'dotenv';
import fetch from 'node-fetch';
import { format } from 'date-fns';

dotenv.config();

const mines = [
  { name: process.env.NAME1, lat: process.env.LAT1, lon: process.env.LON1 },
  { name: process.env.NAME2, lat: process.env.LAT2, lon: process.env.LON2 },
  { name: process.env.NAME3, lat: process.env.LAT3, lon: process.env.LON3 },
  { name: process.env.NAME4, lat: process.env.LAT4, lon: process.env.LON4 },
  { name: process.env.NAME5, lat: process.env.LAT5, lon: process.env.LON5 }
];

const API_KEY = process.env.OPENWEATHER_API_KEY;

const fetchWeatherData = async (lat, lon) => {
  const res = await fetch(`https://api.openweathermap.org/data/3.0/onecall?lat=${lat}&lon=${lon}&units=metric&exclude=minutely,alerts&appid=${API_KEY}`);
  if (!res.ok) throw new Error(`Fetch failed: ${res.status}`);
  return res.json();
};

const getTime = (timestamp) => {
  const date = new Date(timestamp * 1000);
  return date.toLocaleTimeString('en-IN', {
    hour: 'numeric',
    minute: '2-digit',
    hour12: true
  });
};

const groupByTimeSlots = (hourlyData) => {
  const blocks = [];
  let block = [];

  for (let i = 0; i < hourlyData.length; i++) {
    const h = hourlyData[i];
    if (h.pop < 0.4) continue;

    if (block.length === 0) {
      block.push(h);
    } else {
      const last = block[block.length - 1];
      if ((h.dt - last.dt) <= 7200 && block.length < 4) {
        block.push(h);
      } else {
        blocks.push(block);
        block = [h];
      }
    }
  }
  if (block.length > 0) blocks.push(block);

  return blocks.sort((a, b) => a[0].dt - b[0].dt);
};

const formatRainBlocks = (blocks) => {
  return blocks.map((block) => {
    const start = getTime(block[0].dt);
    const end = getTime(block[block.length - 1].dt);
    const avgProb = Math.round(block.reduce((sum, h) => sum + h.pop, 0) / block.length * 100);
    return `\t\t• ${start} to ${end} – ${avgProb}%`;
  });
};

const summarizeDay = (daily) => ({
  weather: daily.weather[0].description,
  max: daily.temp.max.toFixed(1),
  min: daily.temp.min.toFixed(1),
  rain: daily.pop > 0
});

const displayForecast = async () => {
  const today = format(new Date(), 'd MMMM, yyyy');
  const tomorrow = format(new Date(Date.now() + 86400000), 'd MMMM, yyyy');

  for (let mine of mines) {
    try {
      const data = await fetchWeatherData(mine.lat, mine.lon);
      const todayData = summarizeDay(data.daily[0]);
      const tomorrowData = summarizeDay(data.daily[1]);

      const todayRainBlocks = formatRainBlocks(groupByTimeSlots(data.hourly.slice(0, 24)));
      const tomorrowRainBlocks = formatRainBlocks(groupByTimeSlots(data.hourly.slice(24, 48)));

      // --- TODAY ---
      console.log(`\n📍 ${mine.name} - Forecast for Today, ${today}`);
      console.log(`\t• Weather: ${todayData.weather}`);
      console.log(`\t• Max Temp: ${todayData.max}°C`);
      console.log(`\t• Min Temp: ${todayData.min}°C`);
      console.log(`\t• Rain Probability: ${todayData.rain ? 'Yes' : 'No'}`);
      console.log(`\t• Rain Timing:`);
      console.log(todayRainBlocks.length ? todayRainBlocks.join('\n') : `\t\t• None`);
      if (todayData.rain && todayRainBlocks.length) {
        console.log(`\t• Production may be impacted due to rain.`);
      }

      // --- TOMORROW ---
      console.log(`\n📍 ${mine.name} - Forecast for Tomorrow, ${tomorrow}`);
      console.log(`\t• Weather: ${tomorrowData.weather}`);
      console.log(`\t• Max Temp: ${tomorrowData.max}°C`);
      console.log(`\t• Min Temp: ${tomorrowData.min}°C`);
      console.log(`\t• Rain Probability: ${tomorrowData.rain ? 'Yes' : 'No'}`);
      console.log(`\t• Rain Timing:`);
      console.log(tomorrowRainBlocks.length ? tomorrowRainBlocks.join('\n') : `\t\t• None`);
      if (tomorrowData.rain && tomorrowRainBlocks.length) {
        console.log(`\t• Production may be impacted due to rain.`);
      }

    } catch (err) {
      console.error(`\n❌ Error fetching data for ${mine.name}: ${err.message}`);
    }
  }
};

displayForecast();

