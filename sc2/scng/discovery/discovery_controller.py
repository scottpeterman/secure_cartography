"""
SecureCartography v2 - Discovery Controller

Integrates the discovery engine with the PyQt6 GUI.
Handles threading, event bridging, and UI state management.

Place this file at: sc2/scng/discovery/discovery_controller.py

Usage in main_window.py:
    from .discovery_controller import DiscoveryController

    # In MainWindow.__init__ (after _apply_theme):
    self.discovery_controller = DiscoveryController(self)

    # Replace _on_start_crawl with:
    def _on_start_crawl(self):
        if self.discovery_controller.is_running:
            self.discovery_controller.cancel()
            return
        # ... get config from panels ...
        self.discovery_controller.start_crawl(seeds=seeds, max_depth=depth, ...)

Required panel methods:
    progress_panel:
        - reset()           : Zero all counters
        - set_running()     : Show running state
        - set_idle()        : Show idle state
        - set_status(str)   : Update status text
        - set_depth(cur, max) : Update depth indicator
        - set_progress(int) : Update progress bar (0-100)
        - set_counts(discovered, failed, queue, total)

    log_panel:
        - clear()           : Clear log
        - info(str)         : Info message
        - success(str)      : Success message (green)
        - warning(str)      : Warning message (orange)
        - error(str)        : Error message (red)

    action_buttons:
        - set_running(bool) : Toggle start/stop state

    preview_panel (optional):
        - set_loading()     : Show loading state
        - update_topology(dict) : Update with topology data
        - set_ready()       : Show ready state
"""

import asyncio
import json
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

from PyQt6.QtCore import QObject, pyqtSignal, QThread, Qt


# Debug flag
DEBUG = True


def debug_print(msg: str):
    """Print debug message if DEBUG is enabled."""
    if DEBUG:
        print(f"[DiscoveryController] {msg}")


class DiscoverySignalBridge(QObject):
    """
    Bridge between async discovery events and Qt signals.

    Converts DiscoveryEvent objects into Qt signals for
    thread-safe UI updates.

    IMPORTANT: Events come from a background thread. We use
    QMetaObject.invokeMethod with QueuedConnection to ensure
    all UI updates happen on the main thread.
    """

    # Signals for UI updates (emitted on main thread)
    stats_updated = pyqtSignal(dict)
    device_started = pyqtSignal(dict)
    device_complete = pyqtSignal(dict)
    device_failed = pyqtSignal(dict)
    device_excluded = pyqtSignal(dict)
    neighbor_queued = pyqtSignal(dict)
    depth_started = pyqtSignal(dict)
    depth_complete = pyqtSignal(dict)
    topology_updated = pyqtSignal(dict)
    crawl_started = pyqtSignal(dict)
    crawl_complete = pyqtSignal(dict)
    crawl_cancelled = pyqtSignal()
    log_message = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._last_stats_time = 0
        self._last_topology_time = 0
        self._throttle_ms = 250  # Minimum ms between updates

    def handle_event(self, event) -> None:
        """
        Handle discovery event from background thread.

        Called from discovery thread - we copy data and queue
        the signal emission to the main thread.

        THROTTLING: High-frequency events are throttled or skipped
        to prevent overwhelming the UI thread.
        """
        import time
        import copy

        event_type = event.event_type.value

        # SKIP very noisy events entirely - they're not useful for UI
        if event_type in ('neighbor_queued', 'device_started'):
            return  # These fire too often, provide little value

        # Throttle high-frequency events
        current_time = time.time() * 1000  # ms

        if event_type == 'stats_updated':
            if current_time - self._last_stats_time < self._throttle_ms:
                return  # Skip this update
            self._last_stats_time = current_time

        elif event_type == 'topology_updated':
            # SKIP topology updates entirely during crawl
            # Final topology is loaded from map.json after crawl completes
            return

        # Deep copy data to avoid cross-thread mutation issues
        data = copy.deepcopy(event.data) if event.data else {}

        # Map event types to signals
        signal_map = {
            'stats_updated': self.stats_updated,
            'device_started': self.device_started,
            'device_complete': self.device_complete,
            'device_failed': self.device_failed,
            'device_excluded': self.device_excluded,
            'neighbor_queued': self.neighbor_queued,
            'depth_started': self.depth_started,
            'depth_complete': self.depth_complete,
            'topology_updated': self.topology_updated,
            'crawl_started': self.crawl_started,
            'crawl_complete': self.crawl_complete,
            'crawl_cancelled': self.crawl_cancelled,
            'log_message': self.log_message,
        }

        signal = signal_map.get(event_type)
        if signal:
            # Emit signal - Qt handles thread marshaling
            if event_type == 'crawl_cancelled':
                signal.emit()
            else:
                signal.emit(data)


class DiscoveryWorker(QThread):
    """
    Background thread for running async discovery.
    """

    finished = pyqtSignal(object)  # Emits DiscoveryResult
    error = pyqtSignal(str)

    def __init__(
        self,
        vault,
        seeds: List[str],
        max_depth: int,
        domains: List[str],
        exclude_patterns: List[str],
        output_dir: Path,
        concurrency: int,
        timeout: float,
        no_dns: bool,
        verbose: bool,
        event_handler,
        parent=None
    ):
        super().__init__(parent)
        self.vault = vault
        self.seeds = seeds
        self.max_depth = max_depth
        self.domains = domains
        self.exclude_patterns = exclude_patterns
        self.output_dir = output_dir
        self.concurrency = concurrency
        self.timeout = timeout
        self.no_dns = no_dns
        self.verbose = verbose
        self.event_handler = event_handler

        self._cancel_event = None

    def run(self):
        """Run discovery in background thread."""
        # Import here to avoid circular imports
        try:
            from sc2.scng.discovery import DiscoveryEngine
            from sc2.scng.discovery.events import EventEmitter
        except ImportError:
            try:
                from scng.discovery import DiscoveryEngine
                from scng.discovery.events import EventEmitter
            except ImportError:
                self.error.emit("Could not import discovery engine")
                return

        # Create event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # Create event emitter and subscribe handler
            emitter = EventEmitter()
            emitter.subscribe(self.event_handler)

            # Create cancel event
            self._cancel_event = asyncio.Event()

            # Create engine
            engine = DiscoveryEngine(
                vault=self.vault,
                max_concurrent=self.concurrency,
                default_timeout=self.timeout,
                no_dns=self.no_dns,
                verbose=self.verbose,
                event_emitter=emitter,
            )

            # Run discovery
            result = loop.run_until_complete(
                engine.crawl(
                    seeds=self.seeds,
                    max_depth=self.max_depth,
                    domains=self.domains,
                    exclude_patterns=self.exclude_patterns,
                    output_dir=self.output_dir,
                    cancel_event=self._cancel_event,
                )
            )

            self.finished.emit(result)

        except Exception as e:
            self.error.emit(str(e))
        finally:
            loop.close()

    def cancel(self):
        """Request cancellation."""
        if self._cancel_event:
            # Need to set from the thread's event loop
            # For simplicity, just set a flag
            self._cancel_event.set()


class DiscoveryController(QObject):
    """
    Main controller for GUI-integrated discovery.

    Manages:
    - Signal bridge between engine and UI
    - Background worker thread
    - UI state updates
    - Start/stop/cancel operations
    """

    # Signals for external listeners
    discovery_started = pyqtSignal()
    discovery_finished = pyqtSignal(object)  # DiscoveryResult
    discovery_error = pyqtSignal(str)
    discovery_cancelled = pyqtSignal()

    def __init__(self, main_window, parent=None):
        super().__init__(parent)

        self.main_window = main_window
        self.vault = main_window.vault

        # Get panel references (with safe fallbacks)
        self.progress_panel = getattr(main_window, 'progress_panel', None)
        self.log_panel = getattr(main_window, 'log_panel', None)
        self.preview_panel = getattr(main_window, 'preview_panel', None)
        self.action_buttons = getattr(main_window, 'action_buttons', None)

        # Signal bridge
        self.bridge = DiscoverySignalBridge(self)
        self._connect_bridge_signals()

        # Worker thread
        self._worker: Optional[DiscoveryWorker] = None
        self._is_running = False

        # Store output directory for topology loading
        self._output_dir: Optional[Path] = None

        debug_print("DiscoveryController initialized")
        debug_print(f"  progress_panel: {self.progress_panel is not None}")
        debug_print(f"  log_panel: {self.log_panel is not None}")
        debug_print(f"  preview_panel: {self.preview_panel is not None}")
        debug_print(f"  action_buttons: {self.action_buttons is not None}")

    def _safe_call(self, obj, method_name: str, *args, **kwargs):
        """Safely call a method if it exists."""
        if obj and hasattr(obj, method_name):
            method = getattr(obj, method_name)
            if callable(method):
                try:
                    return method(*args, **kwargs)
                except Exception as e:
                    print(f"[DiscoveryController] Error calling {method_name}: {e}")
        return None

    def _connect_bridge_signals(self):
        """
        Connect bridge signals to UI update methods.

        IMPORTANT: Use Qt.QueuedConnection explicitly because these
        signals are emitted from a background thread. This ensures
        slots run on the main thread's event loop.
        """
        Q = Qt.ConnectionType.QueuedConnection

        # Stats → Progress Panel
        self.bridge.stats_updated.connect(self._on_stats_updated, Q)

        # Device events → Log Panel
        self.bridge.device_started.connect(self._on_device_started, Q)
        self.bridge.device_complete.connect(self._on_device_complete, Q)
        self.bridge.device_failed.connect(self._on_device_failed, Q)
        self.bridge.device_excluded.connect(self._on_device_excluded, Q)
        self.bridge.neighbor_queued.connect(self._on_neighbor_queued, Q)

        # Depth events
        self.bridge.depth_started.connect(self._on_depth_started, Q)

        # Topology → Preview Panel
        self.bridge.topology_updated.connect(self._on_topology_updated, Q)

        # Lifecycle
        self.bridge.crawl_started.connect(self._on_crawl_started, Q)
        self.bridge.crawl_complete.connect(self._on_crawl_complete, Q)
        self.bridge.crawl_cancelled.connect(self._on_crawl_cancelled, Q)

        # Log messages
        self.bridge.log_message.connect(self._on_log_message, Q)

    @property
    def is_running(self) -> bool:
        """Check if discovery is currently running."""
        return self._is_running

    def start_crawl(
        self,
        seeds: List[str],
        max_depth: int = 5,
        domains: Optional[List[str]] = None,
        exclude_patterns: Optional[List[str]] = None,
        output_dir: Optional[Path] = None,
        concurrency: int = 20,
        timeout: float = 5.0,
        no_dns: bool = False,
        verbose: bool = False,
    ):
        """
        Start a discovery crawl in background thread.
        """
        if self._is_running:
            self._safe_call(self.log_panel, 'warning', "Discovery already running")
            return

        # Update vault reference in case it changed
        self.vault = self.main_window.vault

        if not self.vault:
            self._safe_call(self.log_panel, 'error', "No vault available - please login first")
            return

        if not seeds:
            self._safe_call(self.log_panel, 'error', "No seed IPs provided")
            return

        # Default output directory
        if output_dir is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = Path(f"./discovery_{timestamp}")
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Store output directory for topology loading later
        self._output_dir = output_dir
        debug_print(f"Output directory: {self._output_dir}")

        # Create and start worker
        self._worker = DiscoveryWorker(
            vault=self.vault,
            seeds=seeds,
            max_depth=max_depth,
            domains=domains or [],
            exclude_patterns=exclude_patterns or [],
            output_dir=output_dir,
            concurrency=concurrency,
            timeout=timeout,
            no_dns=no_dns,
            verbose=verbose,
            event_handler=self.bridge.handle_event,
            parent=self,
        )

        self._worker.finished.connect(self._on_worker_finished)
        self._worker.error.connect(self._on_worker_error)

        self._is_running = True
        self._worker.start()

        self.discovery_started.emit()

    def cancel(self):
        """Cancel running discovery."""
        if self._worker and self._is_running:
            self._worker.cancel()
            self._safe_call(self.log_panel, 'warning', "Cancellation requested...")

    # =========================================================================
    # UI Update Handlers
    # =========================================================================

    def _on_stats_updated(self, data: Dict[str, Any]):
        """Update progress panel with stats."""
        if not self.progress_panel:
            return

        # Try set_counts first, fallback to individual setters
        if hasattr(self.progress_panel, 'set_counts'):
            self._safe_call(
                self.progress_panel, 'set_counts',
                discovered=data.get('discovered', 0),
                failed=data.get('failed', 0),
                queue=data.get('queue', 0),
                total=data.get('total', 0),
            )
        else:
            # Try individual counter methods
            self._safe_call(self.progress_panel, 'set_discovered', data.get('discovered', 0))
            self._safe_call(self.progress_panel, 'set_failed', data.get('failed', 0))
            self._safe_call(self.progress_panel, 'set_queue', data.get('queue', 0))
            self._safe_call(self.progress_panel, 'set_total', data.get('total', 0))

        # Update status
        status = data.get('status', '')
        if status:
            self._safe_call(self.progress_panel, 'set_status', status)

        # Update depth progress
        current_depth = data.get('current_depth', 0)
        max_depth = data.get('max_depth', 0)
        if max_depth > 0:
            self._safe_call(self.progress_panel, 'set_depth', current_depth, max_depth)
            progress = data.get('depth_progress', 0)
            self._safe_call(self.progress_panel, 'set_progress', int(progress * 100))

    def _on_device_started(self, data: Dict[str, Any]):
        """Handle device discovery starting."""
        # Could update status, but stats_updated already handles this
        pass

    def _on_device_complete(self, data: Dict[str, Any]):
        """Log successful device discovery."""
        hostname = data.get('hostname', 'unknown')
        method = data.get('method', 'unknown')
        neighbors = data.get('neighbor_count') or 0
        duration = data.get('duration_ms') or 0

        self._safe_call(
            self.log_panel, 'success',
            f"{hostname} via {method} ({neighbors} neighbors, {duration:.0f}ms)"
        )

    def _on_device_failed(self, data: Dict[str, Any]):
        """Log failed device discovery."""
        target = data.get('target', 'unknown')
        error = data.get('error', 'Unknown error')

        # Truncate long errors
        if len(error) > 80:
            error = error[:77] + "..."

        self._safe_call(self.log_panel, 'error', f"{target} - {error}")

    def _on_device_excluded(self, data: Dict[str, Any]):
        """Log excluded device."""
        hostname = data.get('hostname', 'unknown')
        pattern = data.get('pattern', '')

        self._safe_call(self.log_panel, 'warning', f"{hostname} excluded (matches: {pattern})")

    def _on_neighbor_queued(self, data: Dict[str, Any]):
        """Log queued neighbor (verbose only)."""
        # Skip neighbor queue logging to reduce noise
        # Uncomment if you want verbose queue logging:
        # target = data.get('target', 'unknown')
        # self._safe_call(self.log_panel, 'info', f"  → Queued: {target}")
        pass

    def _on_depth_started(self, data: Dict[str, Any]):
        """Handle new depth level starting."""
        depth = data.get('depth', 0)
        max_depth = data.get('max_depth', 0)
        device_count = data.get('device_count', 0)

        self._safe_call(self.log_panel, 'info', "")  # Blank line
        self._safe_call(
            self.log_panel, 'info',
            f"═══ Depth {depth}/{max_depth}: {device_count} devices ═══"
        )
        self._safe_call(self.progress_panel, 'set_depth', depth, max_depth)

    def _on_topology_updated(self, data: Dict[str, Any]):
        """
        Topology update during crawl - IGNORED.

        We don't update the webview during crawl to avoid UI freezes.
        Final topology is loaded from map.json after crawl completes.
        """
        # Do nothing - webview stays untouched during crawl
        pass

    def _on_crawl_started(self, data: Dict[str, Any]):
        """Handle crawl start."""
        seeds = data.get('seeds', [])
        max_depth = data.get('max_depth', 0)
        domains = data.get('domains', [])
        exclude_patterns = data.get('exclude_patterns', [])
        no_dns = data.get('no_dns', False)
        concurrency = data.get('concurrency', 20)
        timeout = data.get('timeout', 5)

        # Clear and setup UI - but DON'T touch the webview
        self._safe_call(self.log_panel, 'clear')
        self._safe_call(self.progress_panel, 'reset')
        self._safe_call(self.progress_panel, 'set_running')
        self._safe_call(self.action_buttons, 'set_running', True)

        # Just update status label, don't call set_loading() which touches webview
        # self._safe_call(self.preview_panel, 'set_loading')  # DISABLED

        # Build equivalent CLI command for debugging
        cli_parts = ["python -m sc2.scng.discovery crawl"]
        cli_parts.append(" ".join(seeds))
        cli_parts.append(f"-d {max_depth}")
        if domains:
            for d in domains:
                cli_parts.append(f"--domain {d}")
        if exclude_patterns:
            for p in exclude_patterns:
                cli_parts.append(f"--exclude '{p}'")
        if no_dns:
            cli_parts.append("--no-dns")
        cli_parts.append(f"-c {concurrency}")
        cli_parts.append(f"-t {timeout}")

        cli_command = " ".join(cli_parts)

        # Log start info
        self._safe_call(self.log_panel, 'info', f"Starting discovery from {len(seeds)} seed(s)")
        self._safe_call(self.log_panel, 'info', f"Max depth: {max_depth}")
        if domains:
            self._safe_call(self.log_panel, 'info', f"Domains: {', '.join(domains)}")
        if no_dns:
            self._safe_call(self.log_panel, 'info', "No-DNS mode enabled")
        self._safe_call(self.log_panel, 'debug', f"CLI: {cli_command}")

    def _on_crawl_complete(self, data: Dict[str, Any]):
        """Handle crawl completion."""
        discovered = data.get('discovered') or 0
        failed = data.get('failed') or 0
        duration = data.get('duration_seconds') or 0

        self._safe_call(self.log_panel, 'info', "")
        self._safe_call(self.log_panel, 'info', "═══════════════════════════════════════")
        self._safe_call(self.log_panel, 'success', "Discovery complete!")
        self._safe_call(self.log_panel, 'info', f"  Discovered: {discovered}")
        self._safe_call(self.log_panel, 'info', f"  Failed: {failed}")
        self._safe_call(self.log_panel, 'info', f"  Duration: {duration:.1f}s")

        # Load topology from map.json and update preview
        debug_print("=" * 50)
        debug_print("Crawl complete - loading topology from map.json")
        debug_print("=" * 50)
        self._load_topology_to_preview()

    def _load_topology_to_preview(self):
        """Load the saved topology file into the preview panel."""
        debug_print(f"_load_topology_to_preview called")
        debug_print(f"  preview_panel: {self.preview_panel is not None}")
        debug_print(f"  output_dir: {self._output_dir}")

        if not self.preview_panel:
            debug_print("  ERROR: No preview_panel available!")
            return

        if not self._output_dir:
            debug_print("  ERROR: No output_dir set!")
            self._safe_call(self.log_panel, 'warning', "No output directory - cannot load topology")
            return

        map_file = self._output_dir / "map.json"
        debug_print(f"  Looking for map file: {map_file}")
        debug_print(f"  File exists: {map_file.exists()}")

        if map_file.exists():
            try:
                with open(map_file, 'r') as f:
                    topology = json.load(f)

                debug_print(f"  Loaded topology with {len(topology)} devices")

                # Log first few devices for debugging
                for i, (name, data) in enumerate(list(topology.items())[:3]):
                    details = data.get('node_details', {})
                    peers = list(data.get('peers', {}).keys())
                    debug_print(f"    Device {i+1}: {name} ({details.get('platform', '?')}) -> {peers[:3]}")

                self._safe_call(self.log_panel, 'info', f"  Loading topology: {len(topology)} devices")

                # Call update_topology on preview panel
                debug_print("  Calling preview_panel.update_topology()...")
                result = self._safe_call(self.preview_panel, 'update_topology', topology)
                debug_print(f"  update_topology returned: {result}")

            except json.JSONDecodeError as e:
                debug_print(f"  ERROR: JSON decode error: {e}")
                self._safe_call(self.log_panel, 'error', f"  Failed to parse topology: {e}")
            except Exception as e:
                debug_print(f"  ERROR: Exception: {e}")
                self._safe_call(self.log_panel, 'error', f"  Failed to load topology: {e}")
        else:
            debug_print(f"  WARNING: map.json not found!")
            self._safe_call(self.log_panel, 'warning', f"  No map.json found at {map_file}")

    def _on_crawl_cancelled(self):
        """Handle crawl cancellation."""
        self._safe_call(self.log_panel, 'warning', "Discovery cancelled")
        self._cleanup_after_discovery()
        self.discovery_cancelled.emit()

    def _on_log_message(self, data: Dict[str, Any]):
        """Handle generic log message."""
        message = data.get('message', '')
        level = data.get('level', 'info')

        method_map = {
            'error': 'error',
            'warning': 'warning',
            'success': 'success',
            'debug': 'debug',
            'info': 'info',
        }
        method = method_map.get(level, 'info')
        self._safe_call(self.log_panel, method, message)

    def _on_worker_finished(self, result):
        """Handle worker thread completion."""
        debug_print("Worker finished")
        self._cleanup_after_discovery()
        self.discovery_finished.emit(result)

    def _on_worker_error(self, error_msg: str):
        """Handle worker thread error."""
        debug_print(f"Worker error: {error_msg}")
        self._safe_call(self.log_panel, 'error', f"Discovery error: {error_msg}")
        self._cleanup_after_discovery()
        self.discovery_error.emit(error_msg)

    def _cleanup_after_discovery(self):
        """Reset UI state after discovery ends."""
        debug_print("Cleanup after discovery")
        self._is_running = False
        self._safe_call(self.action_buttons, 'set_running', False)
        self._safe_call(self.progress_panel, 'set_idle')
        self._safe_call(self.preview_panel, 'set_ready')
        self._worker = None