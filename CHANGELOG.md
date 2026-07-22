# Changelog

## [0.3.0] - 2026-07-21

### Breaking changes

- `OpenShockAPI` requires `api_token`. Session-cookie authentication is gone, along with
  `link_share_code()` and `unlink_share_code()`.
- Removed `SessionOnlyError` and `TokenAuthNotSupportedError`.
- Removed OpenShock share-code management from the CLI. `code add`, `code delete`, and `code list` are PiShock-only.
- `code list` uses the selected PiShock account. Use the global `--account` flag to change it.
- Removed `_current_account_id` and `_current_api_client` contextvars. All CLI commands take an explicit
  `session` parameter.
- `get_api_for_account` is `get_session_for_account` and returns a `Session`. Removed `get_api` and
  `set_api_client`.
- `prepare_api_session` is `build_session`.
- `validate_operation_params` is `validate_duration`. Intensity bounds are cyclopts type constraints now.

### Added

- `_omit_from_json()` helper marks `Shocker` dataclass fields with `cli_json_exclude`
  metadata. `shocker_json()` filters on that metadata instead of a hardcoded exclude list.
- `_apply_owned_fields()` replaces `_merge_shockers`. Runtime type checks on `claimed_data`
  and `shared_data` before parsing.
- `protocols.py` with a `ShockerClient` Protocol and `Session` dataclass, exported via `__all__`.
- `providers.py` with a `PROVIDERS` dispatch table and `ProviderSpec`.
- `constants.py` holds provider duration limits.
- `Shocker.__repr__` includes `shared_by` when the shocker is shared.
- Test for unsupported operation values in `OpenShockAPI.operate_shocker`.

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
