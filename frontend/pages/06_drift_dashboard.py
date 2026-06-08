# frontend/pages/06_drift_dashboard.py
"""
Page 06 — Drift Detection Dashboard
"""

import streamlit as st
import httpx

API_BASE = "http://localhost:8000"

st.set_page_config(page_title="Drift | Monolith Breaker", page_icon="🔍", layout="wide")
st.title("🔍 Drift Detection Dashboard")

job_id = st.text_input("Job ID", value=st.session_state.get("job_id", ""))

if not job_id:
    st.info("Enter a Job ID to view drift alerts.")
    st.stop()

# ── Trigger scan ───────────────────────────────────────────────────────────

st.subheader("Run Drift Scan")
col1, col2 = st.columns([3, 1])
with col1:
    repo_path = st.text_input("Service Repository Path", placeholder="/path/to/deployed/service")
with col2:
    st.write("")  # spacing
    st.write("")
    scan_clicked = st.button("🔎 Run Scan", use_container_width=True)

if scan_clicked and repo_path:
    try:
        r = httpx.post(
            f"{API_BASE}/drift/scan",
            json={"job_id": job_id, "service_repo_path": repo_path},
            timeout=10,
        )
        r.raise_for_status()
        st.success("Scan started! Refresh to see results.")
    except Exception as exc:
        st.error(f"Scan failed: {exc}")

# ── Display alerts ─────────────────────────────────────────────────────────

st.divider()
st.subheader("Drift Alerts")

VIOLATION_COLORS = {
    "CIRCULAR_DEP": "🔴",
    "SHARED_DB": "🟠",
    "CROSS_BOUNDARY_CALL": "🟡",
    "GOD_CLASS_REGROWTH": "🟣",
}

try:
    r = httpx.get(f"{API_BASE}/drift/alerts", params={"job_id": job_id}, timeout=10)
    r.raise_for_status()
    alerts = r.json().get("alerts", [])

    if not alerts:
        st.success("✅ No drift violations detected!")
    else:
        st.warning(f"⚠️ {len(alerts)} violation(s) detected")

        for alert in alerts:
            vtype = alert.get("violation_type", "UNKNOWN")
            icon = VIOLATION_COLORS.get(vtype, "⚪")
            resolved = alert.get("resolved", False)
            svc = alert.get("service_name", "")
            detected = alert.get("detected_at", "")

            status_badge = "✅ Resolved" if resolved else "❌ Active"

            st.markdown(
                f"{icon} **{vtype}** — `{svc}` — {detected[:19]} — {status_badge}"
            )

except httpx.ConnectError:
    st.error("Cannot connect to backend API.")
except Exception as exc:
    st.error(f"Error fetching alerts: {exc}")
