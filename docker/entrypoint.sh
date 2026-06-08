#!/bin/bash
set -e

# ── Monolith Breaker Entrypoint ───────────────────────────────────────────
# Usage:
#   docker run ... monolith-breaker all       # both backend + frontend (default)
#   docker run ... monolith-breaker backend   # FastAPI only
#   docker run ... monolith-breaker frontend  # Streamlit only

MODE="${1:-all}"

echo "╔══════════════════════════════════════╗"
echo "║       🔨 Monolith Breaker            ║"
echo "╚══════════════════════════════════════╝"
echo "Mode: $MODE"

case "$MODE" in
  backend)
    echo "Starting FastAPI backend on :8000..."
    exec uvicorn backend.main:app --host 0.0.0.0 --port 8000
    ;;
  frontend)
    echo "Starting Streamlit frontend on :8501..."
    exec streamlit run frontend/app.py \
      --server.address 0.0.0.0 \
      --server.port 8501 \
      --server.headless true \
      --browser.gatherUsageStats false
    ;;
  all)
    echo "Starting backend on :8000 and frontend on :8501..."

    # Start backend in background
    uvicorn backend.main:app --host 0.0.0.0 --port 8000 &
    BACKEND_PID=$!

    # Start frontend in foreground
    streamlit run frontend/app.py \
      --server.address 0.0.0.0 \
      --server.port 8501 \
      --server.headless true \
      --browser.gatherUsageStats false &
    FRONTEND_PID=$!

    # Wait for either to exit
    wait -n $BACKEND_PID $FRONTEND_PID
    EXIT_CODE=$?

    # Kill the other process
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null || true
    exit $EXIT_CODE
    ;;
  *)
    echo "Unknown mode: $MODE"
    echo "Usage: entrypoint.sh [all|backend|frontend]"
    exit 1
    ;;
esac
