# frontend/pages/05_download.py
"""
Page 05 — Output Download
"""

import streamlit as st
import httpx

API_BASE = "http://localhost:8000"

st.set_page_config(page_title="Download | Monolith Breaker", page_icon="📦", layout="wide")
st.title("📦 Download Output")

job_id = st.text_input("Job ID", value=st.session_state.get("job_id", ""))

if not job_id:
    st.info("Enter a Job ID to download output.")
    st.stop()


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


# ── Check job status ───────────────────────────────────────────────────────

try:
    r = httpx.get(f"{API_BASE}/jobs/{job_id}", headers=_headers(), timeout=5)
    r.raise_for_status()
    job = r.json()
except httpx.ConnectError:
    st.error("Cannot connect to backend API.")
    st.stop()
except Exception as exc:
    st.error(f"Error: {exc}")
    st.stop()

status = job.get("status", "unknown")

if status != "done":
    st.warning(f"Job is not complete yet. Current status: **{status}**")
    st.info("Navigate to **Progress** to track the pipeline.")
    st.stop()

# ── Download ───────────────────────────────────────────────────────────────

st.success("✅ Decomposition complete!")

st.markdown(f"""
### Job Summary
- **Job ID:** `{job_id}`
- **Status:** {status.upper()}
""")

try:
    r = httpx.get(f"{API_BASE}/output/{job_id}", headers=_headers(), timeout=30)
    r.raise_for_status()

    st.download_button(
        label="📥 Download Microservices Archive",
        data=r.content,
        file_name=f"monolith-breaker-{job_id}.zip",
        mime="application/zip",
        use_container_width=True,
        type="primary",
    )

    size_mb = len(r.content) / (1024 * 1024)
    st.caption(f"Archive size: {size_mb:.2f} MB")

except httpx.ConnectError:
    st.error("Cannot connect to backend to download.")
except Exception as exc:
    st.error(f"Download failed: {exc}")
