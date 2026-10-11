import math
from datetime import date
import streamlit as st
from streamlit_geolocation import streamlit_geolocation
from itinerary import plan_day
from spot_filter import load_spots
from field_notes import QUESTIONS, render_tip, save_tip, summarise_spot

st.set_page_config(page_title="Satara Weekend Picker", page_icon="🌿")
st.title("🌿 Satara Weekend Picker")
st.caption("Runs on a local open model (Gemma via Ollama). Facts and safety rules come from code.")

SPOTS = load_spots()
SPOT_NAMES = [s["name"] for s in SPOTS]


def meters(lat1, lon1, lat2, lon2):
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def find_nearby(lat, lon):
    """Return the nearest spot whose radius contains the user, or (None, None)."""
    best, best_d = None, None
    for s in SPOTS:
        if s.get("lat") is None or s.get("lon") is None:
            continue
        d = meters(lat, lon, s["lat"], s["lon"])
        if d <= s.get("radius_m", 300) and (best_d is None or d < best_d):
            best, best_d = s, d
    return best, best_d


tab_plan, tab_tip = st.tabs(["Plan my day", "Share a tip"])

# ---------------------------------------------------------------- Plan tab
with tab_plan:
    mood = st.selectbox("Mood", ["chill", "energetic", "curious", "social"])
    group = st.selectbox("Travelling as", ["solo", "friends", "family_kids", "seniors"])
    fitness = st.selectbox("Fitness level", ["easy", "moderate", "trek"])
    transport = st.selectbox("Transport", ["own", "public"])
    hours = st.slider("Hours available", 2, 10, 5)

    if st.button("Plan my day", type="primary"):
        with st.spinner("Planning (Gemma may take a while on CPU)..."):
            plan, weather = plan_day(mood, hours, group, fitness, transport)
        st.session_state["plan"] = plan
        st.session_state["plan_done"] = True

    if st.session_state.get("plan_done"):
        plan = st.session_state.get("plan")
        if plan is None:
            st.warning("No suitable plan today. Try more hours, a higher fitness level, or own transport.")
        else:
            st.subheader("Area: " + plan["area"])
            st.write(plan["story"])
            st.write("Leave Satara around 8:00 AM (" + plan["leave"] + ")")
            for item in plan["timeline"]:
                s = item["spot"]
                st.markdown("**{} - {}** &nbsp; {} ({} km)".format(
                    item["arrive"], item["leave"], s["name"], s["distance_km"]))
                summary = summarise_spot(s["name"])
                if summary:
                    st.caption("Based on {} visit(s), latest {}: {}; {}.".format(
                        summary["visitors"], summary["latest_date"],
                        summary["crowded"], summary["road"]))
            st.write("Back in Satara by about " + plan["back_home"])
            st.write("**Carry:** " + ", ".join(plan["carry"]))

# ----------------------------------------------------------------- Tip tab
with tab_tip:
    st.write("Been somewhere recently? Help the next visitor.")

    st.markdown("**Option 1: check where I am**")
    st.caption("Your location is read in your browser and used only to find a nearby place. It is not stored.")
    loc = streamlit_geolocation()

    nearby = None
    if loc and loc.get("latitude") is not None and loc.get("longitude") is not None:
        nearby, dist = find_nearby(loc["latitude"], loc["longitude"])
        if nearby:
            st.success("You seem to be at {} (about {} m away). Want to leave a quick tip?".format(
                nearby["name"], int(dist)))
        else:
            st.info("You are not near any of the listed places. You can still pick one below.")

    st.markdown("**Option 2: choose a place yourself**")
    default_index = SPOT_NAMES.index(nearby["name"]) if nearby else 0
    spot_name = st.selectbox("Place", SPOT_NAMES, index=default_index)
    trigger = "nearby" if (nearby and nearby["name"] == spot_name) else "voluntary"

    with st.form("tip_form"):
        answers = {}
        for key, question, options in QUESTIONS:
            answers[key] = st.selectbox(question, options)
        extra = st.text_input("Anything else? (optional)", max_chars=120)
        preview = st.form_submit_button("Preview my tip")

    if preview:
        st.session_state["draft"] = {
            "spot": spot_name, "answers": answers,
            "tip": render_tip(answers, extra.strip()), "trigger": trigger}

    draft = st.session_state.get("draft")
    if draft:
        st.markdown("**This is what other visitors will see for {}. You can edit it.**".format(draft["spot"]))
        edited = st.text_area("Your tip", value=draft["tip"], max_chars=200)
        col1, col2 = st.columns(2)
        if col1.button("Accept and share", type="primary") and edited.strip():
            save_tip({
                "spot": draft["spot"],
                "date": date.today().isoformat(),
                "crowd": draft["answers"]["crowd"],
                "road": draft["answers"]["road"],
                "best_time": draft["answers"]["best_time"],
                "highlight": draft["answers"]["highlight"],
                "tip": edited.strip(),
                "trigger": draft["trigger"],
            })
            del st.session_state["draft"]
            st.success("Saved. Thank you for helping the next visitor!")
        if col2.button("Discard"):
            del st.session_state["draft"]
            st.info("Nothing was saved.")
            