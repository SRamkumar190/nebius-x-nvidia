# Demo Google authorization and sandbox token installation

This flow is for a disposable demo Google account. Keep the Desktop OAuth client JSON and generated token outside the repository. No script here seeds inbox messages or sends mail.

## 1. Authorize on the computer with a browser

Create a Google Cloud OAuth **Desktop app** client for the demo account and enable Gmail and Calendar APIs. Download its client JSON into a private folder outside this checkout. Install the Python dependencies with `py -m pip install -r requirements.txt` on Windows (or `python3 -m pip install -r requirements.txt` on a local Unix machine).

From PowerShell, with the repo as the working directory:

```powershell
py scripts/google_oauth.py --client-secrets "$env:USERPROFILE\keeper-secrets\desktop-client.json" --output "$env:USERPROFILE\keeper-secrets\google-token.json"
```

The script opens a loopback browser consent flow. Confirm that Google shows the throwaway account. It asks for `gmail.modify` and `calendar.events`, requests offline access for scheduled runs, and refuses to write a token without a refresh token. It refuses a token path inside the repository or an existing destination, so reruns cannot silently replace a working token. On Unix, the output directory must be private (mode 700); the token is mode 600. On Windows, the script removes inherited ACLs from the new file and grants the current account access. The output file includes a refresh token and OAuth client secret; do not paste it into chat or commit it.

The runtime token does not request `gmail.insert` or `gmail.send`. Google states that `gmail.modify` itself also permits sending. The product must enforce draft-only behavior through its adapter surface and final sandbox network policy; absence of `gmail.send` alone is not a send prohibition. `gmail.modify` covers message label changes and draft creation; adding `gmail.compose` would be redundant. [Gmail scope definitions](https://developers.google.com/workspace/gmail/api/auth/scopes), [draft creation scopes](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.drafts/create), and [Calendar event scopes](https://developers.google.com/workspace/calendar/api/auth) describe these permissions.

## 2. Install in Ubuntu/WSL

Pass the generated Windows file through `/mnt/c/...` to the installer; use the actual path from your machine:

```bash
bash agent/openshell/install-google-token.sh /mnt/c/Users/YOUR_USER/keeper-secrets/google-token.json keeper
```

The installer checks the JSON shape, required refresh token, token endpoint, and exact runtime scopes without displaying secrets. It stages a mode 600 copy on the Linux filesystem, verifies the bytes, uploads it, and installs it at `/sandbox/keeper/secrets/google-token.json` (directory mode 700; file mode 600). It leaves the Token Factory key and other secrets in that directory alone. `agent/deploy.sh` leaves this secrets directory alone too. Run the installer only from the trusted WSL account that owns the sandbox.

Validate the file's presence and permissions without printing its content:

```bash
nemohermes keeper exec -- stat -c '%a %n' /sandbox/keeper/secrets /sandbox/keeper/secrets/google-token.json
```

Expect `700` and `600`. The Gmail and Calendar adapters have offline tests but no live account smoke check, so this confirms installation and file permissions only. If Google access is revoked or expires, run authorization again to a new output path and reinstall that file. Revoke the demo app's access in the Google account security settings when the demo is retired. A Google OAuth app in Testing status may issue refresh tokens with limited lifetimes; plan a reauthorization before the demo if needed. [Google OAuth guidance](https://developers.google.com/identity/protocols/oauth2/) explains that limit.
