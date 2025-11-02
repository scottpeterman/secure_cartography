import requests
from bs4 import BeautifulSoup
from pathlib import Path
import time


def download_cisco_svgs(html_file, output_dir='cisco_icons'):
    """
    Extract SVG links from Vecta HTML and download them.
    """
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    # Read the HTML file
    with open(html_file, 'r', encoding='utf-8') as f:
        html_content = f.read()

    # Parse with BeautifulSoup
    soup = BeautifulSoup(html_content, 'html.parser')

    # Find all SVG links - they're in the download section
    svg_links = []

    # Method 1: Find links with .svg extension
    for link in soup.find_all('a', href=True):
        href = link['href']
        if href.endswith('.svg') and 'symbols.getvecta.com' in href:
            svg_links.append(href)

    # Method 2: Also check data-src attributes on img tags
    for img in soup.find_all('img', attrs={'data-src': True}):
        data_src = img['data-src']
        if data_src.endswith('.svg'):
            svg_links.append(data_src)

    # Remove duplicates
    svg_links = list(set(svg_links))

    print(f"Found {len(svg_links)} SVG files to download")

    # Download each SVG
    for i, svg_url in enumerate(svg_links, 1):
        # Extract filename from URL
        filename = svg_url.split('/')[-1]

        # Clean up the filename (remove hash if desired)
        # e.g., "17_atm-router.1a0faf71b5.svg" -> "atm-router.svg"
        parts = filename.split('.')
        if len(parts) >= 3:  # has hash
            clean_name = f"{parts[0].split('_', 1)[-1]}.svg"
        else:
            clean_name = filename

        filepath = output_path / clean_name

        try:
            print(f"[{i}/{len(svg_links)}] Downloading: {clean_name}")
            response = requests.get(svg_url, timeout=10)
            response.raise_for_status()

            with open(filepath, 'wb') as f:
                f.write(response.content)

            # Be nice to the server
            time.sleep(0.5)

        except Exception as e:
            print(f"  ✗ Error downloading {clean_name}: {e}")
            continue

    print(f"\n✓ Downloaded {len(svg_links)} icons to {output_path}")


# Usage
if __name__ == "__main__":
    download_cisco_svgs('cisco_icons.html', 'cisco_svgs')