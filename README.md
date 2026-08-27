# Mast Flag Status

A Home Assistant custom integration that exposes current U.S. flag status from
[Mast](https://www.mast.today). Configure an API key and state through the UI,
then use the entities in your dashboards or your own automations.

**Information only:** this integration does not create automations or control
flagpoles, motors, ESPHome devices, or other hardware.

Mast aggregates federal and state flag-status information. This community project
is **not affiliated with or endorsed by Mast**. Data is powered by Mast; verify
important decisions against official notices.

## Requirements

- Home Assistant 2025.12 or later.
- A [Mast developer API key](https://www.mast.today/api) (use **Get an API key**).
- Internet access to `www.mast.today` over HTTPS.

## Installation

### HACS custom repository

[![Open this repository in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=ArcReactorKC&repository=USAFlagtoday&category=integration)

With HACS already installed, use the button to open this repository in your
Home Assistant instance. My Home Assistant may ask for your instance URL.
Follow the prompts in HACS to add/download the integration, then restart Home
Assistant and follow Setup below. The button does not install HACS itself.

Alternatively, add the repository manually:

1. Open HACS, then its menu → **Custom repositories**.
2. Add `https://github.com/ArcReactorKC/USAFlagtoday` with type **Integration**.
3. Download **Mast Flag Status** and restart Home Assistant.
4. Follow Setup below.

This is a custom repository, not a claim of inclusion in the default HACS catalog.

### Manual

Copy `custom_components/mast_flag` into your Home Assistant configuration
directory as `config/custom_components/mast_flag`. Restart Home Assistant.
Do not copy the entire repository into `custom_components`.

## Setup

Go to **Settings → Devices & services → Add integration → Mast Flag Status**.
Enter your API key, keep United States selected, and choose one of the 50 states
or District of Columbia. Setup makes a real request to validate the key and location.
No YAML configuration is required.

Use **Configure** on the integration to change the state. The new location is
validated before saving and the integration reloads automatically. Entity IDs
remain the same; their displayed device name and state attributes update.
If you previously renamed an entity, its user-assigned name is retained.

Revoked keys trigger Home Assistant's reauthentication flow. Replace the key in
that flow without deleting the integration. Keys are not editable in options.

One entry per state is allowed, regardless of key: flag status for a location is
the same across API accounts. You can monitor multiple states with separate entries.
Location unique IDs contain only `US` and the state code. Device and entity unique
IDs use Home Assistant's stable config entry ID, never the API key or a key hash.

## Entities

Each location has one service device, for example **Mast Flag Status - Missouri**.

| Entity | State | Meaning |
| --- | --- | --- |
| Flag half staff | `on` / `off` | Mast reports half-staff / full staff |
| Flag status | `half_staff` / `full_staff` | Machine-readable equivalent |
| Flag status reason | Mast's current title, or `unknown` | Human-readable context |

Home Assistant generates actual entity IDs from the device/entity names. Find
them on the device page; no IDs are forced by this integration. The status sensor
may display translated labels while templates still see the values above.

Attributes include `country_code`, `state_code`, and, when provided, `reason`,
`authority`, and `cache_is_stale`. Long reasons are truncated to 255 characters
in the sensor state; the full text remains in its `reason` attribute.

### Documented API limitations

The current-status example documents `status.isHalfMast`, `status.title`,
`status.authority`, `status.countryCode`, and `status.stateCode`.
The normalized model reserves `start`, `end`, and `source_url`, but these remain
unset because the public documentation does not specify their keys on this
endpoint. Calendar events are **not** assumed to describe the active order.
No additional calendar or source requests are made. Live responses may omit
`status.stateCode`; in that case the same response's `calendar.countryCode` and
`calendar.stateCode` must confirm the requested location. Explicit conflicting
location codes are rejected. Calendar events are never used to determine status.

An explicitly stale Mast cache is exposed as `cache_is_stale: true`; it is not a
claim that data is freshly verified. Missing cache metadata means freshness is
unknown. A malformed response or wrong returned location makes the entities
unavailable rather than silently interpreting it as full staff.

### Generic notification example

This optional example is user configuration, not functionality installed by the
integration. Substitute your actual entity ID and notify action.

```yaml
alias: Notify when flag status becomes half-staff
triggers:
  - trigger: state
    entity_id: binary_sensor.mast_flag_status_missouri_flag_half_staff
    from: "off"
    to: "on"
actions:
  - action: persistent_notification.create
    data:
      title: Flag status changed
      message: Mast now reports half-staff for the configured location.
```

## Polling

One shared coordinator sends one request per location every hour while its
entities are enabled. Setup, location validation, reauthentication, reloads,
and manual refreshes make additional requests. Three entities do not triple
polling. The interval is defined in `const.py` as `UPDATE_INTERVAL`.

Mast's upstream refresh schedule is independent of this polling interval.
Status changes can take up to an hour to appear after Mast updates. This is
not a real-time timer for sunrise, sunset, or noon; the API decides the status.
Rate limits and temporary failures use Home Assistant's normal retry and
availability behavior. The integration does not run its own retry loop.

## Troubleshooting

- **Invalid authentication:** verify the developer key in Mast; reauthenticate
  when prompted. HTTP 401/403 are treated as authentication failures.
- **Cannot connect:** check DNS, HTTPS access, Mast availability, and your request
  allowance. HTTP 429 and server errors are temporary failures.
- **Invalid location:** Mast must confirm `US` and the selected postal abbreviation
  in status metadata, or in calendar metadata when `status.stateCode` is missing.
  HTTP 400/422 and conflicting location codes also produce this error.
- **Unexpected response:** Mast may have changed its schema or returned non-JSON.
  Report the problem with sanitized details, never your API key or raw headers.
- **Unavailable:** Home Assistant retries temporary failures. Previously cached
  information is not presented as an available current status after a failed poll.
- **No reason:** Mast did not provide a title; `unknown` is expected.
- **Already configured:** change/remove the existing state entry first.
- **Missing integration after installation:** confirm the directory layout and restart.

## Privacy and security

The API key is stored in the Home Assistant config entry. Protect your Home
Assistant configuration directory and backups; it is not encrypted by this
integration. Requests send only the key in the documented
`x-mast-license-key` header and the selected country/state as query parameters.
Redirects are disabled so that a custom credential header is not forwarded to
another host. The integration never logs the key, raw response, or request headers.
Do not share debug captures or configuration backups containing secrets.

## Development

Run the full test suite on Linux with Python 3.14:

```sh
python -m venv .venv
. .venv/bin/activate
pip install -r requirements-test.txt
ruff check .
ruff format --check .
pytest -q
```

Tests mock API responses and need no Mast credentials. The test dependency pins
Home Assistant 2026.8.3. HACS and Hassfest validation workflows are included.
All HACS checks, including brand assets, are enabled. Before publishing, run
HACS, Hassfest, and the tests successfully, then publish a release containing the
validated changes. Keep the release tag and `manifest.json` version aligned.

The declared runtime minimum is Home Assistant 2025.12; automated integration
tests currently cover 2026.8.3. Bundled brand icons are supported starting with
Home Assistant 2026.3; earlier versions may show a placeholder icon.

### Default HACS catalog submission

Before submitting, verify installation and setup with a real Mast key, all three
entities, an hourly refresh, state changes, and behavior after a Home Assistant
restart. Never include credentials in screenshots or reports.

After all checks pass without ignores and a full release is published, the owner
or a major contributor can submit a PR to `hacs/default`, adding
`ArcReactorKC/USAFlagtoday` alphabetically to its `integration` list. Follow the
current submission template and allow maintainer edits. Catalog acceptance is a
separate review; the HACS button does not mean this repository is already listed.

### Specifications checked

- [Mast API](https://www.mast.today/api), checked 2026-08-27.
- [Home Assistant config flows](https://developers.home-assistant.io/docs/core/integration/config_flow/).
- [Options flows](https://developers.home-assistant.io/docs/core/integration/options_flow/).
- [Coordinator fetching](https://developers.home-assistant.io/docs/integration_fetching_data/).
- [Integration manifest](https://developers.home-assistant.io/docs/creating_integration_manifest/).
- [HACS integration requirements](https://hacs.xyz/docs/publish/integration/).
- [HACS validation action](https://hacs.xyz/docs/publish/action/).

## License

Integration code: MIT. See [LICENSE](LICENSE).

The bundled Mast icon is third-party artwork from [Mast](https://www.mast.today),
used to identify the API service. It is not covered by this project's MIT license.
See [brand attribution](custom_components/mast_flag/brand/README.md) for its source.
Its use does not imply affiliation with or endorsement by Mast.
