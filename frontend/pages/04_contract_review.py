# frontend/pages/04_contract_review.py
"""
Page 04 — Gate B: API Contract Review
"""

import streamlit as st
import httpx

API_BASE = "http://localhost:8000"

st.set_page_config(page_title="Contracts | Monolith Breaker", page_icon="📜", layout="wide")
st.title("📜 Gate B: API Contract Review")

job_id = st.text_input("Job ID", value=st.session_state.get("job_id", ""))

if not job_id:
    st.info("Enter a Job ID to review contracts.")
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


# ── Fetch contracts ────────────────────────────────────────────────────────

try:
    r = httpx.get(f"{API_BASE}/review/contracts/{job_id}", headers=_headers(), timeout=10)
    r.raise_for_status()
    data = r.json()
except httpx.ConnectError:
    st.error("Cannot connect to backend API.")
    st.stop()
except httpx.HTTPStatusError as exc:
    st.error(f"Error: {exc.response.json().get('detail', str(exc))}")
    st.stop()

contracts = data.get("contracts", [])

if not contracts:
    st.warning("No contracts available. Pipeline may not have reached Gate B yet.")
    st.stop()

# ── Display contracts ──────────────────────────────────────────────────────

st.markdown(f"**{len(contracts)} service contracts generated**")

approved_flags = {}
edited_contracts = []

for i, contract in enumerate(contracts):
    svc_name = contract.get("service_name", f"Service {i+1}")
    openapi = contract.get("openapi_yaml", "")
    asyncapi = contract.get("asyncapi_yaml")
    proto = contract.get("proto_definition")

    with st.expander(f"📄 {svc_name}", expanded=(i == 0)):
        # OpenAPI tab
        tab_names = ["OpenAPI"]
        if asyncapi:
            tab_names.append("AsyncAPI")
        if proto:
            tab_names.append("Protobuf")

        tabs = st.tabs(tab_names)

        with tabs[0]:
            edited_yaml = st.text_area(
                f"OpenAPI YAML — {svc_name}",
                value=openapi,
                height=400,
                key=f"openapi_{i}",
            )

        if asyncapi and len(tabs) > 1:
            with tabs[1]:
                st.code(asyncapi, language="yaml")

        if proto and len(tabs) > (2 if asyncapi else 1):
            with tabs[-1]:
                st.code(proto, language="protobuf")

        approved_flags[svc_name] = st.checkbox(f"✅ Approve {svc_name}", key=f"approve_{i}")

        edited_contracts.append({
            "service_name": svc_name,
            "openapi_yaml": edited_yaml,
        })

# ── Approve / Reject ──────────────────────────────────────────────────────

st.divider()

all_approved = all(approved_flags.values()) if approved_flags else False

if not all_approved:
    st.warning("All services must be individually approved before submitting.")

col1, col2 = st.columns(2)

with col1:
    if st.button(
        "✅ Submit Approved Contracts",
        use_container_width=True,
        type="primary",
        disabled=not all_approved,
    ):
        try:
            with st.spinner("Generating microservice code — this takes a few minutes..."):
                r = httpx.post(
                    f"{API_BASE}/review/contracts",
                    json={"job_id": job_id, "decision": "approved", "contracts": edited_contracts},
                    headers=_headers(),
                    timeout=600,  # Code gen for 5 services can take 5+ minutes
                )
                r.raise_for_status()
            st.success("✅ Contracts approved! Scaffolding complete!")
            st.info("Navigate to **Download** to get your microservices archive.")
        except Exception as exc:
            st.error(f"Failed: {exc}")

with col2:
    if st.button("❌ Reject Contracts", use_container_width=True):
        try:
            r = httpx.post(
                f"{API_BASE}/review/contracts",
                json={"job_id": job_id, "decision": "rejected"},
                headers=_headers(),
                timeout=10,
            )
            st.warning("Contracts rejected.")
        except Exception as exc:
            st.error(f"Failed: {exc}")
