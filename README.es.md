
## 🌐 Select language / Selecciona idioma

🇬🇧 [English](README.md) | 🇪🇸 [Español](README.es.md)


# 🩸 Home Assistant Glucose NG (NightScout Gateway)

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Una **integración personalizada para Home Assistant** que recibe lecturas de glucosa desde **Juggluco, xDrip o Diabox** (o cualquier uploader compatible con Nightscout) directamente sin intermediarios.

Esto crea sensores nativos en Home Assistant para cada dispositivo.

Ejemplo de sensores y eventos creados:

- `sensor.glucose_ng_glucosa_glucosa`
- `sensor.glucose_ng_glucosa_delta`
- `sensor.glucose_ng_glucosa_rate`
- `event.glucose_ng_glucosa_treatment`  

Esto permite crear automatizaciones, alertas y dashboards personalizados en Home Assistant para gestionar la diabetes.

El proyecto **implementa las APIs Nightscout v3** para que el uploader envíe los datos directamente a Home Assistant, donde se crean sensores nativos.

El consumo de datos mobiles dependera del uso, si solo se usa uploader que envia lecturas cada minuto:

🔹 Consumo por hora ≈ 0,0135 MB
🔹 Consumo por día ≈ 0,324 MB
🔹 Consumo por mes (30 días) ≈ 9,7 MB

Si además se envian tratamientos, el consumo aumentara minimamente.
Por otro lado, si se usa en modo follower, el consumo aumentara en funcion de la frecuencia de actualizacion de los sensores.

---
## Instalación

[Instalación](external/INSTALACION.es.md)

## 🤓 Sobre este proyecto

Este es un **proyecto personal y de hobby**. No soy desarrollador profesional, **no conozco Python**, y gran parte del desarrollo se ha hecho con ayuda de **Vive Coding** dentro de https://antigravity.google/ con ayuda de Copilot y Gemini.

Aunque sea un proyecto amateur, está diseñado para ser **simple, útil y robusto** dentro de Home Assistant.d

Uso personalmente la solución, con un sensor Libre 2, Juggluco, y Home Assistant a través de nginx redirigiendo puertos en el router. 
Hasta la fecha funciona perfectamente.

---

# 🏠 ¿Por qué Home Assistant?

**Home Assistant (HA)** es un sistema de domótica abierto que permite integrar sensores, dispositivos, automatizaciones y servicios en un mismo sitio.

Incluso si hoy no tienes domótica en casa, te permite integrar el senso de glucosa con automatizaciones, alertas y dashboards personalizados que no requieren dispositivos adicionales. Como enviar alertas a Telegram, etc.

Recomiendo visitar: **https://unlocoysutecnologia.com/**

---

### ✔️ Este proyecto crea un servidor NightScout directamente en Home Assistant

De esta forma, aplicaciones como:

- Juggluco
- xDrip
- Diabox

pueden enviar los datos **directamente a HA**, de forma local, rápida y sin intermediarios.

Estos datos nutren los sensores de HA.

---

# 🔔 Ejemplos reales de automatizaciones muy potentes

Gracias a que el sensor vive dentro de HA:

1. **Si la glucosa baja de 70 mg/dL después de medianoche:** encender la luz de la habitación.
2. **Si baja de 60 mg/dL:** activar la alarma de la casa.
3. **Si baja de 50 mg/dL y la persona está sola:** realizar llamada automática vía Twilio a un contacto de emergencia.
4. **Si es horario escolar y la glucosa baja de 75 mg/dL:** enviar mensaje por Telegram al tutor y a los padres. Si es fin de semana → solo a los padres.

Las combinaciones posibles son prácticamente infinitas.

---

# 📦 Requisitos para usar este proyecto

### 1. Tener un Home Assistant en casa 24*7

Es necesario tener un Home Assistant en casa funcionando 24 horas al día 7 días a la semana. 
Puedes usar un PC viejo, una Raspberry Pi, etc.

Si tienes un PC viejo, puedes usarlo para ejecutar Home Assistant OS y un nginx.
Si tienes conocimientos, puedes redirigir puertos y usar un proxy Nginx.
Esta opción es la que he probado en este proyecto, y es **100% gratuita**.

Si no tienes hardware y has de comprar algo, se recomienda **Home Assistant Green**, que **normalmente ronda los 139 €** 👉 https://www.home-assistant.io/green/ 

Para adentrarte en el mundo de HA visita  **https://unlocoysutecnologia.com/**

### 2. Home Assistant debe ser accesible desde Internet

Puede lograrse de dos formas:

- **Home Assistant Cloud**, precio 7,50€ mes https://www.nabucasa.com/pricing/
- Redirigiendo puertos en el router y usando un **proxy Nginx** (esta es la opción probada en este proyecto) y es **100% gratuita**.

### 3. Tener un sensor de glucosa ( Libre2, Libre3, Dexcom, etc)

Y utilizar aplicaciones compatibles con NightScout, como:

- **Juggluco** (probado en este proyecto): https://github.com/j-kaltes/Juggluco
- xDrip
- Diabox

Estas apps envían las lecturas directamente a Home Assistant a través de esta integración.

---

# ⭐ Características técnicas


## Funcionalidades

- Emulación completa de Nightscout en los endpoints usados por los uploaders.
- Multi-dispositivo/persona: cada entrada tiene su propio secreto y sensores independientes.
- Tres sensores por dispositivo:
    - `sensor.<nombre>` — glucosa actual (mg/dL)
    - `sensor.<nombre>_delta` — cambio desde la última lectura
    - `sensor.<nombre>_rate` — velocidad de cambio (mg/dL/min)
- Autenticación flexible.
- Alertas integradas.
- Compatible con HACS.

---

# 📊 Sensores disponibles

|Sensor|Unidad|Descripción|
|---|---|---|
|sensor.<nombre>|mg/dL|Última lectura de glucosa. (device_class: blood_glucose_concentration)|
|sensor.<nombre>_delta|mg/dL|Diferencia respecto a la lectura anterior.|
|sensor.<nombre>_rate|mg/dL/min|Velocidad de cambio por minuto.|

Los sensores tienen `state_class: measurement`, por lo que Home Assistant registra el historial automáticamente.

Atributos adicionales del sensor principal:

- `direction` — flecha/trend del uploader (Flat, SingleUp, etc.)
- `timestamp_ms` — marca de tiempo original del dispositivo

---

# 📅 Entidades de Evento (Tratamientos)

La integración crea entidades de tipo `event` (Ej: `event.<nombre>_treatment`) específicas para los tratamientos que introduzcas en la aplicación (Insulina, Carbohidratos, Cambios de sensor, etc.).

|Entidad|Descripción|Payload|
|---|---|---|
|event.<nombre>_treatment|Registra cada nuevo tratamiento.|Atributos del evento (eventType, insulin, carbs, notes, etc.)|

**Ventajas de la entidad Event:**
1. Se integra de forma nativa con el **Logbook** (Libro de registro) de Home Assistant, permitiéndote ver una línea temporal visual de tus inyecciones y comidas.
2. Es muy sencillo usarla como disparador (Trigger) en automatizaciones escogiendo el estado de la entidad evento.

---

# 🚨 Alertas

La integración dispara un evento `glucose_ng_alert` y crea una **notificación persistente** en estos casos:

|Condición|Disparo|
|---|---|
|Hipoglucemia|sgv < low_threshold|
|Hiperglucemia|sgv > high_threshold|
|Caída rápida|rate <= -rapid_drop|

El evento incluye `title`, `message` y `entry_id` (útil para automatizaciones por persona).

Se activa con cada lectura que esté fuera de rango. Si su glucosa es de 200 mg/dL y recibe una lectura cada minuto, la integración activará este evento cada minuto.

A menos que tengas una automatización que escuche específicamente el evento event_type: glucose_ng_alert, este evento ocurre silenciosamente en segundo plano y no envía ninguna notificación.

No tiene lógica de recuperación ni limitación de frecuencia integradas. Si lo usas para alertas de Telegram, recibirás mensajes cada minuto hasta que tu glucosa vuelva a la normalidad.

Por eso no se recomienda usar el evento directamente, sino usar las automatizaciones sugeridas en external/automation_samples/.


## Eventos de Bus del Sistema (Avanzado)

Además de las entidades de sensor y de evento mostradas arriba, la integración sigue disparando eventos puros en el Bus de Home Assistant:

|Evento del Bus|Trigger|Payload|
|---|---|---|
|glucose_ng_new_treatment|POST a /api/v3/treatments|entry_id, datos de insulina/carbs|
|glucose_ng_new_devicestatus|POST a /api/v3/devicestatus|nivel de batería, info del uploader|

Puedes suscribirte a estos eventos como **disparadores de automatización** personalizados si prefieres no usar la entidad `event.<nombre>_treatment`.

---
# 📄 Licencia

MIT
