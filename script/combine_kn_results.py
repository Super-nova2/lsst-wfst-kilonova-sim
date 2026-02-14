#!/usr/bin/env python3
"""
Combine per-event SNANA outputs into a single dataset per survey.

Outputs per survey:
- *_KN_ASTRO_COMBINED_HEAD.FITS
- *_KN_ASTRO_COMBINED_PHOT.FITS
- *_KN_ASTRO_COMBINED.DUMP
- *_KN_ASTRO_COMBINED.README
- detected_summary_*.csv
"""
from __future__ import annotations

import argparse
import csv
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from astropy.io import fits
from astropy.table import Table, vstack


def parse_event_id(path: Path) -> Optional[int]:
    m = re.search(r"_(\d+)$", path.name)
    if not m:
        return None
    return int(m.group(1))


def safe_snid(base: str, idx: Optional[int] = None) -> str:
    if idx is None:
        snid = f"{base}"
    else:
        snid = f"{base}_{idx}"
    return snid[:16]


def load_fits_table(path: Path) -> Tuple[fits.Header, fits.ColDefs, Table]:
    try:
        with fits.open(path, memmap=False) as hdul:
            if len(hdul) < 2:
                raise OSError("missing table extension HDU[1]")
            if hdul[1].data is None:
                raise OSError("missing table data in HDU[1]")
            header0 = hdul[0].header.copy()
            cols = hdul[1].columns
            data = Table(hdul[1].data)
    except Exception as exc:
        raise OSError(f"failed to read FITS table: {path} ({exc})") from exc
    return header0, cols, data


def parse_readme_int(text: str, key: str) -> int:
    m = re.search(rf"^\s*{re.escape(key)}:\s*([+-]?\d+)", text, flags=re.MULTILINE)
    if not m:
        return 0
    try:
        return int(m.group(1))
    except Exception:
        return 0


def parse_readme_float(text: str, key: str) -> float:
    m = re.search(
        rf"^\s*{re.escape(key)}:\s*([+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)",
        text,
        flags=re.MULTILINE,
    )
    if not m:
        return 0.0
    try:
        return float(m.group(1))
    except Exception:
        return 0.0


def parse_nreject(text: str) -> List[int]:
    out = [0, 0, 0, 0]
    m = re.search(r"^\s*NREJECT:\s*\[([^\]]+)\]", text, flags=re.MULTILINE)
    if not m:
        return out
    parts = [p.strip() for p in m.group(1).split(",")]
    for i in range(min(4, len(parts))):
        try:
            out[i] = int(parts[i])
        except Exception:
            out[i] = 0
    return out


def replace_key_value(text: str, key: str, new_value: str) -> str:
    pattern = re.compile(
        rf"^(\s*{re.escape(key)}:\s*)(.*?)(\s*(?:#.*)?)$",
        flags=re.MULTILINE,
    )
    return pattern.sub(lambda m: f"{m.group(1)}{new_value}{m.group(3)}", text, count=1)


def replace_input_file_block(text: str, source_dir: Path) -> str:
    pattern = re.compile(r"(^\s*INPUT_FILE:\s*\n)(?:^\s*-\s.*\n)*", flags=re.MULTILINE)
    replacement = f"    INPUT_FILE:\n    - COMBINED_FROM: {source_dir}\n"
    if pattern.search(text):
        return pattern.sub(replacement, text, count=1)
    return text


def normalize_varnames(varnames_line: str) -> str:
    return " ".join(varnames_line.split())


def extract_dump_parts(dump_path: Path) -> Tuple[List[str], Optional[str], List[str]]:
    lines = dump_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    header_lines: List[str] = []
    varnames_line: Optional[str] = None
    sn_lines: List[str] = []
    seen_varnames = False

    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("VARNAMES:"):
            if varnames_line is None:
                varnames_line = line.rstrip()
            seen_varnames = True
            continue

        if stripped.startswith("SN:"):
            sn_lines.append(line.rstrip())
            continue

        if not seen_varnames:
            header_lines.append(line.rstrip())

    return header_lines, varnames_line, sn_lines


def renumber_cid(sn_line: str, cid: int) -> str:
    m = re.match(r"^(\s*SN:\s*)\S+(.*)$", sn_line)
    if not m:
        return sn_line
    return f"{m.group(1)}{cid}{m.group(2)}"


def write_combined_dump(
    survey: str,
    input_dir: Path,
    out_dir: Path,
    event_dirs: Sequence[Tuple[int, Path]],
) -> Tuple[Optional[Path], int]:
    header_template: List[str] = []
    varnames_template: Optional[str] = None
    varnames_norm: Optional[str] = None
    combined_sn_lines: List[str] = []
    cid_counter = 1

    for event_id, ev_dir in event_dirs:
        dump_path = ev_dir / f"{survey}_KN_ASTRO_{event_id}.DUMP"
        if not dump_path.exists():
            print(f"WARN: missing DUMP for event {event_id}: {dump_path}")
            continue

        header_lines, varnames_line, sn_lines = extract_dump_parts(dump_path)
        if varnames_line is None:
            print(f"WARN: missing VARNAMES in DUMP for event {event_id}: {dump_path}")
            continue

        this_norm = normalize_varnames(varnames_line)
        if varnames_template is None:
            header_template = header_lines
            varnames_template = varnames_line
            varnames_norm = this_norm
        elif this_norm != varnames_norm:
            print(
                f"WARN: VARNAMES mismatch in DUMP for event {event_id}, skip SN rows from {dump_path}"
            )
            continue

        for sn_line in sn_lines:
            combined_sn_lines.append(renumber_cid(sn_line, cid_counter))
            cid_counter += 1

    if varnames_template is None:
        print(f"WARN: no valid DUMP found under {input_dir}")
        return None, 0

    dump_out = out_dir / f"{survey}_KN_ASTRO_COMBINED.DUMP"
    out_lines = list(header_template)
    if out_lines and out_lines[-1] != "":
        out_lines.append("")
    out_lines.append(varnames_template)
    out_lines.append("")
    out_lines.extend(combined_sn_lines)
    dump_out.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    return dump_out, len(combined_sn_lines)


def write_combined_readme(
    survey: str,
    input_dir: Path,
    out_dir: Path,
    event_dirs: Sequence[Tuple[int, Path]],
    detected_count: int,
    head_rows: int,
    phot_rows: int,
    dump_rows: int,
    head_out: Path,
    phot_out: Path,
    dump_out: Optional[Path],
    summary_path: Path,
) -> Optional[Path]:
    template_text: Optional[str] = None
    template_path: Optional[Path] = None
    stats = {
        "cpu_minutes": 0.0,
        "ngenev_tot": 0,
        "ngenlc_tot": 0,
        "ngenlc_write": 0,
        "ngenspec_write": 0,
        "ngen_per_season": 0,
        "nreject": [0, 0, 0, 0],
    }

    for event_id, ev_dir in event_dirs:
        readme_path = ev_dir / f"{survey}_KN_ASTRO_{event_id}.README"
        if not readme_path.exists():
            print(f"WARN: missing README for event {event_id}: {readme_path}")
            continue

        text = readme_path.read_text(encoding="utf-8", errors="ignore")
        if template_text is None:
            template_text = text
            template_path = readme_path

        stats["cpu_minutes"] += parse_readme_float(text, "CPU_MINUTES")
        stats["ngenev_tot"] += parse_readme_int(text, "NGENEV_TOT")
        stats["ngenlc_tot"] += parse_readme_int(text, "NGENLC_TOT")
        stats["ngenlc_write"] += parse_readme_int(text, "NGENLC_WRITE")
        stats["ngenspec_write"] += parse_readme_int(text, "NGENSPEC_WRITE")
        stats["ngen_per_season"] += parse_readme_int(text, "NGEN_PER_SEASON")

        nreject = parse_nreject(text)
        for i in range(4):
            stats["nreject"][i] += nreject[i]

    if template_text is None:
        print(f"WARN: no valid README found under {input_dir}")
        return None

    ngenlc_tot = stats["ngenlc_tot"]
    ngenlc_write = stats["ngenlc_write"]
    eff = (ngenlc_write / ngenlc_tot) if ngenlc_tot > 0 else 0.0
    eff_err = math.sqrt(eff * (1.0 - eff) / ngenlc_tot) if ngenlc_tot > 0 else 0.0
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d  %H:%M")

    readme_text = template_text
    readme_text = replace_key_value(readme_text, "TIME_START", f"{now_utc}  ")
    readme_text = replace_key_value(readme_text, "GENVERSION", f"{survey}_KN_ASTRO_COMBINED")
    readme_text = replace_key_value(readme_text, "CWD", str(Path.cwd()))
    readme_text = replace_input_file_block(readme_text, input_dir)

    readme_text = replace_key_value(readme_text, "CPU_MINUTES", f"{stats['cpu_minutes']:.2f}")
    readme_text = replace_key_value(readme_text, "NGENEV_TOT", str(stats["ngenev_tot"]))
    readme_text = replace_key_value(readme_text, "NGENLC_TOT", str(stats["ngenlc_tot"]))
    readme_text = replace_key_value(readme_text, "NGENLC_WRITE", str(stats["ngenlc_write"]))
    readme_text = replace_key_value(readme_text, "NGENSPEC_WRITE", str(stats["ngenspec_write"]))
    readme_text = replace_key_value(readme_text, "EFF(SEARCH+CUTS)", f"{eff:.4f} +-  {eff_err:.4f}")
    readme_text = replace_key_value(readme_text, "NACCEPT", f"[ {ngenlc_write}, 0, 0 ]")
    readme_text = replace_key_value(readme_text, "NGEN_PER_SEASON", str(stats["ngen_per_season"]))
    readme_text = replace_key_value(
        readme_text,
        "NREJECT",
        f"[{stats['nreject'][0]},   {stats['nreject'][1]}, {stats['nreject'][2]}, {stats['nreject'][3]}]",
    )

    readme_text = re.sub(
        r"\n  MERGE_INFO:\n.*?(?=\nDOCUMENTATION_END:)",
        "\n",
        readme_text,
        flags=re.DOTALL,
    )
    merge_lines = [
        "  MERGE_INFO:",
        f"    MERGE_TIME_UTC:   {now_utc}",
        f"    SOURCE_DIR:       {input_dir}",
        f"    TEMPLATE_README:  {template_path}",
        f"    EVENT_DIRS_TOTAL: {len(event_dirs)}",
        f"    EVENTS_DETECTED:  {detected_count}",
        f"    HEAD_ROWS:        {head_rows}",
        f"    PHOT_ROWS:        {phot_rows}",
        f"    DUMP_SN_ROWS:     {dump_rows}",
        "    OUTPUT_FILES:",
        f"    - {head_out.name}",
        f"    - {phot_out.name}",
        f"    - {dump_out.name if dump_out is not None else 'NONE'}",
        f"    - {summary_path.name}",
    ]
    merge_block = "\n" + "\n".join(merge_lines) + "\n"
    if "DOCUMENTATION_END:" in readme_text:
        readme_text = readme_text.replace("DOCUMENTATION_END:", f"{merge_block}DOCUMENTATION_END:", 1)
    else:
        readme_text = readme_text.rstrip() + merge_block + "\n"

    readme_out = out_dir / f"{survey}_KN_ASTRO_COMBINED.README"
    readme_out.write_text(readme_text, encoding="utf-8")
    return readme_out


def combine_survey(sim_root: Path, survey: str, snid_prefix: str, event_id_list: Optional[List[str]]) -> None:
    input_dir = sim_root / f"{survey}_KN_ASTRO"
    if not input_dir.exists():
        print(f"WARN: input dir not found: {input_dir}")
        return

    out_dir = sim_root / f"{survey}_KN_ASTRO_COMBINED"
    out_dir.mkdir(parents=True, exist_ok=True)

    head_tables: List[Table] = []
    phot_tables: List[Table] = []
    head_header0: Optional[fits.Header] = None
    phot_header0: Optional[fits.Header] = None
    head_cols: Optional[fits.ColDefs] = None
    phot_cols: Optional[fits.ColDefs] = None

    summary_rows: List[Dict[str, str]] = []
    phot_offset = 0

    # collect event dirs
    event_dirs: List[Tuple[int, Path]] = []
    for p in input_dir.iterdir():
        if p.is_dir() and p.name.startswith(f"{survey}_KN_ASTRO_"):
            event_id = parse_event_id(p)
            if event_id is not None:
                event_dirs.append((event_id, p))
    event_dirs.sort(key=lambda x: x[0])

    for event_id, ev_dir in event_dirs:
        head_path = ev_dir / f"{survey}_KN_ASTRO_{event_id}_HEAD.FITS"
        phot_path = ev_dir / f"{survey}_KN_ASTRO_{event_id}_PHOT.FITS"
        if not head_path.exists():
            print(f"WARN: missing HEAD for event {event_id}: {head_path}")
            summary_rows.append({
                "event_id": str(event_id),
                "detected": "0",
                "n_head_rows": "0",
                "n_obs": "0",
                "sim_searcheff_mask": "",
            })
            continue

        # load head
        try:
            h0, hcols, head_tbl = load_fits_table(head_path)
        except OSError as exc:
            print(f"WARN: invalid HEAD for event {event_id}: {head_path} ({exc})")
            summary_rows.append({
                "event_id": str(event_id),
                "detected": "0",
                "n_head_rows": "0",
                "n_obs": "0",
                "sim_searcheff_mask": "",
            })
            continue
        if head_header0 is None:
            head_header0 = h0
        if head_cols is None:
            head_cols = hcols

        n_head = len(head_tbl)
        detected = 1 if n_head > 0 else 0

        # load phot if present
        phot_tbl = None
        n_phot = 0
        if phot_path.exists():
            try:
                p0, pcols, phot_tbl = load_fits_table(phot_path)
                if phot_header0 is None:
                    phot_header0 = p0
                if phot_cols is None:
                    phot_cols = pcols
                n_phot = len(phot_tbl)
            except OSError as exc:
                print(f"WARN: invalid PHOT for event {event_id}: {phot_path} ({exc})")
                phot_tbl = None
                n_phot = 0

        # summary values
        n_obs = 0
        sim_mask = ""
        if n_head > 0:
            if "NOBS" in head_tbl.colnames:
                n_obs = int(head_tbl["NOBS"].sum())
            if "SIM_SEARCHEFF_MASK" in head_tbl.colnames:
                try:
                    sim_mask = str(int(head_tbl["SIM_SEARCHEFF_MASK"][0]))
                except Exception:
                    sim_mask = ""

        summary_rows.append({
            "event_id": str(event_id),
            "detected": str(detected),
            "n_head_rows": str(n_head),
            "n_obs": str(n_obs),
            "sim_searcheff_mask": sim_mask,
        })

        if n_head > 0:
            # determine base SNID: prefer event_id from population CSV (first column)
            if event_id_list and 0 <= (event_id - 1) < len(event_id_list):
                base_snid = str(event_id_list[event_id - 1])
            else:
                base_snid = f"{snid_prefix}_{event_id}" if snid_prefix else str(event_id)

            # update SNID
            if len(head_tbl) == 1:
                head_tbl["SNID"] = safe_snid(base_snid)
            else:
                for i in range(len(head_tbl)):
                    head_tbl["SNID"][i] = safe_snid(base_snid, i + 1)

            # adjust PTROBS if phot exists
            if phot_tbl is not None and n_phot > 0 and "PTROBS_MIN" in head_tbl.colnames:
                mask = head_tbl["PTROBS_MIN"] > 0
                head_tbl["PTROBS_MIN"][mask] = head_tbl["PTROBS_MIN"][mask] + phot_offset
                if "PTROBS_MAX" in head_tbl.colnames:
                    head_tbl["PTROBS_MAX"][mask] = head_tbl["PTROBS_MAX"][mask] + phot_offset

            head_tables.append(head_tbl)

        if phot_tbl is not None and n_phot > 0:
            phot_tables.append(phot_tbl)
            phot_offset += n_phot

    # build combined HEAD/PHOT tables
    if head_cols is None or phot_cols is None:
        print(f"ERROR: cannot combine {survey}; missing template columns")
        return

    if head_tables:
        head_combined = vstack(head_tables, metadata_conflicts="silent")
    else:
        head_combined = Table(fits.BinTableHDU.from_columns(head_cols, nrows=0).data)

    if phot_tables:
        phot_combined = vstack(phot_tables, metadata_conflicts="silent")
    else:
        phot_combined = Table(fits.BinTableHDU.from_columns(phot_cols, nrows=0).data)

    # write combined HEAD
    head_out = out_dir / f"{survey}_KN_ASTRO_COMBINED_HEAD.FITS"
    phot_out = out_dir / f"{survey}_KN_ASTRO_COMBINED_PHOT.FITS"

    head_primary = fits.PrimaryHDU(header=head_header0)
    head_primary.header["VERSION"] = f"{survey}_KN_ASTRO_COMBINED"
    head_primary.header["PHOTFILE"] = phot_out.name
    head_hdu = fits.BinTableHDU(head_combined)
    fits.HDUList([head_primary, head_hdu]).writeto(head_out, overwrite=True)

    phot_primary = fits.PrimaryHDU(header=phot_header0)
    phot_primary.header["VERSION"] = f"{survey}_KN_ASTRO_COMBINED"
    phot_primary.header["PHOTFILE"] = phot_out.name
    phot_hdu = fits.BinTableHDU(phot_combined)
    fits.HDUList([phot_primary, phot_hdu]).writeto(phot_out, overwrite=True)

    # write summary
    summary_path = out_dir / f"detected_summary_{survey}.csv"
    with summary_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["event_id", "detected", "n_head_rows", "n_obs", "sim_searcheff_mask"],
        )
        writer.writeheader()
        writer.writerows(summary_rows)

    detected_count = sum(int(row["detected"]) for row in summary_rows)
    dump_out, dump_rows = write_combined_dump(
        survey,
        input_dir,
        out_dir,
        event_dirs,
    )
    readme_out = write_combined_readme(
        survey=survey,
        input_dir=input_dir,
        out_dir=out_dir,
        event_dirs=event_dirs,
        detected_count=detected_count,
        head_rows=len(head_combined),
        phot_rows=len(phot_combined),
        dump_rows=dump_rows,
        head_out=head_out,
        phot_out=phot_out,
        dump_out=dump_out,
        summary_path=summary_path,
    )

    print(f"[{survey}] combined HEAD: {head_out}")
    print(f"[{survey}] combined PHOT: {phot_out}")
    print(f"[{survey}] combined DUMP: {dump_out if dump_out is not None else 'NONE'}")
    print(f"[{survey}] combined README: {readme_out if readme_out is not None else 'NONE'}")
    print(f"[{survey}] summary: {summary_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Combine per-event SNANA outputs into one HEAD/PHOT per survey")
    parser.add_argument("--survey", default="both", choices=["LSST", "WFST", "both", "lsst", "wfst"])
    parser.add_argument("--sim-root", default="/fred/oz016/bgao_kn/SNANA/SNDATA_ROOT/SIM")
    parser.add_argument("--snid-prefix", default="ASTRO")
    parser.add_argument(
        "--population-csv",
        default="LSST+WFST/results/Astrophysical/bns_population.csv",
        help="CSV with first column as event_id for SNID mapping",
    )
    args = parser.parse_args()

    sim_root = Path(args.sim_root)
    do_lsst = args.survey.lower() in ("lsst", "both")
    do_wfst = args.survey.lower() in ("wfst", "both")

    event_id_list: Optional[List[str]] = None
    pop_path = Path(args.population_csv)
    if pop_path.exists():
        with pop_path.open("r", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            # treat first column as event_id (per requirement)
            if header is not None and len(header) > 0:
                event_id_list = [row[0] for row in reader if row]

    if do_lsst:
        combine_survey(sim_root, "LSST", args.snid_prefix, event_id_list)
    if do_wfst:
        combine_survey(sim_root, "WFST", args.snid_prefix, event_id_list)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
