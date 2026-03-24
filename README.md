## 🌐 Select language / Selecciona idioma

🇬🇧 [English](README.md) | 🇪🇸 [Español](README.es.md)

# 🩸 Home Assistant Glucose NG (NightScout Gateway)

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A **custom integration for Home Assistant** that receives glucose readings from **Juggluco, xDrip, or Diabox** (or any Nightscout‑compatible uploader) directly, with no intermediaries.

It creates native Home Assistant sensors for each device, enabling full automation, alerts, and custom dashboards for diabetes management.

Examples of created sensors and events:

- `sensor.glucose_ng_glucosa_glucosa`
- `sensor.glucose_ng_glucosa_delta`
- `sensor.glucose_ng_glucosa_rate`
- `event.glucose_ng_glucosa_treatment`

The project implements **Nightscout v3 APIs**, allowing uploaders to send data straight into Home Assistant, where native sensors and events are generated.

---

## 🖼️ Example screenshots


<p align="center">
  <img src="https://raw.githubusercontent.com/TheBullRing/home-assistant-glucose-ng/main/external/capturas/HomeAssistantAndroid.png" width="350" style="margin-right: 25px;" />
  <img src="https://raw.githubusercontent.com/TheBullRing/home-assistant-glucose-ng/main/external/capturas/TelegramMensaje.png" width="350" />
</p>
---

## 📶 Mobile data usage

If your uploader sends one reading per minute:

- **Per hour:** ≈ 0.0135 MB  
- **Per day:** ≈ 0.324 MB  
- **Per month (30 days):** ≈ 9.7 MB  

If treatments are also sent, the usage increases slightly.  
If used in *follower mode*, data consumption depends on sensor update frequency.

---

## 🤓 About this project

This is a **personal/hobby project**. I’m not a professional developer, I **don’t know Python**, and most of the development was done with the help of **Vive Coding** in https://antigravity.google/ and tools like Copilot and Gemini.

Even though it is an amateur project, it is designed to be **simple, useful, and robust** inside Home Assistant.

I use this solution personally with a Libre 2 sensor, Juggluco, and Home Assistant running behind an Nginx reverse proxy.

---

# 🏠 Why Home Assistant?

**Home Assistant (HA)** is an open‑source home automation platform that allows you to integrate sensors, devices, automations, and services in one place.

Even if you don’t use home automation, HA lets you integrate glucose readings and create custom dashboards and alerts without extra hardware (for example, sending Telegram alerts).

Recommended reading: **https://unlocoysutecnologia.com/**

---

## ✔️ This project runs a NightScout server directly inside Home Assistant

Compatible uploaders:

- [Juggluco](https://github.com/j-kaltes/Juggluco)
- [GlucoDataHandler](https://github.com/GlucoDataHandler/GlucoDataHandler)
- [xDrip](https://github.com/NightscoutFoundation/xDrip)
- [Diabox](https://github.com/Diabox/Diabox)

All of them can send data **directly to HA**, locally, quickly, and in real time.

The incoming data feeds native HA sensors, which you can then use for automations, alerts, and dashboards.

---

# 🔔 Examples of automations

Because the glucose sensor lives inside HA, you can create automations like:

1. **If glucose drops below 70 mg/dL after midnight:** turn on the bedroom light.  
2. **If it drops below 60 mg/dL:** trigger the home alarm.  
3. **If it drops below 50 mg/dL and the person is alone:** place an automatic call via Twilio to an emergency contact.  
4. **If it’s school hours and glucose drops below 75 mg/dL:** send a Telegram message to the tutor and parents. On weekends → only parents.

The possibilities are nearly infinite.

---

# 📦 Requirements

### 1. A Home Assistant system running 24/7

You can use:

- An old PC  
- A Raspberry Pi  
- **Home Assistant Green** (~139 €) → https://www.home-assistant.io/green/

If you have some technical knowledge, you can expose HA using an Nginx reverse proxy (tested, 100% free).

### 2. Home Assistant must be accessible from the Internet

Options:

- **Home Assistant Cloud** (7.50 €/month) → https://www.nabucasa.com/pricing/  
- Port forwarding + **Nginx reverse proxy** (tested in this project, free)

### 3. A compatible glucose sensor

Examples: Libre 2, Libre 3, Dexcom…

Nightscout‑compatible apps:

- **Juggluco** → https://github.com/j-kaltes/Juggluco  
 xDrip  
- Diabox  

---

# ⭐ Technical features

## Functionality

- Full Nightscout emulation for all uploader‑used endpoints.  
- Multi‑device/person support with individual secrets.  
- Three sensors per device:  
  - `sensor.glucose_ng_<name>` — current glucose (mg/dL)  
  - `sensor.glucose_ng_<name>_delta` — change since last reading  
  - `sensor.glucose_ng_<name>_rate` — rate of change (mg/dL/min)  
- Flexible authentication.  
- Built‑in alerts.  
- HACS compatible.

---

# 📊 Available sensors

Sensor | Unit | Description
------ | ----- | -----------
`sensor.glucose_ng_<name>` | mg/dL | Latest glucose reading *(device_class: blood_glucose_concentration)*
`sensor.glucose_ng_<name>_delta` | mg/dL | Difference to the previous reading
`sensor.glucose_ng_<name>_rate` | mg/dL/min | Rate of change per minute

Additional attributes:

- `direction` — trend arrow reported by the uploader  
- `timestamp_ms` — original device timestamp  

---

# 📅 Event entities (Treatments)

Entity | Description | Payload
------ | ----------- | -------
`event.glucose_ng_<name>_treatment` | Logs each new treatment | Attributes such as eventType, insulin, carbs, notes, etc.

**Advantages:**

1. Integrates with HA’s **Logbook**, showing a visual timeline of treatments.  
2. Very easy to use as a trigger in HA automations.

---

# 🚨 Alerts

The integration fires a `glucose_ng_alert` event and creates a **persistent notification** when:

Condition | Trigger
--------- | -------
Hypoglycemia | `sgv < low_threshold`
Hyperglycemia | `sgv > high_threshold`
Rapid drop | `rate <= -rapid_drop`

The event includes `title`, `message`, and `entry_id`.

> Note: There is **no frequency limiting**.  
> If used for Telegram alerts, you will receive one message per minute until glucose returns to normal.

---

# 🛠️ Installation

<p align="left">
  <a href="external/INSTALACION.md" style="display: inline-block; background-color: #007bff; color: white; padding: 12px 20px; font-size: 18px; font-weight: bold; border-radius: 8px; text-decoration: none;">
    📘 Open detailed installation instructions
  </a>
</p>

---

# 📄 License
MIT
