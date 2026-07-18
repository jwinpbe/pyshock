# Changelog

## [0.2.0] - 2026-07-18

### Breaking changes

- Removed `OpenShockAPI.list_share_codes()` because its endpoint returned user shares instead of issued share codes.
- Changed `PiShockAPI.delete_share()` to accept a share ID instead of a share code.
- Removed `Shocker.merge()` in favor of provider-specific merge rules.

### Added

- Added `list_shockers(refresh=True)` to bypass each client's in-memory cache.
- Added a CI job that runs the core test suite without CLI dependencies.

### Fixed

- PiShock now preserves share permissions and limits when it combines shared and owned shocker records.
- PiShock now accepts the provider's 16 ms minimum duration.
- OpenShock now prefers owned records when owned and shared responses contain the same shocker ID.
- OpenShock now maps share, shocker, authentication, and permission errors to typed exceptions.
- OpenShock now raises `APIError` for malformed collection responses and permission metadata.

## [0.1.2] - 2026-06-21

- Changed text color on rendered badges for visual clarity on unthemed terminals

## [0.1.1] - 2026-06-17

- Bumped version to build and push to pypi due to pre-existing pyshock name collision

## [0.1.0] - 2026-06-17

### Added
- PiShock API client: list shockers, operate (shock/vibrate/beep), share codes, health check
- OpenShock API client: full parity with PiShock plus session & token auth, share code management
- CLI: `init`, `shock`, `vibrate`, `beep`, `info`, `devices`, `verify`, `logout`, `code add/remove/list`
- CLI: credential caching in user config directory
- CLI: `--json` flag for machine-readable output
- CLI: `--debug` flag for verbose logging
- Typed exception hierarchy with HTTP status codes
- Frozen data models (`Shocker`, `AccountInfo`)
- Full test suite (261 tests, 83%+ coverage)
