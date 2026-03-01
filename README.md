
# Home Assistant Glucose NG (NightScout Gateway)

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/)

**Integración personalizada** para aceptar publicaciones HTTP de **Juggluco (Nightscout uploader)** directamente en Home Assistant, **sin Nightscout**.

## Características
- Endpoints compatibles con Nightscout: `GET /api/v2/authorization/request/<token>`, `POST /api/v1/entries`, `POST /api/v3/entries`.
- Autenticación flexible: `api-secret` (texto o `sha1(secret)`), `Authorization: Bearer <token>`, `X-Shared-Secret`, o `?token=`.
- Sensor principal: `sensor.glucosa` (mg/dL) con `state_class: measurement` (historial y estadísticas).
- Derivadas: `sensor.glucosa_delta` (mg/dL) y `sensor.glucosa_velocidad` (mg/dL/min).
- Evento `glucose_ng_alert` y notificación persistente.

> **English?** See [README_EN.md](README_EN.md).

## Instalación (HACS - Custom Repository)
1. Sube este repositorio a GitHub (público) y copia la URL.
2. En **HACS → Integrations → + → Custom repositories**, añade la URL y selecciona categoría **Integration**.
3. Instala **Home Assistant Glucose NG** y **reinicia** HA.
4. Añade la integración desde **Ajustes → Dispositivos y servicios** y define:
   - **Shared secret** (seguro)
   - **Umbral bajo/alto** (por defecto 70–180 mg/dL)
   - **Caída rápida** (por defecto 3 mg/dL/min)

## Configurar Juggluco
- URL base de tu HA (sin ruta). Juggluco llamará `/api/v1/entries` o `/api/v3/entries` y `/api/v2/authorization/...`.
- **V1**: header `api-secret` = tu secreto (o `sha1(secret)`).
- **V3**: `Authorization: Bearer <secret>`.

## Prueba rápida
```bash
curl -X POST "http://<HA>:8123/api/v1/entries?token=TU_SECRET"   -H "Content-Type: application/json"   -d '[{"sgv": 123, "direction": "Flat", "date": 1740844800000}]'
```

## Panel Lovelace (ApexCharts)
Instala **apexcharts-card** desde HACS y añade el recurso. Luego crea una vista con:
```yaml
- title: Glucosa
  path: glucosa
  icon: mdi:diabetes
  cards:
    - type: custom:apexcharts-card
      header:
        show: true
        title: Glucosa (24h)
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
                    text: 'Rango objetivo (70–180)'
      series:
        - entity: sensor.glucosa
          name: Glucosa
          type: line
          stroke_width: 3
          color: '#2196F3'
        - entity: sensor.glucosa_velocidad
          name: Velocidad (mg/dL/min)
          yaxis_id: second
          type: area
          color: '#FF6D00'
          opacity: 0.3
      apex_config:
        yaxis:
          - seriesName: Glucosa
          - opposite: true
            decimalsInFloat: 1
            title: { text: 'mg/dL/min' }
```

## Blueprint de alertas
Importa el blueprint en `blueprints/automation/home_assistant_glucose_ng/alerts.yaml` y crea una automatización para:
- Hipo (< low), Hiper (> high)
- Caída rápida (|rate| ≥ rate_drop)

## Licencia
MIT
