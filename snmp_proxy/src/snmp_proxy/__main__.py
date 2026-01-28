#!/usr/bin/env python3
"""
SNMP Proxy - CLI entry point

Usage:
    snmp-proxy [options]
    python -m snmp_proxy [options]
"""

import argparse
import logging
import sys
import uuid

import uvicorn

from . import __version__
from .server import app, set_api_key


def setup_logging(level: str = "INFO"):
    """Configure logging with optional colors"""
    
    # Color codes (disabled on Windows unless using Windows Terminal)
    use_color = sys.platform != 'win32' or 'WT_SESSION' in __import__('os').environ
    
    class ColorFormatter(logging.Formatter):
        COLORS = {
            'DEBUG': '\033[36m',    # Cyan
            'INFO': '\033[32m',     # Green
            'WARNING': '\033[33m',  # Yellow
            'ERROR': '\033[31m',    # Red
            'CRITICAL': '\033[35m', # Magenta
        }
        RESET = '\033[0m'
        
        def format(self, record):
            if use_color:
                color = self.COLORS.get(record.levelname, self.RESET)
                record.levelname = f"{color}{record.levelname:8}{self.RESET}"
            else:
                record.levelname = f"{record.levelname:8}"
            return super().format(record)
    
    # Configure root logger for our modules
    log_level = getattr(logging, level.upper(), logging.INFO)
    
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(ColorFormatter(
        '%(asctime)s | %(levelname)s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))
    
    # Set up our loggers
    for name in ['snmp_proxy', 'snmp_proxy.server', 'snmp_proxy.jobs', 'snmp_proxy.snmp']:
        logger = logging.getLogger(name)
        logger.setLevel(log_level)
        logger.handlers = [handler]
        logger.propagate = False


def print_banner(host: str, port: int, api_key: str, config: dict):
    """Print startup banner"""
    print()
    print("═" * 64)
    print(f"  SNMP PROXY v{__version__}")
    print("  Async ticket-based SNMP polling")
    print("═" * 64)
    print()
    print(f"  🔑 API Key: {api_key}")
    print()
    print(f"  📡 Server:  http://{host}:{port}")
    print(f"  🏥 Health:  http://{host}:{port}/health")
    print(f"  📚 Docs:    http://{host}:{port}/docs")
    print()
    print("  ⚙️  Configuration:")
    print(f"      Max concurrent polls: {config['max_concurrent']}")
    print(f"      Job retention:        {config['retention_hours']} hour(s)")
    print(f"      Default GET timeout:  {config['get_timeout']}s")
    print(f"      Default WALK timeout: {config['walk_timeout']}s")
    print()
    print("  📋 Endpoints:")
    print("      POST /snmp/poll       Submit poll job (returns ticket)")
    print("      GET  /status/{ticket} Check job status/get results")
    print("      DELETE /jobs/{ticket} Cancel or delete job")
    print("      GET  /jobs            List all jobs")
    print("      POST /snmp/get        Direct SNMP GET")
    print("      POST /snmp/walk       Direct SNMP WALK")
    print()
    print("  Use X-API-Key header for authentication")
    print("═" * 64)
    print()


def main():
    parser = argparse.ArgumentParser(
        description="SNMP Proxy - Async ticket-based SNMP polling server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  snmp-proxy                              # Default settings
  snmp-proxy --port 9000                  # Custom port
  snmp-proxy --max-concurrent 4           # Limit concurrent polls
  snmp-proxy --host 0.0.0.0 --port 8899   # Bind to all interfaces

The API key is generated fresh on each startup and printed to console.
Only authenticated requests with the X-API-Key header are accepted.
        """
    )
    
    parser.add_argument(
        '--host',
        default='0.0.0.0',
        help='Bind address (default: 0.0.0.0)'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=8899,
        help='Listen port (default: 8899)'
    )
    parser.add_argument(
        '--max-concurrent',
        type=int,
        default=6,
        help='Maximum concurrent polls (default: 6)'
    )
    parser.add_argument(
        '--retention-hours',
        type=int,
        default=1,
        help='Hours to retain completed jobs (default: 1)'
    )
    parser.add_argument(
        '--get-timeout',
        type=int,
        default=10,
        help='Default SNMP GET timeout in seconds (default: 10)'
    )
    parser.add_argument(
        '--walk-timeout',
        type=int,
        default=120,
        help='Default SNMP WALK timeout in seconds (default: 120)'
    )
    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='Log level (default: INFO)'
    )
    parser.add_argument(
        '--api-key',
        default=None,
        help='Use specific API key instead of generating one'
    )
    parser.add_argument(
        '--version',
        action='version',
        version=f'snmp-proxy {__version__}'
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.log_level)
    
    # Generate or use provided API key
    api_key = args.api_key or str(uuid.uuid4())
    set_api_key(api_key)
    
    # Store config in app state for lifespan to access
    app.state.max_concurrent = args.max_concurrent
    app.state.retention_hours = args.retention_hours
    app.state.get_timeout = args.get_timeout
    app.state.walk_timeout = args.walk_timeout
    
    # Print banner
    print_banner(
        args.host,
        args.port,
        api_key,
        {
            'max_concurrent': args.max_concurrent,
            'retention_hours': args.retention_hours,
            'get_timeout': args.get_timeout,
            'walk_timeout': args.walk_timeout,
        }
    )
    
    # Run server
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_level="warning",  # We handle our own logging
        access_log=False,
    )


if __name__ == "__main__":
    main()
