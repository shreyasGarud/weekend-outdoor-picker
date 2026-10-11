import json
import requests
from weather import get_weather, get_conditions
from spot_filter import load_spots, filter_spots
from picker import build_carry_list, best_time_to_leave, weather_summary, OLLAMA_URL, MODEL
from field_notes import summarise_spot

EFFORT_BY_FITNESS = {
    "easy": ["easy"],
    "moderate": ["easy", "moderate"],
    "trek": ["easy", "moderate", "hard"],
}
GENTLE_GROUPS = ("family_kids", "seniors")
KM_PER_HOUR = 40        # rough average road speed in the hills
STOP_GAP_HOURS = 0.25   # short break/travel between stops in the same area
START_HOUR = 8.0


def profile_filter(spots, group, fitness, transport):
    """Remove spots that don't suit this traveller."""
    allowed = EFFORT_BY_FITNESS[fitness]
    if group in GENTLE_GROUPS:
        allowed = ["easy"]
    result = [s for s in spots if s["effort"] in allowed]
    if transport == "public":
        result = [s for s in result if s["distance_km"] <= 40]
    return result


def trip_hours(stops):
    """Time on site plus a rough allowance for travel (round trip to the farthest stop)."""
    visit = sum(s["duration_hours"] for s in stops)
    farthest = max(s["distance_km"] for s in stops)
    travel = 2.0 * farthest / KM_PER_HOUR + STOP_GAP_HOURS * (len(stops) - 1)
    return visit + travel


def pick_area_plan(candidates, mood, hours):
    """Group by area, fill each area with as many stops as fit, keep the best area."""
    by_area = {}
    for s in candidates:
        by_area.setdefault(s.get("area", "Satara"), []).append(s)

    best_stops, best_score = None, None
    for area, area_spots in by_area.items():
        stops = []
        for s in area_spots:  # candidates are already sorted mood-match first
            if trip_hours(stops + [s]) <= hours:
                stops.append(s)
        if not stops:
            continue
        score = (sum(1 for s in stops if mood in s["best_moods"]), len(stops))
        if best_score is None or score > best_score:
            best_stops, best_score = stops, score

    if best_stops is None:
        return None
    return sorted(best_stops, key=lambda s: s["distance_km"])  # nearest first on the way out


def fmt_time(t):
    total_min = int(round(t * 60 / 5.0)) * 5
    h = (total_min // 60) % 24
    m = total_min % 60
    suffix = "AM" if h < 12 else "PM"
    h12 = h % 12 or 12
    return "{}:{:02d} {}".format(h12, m, suffix)


def schedule(stops):
    """Give each stop an arrival and leaving time, starting from Satara at 8 AM."""
    t = START_HOUR + stops[0]["distance_km"] / float(KM_PER_HOUR)
    timeline = []
    for s in stops:
        arrive = t
        t += s["duration_hours"]
        timeline.append({"spot": s, "arrive": fmt_time(arrive), "leave": fmt_time(t)})
        t += STOP_GAP_HOURS
    back = (t - STOP_GAP_HOURS) + stops[-1]["distance_km"] / float(KM_PER_HOUR)
    return timeline, fmt_time(back)


def narrate(timeline, weather, mood, group, hours):
    """Ask Gemma for a friendly overview. Falls back to a plain sentence if it fails."""
    lines = []
    for item in timeline:
        s = item["spot"]
        lines.append("- {} ({}), {} to {}: {}".format(
            s["name"], s["type"], item["arrive"], item["leave"], s["description"]))

    prompt = (
        "You are a friendly local guide in Satara, Maharashtra.\n"
        "Write 3 or 4 warm sentences introducing this day plan to a traveller "
        "who feels '{mood}', is travelling as '{group}', and has {hours} hours.\n"
        "Weather today: {weather}.\n\nPlan:\n{plan}\n\n"
        "Reply with JSON only: {{\"story\": \"<your text>\"}}\n"
        "Use only the facts above. Do not change times or add places."
    ).format(mood=mood, group=group.replace("_", " "), hours=hours,
             weather=weather_summary(weather), plan="\n".join(lines))

    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.7},
    }
    try:
        r = requests.post(OLLAMA_URL, json=payload, timeout=180)
        r.raise_for_status()
        story = json.loads(r.json()["message"]["content"]).get("story")
        if story:
            return story
    except (requests.RequestException, ValueError, KeyError):
        pass
    names = ", ".join(i["spot"]["name"] for i in timeline)
    return "Here is a {} plan for your day: {}.".format(mood, names)


def plan_day(mood, hours, group, fitness, transport, day_offset=0):
    weather = get_weather(day_offset)
    conditions = get_conditions(weather)
    month = int(weather["date"][5:7])

    spots = profile_filter(load_spots(), group, fitness, transport)
    candidates = filter_spots(spots, mood, hours, conditions, month)
    stops = pick_area_plan(candidates, mood, hours) if candidates else None
    if not stops:
        return None, weather

    timeline, back_home = schedule(stops)

    carry = []
    for item in timeline:
        for thing in build_carry_list(item["spot"], weather):
            if thing not in carry:
                carry.append(thing)

    return {
        "area": stops[0].get("area", "Satara"),
        "timeline": timeline,
        "back_home": back_home,
        "carry": carry,
        "leave": best_time_to_leave(weather),
        "story": narrate(timeline, weather, mood, group, hours),
    }, weather


def ask(prompt, options):
    while True:
        value = input("{} ({}): ".format(prompt, "/".join(options))).strip().lower()
        if value in options:
            return value
        print("Please type one of:", ", ".join(options))


if __name__ == "__main__":
    mood = ask("Mood", ["chill", "energetic", "curious", "social"])
    group = ask("Travelling as", ["solo", "friends", "family_kids", "seniors"])
    fitness = ask("Fitness level", ["easy", "moderate", "trek"])
    transport = ask("Transport", ["own", "public"])
    hours = int(input("Total hours available for the day: "))

    print("\nPlanning your day (Gemma may take a while on CPU)...\n")
    plan, weather = plan_day(mood, hours, group, fitness, transport)

    if plan is None:
        print("No suitable plan today. Try more hours, a higher fitness level, or own transport.")
    else:
        print("Area:", plan["area"])
        print("\n" + plan["story"] + "\n")
        print("Leave Satara around 8:00 AM ({})".format(plan["leave"]))
        for item in plan["timeline"]:
            print("  {} - {}  {} ({} km)".format(
                item["arrive"], item["leave"], item["spot"]["name"], item["spot"]["distance_km"]))
            summary = summarise_spot(item["spot"]["name"])
            if summary:
                print("      Based on {} visit(s), latest {}: {}; {}.".format(
                    summary["visitors"], summary["latest_date"],
                    summary["crowded"], summary["road"]))
        print("Back in Satara by about", plan["back_home"])
        print("\nCarry:", ", ".join(plan["carry"]))
        