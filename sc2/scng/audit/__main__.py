"""
SCNG Audit - Module entry point.

Allows: python -m sc2.scng.audit [command] [args]
"""

from .cli import main

if __name__ == "__main__":
    main()