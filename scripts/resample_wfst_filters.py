#!/usr/bin/env python3
"""
Resample WFST filter transmission curves to 1 Angstrom resolution for SNANA.

This script reads the fine-resolution WFST filter files, interpolates them,
and resamples to 1 Angstrom resolution suitable for SNANA kcor.exe.
"""

import argparse
import os
from pathlib import Path

import numpy as np
from scipy.interpolate import interp1d

from project_paths import repo_path, resolve_path

# Filter files to process
FILTER_FILES = [
    "WFST_u_fine.dat",
    "WFST_g_fine.dat",
    "WFST_r_fine.dat",
    "WFST_i_fine.dat",
    "WFST_z_fine.dat",
    "WFST_w_fine.dat",
]

# Target resolution in Angstrom
TARGET_RESOLUTION = 1.0


def default_input_dir() -> Path:
    if "SNDATA_ROOT" in os.environ:
        sndata_root = Path(os.path.expandvars(os.path.expanduser(os.environ["SNDATA_ROOT"])))
        return sndata_root / "filters" / "WFST"
    return repo_path("data", "filters", "wfst")


def read_filter(filepath):
    """Read filter transmission file.
    
    Args:
        filepath: Path to filter file
        
    Returns:
        wavelength: Array of wavelengths in Angstrom
        transmission: Array of transmission values
    """
    data = np.loadtxt(filepath)
    wavelength = data[:, 0]
    transmission = data[:, 1]
    return wavelength, transmission


def resample_filter(wavelength, transmission, resolution=1.0):
    """Resample filter transmission to new resolution.
    
    Args:
        wavelength: Original wavelength array
        transmission: Original transmission array
        resolution: Target resolution in Angstrom (default=1.0)
        
    Returns:
        new_wavelength: Resampled wavelength array
        new_transmission: Resampled transmission array
    """
    # Create interpolation function (linear interpolation)
    interp_func = interp1d(
        wavelength, 
        transmission, 
        kind='linear',
        bounds_error=False,
        fill_value=0.0  # Set to 0 outside the original range
    )
    
    # Create new wavelength grid with target resolution
    # Round to nearest integer Angstrom for clean grid
    wl_min = np.ceil(wavelength.min())
    wl_max = np.floor(wavelength.max())
    new_wavelength = np.arange(wl_min, wl_max + resolution, resolution)
    
    # Interpolate transmission to new grid
    new_transmission = interp_func(new_wavelength)
    
    # Ensure non-negative values
    new_transmission = np.maximum(new_transmission, 0.0)
    
    return new_wavelength, new_transmission


def write_filter(filepath, wavelength, transmission, precision=6):
    """Write filter transmission to file.
    
    Args:
        filepath: Output path
        wavelength: Wavelength array
        transmission: Transmission array
        precision: Decimal precision for transmission values
    """
    with open(filepath, 'w', encoding='utf-8') as f:
        for wl, trans in zip(wavelength, transmission):
            f.write(f"{wl:.1f} {trans:.{precision}f}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Resample WFST filter transmission curves to 1 Angstrom resolution."
    )
    parser.add_argument(
        "--input-dir",
        default=str(default_input_dir()),
        help="Directory containing the fine-resolution WFST filter files.",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Directory for the resampled filters (default: same as --input-dir).",
    )
    args = parser.parse_args()

    input_dir = resolve_path(args.input_dir)
    output_dir = resolve_path(args.output_dir) if args.output_dir else input_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("WFST Filter Transmission Resampling")
    print(f"Input directory:  {input_dir}")
    print(f"Output directory: {output_dir}")
    print(f"Target resolution: {TARGET_RESOLUTION} Angstrom")
    print("=" * 60)
    
    for filter_file in FILTER_FILES:
        input_path = input_dir / filter_file
        
        if not input_path.exists():
            print(f"[SKIP] {filter_file} not found")
            continue
        
        # Read original filter
        wl_orig, trans_orig = read_filter(input_path)
        orig_resolution = np.median(np.diff(wl_orig))
        
        print(f"\nProcessing: {filter_file}")
        print(f"  Original: {len(wl_orig)} points, "
              f"λ = {wl_orig.min():.1f} - {wl_orig.max():.1f} Å, "
              f"Δλ ≈ {orig_resolution:.3f} Å")
        
        # Resample
        wl_new, trans_new = resample_filter(wl_orig, trans_orig, TARGET_RESOLUTION)
        
        print(f"  Resampled: {len(wl_new)} points, "
              f"λ = {wl_new.min():.1f} - {wl_new.max():.1f} Å, "
              f"Δλ = {TARGET_RESOLUTION} Å")
        
        # Output filename: replace _fine with _1A
        output_file = filter_file.replace("_fine", "")
        output_path = output_dir / output_file
        
        # Write output
        write_filter(output_path, wl_new, trans_new)
        print(f"  Written: {output_path}")
    
    print("\n" + "=" * 60)
    print("Done! Resampled filter files created.")
    print("=" * 60)


if __name__ == "__main__":
    main()
