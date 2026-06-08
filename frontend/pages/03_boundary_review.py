# frontend/pages/03_boundary_review.py
"""
Page 03 — Gate A: Service Boundary Review
"""

import json
import streamlit as st
import httpx

API_BASE = "http://localhost:8000"

st.set_page_config(page_title="Boundaries | Monolith Breaker", page_icon="🗺️", layout="wide")
st.title("🗺️ Gate A: Service Boundary Review")

job_id = st.text_input("Job ID", value=st.session_state.get("job_id", ""))

if not job_id:
    st.info("Enter a Job ID to review boundaries.")
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


# ── Fetch proposals ────────────────────────────────────────────────────────

try:
    r = httpx.get(f"{API_BASE}/review/boundaries/{job_id}", headers=_headers(), timeout=10)
    r.raise_for_status()
    data = r.json()
except httpx.ConnectError:
    st.error("Cannot connect to backend API.")
    st.stop()
except httpx.HTTPStatusError as exc:
    st.error(f"Error: {exc.response.json().get('detail', str(exc))}")
    st.stop()

proposals = data.get("boundary_proposals", [])
scores = data.get("confidence_scores", [])

if not proposals:
    st.warning("No boundary proposals available. Pipeline may not have reached Gate A yet.")
    st.stop()

# ── Display boundaries ────────────────────────────────────────────────────

st.markdown(f"**{len(proposals)} service boundaries proposed**")

score_map = {s.get("boundary_name", ""): s for s in scores}

for i, boundary in enumerate(proposals):
    name = boundary.get("name", f"Service {i+1}")
    classes = boundary.get("classes", [])
    rationale = boundary.get("rationale", "")
    api_style = boundary.get("suggested_api_style", "REST")
    deps = boundary.get("dependencies_on", [])

    score_data = score_map.get(name, {})
    confidence = score_data.get("confidence", 0)
    flagged = score_data.get("flagged", False)

    # Color-code confidence
    if confidence >= 0.65:
        badge = f"🟢 {confidence:.2f}"
    elif confidence >= 0.45:
        badge = f"🟡 {confidence:.2f}"
    else:
        badge = f"🔴 {confidence:.2f}"

    with st.expander(f"{'⚠️ ' if flagged else ''}{name}  —  {len(classes)} classes  |  Confidence: {badge}", expanded=flagged):
        col1, col2 = st.columns([2, 1])
        with col1:
            st.markdown(f"**Rationale:** {rationale}")
            st.markdown(f"**API Style:** `{api_style}`")
            st.markdown(f"**Dependencies:** {', '.join(deps) if deps else 'None'}")
        with col2:
            st.markdown("**Classes:**")
            for cls in classes:
                st.code(cls, language=None)

        if flagged:
            st.warning("⚠️ Low confidence — requires explicit confirmation.")
            st.checkbox(f"I confirm boundary '{name}' is acceptable", key=f"confirm_{i}")

# ── Editable JSON ──────────────────────────────────────────────────────────

st.divider()
st.subheader("Edit Boundaries (Advanced)")
edited_json = st.text_area(
    "Modify the boundary proposals JSON if needed:",
    value=json.dumps(proposals, indent=2),
    height=300,
)

# ── Approve / Reject ──────────────────────────────────────────────────────

st.divider()
col1, col2 = st.columns(2)

with col1:
    if st.button("✅ Approve Boundaries", use_container_width=True, type="primary"):
        try:
            parsed = json.loads(edited_json)
            r = httpx.post(
                f"{API_BASE}/review/boundaries",
                json={"job_id": job_id, "decision": "approved", "boundaries": parsed},
                headers=_headers(),
                timeout=120,
            )
            r.raise_for_status()
            st.success("Boundaries approved! Pipeline resuming — generating contracts...")
            st.info("Navigate to **Progress** to track contract generation.")
        except json.JSONDecodeError:
            st.error("Invalid JSON in the editor.")
        except Exception as exc:
            st.error(f"Failed: {exc}")

with col2:
    if st.button("❌ Reject & Re-analyse", use_container_width=True):
        try:
            r = httpx.post(
                f"{API_BASE}/review/boundaries",
                json={"job_id": job_id, "decision": "rejected"},
                headers=_headers(),
                timeout=10,
            )
            st.warning("Boundaries rejected. Adjust parameters and re-upload.")
        except Exception as exc:
            st.error(f"Failed: {exc}")
