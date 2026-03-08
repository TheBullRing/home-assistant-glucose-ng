
# 🩸 Home Assistant Glucose NG (NightScout Gateway)

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Una **integración personalizada para Home Assistant** que recibe lecturas de glucosa desde **Juggluco** (o cualquier uploader compatible con Nightscout) directamente — **sin necesidad de un servidor Nightscout real**.

El proyecto **emula las APIs Nightscout v1/v3** para que el uploader envíe los datos directamente a Home Assistant, donde se crean sensores nativos.

---


## 🤓 Sobre este proyecto

Este es un **proyecto personal y de hobby**. No soy desarrollador profesional, **no conozco Python**, y gran parte del desarrollo se ha hecho con ayuda de **Vive Coding** dentro de https://antigravity.google/.

Aunque sea un proyecto amateur, está diseñado para ser **simple, útil y robusto** dentro de Home Assistant.

---

# 🏠 ¿Qué es Home Assistant y por qué es ideal para gestionar sensores?

Para quien no conoce Home Assistant:

**Home Assistant (HA)** es un sistema de domótica abierto que permite integrar sensores, dispositivos, automatizaciones y servicios en un mismo sitio.

Incluso si hoy no tienes domótica en casa, Home Assistant es una plataforma:

- gratuita
- segura
- estable
- extensible
- con miles de integraciones

Recomiendo visitar: **https://unlocoysutecnologia.com/**

Es una web perfecta para familiarizarse con Home Assistant desde cero.

### ¿Por qué usar Home Assistant para sensores de glucosa?

Porque te permite crear **automatizaciones**, **avisos inteligentes**, **históricos**, **dashboards**, y combinar los valores del sensor con:

- luces
- alarmas
- mensajes
- llamadas
- notificaciones
- estados de presencia
- horarios (escuela, trabajo, etc.)

Aunque **no tengas ningún enchufe inteligente**, Home Assistant sigue siendo increíble para monitorizar sensores y enviar alertas.

---

# 🆚 ¿Por qué esta integración y no LibreView?

Hoy en día la única opción para meter un sensor de glucosa en HA es:

👉 https://github.com/PTST/LibreView-HomeAssistant

Pero esa integración depende de **LibreView**, un servicio externo en la nube.

Este proyecto evita esa dependencia mediante un enfoque diferente:

### ✔️ Este proyecto simula un servidor NightScout directamente en Home Assistant

De esta forma, aplicaciones como:

- Juggluco
- xDrip
- Diabox

pueden enviar los datos **directamente a HA**, de forma local, rápida y sin intermediarios.

⚠️ Al ser un **simulador**, no todas las funciones NightScout están implementadas.

Pero sí las necesarias para tener sensores funcionales y estables en Home Assistant con posibilidad de automatizaciones.

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

### 1. Tener un Home Assistant en casa

Si tienes un PC viejo, puedes usarlo para ejecutar Home Assistant OS y un nginx.
Si tienes conocimientos, puedes redirigir puertos y usar un proxy Nginx.
Esta opción es la que he probado en este proyecto, y es **100% gratuita**.

Si no tienes hardware ni conocimientos, se recomienda usar Home Assistant Cloud con un Home Assistant Green.

Se recomienda el modelo **Home Assistant Green**, que **actualmente cuesta 139 €**.

Para consultar el precio actualizado en cualquier momento, puedes visitar la página oficial:
👉 https://www.home-assistant.io/green/

### 2. Home Assistant debe ser accesible desde Internet

Puede lograrse de dos formas:

- **Home Assistant Cloud**, precio 7,50€ mes https://www.nabucasa.com/pricing/
- Redirigiendo puertos en el router y usando un **proxy Nginx** (esta es la opción probada en este proyecto) y es **100% gratuita**.

### 3. Tener un sensor de glucosa ( En mi caso Libre 2)

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

# 🔧 Instalación

## Via HACS (recomendado)

1. Accede a HACS
2. Busca Home Assistant Glucose NG
3. Haz click sobre los 3 puntos verticales, y selecciona la opción "Descarga" e instala la última versión.
4. Si vas a configurar el Dashboard, instala también ApexCharts.
5. Reinicia Home Assistant

## Instalación manual

1. Copia `custom_components/glucose_ng/` en `config/custom_components/`.
2. Reinicia Home Assistant.

---

# ⚙️ Configuración

Después de reiniciar Home Assistant, añade una entrada de integración por cada dispositivo uploader:

1. Ve a **Ajustes → Dispositivos y Servicios → Añadir integración**.
2. Busca **Glucose NG** y selecciónala.
3. Completa el formulario:

|Campo|Descripción|Valor por defecto|
|---|---|---|
|Shared Secret|El token API configurado en el uploader. Debe ser único por dispositivo.|(obligatorio)|
|Name|Nombre de la persona/dispositivo. Se usa para nombrar los sensores.|Glucosa|
|Low threshold|Límite inferior para alerta de hipoglucemia (mg/dL).|70|
|High threshold|Límite superior para hiperglucemia (mg/dL).|180|
|Rapid drop|Alerta cuando la velocidad de descenso es ≤ N mg/dL/min.|3.0|

Cada entrada crea un **Dispositivo** en la interfaz de Home Assistant llamado `Glucose NG — <Name>` que contiene tres sensores.

---

# 📱 Configuración del Uploader

En la app que utilices, xDrip, Diabox o Juggluco, configura el uploader **Nightscout**:

|Ajuste|Valor|
|---|---|
|URL|https://tu-servidor-ha (sin rutas adicionales)|
|API Secret|El mismo Shared Secret que configuraste en Home Assistant|
|API version|v3

El uploader realizará estas llamadas:

- `GET https://tu-ha/api/v2/authorization/request/<token>` → Verificación del token.
- `POST https://tu-ha/api/v3/entries` → Envío de lecturas.
- `POST https://tu-ha/api/v3/treatments` → Cuando se introducen tratamientos (insulina, carbohidratos).

**Nota para usuarios de Nginx:** Home Assistant puede eliminar el header `Authorization` antes de enviarlo a la integración. Glucose NG soluciona esto usando una sesión basada en IP durante 5 minutos tras la autorización inicial.

```yaml
        location / {
            proxy_pass http://internalha:8123/;
            client_max_body_size 10M;
            client_body_buffer_size 10M;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "Upgrade";
            proxy_set_header Host $host;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_set_header X-Real-IP $remote_addr;
        }
```
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

# 🚨 Alertas

La integración dispara un evento `glucose_ng_alert` y crea una **notificación persistente** en estos casos:

|Condición|Disparo|
|---|---|
|Hipoglucemia|sgv < low_threshold|
|Hiperglucemia|sgv > high_threshold|
|Caída rápida|rate <= -rapid_drop|

El evento incluye `title`, `message` y `entry_id` (útil para automatizaciones por persona).

## Eventos de Treatments y Device Status

|Evento|Trigger|Payload|
|---|---|---|
|glucose_ng_new_treatment|POST a /api/v3/treatments|entry_id, datos de insulina/carbs|
|glucose_ng_new_devicestatus|POST a /api/v3/devicestatus|nivel de batería, info del uploader|

Puedes usar estos eventos como **disparadores de automatización** en Home Assistant.

---

# 📈 Dashboard Lovelace (ApexCharts)

Para mostrar gráficas:

1. Instala **apexcharts-card** desde HACS.
2. Añade una tarjeta como esta: ( Cambia el nombre del sensor sensor glucose_ng_glucosa_glucosa por el que uses)
3. En Home Assistant > Configuración > Paneles de Control  >  Añadir panel de control > "Nuevo Panel de control desde cero"
  - Título: Glucosa
  - Icono: mdi:medication
  - Añadir a la barra lateral selecciona "Sí"
4. En la barra lateral aparece en el menu ahora la opción "Glucosa":
  - Pincha y pincha en el icono del lapiz para editar el panel. 
  - Selecciona los 3 puntos y pincha la opción "Editor de configuración en bruto"
  - Borra lo que aparezca y copia y pega el YAML que se muestra a continuación, cambia el nombre del sensor sensor glucose_ng_glucosa_glucosa por el que uses.

```yaml
views:
  - title: Glucosa
    panel: true
    cards:
      - type: custom:apexcharts-card
        graph_span: 24h
        header:
          show: true
          title: Glucosa - Últimas 24 h (mg/dL)
        yaxis:
          - decimals: 0
        apex_config:
          stroke:
            curve: smooth
            width: 3
          markers:
            size: 0
          legend:
            show: false
          yaxis:
            - forceNiceScale: true
          annotations:
            yaxis:
              - 'y': 70
                borderColor: '#2e7d32'
              - 'y': 180
                borderColor: '#2e7d32'
              - 'y': 70
                y2: 180
                fillColor: rgba(46,125,50,0.12)
                borderColor: transparent
        series:
          - entity: sensor.glucose_ng_glucosa_glucosa
            name: Glucosa < 70
            type: line
            color: '#d32f2f'
            group_by:
              duration: 5min
              func: avg
            transform: 'return x == null ? null : (Number(x) < 70 ? Number(x) : null);'
          - entity: sensor.glucose_ng_glucosa_glucosa
            name: Glucosa 70–180
            type: line
            color: '#2e7d32'
            group_by:
              duration: 5min
              func: avg
            transform: >-
              return x == null ? null : (Number(x) >= 70 && Number(x) <= 180 ?
              Number(x) : null);
          - entity: sensor.glucose_ng_javi_javi
            name: Glucosa > 180
            type: line
            color: '#d32f2f'
            group_by:
              duration: 5min
              func: avg
            transform: 'return x == null ? null : (Number(x) > 180 ? Number(x) : null);'

```

---

# 🧪 Prueba rápida (curl)

```bash
SECRET="tu_shared_secret"
SECRET_SHA1=$(echo -n "$SECRET" | sha1sum | cut -d' ' -f1)

# Probar autenticación
curl -s "http://TU_HA_IP:8123/api/v2/authorization/request/$SECRET"

# Enviar lectura
curl -X POST "http://TU_HA_IP:8123/api/v3/entries" \
  -H "Content-Type: application/json" \
  -H "api-secret: $SECRET_SHA1" \
  -d '[{"sgv": 120, "date": '"$(date +%s%3N)"', "direction": "Flat", "type": "sgv"}]'

# Enviar tratamiento (insulina)
curl -X POST "http://TU_HA_IP:8123/api/v3/treatments" \
  -H "Content-Type: application/json" \
  -H "api-secret: $SECRET_SHA1" \
  -d '[{"eventType": "Correction Bolus", "insulin": 2.5, "created_at": "'$(date -u +"%Y-%m-%dT%H:%M:%SZ")'"}]'
```

Respuesta esperada: `{"ok": true, "count": 1}`.

Luego revisa **Herramientas de desarrollador → Estados** para ver `sensor.<nombre>`.

---

# 🩻 Troubleshooting

Activa logs detallados añadiendo esto a `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.glucose_ng: debug
```

Reinicia HA y revisa **Ajustes → Sistema → Logs**.

Problemas comunes:

|Síntoma|Causa probable|Solución|
|---|---|---|
|401 en logs de Nginx, sin logs en HA|La integración no cargó|Reiniciar HA y revisar errores|
|WARNING: token did not match|Secret en el uploader ≠ secret en HA|Verificar que coinciden exactamente|
|Sensor en unknown|Falta el campo sgv en la lectura|Revisar cuerpo enviado por el uploader|

---

# 📄 Licencia

MIT
