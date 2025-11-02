#!/usr/bin/env python3
"""
Direct SVG Color Themer
Replaces specific Cisco icon colors with exact theme colors.
No adaptive logic - just direct color mapping.

Author: Scott Peterman
"""

import xml.etree.ElementTree as ET
from pathlib import Path
import re
import sys


class DirectSVGThemer:
    """Direct color replacement - no adaptive logic."""

    def __init__(self, input_dir, output_dir, theme_name='cyberteal'):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.theme_name = theme_name
        self.output_dir.mkdir(exist_ok=True)

        # Define themes with explicit color mappings
        # Maps: original_color -> new_color
        self.themes = {
            # Dark Mode Themes
            'cyberteal': {
                'name': 'Cyber Teal (Dark)',
                'colors': {
                    # ALL Cisco blue variations -> cyber teal #00f4e4
                    '#046897': '#00f4e4',
                    '#0e6f9c': '#00f4e4',
                    '#036c9b': '#00f4e4',
                    '#126d99': '#00f4e4',
                    '#0f73a0': '#00f4e4',
                    '#007eba': '#00f4e4',
                    '#0b719f': '#00f4e4',
                    '#036897': '#00f4e4',
                    '#0c6d9c': '#00f4e4',
                    '#0c719f': '#00f4e4',
                    '#026c9b': '#00f4e4',
                    '#0d6e9c': '#00f4e4',
                    '#0e6a98': '#00f4e4',
                    '#126a98': '#00f4e4',
                    '#036998': '#00f4e4',
                    '#156287': '#00f4e4',
                    '#036e9d': '#00f4e4',
                    '#0084c0': '#00f4e4',

                    # Grays
                    '#b5b5b5': '#8b949e',
                    'gray': '#8b949e',
                    '#c1daea': '#39ff14',  # Light blue-gray -> cyber green

                    # White/light
                    '#ffffff': '#e0e0e0',
                    '#fff': '#e0e0e0',
                    'white': '#e0e0e0',

                    # Black/dark
                    '#000000': '#0a0e1a',
                    '#000': '#0a0e1a',
                    'black': '#0a0e1a',
                    '#060606': '#0a0e1a',
                }
            },

            'matrix': {
                'name': 'Matrix Green (Dark)',
                'colors': {
                    # ALL blues -> green variations
                    '#046897': '#00ff00',
                    '#0e6f9c': '#00ff00',
                    '#036c9b': '#00ff00',
                    '#126d99': '#00ff00',
                    '#0f73a0': '#00ff00',
                    '#007eba': '#00dd00',
                    '#0b719f': '#00ff00',
                    '#036897': '#00ff00',
                    '#0c6d9c': '#00ff00',
                    '#0c719f': '#00ff00',
                    '#026c9b': '#00ff00',
                    '#0d6e9c': '#00ff00',
                    '#0e6a98': '#00ff00',
                    '#126a98': '#00ff00',
                    '#036998': '#00ff00',
                    '#156287': '#00cc00',
                    '#036e9d': '#00ff00',
                    '#0084c0': '#00ff00',

                    # Grays -> greens
                    '#b5b5b5': '#00aa00',
                    'gray': '#00aa00',
                    '#c1daea': '#00cc00',

                    # Whites -> bright green
                    '#ffffff': '#00ff00',
                    '#fff': '#00ff00',
                    'white': '#00ff00',

                    # Blacks -> stay black
                    '#000000': '#000000',
                    '#000': '#000000',
                    'black': '#000000',
                    '#060606': '#000000',
                }
            },

            'amber': {
                'name': 'Retro Amber (Dark)',
                'colors': {
                    # ALL blues -> amber variations
                    '#046897': '#ffb000',
                    '#0e6f9c': '#ffb000',
                    '#036c9b': '#ffb000',
                    '#126d99': '#ffb000',
                    '#0f73a0': '#ffb000',
                    '#007eba': '#ffc933',
                    '#0b719f': '#ffb000',
                    '#036897': '#ffb000',
                    '#0c6d9c': '#ffb000',
                    '#0c719f': '#ffb000',
                    '#026c9b': '#ffb000',
                    '#0d6e9c': '#ffb000',
                    '#0e6a98': '#ffb000',
                    '#126a98': '#ffb000',
                    '#036998': '#ffb000',
                    '#156287': '#cc8800',
                    '#036e9d': '#ffb000',
                    '#0084c0': '#ffc933',

                    # Grays -> amber tones
                    '#b5b5b5': '#e6a000',
                    'gray': '#e6a000',
                    '#c1daea': '#ffd480',

                    # Whites -> light amber
                    '#ffffff': '#ffe6b3',
                    '#fff': '#ffe6b3',
                    'white': '#ffe6b3',

                    # Blacks -> dark brown
                    '#000000': '#1a0f00',
                    '#000': '#1a0f00',
                    'black': '#1a0f00',
                    '#060606': '#1a0f00',
                }
            },

            # Light Mode Themes
            'burgundy': {
                'name': 'Burgundy (Light)',
                'colors': {
                    # ALL blues -> burgundy variations
                    '#046897': '#8b1538',
                    '#0e6f9c': '#8b1538',
                    '#036c9b': '#8b1538',
                    '#126d99': '#8b1538',
                    '#0f73a0': '#8b1538',
                    '#007eba': '#a01d48',
                    '#0b719f': '#8b1538',
                    '#036897': '#8b1538',
                    '#0c6d9c': '#8b1538',
                    '#0c719f': '#8b1538',
                    '#026c9b': '#8b1538',
                    '#0d6e9c': '#8b1538',
                    '#0e6a98': '#8b1538',
                    '#126a98': '#8b1538',
                    '#036998': '#8b1538',
                    '#156287': '#6b0f2a',
                    '#036e9d': '#8b1538',
                    '#0084c0': '#a01d48',

                    # Grays -> burgundy tones
                    '#b5b5b5': '#9f1f42',
                    'gray': '#9f1f42',
                    '#c1daea': '#b33456',

                    # Whites
                    '#ffffff': '#ffffff',
                    '#fff': '#ffffff',
                    'white': '#ffffff',

                    # Blacks
                    '#000000': '#2d0a14',
                    '#000': '#2d0a14',
                    'black': '#2d0a14',
                    '#060606': '#2d0a14',
                }
            },

            'forest': {
                'name': 'Forest Green (Light)',
                'colors': {
                    # ALL blues -> forest green variations
                    '#046897': '#2d5016',
                    '#0e6f9c': '#2d5016',
                    '#036c9b': '#2d5016',
                    '#126d99': '#2d5016',
                    '#0f73a0': '#2d5016',
                    '#007eba': '#3d6b1f',
                    '#0b719f': '#2d5016',
                    '#036897': '#2d5016',
                    '#0c6d9c': '#2d5016',
                    '#0c719f': '#2d5016',
                    '#026c9b': '#2d5016',
                    '#0d6e9c': '#2d5016',
                    '#0e6a98': '#2d5016',
                    '#126a98': '#2d5016',
                    '#036998': '#2d5016',
                    '#156287': '#1f3d0c',
                    '#036e9d': '#2d5016',
                    '#0084c0': '#3d6b1f',

                    # Grays -> forest tones
                    '#b5b5b5': '#355a1a',
                    'gray': '#355a1a',
                    '#c1daea': '#4d7a2a',

                    # Whites
                    '#ffffff': '#fafaf5',
                    '#fff': '#fafaf5',
                    'white': '#fafaf5',

                    # Blacks
                    '#000000': '#1a1f0a',
                    '#000': '#1a1f0a',
                    'black': '#1a1f0a',
                    '#060606': '#1a1f0a',
                }
            },

            'autumn': {
                'name': 'Autumn Orange (Light)',
                'colors': {
                    # ALL blues -> autumn orange variations
                    '#046897': '#cc5500',
                    '#0e6f9c': '#cc5500',
                    '#036c9b': '#cc5500',
                    '#126d99': '#cc5500',
                    '#0f73a0': '#cc5500',
                    '#007eba': '#e67300',
                    '#0b719f': '#cc5500',
                    '#036897': '#cc5500',
                    '#0c6d9c': '#cc5500',
                    '#0c719f': '#cc5500',
                    '#026c9b': '#cc5500',
                    '#0d6e9c': '#cc5500',
                    '#0e6a98': '#cc5500',
                    '#126a98': '#cc5500',
                    '#036998': '#cc5500',
                    '#156287': '#994000',
                    '#036e9d': '#cc5500',
                    '#0084c0': '#e67300',

                    # Grays -> orange tones
                    '#b5b5b5': '#b35f00',
                    'gray': '#b35f00',
                    '#c1daea': '#e68533',

                    # Whites
                    '#ffffff': '#fff8f0',
                    '#fff': '#fff8f0',
                    'white': '#fff8f0',

                    # Blacks
                    '#000000': '#2d1f0a',
                    '#000': '#2d1f0a',
                    'black': '#2d1f0a',
                    '#060606': '#2d1f0a',
                }
            },
        }

    def normalize_color(self, color):
        """Normalize color to lowercase hex or name."""
        if not color:
            return None
        color = color.strip().lower()
        # Convert 3-digit hex to 6-digit
        if color.startswith('#') and len(color) == 4:
            color = '#' + ''.join([c * 2 for c in color[1:]])
        return color

    def replace_color(self, color, color_map):
        """Replace color if it exists in the map, otherwise return original."""
        if not color or color in ('none', 'transparent'):
            return color

        normalized = self.normalize_color(color)

        # Direct lookup
        if normalized in color_map:
            return color_map[normalized]

        # Return original if no mapping found
        return color

    def process_element(self, elem, color_map):
        """Process a single element's color attributes."""
        # Handle fill attribute
        if 'fill' in elem.attrib:
            elem.attrib['fill'] = self.replace_color(elem.attrib['fill'], color_map)

        # Handle stroke attribute
        if 'stroke' in elem.attrib:
            elem.attrib['stroke'] = self.replace_color(elem.attrib['stroke'], color_map)

        # Handle style attribute
        if 'style' in elem.attrib:
            style = elem.attrib['style']

            # Replace fill in style
            def replace_fill(match):
                original = match.group(1).strip()
                return f'fill:{self.replace_color(original, color_map)}'

            style = re.sub(r'fill:\s*([^;]+)', replace_fill, style)

            # Replace stroke in style
            def replace_stroke(match):
                original = match.group(1).strip()
                return f'stroke:{self.replace_color(original, color_map)}'

            style = re.sub(r'stroke:\s*([^;]+)', replace_stroke, style)

            elem.attrib['style'] = style

    def process_svg(self, svg_path, color_map):
        """Process a single SVG file."""
        try:
            ET.register_namespace('', 'http://www.w3.org/2000/svg')
            ET.register_namespace('xlink', 'http://www.w3.org/1999/xlink')

            tree = ET.parse(svg_path)
            root = tree.getroot()

            # Process root and all elements
            self.process_element(root, color_map)
            for elem in root.iter():
                self.process_element(elem, color_map)

            # Write output
            output_file = self.output_dir / svg_path.name
            tree.write(output_file, encoding='unicode', xml_declaration=True)

            return True
        except Exception as e:
            print(f"  ✗ Error: {svg_path.name}: {e}")
            return False

    def process_all(self):
        """Process all SVG files."""
        svg_files = list(self.input_dir.glob('*.svg'))

        if not svg_files:
            print(f"❌ No SVG files found in {self.input_dir}")
            return

        theme = self.themes.get(self.theme_name, self.themes['cyberteal'])
        color_map = theme['colors']

        print("=" * 70)
        print(f"⚡ Direct SVG Themer - {theme['name']}")
        print("=" * 70)
        print(f"\n📂 Input:  {self.input_dir}")
        print(f"📁 Output: {self.output_dir}")
        print(f"🎨 Theme:  {self.theme_name}")
        print(f"\n🔄 Processing {len(svg_files)} SVG files...")
        print()

        success_count = 0
        for i, svg_file in enumerate(svg_files, 1):
            if i <= 5 or i % 50 == 0 or i == len(svg_files):
                print(f"[{i}/{len(svg_files)}] {svg_file.name}")
            if self.process_svg(svg_file, color_map):
                success_count += 1

        print()
        print("=" * 70)
        print(f"✅ Successfully processed {success_count}/{len(svg_files)} files")
        print("=" * 70)


def main():
    if len(sys.argv) < 3:
        print("Usage: python svg_themer_direct.py <input_dir> <output_dir> [theme]")
        print("\n🎨 Available Themes:")
        print("\n  Dark Mode:")
        print("    cyberteal  - Cyber Teal (#00f4e4) - matches VelociTerm")
        print("    matrix     - Matrix Green (#00ff00)")
        print("    amber      - Retro Amber (#ffb000)")
        print("\n  Light Mode:")
        print("    burgundy   - Deep Burgundy (#8b1538)")
        print("    forest     - Forest Green (#2d5016)")
        print("    autumn     - Autumn Orange (#cc5500)")
        print("\n📝 Examples:")
        print("  python svg_themer_direct.py cisco_svgs cisco_svgs_teal cyberteal")
        print("  python svg_themer_direct.py cisco_svgs cisco_svgs_matrix matrix")
        print("  python svg_themer_direct.py cisco_svgs cisco_svgs_burgundy burgundy")
        sys.exit(0)

    input_dir = sys.argv[1]
    output_dir = sys.argv[2]
    theme = sys.argv[3] if len(sys.argv) > 3 else 'cyberteal'

    themer = DirectSVGThemer(input_dir, output_dir, theme)
    themer.process_all()


if __name__ == "__main__":
    main()