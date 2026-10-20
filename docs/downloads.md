---
title: "Upstream asset downloads"
description: "Place upstream files without execution, with ownership and integrity checks."
publishedAt: 2026-10-14
tags: [Etch, Reference]
draft: false
---

# Upstream asset downloads

Use `download` to place an upstream file without executing it. For example:

```python
{'download': {
  'url': 'https://raw.githubusercontent.com/junegunn/vim-plug/master/plug.vim',
  'destination': '~/.local/share/vim/site/autoload/plug.vim',
  'check': {'file_exists': '~/.local/share/vim/site/autoload/plug.vim'},
}}
```

The action accepts `url`, `destination`, optional `check`, `sha256`, `tls`,
`download_timeout`, and `description`. Its HTTPS rules match the
[installer transport](installers.md): no redirects, verified TLS by default,
HTTP 200, a nonempty unencoded non-HTML body, an 8 MiB limit, and optional
SHA-256 validation. `tls.ca_file` must be a module-owned file. Download defaults
may set `tls` and `download_timeout` only. A pinned URL and checksum make the
bytes reproducible; a live URL without a hash supplies current upstream bytes
on a fresh install.

Planning reports the URL, destination, path claim, and network requirement
without making a request or creating directories. Apply creates missing parent
directories, downloads into a temporary location on the destination filesystem,
validates the complete response, then moves it into place. Transfer and checksum
failures leave any prior destination untouched and remove the temporary file.

Etch refuses an existing file or symlink unless it recognizes the file as one
previously downloaded by the same module. It records the downloaded content in
`.etch/downloads/` (module, URL, destination and content checksum); deleting that receipt or changing the file makes the
destination unmanaged, so Etch will refuse to replace it. A matching `check`
skips a managed file on subsequent applies. Without a `check`, an unchanged URL
also skips the managed file. Changing the URL, or failing a configured `check`,
downloads an owned file again; an unpinned live URL is never refreshed silently on
each apply. Remove or move an unrelated destination yourself before letting
Etch take ownership of it.

## Local working files and ownership records

`.etch/downloads/` contains small ownership records, not downloaded archives or
payload caches. The installed destination is the requested output and remains
until deliberately removed or replaced. Removing a module or declaration does
not automatically uninstall downloaded files. Automatic link retirement and
explicit `clean` actions do not delete ordinary downloaded files.

Transfers use a temporary directory beside the destination so publication stays
on the same filesystem. Normal completion, failed transfers and handled errors
release that directory. Downloaded installers use separate temporary storage
that is removed after execution. Neither path retains a history of old payloads.
A forced process termination or power loss can leave temporary working files;
Etch does not sweep arbitrary system temporary directories or other running
processes' workspaces.

After a successful apply, automatic housekeeping prunes records whose recorded
download destination is missing. Existing legacy records remain readable. When
the destination can be identified from the repository's declarations, housekeeping
adds that path without downloading again or changing the recorded checksum.
A full run can discard unmatched legacy records; partial runs preserve them.
Future-version records are preserved rather than interpreted by an older engine.
See [cleanup](clean.md) for scope, planning and ownership rules.
