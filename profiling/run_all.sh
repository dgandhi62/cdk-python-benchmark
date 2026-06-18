#!/usr/bin/env bash
#
# run_all.sh — profile app-1/2/3 in parallel and aggregate the results.
#
# No venv activation needed: each app is profiled with its OWN venv python,
# so the aws_cdk/jsii build installed in that app is the one measured.
#
# Usage:
#   ./run_all.sh                      # default: 5 stacks x 400 resources
#   ./run_all.sh --stacks 20          # override workload size
#   ./run_all.sh --stacks 100 --resources 400
#   LABEL=eager ./run_all.sh          # tag output files (e.g. lazy vs eager)
#
# Results are written to profiling/results/<app>[-<LABEL>].json and then
# aggregated into a table + profiling/summary.csv.

set -euo pipefail

# --- locate ourselves so the script works from any cwd ---------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BENCH="$(cd "$SCRIPT_DIR/.." && pwd)"
RESULTS="$SCRIPT_DIR/results"
mkdir -p "$RESULTS"

# --- defaults / arg parsing ------------------------------------------------
STACKS=5
RESOURCES=400
LABEL="${LABEL:-}"   # optional tag, also settable via env

while [[ $# -gt 0 ]]; do
  case "$1" in
    --stacks)    STACKS="$2"; shift 2 ;;
    --resources) RESOURCES="$2"; shift 2 ;;
    --label)     LABEL="$2"; shift 2 ;;
    -h|--help)
      grep '^#' "$0" | sed 's/^# \{0,1\}//'
      exit 0 ;;
    *) echo "Unknown arg: $1" >&2; exit 2 ;;
  esac
done

APPS=(app-1 app-2 app-3)
suffix=""
[[ -n "$LABEL" ]] && suffix="-$LABEL"

echo "Benchmark root : $BENCH"
echo "Workload       : $STACKS stacks x $RESOURCES resources = $((STACKS*RESOURCES)) resources/app"
[[ -n "$LABEL" ]] && echo "Label          : $LABEL"
echo "Launching ${#APPS[@]} apps in parallel..."
echo

# --- launch all apps in parallel -------------------------------------------
pids=()
for app in "${APPS[@]}"; do
  py="$BENCH/$app/.venv/bin/python"
  if [[ ! -x "$py" ]]; then
    echo "SKIP $app: no venv python at $py" >&2
    continue
  fi
  "$py" "$SCRIPT_DIR/profile_app.py" \
      "$BENCH/$app" \
      --stacks "$STACKS" --resources "$RESOURCES" \
      --out "$RESULTS/${app}${suffix}.json" &
  pids+=("$!")
done

# --- wait for all, capture any failure -------------------------------------
fail=0
for pid in "${pids[@]}"; do
  wait "$pid" || fail=1
done

if [[ "$fail" -ne 0 ]]; then
  echo >&2
  echo "One or more profiling runs failed. See output above." >&2
  exit 1
fi

echo
echo "All runs complete. Aggregating..."
echo

# --- aggregate (any venv python works; aggregate.py is pure stdlib) --------
AGG_PY="$BENCH/${APPS[0]}/.venv/bin/python"
"$AGG_PY" "$SCRIPT_DIR/aggregate.py" \
    "$RESULTS"/*.json \
    --csv "$SCRIPT_DIR/summary.csv"
