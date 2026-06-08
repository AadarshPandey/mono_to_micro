# frontend/pages/01_upload.py
"""
Page 01 — File Upload & Job Submission
"""

import streamlit as st
import httpx

API_BASE = "http://localhost:8000"

st.set_page_config(page_title="Upload | Monolith Breaker", page_icon="📤", layout="wide")

# ── Sidebar API key (shared across pages) ──────────────────────────────────
st.sidebar.subheader("🔑 Gemini API Key")
api_key = st.sidebar.text_input(
    "API Key", type="password",
    value=st.session_state.get("gemini_api_key", ""),
    key="sidebar_key_upload",
    placeholder="AIzaSy...",
)
if api_key:
    st.session_state.gemini_api_key = api_key

# ── Sidebar model selector ────────────────────────────────────────────────
AVAILABLE_MODELS = {
    "gemini-2.5-flash":           "⚡ Best balance of speed & quality — recommended",
    "gemini-2.5-pro":             "🧠 Highest quality — complex codebases",
    "gemini-2.0-flash":           "🚀 Fast & reliable — quick iterations",
    "gemini-2.0-flash-lite":      "💨 Fastest & cheapest — rapid prototyping",
    "gemini-3.5-flash":           "✨ Latest gen flash — cutting-edge",
    "gemini-3-pro-preview":       "🔬 Next-gen pro preview — best reasoning",
    "gemini-3-flash-preview":     "⚡ Next-gen flash preview",
    "gemini-3.1-pro-preview":     "🔬 Latest pro preview",
    "gemini-3.1-flash-lite-preview": "💨 Latest lite preview",
    "gemini-3.1-flash-lite":      "💨 Latest lite — ultra-fast",
}
model_names = list(AVAILABLE_MODELS.keys())

st.sidebar.subheader("🤖 Model")
selected_model = st.sidebar.selectbox(
    "Gemini Model",
    model_names,
    index=st.session_state.get("model_index", 0),
    key="sidebar_model_upload",
    help="Select the Gemini model for AI analysis.",
)
st.session_state.gemini_model = selected_model
st.session_state.model_index = model_names.index(selected_model)
st.sidebar.caption(AVAILABLE_MODELS[selected_model])

st.title("📤 Upload Source Code")
st.markdown("Upload your monolithic codebase to begin decomposition.")

if not st.session_state.get("gemini_api_key"):
    st.error("⚠️ Enter your **Gemini API Key** in the sidebar before uploading.")

# ── Upload form ────────────────────────────────────────────────────────────

with st.form("upload_form"):
    source_file = st.file_uploader(
        "Source Code (ZIP)",
        type=["zip"],
        help="Zip archive containing your monolith source code.",
    )

    otel_file = st.file_uploader(
        "OTel Traces (JSON, optional)",
        type=["json"],
        help="OpenTelemetry JSON export for runtime call analysis.",
    )

    col1, col2 = st.columns(2)
    with col1:
        language = st.selectbox(
            "Language",
            ["Auto-detect", "java", "python", "csharp", "go"],
            help="Source language. Auto-detect uses file extensions.",
        )
    with col2:
        hint_services = st.number_input(
            "Target service count (optional)",
            min_value=0, max_value=50, value=0,
            help="Hint for the AI on how many services to target. 0 = auto.",
        )

    submitted = st.form_submit_button("🚀 Start Decomposition", use_container_width=True)

# ── Handle submission ──────────────────────────────────────────────────────

if submitted:
    if source_file is None:
        st.error("Please upload a source code ZIP file.")
    elif not st.session_state.get("gemini_api_key"):
        st.error("Please enter your Gemini API key in the sidebar.")
    else:
        with st.spinner("Uploading and starting pipeline..."):
            try:
                files = {"source_code": (source_file.name, source_file.getvalue(), "application/zip")}
                if otel_file:
                    files["otel_traces"] = (otel_file.name, otel_file.getvalue(), "application/json")

                data = {}
                if language != "Auto-detect":
                    data["language"] = language
                if hint_services > 0:
                    data["hint_services"] = str(hint_services)

                headers = {
                    "X-Gemini-API-Key": st.session_state.gemini_api_key,
                    "X-Gemini-Model": st.session_state.get("gemini_model", "gemini-2.5-flash"),
                }

                r = httpx.post(f"{API_BASE}/upload", files=files, data=data, headers=headers, timeout=30)
                r.raise_for_status()
                result = r.json()

                job_id = result["job_id"]
                st.session_state.job_id = job_id

                st.success(f"✅ Job created: `{job_id}`")
                st.info("Navigate to **Progress** to track the pipeline.")

            except httpx.ConnectError:
                st.error("❌ Cannot connect to backend. Is the API running?")
            except Exception as exc:
                st.error(f"❌ Upload failed: {exc}")
