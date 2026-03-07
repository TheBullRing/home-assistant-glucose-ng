# Home Assistant Glucose NG (NightScout Gateway)

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A **custom Home Assistant integration** that receives glucose readings from **Juggluco** (or any Nightscout-compatible uploader) directly — no Nightscout server required.

It emulates the Nightscout v1/v3 HTTP API so that Juggluco posts data straight to Home Assistant, which exposes it as native sensors.

---

## Features

- **Drop-in Nightscout emulation** — implements the exact endpoints Juggluco calls:
  - `GET /api/v2/authorization/request/<token>` — auth handshake
  - `POST /api/v1/entries` — Nightscout v1 entries
  - `POST /api/v3/entries` — Nightscout v3 entries
- **Multi-device support** — add one config entry per person/device, each with its own secret. Every entry gets its own isolated set of sensors and its own HA Device.
- **Three sensors per device:**
  - `sensor.<name>` — current glucose value in mg/dL
  - `sensor.<name>_delta` — change since last reading (mg/dL)
  - `sensor.<name>_rate` — rate of change (mg/dL/min)
- **Flexible authentication** — accepts credentials via `api-secret` header (plain or SHA1), `Authorization: Bearer`, `X-Shared-Secret`, or `?token=` query param. Falls back to an IP-based session (needed because HA's auth middleware can strip the Authorization header when behind a reverse proxy).
- **Alerts** — fires a `glucose_ng_alert` event and creates a persistent HA notification for hypo, hyper, and rapid-drop conditions.
- **HACS-ready** — installs as a custom repository with zero YAML configuration.

---

## How It Works

```
Juggluco (Android)
    │
    │  GET /api/v2/authorization/request/<token>   ← auth handshake
    │  POST /api/v3/entries  [JSON glucose data]   ← reading upload
    ▼
nginx (reverse proxy, HTTPS)
    ▼
Home Assistant  →  glucose_ng custom integration
    │
    ├── sensor.<name>          (mg/dL)
    ├── sensor.<name>_delta    (mg/dL)
    └── sensor.<name>_rate     (mg/dL/min)
```

---

## Installation

### Via HACS (recommended)

1. Publish (or fork) this repository to GitHub as a **public** repo.
2. In Home Assistant: **HACS → Integrations → ⋮ → Custom repositories**.
3. Paste the GitHub URL and select category **Integration**.
4. Install **Home Assistant Glucose NG** and **restart** Home Assistant.

### Manual

1. Copy the `custom_components/glucose_ng/` folder into your HA `config/custom_components/` directory.
2. Restart Home Assistant.

---

## Configuration

After restarting, add one integration entry per Juggluco device:

1. Go to **Settings → Devices & Services → Add Integration**.
2. Search for **Glucose NG** and click it.
3. Fill in the form:

| Field | Description | Default |
|-------|-------------|---------|
| **Shared Secret** | The API token you set in Juggluco. Must be unique per device. | _(required)_ |
| **Name** | Label for this device/person (e.g. `Alice`). Used in sensor names. | `Glucosa` |
| **Low threshold** | Hypo alert below this value (mg/dL). | `70` |
| **High threshold** | Hyper alert above this value (mg/dL). | `180` |
| **Rapid drop** | Alert when rate of change ≤ −N mg/dL/min. | `3.0` |

4. Repeat for each additional device/person.

Each entry creates a **Device** named `Glucose NG — <Name>` in the HA UI containing three sensors.

---

## Configuring Juggluco

In the Juggluco app, configure the **Nightscout** uploader:

| Setting | Value |
|---------|-------|
| **URL** | `https://your-ha-host` (no path suffix) |
| **API Secret** | The exact **Shared Secret** you set in HA |
| **API version** | v3 (preferred) or v1 |

Juggluco will call:
- `GET https://your-ha-host/api/v2/authorization/request/<token>` to verify the token.
- `POST https://your-ha-host/api/v3/entries` with the glucose data.

> **Note for nginx users:** HA's auth middleware can strip the `Authorization` header before it reaches the integration. The integration handles this automatically using an IP-based session: after the GET auth succeeds, the source IP is trusted for 5 minutes, so the POST goes through without needing the header.

---

## Sensors

| Sensor | Unit | Description |
|--------|------|-------------|
| `sensor.<name>` | mg/dL | Latest glucose reading. `device_class: blood_glucose_concentration` |
| `sensor.<name>_delta` | mg/dL | Difference from the previous reading |
| `sensor.<name>_rate` | mg/dL/min | Rate of change per minute |

All sensors have `state_class: measurement`, so HA automatically tracks history and statistics.

Extra attributes on the main sensor:
- `direction` — Juggluco trend arrow (e.g. `Flat`, `FortyFiveUp`, `SingleUp`)
- `timestamp_ms` — original epoch timestamp from the device

---

## Alerts

The integration fires a `glucose_ng_alert` **HA event** and creates a **persistent notification** when:

| Condition | Trigger |
|-----------|---------|
| Hypoglycemia | `sgv < low_threshold` |
| Hyperglycemia | `sgv > high_threshold` |
| Rapid drop | rate ≤ −`rate_drop` mg/dL/min |

The event payload contains `title`, `message`, and `entry_id` (useful for routing alerts per person in automations).

### Alert Automation Blueprint

Import the blueprint from `blueprints/automation/home_assistant_glucose_ng/alerts.yaml` to quickly create mobile push notifications for any of the above conditions.

---

## Lovelace Dashboard (ApexCharts)

Install **[apexcharts-card](https://github.com/RomRider/apexcharts-card)** via HACS, then add a card like this (replace `sensor.alice` with your sensor name):

```yaml
type: custom:apexcharts-card
header:
  show: true
  title: Glucose (24h)
graph_span: 24h
now:
  show: true
yaxis:
  - min: 40
    max: 300
    decimals: 0
    apex_config:
      annotations:
        yaxis:
          - y: 70
            y2: 180
            borderColor: '#00C853'
            fillColor: 'rgba(0,200,83,0.10)'
            label:
              text: 'Target range (70–180)'
series:
  - entity: sensor.alice
    name: Glucose
    type: line
    stroke_width: 3
    color: '#2196F3'
  - entity: sensor.alice_rate
    name: Rate (mg/dL/min)
    yaxis_id: second
    type: area
    color: '#FF6D00'
    opacity: 0.3
apex_config:
  yaxis:
    - seriesName: Glucose
    - opposite: true
      decimalsInFloat: 1
      title:
        text: 'mg/dL/min'
```

---

## Quick Test (curl)

Verify the integration is working without Juggluco:

```bash
SECRET="your_shared_secret"
SECRET_SHA1=$(echo -n "$SECRET" | sha1sum | cut -d' ' -f1)

# Test auth endpoint
curl -s "http://YOUR_HA_IP:8123/api/v2/authorization/request/$SECRET"

# Post a test reading (SHA1 of secret in api-secret header)
curl -X POST "http://YOUR_HA_IP:8123/api/v3/entries" \
  -H "Content-Type: application/json" \
  -H "api-secret: $SECRET_SHA1" \
  -d '[{"sgv": 120, "date": '"$(date +%s%3N)"', "direction": "Flat", "type": "sgv"}]'
```

Expected response: `{"ok": true, "count": 1}`.  
Then check **Developer Tools → States** for `sensor.<your_name>`.

---

## Troubleshooting

Enable debug logging in `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.glucose_ng: debug
```

Then restart HA and check **Settings → System → Logs**. The integration logs:
- Every auth decision with the exact header values received.
- A `WARNING` with full headers when a request is rejected.
- Each reading dispatched to sensors.

**Common issues:**

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `401` in nginx log, no HA log entries | Integration not loaded / HA not restarted | Restart HA, check for load errors |
| `WARNING: token did not match any registered entry` | Juggluco secret ≠ HA shared secret | Match the values exactly |
| Sensor stays `unknown` | Reading arrives but no `sgv` field | Check Juggluco body format in debug log |

---

## License

MIT
