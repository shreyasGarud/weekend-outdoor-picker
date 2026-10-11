import json
import shutil

PATH = "spots.json"
DEFAULT_RADIUS = {"plateau": 1000, "lake": 500, "waterfall": 300, "fort": 300,
                  "hill": 300, "river": 300}

shutil.copy(PATH, PATH + ".bak")

with open(PATH, encoding="utf-8") as f:
    spots = json.load(f)

for s in spots:
    if s.get("lat") is not None and s.get("lon") is not None:
        continue
    print("\n" + s["name"] + " (" + s.get("area", "") + ")")
    raw = input("Paste 'lat, lon' from Google Maps (Enter to skip): ").strip()
    if not raw:
        continue
    try:
        lat_text, lon_text = raw.split(",")
        lat, lon = float(lat_text), float(lon_text)
    except ValueError:
        print("Could not read that, skipping. Expected something like 17.6805, 74.0183")
        continue
    if not (16.5 <= lat <= 18.5 and 73.0 <= lon <= 75.5):
        confirm = input("That is outside the usual Satara range. Keep it anyway? (y/n): ").strip().lower()
        if confirm != "y":
            continue
    default = DEFAULT_RADIUS.get(s["type"], 300)
    radius_raw = input("Radius in metres [{}]: ".format(default)).strip()
    s["lat"] = round(lat, 5)
    s["lon"] = round(lon, 5)
    s["radius_m"] = int(radius_raw) if radius_raw.isdigit() else default

with open(PATH, "w", encoding="utf-8") as f:
    json.dump(spots, f, indent=2, ensure_ascii=False)

print("\nDone. Spots still without coordinates:",
      [s["name"] for s in spots if s.get("lat") is None] or "none")
