import json
from weather import get_weather, get_conditions


def load_spots(path="spots.json"):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def filter_spots(spots, mood, hours_available, conditions, month):
    """Keep only spots that suit the season, weather and time available.
    Spots matching the user's mood are placed first."""
    results = []
    for spot in spots:
        if month not in spot.get("best_months", range(1, 13)):
            continue
        if any(c in spot["avoid_if"] for c in conditions):
            continue
        if spot["duration_hours"] > hours_available:
            continue
        results.append(spot)

    # False sorts before True, so mood matches come first
    results.sort(key=lambda s: mood not in s["best_moods"])
    return results


if __name__ == "__main__":
    mood = input("Mood (chill/energetic/curious/social): ").strip().lower()
    hours = int(input("Hours available: "))

    spots = load_spots()
    weather = get_weather(0)
    conditions = get_conditions(weather)
    month = int(weather["date"][5:7])

    print("\nWeather:", weather)
    print("Conditions:", conditions)

    picks = filter_spots(spots, mood, hours, conditions, month)
    if not picks:
        print("\nNo suitable spots today. Try more hours or a different day.")
    else:
        print("\nSuitable spots:")
        for s in picks:
            match = "mood match" if mood in s["best_moods"] else "other"
            print("- {} ({}, {}h, {} km)".format(s["name"], match, s["duration_hours"], s["distance_km"]))
            