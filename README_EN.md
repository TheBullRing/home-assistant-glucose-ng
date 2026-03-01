
# Home Assistant Glucose NG (NightScout Gateway)

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/)

**Custom integration** that accepts **Juggluco (Nightscout uploader)** HTTP posts directly in Home Assistant, **without Nightscout**.

## Features
- Nightscout-compatible endpoints: `GET /api/v2/authorization/request/<token>`, `POST /api/v1/entries`, `POST /api/v3/entries`.
- Flexible authentication: `api-secret` (plain or `sha1(secret)`), `Authorization: Bearer <token>`, `X-Shared-Secret`, or `?token=`.
- Main sensor: `sensor.glucosa` (mg/dL) with `state_class: measurement` (history & statistics).
- Derivative sensors: `sensor.glucosa_delta` (mg/dL) and `sensor.glucosa_velocidad` (mg/dL/min).
- Emits `glucose_ng_alert` events and creates persistent notifications.

## Install (HACS - Custom Repository)
1. Publish this repo on GitHub (public) and copy the URL.
2. **HACS → Integrations → + → Custom repositories**: add the URL, category **Integration**.
3. Install **Home Assistant Glucose NG** and **restart** HA.
4. Add the integration via **Settings → Devices & Services** and set:
   - **Shared secret**
   - **Low/High thresholds** (default 70–180 mg/dL)
   - **Rapid drop** (default 3 mg/dL/min)

## Configure Juggluco
- Base URL of your HA (no suffix). Juggluco will call `/api/v1/entries` or `/api/v3/entries` and `/api/v2/authorization/...`.
- **V1**: `api-secret` header = your secret (or its `sha1`).
- **V3**: `Authorization: Bearer <secret>`.

## Quick test
```bash
curl -X POST "http://<HA>:8123/api/v1/entries?token=YOUR_SECRET"   -H "Content-Type: application/json"   -d '[{"sgv": 123, "direction": "Flat", "date": 1740844800000}]'
```

## Lovelace Panel (ApexCharts)
Install **apexcharts-card** via HACS and add the resource, then create a view using the YAML in the Spanish README (`README.md`).

## License
MIT
