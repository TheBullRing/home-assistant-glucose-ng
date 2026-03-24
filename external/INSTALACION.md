## 🌐 Select language / Selecciona idioma

🇬🇧 [English](INSTALACION.md) | 🇪🇸 [Español](INSTALACION.es.md)

# 🔧 Installation

## Via HACS (recommended)

1. Go to HACS (Instructions to install HACS: https://www.hacs.xyz)
2. Add a custom repository  
   ![InstallRepo](https://raw.githubusercontent.com/TheBullRing/home-assistant-glucose-ng/main/external/capturas/1-InstallRepo.png)
3. Enter the repository URL: https://github.com/TheBullRing/home-assistant-glucose-ng  
   Type: Integration  
   ![RepoURL](https://raw.githubusercontent.com/TheBullRing/home-assistant-glucose-ng/main/external/capturas/2-RepoURL.png)
4. Click on the three vertical dots and select **“Download”**  
   ![Download](https://raw.githubusercontent.com/TheBullRing/home-assistant-glucose-ng/main/external/capturas/3-Download.png)
5. Download the latest version:  
   ![DownloadButton](https://raw.githubusercontent.com/TheBullRing/home-assistant-glucose-ng/main/external/capturas/4-DownloadButton.png)
6. For the dashboard, install **card-mod**, **button-card**, and **plotly-graph**:  
   ![Card-Mod](https://raw.githubusercontent.com/TheBullRing/home-assistant-glucose-ng/main/external/capturas/5-Card-Mod.png)  
   ![Button-Card](https://raw.githubusercontent.com/TheBullRing/home-assistant-glucose-ng/main/external/capturas/6-Button-card.png)  
   ![Plotly-Graph](https://raw.githubusercontent.com/TheBullRing/home-assistant-glucose-ng/main/external/capturas/7-Ploty-graph.png)
7. Go to **Settings → Devices & Services → Integrations → Add Integration**  
   ![AddIntegration](https://raw.githubusercontent.com/TheBullRing/home-assistant-glucose-ng/main/external/capturas/8-AddIntegration.png)
8. Fill in the sensor values. **Important:** the "Shared Secret" must match the one configured in the uploader.  
   ![DefaultValues](https://raw.githubusercontent.com/TheBullRing/home-assistant-glucose-ng/main/external/capturas/9-DefaultValues.png)
9. Click **“Finish”**. You may assign an Area or leave it empty.  
   ![Finish](https://raw.githubusercontent.com/TheBullRing/home-assistant-glucose-ng/main/external/capturas/10-Finish.png)
10. You will see the installed integration:  
   ![IntegrationAdded](https://raw.githubusercontent.com/TheBullRing/home-assistant-glucose-ng/main/external/capturas/11-IntegrationAdded.png)
11. First view: since there are no readings yet, the sensors will appear as *unknown*.  
   ![FirstView](https://raw.githubusercontent.com/TheBullRing/home-assistant-glucose-ng/main/external/capturas/12-FirstView.png)

## Manual installation
1. Copy `custom_components/glucose_ng/` into `config/custom_components/`.
2. Restart Home Assistant.

---
# ⚙️ Configuration
After restarting Home Assistant, add one entry for each uploader device:

Field   Description   Default value
------   -----------   -------------
**Shared Secret**   API token configured in the uploader   (required)
**Name**   Device/person name   Glucose
**Low threshold**   Hypoglycemia limit (mg/dL)   70
**High threshold**   Hyperglycemia limit (mg/dL)   180
**Rapid drop**   Alert when the rate ≤ N mg/dL/min   3.0
Each entry creates a **Device**: `Glucose NG — <Name>` with three sensors.

---
# 📱 Uploader Configuration
In xDrip, Diabox or Juggluco configure:

Setting   Value
------   -----
**URL**   https://your-ha-server
**API Secret**   Same as in Home Assistant
**API version**   v3
Calls performed:
- `GET https://your-ha/api/v2/authorization/request/<token>`
- `POST https://your-ha/api/v3/entries`
- `POST https://your-ha/api/v3/treatments`
**Nginx Note:** HA may remove `Authorization`. The integration uses an IP-based session for 5 minutes.

### Nginx configuration:
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
# 📈 Lovelace Dashboard (plotly-graph)
1. Install **plotly-graph**, **button-card**, **card-mod**.
2. Create a new panel (Blank panel):
 - Title: Glucose
 - Icon: mdi:medication
 - Add to sidebar: Yes
![Dashboard1](https://raw.githubusercontent.com/TheBullRing/home-assistant-glucose-ng/main/external/capturas/Dashboard1.png)
![Dashboard2](https://raw.githubusercontent.com/TheBullRing/home-assistant-glucose-ng/main/external/capturas/Dashboard2.png)
3. Edit the panel → Raw configuration editor:
![Dashboard3](https://raw.githubusercontent.com/TheBullRing/home-assistant-glucose-ng/main/external/capturas/Dashboard3.png)
![Dashboard4](https://raw.githubusercontent.com/TheBullRing/home-assistant-glucose-ng/main/external/capturas/Dashboard4.png)
4. Delete everything and paste the YAML from `dashboard/glucosa.yaml`. Adjust the sensor if needed.
![Dashboard5](https://raw.githubusercontent.com/TheBullRing/home-assistant-glucose-ng/main/external/capturas/Dashboard5.png)
5. Click **Done**
![Dashboard6](https://raw.githubusercontent.com/TheBullRing/home-assistant-glucose-ng/main/external/capturas/Dashboard6.png)

---
# 🧪 Quick test (curl)
```bash
SECRET="your_shared_secret"
SECRET_SHA1=$(echo -n "$SECRET"  sha1sum  cut -d' ' -f1)

curl -s "http://YOUR_HA_IP:8123/api/v2/authorization/request/$SECRET"
curl -X POST "http://YOUR_HA_IP:8123/api/v3/entries" -H "Content-Type: application/json" -H "api-secret: $SECRET_SHA1" -d '[{"sgv": 120, "date": '"$(date +%s%3N)"', "direction": "Flat", "type": "sgv"}]'
curl -X POST "http://YOUR_HA_IP:8123/api/v3/treatments" -H "Content-Type: application/json" -H "api-secret: $SECRET_SHA1" -d '[{"eventType": "Correction Bolus", "insulin": 2.5, "created_at": '"$(date -u +"%Y-%m-%dT%H:%M:%SZ")"'}]'
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
Common problems:

Symptom   Cause   Solution
-------   ------   -------
401 in Nginx   Integration did not load   Restart HA
WARNING token mismatch   Secret does not match   Verify values
Sensor unknown   Missing sgv field   Check payload
