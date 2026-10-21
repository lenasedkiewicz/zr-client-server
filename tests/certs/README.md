# Test-only TLS certificates

**Do not use these anywhere except the test suite.** The private key is public (it is in
git), so it protects nothing. Secret scanners will flag `test-server.key`; that is expected.

| File | Purpose |
|------|---------|
| `test-server.crt` / `test-server.key` | Certificate and key the test server uses; test clients trust only this certificate |
| `other.crt` | An unrelated self-signed certificate, for the "client trusts a different certificate" test (its key was deleted) |

Both are self-signed for `CN=localhost` with `subjectAltName=IP:127.0.0.1,DNS:localhost`
and valid for 100 years, so the tests do not start failing when they expire.
Regenerate from this folder in Git Bash:

```bash
MSYS_NO_PATHCONV=1 openssl req -x509 -newkey rsa:2048 -nodes -keyout test-server.key -out test-server.crt -days 36500 -subj "/CN=localhost" -addext "subjectAltName=IP:127.0.0.1,DNS:localhost"
MSYS_NO_PATHCONV=1 openssl req -x509 -newkey rsa:2048 -nodes -keyout other.key -out other.crt -days 36500 -subj "/CN=localhost" -addext "subjectAltName=IP:127.0.0.1,DNS:localhost"
rm other.key
```

The real server uses its own `server.crt` / `server.key` in the project root (git-ignored).
