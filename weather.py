import requests

SATARA_LAT = 17.68
SATARA_LON = 74.02

THUNDER_CODES = (95, 96, 99)
HEAVY_RAIN_CODES = (65, 67, 82)


def get_weather(day_offset=0):
    """Fetch a daily forecast for Satara. day_offset: 0 = today, 1 = tomorrow."""
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": SATARA_LAT,
        "longitude": SATARA_LON,
        "daily": "weather_code,temperature_2m_max,precipitation_sum,precipitation_probability_max",
        "timezone": "Asia/Kolkata",
        "forecast_days": 3,
    }
    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    daily = response.json()["daily"]

    return {
        "date": daily["time"][day_offset],
        "weather_code": daily["weather_code"][day_offset],
        "temp_max_c": daily["temperature_2m_max"][day_offset],
        "rain_mm": daily["precipitation_sum"][day_offset],
        "rain_chance_pct": daily["precipitation_probability_max"][day_offset],
    }


def get_conditions(weather):
    """Turn raw weather numbers into labels that match spots.json 'avoid_if'."""
    conditions = []
    if weather["weather_code"] in THUNDER_CODES:
        conditions.append("thunderstorm")
    if weather["weather_code"] in HEAVY_RAIN_CODES or weather["rain_mm"] >= 20:
        conditions.append("heavy_rain")
    if weather["temp_max_c"] >= 38:
        conditions.append("extreme_heat")
    return conditions


if __name__ == "__main__":
    w = get_weather(0)
    print("Weather:", w)
    print("Conditions:", get_conditions(w))
