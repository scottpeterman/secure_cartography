"""
SecureCartography NG - Discovery Event System.

Structured events for GUI integration. The discovery engine emits these
events which can be consumed by CLI (print) or GUI (update widgets).

Event Flow:
    crawl_started -> depth_started -> device_queued* -> device_started ->
    device_complete/device_failed -> neighbor_queued* -> depth_complete ->
    ... -> crawl_complete

GUI Panel Mapping:
    - PROGRESS panel: stats_updated (discovered, failed, queue, total)
    - Status line: device_started, depth_started
    - Depth bar: depth_started, depth_complete (depth, max_depth, percentage)
    - DISCOVERY LOG: log_message (timestamped entries)
    - TOPOLOGY PREVIEW: topology_updated (incremental map data)
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Protocol


class EventType(str, Enum):
    """Discovery event types."""
    # Crawl lifecycle
    CRAWL_STARTED = "crawl_started"
    CRAWL_COMPLETE = "crawl_complete"
    CRAWL_CANCELLED = "crawl_cancelled"

    # Depth progression
    DEPTH_STARTED = "depth_started"
    DEPTH_COMPLETE = "depth_complete"

    # Device discovery
    DEVICE_QUEUED = "device_queued"
    DEVICE_STARTED = "device_started"
    DEVICE_COMPLETE = "device_complete"
    DEVICE_FAILED = "device_failed"
    DEVICE_EXCLUDED = "device_excluded"

    # Neighbor processing
    NEIGHBOR_QUEUED = "neighbor_queued"
    NEIGHBOR_SKIPPED = "neighbor_skipped"

    # Aggregated updates (for efficient GUI updates)
    STATS_UPDATED = "stats_updated"
    TOPOLOGY_UPDATED = "topology_updated"

    # Log messages (for Discovery Log panel)
    LOG_MESSAGE = "log_message"


class LogLevel(str, Enum):
    """Log message severity levels."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    SUCCESS = "success"


@dataclass
class DiscoveryStats:
    """Current discovery statistics for PROGRESS panel."""
    discovered: int = 0
    failed: int = 0
    queue: int = 0
    total: int = 0
    excluded: int = 0
    skipped: int = 0

    current_depth: int = 0
    max_depth: int = 0
    depth_progress: float = 0.0  # 0.0 to 1.0

    current_device: str = ""
    status: str = "Ready"

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.total == 0:
            return 0.0
        return (self.discovered / self.total) * 100


@dataclass
class DiscoveryEvent:
    """
    Base event emitted by the discovery engine.

    All events have a type, timestamp, and event-specific data.
    GUI handlers can switch on event_type to update appropriate panels.
    """
    event_type: EventType
    timestamp: datetime = field(default_factory=datetime.now)
    data: Dict[str, Any] = field(default_factory=dict)

    # Convenience accessors for common event data
    @property
    def message(self) -> str:
        """Get log message if present."""
        return self.data.get("message", "")

    @property
    def target(self) -> str:
        """Get target device if present."""
        return self.data.get("target", "")

    @property
    def depth(self) -> int:
        """Get current depth if present."""
        return self.data.get("depth", 0)


# Type alias for event callback
EventCallback = Callable[[DiscoveryEvent], None]


class EventEmitter:
    """
    Event emitter for discovery engine.

    Manages event subscriptions and dispatching.
    Supports multiple listeners for GUI + logging.

    Usage:
        emitter = EventEmitter()

        # Subscribe to all events
        emitter.subscribe(my_handler)

        # Subscribe to specific event types
        emitter.subscribe(stats_handler, EventType.STATS_UPDATED)

        # Emit events
        emitter.emit(EventType.DEVICE_COMPLETE, device=device_obj)
    """

    def __init__(self):
        self._listeners: List[tuple[EventCallback, Optional[EventType]]] = []
        self._stats = DiscoveryStats()

    @property
    def stats(self) -> DiscoveryStats:
        """Get current statistics."""
        return self._stats

    def reset_stats(self) -> None:
        """Reset statistics for new crawl."""
        self._stats = DiscoveryStats()

    def subscribe(
        self,
        callback: EventCallback,
        event_type: Optional[EventType] = None
    ) -> None:
        """
        Subscribe to events.

        Args:
            callback: Function to call with DiscoveryEvent
            event_type: If specified, only receive this event type
        """
        self._listeners.append((callback, event_type))

    def unsubscribe(self, callback: EventCallback) -> None:
        """Remove a callback from listeners."""
        self._listeners = [
            (cb, et) for cb, et in self._listeners if cb != callback
        ]

    def clear(self) -> None:
        """Remove all listeners."""
        self._listeners.clear()

    def emit(self, event_type: EventType, **data) -> DiscoveryEvent:
        """
        Emit an event to all subscribed listeners.

        Args:
            event_type: Type of event
            **data: Event-specific data

        Returns:
            The emitted event
        """
        event = DiscoveryEvent(
            event_type=event_type,
            timestamp=datetime.now(),
            data=data
        )

        for callback, filter_type in self._listeners:
            if filter_type is None or filter_type == event_type:
                try:
                    callback(event)
                except Exception as e:
                    # Don't let listener errors break discovery
                    print(f"Event listener error: {e}")

        return event

    # =========================================================================
    # Convenience methods for common events
    # =========================================================================

    def crawl_started(
        self,
        seeds: List[str],
        max_depth: int,
        domains: List[str],
        exclude_patterns: List[str],
        no_dns: bool = False,
        concurrency: int = 20,
        timeout: float = 5.0,
    ) -> None:
        """Emit crawl started event and reset stats."""
        self.reset_stats()
        self._stats.max_depth = max_depth
        self._stats.queue = len(seeds)
        self._stats.status = "Starting"

        self.emit(
            EventType.CRAWL_STARTED,
            seeds=seeds,
            max_depth=max_depth,
            domains=domains,
            exclude_patterns=exclude_patterns,
            no_dns=no_dns,
            concurrency=concurrency,
            timeout=timeout,
            total_seeds=len(seeds),
        )
        self._emit_stats_update()

    def crawl_complete(
        self,
        duration_seconds: float,
        topology: Optional[Dict] = None,
    ) -> None:
        """Emit crawl complete event."""
        self._stats.status = "Complete"
        self._stats.queue = 0
        self._stats.depth_progress = 1.0

        self.emit(
            EventType.CRAWL_COMPLETE,
            discovered=self._stats.discovered,
            failed=self._stats.failed,
            total=self._stats.total,
            excluded=self._stats.excluded,
            duration_seconds=duration_seconds,
            topology=topology,
        )
        self._emit_stats_update()

    def crawl_cancelled(self) -> None:
        """Emit crawl cancelled event."""
        self._stats.status = "Cancelled"
        self.emit(EventType.CRAWL_CANCELLED)
        self._emit_stats_update()

    def depth_started(self, depth: int, device_count: int) -> None:
        """Emit depth started event."""
        self._stats.current_depth = depth
        self._stats.status = f"Depth {depth}"

        # Calculate progress (simple linear by depth)
        if self._stats.max_depth > 0:
            self._stats.depth_progress = depth / self._stats.max_depth
        else:
            self._stats.depth_progress = 0.0

        self.emit(
            EventType.DEPTH_STARTED,
            depth=depth,
            max_depth=self._stats.max_depth,
            device_count=device_count,
        )
        self._emit_stats_update()

    def depth_complete(self, depth: int, discovered: int, failed: int) -> None:
        """Emit depth complete event."""
        self.emit(
            EventType.DEPTH_COMPLETE,
            depth=depth,
            discovered=discovered,
            failed=failed,
        )

    def device_queued(self, target: str, depth: int, source: str = "") -> None:
        """Emit device queued event (initial seeds or neighbor)."""
        self._stats.queue += 1

        self.emit(
            EventType.DEVICE_QUEUED,
            target=target,
            depth=depth,
            source=source,
        )
        # Don't emit stats for every queue - too noisy

    def device_started(self, target: str, depth: int) -> None:
        """Emit device discovery started event."""
        self._stats.current_device = target
        self._stats.status = f"Discovering: {target}"

        self.emit(
            EventType.DEVICE_STARTED,
            target=target,
            depth=depth,
        )
        self._emit_stats_update()

    def device_complete(
        self,
        target: str,
        hostname: str,
        ip: str,
        vendor: str,
        neighbor_count: int,
        duration_ms: float,
        method: str,
        depth: int,
    ) -> None:
        """Emit device discovery complete event."""
        self._stats.discovered += 1
        self._stats.total += 1
        self._stats.queue = max(0, self._stats.queue - 1)

        self.emit(
            EventType.DEVICE_COMPLETE,
            target=target,
            hostname=hostname,
            ip=ip,
            vendor=vendor,
            neighbor_count=neighbor_count,
            duration_ms=duration_ms,
            method=method,
            depth=depth,
        )
        self._emit_stats_update()

    def device_failed(
        self,
        target: str,
        error: str,
        depth: int,
    ) -> None:
        """Emit device discovery failed event."""
        self._stats.failed += 1
        self._stats.total += 1
        self._stats.queue = max(0, self._stats.queue - 1)

        self.emit(
            EventType.DEVICE_FAILED,
            target=target,
            error=error,
            depth=depth,
        )
        self._emit_stats_update()

    def device_excluded(self, hostname: str, pattern: str) -> None:
        """Emit device excluded event."""
        self._stats.excluded += 1

        self.emit(
            EventType.DEVICE_EXCLUDED,
            hostname=hostname,
            pattern=pattern,
        )
        self._emit_stats_update()

    def neighbor_queued(
        self,
        target: str,
        ip: Optional[str],
        from_device: str,
        depth: int,
    ) -> None:
        """Emit neighbor queued for discovery."""
        self._stats.queue += 1

        self.emit(
            EventType.NEIGHBOR_QUEUED,
            target=target,
            ip=ip,
            from_device=from_device,
            depth=depth,
        )
        # Emit stats update for queue change
        self._emit_stats_update()

    def neighbor_skipped(
        self,
        target: str,
        reason: str,
        from_device: str,
    ) -> None:
        """Emit neighbor skipped (already discovered, MAC address, etc.)."""
        self._stats.skipped += 1

        self.emit(
            EventType.NEIGHBOR_SKIPPED,
            target=target,
            reason=reason,
            from_device=from_device,
        )

    def topology_updated(self, topology: Dict) -> None:
        """Emit topology update for preview panel."""
        self.emit(
            EventType.TOPOLOGY_UPDATED,
            topology=topology,
            device_count=len(topology),
        )

    def log(
        self,
        message: str,
        level: LogLevel = LogLevel.INFO,
        device: str = "",
    ) -> None:
        """Emit log message for Discovery Log panel."""
        self.emit(
            EventType.LOG_MESSAGE,
            message=message,
            level=level.value,
            device=device,
        )

    def _emit_stats_update(self) -> None:
        """Emit aggregated stats update."""
        self.emit(
            EventType.STATS_UPDATED,
            discovered=self._stats.discovered,
            failed=self._stats.failed,
            queue=self._stats.queue,
            total=self._stats.total,
            excluded=self._stats.excluded,
            skipped=self._stats.skipped,
            current_depth=self._stats.current_depth,
            max_depth=self._stats.max_depth,
            depth_progress=self._stats.depth_progress,
            current_device=self._stats.current_device,
            status=self._stats.status,
        )


# =========================================================================
# Console Event Printer (for CLI)
# =========================================================================

class ConsoleEventPrinter:
    """
    Prints discovery events to console in a formatted way.

    Maintains CLI backward compatibility while using the new event system.
    Supports color output and different verbosity levels.

    Usage:
        printer = ConsoleEventPrinter(verbose=True, color=True)
        emitter.subscribe(printer.handle_event)
    """

    # ANSI color codes
    COLORS = {
        "reset": "\033[0m",
        "bold": "\033[1m",
        "dim": "\033[2m",
        "red": "\033[31m",
        "green": "\033[32m",
        "yellow": "\033[33m",
        "blue": "\033[34m",
        "magenta": "\033[35m",
        "cyan": "\033[36m",
        "white": "\033[37m",
    }

    def __init__(
        self,
        verbose: bool = False,
        color: bool = True,
        show_timestamps: bool = False,
    ):
        self.verbose = verbose
        self.color = color
        self.show_timestamps = show_timestamps

    def _c(self, text: str, *colors: str) -> str:
        """Apply colors if enabled."""
        if not self.color:
            return text
        codes = "".join(self.COLORS.get(c, "") for c in colors)
        return f"{codes}{text}{self.COLORS['reset']}"

    def _timestamp(self, event: DiscoveryEvent) -> str:
        """Format timestamp if enabled."""
        if not self.show_timestamps:
            return ""
        return f"[{event.timestamp.strftime('%H:%M:%S')}] "

    def handle_event(self, event: DiscoveryEvent) -> None:
        """Handle and print a discovery event."""
        handler = getattr(self, f"_handle_{event.event_type.value}", None)
        if handler:
            handler(event)
        elif self.verbose:
            # Print unknown events in verbose mode
            print(f"{self._timestamp(event)}[{event.event_type.value}] {event.data}")

    def _handle_crawl_started(self, event: DiscoveryEvent) -> None:
        """Print crawl started banner."""
        data = event.data
        print()
        print(self._c("=" * 60, "cyan", "bold"))
        print(self._c("NETWORK DISCOVERY STARTED", "cyan", "bold"))
        print(self._c("=" * 60, "cyan", "bold"))
        print(f"Seeds: {', '.join(data['seeds'])}")
        print(f"Max Depth: {data['max_depth']}")
        if data.get('domains'):
            print(f"Domains: {', '.join(data['domains'])}")
        if data.get('exclude_patterns'):
            print(f"Exclude: {', '.join(data['exclude_patterns'])}")
        print()

    def _handle_crawl_complete(self, event: DiscoveryEvent) -> None:
        """Print crawl complete summary."""
        data = event.data
        print()
        print(self._c("#" * 60, "green", "bold"))
        print(self._c("DISCOVERY COMPLETE", "green", "bold"))
        print(self._c("#" * 60, "green", "bold"))
        print(f"Total Attempted: {data['total']}")
        print(f"Successful: {self._c(str(data['discovered']), 'green')}")
        print(f"Failed: {self._c(str(data['failed']), 'red')}")
        if data.get('excluded', 0) > 0:
            print(f"Excluded: {data['excluded']}")
        print(f"Duration: {data['duration_seconds']:.1f}s")
        print()

    def _handle_crawl_cancelled(self, event: DiscoveryEvent) -> None:
        """Print cancellation notice."""
        print()
        print(self._c("Discovery cancelled by user", "yellow", "bold"))
        print()

    def _handle_depth_started(self, event: DiscoveryEvent) -> None:
        """Print depth level header."""
        data = event.data
        print()
        print(self._c("=" * 60, "blue"))
        print(self._c(
            f"DEPTH {data['depth']}/{data['max_depth']}: "
            f"Processing {data['device_count']} devices",
            "blue", "bold"
        ))
        print(self._c("=" * 60, "blue"))

    def _handle_depth_complete(self, event: DiscoveryEvent) -> None:
        """Print depth completion (verbose only)."""
        if self.verbose:
            data = event.data
            print(f"  Depth {data['depth']} complete: "
                  f"{data['discovered']} discovered, {data['failed']} failed")

    def _handle_device_started(self, event: DiscoveryEvent) -> None:
        """Print device discovery start (verbose only)."""
        if self.verbose:
            data = event.data
            print(f"{self._timestamp(event)}  Discovering: {data['target']}")

    def _handle_device_complete(self, event: DiscoveryEvent) -> None:
        """Print successful device discovery."""
        data = event.data
        method = data.get('method', 'unknown')
        neighbors = data.get('neighbor_count', 0)
        duration = data.get('duration_ms', 0)

        status = self._c("OK", "green", "bold")
        detail = f"via {method} ({neighbors} neighbors, {duration:.0f}ms)"

        print(f"{self._timestamp(event)}  {status}: {data['hostname']} {detail}")

    def _handle_device_failed(self, event: DiscoveryEvent) -> None:
        """Print failed device discovery."""
        data = event.data
        status = self._c("FAILED", "red", "bold")
        error = data.get('error', 'Unknown error')

        # Truncate long errors
        if len(error) > 60:
            error = error[:57] + "..."

        print(f"{self._timestamp(event)}  {status}: {data['target']} - {error}")

    def _handle_device_excluded(self, event: DiscoveryEvent) -> None:
        """Print excluded device."""
        data = event.data
        status = self._c("EXCLUDED", "yellow")
        print(f"{self._timestamp(event)}  {status}: {data['hostname']} "
              f"(matches: {data['pattern']})")

    def _handle_neighbor_queued(self, event: DiscoveryEvent) -> None:
        """Print queued neighbor."""
        data = event.data
        target = data['target']
        ip = data.get('ip')

        ip_str = f" ({ip})" if ip and ip != target else ""
        print(f"{self._timestamp(event)}  {self._c('QUEUED', 'cyan')}: "
              f"{target}{ip_str}")

    def _handle_neighbor_skipped(self, event: DiscoveryEvent) -> None:
        """Print skipped neighbor (verbose only)."""
        if self.verbose:
            data = event.data
            print(f"{self._timestamp(event)}  SKIPPED: {data['target']} "
                  f"({data['reason']})")

    def _handle_log_message(self, event: DiscoveryEvent) -> None:
        """Print log message."""
        data = event.data
        level = data.get('level', 'info')
        message = data.get('message', '')

        # Color by level
        level_colors = {
            'debug': ('dim',),
            'info': (),
            'warning': ('yellow',),
            'error': ('red',),
            'success': ('green',),
        }
        colors = level_colors.get(level, ())

        prefix = f"[{level.upper()}]" if self.verbose else ""
        print(f"{self._timestamp(event)}{prefix} {self._c(message, *colors)}")

    def _handle_stats_updated(self, event: DiscoveryEvent) -> None:
        """Stats updates are silent in CLI (visual in GUI)."""
        pass

    def _handle_topology_updated(self, event: DiscoveryEvent) -> None:
        """Topology updates are silent in CLI (visual in GUI)."""
        pass