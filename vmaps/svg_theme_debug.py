#!/usr/bin/env python3
"""
Debug SVG Themer - Shows what colors are found and replaced
"""

import xml.etree.ElementTree as ET
from pathlib import Path
import re
import sys
from collections import Counter


class DebugSVGThemer:
    """Debug version that shows all colors found."""

    def __init__(self, input_dir):
        self.input_dir = Path(input_dir)
        self.all_colors = Counter()

    def normalize_color(self, color):
        """Normalize color to lowercase hex or name."""
        if not color:
            return None
        color = color.strip().lower()
        # Convert 3-digit hex to 6-digit
        if color.startswith('#') and len(color) == 4:
            color = '#' + ''.join([c * 2 for c in color[1:]])
        return color

    def extract_colors_from_element(self, elem):
        """Extract all colors from an element."""
        # Check fill attribute
        if 'fill' in elem.attrib:
            color = self.normalize_color(elem.attrib['fill'])
            if color and color not in ('none', 'transparent'):
                self.all_colors[('fill', color)] += 1

        # Check stroke attribute
        if 'stroke' in elem.attrib:
            color = self.normalize_color(elem.attrib['stroke'])
            if color and color not in ('none', 'transparent'):
                self.all_colors[('stroke', color)] += 1

        # Check style attribute
        if 'style' in elem.attrib:
            style = elem.attrib['style']

            # Find fill in style
            fill_match = re.search(r'fill:\s*([^;]+)', style)
            if fill_match:
                color = self.normalize_color(fill_match.group(1))
                if color and color not in ('none', 'transparent'):
                    self.all_colors[('fill', color)] += 1

            # Find stroke in style
            stroke_match = re.search(r'stroke:\s*([^;]+)', style)
            if stroke_match:
                color = self.normalize_color(stroke_match.group(1))
                if color and color not in ('none', 'transparent'):
                    self.all_colors[('stroke', color)] += 1

    def analyze_svg(self, svg_path):
        """Analyze a single SVG file."""
        try:
            tree = ET.parse(svg_path)
            root = tree.getroot()

            # Check root
            self.extract_colors_from_element(root)

            # Check all elements
            for elem in root.iter():
                self.extract_colors_from_element(elem)

            return True
        except Exception as e:
            print(f"  ✗ Error: {svg_path.name}: {e}")
            return False

    def analyze_all(self):
        """Analyze all SVG files."""
        svg_files = list(self.input_dir.glob('*.svg'))

        if not svg_files:
            print(f"❌ No SVG files found in {self.input_dir}")
            return

        print("=" * 70)
        print(f"🔍 Analyzing {len(svg_files)} SVG files")
        print("=" * 70)
        print()

        for svg_file in svg_files:
            self.analyze_svg(svg_file)

        # Display results
        print(f"Found {len(self.all_colors)} unique color/attribute combinations:")
        print()
        print("Type     Count   Color")
        print("-" * 70)

        # Sort by count (most common first)
        for (attr_type, color), count in self.all_colors.most_common(30):
            print(f"{attr_type:8} {count:5}   {color}")

        print()
        print("=" * 70)
        print("Copy these colors into your theme dictionary!")
        print("=" * 70)


def main():
    if len(sys.argv) < 2:
        print("Usage: python svg_themer_debug.py <svg_directory>")
        print("\nExample: python svg_themer_debug.py cisco_svgs")
        sys.exit(0)

    input_dir = sys.argv[1]
    analyzer = DebugSVGThemer(input_dir)
    analyzer.analyze_all()


if __name__ == "__main__":
    main()