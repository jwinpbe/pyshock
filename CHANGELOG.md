# Changelog

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
