#!/usr/bin/env python3
"""
Generate per-event SNANA INPUT files (LSST/WFST) from an astrophysical
BNS population CSV and optionally run snlc_sim.exe.
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import shutil
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd

from project_paths import default_sim_root, ensure_runtime_env, repo_path, resolve_path


def find_column(df: pd.DataFrame, candidates: List[str]) -> str:
    cols = {c.lower(): c for c in df.columns}
    for cand in candidates:
        if cand.lower() in cols:
            return cols[cand.lower()]
    raise KeyError(f"Required column not found. Tried: {candidates}")


def fmt_val(val: float) -> str:
    return f"{val:.6g}"


def clip_param(name: str, val: float, vmin: float, vmax: float) -> Tuple[float, bool]:
    clipped = False
    if val < vmin:
        val = vmin
        clipped = True
    elif val > vmax:
        val = vmax
        clipped = True
    return val, clipped


def replace_key(text: str, key: str, value: str) -> str:
    pattern = rf"^({re.escape(key)}\s*:)\s*.*$"
    repl = rf"\1 {value}"
    if re.search(pattern, text, flags=re.MULTILINE):
        return re.sub(pattern, repl, text, flags=re.MULTILINE)
    return text


def ensure_key_after(text: str, insert_after_key: str, key: str, value: str) -> str:
    """Ensure a KEY: value line exists; insert after insert_after_key if missing."""
    pattern = rf"^({re.escape(key)}\s*:)\s*.*$"
    if re.search(pattern, text, flags=re.MULTILINE):
        return re.sub(pattern, rf"\1 {value}", text, flags=re.MULTILINE)

    lines = text.splitlines()
    insert_idx = None
    for i, line in enumerate(lines):
        if line.strip().startswith(insert_after_key):
            insert_idx = i + 1
            break
    new_line = f"{key}:  {value}"
    if insert_idx is None:
        lines.insert(0, new_line)
    else:
        lines.insert(insert_idx, new_line)
    return "\n".join(lines) + ("\n" if text.endswith("\n") else "")


def build_input_text(template_text: str, params: Dict[str, str]) -> str:
    text = template_text

    # set NGEN_SEASON=0 for single-event simulations
    text = replace_key(text, "NGEN_SEASON", "0")

    # Required replacements
    text = replace_key(text, "GENVERSION", params["GENVERSION"])
    text = replace_key(text, "GENPEAK_COSTHETA", params["COSTHETA"])
    text = replace_key(text, "GENRANGE_COSTHETA", f"{params['COSTHETA']} {params['COSTHETA']}")

    text = replace_key(text, "GENPEAK_MEJDYN", params["MEJDYN"])
    text = replace_key(text, "GENRANGE_MEJDYN", f"{params['MEJDYN']} {params['MEJDYN']}")

    text = replace_key(text, "GENPEAK_MEJWIND", params["MEJWIND"])
    text = replace_key(text, "GENRANGE_MEJWIND", f"{params['MEJWIND']} {params['MEJWIND']}")

    text = replace_key(text, "GENPEAK_PHI", params["PHI"])
    text = replace_key(text, "GENRANGE_PHI", f"{params['PHI']} {params['PHI']}")

    text = replace_key(text, "GENRANGE_REDSHIFT", f"{params['REDSHIFT']} {params['REDSHIFT']}")
    text = replace_key(text, "RANSEED", params["RANSEED"])
    # Randomize SIMLIB start position so per-event runs do not always use LIBID=0.
    text = ensure_key_after(text, "SIMLIB_FILE:", "SIMLIB_MAXRANSTART", params["SIMLIB_MAXRANSTART"])

    # Ensure single-event generation
    text = ensure_key_after(text, "NGEN_SEASON:", "NGENTOT_LC", "1")

    return text


def run_snlc_sim(input_path: Path, log_path: Path) -> int:
    import subprocess

    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as f:
        proc = subprocess.run(["snlc_sim.exe", str(input_path)], stdout=f, stderr=subprocess.STDOUT)
    return proc.returncode


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate per-event SNANA INPUTs from bns_population.csv and optionally run snlc_sim.exe",
    )
    parser.add_argument(
        "--samples",
        default=str(repo_path("data", "samples", "bns_population.csv")),
        help="CSV file with columns: mej_dyn, mej_wind, cos_theta, redshift",
    )
    parser.add_argument(
        "--surveys",
        default="both",
        choices=["LSST", "WFST", "both", "lsst", "wfst"],
        help="Which survey(s) to run",
    )
    parser.add_argument(
        "--start",
        type=int,
        default=1,
        help="1-based start event index",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=None,
        help="Number of events to process (default: all)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only generate INPUT files; do not run snlc_sim.exe",
    )
    parser.add_argument(
        "--base-seed",
        type=int,
        default=123456,
        help="Base random seed for RANSEED; event_id is added",
    )
    parser.add_argument(
        "--simlib-maxranstart",
        type=int,
        default=1000000,
        help="Value for SIMLIB_MAXRANSTART to randomize starting LIBID selection",
    )
    args = parser.parse_args()
    ensure_runtime_env()

    if args.simlib_maxranstart < 1:
        print("ERROR: --simlib-maxranstart must be >= 1")
        return 1

    samples_path = resolve_path(args.samples)
    if not samples_path.exists():
        print(f"ERROR: samples file not found: {samples_path}")
        return 1

    df = pd.read_csv(samples_path)

    col_mej_dyn = find_column(df, ["mej_dyn"])
    col_mej_wind = find_column(df, ["mej_wind"])
    col_cos_theta = find_column(df, ["cos_theta", "costheta"])
    col_redshift = find_column(df, ["redshift", "z"])

    total = len(df)
    start_idx = max(args.start - 1, 0)
    end_idx = total if args.count is None else min(start_idx + args.count, total)

    if start_idx >= total:
        print("ERROR: start index beyond dataset length")
        return 1

    repo_root = repo_path()
    input_dir = repo_root / "outputs" / "generated_inputs"
    log_dir = repo_root / "outputs" / "logs" / "astro_pop"
    log_dir.mkdir(parents=True, exist_ok=True)

    lsst_template = repo_root / "templates" / "snana" / "SIMGEN_KN_LSST_TEMPLATE.INPUT"
    wfst_template = repo_root / "templates" / "snana" / "SIMGEN_KN_WFST_TEMPLATE.INPUT"

    lsst_text = lsst_template.read_text(encoding="utf-8")
    wfst_text = wfst_template.read_text(encoding="utf-8")

    clipped_rows: List[Dict[str, str]] = []
    failed_rows: List[str] = []

    do_lsst = args.surveys.lower() in ("lsst", "both")
    do_wfst = args.surveys.lower() in ("wfst", "both")

    for idx in range(start_idx, end_idx):
        event_id = idx + 1
        row = df.iloc[idx]

        mej_dyn = float(row[col_mej_dyn])
        mej_wind = float(row[col_mej_wind])
        cos_theta = float(row[col_cos_theta])
        redshift = float(row[col_redshift])
        phi = 45.0

        # clip to model ranges
        mej_dyn_c, c1 = clip_param("mej_dyn", mej_dyn, 0.001, 0.02)
        mej_wind_c, c2 = clip_param("mej_wind", mej_wind, 0.01, 0.13)
        cos_theta_c, c3 = clip_param("cos_theta", cos_theta, 0.0, 1.0)
        redshift_c, c4 = clip_param("redshift", redshift, 0.01, 0.2)
        phi_c, c5 = clip_param("phi", phi, 0.0, 90.0)

        for name, orig, new, clipped in [
            ("mej_dyn", mej_dyn, mej_dyn_c, c1),
            ("mej_wind", mej_wind, mej_wind_c, c2),
            ("cos_theta", cos_theta, cos_theta_c, c3),
            ("redshift", redshift, redshift_c, c4),
            ("phi", phi, phi_c, c5),
        ]:
            if clipped:
                clipped_rows.append(
                    {
                        "event_id": str(event_id),
                        "param": name,
                        "orig": fmt_val(orig),
                        "clipped": fmt_val(new),
                    }
                )

        params_common = {
            "COSTHETA": fmt_val(cos_theta_c),
            "MEJDYN": fmt_val(mej_dyn_c),
            "MEJWIND": fmt_val(mej_wind_c),
            "PHI": fmt_val(phi_c),
            "REDSHIFT": fmt_val(redshift_c),
            "RANSEED": str(args.base_seed + event_id),
            "SIMLIB_MAXRANSTART": str(args.simlib_maxranstart),
        }

        if do_lsst:
            genversion = f"LSST_KN_ASTRO_{event_id}"
            params = {**params_common, "GENVERSION": genversion}
            input_text = build_input_text(lsst_text, params)
            out_dir = input_dir / "LSST"
            out_dir.mkdir(parents=True, exist_ok=True)
            input_path = out_dir / f"SIMGEN_{genversion}.INPUT"
            input_path.write_text(input_text, encoding="utf-8")

            if not args.dry_run:
                log_path = log_dir / f"LSST_{event_id}.log"
                rc = run_snlc_sim(input_path, log_path)
                if rc != 0:
                    failed_rows.append(f"LSST,{event_id}")

        if do_wfst:
            genversion = f"WFST_KN_ASTRO_{event_id}"
            params = {**params_common, "GENVERSION": genversion}
            input_text = build_input_text(wfst_text, params)
            out_dir = input_dir / "WFST"
            out_dir.mkdir(parents=True, exist_ok=True)
            input_path = out_dir / f"SIMGEN_{genversion}.INPUT"
            input_path.write_text(input_text, encoding="utf-8")

            if not args.dry_run:
                log_path = log_dir / f"WFST_{event_id}.log"
                rc = run_snlc_sim(input_path, log_path)
                if rc != 0:
                    failed_rows.append(f"WFST,{event_id}")

    # write clipped params log
    if clipped_rows:
        clipped_path = log_dir / "clipped_params.csv"
        with clipped_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["event_id", "param", "orig", "clipped"])
            writer.writeheader()
            writer.writerows(clipped_rows)

    # write failed ids log
    if failed_rows:
        failed_path = log_dir / "failed_ids.txt"
        failed_path.write_text("\n".join(failed_rows) + "\n", encoding="utf-8")

    # consolidate outputs for easier lookup
    if not args.dry_run:
        sim_root = default_sim_root()
        if do_lsst:
            dst = sim_root / "LSST_KN_ASTRO"
            dst.mkdir(parents=True, exist_ok=True)
            for p in sim_root.glob("LSST_KN_ASTRO_*"):
                target = dst / p.name
                try:
                    if target.exists():
                        shutil.rmtree(target)
                    p.rename(target)
                except Exception:
                    # keep going if one move fails
                    continue
        if do_wfst:
            dst = sim_root / "WFST_KN_ASTRO"
            dst.mkdir(parents=True, exist_ok=True)
            for p in sim_root.glob("WFST_KN_ASTRO_*"):
                target = dst / p.name
                try:
                    if target.exists():
                        shutil.rmtree(target)
                    p.rename(target)
                except Exception:
                    # keep going if one move fails
                    continue

    print(f"Processed events {start_idx + 1} to {end_idx} (total {end_idx - start_idx}).")
    print(f"INPUTs written to: {input_dir}")
    if args.dry_run:
        print("Dry run: snlc_sim.exe not executed.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
