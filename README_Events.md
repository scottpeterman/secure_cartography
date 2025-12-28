# Secure Cartography v2 - Event System Update

## Overview

This update adds a structured event system to the discovery engine that enables real-time GUI updates. The engine now emits granular events that map directly to your UI panels.

## Files

| File | Description |
|------|-------------|
| `events.py` | Event types, EventEmitter, ConsoleEventPrinter |
| `engine.py` | Updated engine with event emission |
| `cli.py` | Updated CLI using event system |
| `gui_integration.py` | PyQt6 integration example with signal bridge |

## Event → UI Panel Mapping

```
┌─────────────────────────────────────────────────────────────┐
│  PROGRESS PANEL                                             │
│  ┌──────────┬──────────┬──────────┬──────────┐             │
│  │ DISCOVERED│  FAILED  │  QUEUE   │  TOTAL   │  ◄── STATS_UPDATED
│  │    15    │    2     │    8     │    25    │             │
│  └──────────┴──────────┴──────────┴──────────┘             │
│  Discovering: core-switch-01                ◄── STATS_UPDATED
│  Depth 2 of 5 ████████░░░░░░░░░░ 40%       ◄── STATS_UPDATED
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  DISCOVERY LOG                                              │
│  [14:32:05] ✓ core-switch-01 via snmp (5 neighbors)  ◄── DEVICE_COMPLETE
│  [14:32:08] ✗ 192.168.1.99 - SNMP timeout           ◄── DEVICE_FAILED  
│  [14:32:10] → Queued: dist-switch-01 (192.168.1.2)  ◄── NEIGHBOR_QUEUED
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  TOPOLOGY PREVIEW                                           │
│                    [core-sw]                                │
│                    /       \                   ◄── TOPOLOGY_UPDATED
│              [dist-1]    [dist-2]                           │
└─────────────────────────────────────────────────────────────┘
```

## Event Types

| Event | Frequency | Use For |
|-------|-----------|---------|
| `STATS_UPDATED` | ~Every action | All counters, status, progress bar |
| `DEVICE_COMPLETE` | Per device | Log success entries |
| `DEVICE_FAILED` | Per device | Log failure entries |
| `DEVICE_STARTED` | Per device | "Discovering: X" status |
| `NEIGHBOR_QUEUED` | Per neighbor | Log queued entries, queue counter |
| `DEPTH_STARTED` | Per depth | Depth progress indicator |
| `TOPOLOGY_UPDATED` | End of crawl | Preview panel refresh |
| `CRAWL_STARTED` | Once | Reset UI, show config |
| `CRAWL_COMPLETE` | Once | Final summary |

## CLI Usage

```bash
# Standard console output (uses ConsoleEventPrinter)
python -m scng.discovery crawl 192.168.1.1 -d 3

# Verbose with timestamps
python -m scng.discovery crawl 192.168.1.1 -v --timestamps

# JSON events for GUI subprocess integration
python -m scng.discovery crawl 192.168.1.1 --json-events

# Disable colors (for logging)
python -m scng.discovery crawl 192.168.1.1 --no-color
```

## GUI Integration Pattern

```python
from scng.discovery import DiscoveryEngine
from scng.discovery.events import EventEmitter
from scng.discovery.gui_integration import DiscoverySignalBridge

# Create bridge and connect to widgets
bridge = DiscoverySignalBridge()
bridge.stats_updated.connect(progress_panel.update_stats)
bridge.device_complete.connect(discovery_log.add_success)
bridge.device_failed.connect(discovery_log.add_failure)
bridge.neighbor_queued.connect(discovery_log.add_queued)
bridge.topology_updated.connect(topology_preview.update_map)

# Create engine with event system
emitter = EventEmitter()
emitter.subscribe(bridge.handle_event)

engine = DiscoveryEngine(
    vault=vault,
    event_emitter=emitter,
)

# Run crawl (events automatically flow to UI)
result = await engine.crawl(seeds=["192.168.1.1"], max_depth=3)
```

## STATS_UPDATED Data Structure

This is the most important event - it contains everything your PROGRESS panel needs:

```python
{
    "discovered": 15,           # ◄── DISCOVERED box
    "failed": 2,                # ◄── FAILED box  
    "queue": 8,                 # ◄── QUEUE box
    "total": 17,                # ◄── TOTAL box
    "excluded": 1,              # (optional display)
    "skipped": 3,               # (optional display)
    "current_depth": 2,         # ◄── "Depth X of Y"
    "max_depth": 5,             # ◄── "Depth X of Y"
    "depth_progress": 0.4,      # ◄── Progress bar (0.0-1.0)
    "current_device": "sw-01",  # ◄── Status line
    "status": "Discovering: sw-01"  # ◄── Status line
}
```

## Backward Compatibility

- Legacy `progress_callback` parameter still works
- CLI behavior is unchanged (just prettier output)
- All existing engine methods preserved
- `discover` command renamed to `device` for clarity

## Key Changes from Original

1. **Engine emits events instead of print()** - All status messages go through the event system
2. **ConsoleEventPrinter** - Formats events for terminal (replaces inline prints)
3. **JsonEventPrinter** - Outputs JSON lines for subprocess GUI communication
4. **DiscoverySignalBridge** - Converts events to Qt signals for thread-safe UI updates
5. **DiscoveryStats** - Maintains running totals, exposed via `engine.events.stats`

## Thread Safety

The event system is designed for async/threading:
- Events are emitted from discovery coroutines
- `DiscoverySignalBridge` converts to Qt signals (thread-safe)
- UI updates happen on Qt main thread via signal/slot

---

*Built for Secure Cartography v2 - PyQt6 GUI Integration*