# Windows Registry preferences reference plugin

This standard-library-only plugin reconciles named values under
`HKEY_CURRENT_USER`, using Python's native
[`winreg` API](https://docs.python.org/3/library/winreg.html).
Copy this directory to `vendor/etch-windows-registry` and declare it in
`defaults.conf`:

```python
{'schema_version': 1, 'plugins': ['vendor/etch-windows-registry']}
```

Declare a Windows-only module, using a key and value types documented by the
application or Windows setting you want to manage:

```python
{
  'schema_version': 1,
  'name': 'explorer',
  'when': {'os': 'windows'},
  'actions': [
    {
      'windows_registry': {
        'hive': 'HKEY_CURRENT_USER',
        'key': 'Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\Advanced',
        'values': {
          'HideFileExt': {'type': 'REG_DWORD', 'data': 0},
        },
      },
    },
  ],
}
```

`key` is a relative backslash-separated path under `HKEY_CURRENT_USER`.
Use escaped backslashes in configuration strings. Keys and value names are
case-insensitive; duplicate value names ignoring case are rejected. Access
always selects the 64-bit Registry view, independent of Python's bitness;
on 32-bit Windows the view flag has no effect. Remote Registries and other
hives are unsupported. The hive belongs to the account running Etch, so run
as the intended user.

Every named value requires explicit `type` and `data`:

| Type | Data |
| --- | --- |
| `REG_SZ` | String without NUL characters |
| `REG_EXPAND_SZ` | String without NUL; `%VARIABLE%` text stays unexpanded |
| `REG_DWORD` | Integer from 0 through 2³²−1; booleans are rejected |
| `REG_QWORD` | Integer from 0 through 2⁶⁴−1 |
| `REG_MULTI_SZ` | List of nonempty strings without NUL; an empty list is allowed |

Default unnamed values, binary values, deletion and system hives are outside
this initial contract. `plan` and `doctor` read only declared values, without
creating keys or writing. Missing key/value state is shown separately from
replacement, and both data and Registry type must match. Plans display current
and desired data: do not use this preference plugin to store secrets.

`apply` rereads current state, creates a missing key when needed, and writes
only values that still differ. Unrelated values and subkeys remain intact.
A second apply is a no-op. Permission failures name the affected key and ask
you to check its permissions; Etch does not elevate or change permissions.
Multiple writes are not a transaction: an error may leave earlier values
updated. Rerun after resolving the error to reconcile the remaining values.

Without the Windows module guard, inspection on macOS/Linux reports a clear
platform error. Some preferences require an application restart, Explorer
restart, sign-out or reboot. Check the setting's documentation and perform that
step yourself; Etch never implicitly restarts anything or broadcasts changes.
Windows CI tests a unique disposable key under `HKCU\Software`, preserving an
unrelated value and removing only that test key afterward.
