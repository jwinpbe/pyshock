# PyShock ⚡

[![PyPI - Version](https://img.shields.io/pypi/v/pyshock?style=for-the-badge&color=blue)](https://pypi.org/project/pyshock/)
[![PyPI - License](https://img.shields.io/pypi/l/pyshock?style=for-the-badge&color=blue)](https://github.com/jwinpbe/pyshock/blob/main/LICENSE)
[![PyPI - Python Version](https://img.shields.io/badge/python-3.10%2B-blue?style=for-the-badge)](https://pypi.org/project/pyshock/)
[![build](https://img.shields.io/github/actions/workflow/status/jwinpbe/pyshock/ci.yml?branch=main&style=for-the-badge&label=build)](https://github.com/jwinpbe/pyshock/actions/workflows/ci.yml)

Python client and CLI for controlling PiShock and OpenShock devices, based on the new unified PiShock API and the OpenShock API.

Control a shocker from the terminal, or add control to your program!

## Install

For the command line tool:

```bash
uv tool install 'pyshock[cli]'
```

Use it as a library in your python program:

```bash
uv add pyshock
```

## Usage

Set up credentials:

```bash
pyshock init
```

Control a device:

```bash
pyshock shock --duration 2 --intensity 75 --shocker-id 00000

# or, if you only have one shocker associated with your account:
pyshock shock 2 75
```

Run `pyshock info 00000` for device details. Run `pyshock devices` to list devices and capabilities.

Note: Due to a limitation in the Pishock API, you will need to share your own shocker with yourself in order to use it via the API or CLI.

## Authentication

Pass credentials on the command line or cache them with `pyshock init`.

With a flag:

```bash
pyshock --key KEY shock --duration 2 --intensity 15 --shocker-id 00000
```

Interactively:

```bash
pyshock auth

Enter your API key: _____
```

Or in one step:

```bash
pyshock auth --key KEY
```

PyShock stores credentials in your user configuration folder. Refresh with `pyshock devices`.

Be advised, your API key will be stored in plain text. 

## API

Each API client caches the result of `list_shockers()` for its lifetime. Call `list_shockers(refresh=True)` to fetch current data.

### PiShockAPI

```python
from pyshock import PiShockAPI, ShockerOperation

with PiShockAPI(api_key="key") as api:
    for shocker in api.list_shockers():
        print(shocker.name, shocker.shocker_id)

    shared_shocker = api.get_shocker_by_share_code("ABC123456")

    api.operate_shocker(
        shocker=shared_shocker,
        operation=ShockerOperation.SHOCK,
        duration=2000,  # 2 seconds
        intensity=50,
    )

    api.delete_share(share_id=12345)
```

#### Operations:
`ShockerOperation.SHOCK`, `VIBRATE`, `BEEP`. Duration in milliseconds **(16-15000)**, intensity **0-100**.

> [!NOTE]
> Shockers may appear in both owned and shared provider responses.
> 
> PyShock returns one record per shocker ID, which combine 'owned device' metadata with permissions and limits attached to shared devices.

### OpenShockAPI

```python
from pyshock import OpenShockAPI, ShockerOperation

# Token authentication (limited endpoints)
with OpenShockAPI(api_token="token") as api:
    for shocker in api.list_shockers():
        print(shocker.name, shocker.shocker_id)
        api.operate_shocker(
            shocker=shocker,
            operation=ShockerOperation.SHOCK,
            duration=2000,
            intensity=50,
        )

# Cookie authentication (account and supported sharing endpoints)
from http.cookiejar import MozillaCookieJar

jar = MozillaCookieJar("cookies.txt")
jar.load(ignore_discard=True, ignore_expires=True)
cookie = jar["openShockSession"].value

with OpenShockAPI(session_cookie=cookie) as api:
    account = api.get_account()
    print(account.username)

    api.link_share_code("01234567-89ab-cdef-0123-456789abcdef")
```

#### Operations:
`ShockerOperation.SHOCK`, `VIBRATE`, `BEEP`. Duration in milliseconds **(300-65535)**, intensity **0-100**.

---

> [!NOTE]
> PyShock validates the contents of provider responses.
> 
> Malformed or unexpected responses will raise APIError rather than being treated as empty results or discarded.

## Requirements

Python 3.10+.

[Niquests](https://github.com/jawah/niquests) for the library.

The `[cli]` extra adds cyclopts, platformdirs, and rich for the terminal interface.

## License

Your choice of AGPLv3-or-later or commercial. See LICENSE for more information.
