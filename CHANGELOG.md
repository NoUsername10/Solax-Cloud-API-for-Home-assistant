# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [v0.1.8.5] - 2026-02-12

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
