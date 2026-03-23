
## 🌐 Select language / Selecciona idioma

🇬🇧 [English](INSTALACION.md) | 🇪🇸 [Español](INSTALACION.es.md)

# 🔧 Installation

## Via HACS (recommended)
1. Open HACS (Instructions to install HACS: https://www.hacs.xyz)
2. Add a custom repository:
![InstallRepo](https://raw.githubusercontent.com/TheBullRing/home-assistant-glucose-ng/main/external/capturas/1-InstallRepo.png)
3. Add the repository URL `https://github.com/TheBullRing/home-assistant-glucose-ng` and set type to **Integration**:
![RepoURL](https://raw.githubusercontent.com/TheBullRing/home-assistant-glucose-ng/main/external/capturas/2-RepoURL.png)
4. Click the 3‑dot menu and select **Download**, then install the latest version:
![Download](https://raw.githubusercontent.com/TheBullRing/home-assistant-glucose-ng/main/external/capturas/3-Download.png)
5. Download the latest release:
![DownloadButton](https://raw.githubusercontent.com/TheBullRing/home-assistant-glucose-ng/main/external/capturas/4-DownloadButton.png)
6. For the dashboard, install **card-mod**, **button-card**, and **plotly-graph**:
![Card-Mod](https://raw.githubusercontent.com/TheBullRing/home-assistant-glucose-ng/main/external/capturas/5-Card-Mod.png)
![Button-Card](https://raw.githubusercontent.com/TheBullRing/home-assistant-glucose-ng/main/external/capturas/6-Button-card.png)
![Plotly-Graph](https://raw.githubusercontent.com/TheBullRing/home-assistant-glucose-ng/main/external/capturas/7-Ploty-graph.png)
7. Go to **Settings → Devices & Services → Integrations → Add Integration**:
![AddIntegration](https://raw.githubusercontent.com/TheBullRing/home-assistant-glucose-ng/main/external/capturas/8-AddIntegration.png)
8. Fill in the sensor configuration. **Important:** the *shared secret* must match the one configured in your uploader:
![DefaultValues](https://raw.githubusercontent.com/TheBullRing/home-assistant-glucose-ng/main/external/capturas/9-DefaultValues.png)
9. Click **Finish**. You may assign an Area or leave it blank:
![Finish](https://raw.githubusercontent.com/TheBullRing/home-assistant-glucose-ng/main/external/capturas/10-Finish.png)
10. The integration will appear under **Settings → Devices & Services**:
![IntegrationAdded](https://raw.githubusercontent.com/TheBullRing/home-assistant-glucose-ng/main/external/capturas/11-IntegrationAdded.png)
11. First view of the integration — without readings, sensors appear as *unknown*:
![FirstView](https://raw.githubusercontent.com/TheBullRing/home-assistant-glucose-ng/main/external/capturas/12-FirstView.png)

## Manual Installation
1. Copy `custom_components/glucose_ng/` into `config/custom_components/`.
2. Restart Home Assistant.

---
# ⚙️ Configuration
After restarting HA, add one integration entry per uploader device:
1. Go to **Settings → Devices & Services → Add integration**.
2. Search for **Glucose NG**.
3. Fill out the form:

### Field descriptions
**Shared Secret** — API token used by the uploader (must be unique per device).  
**Name** — Name of the person/device (used to name sensors). Default: *Glucose*.  
**Low threshold** — Lower mg/dL limit for hypoglycemia alert. Default: *70*.  
**High threshold** — Upper mg/dL limit for hyperglycemia alert. Default: *180*.  
**Rapid drop** — Alert when rate ≤ N mg/dL/min. Default: *3.0*.

Each entry creates a **Device** in HA named `Glucose NG — <Name>` containing three sensors.

---
# 📱 Uploader Configuration
In your uploader app (xDrip, Diabox, Juggluco), configure **Nightscout**:

| Setting | Value |
|--------|-------|
| URL | `https://your-ha-server` (no extra path) |
| API Secret | The same Shared Secret used in HA |
| API Version | `v3` |

Uploader performs:
- `GET https://your-ha/api/v2/authorization/request/<token>` → Token validation.
- `POST https://your-ha/api/v3/entries` → Send glucose readings.
- `POST https://your-ha/api/v3/treatments` → Send treatments.

**Note for Nginx users:** Home Assistant may strip the `Authorization` header. Glucose NG works around this with a 5‑min IP‑based session.

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
# 📈 Lovelace Dashboard (plotly-graph)
1. Install **plotly-graph**, **button-card**, **card-mod** from HACS.
2. Add a card (replace sensor name with yours).
3. Go to **Settings → Dashboards → Add Dashboard → Empty Dashboard**:
   - Title: *Glucose*
   - Icon: `mdi:medication`
   - Add to sidebar: Yes
4. Edit Dashboard → Raw configuration editor → paste YAML from `dashboard/glucosa.yaml` (replace sensor name).

---
# 🧪 Quick Test (curl)
```bash
SECRET="your_shared_secret"
SECRET_SHA1=$(echo -n "$SECRET" | sha1sum | cut -d' ' -f1)

# Test auth
curl -s "http://YOUR_HA_IP:8123/api/v2/authorization/request/$SECRET"

# Send reading
date_ms=$(date +%s%3N)
curl -X POST "http://YOUR_HA_IP:8123/api/v3/entries"   -H "Content-Type: application/json"   -H "api-secret: $SECRET_SHA1"   -d "[{"sgv":120, "date":$date_ms, "direction":"Flat", "type":"sgv"}]"

# Send treatment (insulin)
curl -X POST "http://YOUR_HA_IP:8123/api/v3/treatments"   -H "Content-Type: application/json"   -H "api-secret: $SECRET_SHA1"   -d "[{"eventType":"Correction Bolus", "insulin":2.5, "created_at":"$(date -u +%Y-%m-%dT%H:%M:%SZ)"}]"
```
Expected response: `{"ok": true, "count": 1}`.

Then check **Developer Tools → States** for `sensor.<name>`.

---
# 🩻 Troubleshooting
Enable detailed logs in `configuration.yaml`:
```yaml
logger:
  default: info
  logs:
    custom_components.glucose_ng: debug
```
Restart HA and check **Settings → System → Logs**.

### Common issues:
| Symptom | Probable Cause | Solution |
|---------|----------------|----------|
| 401 in Nginx logs, nothing in HA | Integration didn't load | Restart HA and check errors |
| "WARNING: token did not match" | Secret mismatch | Ensure uploader and HA secrets match exactly |
| Sensor shows `unknown` | Missing `sgv` in payload | Check uploader POST body |

---
