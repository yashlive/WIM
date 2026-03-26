equire('dotenv').config();
const axios = require('axios');

const apiKey = process.env.ACCUWEATHER_API_KEY;
const locationKey = process.env.ACCUWEATHER_LOCATION_KEY;

async function getTodayForecast() {
  const url = `http://dataservice.accuweather.com/forecasts/v1/daily/1day/${locationKey}?apikey=${apiKey}&details=true&metric=true`;

  try {
    const dailyRes = await axios.get(url);

    // Check if the expected data exists before using it
    if (!dailyRes.data || !dailyRes.data.DailyForecasts || !dailyRes.data.DailyForecasts[0]) {
      console.error('Error: Weather data is missing');
      return;
    }

    const daily = dailyRes.data.DailyForecasts[0];

    // Safe access of data, checking for existence before using it
    const maxTemp = daily.Temperature?.Maximum?.Value || 'N/A';
    const minTemp = daily.Temperature?.Minimum?.Value || 'N/A';
    const weatherType = daily.Day?.IconPhrase || 'N/A';
    const precipitation = daily.Day?.HasPrecipitation ? 'Yes' : 'No';
    const rainChance = daily.Day?.RainProbability || 'N/A';
    const windSpeed = daily.Day?.Wind?.Speed?.Value || 'N/A';
    const visibility = daily.Day?.Visibility?.Value || 'N/A';
    const forecastDate = new Date(daily.Date).toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });

    // Check if there is rain and get the time of rain
    let rainTime = "No rain expected"; // Default message if no rain
    let rainInNext12Hours = "No major rain expected in the next 12 hours.";
    if (daily.Day?.HourlyForecasts) {
      for (let hour of daily.Day.HourlyForecasts) {
        if (hour.HasPrecipitation) {
          rainTime = new Date(hour.DateTime).toLocaleTimeString('en-IN', { timeStyle: 'short' });
          rainInNext12Hours = `Rain expected at ${rainTime}`;
          break; // First occurrence of rain
        }
      }
    }

    // Output the weather forecast in structured format
    console.log(`=== Suliyari Coal Mine Weather Forecast for ${forecastDate} ===`);
    console.log(`Weather: ${weatherType}`);
    console.log(`Max Temp: ${maxTemp}°C`);
    console.log(`Min Temp: ${minTemp}°C`);

    console.log('\n--- Precipitation Info ---');
    console.log(`Chance of Rain: ${rainChance}%`);
    console.log(`Precipitation: ${precipitation}`);

    console.log('\n--- Hourly Rain Forecast ---');
    console.log(rainInNext12Hours);

  } catch (err) {
    console.error('Failed to fetch weather data:', err.message);
  }
}

getTodayForecast();

