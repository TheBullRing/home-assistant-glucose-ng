
## 🌐 Select language / Selecciona idioma

🇬🇧 [English](INSTALACION.md) | 🇪🇸 [Español](INSTALACION.es.md)

# 🔧 Instalación

## Via HACS (recomendado)

1. Accede a HACS ( Instrucciones para instalar HACS: https://www.hacs.xyz)
2. Añade un repositorio personalizado

![InstallRepo](https://raw.githubusercontent.com/TheBullRing/home-assistant-glucose-ng/main/external/capturas/1-InstallRepo.png)
3. Añade la URL del reposotorio https://github.com/TheBullRing/home-assistant-glucose-ng y tipo Integración:

![RepoURL](https://raw.githubusercontent.com/TheBullRing/home-assistant-glucose-ng/main/external/capturas/2-RepoURL.png)

3. Haz click sobre los 3 puntos verticales, y selecciona la opción "Descargar" e instala la última versión.

![Download](https://raw.githubusercontent.com/TheBullRing/home-assistant-glucose-ng/main/external/capturas/3-Download.png)

4. Descarga la última versión:

![DownloadButton](https://raw.githubusercontent.com/TheBullRing/home-assistant-glucose-ng/main/external/capturas/4-DownloadButton.png)

5. Para el dashboard instala card-mod, button-card y plotly-graph:

![Card-Mod](https://raw.githubusercontent.com/TheBullRing/home-assistant-glucose-ng/main/external/capturas/5-Card-Mod.png)

![Button-Card](https://raw.githubusercontent.com/TheBullRing/home-assistant-glucose-ng/main/external/capturas/6-Button-card.png)

![Plotly-Graph](https://raw.githubusercontent.com/TheBullRing/home-assistant-glucose-ng/main/external/capturas/7-Ploty-graph.png)

6. Ves a Configuración > Dispositivos y Servicios > Integraciones > Añadir Integración

![AddIntegration](https://raw.githubusercontent.com/TheBullRing/home-assistant-glucose-ng/main/external/capturas/8-AddIntegration.png)

7. Rellena los valores del sensor, **importante** el "secreto compartido" debe ser el mismo que el que configures en el uploader.

![DefaultValues](https://raw.githubusercontent.com/TheBullRing/home-assistant-glucose-ng/main/external/capturas/9-DefaultValues.png)

8. Pincha en "Terminar" para finalizar la configuración. Puedes definir un Area para el sensor o dejarlo en blanco.

![Finish](https://raw.githubusercontent.com/TheBullRing/home-assistant-glucose-ng/main/external/capturas/10-Finish.png)

9. En Configuración > Dispositivos y Servicios verás la integración instalada.

![IntegrationAdded](https://raw.githubusercontent.com/TheBullRing/home-assistant-glucose-ng/main/external/capturas/11-IntegrationAdded.png)

10. Primera vista de la integración, al no tener lecturas los sensores aparecen como "desconocidos".

![FirstView](https://raw.githubusercontent.com/TheBullRing/home-assistant-glucose-ng/main/external/capturas/12-FirstView.png)

## Instalación manual

1. Copia `custom_components/glucose_ng/` en `config/custom_components/`.
2. Reinicia Home Assistant.

---

# ⚙️ Configuración

Después de reiniciar Home Assistant, añade una entrada de integración por cada dispositivo uploader:

1. Ve a **Configuración → Dispositivos y Servicios → Añadir integración**.
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
# 📈 Dashboard Lovelace (plotly-graph)

Para mostrar gráficas:

1. Instala **plotly-graph** desde HACS junto a **button-card** y **card-mod**
2. Añade una tarjeta como esta: ( Cambia el nombre del sensor sensor glucose_ng_glucosa_glucosa por el que uses)
3. En Home Assistant > Configuración > Paneles de Control  >  Añadir panel de control > "Nuevo Panel de control desde cero"
  - Título: Glucosa
  - Icono: mdi:medication
  - Añadir a la barra lateral selecciona "Sí"
4. En la barra lateral aparece en el menu ahora la opción "Glucosa":
  - Pincha y pincha en el icono del lapiz para editar el panel. 
  - Selecciona los 3 puntos y pincha la opción "Editor de configuración en bruto"
  - Borra lo que aparezca y copia y pega el YAML que se encuentra dentro de dashboard/glucosa.yaml , cambia el nombre del sensor sensor glucose_ng_glucosa_glucosa por el que uses.

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