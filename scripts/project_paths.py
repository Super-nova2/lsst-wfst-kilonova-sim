#!/usr/bin/env python3
"""Helpers for portable path resolution inside the LSST+WFST repository."""

from __future__ import annotations

import os
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def repo_path(*parts: str) -> Path:
    return REPO_ROOT.joinpath(*parts)


def resolve_path(value: str | Path, base: Path = REPO_ROOT) -> Path:
    path = Path(os.path.expandvars(os.path.expanduser(str(value))))
    if path.is_absolute():
        return path
    return base / path


def default_sim_root() -> Path:
    if "KN_SIM_ROOT" in os.environ:
        return resolve_path(os.environ["KN_SIM_ROOT"])
    if "SNDATA_ROOT" in os.environ:
        sndata_root = Path(os.path.expandvars(os.path.expanduser(os.environ["SNDATA_ROOT"])))
        return sndata_root / "SIM"
    return repo_path("outputs", "sim")


def default_simlib_dir() -> Path:
    if "KN_SIMLIB_DIR" in os.environ:
        return resolve_path(os.environ["KN_SIMLIB_DIR"])
    return repo_path("outputs", "simlib")


def ensure_runtime_env() -> None:
    os.environ.setdefault("KN_SIMLIB_DIR", str(default_simlib_dir()))
    if "KN_SIM_ROOT" not in os.environ and "SNDATA_ROOT" in os.environ:
        os.environ["KN_SIM_ROOT"] = str(default_sim_root())
