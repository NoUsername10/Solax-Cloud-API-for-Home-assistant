# Solax Multi Inverter Integration for Home Assistant
![Solax Logo](https://raw.githubusercontent.com/NoUsername10/Solax-API-2.0-single-and-multiple-inverters-for-Home-assistant/main/custom_components/solax_multi/images/logo.png)

! This code is created with AI (chatGPT and DeepSeek) !
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
  - Grid Interaction (`feedinpower`, `feedinenergy`, `consumeenergy`)
  - Battery Data (`soc`, `batPower`, `batStatus`)
  - Inverter Status (`inverterStatus`, `inverterType`)
- **🔍 Smart Sensor Creation** - Only creates sensors for available data (no null-value sensors)
- **📈 System Totals** - Combined metrics across all inverters:
  - Total AC Power
  - Total DC Power  
  - Total Daily Yield
  - Total Lifetime Yield
- **🎯 Status Mapping** - Human-readable inverter and battery status
- **⚙️ Configurable Polling** - Adjustable update interval (default: 60 seconds)

## Prerequisites

Before installation, you need:
1. **Solax Cloud Account** - Register at [solaxcloud.com](https://www.solaxcloud.com)
2. **API Token** - Obtain from Solax Cloud under **Service → API**
3. **Inverter Serial Numbers** - Wi-Fi module SNs (comma-separated)

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

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for **"Solax Multi Inverter"**
4. Enter your configuration:
   - **API Token**: Your Solax Cloud API token
   - **Inverter Serial Numbers**: Comma-separated list of Wi-Fi module SNs
   - **Scan Interval**: Optional, polling frequency in seconds (default: 60)

## Important Notes

- **📊 Data Refresh Rate**: The Solax Cloud API typically updates data every 5 minutes. Even with a shorter scan interval, you'll only get new data when the cloud updates.
- **🔐 Token Security**: Keep your API token secure and never share it publicly
- **⚡ API Limits**: Be reasonable with scan intervals to avoid API throttling
- **🔧 Dynamic Sensors**: Sensors are automatically created/deprecated based on available data from your specific inverter model

## Supported Inverter Types

This integration supports various Solax inverter models including:
- Solax X1 Mini
- Solax X1 Boost
- Solax X1 Pro  
- Solax X3
- Solax X1 Micro 2 in 1
- And more...

- If you have an inverter that you want to add, please make a pull request.

## Sensor Naming

Sensors follow this naming pattern:
- Per-inverter: `Solax {field} {serial}`
- System totals: `Solax {metric} Total System`

## Troubleshooting

**No data appearing?**
- Verify your API token is correct
- Check inverter serial numbers are accurate
- Ensure inverters are connected to Solax Cloud
- Check Home Assistant logs for error messages

**Missing sensors?**
- Some sensors only appear if your inverter supports that feature
- Battery sensors only appear if you have battery storage
- PV channel sensors depend on your inverter's configuration

## Contributing

Found a bug or have a feature request? Please open an issue on GitHub.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Disclaimer

This integration is not officially affiliated with Solax Power. Use at your own risk.
