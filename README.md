
## 🌐 Select language / Selecciona idioma

🇬🇧 [English](README.md) | 🇪🇸 [Español](README.es.md)

# 🩸 Home Assistant Glucose NG (NightScout Gateway)

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/)  
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A **custom Home Assistant integration** that receives glucose readings from **Juggluco, xDrip or Diabox** (or any Nightscout‑compatible uploader) **directly**, with no intermediaries.

This creates native sensors in Home Assistant for each device.

Example of created sensors and events:
- `sensor.glucose_ng_glucosa_glucosa`
- `sensor.glucose_ng_glucosa_delta`
- `sensor.glucose_ng_glucosa_rate`
- `event.glucose_ng_glucosa_treatment`

This allows you to build automations, alerts and custom dashboards in Home Assistant to help manage diabetes.

The project **implements the Nightscout v3 APIs**, so the uploader sends data directly to Home Assistant, where native sensors are created.

Mobile data consumption depends on usage. If readings are sent once per minute:
- Hourly ≈ 0.0135 MB
- Daily ≈ 0.324 MB
- Monthly (30 days) ≈ 9.7 MB

If treatments are also sent, the increase is minimal.
If used in follower mode, consumption increases according to sensor polling rate.

---

## 🛠️ Installation

[📘 Open detailed instructions](external/INSTALACION.es.md)

---

## 🤓 About this project

This is a **personal hobby project**. I’m not a professional developer, I **don’t know Python**, and much of the development was done using **Vive Coding**, Copilot and Gemini.

Even though it's an amateur project, it’s designed to be **simple, useful and robust** within Home Assistant.

I personally use this solution with a Libre 2 sensor, Juggluco, and Home Assistant behind nginx with port forwarding. It works perfectly.

---

# 🏠 Why Home Assistant?

**Home Assistant (HA)** is an open-home automation system allowing integration of sensors, devices, automations and services in one place.

Even if you don’t yet have smart home devices, HA allows glucose monitoring with dashboards and alerts.

Recommended: https://unlocoysutecnologia.com/

---

### ✔️ NightScout server inside HA

Apps like Juggluco, xDrip and Diabox send data **directly to HA**, locally and with no intermediaries.

---

# 🔔 Example automations

1. If glucose < 70 mg/dL after midnight → turn on bedroom light.
2. If < 60 mg/dL → trigger home alarm.
3. If < 50 mg/dL and person is alone → auto-call via Twilio.
4. If school hours & < 75 mg/dL → notify tutor + parents.

---

# 📦 Requirements

### 1. Home Assistant running 24/7
Use a PC, Raspberry Pi, etc. HA Green recommended (~139€).

### 2. HA accessible from the Internet
- HA Cloud (7.50€/month)
- OR router port forwarding + Nginx proxy (free)

### 3. Glucose sensor (Libre2, Libre3, Dexcom…)
Apps:
- Juggluco
- xDrip
- Diabox

---

# ⭐ Technical Features

- Nightscout endpoint emulation.
- Multi-user/device.
- Three sensors per device.
- Flexible authentication.
- Integrated alerts.
- Compatible with HACS.

---

# 📊 Sensors

| Sensor | Unit | Description |
|--------|-------|-------------|
| `sensor.` | mg/dL | Latest glucose reading |
| `sensor._delta` | mg/dL | Difference from previous reading |
| `sensor._rate` | mg/dL/min | Rate of change |

Additional attributes:
- `direction`
- `timestamp_ms`

---

# 📅 Event Entities (Treatments)

Logged as `event.<device>_treatment`.

Advantages:
1. Works with HA Logbook.
2. Easy automation triggers.

---

# 🚨 Alerts

Triggers `glucose_ng_alert` when:
- Hypoglycemia (sgv < low_threshold)
- Hyperglycemia (sgv > high_threshold)
- Rapid drop (rate ≤ rapid_drop)

Contains `title`, `message`, `entry_id`.

---

# 📄 License
MIT
