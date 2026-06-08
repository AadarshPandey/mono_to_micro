# frontend/pages/02_progress.py
"""
Page 02 — Real-time Job Progress
"""

import time
import streamlit as st
import httpx

API_BASE = "http://localhost:8000"

st.set_page_config(page_title="Progress | Monolith Breaker", page_icon="📊", layout="wide")
st.title("📊 Pipeline Progress")

# ── Job ID input ───────────────────────────────────────────────────────────

job_id = st.text_input(
    "Job ID",
    value=st.session_state.get("job_id", ""),
    help="Enter the job ID from the upload step.",
)

STATUS_COLORS = {
    "queued": "🔵", "parsing": "🟡", "graphing": "🟡", "embedding": "🟡",
    "ai_processing": "🟡", "gate_a": "🟠", "contracting": "🟡",
    "gate_b": "🟠", "scaffolding": "🟡", "done": "🟢", "error": "🔴",
}


def _headers() -> dict:
    """Build headers with API key and model from session state."""
    h = {}
    key = st.session_state.get("gemini_api_key", "")
    if key:
        h["X-Gemini-API-Key"] = key
    model = st.session_state.get("gemini_model", "")
    if model:
        h["X-Gemini-Model"] = model
    return h


# ── Polling loop ───────────────────────────────────────────────────────────

if job_id:
    st.session_state.job_id = job_id
    status_placeholder = st.empty()
    progress_bar = st.progress(0)
    auto_refresh = st.checkbox("Auto-refresh (2s)", value=True)

    def fetch_and_display():
        try:
            r = httpx.get(f"{API_BASE}/jobs/{job_id}", headers=_headers(), timeout=5)
            r.raise_for_status()
            data = r.json()

            status = data.get("status", "unknown")
            progress = data.get("progress", 0)
            step = data.get("current_step", "")
            error = data.get("error")
            icon = STATUS_COLORS.get(status, "⚪")

            progress_bar.progress(progress / 100)

            with status_placeholder.container():
                col1, col2 = st.columns([1, 3])
                with col1:
                    st.metric("Status", f"{icon} {status.upper()}")
                    st.metric("Progress", f"{progress}%")
                with col2:
                    st.markdown(f"**Current Step:** {step}")
                    if error:
                        st.error(f"Error: {error}")

                if status == "gate_a":
                    st.warning("🗺️ Pipeline paused at **Gate A** — navigate to **Boundaries** to review.")
                elif status == "gate_b":
                    st.warning("📜 Pipeline paused at **Gate B** — navigate to **Contracts** to review.")
                elif status == "done":
                    st.success("✅ Complete! Navigate to **Download** to get your output.")
                    return True
                elif status == "error":
                    return True
            return False
        except httpx.ConnectError:
            status_placeholder.error("Cannot connect to backend API.")
            return True
        except Exception as exc:
            status_placeholder.error(f"Error: {exc}")
            return True

    done = fetch_and_display()
    if auto_refresh and not done:
        time.sleep(2)
        st.rerun()
else:
    st.info("Enter a Job ID or upload source code first.")
