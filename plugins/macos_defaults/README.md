# macOS preferences reference plugin

This standard-library-only plugin reconciles selected keys in a current user's
macOS preferences domain. It uses Apple's `defaults export` for inspection and
typed `defaults write` calls for changes. It does not import, overwrite, or link
whole plist files, remove undeclared keys, use `sudo`, or restart apps or
`cfprefsd`.

Copy this directory into a consumer repository as `vendor/etch-macos-defaults`
and declare it in `defaults.conf`:

```python
{"schema_version": 1, "plugins": ["vendor/etch-macos-defaults"]}
```

Declare an action in a macOS-only module:

```python
{
    "schema_version": 1,
    "name": "rectangle",
    "when": {"os": "macos"},
    "actions": [
        {
            "macos_defaults": {
                "domain": "com.knollsoft.Rectangle",
                "values": {"hideMenubarIcon": True, "windowSnapping": 2},
            }
        }
    ],
}
```

`values` requires at least one key. Supported values are strings, booleans,
integers, and finite floating-point numbers. They retain distinct plist types:
`True`, `1`, and `"1"` are different. `plan` and `doctor` report missing or
different keys without displaying their values. `apply` rechecks the domain and
writes only keys that still differ. Unrelated keys remain untouched.

The module guard lets Linux skip the action. Without it, inspection reports a
clear macOS-only error. On macOS, `defaults` talks to the preferences system;
directly editing the live plist is unsafe because `cfprefsd` and the app may
cache and rewrite preferences. Some apps read preferences only at startup, so
restart the app yourself if a setting does not appear immediately. This plugin
does not do that as a hidden side effect.

Use a disposable domain when testing, and inspect the affected app's own
preference keys and value types before declaring them. The plugin does not
prescribe settings for Rectangle, AltTab, or any other app.
