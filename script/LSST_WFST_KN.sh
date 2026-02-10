#!/bin/bash
# Run WFST and LSST KN simulations with parameters from a JSON config file.
# Usage: bash LSST_WFST_KN.sh [config.json]
#
# The JSON config overrides parameters in the INPUT files via snlc_sim.exe
# command-line arguments. Parameters not in the JSON use INPUT file defaults.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(dirname "$SCRIPT_DIR")"
CONFIG="${1:-${SCRIPT_DIR}/sim_config.json}"

if [ ! -f "$CONFIG" ]; then
    echo "ERROR: config file not found: $CONFIG"
    exit 1
fi

echo "Using config: $CONFIG"

# Parse JSON values using python (available on all systems with SNANA)
read_json() {
    python3 -c "import json,sys; d=json.load(open('$CONFIG')); print(d.get('$1',''))"
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

WFST_INPUT="${BASE_DIR}/INPUT/SIMGEN_KN_WFST_TEMPLATE.INPUT"
LSST_INPUT="${BASE_DIR}/INPUT/SIMGEN_KN_LSST_TEMPLATE.INPUT"

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
