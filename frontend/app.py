# frontend/app.py
"""
Streamlit Frontend — Main entry point for Monolith Breaker UI.
"""

import streamlit as st

st.set_page_config(
    page_title="Monolith Breaker",
    page_icon="🔨",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Sidebar ────────────────────────────────────────────────────────────────

st.sidebar.title("🔨 Monolith Breaker")
st.sidebar.markdown("AI-powered monolith → microservice decomposition")

st.sidebar.divider()

# API Key input — stored in session_state, never saved to disk
st.sidebar.subheader("🔑 Configuration")
api_key = st.sidebar.text_input(
    "Gemini API Key",
    type="password",
    value=st.session_state.get("gemini_api_key", ""),
    help="Your Google Gemini API key. Get one at https://aistudio.google.com/app/apikey",
    placeholder="AIzaSy...",
)
if api_key:
    st.session_state.gemini_api_key = api_key
    st.sidebar.success("✅ API key set")
else:
    st.sidebar.warning("⚠️ Enter your Gemini API key to use AI features")

# ── Model selector ─────────────────────────────────────────────────────
AVAILABLE_MODELS = {
    "gemini-2.5-flash":           "⚡ Best balance of speed & quality — recommended default",
    "gemini-2.5-pro":             "🧠 Highest quality, slower — complex legacy codebases",
    "gemini-2.0-flash":           "🚀 Fast & reliable — quick iterations",
    "gemini-2.0-flash-lite":      "💨 Fastest & cheapest — rapid prototyping",
    "gemini-3.5-flash":           "✨ Latest gen flash — cutting-edge speed",
    "gemini-3-pro-preview":       "🔬 Next-gen pro (preview) — best reasoning",
    "gemini-3-flash-preview":     "⚡ Next-gen flash (preview) — fast + smart",
    "gemini-3.1-pro-preview":     "🔬 Latest pro preview — newest capabilities",
    "gemini-3.1-flash-lite-preview": "💨 Latest lite preview — ultra-fast",
    "gemini-3.1-flash-lite":      "💨 Latest lite — ultra-fast, production ready",
}

model_names = list(AVAILABLE_MODELS.keys())
default_idx = 0  # gemini-2.5-flash

selected_model = st.sidebar.selectbox(
    "🤖 Gemini Model",
    model_names,
    index=st.session_state.get("model_index", default_idx),
    format_func=lambda m: f"{m}",
    help="Select the Gemini model for AI analysis.",
)
st.session_state.gemini_model = selected_model
st.session_state.model_index = model_names.index(selected_model)
st.sidebar.caption(AVAILABLE_MODELS[selected_model])

st.sidebar.divider()

st.sidebar.markdown("""
**Pages**
- 📤 **Upload** — Submit source code
- 📊 **Progress** — Track pipeline
- 🗺️ **Boundaries** — Review Gate A
- 📜 **Contracts** — Review Gate B
- 📦 **Download** — Get output
- 🔍 **Drift** — Monitor drift
""")

# ── API config ─────────────────────────────────────────────────────────────

API_BASE = "http://localhost:8000"

if "job_id" not in st.session_state:
    st.session_state.job_id = None


def get_api_headers() -> dict:
    """Return headers with Gemini API key and model for backend calls."""
    headers = {}
    key = st.session_state.get("gemini_api_key", "")
    if key:
        headers["X-Gemini-API-Key"] = key
    model = st.session_state.get("gemini_model", "")
    if model:
        headers["X-Gemini-Model"] = model
    return headers


# ── Landing page ───────────────────────────────────────────────────────────

st.title("🔨 Monolith Breaker")
st.markdown("""
### AI-Powered Monolith-to-Microservice Decomposition

Upload your monolithic codebase and let AI analyse, decompose, and scaffold
standalone microservices — with human-in-the-loop review gates.

**Pipeline:**
1. 📤 Upload source code (zip) + optional OTel traces
2. 🔬 Static + dynamic analysis via Tree-sitter & Neo4j
3. 🤖 AI boundary detection with confidence scoring
4. 🗺️ **Gate A** — Review & approve service boundaries
5. 📜 API contract generation (OpenAPI / AsyncAPI / gRPC)
6. 📝 **Gate B** — Review & approve contracts
7. 🏗️ Code scaffolding + infrastructure generation
8. 📦 Download ready-to-deploy microservices
""")

# ── Health check ───────────────────────────────────────────────────────────

st.divider()
col1, col2 = st.columns(2)

with col1:
    st.subheader("System Status")
    try:
        import httpx
        r = httpx.get(f"{API_BASE}/health", timeout=3)
        if r.status_code == 200:
            st.success("✅ Backend API: Connected")
        else:
            st.error(f"❌ Backend API: HTTP {r.status_code}")
    except Exception:
        st.warning("⚠️ Backend API: Not reachable (start with `uvicorn backend.main:app --reload`)")

with col2:
    st.subheader("Quick Start")
    if not api_key:
        st.error("👆 Enter your **Gemini API Key** in the sidebar first!")
    else:
        st.info("👉 Navigate to **Upload** in the sidebar to begin.")
    if st.session_state.job_id:
        st.code(f"Active Job: {st.session_state.job_id}")
