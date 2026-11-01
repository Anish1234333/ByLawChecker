"""BylawCheck UI. Runs pipeline.py in-process, or calls the FastAPI service when API_URL is set."""
import html
import os
import traceback

import streamlit as st

CITIES = ["Delhi", "Mumbai", "Hyderabad", "All"]
MODES = ["Quick Check", "Plan Review"]
SUBTITLES = {"Quick Check": "Ask a question, get the rule.", "Plan Review": "Describe your plan, get a review."}
EXAMPLES = [
    "What is the maximum permitted building height?",
    "What setbacks are required for a residential plot?",
    "How many parking spaces does a residential building need?",
    "Is rainwater harvesting mandatory?",
]
RATINGS = {"Looks Good": "good", "Needs Changes": "warn", "Not Enough Info": "info"}

PALETTES = {
    "light": dict(bg="#FAFAF7", surface="#FFFFFF", border="#E6E4DC", text="#1B1B18", muted="#6B6A63",
                  accent="#1F4E3D", on_accent="#FFFFFF", good_bg="#E6F0E9", good_fg="#2D6A45",
                  warn_bg="#FAF0D9", warn_fg="#8A5A00", info_bg="#EEEDE8", info_fg="#5C5B54"),
    "dark": dict(bg="#121413", surface="#1A1D1B", border="#2A2E2B", text="#ECECE6", muted="#9A9C94",
                 accent="#7FC8A9", on_accent="#0F1A15", good_bg="#1C2C24", good_fg="#8FD1AB",
                 warn_bg="#2F2817", warn_fg="#E2B960", info_bg="#252826", info_fg="#A9AAA2"),
}

BASE_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');
.stApp, .stApp p, .stApp label, .stApp li, .stApp input, .stApp textarea, .stApp button, .stApp h1, .stApp h2, .stApp h3, .stApp h4
  { font-family: 'Inter', system-ui, sans-serif; }
.stApp { background: var(--bg); color: var(--text); }
.stApp p, .stApp li, .stApp label, .stApp span, .stApp h1, .stApp h2, .stApp h3, .stApp h4 { color: var(--text); }
h1, h2, h3, h4 { font-weight: 600 !important; letter-spacing: -0.02em !important; }
h2 { font-size: 1.05rem !important; margin-top: 1.4rem !important; }
#MainMenu, footer, [data-testid="stToolbar"], [data-testid="stDecoration"], .stDeployButton,
[data-testid="stStatusWidget"] { display: none !important; }
[data-testid="stHeader"] { background: transparent; }
.block-container { max-width: 900px; padding: 1.5rem 1.25rem 6rem; }
[data-testid="stSidebar"] { background: var(--surface); border-right: 1px solid var(--border); }
[data-testid="stWidgetLabel"] p { font-size: 12px; color: var(--muted); }
.eyebrow { font-size: 11px; letter-spacing: .09em; text-transform: uppercase; color: var(--muted); }
.wordmark { font-weight: 600; font-size: 20px; letter-spacing: -0.03em; color: var(--text); }
.wordmark b { color: var(--accent); }
.tag { color: var(--muted); font-size: 14px; margin-top: .25rem; }
.note { color: var(--muted); font-size: 12px; border-top: 1px solid var(--border); padding-top: .55rem; margin: .8rem 0 1.4rem; }
.sub { color: var(--muted); font-size: 15px; margin: .9rem 0 1.1rem; }
input, textarea, [data-baseweb="select"] > div, [data-baseweb="input"], [data-baseweb="base-input"], [data-baseweb="textarea"]
  { background: var(--surface) !important; color: var(--text) !important; border-color: var(--border) !important; border-radius: 10px !important; }
[data-baseweb="input"]:focus-within, [data-baseweb="textarea"]:focus-within, [data-baseweb="select"] > div:focus-within
  { border-color: var(--accent) !important; box-shadow: none !important; }
[data-testid="stNumberInputContainer"], [data-testid="stNumberInputContainer"] > div { background: var(--surface) !important; border-color: var(--border) !important; }
[data-testid="stNumberInput"] button { background: var(--surface) !important; color: var(--text) !important; border-color: var(--border) !important; }
[data-baseweb="popover"] ul, [data-baseweb="menu"] { background: var(--surface) !important; color: var(--text) !important; }
.stButton > button, .stDownloadButton > button, [data-testid="stFormSubmitButton"] > button
  { background: transparent; color: var(--text); border: 1px solid var(--border); border-radius: 8px; font-weight: 500; text-transform: none; box-shadow: none; }
.stButton > button:hover, .stDownloadButton > button:hover { border-color: var(--accent); color: var(--accent); }
button[data-testid="stBaseButton-primary"], button[data-testid="stBaseButton-primaryFormSubmit"]
  { background: var(--accent) !important; color: var(--on-accent) !important; border-color: var(--accent) !important; }
.st-key-clear button { border: 0; background: transparent; color: var(--muted); padding-left: 0; }
button[data-testid="stBaseButton-segmented_control"] { background: var(--surface); color: var(--muted); border: 1px solid var(--border); }
button[data-testid="stBaseButton-segmented_controlActive"] { background: var(--accent); color: var(--on-accent); border: 1px solid var(--accent); }
button[data-testid="stBaseButton-segmented_controlActive"] p, button[data-testid="stBaseButton-primary"] p,
button[data-testid="stBaseButton-primaryFormSubmit"] p { color: var(--on-accent) !important; }
[data-testid="stRadio"] [role="radiogroup"] { gap: .4rem; }
[data-testid="stRadio"] label { border: 1px solid var(--border); border-radius: 999px; padding: .15rem .8rem; background: var(--surface); }
[data-testid="stExpander"], [data-testid="stForm"] { border: 1px solid var(--border); border-radius: 12px; background: var(--surface); }
[data-testid="stExpander"] summary { color: var(--text); }
[data-testid="stChatMessageAvatarUser"], [data-testid="stChatMessageAvatarAssistant"] { display: none; }
[data-testid="stChatMessage"] { background: transparent; padding: .35rem 0; }
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) { flex-direction: row-reverse; }
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) [data-testid="stChatMessageContent"]
  { flex: 0 1 auto; background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: .55rem .9rem; max-width: 80%; margin: 0 0 0 auto !important; }
[data-testid="stBottom"] > div, [data-testid="stBottomBlockContainer"] { background: var(--bg); }
[data-testid="stChatInput"] { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; }
[data-testid="stChatInput"]:focus-within { border-color: var(--accent); }
.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 10px; }
.card { border: 1px solid var(--border); border-radius: 10px; padding: .65rem .8rem; background: var(--bg); }
.card .city { font-size: 11px; letter-spacing: .09em; text-transform: uppercase; color: var(--muted); }
.card .pg { font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 12px; color: var(--accent); margin-left: .5rem; }
.card .snip { font-size: 13px; color: var(--muted); margin-top: .3rem; display: -webkit-box; -webkit-line-clamp: 2;
  -webkit-box-orient: vertical; overflow: hidden; }
.notice { border-left: 3px solid var(--accent); background: var(--surface); padding: .7rem 1rem; border-radius: 0 10px 10px 0; }
.badge { display: inline-block; padding: 4px 14px; border-radius: 999px; font-size: 13px; font-weight: 500; border: 1px solid; margin-bottom: .8rem; }
.badge.good { background: var(--good-bg); color: var(--good-fg); border-color: var(--good-fg); }
.badge.warn { background: var(--warn-bg); color: var(--warn-fg); border-color: var(--warn-fg); }
.badge.info { background: var(--info-bg); color: var(--info-fg); border-color: var(--info-fg); }
"""


def get_css(theme):
    root = ":root{" + "".join(f"--{k.replace('_', '-')}:{v};" for k, v in PALETTES[theme].items()) + "}"
    return f"<style>{root}{BASE_CSS}</style>"


def favicon():
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (64, 64), PALETTES["light"]["accent"])
    ImageDraw.Draw(img).rectangle([20, 14, 28, 50], fill="white")
    ImageDraw.Draw(img).rectangle([28, 14, 44, 22], fill="white")
    ImageDraw.Draw(img).rectangle([28, 30, 44, 38], fill="white")
    return img


def seg(label, options, key, default):
    """Segmented control with a pill-styled radio fallback; never returns None."""
    if hasattr(st, "segmented_control"):
        value = st.segmented_control(label, options, default=default, key=key, label_visibility="collapsed")
    else:
        value = st.radio(label, options, index=options.index(default), key=key, horizontal=True, label_visibility="collapsed")
    if value:
        st.session_state["_last_" + key] = value
    return value or st.session_state.get("_last_" + key, default)


@st.cache_resource(show_spinner=False)
def load_pipeline():
    import pipeline
    pipeline.get_graphs()
    return pipeline


def call_backend(kind, payload):
    """kind is 'ask' or 'report'. Returns {answer, sources, abstained}, or None after showing a friendly error."""
    api = os.environ.get("API_URL")
    try:
        if api:
            import requests
            r = requests.post(f"{api.rstrip('/')}/{kind}", json=payload, timeout=120)
            r.raise_for_status()
            return r.json()
        pipe = load_pipeline()
        return pipe.run_ask(**payload) if kind == "ask" else pipe.run_report(payload)
    except Exception as e:
        traceback.print_exc()  # details go to the server log, not the page
        if api and e.__class__.__name__ in ("ConnectionError", "Timeout", "ConnectTimeout", "ReadTimeout"):
            st.error(f"The review service at {api} is unreachable. Check that it is running.")
        else:
            st.error("Something went wrong while contacting the model. Check the API key and try again.")
        return None


def render_header():
    left, mid, right = st.columns([2, 3.2, 1.4], vertical_alignment="center")
    left.markdown('<div class="wordmark">Bylaw<b>Check</b></div>', unsafe_allow_html=True)
    with mid:
        seg("City", CITIES, "city", "All")
    with right:
        st.toggle("Dark mode", key="dark")
    st.markdown('<div class="tag">Building regulations for Delhi, Mumbai and Hyderabad, searchable and cited.</div>'
                '<div class="note">Pre-check only. Confirm with the municipal authority or an architect.</div>',
                unsafe_allow_html=True)


def render_sources(sources):
    if not sources:
        return
    cards = "".join(
        f'<div class="card" title="{html.escape(s["snippet"])}"><span class="city">{html.escape(s["city"])}</span>'
        f'<span class="pg">p. {s["page"]}</span><div class="snip">{html.escape(s["snippet"])}</div></div>'
        for s in sources)
    with st.expander(f"Sources ({len(sources)})"):
        st.markdown(f'<div class="cards">{cards}</div>', unsafe_allow_html=True)


def render_badge(label):
    st.markdown(f'<span class="badge {RATINGS[label]}">{label}</span>', unsafe_allow_html=True)


def render_answer(res):
    if res["abstained"]:
        st.markdown(f'<div class="notice">{html.escape(res["answer"])}</div>', unsafe_allow_html=True)
    else:
        st.markdown(res["answer"])
        render_sources(res["sources"])


def quick_check():
    ss = st.session_state
    q = ss.pop("pending", None)
    if ss.msgs and st.button("Clear chat", key="clear"):
        ss.msgs = []
        st.rerun()
    if not ss.msgs and not q:
        st.markdown('<div class="eyebrow">Try asking</div>', unsafe_allow_html=True)
        cols = st.columns(2)
        for i, ex in enumerate(EXAMPLES):
            cols[i % 2].button(ex, key=f"ex{i}", use_container_width=True, on_click=lambda e=ex: ss.update(pending=e))
    for m in ss.msgs:
        with st.chat_message(m["role"]):
            if m["role"] == "user":
                st.markdown(m["content"])
            else:
                render_answer(m)
    q = st.chat_input("Ask about height, setbacks, FSI, parking...") or q
    if q:
        with st.chat_message("user"):
            st.markdown(q)
        with st.chat_message("assistant"):
            with st.spinner("Searching the regulations..."):
                res = call_backend("ask", {"question": q, "city": ss.city_used, "k": ss.k})
            if res:
                render_answer(res)
        if res:
            ss.msgs += [{"role": "user", "content": q}, {"role": "assistant", "answer": res["answer"],
                                                         "sources": res["sources"], "abstained": res["abstained"]}]

def split_rating(md):
    first, _, rest = md.strip().partition("\n")
    for label in RATINGS:
        if first.lower().lstrip("*# ").startswith("rating") and label.lower() in first.lower():
            return label, rest.strip()
    return None, md


def plan_review():
    ss = st.session_state
    default_city = ss.city_used if ss.city_used != "All" else "Delhi"
    with st.form("plan"):
        c1, c2 = st.columns(2)
        city = c1.selectbox("City", CITIES[:3], index=CITIES.index(default_city))
        use = c2.selectbox("Use", ["Residential", "Commercial", "Mixed"])
        area = c1.number_input("Plot area (sq m)", min_value=0.0, value=None, step=10.0)
        road = c2.number_input("Road width (m)", min_value=0.0, value=None, step=0.5)
        floors = c1.number_input("Floors", min_value=0, value=None, step=1)
        height = c2.number_input("Height (m)", min_value=0.0, value=None, step=0.5)
        with st.expander("Optional details"):
            o1, o2 = st.columns(2)
            fsi = o1.number_input("FSI", min_value=0.0, value=None, step=0.1)
            parking = o2.number_input("Parking spaces", min_value=0, value=None, step=1)
            front = o1.number_input("Front setback (m)", min_value=0.0, value=None, step=0.5)
            side = o2.number_input("Side setback (m)", min_value=0.0, value=None, step=0.5)
            rear = o1.number_input("Rear setback (m)", min_value=0.0, value=None, step=0.5)
            notes = st.text_area("Notes", placeholder="Anything else the reviewer should know")
        go = st.form_submit_button("Generate review", type="primary")
    if go:
        extras = {"fsi": fsi, "front_setback": front, "side_setback": side, "rear_setback": rear,
                  "parking_spaces": parking, "notes": notes.strip() or None}
        payload = {"city": city, "use": use, "plot_area": area, "road_width": road, "floors": floors,
                   "height": height, "extras": extras}  # empty fields stay None -> "not provided"
        with st.spinner("Reviewing against the regulations..."):
            ss.report = call_backend("report", payload)
    if ss.report:
        label, body = split_rating(ss.report["answer"])
        if label:
            render_badge(label)
        st.markdown(body)
        render_sources(ss.report["sources"])
        st.download_button("Download report (.md)", ss.report["answer"], "plan_review.md", "text/markdown")


def sidebar():
    with st.sidebar:
        st.markdown('<div class="eyebrow">Advanced</div>', unsafe_allow_html=True)
        st.slider("Passages retrieved (top-k)", 3, 8, 5, key="k")
        with st.expander("About"):
            if os.environ.get("API_URL"):
                st.write(f"Mode: API at {os.environ['API_URL']}")
            else:
                st.write("Mode: in-process")
                try:
                    for city, s in load_pipeline().index_stats().items():
                        st.write(f"{city}: {s['pages']} pages, {s['chunks']} chunks")
                except Exception:
                    st.write("Index not found. Run build_index.py.")


def main():
    st.set_page_config(page_title="BylawCheck", page_icon=favicon(), layout="wide", initial_sidebar_state="collapsed")
    ss = st.session_state
    ss.setdefault("dark", False)
    ss.setdefault("msgs", [])
    ss.setdefault("report", None)
    st.markdown(get_css("dark" if ss.dark else "light"), unsafe_allow_html=True)
    sidebar()
    render_header()
    ss.city_used = ss.get("_last_city", "All")
    mode = seg("Mode", MODES, "mode", MODES[0])
    st.markdown(f'<div class="sub">{SUBTITLES[mode]}</div>', unsafe_allow_html=True)
    if mode == MODES[0]:
        quick_check()
    else:
        plan_review()


main()
