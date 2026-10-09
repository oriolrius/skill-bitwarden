# FIDO2 passkeys stored in Bitwarden

Bitwarden stores passkeys inside login items under `login.fido2Credentials[]`.
Each entry carries the private key in `keyValue` (base64url-encoded PKCS#8 DER)
plus metadata (`credentialId`, `rpId`, `userName`, `userHandle`, `counter`,
`keyAlgorithm`, `keyCurve`, `discoverable`).

## Find items with passkeys

```bash
bw-agent list items \
  | jq '[.[] | select((.login.fido2Credentials // []) | length > 0)
        | {id, name, username: .login.username, rp: [.login.fido2Credentials[].rpId]}]'
```

## Export to PEM

```bash
<skill-dir>/scripts/bw-passkey-export <item-id> [output-dir]
```

Writes one `<name>.<n>.pem` (mode 600) plus a `<name>.<n>.json` with the
non-secret metadata per credential, into a private temporary directory unless
one is given. Inspect with `openssl pkey -in <file>.pem -text -noout`.

Notes:

- Usual algorithm is ECDSA P-256 (`prime256v1`); `openssl pkcs8` also handles RSA.
- Some relying parties encode `userHandle` with a provider-specific prefix;
  base64-decode the field first.
- The PEM files are raw private keys. Shred them when done
  (`shred -u <dir>/*.pem` on Linux, `rm -P` on macOS) and never paste them into
  chat or commit them.
