# Installer HTTPS fixtures

`installer-ca.pem` and `installer-key.pem` are a self-signed localhost certificate
and its intentionally public, unencrypted test key. They are used only by the
temporary loopback HTTPS server; never use them for a deployed service.

The certificate expires September 12, 2036. To replace the pair from the repository
root (OpenSSL is needed only for regeneration, not normal tests):

```sh
openssl req -x509 -newkey rsa:2048 -nodes \
  -keyout tests/fixtures/installer-key.pem \
  -out tests/fixtures/installer-ca.pem -days 3650 \
  -subj '/CN=localhost' \
  -addext 'subjectAltName=DNS:localhost,IP:127.0.0.1'
```

Update the expiry date here after regeneration. The regular tests require only
Python's standard-library HTTPS server and permission to bind a loopback socket.

## VS Code fake CLI

`vscode_cli.py` is copied into a temporary executable by the VS Code plugin tests.
It reads/writes only the adjacent temporary `state.json` and `calls.jsonl` files.
It never invokes VS Code, installs a real extension, or accesses the network.

## Homebrew fake CLI

`brew_cli.py` is copied into a temporary executable by the Homebrew bundle tests.
It modifies only adjacent temporary inventory, logs, lock/gate files, and a fake
installed tool. It never invokes Homebrew, installs real packages, or accesses the
network. The gate/lock protocol checks serialization alongside independent work.
