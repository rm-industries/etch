# WinGet plugin

Approved in chat on 2026-10-28. Optional API 1 bundle: presence-only `winget`
action and `winget.command`, `winget.version`, `winget.packages` facts.
Python 3.9+, standard library only. Mirror npm/Homebrew bundle conventions.

Use shared native execution, JSON export inventory and exact package IDs.
Recheck before and after installation; preserve installed versions and extras.
No bootstrap, upgrades, removal, source management or arbitrary CLI flags.

Selected approach: JSON export to a disposable file. Alternative: parsing
localized list tables, rejected as fragile. Add regression tests and documentation.
Develop on macOS with a simulated CLI; disclose lack of real Windows validation.
