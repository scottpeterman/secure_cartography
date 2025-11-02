#!/usr/bin/env python3
"""
Batch SVG to PNG Converter (Windows-friendly)
Uses svglib + reportlab (pure Python, no native dependencies)

Requirements: pip install svglib reportlab pillow

Author: Scott Peterman
"""

from pathlib import Path
import sys

try:
    from svglib.svglib import svg2rlg
    from reportlab.graphics import renderPM
    from PIL import Image
    import io
except ImportError as e:
    print(f"❌ Error: Required library not installed: {e}")
    print("\nInstall with: pip install svglib reportlab pillow")
    sys.exit(1)


def convert_svg_to_png(svg_path: Path, output_path: Path, width: int = 64, height: int = 64):
    """Convert a single SVG file to PNG using pure Python libraries."""
    try:
        # Read SVG and convert to ReportLab drawing
        drawing = svg2rlg(str(svg_path))

        if drawing is None:
            print(f"  ✗ Could not parse SVG: {svg_path.name}")
            return False

        # Scale the drawing to desired size
        scale_x = width / drawing.width
        scale_y = height / drawing.height
        scale = min(scale_x, scale_y)  # Maintain aspect ratio

        drawing.width = width
        drawing.height = height
        drawing.scale(scale, scale)

        # Render to PNG
        renderPM.drawToFile(drawing, str(output_path), fmt='PNG')

        return True

    except Exception as e:
        print(f"  ✗ Error converting {svg_path.name}: {e}")
        return False


def batch_convert(input_dir: str, output_dir: str, size: int = 64):
    """Convert all SVG files in a directory to PNG."""
    input_path = Path(input_dir)
    output_path = Path(output_dir)

    print("=" * 70)
    print(f"🎨 SVG to PNG Converter (Windows)")
    print("=" * 70)
    print(f"\n📂 Checking input directory: {input_path.absolute()}")

    if not input_path.exists():
        print(f"❌ Error: Input directory does not exist!")
        print(f"   Path: {input_path.absolute()}")
        return

    output_path.mkdir(parents=True, exist_ok=True)
    print(f"📁 Output directory: {output_path.absolute()}")

    svg_files = list(input_path.glob('*.svg'))

    if not svg_files:
        print(f"\n❌ No SVG files found in {input_dir}")
        print(f"   Looked in: {input_path.absolute()}")
        return

    print(f"📐 Size:   {size}x{size} pixels")
    print(f"\n🔄 Converting {len(svg_files)} SVG files...")
    print()

    success_count = 0

    for i, svg_file in enumerate(svg_files, 1):
        png_file = output_path / f"{svg_file.stem}.png"

        if i <= 5 or i % 50 == 0 or i == len(svg_files):
            print(f"[{i}/{len(svg_files)}] {svg_file.name} → {png_file.name}")

        if convert_svg_to_png(svg_file, png_file, size, size):
            success_count += 1

    print()
    print("=" * 70)
    print(f"✅ Successfully converted {success_count}/{len(svg_files)} files")
    print(f"📁 Output: {output_path.absolute()}")
    print("=" * 70)


def main():
    if len(sys.argv) < 3:
        print("Usage: python svg_to_png_windows.py <input_dir> <output_dir> [size]")
        print("\nArguments:")
        print("  input_dir   - Directory containing SVG files")
        print("  output_dir  - Directory for PNG output")
        print("  size        - PNG size in pixels (default: 64)")
        print("\n📝 Examples:")
        print("  python svg_to_png_windows.py cisco_svgs_cyberteal static\\icons_lib")
        print("  python svg_to_png_windows.py cisco_svgs_amber cisco_png_amber 128")
        sys.exit(0)

    input_dir = sys.argv[1]
    output_dir = sys.argv[2]
    size = int(sys.argv[3]) if len(sys.argv) > 3 else 64

    batch_convert(input_dir, output_dir, size)


if __name__ == "__main__":
    main()