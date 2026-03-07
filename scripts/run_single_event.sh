#!/bin/bash
# Run the 170817A-style WFST and LSST KN simulations from a JSON config file.
# Usage: bash scripts/run_single_event.sh [config.json]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
CONFIG="${1:-${REPO_ROOT}/configs/single_event/kn_170817A.json}"

if [ ! -f "$CONFIG" ]; then
    echo "ERROR: config file not found: $CONFIG"
    exit 1
fi

if [ -z "${KN_SIMLIB_DIR:-}" ]; then
    KN_SIMLIB_DIR="${REPO_ROOT}/outputs/simlib"
fi
export KN_SIMLIB_DIR

if [ -z "${KN_SIM_ROOT:-}" ] && [ -n "${SNDATA_ROOT:-}" ]; then
    KN_SIM_ROOT="${SNDATA_ROOT}/SIM"
fi
if [ -n "${KN_SIM_ROOT:-}" ]; then
    export KN_SIM_ROOT
fi

echo "Using config: $CONFIG"

# Parse JSON values using python (available on all systems with SNANA)
read_json() {
    python3 - "$CONFIG" "$1" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    config = json.load(handle)

print(config.get(sys.argv[2], ""))
PY
}

GENVERSION_WFST=$(read_json GENVERSION_WFST)
GENVERSION_LSST=$(read_json GENVERSION_LSST)
DNDZ=$(read_json DNDZ)
NGEN_SEASON=$(read_json NGEN_SEASON)
RANSEED=$(read_json RANSEED)
GENRANGE_REDSHIFT=$(read_json GENRANGE_REDSHIFT)
GENRANGE_PEAKMJD=$(read_json GENRANGE_PEAKMJD)
SOLID_ANGLE=$(read_json SOLID_ANGLE)
GENRANGE_TREST=$(read_json GENRANGE_TREST)

# Build override string (only include non-empty values)
build_overrides() {
    local genversion="$1"
    local overrides=""
    [ -n "$genversion" ]         && overrides+=" GENVERSION ${genversion}"
    [ -n "$DNDZ" ]               && overrides+=" DNDZ: ${DNDZ}"
    [ -n "$NGEN_SEASON" ]        && overrides+=" NGEN_SEASON: ${NGEN_SEASON}"
    [ -n "$RANSEED" ]            && overrides+=" RANSEED: ${RANSEED}"
    [ -n "$GENRANGE_REDSHIFT" ]  && overrides+=" GENRANGE_REDSHIFT: ${GENRANGE_REDSHIFT}"
    [ -n "$GENRANGE_PEAKMJD" ]   && overrides+=" GENRANGE_PEAKMJD: ${GENRANGE_PEAKMJD}"
    [ -n "$SOLID_ANGLE" ]        && overrides+=" SOLID_ANGLE: ${SOLID_ANGLE}"
    [ -n "$GENRANGE_TREST" ]     && overrides+=" GENRANGE_TREST: ${GENRANGE_TREST}"
    echo "$overrides"
}

WFST_INPUT="${REPO_ROOT}/templates/snana/SIMGEN_KN_WFST_TEMPLATE.INPUT"
LSST_INPUT="${REPO_ROOT}/templates/snana/SIMGEN_KN_LSST_TEMPLATE.INPUT"

echo "============================================"
echo "  Running WFST KN simulation"
echo "  GENVERSION: ${GENVERSION_WFST}"
echo "============================================"
snlc_sim.exe "${WFST_INPUT}" $(build_overrides "$GENVERSION_WFST")

echo ""
echo "============================================"
echo "  Running LSST KN simulation"
echo "  GENVERSION: ${GENVERSION_LSST}"
echo "============================================"
snlc_sim.exe "${LSST_INPUT}" $(build_overrides "$GENVERSION_LSST")

echo ""
echo "Done. Simulations complete."
