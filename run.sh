#!/bin/bash
# Trading Intelligence Platform — Start/Stop Script
# Usage: ./run.sh [start|stop|status]

set -e

BACKEND_DIR="$HOME/projects/trading-intel-mvp/backend"
FRONTEND_DIR="$HOME/projects/trading-intel-mvp/frontend"
BACKEND_PORT=8000
FRONTEND_PORT=3000

PID_FILE="/tmp/trading-intel.pids"

start() {
  echo "Starting Trading Intelligence Platform..."

  # Check for Doppler and load secrets if available
  if command -v doppler &> /dev/null && [ -f ".doppler.yaml" ]; then
    echo "  Loading secrets from Doppler..."
    eval "$(doppler secrets download --no-file --format env 2>/dev/null | sed 's/^/export /')"
  fi

  # Start backend
  echo "  Starting backend (FastAPI) on port $BACKEND_PORT..."
  cd "$BACKEND_DIR"
  source venv/bin/activate
  doppler run -- uvicorn app.main:app --host 0.0.0.0 --port $BACKEND_PORT >> /tmp/trading-intel-backend.log 2>&1 &
  BACKEND_PID=$!
  echo "    Backend PID: $BACKEND_PID"

  # Start frontend
  echo "  Starting frontend (Next.js) on port $FRONTEND_PORT..."
  cd "$FRONTEND_DIR"
  doppler run -- npm run dev -- --port $FRONTEND_PORT >> /tmp/trading-intel-frontend.log 2>&1 &
  FRONTEND_PID=$!
  echo "    Frontend PID: $FRONTEND_PID"

  # Save PIDs
  echo "$BACKEND_PID $FRONTEND_PID" > "$PID_FILE"

  echo ""
  echo "Trading Intelligence Platform is running:"
  echo "  Frontend: http://localhost:$FRONTEND_PORT"
  echo "  Backend:  http://localhost:$BACKEND_PORT/docs"
  echo ""
  echo "Logs:"
  echo "  Backend:  tail -f /tmp/trading-intel-backend.log"
  echo "  Frontend: tail -f /tmp/trading-intel-frontend.log"
  echo ""
  echo "Press Ctrl+C to stop."

  # Wait for both processes
  wait $BACKEND_PID $FRONTEND_PID
}

stop() {
  if [ -f "$PID_FILE" ]; then
    BACKEND_PID=$(awk '{print $1}' "$PID_FILE")
    FRONTEND_PID=$(awk '{print $2}' "$PID_FILE")
    echo "Stopping Trading Intelligence Platform..."
    [ -n "$BACKEND_PID" ]  && kill $BACKEND_PID 2>/dev/null && echo "  Backend stopped (PID $BACKEND_PID)"
    [ -n "$FRONTEND_PID" ] && kill $FRONTEND_PID 2>/dev/null && echo "  Frontend stopped (PID $FRONTEND_PID)"
    rm -f "$PID_FILE"
  else
    # Fallback: kill by port
    echo "No PID file found, killing by port..."
    fuser -k $BACKEND_PORT/tcp 2>/dev/null && echo "  Backend port freed"
    fuser -k $FRONTEND_PORT/tcp 2>/dev/null && echo "  Frontend port freed"
  fi
}

status() {
  if [ -f "$PID_FILE" ]; then
    BACKEND_PID=$(awk '{print $1}' "$PID_FILE")
    FRONTEND_PID=$(awk '{print $2}' "$PID_FILE")
    echo "Trading Intelligence Platform status:"
    [ -n "$BACKEND_PID" ]  && kill -0 $BACKEND_PID 2>/dev/null && echo "  Backend:  running (PID $BACKEND_PID)"  || echo "  Backend:  not running"
    [ -n "$FRONTEND_PID" ] && kill -0 $FRONTEND_PID 2>/dev/null && echo "  Frontend: running (PID $FRONTEND_PID)" || echo "  Frontend: not running"
  else
    echo "Not running (no PID file)"
  fi
}

case "${1:-start}" in
  start)   start ;;
  stop)    stop ;;
  status)  status ;;
  *)
    echo "Usage: $0 {start|stop|status}"
    exit 1 ;;
esac
