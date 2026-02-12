# Solax Cloud API for Single and Multi Inverter Systems
<img src="https://raw.githubusercontent.com/NoUsername10/Solax-Cloud-API-for-Home-assistant/main/assets/icon.png" width=20% height=20%>

Home Assistant custom integration to monitor Solax inverters using the official Solax Cloud API V2.0. <br>
Supports both single and multi-inverter systems, dynamic sensors, system totals, and reliability-focused error handling.

This integration was developed with AI-assisted collaboration and practical testing in real Home Assistant setups.<br>
It has been iteratively improved with a focus on reliability, maintainability, and Home Assistant best practices.<br>
Contributions, issues, and pull requests are welcome.<br>


[![coffee_badge](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-donate-orange.svg)](https://www.buymeacoffee.com/DefaultLogin)

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)




Total System information (this system contains 3 micro-inverters): <br>
<img src="https://raw.githubusercontent.com/NoUsername10/Solax-Cloud-API-for-Home-assistant/main/assets/info%20system.png" width=50% height=50%>

Single-inverter info: <br>
<img src="https://raw.githubusercontent.com/NoUsername10/Solax-Cloud-API-for-Home-assistant/main/assets/info%20inverter.png" width=50% height=50%>

Example of displaying useful information: <br>
Total DC (sun) input, Total AC output from the system, and efficiency of DC/AC conversion. <br>
As the system has micro inverters, we can also see individual panel performance. <br>
<img src="https://raw.githubusercontent.com/NoUsername10/Solax-Cloud-API-for-Home-assistant/main/assets/info%20solar%20panels.png" width=50% height=50%>

Individual DC string performance over the day.<br>
One of the panels is in some shade during the winter months.<br>
<img src="https://raw.githubusercontent.com/NoUsername10/Solax-Cloud-API-for-Home-assistant/main/assets/info%20DC%20strings.png" width=50% height=50%>





## ✨ Features

Created using the latest Solax API documentation:
https://www.solaxcloud.com/user_api/SolaxCloud_Monitoring_API_V7.1.pdf

- **Single Integration Instance** - One config entry for a full site (single- or multi-inverter)
- **Single API Token** - One token for all configured inverter serials
- **Dynamic Sensor Creation** - Creates only sensors with real API data
- **Per-Inverter Metrics** - Power, yield, battery, EPS, status/type, and upload timestamps
- **Computed Per-Inverter Sensors** - DC total and inverter efficiency
- **System Totals Device** - AC/DC totals, yield today/lifetime, system efficiency, system health, and API rate-limit status
- **Per-Inverter API Access Status** - `OK`, `Rate Limited`, `Serial Unauthorized`, `API Error`
- **Resilient API Handling** - Rate-limit cooldown and clear status reporting
- **Smart Reload on Config Changes** - New inverter(s) are queried first; unchanged inverters keep cached values
- **Invalid Serial Handling (1003)** - Unauthorized serials are marked unavailable and clearly surfaced
- **Options Flow Safety Popups** - Acknowledgment dialogs for rate limits and invalid serial/access
- **Persistent Notifications + Toggle** - Rate-limit notifications can be enabled/disabled from System Totals
- **Entity/Device Cleanup** - Removed serials clean up stale entities/devices from the registry
- **Stable Entity Prefix** - Entity IDs remain stable when system name changes
- **UI Language Support** - Built-in translations for English (`en`), Swedish (`sv`), and Spanish (`es`)

## ✅ Prerequisites

Before installation, you need:
1. **Solax Cloud Account** - Register at [solaxcloud.com](https://www.solaxcloud.com)
2. **API Token** - Obtain from Solax Cloud under **Service → Third-party Ecosystem**
3. **Inverter Serial Numbers** - Wi-Fi module serial (or SN for microinverters) under **Devices**

## 📦 Installation

### Method 1: HACS (Recommended)

1. Open **HACS** in your Home Assistant
2. Click on **Integrations**
3. Click the three dots in the top right corner → **Custom repositories**
4. Add this repository URL:  
   `https://github.com/NoUsername10/Solax-Cloud-API-for-Home-assistant`
5. Select **Integration** as the category
6. Click **Add**
7. Search for "Solax Cloud API" and install
8. Restart Home Assistant

### Method 2: Manual Installation

1. Download the latest release
2. Copy the `custom_components/solax_cloud_api` folder to your Home Assistant `custom_components` directory
3. Restart Home Assistant

## ⚙️ Configuration

### 🚀 Initial Setup
1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for **"Solax Cloud API"**
4. Enter your configuration:
   - **API Token**: Your Solax Cloud API token
   - **System Name**: Name for your solar system (used for system total sensors and entity ID prefix)
   - **Scan Interval**: Polling frequency in seconds (default: 120, minimum suggested: 120)

### ➕ Adding Inverters
5. After initial setup, you'll be guided to add inverter serials one by one
6. Enter each inverter's Wi-Fi module serial number
7. Check "Finish Setup" when all inverters are added

### 🧩 Managing Inverters
To add or remove inverters later:
1. Go to your Solax Cloud API integration
2. Click **Configure**
3. Add new serial numbers or remove existing ones
4. Click **Save Changes**

After saving, the integration reloads automatically and validates the result.  
If rate limits or invalid serial/access errors are detected, you get a GUI popup (options flow) and a persistent notification.

## 📝 Important Notes

- **📊 Data Refresh Rate**: Solax Cloud typically updates values about every 5 minutes.
- **⏱️ Polling Model**: One shared interval is used, and configured inverters are queried sequentially.
- **🔐 Token Validation**: API token is validated during setup and when changed in options.
- **💾 Transient Error Retention**: The last good values are retained during temporary rate limits/API issues.
- **🔧 Dynamic Sensors**: Entities are created based on real fields returned for your inverter model.

## 🔌 Supported Inverter Types

This integration currently includes the following inverter type names:
- X1-LX
- X-Hybrid
- X1-Hybiyd/Fit
- X1-Boost/Air/Mini
- X3-Hybrid-G1/G2
- X3-20K/30K
- X3-MIC/PRO
- X1-Smart
- X1-AC
- A1-Hybrid
- A1-FIT
- A1
- J1-ESS
- X3-Hybrid-G4
- X1-Hybrid-G4
- X3-MIC/PRO-G2
- X1-SPT
- X1-Boost-G4
- A1-HYB-G2
- A1-AC-G2
- A1-SMT-G2
- X1-Mini-G4
- X1-IES
- X3-IES
- X3-ULT
- X1-SMART-G2
- A1-Micro 1 in 1
- X1-Micro 2 in 1
- X1-Micro 4 in 1
- X3-AELIO
- X3-HYB-G4 PRO
- X3-NEO-LV
- X1-VAST
- X3-IES-P
- J3-ULT-LV-16.5K
- J3-ULT-30K
- J1-ESS-HB-2
- C3-IES
- X3-IES-A
- X1-IES-A
- X3-ULT-GLV
- X1-MINI-G4 PLUS
- X1-Reno-LV
- A1-HYB-G3
- X3-FTH
- X3-MGA-G2
- X1-Hybrid-LV
- X1-Lite-LV
- X3-GRAND-HV
- X3-FORTH-PLUS

If any inverter type name is missing or incorrect, please open a pull request.

## 📊 Sensor Information

### Per-Inverter Sensors
Each inverter gets its own set of sensors with entity IDs like:
- `[System Name] AC Output Power [Serial]`
- `[System Name] Battery State of Charge [Serial]`
- `[System Name] DC Power Inverter Total [Serial]`

### System Total Sensors
System-wide totals:
- `System AC Power`
- `System DC Power`
- `System Yield Today`
- `System Yield Lifetime`
- `System Total Efficiency`

### Diagnostic / Control Entities
- `API Access Status [Serial]` (diagnostic): API access health for each inverter
- `System Health` (diagnostic): overall health status across configured inverters
- `API Rate Limit Status` (diagnostic): current API rate-limit state
- `Last Poll Attempt` (diagnostic, disabled by default): timestamp of the latest coordinator poll attempt
- `Next Scheduled Poll` (diagnostic, disabled by default): timestamp of the next planned poll
- `API Rate Limit Notifications` (switch under System Totals): toggle persistent rate-limit notifications

### Sensor Attributes
- Status sensors include both human-readable text and raw numeric values
- All sensors include timestamp information
- System total sensors show active/total inverter count

## 🛠️ Troubleshooting

**No data appearing?**
- Verify your API token is correct (it is validated during setup)
- Check inverter serial numbers are accurate (Wi-Fi module SN, not inverter SN)
- Ensure inverters are connected to Solax Cloud and reporting data
- Check Home Assistant logs for specific error messages

**Rate limiting warnings?**
- Increase your scan interval (recommended: 120+ seconds for multi-inverter systems)
- The integration automatically handles rate limits with backoff logic
- Check `API Rate Limit Status` and per-inverter `API Access Status`

**Wrong serial / no auth (1003)?**
- You will get an invalid serial/access persistent notification
- During options changes, you also get an acknowledgment popup
- Affected inverter remains unavailable until serial/access is corrected

**Missing sensors?**
- Some sensors only appear if your inverter supports that feature
- Battery sensors only appear if you have battery storage
- PV channel sensors depend on your inverter's configuration
- EPS sensors only appear if you have backup power capability

**Configuration issues?**
- Use the integration's configure option to add/remove inverters
- The system automatically reloads when changes are saved
- Removed inverters are cleaned from registry, and new ones are fetched first

**Need an immediate refresh test?**
- Call the Home Assistant action/service `solax_cloud_api.manual_refresh`
- This triggers an instant fetch outside the normal scan interval

## 🤝 Contributing

Found a bug or have a feature request? Please open an issue on GitHub. <br>
Want to add support for more inverter types or features? Pull requests are welcome!<br>

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## ⚠️ Disclaimer

This integration is not officially affiliated with Solax Power.

---

**Note**: This integration is designed to be robust and user-friendly, with proper error handling and rate limit protection to ensure reliable operation with the Solax Cloud API.
