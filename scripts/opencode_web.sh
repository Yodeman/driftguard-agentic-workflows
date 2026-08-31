#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$ROOT/.venv"
OPENCODE_BIN="${DRIFTGUARD_OPENCODE_BIN:-opencode}"
HOST="${DRIFTGUARD_OPENCODE_WEB_HOST:-127.0.0.1}"
PORT="${DRIFTGUARD_OPENCODE_WEB_PORT:-4096}"
EXPLICIT_URL="${DRIFTGUARD_OPENCODE_WEB_URL:-}"
SERVER_CWD="${DRIFTGUARD_OPENCODE_WEB_CWD:-$ROOT}"
STATE_DIR="$ROOT/evidence/opencode_web"
PID_FILE="$STATE_DIR/server.pid"
URL_FILE="$STATE_DIR/server.url"
CWD_FILE="$STATE_DIR/server.cwd"
LOG_FILE="$STATE_DIR/server.log"
PROJECT_TAB_FILE="$STATE_DIR/project_tab.url"

mkdir -p "$STATE_DIR"

usage() {
  cat <<'TXT'
Usage: ./scripts/opencode_web.sh {start|ensure|status|stop|url}

Environment overrides:
  DRIFTGUARD_OPENCODE_WEB_URL   Reuse an already-running OpenCode web server.
  DRIFTGUARD_OPENCODE_WEB_HOST  Host for a locally-started server (default 127.0.0.1).
  DRIFTGUARD_OPENCODE_WEB_PORT  Port for a locally-started server (default 4096).
  DRIFTGUARD_OPENCODE_WEB_CWD   Working directory for a locally-started server.
                                Defaults to the DriftGuard project root.
  DRIFTGUARD_OPENCODE_BIN       OpenCode executable (default opencode).
  DRIFTGUARD_OPENCODE_WEB_OPEN  Set to 1 to auto-open the server home page
                                on first start (default 0). The flow runner opens
                                the stable project view instead. Never re-opens
                                a tab when reusing an already-running server.

If OPENCODE_SERVER_PASSWORD is set, health checks use HTTP basic auth with
OPENCODE_SERVER_USERNAME (default: opencode). The password is never written to
the DriftGuard evidence bundle.
TXT
}

server_url() {
  if [[ -n "$EXPLICIT_URL" ]]; then
    printf '%s\n' "${EXPLICIT_URL%/}"
    return 0
  fi
  printf 'http://%s:%s\n' "$HOST" "$PORT"
}

curl_health() {
  local url="$1"
  local args=(-fsS --max-time 2)
  if [[ -n "${OPENCODE_SERVER_PASSWORD:-}" ]]; then
    args+=(-u "${OPENCODE_SERVER_USERNAME:-opencode}:${OPENCODE_SERVER_PASSWORD}")
  fi
  curl "${args[@]}" "$url/global/health" 2>/dev/null
}

healthy() {
  local url="$1"
  local body
  body="$(curl_health "$url" || true)"
  [[ "$body" == *'"healthy":true'* || "$body" == *'"healthy": true'* ]]
}

wait_healthy() {
  local url="$1"
  local attempts="${2:-80}"
  local i
  for ((i=1; i<=attempts; i++)); do
    if healthy "$url"; then
      return 0
    fi
    sleep 0.25
  done
  return 1
}

start_server() {
  command -v "$OPENCODE_BIN" >/dev/null 2>&1 || {
    echo "OpenCode CLI not found: $OPENCODE_BIN" >&2
    exit 2
  }

  local url
  url="$(server_url)"

  # An explicit URL always means "reuse this server"; never try to own/kill it.
  if [[ -n "$EXPLICIT_URL" ]]; then
    if ! healthy "$url"; then
      echo "OpenCode web server is not healthy at: $url" >&2
      echo "Start it with 'opencode web' or unset DRIFTGUARD_OPENCODE_WEB_URL." >&2
      exit 2
    fi
    printf '%s\n' "$url"
    return 0
  fi

  [[ -d "$SERVER_CWD" ]] || {
    echo "OpenCode web working directory does not exist: $SERVER_CWD" >&2
    exit 2
  }
  SERVER_CWD="$(cd "$SERVER_CWD" && pwd -P)"

  if healthy "$url"; then
    # Reuse only a server DriftGuard previously started. An unrelated server
    # may not have inherited the pinned benchmark PATH. Attached agent stages
    # still use --dir for their exact workspace; direct web links are generated
    # per session to avoid relying on the Web Home project's client-side state.
    if [[ -f "$PID_FILE" ]]; then
      local pid
      pid="$(cat "$PID_FILE")"
      if kill -0 "$pid" 2>/dev/null; then
        printf '%s\n' "$url" > "$URL_FILE"
        if [[ -f "$CWD_FILE" && "$(cat "$CWD_FILE")" != "$SERVER_CWD" ]]; then
          echo "Note: reusing OpenCode web server started in $(cat "$CWD_FILE"); requested cwd is $SERVER_CWD." >&2
          echo "Attached runs still use --dir; use the printed direct session URL to view them." >&2
        fi
        printf '%s\n' "$url"
        return 0
      fi
    fi
    echo "A healthy OpenCode server already exists at $url, but DriftGuard does not own it." >&2
    echo "For reproducibility, either stop it or explicitly opt in with:" >&2
    echo "  export DRIFTGUARD_OPENCODE_WEB_URL='$url'" >&2
    exit 2
  fi

  [[ -x "$VENV/bin/python" ]] || {
    echo "Run ./scripts/bootstrap.sh first so the OpenCode server inherits the pinned dbt/Python PATH." >&2
    exit 2
  }

  rm -f "$PID_FILE" "$URL_FILE" "$CWD_FILE" "$PROJECT_TAB_FILE"
  : > "$LOG_FILE"

  # Tool execution happens in the server process when `opencode run --attach`
  # is used. Start from a deterministic project directory and inherit the
  # benchmark's pinned environment.
  (
    cd "$SERVER_CWD"
    # BROWSER=none suppresses OpenCode's own auto-open (the `open` package's
    # standard opt-out convention). We open exactly one tab ourselves below,
    # only on a genuinely fresh start, so repeated `ensure` calls across many
    # sessions/cases never spawn additional tabs.
    nohup env \
      PATH="$VENV/bin:$PATH" \
      VIRTUAL_ENV="$VENV" \
      NO_COLOR=1 \
      BROWSER=none \
      "$OPENCODE_BIN" web --hostname "$HOST" --port "$PORT" \
      >>"$LOG_FILE" 2>&1 &
    printf '%s\n' "$!" > "$PID_FILE"
  )

  local pid
  pid="$(cat "$PID_FILE")"
  printf '%s\n' "$url" > "$URL_FILE"
  printf '%s\n' "$SERVER_CWD" > "$CWD_FILE"

  if ! wait_healthy "$url"; then
    echo "OpenCode web server failed to become healthy at $url" >&2
    echo "Server log: $LOG_FILE" >&2
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
    fi
    rm -f "$PID_FILE" "$URL_FILE" "$CWD_FILE"
    exit 2
  fi

  # Open exactly one tab for the life of this server. Every subsequent
  # session (baseline/verifier/retry, across every case) shares this same
  # server and should appear/update in this tab live rather than opening more.
  if [[ "${DRIFTGUARD_OPENCODE_WEB_OPEN:-0}" == "1" ]]; then
    local opener=""
    if command -v xdg-open >/dev/null 2>&1; then
      opener="xdg-open"
    elif command -v open >/dev/null 2>&1; then
      opener="open"
    fi
    if [[ -n "$opener" ]]; then
      "$opener" "$url" >/dev/null 2>&1 &
      disown 2>/dev/null || true
    fi
  fi

  printf '%s\n' "$url"
}

case "${1:-}" in
  start|ensure)
    start_server
    ;;
  status)
    url="$(server_url)"
    if healthy "$url"; then
      echo "OpenCode web is healthy: $url"
      if [[ -f "$PID_FILE" ]]; then
        echo "Managed PID: $(cat "$PID_FILE")"
        [[ -f "$CWD_FILE" ]] && echo "Server cwd: $(cat "$CWD_FILE")"
      else
        echo "Managed PID: none (reusing an external/already-running server)"
      fi
      exit 0
    fi
    echo "OpenCode web is not reachable: $url"
    exit 1
    ;;
  url)
    server_url
    ;;
  stop)
    if [[ -n "$EXPLICIT_URL" ]]; then
      echo "DRIFTGUARD_OPENCODE_WEB_URL points to an external server; DriftGuard will not stop it." >&2
      exit 0
    fi
    if [[ -f "$PID_FILE" ]]; then
      pid="$(cat "$PID_FILE")"
      if kill -0 "$pid" 2>/dev/null; then
        kill "$pid"
        for _ in {1..40}; do
          if ! kill -0 "$pid" 2>/dev/null; then break; fi
          sleep 0.1
        done
        if kill -0 "$pid" 2>/dev/null; then
          kill -9 "$pid" 2>/dev/null || true
        fi
        echo "Stopped DriftGuard-managed OpenCode web server (PID $pid)."
      else
        echo "Managed OpenCode web PID $pid is not running."
      fi
      rm -f "$PID_FILE" "$URL_FILE" "$CWD_FILE" "$PROJECT_TAB_FILE"
    else
      echo "No DriftGuard-managed OpenCode web server is recorded."
    fi
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac
