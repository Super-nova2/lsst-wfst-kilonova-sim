#!/bin/bash
# Run per-event KN simulations from population CSV and combine outputs.
# Usage: bash LSST_WFST_KN_ASTRO.sh [config.json]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(dirname "$SCRIPT_DIR")"
CONFIG="${1:-${SCRIPT_DIR}/kn_astro_config.json}"

if [ ! -f "$CONFIG" ]; then
    echo "ERROR: config file not found: $CONFIG"
    exit 1
fi

echo "Using config: $CONFIG"

# Parse JSON values using python3
read_json() {
    python3 -c "import json,sys; d=json.load(open('$CONFIG')); print(d.get('$1',''))"
}

# Config values
SAMPLES=$(read_json SAMPLES)
SURVEYS=$(read_json SURVEYS)
START=$(read_json START)
COUNT=$(read_json COUNT)
DRY_RUN=$(read_json DRY_RUN)
BASE_SEED=$(read_json BASE_SEED)
SIMLIB_MAXRANSTART=$(read_json SIMLIB_MAXRANSTART)
SNID_PREFIX=$(read_json SNID_PREFIX)
SIM_ROOT=$(read_json SIM_ROOT)
POPULATION_CSV=$(read_json POPULATION_CSV)
RUN_SIM=$(read_json RUN_SIM)
COMBINE=$(read_json COMBINE)

RUN_SIM=${RUN_SIM,,}
COMBINE=${COMBINE,,}
DRY_RUN=${DRY_RUN,,}

RUN_SCRIPT="${SCRIPT_DIR}/run_kn_from_population.py"
COMBINE_SCRIPT="${SCRIPT_DIR}/combine_kn_results.py"

if [[ "$RUN_SIM" != "false" ]]; then
    cmd=("python3" "$RUN_SCRIPT")
    [ -n "$SAMPLES" ] && cmd+=(--samples "$SAMPLES")
    [ -n "$SURVEYS" ] && cmd+=(--surveys "$SURVEYS")
    [ -n "$START" ] && cmd+=(--start "$START")
    [ -n "$COUNT" ] && cmd+=(--count "$COUNT")
    [ -n "$BASE_SEED" ] && cmd+=(--base-seed "$BASE_SEED")
    [ -n "$SIMLIB_MAXRANSTART" ] && cmd+=(--simlib-maxranstart "$SIMLIB_MAXRANSTART")
    if [[ "$DRY_RUN" == "true" ]]; then
        cmd+=(--dry-run)
    fi
    echo "Running: ${cmd[*]}"
    "${cmd[@]}"
else
    echo "RUN_SIM=false, skip run_kn_from_population.py"
fi

if [[ "$COMBINE" != "false" ]]; then
    cmd=("python3" "$COMBINE_SCRIPT")
    [ -n "$SURVEYS" ] && cmd+=(--survey "$SURVEYS")
    [ -n "$SIM_ROOT" ] && cmd+=(--sim-root "$SIM_ROOT")
    [ -n "$SNID_PREFIX" ] && cmd+=(--snid-prefix "$SNID_PREFIX")
    [ -n "$POPULATION_CSV" ] && cmd+=(--population-csv "$POPULATION_CSV")
    echo "Running: ${cmd[*]}"
    "${cmd[@]}"
else
    echo "COMBINE=false, skip combine_kn_results.py"
fi

echo "Done."
