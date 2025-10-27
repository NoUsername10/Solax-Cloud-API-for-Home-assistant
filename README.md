# Solax Multi Inverter

Home Assistant custom integration to read multiple Solax inverters from the Solax Cloud v2 API.

Features
- Multiple inverter support (add serial numbers in the integration UI)
- Single shared API token for all inverters
- Per-inverter sensors: acpower, powerdc1, powerdc2, powerdc3, powerdc4, yieldtoday, yieldtotal, inverterType, inverterStatus, batStatus, etc.
- Mapped inverter status and error codes
- System total sensors that combines all the inverters (AC, DC, yields)
- Configurable scan interval in the integration UI (Solax API updates data every 5 min, so even if you set to 60s, 5 min is the interval new data is provided)

Installation
1. Copy the `custom_components/solax_multi` folder into your Home Assistant `custom_components` folder.
2. Restart Home Assistant.
3. In Home Assistant, go to **Settings → Devices & Services → + Add Integration → Solax Multi Inverter** and enter your API token and inverter serials (comma-separated). Optionally set the polling interval.

Notes
- Keep the scan interval reasonable to avoid API throttling (default: 60s).
- This is a template repo. Replace documentation and codeowners in manifest.json before publishing.
