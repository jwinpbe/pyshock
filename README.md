# PyShock

Python client for the new, unified PiShock API. Control a shocker from the terminal, or add control to your program!

## Install

For the command line tool:

```
uv tool install 'pyshock[cli]'
```

Use it as a library in your python program:

```
uv add pyshock
```

## Usage

Set up credentials:

```
pyshock init
```

Control a device:

```
pyshock shock --duration 2 --intensity 75 --shocker-id 00000

# or, if you only have one shocker associated with your account:
pyshock shock 2 75
```

Run `pyshock info 00000` for device details. Run `pyshock devices` to list devices and capabilities.

## Authentication

Pass credentials on the command line or cache them with `pyshock init`.

With a flag:

```
pyshock --pishock-key KEY shock --duration 2 --intensity 15 --shocker-id 00000
```

Interactively:

```
pyshock init

Enter your API key: _____
```

Or in one step:

```
pyshock init --pishock-key KEY
```

PyShock stores credentials in your user configuration folder. Shockers are cached to avoid API lookups. Refresh with `pyshock devices`.

Be advised, your API key will be stored in plain text. 

## API

```python
from pyshock import PiShockAPI, ShockerOperation

with PiShockAPI(api_key="key") as api:
    for shocker in api.list_shockers():
        print(shocker.name, shocker.shocker_id)

    shared_shocker = api.get_shocker_by_share_code("ABC123")

    api.operate_shocker(
        shocker=shared_shocker,
        operation=ShockerOperation.SHOCK,
        duration=2000, # 2 seconds
        intensity=50,
    )
```

Operations: `ShockerOperation.SHOCK`, `VIBRATE`, `BEEP`. Duration in milliseconds (0-15000), intensity 0-100.

## Requirements

Python 3.10+. Niquests for the library. The `[cli]` extra adds cyclopts, platformdirs, and rich for the terminal interface.

## License

Your choice of AGPL or commercial. See LICENSE for more information.
