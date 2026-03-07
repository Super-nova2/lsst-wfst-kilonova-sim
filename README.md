# LSST+WFST

Portable workflows for comparing kilonova detectability in LSST and WFST with SNANA.

This repository contains:

- SNANA input templates for matched LSST/WFST simulations
- shell and Python entrypoints for a single-event example and an astrophysical population run
- small tracked reference data and example figures
- notebooks for population generation, SIMLIB construction, and result inspection

Large runtime artifacts such as `SIMLIB` files, generated SNANA inputs, and logs are intentionally kept under `outputs/` and ignored by Git so the repository stays lightweight for GitHub.

## Repository Layout

```text
configs/          Workflow configuration files
data/             Tracked small inputs (sample population, SIMOBS CSVs, filters)
examples/         Example figures kept in version control
notebooks/        Analysis and preparation notebooks
outputs/          Local runtime artifacts, ignored by Git
scripts/          Canonical command-line entrypoints
templates/snana/  SNANA template inputs and reference config files
```

## Prerequisites

- SNANA with `snlc_sim.exe`
- `SNDATA_ROOT` pointing to your SNANA data tree
- Python 3 with:
  - runtime: `pandas`, `astropy`, `numpy`, `scipy`
  - notebooks: `matplotlib`, `healpy`, `opsimsummaryv2`

## Environment Setup

```bash
export SNDATA_ROOT=/path/to/SNANA/SNDATA_ROOT
export KN_SIM_ROOT="${KN_SIM_ROOT:-$SNDATA_ROOT/SIM}"
export KN_SIMLIB_DIR="${KN_SIMLIB_DIR:-$PWD/outputs/simlib}"
```

`KN_SIM_ROOT` is where SNANA simulation products are read/written. `KN_SIMLIB_DIR` must contain the SIMLIB files referenced by the templates.

Expected SIMLIB filenames:

- `WFST_simobs_2.SIMLIB`
- `baseline_v5.0.1_10yrs_WFSTfootprint.SIMLIB`

## Quickstart

Single-event 170817A-style example:

```bash
bash scripts/run_single_event.sh
```

Population workflow using the tracked sample catalog:

```bash
bash scripts/run_population_pipeline.sh
```

Useful config files:

- `configs/single_event/kn_170817A.json`
- `configs/population/kn_astro.json`

The population pipeline writes generated `.INPUT` files and logs to `outputs/`, then moves SNANA event directories into `${KN_SIM_ROOT}/LSST_KN_ASTRO` and `${KN_SIM_ROOT}/WFST_KN_ASTRO`. Combined survey products are written under `${KN_SIM_ROOT}/LSST_KN_ASTRO_COMBINED` and `${KN_SIM_ROOT}/WFST_KN_ASTRO_COMBINED`.

## SIMLIB Preparation

This repository does not track the large SIMLIB products needed for simulation runs on GitHub. Place or generate them locally in `outputs/simlib/` or point `KN_SIMLIB_DIR` to another directory containing the required files.

`notebooks/gen_SIMLIB.ipynb` documents how the matched WFST and LSST SIMLIBs were built from:

- `data/simobs/WFST_simobs_2.csv`
- a local Rubin OpSim SQLite database, optionally provided via `LSST_OPSIM_DB`

## Notebooks

- `notebooks/astro_pop.ipynb` generates the tracked sample catalog in `data/samples/`
- `notebooks/gen_SIMLIB.ipynb` builds matched SIMLIB files
- `notebooks/analyse.ipynb` and `notebooks/plot_lc.ipynb` inspect SNANA outputs from `KN_SIM_ROOT`

The notebooks are kept as working research notebooks, not polished tutorials. Some cells assume optional local data outside this repository.

## Output Policy

- Track: configs, templates, small CSV inputs, filters, notebooks, example figures
- Do not track: `outputs/`, SNANA run directories, generated FITS products, local logs, cache files

This split is intentional so the repository can be pushed to GitHub without carrying machine-specific runtime artifacts.
