# SCNG Discovery Engine - GUI Progress Events

This document describes the progress events emitted by `DiscoveryEngine.crawl()` for GUI integration.

## Overview

The engine emits `ProgressState` objects via the `progress_callback` parameter. Each state includes:
- An `event` type indicating what just happened
- Current counts (discovered, failed, skipped, excluded, queued)
- Depth tracking info
- Details about the last device processed
- Elapsed time

```python
async def crawl(
    self,
    seeds: List[str],
    max_depth: int = 3,
    progress_callback: Optional[ProgressCallback] = None,  # <-- GUI hooks here
    ...
) -> DiscoveryResult:
```

---

## Event Types

### `CRAWL_STARTED`

**When:** Immediately after `crawl()` begins, before any discovery.

**Use:** Initialize GUI, display configuration summary in log.

**Key Fields:**
| Field | Description |
|-------|-------------|
| `seeds` | List of seed IPs/hostnames |
| `max_depth` | Maximum crawl depth |
| `concurrency` | Number of parallel workers |
| `no_dns` | Whether DNS lookups are disabled |
| `domains` | Domain suffixes for resolution |
| `exclude_patterns` | sysDescr patterns being skipped |
| `started_at` | Crawl start timestamp |

**Example Log Output:**
```
[14:23:01] Starting crawl from 2 seeds
[14:23:01] Depth: 3 | Concurrency: 20 | No-DNS: false
```

---

### `DEPTH_STARTED`

**When:** At the beginning of each depth level, before devices at that depth are discovered.

**Use:** Update depth indicator, show how many devices will be processed.

**Key Fields:**
| Field | Description |
|-------|-------------|
| `current_depth` | Depth level starting (0, 1, 2, ...) |
| `max_depth` | Maximum depth for progress calculation |
| `devices_at_depth` | Number of devices queued at this depth |
| `queued` | Same as `devices_at_depth` at this point |

**Example Log Output:**
```
[14:23:05] Starting depth 1/3 (12 devices)
```

---

### `DEVICE_COMPLETED`

**When:** After a device is successfully discovered.

**Use:** Increment discovered counter, add success entry to log, update "currently discovering" display.

**Key Fields:**
| Field | Description |
|-------|-------------|
| `discovered` | Updated total discovered count |
| `last_device_hostname` | Device hostname (e.g., "core-switch-01") |
| `last_device_ip` | Device IP address |
| `last_device_vendor` | Vendor string ("cisco", "arista", etc.) |
| `last_device_duration_ms` | Discovery time in milliseconds |
| `last_device_cdp_count` | Number of CDP neighbors found |
| `last_device_lldp_count` | Number of LLDP neighbors found |
| `last_device_method` | Discovery method ("snmp" or "ssh") |
| `queued` | Current queue size (may increase as neighbors are found) |

**Example Log Output:**
```
[14:23:02] ✓ core-switch-01 (cisco) - 847ms
[14:23:02]   └─ CDP: 4, LLDP: 2
```

---

### `DEVICE_FAILED`

**When:** After a device discovery fails (timeout, auth failure, unreachable, etc.).

**Use:** Increment failed counter, add warning/error entry to log.

**Key Fields:**
| Field | Description |
|-------|-------------|
| `failed` | Updated total failed count |
| `current_target` | IP/hostname that failed |
| `last_device_error` | Error message describing failure |

**Example Log Output:**
```
[14:23:04] ⚠ 192.168.1.50 - Timeout (5s)
[14:23:04] ✗ 10.0.0.99 - No working SNMP or SSH credential found
```

---

### `DEVICE_SKIPPED`

**When:** After a device is skipped due to exclusion pattern match.

**Use:** Increment excluded counter, optionally log skip reason.

**Key Fields:**
| Field | Description |
|-------|-------------|
| `excluded` | Updated total excluded count |
| `current_target` | Device hostname that was excluded |
| `last_device_error` | "Matched exclusion pattern" |

**Example Log Output:**
```
[14:23:03] ○ phone-controller-01 - skipped (excluded)
```

---

### `DEVICE_QUEUED`

**When:** After a neighbor is added to the discovery queue for the next depth.

**Use:** Update queue counter in real-time as neighbors are discovered.

**Key Fields:**
| Field | Description |
|-------|-------------|
| `queued` | **Updated queue size** - this is the key field |
| `current_target` | Neighbor hostname/IP that was queued |
| `current_depth` | Current depth (neighbor will be at `current_depth + 1`) |

**Example Log Output (verbose mode):**
```
[14:23:02] + Queued: dist-switch-01 (depth 1)
```

> **Note:** This event fires frequently during discovery. Consider batching GUI updates or only updating the queue counter without adding log entries.

---

### `DEPTH_COMPLETED`

**When:** After all devices at a depth level have been processed.

**Use:** Update depth progress, log depth summary.

**Key Fields:**
| Field | Description |
|-------|-------------|
| `current_depth` | Depth level that just completed |
| `discovered` | Total discovered so far |
| `failed` | Total failed so far |
| `queued` | Devices queued for next depth |
| `devices_at_depth` | How many were attempted at this depth |

**Example Log Output:**
```
[14:23:05] Depth 2 complete: 24 devices, 8 queued
```

---

### `CRAWL_COMPLETED`

**When:** After crawl finishes successfully (all depths processed).

**Use:** Show completion message, final stats, enable "View Results" button.

**Key Fields:**
| Field | Description |
|-------|-------------|
| `discovered` | Final discovered count |
| `failed` | Final failed count |
| `skipped` | Final skipped count |
| `excluded` | Final excluded count |
| `queued` | Always 0 at completion |
| `elapsed_seconds` | Total crawl duration |
| `progress_percent` | 100 (or close to it) |

**Example Log Output:**
```
[14:25:30] ✓ Crawl complete: 47 discovered, 3 failed (149.2s)
```

---

### `CRAWL_FAILED`

**When:** Crawl is cancelled or encounters a fatal error.

**Use:** Show error state, partial results may be available.

**Key Fields:**
| Field | Description |
|-------|-------------|
| `last_device_error` | Error/cancellation message |
| `discovered` | Partial discovered count |
| `failed` | Partial failed count |
| `elapsed_seconds` | Time before failure |

**Example Log Output:**
```
[14:24:15] ✗ Crawl cancelled by user
```

---

## GUI Widget Mapping

| GUI Element | ProgressState Field(s) | Update On Events |
|-------------|------------------------|------------------|
| **DISCOVERED** counter | `state.discovered` | DEVICE_COMPLETED |
| **FAILED** counter | `state.failed` | DEVICE_FAILED |
| **QUEUE** counter | `state.queued` | DEVICE_QUEUED, DEPTH_STARTED, DEPTH_COMPLETED |
| **TOTAL** counter | `state.total` (property) | Any count change |
| **Depth indicator** | `state.current_depth` / `state.max_depth` | DEPTH_STARTED, DEPTH_COMPLETED |
| **Progress bar** | `state.progress_percent` (property) | DEPTH_STARTED, DEPTH_COMPLETED |
| **"Discovering: ..."** | `state.current_target` | DEVICE_STARTED*, DEVICE_QUEUED |
| **Log panel** | Various `last_device_*` fields | All events |

> *Note: `DEVICE_STARTED` is defined but not currently emitted. If you need a "currently discovering" indicator, use the last `DEVICE_QUEUED` target or track which devices are in-flight.

---

## PyQt6 Integration Example

```python
from PyQt6.QtCore import QThread, pyqtSignal
from scng.discovery import DiscoveryEngine, ProgressState, ProgressEventType

class DiscoveryWorker(QThread):
    progress = pyqtSignal(object)  # Emits ProgressState
    finished = pyqtSignal(object)  # Emits DiscoveryResult
    
    def __init__(self, config):
        super().__init__()
        self.config = config
    
    def run(self):
        import asyncio
        asyncio.run(self._run_crawl())
    
    async def _run_crawl(self):
        engine = DiscoveryEngine(
            vault=self.config['vault'],
            max_concurrent=self.config['concurrency'],
            no_dns=self.config['no_dns'],
        )
        
        result = await engine.crawl(
            seeds=self.config['seeds'],
            max_depth=self.config['max_depth'],
            domains=self.config['domains'],
            exclude_patterns=self.config['exclude_patterns'],
            output_dir=self.config['output_dir'],
            progress_callback=self._on_progress,
        )
        
        self.finished.emit(result)
    
    def _on_progress(self, state: ProgressState):
        # Emit to main thread via signal
        self.progress.emit(state)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.worker = None
        # ... setup UI ...
    
    def start_crawl(self):
        self.worker = DiscoveryWorker(self.get_config())
        self.worker.progress.connect(self.on_progress)
        self.worker.finished.connect(self.on_finished)
        self.worker.start()
    
    def on_progress(self, state: ProgressState):
        # Update counters
        self.discovered_label.setText(str(state.discovered))
        self.failed_label.setText(str(state.failed))
        self.queue_label.setText(str(state.queued))
        self.total_label.setText(str(state.total))
        
        # Update depth/progress
        self.depth_label.setText(f"Depth {state.current_depth} of {state.max_depth}")
        self.progress_bar.setValue(int(state.progress_percent))
        
        # Update log based on event type
        ts = datetime.now().strftime("%H:%M:%S")
        
        if state.event == ProgressEventType.CRAWL_STARTED:
            self.log(f"[{ts}] Starting crawl from {len(state.seeds)} seeds")
            self.log(f"[{ts}] Depth: {state.max_depth} | Concurrency: {state.concurrency}")
        
        elif state.event == ProgressEventType.DEVICE_COMPLETED:
            vendor = state.last_device_vendor or "unknown"
            duration = state.last_device_duration_ms
            self.log(f"[{ts}] ✓ {state.last_device_hostname} ({vendor}) - {duration:.0f}ms", 
                     color="green")
            
            neighbors = state.last_device_cdp_count + state.last_device_lldp_count
            if neighbors > 0:
                self.log(f"[{ts}]   └─ CDP: {state.last_device_cdp_count}, "
                        f"LLDP: {state.last_device_lldp_count}")
        
        elif state.event == ProgressEventType.DEVICE_FAILED:
            self.log(f"[{ts}] ⚠ {state.current_target} - {state.last_device_error}", 
                     color="orange")
        
        elif state.event == ProgressEventType.DEPTH_COMPLETED:
            self.log(f"[{ts}] Depth {state.current_depth} complete: "
                    f"{state.discovered} devices, {state.queued} queued")
        
        elif state.event == ProgressEventType.CRAWL_COMPLETED:
            self.log(f"[{ts}] ✓ Crawl complete: {state.discovered} discovered, "
                    f"{state.failed} failed ({state.elapsed_seconds:.1f}s)", 
                     color="green")
    
    def on_finished(self, result):
        self.worker = None
        # Enable result viewing, map preview, etc.
```

---

## Event Frequency

| Event | Frequency | Notes |
|-------|-----------|-------|
| `CRAWL_STARTED` | Once | At crawl start |
| `DEPTH_STARTED` | Once per depth | max_depth + 1 times max |
| `DEVICE_COMPLETED` | Per successful device | Main progress driver |
| `DEVICE_FAILED` | Per failed device | Usually fewer than completed |
| `DEVICE_SKIPPED` | Per excluded device | Only if exclusion patterns match |
| `DEVICE_QUEUED` | Per neighbor found | **High frequency** - batch updates |
| `DEPTH_COMPLETED` | Once per depth | Good sync point |
| `CRAWL_COMPLETED` | Once | At crawl end |
| `CRAWL_FAILED` | Once (if error) | Replaces CRAWL_COMPLETED |

---

## Performance Considerations

1. **Batch DEVICE_QUEUED updates**: This event fires for every neighbor discovered. Consider updating the queue counter on a timer (e.g., 100ms) rather than on every event.

2. **Log virtualization**: For large networks (100+ devices), use a virtualized log view that only renders visible entries.

3. **Thread safety**: Always emit progress via Qt signals to ensure GUI updates happen on the main thread.

4. **Progress bar smoothing**: The `progress_percent` property is depth-based and jumps at depth transitions. Consider smoothing or using an indeterminate progress bar during discovery.