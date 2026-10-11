import json
import os
from datetime import date
import requests
from spot_filter import load_spots
from picker import OLLAMA_URL, MODEL

TIPS_FILE = "tips.json"

QUESTIONS = [
    ("crowd", "How crowded was it?", ["low", "medium", "high"]),
    ("road", "How was the road or path?", ["good", "bad"]),
    ("best_time", "When is the best time to go?", ["early morning", "late morning", "afternoon", "evening"]),
    ("highlight", "What stood out most?", ["views", "quiet", "food nearby", "history", "nature"]),
]


def load_tips():
    if not os.path.exists(TIPS_FILE):
        return []
    with open(TIPS_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_tip(tip):
    tips = load_tips()
    tips.append(tip)
    with open(TIPS_FILE, "w", encoding="utf-8") as f:
        json.dump(tips, f, indent=2, ensure_ascii=False)


def get_tips(spot_name, limit=2):
    """Latest tips for one spot."""
    mine = [t for t in load_tips() if t["spot"] == spot_name]
    return mine[-limit:]


def choose(prompt, options):
    print("\n" + prompt)
    for i, opt in enumerate(options, 1):
        print("  {}. {}".format(i, opt))
    while True:
        raw = input("Number: ").strip()
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1]
        print("Please type a number from 1 to", len(options))


def frame_tip(spot_name, answers, extra):
    """Turn the answers into one short tip sentence. Falls back to a template."""
    fallback = "{} crowd, {} road. Best time: {}. Highlight: {}.".format(
        answers["crowd"].capitalize(), answers["road"], answers["best_time"], answers["highlight"])
    if extra:
        fallback += " " + extra

    prompt = (
        "Write ONE short, friendly tip sentence (max 30 words) for future visitors to {spot}, "
        "using only these facts from a recent visitor:\n"
        "- Crowd: {crowd}\n- Road or path: {road}\n- Best time: {best_time}\n"
        "- Highlight: {highlight}\n- Extra note: {extra}\n\n"
        "Do not add facts that are not listed. Reply with JSON only: {{\"tip\": \"<sentence>\"}}"
    ).format(spot=spot_name, extra=extra or "none", **answers)

    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.3},
    }
    try:
        r = requests.post(OLLAMA_URL, json=payload, timeout=180)
        r.raise_for_status()
        tip = json.loads(r.json()["message"]["content"]).get("tip")
        if isinstance(tip, str) and tip.strip():
            return tip.strip()
    except (requests.RequestException, ValueError, KeyError):
        pass
    return fallback

def render_tip(answers, extra=""):
    text = "{} crowd, {} road. Best time: {}. Highlight: {}.".format(
        answers["crowd"].capitalize(), answers["road"],
        answers["best_time"], answers["highlight"])
    if extra:
        text += " " + extra
    return text


def summarise_spot(spot_name):
    """Count answers across visitors. Returns None if there are no tips yet."""
    tips = [t for t in load_tips() if t["spot"] == spot_name]
    if not tips:
        return None
    n = len(tips)
    crowd_high = sum(1 for t in tips if t.get("crowd") == "high")
    road_good = sum(1 for t in tips if t.get("road") == "good")
    return {
        "visitors": n,
        "crowded": "{} of {} found it crowded".format(crowd_high, n),
        "road": "{} of {} found the road good".format(road_good, n),
        "latest_date": tips[-1]["date"],
    }

if __name__ == "__main__":
    spots = load_spots()
    for i, s in enumerate(spots, 1):
        print("{}. {}".format(i, s["name"]))
    while True:
        raw = input("\nWhich place did you visit? Number: ").strip()
        if raw.isdigit() and 1 <= int(raw) <= len(spots):
            spot = spots[int(raw) - 1]
            break
        print("Please type a number from 1 to", len(spots))

    answers = {}
    for key, question, options in QUESTIONS:
        answers[key] = choose(question, options)

    extra = input("\nAnything else other visitors should know? (optional, press Enter to skip): ").strip()[:120]

    print("\nFraming your tip...")
    tip = render_tip(spot["name"], extra)

    while True:
        print("\nHere is what other visitors will see:")
        print('  "{}"'.format(tip))
        action = input("\n(a)ccept, (e)dit, or (d)iscard? ").strip().lower()
        if action == "a":
            save_tip({
                "spot": spot["name"],
                "date": date.today().isoformat(),
                "crowd": answers["crowd"],
                "road": answers["road"],
                "tip": tip,
            })
            print("Saved. Thank you for helping the next visitor!")
            break
        if action == "e":
            new_tip = input("Type your corrected tip: ").strip()
            if new_tip:
                tip = new_tip
        elif action == "d":
            print("Nothing was saved.")
            break
