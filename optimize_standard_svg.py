#!/usr/bin/env python3
"""
Script to optimize the standard.svg file using our SVG optimizer

This script:
1. Reads the standard.svg file
2. Runs the SVG optimizer on it
3. Saves the optimized SVG to a new file
4. Prints statistics about the optimization
"""

import os
import sys
from svg_optimizer import simplify_svg

def optimize_standard_svg():
    """Optimize the standard.svg file and save the result"""
    # File paths
    input_file = "diplomacy/maps/svg/standard.svg"
    output_file = "diplomacy/maps/svg/standard_optimized.svg"
    
    print(f"=== OPTIMIZING {input_file} ===")
    
    # Check if input file exists
    if not os.path.exists(input_file):
        print(f"Error: Input file '{input_file}' not found!")
        return False
    
    # Read the input file
    print(f"Reading input file...")
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            svg_content = f.read()
    except Exception as e:
        print(f"Error reading input file: {e}")
        return False
    
    # Run the optimizer
    print(f"Running SVG optimizer...")
    optimized_svg = simplify_svg(svg_content)
    
    # Save the optimized SVG
    print(f"Saving optimized SVG to {output_file}...")
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(optimized_svg)
    except Exception as e:
        print(f"Error saving optimized file: {e}")
        return False
    
    # Print statistics
    original_size = len(svg_content)
    optimized_size = len(optimized_svg)
    reduction = (1 - optimized_size / original_size) * 100
    
    print("\n=== OPTIMIZATION RESULTS ===")
    print(f"Original file size: {original_size:,} bytes")
    print(f"Optimized file size: {optimized_size:,} bytes")
    print(f"Size reduction: {reduction:.2f}%")
    print(f"\nOptimized SVG saved to: {output_file}")
    
    return True

if __name__ == "__main__":
    success = optimize_standard_svg()
    sys.exit(0 if success else 1) 