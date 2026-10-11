import json
import requests
from weather import get_weather, get_conditions
from spot_filter import load_spots, filter_spots

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "gemma3:1b"


def build_prompt(spots, weather, mood, hours):
    spot_lines = []
    for s in spots:
        spot_lines.append("- {} ({}, {} effort, {}h, {} km): {}".format(
            s["name"], s["type"], s["effort"],
            s["duration_hours"], s["distance_km"], s["description"]))

    return (
        "You are a friendly local guide in Satara, Maharashtra.\n"
        "Pick exactly ONE place from the list below for someone who feels '{mood}' "
        "and has {hours} hours.\n"
        "Weather today: max {temp} C, rain chance {rain}%.\n\n"
        "Places (choose ONLY from these):\n{spots}\n\n"
        "Reply with JSON only, using exactly these keys:\n"
        '{{"pick": "<exact place name from the list>", '
        '"pitch": "<2-3 warm sentences on why it suits their mood and today\'s weather>", '
        '"best_time_to_leave": "<short suggestion>", '
        '"carry": ["<item>", "<item>", "<item>"]}}\n'
        "Use only facts from the list. Do not invent details."
    ).format(mood=mood, hours=hours, temp=weather["temp_max_c"],
             rain=weather["rain_chance_pct"], spots="\n".join(spot_lines))


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

    # Only offer the top few so a small model stays focused
    candidates = candidates[:5]

    try:
        answer = ask_gemma(build_prompt(candidates, weather, mood, hours))
    except (requests.RequestException, ValueError, KeyError):
        answer = {}

    # Safety net: the pick must be a real spot from our list
    names = [s["name"] for s in candidates]
    if answer.get("pick") not in names:
        answer = {
            "pick": candidates[0]["name"],
            "pitch": candidates[0]["description"],
            "best_time_to_leave": "Morning",
            "carry": ["Water", "Sun protection", "Comfortable shoes"],
        }
    return answer, weather


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
        print("\nLeave:", answer.get("best_time_to_leave", ""))
        print("Carry:", ", ".join(answer.get("carry", [])))
        