#!/usr/bin/env python
"""
Resample WFST filter transmission curves to 1 Angstrom resolution for SNANA.

This script reads the fine-resolution WFST filter files, interpolates them,
and resamples to 1 Angstrom resolution suitable for SNANA kcor.exe.
"""

import numpy as np
from scipy.interpolate import interp1d
import os
from pathlib import Path

# Paths
INPUT_DIR = Path("/fred/oz016/bgao_kn/SNANA/SNDATA_ROOT/filters/WFST")
OUTPUT_DIR = INPUT_DIR  # Output to same directory, or change if needed

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
    with open(filepath, 'w') as f:
        for wl, trans in zip(wavelength, transmission):
            f.write(f"{wl:.1f} {trans:.{precision}f}\n")


def main():
    print("=" * 60)
    print("WFST Filter Transmission Resampling")
    print(f"Input directory:  {INPUT_DIR}")
    print(f"Output directory: {OUTPUT_DIR}")
    print(f"Target resolution: {TARGET_RESOLUTION} Angstrom")
    print("=" * 60)
    
    for filter_file in FILTER_FILES:
        input_path = INPUT_DIR / filter_file
        
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
        # output_file = filter_file.removeplace("_fine", "")
        output_file = filter_file.replace("_fine", "")
        output_path = OUTPUT_DIR / output_file
        
        # Write output
        write_filter(output_path, wl_new, trans_new)
        print(f"  Written: {output_path}")
    
    print("\n" + "=" * 60)
    print("Done! Resampled filter files created.")
    print("=" * 60)


if __name__ == "__main__":
    main()
