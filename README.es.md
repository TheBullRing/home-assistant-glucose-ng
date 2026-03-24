## 🌐 Select language / Selecciona idioma

🇬🇧 [English](README.md) | 🇪🇸 [Español](README.es.md)

# 🩸 Home Assistant Glucose NG (NightScout Gateway)

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Una **integración personalizada para Home Assistant** que recibe lecturas de glucosa desde **Juggluco, GlucoDataHandler, xDrip o Diabox** (o cualquier uploader compatible con Nightscout) directamente, sin intermediarios.

Esto crea sensores nativos en Home Assistant para cada dispositivo, permitiendo automatizaciones, alertas y dashboards personalizados relacionados con la gestión de la diabetes.

Ejemplos de sensores y eventos creados:

- `sensor.glucose_ng_glucosa_glucosa`
- `sensor.glucose_ng_glucosa_delta`
- `sensor.glucose_ng_glucosa_rate`
- `event.glucose_ng_glucosa_treatment`

El proyecto **implementa las APIs Nightscout v3**, permitiendo que los datos lleguen directamente a Home Assistant, donde se crean sensores y eventos nativos.

---

## 🖼️ Capturas de ejemplo

<p align="center">
  <img src="https://raw.githubusercontent.com/TheBullRing/home-assistant-glucose-ng/main/external/capturas/HomeAssistantAndroid.png" width="350" style="margin-right: 25px;" />
  <img src="https://raw.githubusercontent.com/TheBullRing/home-assistant-glucose-ng/main/external/capturas/TelegramMensaje.png" width="350" />
</p>

---

## 📶 Consumo de datos móviles

Si el uploader envía lecturas cada minuto:

- **Por hora:** ≈ 0,0135 MB  
- **Por día:** ≈ 0,324 MB  
- **Por mes (30 días):** ≈ 9,7 MB  

Si también se envían tratamientos, el consumo aumentará mínimamente.

En modo *follower*, el consumo dependerá de la frecuencia de actualización.

---

## 🤓 Sobre este proyecto

Este es un **proyecto personal y de hobby**. No soy desarrollador profesional, **no conozco Python**, y gran parte del desarrollo se ha hecho con ayuda de **Vive Coding** en https://antigravity.google/ y herramientas como Copilot y Gemini.

Aunque se trate de un proyecto amateur, está diseñado para ser **simple, útil y robusto** dentro de Home Assistant.

Lo utilizo personalmente con un sensor Libre 2, Juggluco y Home Assistant con Nginx redirigiendo puertos en el router.

---

# 🏠 ¿Por qué Home Assistant?

**Home Assistant (HA)** es un sistema de domótica abierto que permite integrar sensores, automatizaciones, dispositivos y servicios en un único lugar.

Incluso si no tienes domótica en casa, te ofrece la posibilidad de integrar tu sensor de glucosa y crear automatizaciones, alertas y paneles personalizados sin necesidad de hardware adicional. Ejemplo: alertas por Telegram.

Recomiendo visitar: **https://unlocoysutecnologia.com/**

---

## ✔️ Este proyecto crea un servidor NightScout directamente en Home Assistant

Uploaders compatibles:

- [Juggluco](https://github.com/j-kaltes/Juggluco)
- [GlucoDataHandler](https://github.com/GlucoDataHandler/GlucoDataHandler)
- [xDrip](https://github.com/NightscoutFoundation/xDrip)
- [Diabox](https://github.com/Diabox/Diabox)

Todos pueden enviar datos **directamente a HA**, de forma local, rápida y en tiempo real.

Los datos alimentan sensores nativos que puedes usar para automatizaciones, alertas y dashboards personalizados.

---

# 🔔 Ejemplos de automatizaciones

Gracias a que los sensores viven dentro de HA:

1. **Si la glucosa baja de 70 mg/dL después de medianoche:** encender la luz de la habitación.  
2. **Si baja de 60 mg/dL:** activar la alarma de la casa.  
3. **Si baja de 50 mg/dL y la persona está sola:** realizar una llamada automática vía Twilio a un contacto de emergencia.  
4. **Si es horario escolar y la glucosa baja de 75 mg/dL:** enviar mensaje por Telegram al tutor y padres. Si es fin de semana → solo a los padres.

Las combinaciones son prácticamente infinitas.

---

# 📦 Requisitos para usar este proyecto

### 1. Tener un Home Assistant en casa 24/7

Opciones:

- Un PC viejo  
- Una Raspberry Pi  
- Home Assistant Green (~139 €): https://www.home-assistant.io/green/

Si tienes conocimientos, puedes usar un proxy Nginx y redirigir puertos (opción gratuita probada en este proyecto).

### 2. Home Assistant debe ser accesible desde Internet

Opciones:

- **Home Assistant Cloud** (7,50 €/mes) → https://www.nabucasa.com/pricing/  
- Redirigir puertos y usar **Nginx** como proxy (opción gratuita)

### 3. Tener un sensor de glucosa compatible

Ejemplos: Libre 2, Libre 3, Dexcom…

---

# ⭐ Características técnicas

## Funcionalidades

- Emulación completa de Nightscout para los endpoints usados por los uploaders.
- Multi-dispositivo/persona: cada uno con su propio secreto.
- Tres sensores por dispositivo:  
  - `sensor.glucose_ng_<nombre>` — glucosa actual (mg/dL)  
  - `sensor.glucose_ng_<nombre>_delta` — cambio respecto a la lectura anterior  
  - `sensor.glucose_ng_<nombre>_rate` — velocidad de cambio (mg/dL/min)  
- Autenticación flexible.
- Alertas integradas.
- Compatible con HACS.

---

# 📊 Sensores disponibles

Sensor | Unidad | Descripción
------ | ------ | -----------
`sensor.glucose_ng_<nombre>` | mg/dL | Última lectura de glucosa *(device_class: blood_glucose_concentration)*
`sensor.glucose_ng_<nombre>_delta` | mg/dL | Diferencia respecto a la lectura anterior.
`sensor.glucose_ng_<nombre>_rate` | mg/dL/min | Velocidad de cambio por minuto.

Atributos adicionales:

- `direction` — flecha/trend del uploader  
- `timestamp_ms` — marca de tiempo original del dispositivo  

---

# 📅 Entidades de Evento (Tratamientos)

Entidad | Descripción | Payload
------- | ----------- | -------
`event.glucose_ng_<nombre>_treatment` | Registra cada nuevo tratamiento | Atributos como eventType, insulin, carbs, notes, etc.

**Ventajas:**

1. Integración con el **Logbook** de Home Assistant.  
2. Uso muy sencillo como disparador de automatizaciones.

---

# 🚨 Alertas

La integración dispara un evento `glucose_ng_alert` y crea una **notificación persistente** cuando:

Condición | Disparo
--------- | -------
Hipoglucemia | `sgv < low_threshold`
Hiperglucemia | `sgv > high_threshold`
Caída rápida | `rate <= -rapid_drop`

El evento incluye `title`, `message` y `entry_id`.

> Nota: no tiene limitación de frecuencia. Si lo usas para alertas de Telegram, recibirás un mensaje por minuto mientras el valor esté fuera de rango.

---

# 🛠️ Instalación

<p align="left">
  <a href="external/INSTALACION.es.md" style="display: inline-block; background-color: #007bff; color: white; padding: 12px 20px; font-size: 18px; font-weight: bold; border-radius: 8px; text-decoration: none;">
    📘 Abrir instrucciones detalladas
  </a>
</p>

---

# 📄 Licencia
MIT
