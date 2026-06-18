#!/usr/bin/env bash
#
# run_all.sh — profile app-1/2/3 in parallel and aggregate the results.
#
# No venv activation needed: each app is profiled with its OWN venv python,
# so the aws_cdk/jsii build installed in that app is the one measured.
#
# By default each app runs at its REAL workload size, matching the benchmark
# README (so profiler output lines up with observed cdk-synth numbers):
#     app-1 -> 20 stacks    (8,000 resources)
#     app-2 -> 100 stacks   (40,000 resources)
#     app-3 -> 400 stacks   (160,000 resources)
#
# Usage:
#   ./run_all.sh                      # real per-app sizes (20 / 100 / 400 stacks)
#   ./run_all.sh --stacks 5           # override: SAME stack count for all apps
#   ./run_all.sh --resources 200      # override resources/stack for all apps
#   ./run_all.sh --label lazy         # tag output files (e.g. lazy vs eager)
#   LABEL=eager ./run_all.sh          # same, via env
#
# NOTE: the real sizes are heavy (app-3 = 160k resources, and cProfile adds
# overhead). Use --stacks 5 for a fast attribution run; use the real sizes only
# when you specifically want to reproduce the observed per-app numbers.
#
# Results are written to profiling/results/<app>[-<LABEL>].json and then
# aggregated into a table + profiling/summary.csv.

set -euo pipefail

# --- locate ourselves so the script works from any cwd ---------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BENCH="$(cd "$SCRIPT_DIR/.." && pwd)"
RESULTS="$SCRIPT_DIR/results"
mkdir -p "$RESULTS"

# --- per-app real stack counts (matches benchmark README) ------------------
# Portable lookup (no associative arrays; macOS ships bash 3.2).
APPS=(app-1 app-2 app-3)
default_stacks_for() {
  case "$1" in
    app-1) echo 20 ;;
    app-2) echo 100 ;;
    app-3) echo 400 ;;
    *)     echo 20 ;;
  esac
}

# --- defaults / arg parsing ------------------------------------------------
RESOURCES=400
STACKS_OVERRIDE=""        # if set, applies to ALL apps
LABEL="${LABEL:-}"        # optional tag, also settable via env

while [[ $# -gt 0 ]]; do
  case "$1" in
    --stacks)    STACKS_OVERRIDE="$2"; shift 2 ;;
    --resources) RESOURCES="$2"; shift 2 ;;
    --label)     LABEL="$2"; shift 2 ;;
    -h|--help)
      grep '^#' "$0" | sed 's/^# \{0,1\}//'
      exit 0 ;;
    *) echo "Unknown arg: $1" >&2; exit 2 ;;
  esac
done

suffix=""
[[ -n "$LABEL" ]] && suffix="-$LABEL"

echo "Benchmark root : $BENCH"
if [[ -n "$STACKS_OVERRIDE" ]]; then
  echo "Workload       : $STACKS_OVERRIDE stacks x $RESOURCES resources (override, all apps)"
else
  echo "Workload       : per-app real sizes (app-1=20, app-2=100, app-3=400) x $RESOURCES resources"
fi
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

  if [[ -n "$STACKS_OVERRIDE" ]]; then
    stacks="$STACKS_OVERRIDE"
  else
    stacks="$(default_stacks_for "$app")"
  fi

  "$py" "$SCRIPT_DIR/profile_app.py" \
      "$BENCH/$app" \
      --stacks "$stacks" --resources "$RESOURCES" \
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
