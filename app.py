"""
Streamlit UI for the multi-agent research pipeline (pipeline.py).

Run with:
    streamlit run app.py

This file expects `pipeline.py` (with `run_research_pipeline`) to be in the
same folder, alongside `agents.py` and whatever else it imports.
"""

import io
import sys
import time
import threading
import contextlib

import streamlit as st

from pipeline import run_research_pipeline


# ----------------------------------------------------------------------
# Page setup
# ----------------------------------------------------------------------
st.set_page_config(
    page_title="Multi-Agent Research Assistant",
    page_icon="🔎",
    layout="wide",
)

st.title("🔎 Multi-Agent Research Assistant")
st.caption(
    "Search agent → Reader agent → Writer chain → Critic chain, "
    "all wired up through `pipeline.py`."
)

if "history" not in st.session_state:
    st.session_state.history = []  # list of {topic, state}
if "is_running" not in st.session_state:
    st.session_state.is_running = False


# ----------------------------------------------------------------------
# Sidebar: past runs
# ----------------------------------------------------------------------
with st.sidebar:
    st.header("📜 Past runs")
    if not st.session_state.history:
        st.caption("No runs yet. Your research history will show up here.")
    else:
        for i, run in enumerate(reversed(st.session_state.history)):
            if st.button(f"{run['topic']}", key=f"hist_{i}"):
                st.session_state.selected_run = run
    st.divider()
    st.caption("Built on top of your existing `pipeline.py` — no pipeline logic was changed.")


# ----------------------------------------------------------------------
# Helper: run the pipeline in a background thread while capturing
# everything it prints, so we can stream logs into the UI live.
# ----------------------------------------------------------------------
def run_pipeline_with_live_logs(topic: str, log_placeholder, status):
    buffer = io.StringIO()
    result_container = {}
    error_container = {}

    def worker():
        try:
            with contextlib.redirect_stdout(buffer):
                result_container["state"] = run_research_pipeline(topic)
        except Exception as e:  # noqa: BLE001
            error_container["error"] = e

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()

    last_len = 0
    step_labels = {
        "step 1": "🔍 Searching the web...",
        "step 2": "📄 Reading top sources...",
        "step 3": "✍️ Drafting the report...",
        "step 4": "🧐 Critic is reviewing...",
    }

    while thread.is_alive():
        text = buffer.getvalue()
        if len(text) != last_len:
            log_placeholder.code(text, language="text")
            last_len = len(text)
            lowered = text.lower()
            for key, label in step_labels.items():
                if key in lowered:
                    status.update(label=label)
        time.sleep(0.3)

    # final flush after thread finishes
    log_placeholder.code(buffer.getvalue(), language="text")

    if "error" in error_container:
        raise error_container["error"]

    return result_container.get("state", {})


# ----------------------------------------------------------------------
# Main input area
# ----------------------------------------------------------------------
col1, col2 = st.columns([4, 1])
with col1:
    topic = st.text_input(
        "Research topic",
        placeholder="e.g. Impact of quantum computing on cryptography",
        disabled=st.session_state.is_running,
    )
with col2:
    st.write("")
    st.write("")
    run_clicked = st.button(
        "Run research",
        type="primary",
        use_container_width=True,
        disabled=st.session_state.is_running or not topic.strip(),
    )

if run_clicked and topic.strip():
    st.session_state.is_running = True
    st.divider()
    st.subheader(f"Researching: *{topic}*")

    with st.status("Starting agents...", expanded=True) as status:
        log_placeholder = st.empty()
        try:
            state = run_pipeline_with_live_logs(topic, log_placeholder, status)
            status.update(label="✅ Done!", state="complete", expanded=False)
        except Exception as e:  # noqa: BLE001
            status.update(label="❌ Pipeline failed", state="error", expanded=True)
            st.error(f"Something went wrong: {e}")
            state = None

    st.session_state.is_running = False

    if state:
        st.session_state.history.append({"topic": topic, "state": state})
        st.session_state.selected_run = {"topic": topic, "state": state}


# ----------------------------------------------------------------------
# Results display
# ----------------------------------------------------------------------
def show_results(run):
    topic = run["topic"]
    state = run["state"]

    st.divider()
    st.subheader(f"📋 Results for: *{topic}*")

    tab_report, tab_critic, tab_search, tab_scraped = st.tabs(
        ["📝 Final Report", "🧐 Critic Feedback", "🔍 Search Results", "📄 Scraped Content"]
    )

    with tab_report:
        report = state.get("report", "")
        st.markdown(report if isinstance(report, str) else str(report))
        st.download_button(
            "Download report as .md",
            data=report if isinstance(report, str) else str(report),
            file_name=f"{topic[:40].strip().replace(' ', '_')}_report.md",
            mime="text/markdown",
        )

    with tab_critic:
        feedback = state.get("feedback", "")
        st.markdown(feedback if isinstance(feedback, str) else str(feedback))

    with tab_search:
        st.markdown(state.get("search_results", ""))

    with tab_scraped:
        st.markdown(state.get("scraped_content", ""))


if "selected_run" in st.session_state and st.session_state.selected_run:
    show_results(st.session_state.selected_run)
elif st.session_state.history:
    show_results(st.session_state.history[-1])