"""
Package Resource Helper for SC2
Provides reliable access to package data in both dev and wheel installations.

Uses importlib.resources (Python 3.9+) which handles:
- Installed wheels (including zip-imported packages)
- Editable installs
- Direct source execution
"""

import sys
from pathlib import Path
from typing import Optional, Union
from contextlib import contextmanager

if sys.version_info >= (3, 9):
    from importlib.resources import files, as_file
else:
    # Backport for Python 3.7-3.8
    from importlib_resources import files, as_file


def get_resource_path(package: str, resource_name: str) -> Path:
    """
    Get a filesystem path to a package resource.

    For resources that need a real filesystem path (like QWebEngineView URLs),
    this extracts the resource if necessary.

    Args:
        package: Dotted package name, e.g., 'sc2.ui' or 'sc2.export'
        resource_name: Resource filename, e.g., 'topology_viewer.html'

    Returns:
        Path to the resource file

    Example:
        html_path = get_resource_path('sc2.ui', 'topology_viewer.html')
        self._web_view.setUrl(QUrl.fromLocalFile(str(html_path)))
    """
    traversable = files(package).joinpath(resource_name)

    # For resources that exist on the real filesystem, return directly
    # This handles editable installs and source runs
    if hasattr(traversable, '_path'):
        return Path(traversable._path)

    # For zipped packages, we need to extract - but this returns a context manager
    # For persistent paths, use get_resource_path_persistent() instead
    try:
        # Try direct path access first (works for filesystem-based packages)
        return Path(str(traversable))
    except Exception:
        raise RuntimeError(
            f"Resource {resource_name} in {package} requires extraction. "
            "Use get_resource_context() for temporary extraction."
        )


@contextmanager
def get_resource_context(package: str, resource_name: str):
    """
    Context manager for resources that may need extraction from zip.

    Use this when you need temporary access to a resource file.
    The path is only valid within the context.

    Example:
        with get_resource_context('sc2.ui', 'topology_viewer.html') as html_path:
            self._web_view.setUrl(QUrl.fromLocalFile(str(html_path)))
    """
    traversable = files(package).joinpath(resource_name)
    with as_file(traversable) as path:
        yield path


def read_resource_text(package: str, resource_name: str) -> str:
    """
    Read a text resource directly into memory.

    Use this for resources you'll process in Python (config files, templates).

    Example:
        html_content = read_resource_text('sc2.ui', 'topology_viewer.html')
        self._web_view.setHtml(html_content)
    """
    return files(package).joinpath(resource_name).read_text(encoding='utf-8')


def read_resource_bytes(package: str, resource_name: str) -> bytes:
    """
    Read a binary resource directly into memory.

    Use this for icons, images, etc.

    Example:
        icon_data = read_resource_bytes('sc2.ui.assets.icons_lib', 'cisco_switch.jpg')
        b64_icon = base64.b64encode(icon_data).decode()
    """
    return files(package).joinpath(resource_name).read_bytes()


def get_resource_dir(package: str) -> Path:
    """
    Get the directory path for a package's resources.

    Note: This only works reliably for filesystem-based packages.
    For zipped packages, iterate resources instead.

    Example:
        icons_dir = get_resource_dir('sc2.ui.assets.icons_lib')
        for icon_file in icons_dir.glob('*.jpg'):
            ...
    """
    pkg_files = files(package)

    # Try to get a real path
    if hasattr(pkg_files, '_path'):
        return Path(pkg_files._path)

    # For traversables that support iteration
    try:
        # This works for most cases
        return Path(str(pkg_files))
    except Exception:
        raise RuntimeError(
            f"Cannot get directory path for {package}. "
            "Package may be zipped. Use iterate_resources() instead."
        )


def iterate_resources(package: str, pattern: str = "*"):
    """
    Iterate over resources in a package directory.

    Yields (name, read_func) tuples where read_func() returns bytes.
    Works for both filesystem and zipped packages.

    Example:
        for name, read_fn in iterate_resources('sc2.ui.assets.icons_lib', '*.jpg'):
            icon_data = read_fn()
            ...
    """
    import fnmatch

    pkg_files = files(package)
    for item in pkg_files.iterdir():
        if fnmatch.fnmatch(item.name, pattern):
            yield item.name, lambda i=item: i.read_bytes()


def resource_exists(package: str, resource_name: str) -> bool:
    """Check if a resource exists in a package."""
    try:
        traversable = files(package).joinpath(resource_name)
        return traversable.is_file()
    except Exception:
        return False