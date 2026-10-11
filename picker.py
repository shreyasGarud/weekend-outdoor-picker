import json
import requests
from weather import get_weather, get_conditions
from spot_filter import load_spots, filter_spots

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "gemma3:1b"


def weather_summary(weather):
    """Plain-English weather line, so the model never has to guess the sky."""
    temp = weather["temp_max_c"]
    if temp >= 33:
        feel = "hot"
    elif temp >= 25:
        feel = "warm"
    elif temp >= 18:
        feel = "pleasant"
    else:
        feel = "cool"
    rain = weather["rain_chance_pct"]
    if rain >= 60:
        sky = "rain is likely"
    elif rain >= 30:
        sky = "some chance of showers"
    else:
        sky = "little chance of rain"
    return "{} (max {} C), {}".format(feel, temp, sky)


def build_carry_list(spot, weather):
    """Decide what to carry using rules, not the model."""
    items = ["Water bottle"]
    if spot["type"] in ("fort", "plateau", "waterfall"):
        items.append("Shoes with good grip")
    if spot["type"] == "river":
        items.append("Comfortable walking footwear")
    if weather["temp_max_c"] >= 30:
        items.append("Cap or hat and sunscreen")
    if weather["rain_chance_pct"] >= 30:
        items.append("Raincoat or umbrella")
    if spot["effort"] in ("moderate", "hard") or spot["duration_hours"] >= 3:
        items.append("Light snacks")
    return items


def best_time_to_leave(weather):
    """Choose a leave time by rule."""
    if weather["temp_max_c"] >= 33:
        return "Before 8:00 AM, to beat the heat"
    if weather["rain_chance_pct"] >= 50:
        return "Late morning, and keep an eye on the sky"
    return "Around 8:00 AM, for the best light and fewer crowds"


def build_prompt(spots, weather, mood, hours):
    spot_lines = []
    for s in spots:
        spot_lines.append("- {} ({}, {} effort, {}h): {}".format(
            s["name"], s["type"], s["effort"],
            s["duration_hours"], s["description"]))

    return (
        "You are a friendly local guide in Satara, Maharashtra.\n"
        "Pick exactly ONE place from the list for someone who feels '{mood}' "
        "and has {hours} hours.\n"
        "Today's weather: {weather}.\n\n"
        "Places (choose ONLY from these):\n{spots}\n\n"
        "Reply with JSON only, with exactly these keys:\n"
        '{{"pick": "<exact place name from the list>", '
        '"pitch": "<2 or 3 warm sentences on why this place suits their mood>"}}\n'
        "Use only facts from the list and the weather line. Do not invent details."
    ).format(mood=mood, hours=hours, weather=weather_summary(weather),
             spots="\n".join(spot_lines))


def ask_gemma(prompt):
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.7},
    }
    response = requests.post(OLLAMA_URL, json=payload, timeout=180)
    response.raise_for_status()
    return json.loads(response.json()["message"]["content"])


def get_suggestion(mood, hours, day_offset=0):
    spots = load_spots()
    weather = get_weather(day_offset)
    conditions = get_conditions(weather)
    month = int(weather["date"][5:7])

    candidates = filter_spots(spots, mood, hours, conditions, month)
    if not candidates:
        return None, weather
    candidates = candidates[:5]

    try:
        answer = ask_gemma(build_prompt(candidates, weather, mood, hours))
    except (requests.RequestException, ValueError, KeyError):
        answer = {}

    by_name = {s["name"]: s for s in candidates}
    chosen = by_name.get(answer.get("pick"))
    pitch = answer.get("pitch")
    if chosen is None:           # model picked something not on our list
        chosen = candidates[0]
        pitch = None
    if not pitch:
        pitch = chosen["description"]

    result = {
        "pick": chosen["name"],
        "pitch": pitch,
        "best_time_to_leave": best_time_to_leave(weather),
        "carry": build_carry_list(chosen, weather),
    }
    return result, weather


if __name__ == "__main__":
    mood = input("Mood (chill/energetic/curious/social): ").strip().lower()
    hours = int(input("Hours available: "))
    print("\nAsking Gemma (this can take a while on CPU)...\n")

    answer, weather = get_suggestion(mood, hours)
    if answer is None:
        print("No suitable spots today. Try more hours or another day.")
    else:
        print("Go to:", answer["pick"])
        print("\n" + answer["pitch"])
        print("\nLeave:", answer["best_time_to_leave"])
        print("Carry:", ", ".join(answer["carry"]))
        