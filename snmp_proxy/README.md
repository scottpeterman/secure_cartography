# SNMP Proxy

Async ticket-based SNMP proxy for remote device polling. Deploy on a jump host or management server with SNMP access to target devices, then poll from desktop clients that lack direct network connectivity.

Part of the [Secure Cartography](https://github.com/scottpeterman/secure_cartography) network discovery toolkit.

## Why a Proxy?

Network engineers often work from desktops that can't reach management networks directly. The SNMP proxy bridges this gap:

```
┌─────────────┐         ┌─────────────┐         ┌─────────────┐
│   Desktop   │  HTTP   │  Jump Host  │  SNMP   │   Network   │
│   Client    │◄───────►│   (Proxy)   │◄───────►│   Devices   │
└─────────────┘  :8899  └─────────────┘  :161   └─────────────┘
```

## Features

- **Cross-platform**: Pure Python using pysnmp - works on Windows, Linux, Mac
- **Async ticket-based polling**: Submit jobs, poll for status, retrieve results
- **Progress tracking**: Real-time progress for long-running walks (200+ interface devices)
- **Concurrency control**: Configurable limit on simultaneous polls
- **SNMPv1/v2c/v3 support**: Community strings or full v3 authentication
- **Cancellation**: Cancel running jobs cleanly mid-walk
- **Ephemeral auth**: Fresh API key generated on each startup

## Installation

```bash
# From source
pip install -e ./snmp_proxy

# Or install dependencies directly
pip install fastapi uvicorn pysnmp pydantic
```

### Requirements

- Python 3.10+
- pysnmp >= 6.0.0 (the lextudio fork or newer mainline)
- FastAPI, Uvicorn, Pydantic

## Quick Start

```bash
# Start the proxy
python -m snmp_proxy

# Or with custom settings
python -m snmp_proxy --port 9000 --max-concurrent 4
```

On startup, the proxy prints its API key:

```
════════════════════════════════════════════════════════════════
  SNMP PROXY v2.0.0
  Async ticket-based SNMP polling
════════════════════════════════════════════════════════════════

  🔑 API Key: d0f0d9e6-36ae-489d-ba96-29da77e529cc

  📡 Server:  http://0.0.0.0:8899
  🏥 Health:  http://0.0.0.0:8899/health
  📚 Docs:    http://0.0.0.0:8899/docs

  ⚙️  Configuration:
      Max concurrent polls: 6
      Job retention:        1 hour(s)
      Default GET timeout:  10s
      Default WALK timeout: 120s
```

## API Usage

### Health Check (No Auth)

```bash
curl http://localhost:8899/health
```

```json
{
  "status": "ok",
  "version": "2.0.0",
  "active_jobs": 0,
  "total_jobs": 3,
  "max_concurrent": 6,
  "uptime_seconds": 1234.5
}
```

### Submit a Poll Job

```bash
curl -X POST http://localhost:8899/snmp/poll \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_API_KEY" \
  -d '{
    "target": "192.168.1.1",
    "community": "public",
    "version": "2c",
    "collect_interfaces": true,
    "collect_arp": true
  }'
```

Response:
```json
{
  "ticket": "e0750fc3-4e6d-4423-9611-b5f8c80da169",
  "status": "queued",
  "target": "192.168.1.1"
}
```

### Check Status

```bash
curl -H "X-API-Key: YOUR_API_KEY" \
  http://localhost:8899/status/e0750fc3-4e6d-4423-9611-b5f8c80da169
```

While running:
```json
{
  "ticket": "e0750fc3-4e6d-4423-9611-b5f8c80da169",
  "target": "192.168.1.1",
  "status": "running",
  "progress": "Walking interfaces... (147 entries)",
  "progress_detail": {
    "system_oids": 6,
    "interfaces_walked": 147
  },
  "elapsed_seconds": 12.4
}
```

When complete:
```json
{
  "ticket": "e0750fc3-4e6d-4423-9611-b5f8c80da169",
  "target": "192.168.1.1",
  "status": "complete",
  "progress": "Complete",
  "elapsed_seconds": 45.2,
  "timing": {
    "system_info": 1.2,
    "interfaces": 28.5,
    "arp": 15.3,
    "total": 45.2
  },
  "data": {
    "target": "192.168.1.1",
    "snmp_data": {
      "sysDescr": "Arista Networks EOS version 4.33.1F...",
      "sysName": "spine1",
      "sysObjectID": "1.3.6.1.4.1.30065.1.2759.462",
      "sysLocation": "DC1 Row 5",
      "sysContact": "noc@example.com",
      "sysUpTime": "29758389"
    },
    "interfaces": [
      {"description": "Ethernet1", "mac": "00:1C:73:AA:BB:CC"},
      {"description": "Ethernet2", "mac": "00:1C:73:AA:BB:CD"}
    ],
    "arp_table": [
      {"ip": "192.168.1.10", "mac": "11:22:33:44:55:66"},
      {"ip": "192.168.1.11", "mac": "11:22:33:44:55:67"}
    ]
  }
}
```

### Cancel a Job

```bash
curl -X DELETE http://localhost:8899/jobs/e0750fc3-... \
  -H "X-API-Key: YOUR_API_KEY"
```

### Direct Operations

For quick single-OID operations without the ticket system:

```bash
# SNMP GET
curl -X POST http://localhost:8899/snmp/get \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_API_KEY" \
  -d '{"target": "192.168.1.1", "community": "public", "oid": "1.3.6.1.2.1.1.5.0"}'

# SNMP WALK
curl -X POST http://localhost:8899/snmp/walk \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_API_KEY" \
  -d '{"target": "192.168.1.1", "community": "public", "oid": "1.3.6.1.2.1.2.2.1.2"}'
```

## SNMPv3 Authentication

For SNMPv3, include the `v3_auth` object:

```json
{
  "target": "192.168.1.1",
  "version": "3",
  "v3_auth": {
    "username": "snmpuser",
    "auth_protocol": "SHA256",
    "auth_password": "authpass123",
    "priv_protocol": "AES256",
    "priv_password": "privpass456"
  }
}
```

**Supported protocols:**
- Auth: MD5, SHA, SHA224, SHA256, SHA384, SHA512
- Priv: DES, 3DES, AES, AES128, AES192, AES256

## CLI Options

```
python -m snmp_proxy --help

Options:
  --host TEXT            Bind address (default: 0.0.0.0)
  --port INTEGER         Listen port (default: 8899)
  --max-concurrent INT   Maximum concurrent polls (default: 6)
  --retention-hours INT  Hours to retain completed jobs (default: 1)
  --get-timeout INT      Default SNMP GET timeout (default: 10)
  --walk-timeout INT     Default SNMP WALK timeout (default: 120)
  --log-level LEVEL      Log level: DEBUG, INFO, WARNING, ERROR
  --api-key TEXT         Use specific API key instead of generating
  --version              Show version
```

## Deployment

### Windows Service (NSSM)

```cmd
nssm install SNMPProxy "C:\Python311\python.exe" "-m" "snmp_proxy" "--port" "8899"
nssm set SNMPProxy AppDirectory "C:\Tools\SNMPProxy"
nssm set SNMPProxy DisplayName "SNMP Proxy Service"
nssm start SNMPProxy
```

### Linux systemd

Create `/etc/systemd/system/snmp-proxy.service`:

```ini
[Unit]
Description=SNMP Proxy Service
After=network.target

[Service]
Type=simple
User=snmpproxy
WorkingDirectory=/opt/snmp-proxy
ExecStart=/usr/bin/python3 -m snmp_proxy --port 8899
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
systemctl daemon-reload
systemctl enable snmp-proxy
systemctl start snmp-proxy
```

### Docker

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY snmp_proxy/ ./snmp_proxy/
RUN pip install --no-cache-dir fastapi uvicorn pysnmp pydantic
EXPOSE 8899
CMD ["python", "-m", "snmp_proxy", "--host", "0.0.0.0"]
```

## Architecture

```
snmp_proxy/
├── __init__.py       # Package exports
├── __main__.py       # CLI entry point
├── models.py         # Pydantic request/response models
├── snmp_ops.py       # pysnmp async operations
├── jobs.py           # Job manager with concurrency control
└── server.py         # FastAPI application
```

**Job Lifecycle:**
```
QUEUED → RUNNING → COMPLETE
                 → FAILED
                 → CANCELLED
```

**Concurrency Control:**
- Semaphore limits concurrent polls (default: 6)
- Jobs queue when limit reached
- Prevents overwhelming network/devices

## Security Considerations

- **Ephemeral API Key**: Generated fresh on startup, never stored
- **Single-user model**: Designed for desktop-to-proxy, not multi-tenant
- **No credential storage**: Community strings passed per-request
- **Network segmentation**: Deploy proxy in management network only

## Troubleshooting

**"No SNMP response"**
- Verify target is reachable from proxy host
- Check community string / credentials
- Confirm SNMP is enabled on device (port 161)

**Timeouts on large devices**
- Increase `--walk-timeout` for devices with 500+ interfaces
- Monitor progress via status endpoint

**pysnmp import errors**
- Ensure pysnmp >= 6.0.0 installed
- API changed: `get_cmd` not `getCmd`, `await UdpTransportTarget.create()`

## License

MIT License - See LICENSE file

## Author

Scott Peterman