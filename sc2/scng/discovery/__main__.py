"""
SecureCartography NG - Discovery Module Entry Point.

Allows running discovery as a module:
    python -m sc2.scng.discovery discover <target>
    python -m sc2.scng.discovery crawl <seeds...>
    python -m sc2.scng.discovery test <target>
"""

from sc2.scng.discovery.cli import main

if __name__ == '__main__':
    main()
