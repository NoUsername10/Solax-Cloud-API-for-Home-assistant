# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Planned]
- Add System health Notifications switch and messaging (with error message, inverter info etc)
- Individual DC string performance over the day comparison (fault finding) for all panels.
- Refactor sensor.py into smaller modules (field, system totals, estimated battery, shared helpers) 
- Improve the rate limited messages for clarity.

## [Unreleased]
- No changes yet.

## [v0.1.9.1] - 2026-03-18

### Release Notes
- Estimated battery energy sensors for battery charge and discharge, calculated from the Power (W) sensor `batPower`.
- Estimated battery sensors are created only when at least one inverter has battery data (`batPower`).
- Estimated battery sensors are disabled by default to keep the UI Solax API data only, as these sensors are calculated from API data, and is not actual API data.
- Lithuanian (`lt`) translation file (thank you @basas!).


### Added (Caluculated sensors ONLY, not available from Solax API)
- Added estimated battery energy sensors per inverter:
  - `Estimated Battery Charge Energy Today`
  - `Estimated Battery Charge Energy Total`
  - `Estimated Battery Discharge Energy Today`
  - `Estimated Battery Discharge Energy Total`
- Added estimated system battery energy sensors (system totals):
  - `Estimated System Battery Charge Energy Today`
  - `Estimated System Battery Charge Energy Total`
  - `Estimated System Battery Discharge Energy Today`
  - `Estimated System Battery Discharge Energy Total`


### Changed
- Config and options flow notice checkboxes now use a stable internal key (`acknowledge`) while keeping the translated UI text unchanged.
- Config-flow API checks now use Home Assistant's shared HTTP session helper (`async_get_clientsession`) instead of ad-hoc client sessions.
- Removed explicit `aiohttp` requirement from `manifest.json` (HA-core managed dependency path).


### Fixed
- Removed raw YAML import payload logging to avoid accidental token exposure in debug logs.
- Rate-limit cooldown logic now uses a fresh monotonic timestamp per inverter iteration (no stale-time drift in cooldown calculations).
- Hardened entity-prefix slug generation by switching to Home Assistant `slugify(...)` with a safe fallback of `solax_cloud_api` when slug output is empty.
- Applied the same safe slug fallback path in config flow, sensor setup, and switch setup to prevent invalid entity-prefix values from special characters.


## [v0.1.9.0] - 2026-03-16

### Release Notes
- Brand and diagnostics release focused on easier troubleshooting and privacy-safe debug data.

### Added
- Added local brand assets under `custom_components/solax_cloud_api/brand` for Home Assistant's new Brands Proxy API path.
- Added Home Assistant diagnostics export with the latest full pre-filter Solax API response per inverter (latest only), including battery field summaries for debugging missing battery entities.

### Changed
- Brand assets are now resolved by integration domain (`solax_cloud_api`) and served by Home Assistant's local brands API path (`/api/brands/integration/{domain}/{image}`), with no extra integration code required.
- Diagnostics are available via Home Assistant's built-in integration action: `Download diagnostics` with partial serial and token masking in exported payloads while preserving support-relevant context.

### Privacy
- Diagnostics intentionally redact sensitive token fields and mask serial data.
- Home Assistant diagnostics packages may still include platform/environment metadata outside this integration's payload.

## [v0.1.8.9] - 2026-03-16

### Release Notes
- Translations and i18n consistency.

### Changed
- Updated Readme.md instructions regarding what serial number to use during setup and getting the API key.
- Added translation files for de, nl, cs, pl, pt, it, fr, da, nb, and fi.
- Standardized the integration translation title globally to `Solax Cloud API SolaXCloud` across all locale files.

## [v0.1.8.8] - 2026-02-19

### Release Notes
- Removed duplicated folder from root.

## [v0.1.8.7] - 2026-02-12

### Release Notes
- Clean version after passing HACS and Hassfest validations.


## [v0.1.8.6] - 2026-02-12

### Release Notes
- Patch release focused on translation quality and release validation hardening.
- Keeps `v0.1.8.5` feature history intact and adds a clear delta for this bump.

### Added
- Spanish (`es`) UI translations.
- Translation key guard script (`scripts/check_translation_keys.py`) for CI.

### Changed
- CI now validates translation keys and language parity before Hassfest.
- Integration version bumped to `v0.1.8.6`.

### Fixed
- Prevented translation-key regressions that can fail Hassfest validation.


## [v0.1.8.5] - 2026-02-12

### Release Notes
- This release focuses on production hardening for setup/reload behavior, API rate-limit handling, and invalid-serial (`1003`) handling.
- System diagnostics and usability were expanded with clear status sensors, polling diagnostics, and a rate-limit notifications control in System Totals.

### Added
- Per-inverter `API Access Status` diagnostic sensor.
- Persistent invalid-serial/access notifications with clear `1003` details.
- Options-flow acknowledgement popup for invalid serial/access during reload.
- API rate-limit notifications toggle (`API Rate Limit Notifications`) in System Totals.
- Initial-setup preflight classification cache to reuse first API results.
- Rate-limit and invalid-serial GUI notices in setup/options flows.
- System polling diagnostics:
  - `Last Poll Attempt` (diagnostic, disabled by default)
  - `Next Scheduled Poll` (diagnostic, disabled by default)
- System-level rate-limit diagnostic details in attributes (affected inverters, counts, details).

### Changed
- Integration name shortened to `Solax Cloud API for Single and Multi Inverter Systems`.
- Setup/options flow validation hardened for token and serial handling.
- Reload behavior improved to keep cached good values and prioritize newly added inverters when token is unchanged.
- System total friendly names no longer include the system-name prefix.
- `System Health` and `API Rate Limit Status` moved to diagnostics in System Totals.
- `Last Poll Attempt` and `Next Scheduled Poll` kept as diagnostics and disabled by default.
- README rewritten and expanded (features, diagnostics, troubleshooting, supported inverter names).
- System-total device model text kept static (`Single Inverter System` / `Multi-Inverter System`).
- Entity creation logic updated so only fields with non-null API data become entities.
- Translation usage cleaned up for switch/sensor friendly names and diagnostics labels.
- Entity prefix stability preserved when changing system name.

### Fixed
- Correct handling of Solax API rate-limit responses (including code `104` and related API messages).
- Correct handling and precedence of `1003 Data Unauthorized` (invalid serial/no access).
- Duplicate serial checks in flow without unnecessary API calls.
- Dynamic sensor creation now avoids creating sensors for null-only fields.
- Removed serials now clean up stale entities/devices from registry.
- Friendly-name translation issue for the rate-limit notification switch.
- Token-invalid setup edge case where flow could continue with bad auth.
- Reload path where unchanged inverters could flip to `unknown` during rate-limit windows.
- Rate-limit state now correctly reflected in status diagnostics while keeping previous good data.
- Invalid serials now stay clearly unavailable and surfaced in UI/notifications after reload.
