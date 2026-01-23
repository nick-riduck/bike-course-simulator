import argparse
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    import matplotlib.pyplot as plt
except ImportError:
    print("Error: matplotlib is required for visualization.")
    print("Please install it using: pip install matplotlib")
    sys.exit(1)

from src.gpx_loader import GpxLoader

def visualize(gpx_path):
    loader = GpxLoader(gpx_path)
    print(f"Loading {gpx_path}...")
    loader.load()
    
    print("Applying smoothing...")
    loader.smooth_elevation(window_size=5)
    
    print("Compressing segments...")
    segments = loader.compress_segments(grade_threshold=0.005, heading_threshold=15.0)
    
    original_count = len(loader.points)
    segment_count = len(segments)
    compression_ratio = (1 - segment_count / original_count) * 100
    
    print(f"\n[Result]")
    print(f"Original Points: {original_count}")
    print(f"Segments: {segment_count}")
    print(f"Compression Ratio: {compression_ratio:.2f}%")

    # Prepare Data for Plotting
    orig_dist = [p.distance_from_start for p in loader.points]
    orig_ele = [p.ele for p in loader.points]
    
    seg_x = []
    seg_y = []
    
    for seg in segments:
        seg_x.append(seg.start_dist)
        seg_y.append(seg.start_ele)
        seg_x.append(seg.end_dist) # Draw line to end of segment
        seg_y.append(seg.end_ele)

    # Plot
    plt.figure(figsize=(12, 6))
    
    # 1. Elevation Profile
    plt.subplot(2, 1, 1)
    plt.plot(orig_dist, orig_ele, color='lightgray', label='Original (Smoothed)', linewidth=1)
    plt.plot(seg_x, seg_y, color='red', label='Adaptive Segments', linewidth=1.5, marker='.', markersize=2)
    plt.title(f"Elevation Profile (Compressed {compression_ratio:.1f}%)")
    plt.ylabel("Elevation (m)")
    plt.legend()
    plt.grid(True, linestyle='--', alpha=0.5)

    # 2. Grade Analysis (Segment Slope)
    plt.subplot(2, 1, 2)
    seg_grades = [s.grade * 100 for s in segments] # %
    seg_centers = [(s.start_dist + s.end_dist)/2 for s in segments]
    
    plt.bar(seg_centers, seg_grades, width=[s.length for s in segments], color='blue', alpha=0.5, label='Segment Grade %')
    plt.ylabel("Grade (%)")
    plt.xlabel("Distance (m)")
    plt.grid(True, linestyle='--', alpha=0.5)
    
    plt.tight_layout()
    
    output_path = "gpx_analysis.png"
    plt.savefig(output_path)
    print(f"Visualization saved to: {output_path}")
    
    # Try to show only if DISPLAY is available
    if os.environ.get('DISPLAY') or sys.platform == 'darwin':
        try:
            plt.show()
        except Exception:
            pass

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Visualize GPX Compression")
    parser.add_argument("gpx_file", help="Path to GPX file")
    args = parser.parse_args()
    
    if not os.path.exists(args.gpx_file):
        print(f"File not found: {args.gpx_file}")
        sys.exit(1)
        
    visualize(args.gpx_file)
