# Solax Multi Inverter Integration for Home Assistant
![Solax Logo](https://raw.githubusercontent.com/NoUsername10/Solax-API-2.0-single-and-multiple-inverters-for-Home-assistant/main/custom_components/solax_multi/images/icon.png)

! This code is created in collaboration with AI (chatGPT and DeepSeek) !
If you want to contribute, you are very welcome.

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

Home Assistant custom integration to monitor multiple Solax inverters using the official Solax Cloud V2 API. This integration supports both single and multiple inverter setups with real-time data and system-wide totals.

## Features

Created using the latest API from Solax.
https://www.solaxcloud.com/user_api/SolaxCloud_Monitoring_API_V7.1.pdf

- **🔢 Multiple Inverter Support** - Monitor one or multiple Solax inverters simultaneously
- **🔐 Single API Token** - Use one token for all your inverters
- **📊 Comprehensive Sensors** - Access all available inverter data:
  - AC Output Power (`acpower`)
  - PV Input Power (`powerdc1`, `powerdc2`, `powerdc3`, `powerdc4`)
  - Energy Production (`yieldtoday`, `yieldtotal`)
  - Grid Interaction (`feedinpower`, `feedinenergy`, `consumeenergy`, `feedinpowerM2`)
  - Battery Data (`soc`, `batPower`, `batStatus`)
  - Inverter Status (`inverterStatus`, `inverterType`)
  - EPS Backup Power (`peps1`, `peps2`, `peps3`)
- **🔍 Smart Sensor Creation** - Only creates sensors for available data (no null-value sensors)
- **📈 System Totals** - Combined metrics across all inverters:
  - System AC Power Total
  - System DC Power Total
  - System Yield Today Total
  - System Yield Lifetime Total
- **🎯 Status Mapping** - Human-readable inverter and battery status with raw values in attributes
- **⚙️ Configurable Polling** - Adjustable update interval (default: 120 seconds)
- **🛡️ Rate Limit Protection** - Automatic backoff and retry logic for API limits
- **🔧 Per-Inverter DC Totals** - Individual inverter DC power summation
- **📱 Device Registry Integration** - Proper device creation for each inverter

## Prerequisites

Before installation, you need:
1. **Solax Cloud Account** - Register at [solaxcloud.com](https://www.solaxcloud.com)
2. **API Token** - Obtain from Solax Cloud under **Service → API**
3. **Inverter Serial Numbers** - Wi-Fi module serial numbers

## Installation

### Method 1: HACS (Recommended)

1. Open **HACS** in your Home Assistant
2. Click on **Integrations**
3. Click the three dots in the top right corner → **Custom repositories**
4. Add this repository URL:  
   `https://github.com/NoUsername10/Solax-API-2.0-single-and-multiple-inverters-for-Home-assistant`
5. Select **Integration** as the category
6. Click **Add**
7. Search for "Solax Multi Inverter" and install
8. Restart Home Assistant

### Method 2: Manual Installation

1. Download the latest release
2. Copy the `custom_components/solax_multi` folder to your Home Assistant `custom_components` directory
3. Restart Home Assistant

## Configuration

### Initial Setup
1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for **"Solax Multi Inverter"**
4. Enter your configuration:
   - **API Token**: Your Solax Cloud API token
   - **System Name**: Name for your solar system (used for system total sensors)
   - **Scan Interval**: Polling frequency in seconds (default: 120, minimum: 120)

### Adding Inverters
5. After initial setup, you'll be guided to add inverters one by one
6. Enter each inverter's Wi-Fi module serial number
7. Check "Finish Setup" when all inverters are added

### Managing Inverters
To add or remove inverters later:
1. Go to your Solax Multi Inverter integration
2. Click **Configure**
3. Add new serial numbers or remove existing ones
4. Click **Save Changes**

## Important Notes

- **📊 Data Refresh Rate**: The Solax Cloud API typically updates data every 5 minutes. Even with a shorter scan interval, you'll only get new data when the cloud updates.
- **🔐 Token Validation**: Your API token is validated during setup to ensure it's correct
- **⚡ API Rate Limits**: The integration includes automatic rate limit protection with progressive delays between inverters
- **🔧 Dynamic Sensors**: Sensors are automatically created based on available data from your specific inverter model
- **🔄 Automatic Retry**: Temporary API errors are handled gracefully with retry logic

## Supported Inverter Types

This integration supports various Solax inverter models including:
- Solax X1 Mini
- Solax X1 Boost
- Solax X1 Pro  
- Solax X3
- Solax X1 Micro 2 in 1
- And more...

If you have an inverter type that you want to add to the mapping, please make a pull request.

## Sensor Information

### Per-Inverter Sensors
Each inverter gets its own set of sensors with names like:
- `Solax AC Output Power [Serial]`
- `Solax Battery State of Charge [Serial]`
- `Solax DC Power Inverter Total [Serial]`

### System Total Sensors
System-wide totals are created with your system name:
- `[System Name] System AC Power`
- `[System Name] System DC Power`
- `[System Name] System Yield Today`
- `[System Name] System Yield Lifetime`

### Sensor Attributes
- Status sensors include both human-readable text and raw numeric values
- All sensors include timestamp information
- System total sensors show active/total inverter count

## Troubleshooting

**No data appearing?**
- Verify your API token is correct (it's validated during setup)
- Check inverter serial numbers are accurate (Wi-Fi module SN, not inverter SN)
- Ensure inverters are connected to Solax Cloud and reporting data
- Check Home Assistant logs for specific error messages

**Rate limiting warnings?**
- Increase your scan interval (recommended: 300+ seconds for multiple inverters)
- The integration automatically handles rate limits with backoff logic

**Missing sensors?**
- Some sensors only appear if your inverter supports that feature
- Battery sensors only appear if you have battery storage
- PV channel sensors depend on your inverter's configuration
- EPS sensors only appear if you have backup power capability

**Configuration issues?**
- Use the integration's configure option to add/remove inverters
- The system will automatically reload when changes are saved

## Contributing

Found a bug or have a feature request? Please open an issue on GitHub.

Want to add support for more inverter types or features? Pull requests are welcome!

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Disclaimer

This integration is not officially affiliated with Solax Power. Use at your own risk 😅

---

**Note**: This integration is designed to be robust and user-friendly, with proper error handling and rate limit protection to ensure reliable operation with the Solax Cloud API.
