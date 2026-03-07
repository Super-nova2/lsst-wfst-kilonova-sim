#!/bin/bash
# Run the astrophysical population KN workflow from a JSON config file.
# Usage: bash scripts/run_population_pipeline.sh [config.json]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
CONFIG="${1:-${REPO_ROOT}/configs/population/kn_astro.json}"

if [ ! -f "$CONFIG" ]; then
    echo "ERROR: config file not found: $CONFIG"
    exit 1
fi

if [ -z "${KN_SIMLIB_DIR:-}" ]; then
    KN_SIMLIB_DIR="${REPO_ROOT}/outputs/simlib"
fi
export KN_SIMLIB_DIR

echo "Using config: $CONFIG"

# Parse JSON values using python3
read_json() {
    python3 - "$CONFIG" "$1" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    config = json.load(handle)

print(config.get(sys.argv[2], ""))
PY
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

if [[ -n "$SIM_ROOT" ]]; then
    KN_SIM_ROOT="$SIM_ROOT"
elif [[ -z "${KN_SIM_ROOT:-}" && -n "${SNDATA_ROOT:-}" ]]; then
    KN_SIM_ROOT="${SNDATA_ROOT}/SIM"
fi
if [[ -n "${KN_SIM_ROOT:-}" ]]; then
    export KN_SIM_ROOT
fi

RUN_SCRIPT="${SCRIPT_DIR}/run_population_from_csv.py"
COMBINE_SCRIPT="${SCRIPT_DIR}/combine_population_results.py"

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
    echo "RUN_SIM=false, skip run_population_from_csv.py"
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
    echo "COMBINE=false, skip combine_population_results.py"
fi

echo "Done."
