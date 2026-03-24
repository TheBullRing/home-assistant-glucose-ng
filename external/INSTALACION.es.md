## 🌐 Select language / Selecciona idioma

🇬🇧 [English](INSTALACION.md) | 🇪🇸 [Español](INSTALACION.es.md)

# 🔧 Instalación

## Via HACS (recomendado)

1. Accede a HACS (Instrucciones para instalar HACS: https://www.hacs.xyz)
2. Añade un repositorio personalizado  
   ![InstallRepo](https://raw.githubusercontent.com/TheBullRing/home-assistant-glucose-ng/main/external/capturas/1-InstallRepo.png)
3. Introduce la URL del repositorio:  https://github.com/TheBullRing/home-assistant-glucose-ng Tipo: Integración
   ![RepoURL](https://raw.githubusercontent.com/TheBullRing/home-assistant-glucose-ng/main/external/capturas/2-RepoURL.png)
4. Haz clic en los tres puntos verticales y selecciona **“Descargar”**  
   ![Download](https://raw.githubusercontent.com/TheBullRing/home-assistant-glucose-ng/main/external/capturas/3-Download.png)
5. Descarga la última versión:  
   ![DownloadButton](https://raw.githubusercontent.com/TheBullRing/home-assistant-glucose-ng/main/external/capturas/4-DownloadButton.png)
6. Para el dashboard instala **card-mod**, **button-card** y **plotly-graph**:  
   ![Card-Mod](https://raw.githubusercontent.com/TheBullRing/home-assistant-glucose-ng/main/external/capturas/5-Card-Mod.png)  
   ![Button-Card](https://raw.githubusercontent.com/TheBullRing/home-assistant-glucose-ng/main/external/capturas/6-Button-card.png)  
   ![Plotly-Graph](https://raw.githubusercontent.com/TheBullRing/home-assistant-glucose-ng/main/external/capturas/7-Ploty-graph.png)
7. Ve a **Configuración → Dispositivos y Servicios → Integraciones → Añadir Integración**  
   ![AddIntegration](https://raw.githubusercontent.com/TheBullRing/home-assistant-glucose-ng/main/external/capturas/8-AddIntegration.png)
8. Rellena los valores del sensor. **Importante:** el "Shared Secret" debe coincidir con el configurado en el uploader.  
   ![DefaultValues](https://raw.githubusercontent.com/TheBullRing/home-assistant-glucose-ng/main/external/capturas/9-DefaultValues.png)
9. Haz clic en **“Terminar”**. Puedes asignar un Área o dejarlo vacío.  
   ![Finish](https://raw.githubusercontent.com/TheBullRing/home-assistant-glucose-ng/main/external/capturas/10-Finish.png)
10. Verás la integración instalada:  
   ![IntegrationAdded](https://raw.githubusercontent.com/TheBullRing/home-assistant-glucose-ng/main/external/capturas/11-IntegrationAdded.png)
11. Primera vista: sin lecturas los sensores aparecerán como *desconocidos*.  
   ![FirstView](https://raw.githubusercontent.com/TheBullRing/home-assistant-glucose-ng/main/external/capturas/12-FirstView.png)

## Instalación manual
1. Copia `custom_components/glucose_ng/` en `config/custom_components/`.
2. Reinicia Home Assistant.

---
# ⚙️ Configuración

Tras reiniciar Home Assistant, añade una entrada por cada dispositivo uploader:

Campo | Descripción | Valor por defecto
------ | ----------- | ----------------
**Shared Secret** | Token API configurado en el uploader | (obligatorio)
**Name** | Nombre del dispositivo/persona | Glucosa
**Low threshold** | Límite de hipoglucemia (mg/dL) | 70
**High threshold** | Límite de hiperglucemia (mg/dL) | 180
**Rapid drop** | Alerta cuando la velocidad ≤ N mg/dL/min | 3.0

Cada entrada crea un **Dispositivo**: `Glucose NG — <Name>` con tres sensores.

---
# 📱 Configuración del Uploader

En xDrip, Diabox o Juggluco configura:

Ajuste | Valor
------ | -----
**URL** | https://tu-servidor-ha
**API Secret** | Igual que en Home Assistant
**API version** | v3

Llamadas realizadas:
- `GET https://tu-ha/api/v2/authorization/request/<token>`
- `POST https://tu-ha/api/v3/entries`
- `POST https://tu-ha/api/v3/treatments`

**Nota Nginx:** HA puede eliminar `Authorization`. La integración usa sesión basada en IP durante 5 minutos.

### Configuración Nginx:
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

### HA configuration.yaml:
```yaml
http:
  use_x_forwarded_for: true
  trusted_proxies:
    - 127.0.0.1
    - 192.168.1.0/24
```

---
# 📈 Dashboard Lovelace (plotly-graph)

1. Instala **plotly-graph**, **button-card**, **card-mod**.
2. Crea un nuevo panel (Panel desde cero):
   - Título: Glucosa
   - Icono: mdi:medication
   - Añadir a barra lateral: Sí

![Dashboard1](https://raw.githubusercontent.com/TheBullRing/home-assistant-glucose-ng/main/external/capturas/Dashboard1.png)
![Dashboard2](https://raw.githubusercontent.com/TheBullRing/home-assistant-glucose-ng/main/external/capturas/Dashboard2.png)

3. Edita el panel → Editor de configuración en bruto:  
![Dashboard3](https://raw.githubusercontent.com/TheBullRing/home-assistant-glucose-ng/main/external/capturas/Dashboard3.png)
![Dashboard4](https://raw.githubusercontent.com/TheBullRing/home-assistant-glucose-ng/main/external/capturas/Dashboard4.png)

4. Borra todo y pega el YAML de `dashboard/glucosa.yaml`. Ajusta el sensor si es necesario.  
![Dashboard5](https://raw.githubusercontent.com/TheBullRing/home-assistant-glucose-ng/main/external/capturas/Dashboard5.png)

5. Pulsa **Hecho**  
![Dashboard6](https://raw.githubusercontent.com/TheBullRing/home-assistant-glucose-ng/main/external/capturas/Dashboard6.png)

---
# 🧪 Prueba rápida (curl)
```bash
SECRET="tu_shared_secret"
SECRET_SHA1=$(echo -n "$SECRET" | sha1sum | cut -d' ' -f1)

curl -s "http://TU_HA_IP:8123/api/v2/authorization/request/$SECRET"

curl -X POST "http://TU_HA_IP:8123/api/v3/entries"   -H "Content-Type: application/json"   -H "api-secret: $SECRET_SHA1"   -d '[{"sgv": 120, "date": '"$(date +%s%3N)"', "direction": "Flat", "type": "sgv"}]'

curl -X POST "http://TU_HA_IP:8123/api/v3/treatments"   -H "Content-Type: application/json"   -H "api-secret: $SECRET_SHA1"   -d '[{"eventType": "Correction Bolus", "insulin": 2.5, "created_at": '"$(date -u +"%Y-%m-%dT%H:%M:%SZ")"'}]'
```

---
# 🩻 Troubleshooting

```yaml
logger:
  default: info
  logs:
    custom_components.glucose_ng: debug
    homeassistant.components.http: debug
    aiohttp: debug
    aiohttp.client: debug
    aiohttp.server: debug
```

Problemas comunes:

Síntoma | Causa | Solución
------- | ------ | -------
401 en Nginx | La integración no cargó | Reiniciar HA
WARNING token mismatch | Secret no coincide | Revisar valores
Sensor unknown | Falta campo sgv | Revisar payload

---