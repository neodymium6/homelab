#!/usr/bin/env bash

set -Eeuo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd -- "${script_dir}/../.." && pwd)"
cluster_file="${CLUSTER_YAML:-${repo_root}/cluster.yaml}"
poll_interval="${AUDIOMUSE_POLL_INTERVAL:-10}"
worker_ready_timeout="${AUDIOMUSE_WORKER_READY_TIMEOUT:-180}"

task_id=""
worker_owned=false
sudo_keepalive_pid=""

log() {
  printf '==> %s\n' "$*"
}

fail() {
  printf 'Error: %s\n' "$*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "$1 is required but was not found in PATH."
}

require_positive_integer() {
  local name="$1"
  local value="$2"
  [[ "$value" =~ ^[1-9][0-9]*$ ]] || fail "${name} must be a positive integer."
}

api_request() {
  local method="$1"
  local path="$2"
  local payload="${3:-}"
  local -a args=(
    --silent
    --show-error
    --fail-with-body
    --max-time 30
    --request "$method"
  )

  if [[ -n "$payload" ]]; then
    args+=(--header 'Content-Type: application/json' --data "$payload")
  fi

  # Pass the bearer token through curl's stdin config so it does not appear in
  # the process command line or normal command output.
  printf 'header = "Authorization: Bearer %s"\n' "$api_token" \
    | curl --config - "${args[@]}" "${api_url}${path}"
}

stop_sudo_keepalive() {
  if [[ -n "$sudo_keepalive_pid" ]]; then
    kill "$sudo_keepalive_pid" >/dev/null 2>&1 || true
    wait "$sudo_keepalive_pid" 2>/dev/null || true
    sudo_keepalive_pid=""
  fi
}

cleanup() {
  local exit_code=$?
  local down_code=0

  trap - EXIT INT TERM
  if [[ "$worker_owned" == true ]]; then
    log "Stopping the local AudioMuse GPU worker..."
    sudo -n -v >/dev/null 2>&1 || true
    make -C "${repo_root}/local" audiomuse-worker-down || down_code=$?
  fi
  stop_sudo_keepalive

  if (( exit_code == 0 && down_code != 0 )); then
    exit_code=$down_code
  fi
  exit "$exit_code"
}

interrupt() {
  printf '\n' >&2
  if [[ -n "$task_id" ]]; then
    log "Cancelling AudioMuse task ${task_id}..."
    api_request POST "/api/cancel/${task_id}" >/dev/null || \
      printf 'Warning: could not cancel task %s; it can be resumed by running this command again.\n' "$task_id" >&2
  fi
  exit 130
}

wait_for_workers() {
  local deadline=$((SECONDS + worker_ready_timeout))
  local summary
  local queues

  log "Waiting for the high and default queue workers..."
  while (( SECONDS < deadline )); do
    if summary="$(api_request GET /api/dashboard/summary 2>/dev/null)"; then
      queues="$(jq -r '.workers[]?.queues[]?' <<<"$summary" | sort -u | tr '\n' ' ')"
      if [[ " $queues " == *" high "* && " $queues " == *" default "* ]]; then
        log "Both AudioMuse queue workers are ready."
        return 0
      fi
    fi
    sleep 3
  done

  fail "AudioMuse workers did not become ready within ${worker_ready_timeout} seconds."
}

find_active_analysis() {
  local active
  local active_type

  active="$(api_request GET /api/active_tasks)" || fail "Could not query active AudioMuse tasks."
  task_id="$(jq -r '.task_id // empty' <<<"$active")"
  [[ -n "$task_id" ]] || return 0

  active_type="$(jq -r '.task_type // empty' <<<"$active")"
  if [[ "$active_type" != main_analysis ]]; then
    fail "AudioMuse task ${task_id} (${active_type:-unknown}) is already active."
  fi

  log "Resuming existing AudioMuse analysis task ${task_id}."
}

start_analysis() {
  local response

  [[ -z "$task_id" ]] || return 0
  log "Starting incremental AudioMuse analysis (num_recent_albums=0)..."
  if ! response="$(api_request POST /api/analysis/start '{"num_recent_albums":0}')"; then
    fail "AudioMuse rejected the analysis request. Check the AudioMuse logs."
  fi

  task_id="$(jq -er '.task_id' <<<"$response")" || fail "AudioMuse returned no task ID."
  log "AudioMuse analysis task: ${task_id}"
}

monitor_analysis() {
  local response
  local state
  local progress
  local message
  local display
  local last_display=""
  local request_failures=0

  while true; do
    if ! response="$(api_request GET "/api/status/${task_id}")"; then
      request_failures=$((request_failures + 1))
      if (( request_failures >= 6 )); then
        fail "Could not read AudioMuse task status after ${request_failures} attempts."
      fi
      printf 'Warning: status request failed (%d/6); retrying.\n' "$request_failures" >&2
      sleep "$poll_interval"
      continue
    fi
    request_failures=0

    state="$(jq -r '.state // "UNKNOWN"' <<<"$response")"
    progress="$(jq -r '.progress // 0' <<<"$response")"
    message="$(jq -r '(.status_message // .state // "") | gsub("[\\r\\n]+"; " ")' <<<"$response")"
    display="${state} ${progress}% ${message}"
    if [[ "$display" != "$last_display" ]]; then
      printf '    %s\n' "$display"
      last_display="$display"
    fi

    case "$state" in
      SUCCESS)
        log "AudioMuse incremental analysis completed successfully."
        return 0
        ;;
      FAIL | REVOKED | UNKNOWN)
        fail "AudioMuse analysis ended with state ${state}: ${message}"
        ;;
      NEW | RUNNING)
        sleep "$poll_interval"
        ;;
      *)
        fail "AudioMuse returned an unexpected task state: ${state}"
        ;;
    esac
  done
}

require_command curl
require_command jq
require_command make
require_command sudo
require_command yq
require_positive_integer AUDIOMUSE_POLL_INTERVAL "$poll_interval"
require_positive_integer AUDIOMUSE_WORKER_READY_TIMEOUT "$worker_ready_timeout"
[[ -f "$cluster_file" ]] || fail "Cluster configuration not found: ${cluster_file}"

domain="$(yq -r '.network.domain // empty' "$cluster_file")"
api_token="$(yq -r '.secrets.audiomuse.api_token // empty' "$cluster_file")"
[[ -n "$domain" ]] || fail "network.domain is missing from ${cluster_file}."
[[ ${#api_token} -ge 24 ]] || fail "secrets.audiomuse.api_token is missing or too short."
api_url="${AUDIOMUSE_API_URL:-https://audiomuse-proxy.${domain}}"
api_url="${api_url%/}"

trap cleanup EXIT
trap interrupt INT TERM

# Validate the API and adopt an interrupted analysis before starting the worker.
find_active_analysis

# Keep the sudo timestamp valid during a long analysis so shutdown does not
# require another password prompt hours later.
sudo -v
(
  while true; do
    sleep 45
    sudo -n -v >/dev/null 2>&1 || exit 0
  done
) &
sudo_keepalive_pid=$!

worker_owned=true
log "Starting the local AudioMuse GPU worker..."
make -C "${repo_root}/local" audiomuse-worker-up
wait_for_workers
start_analysis
monitor_analysis
