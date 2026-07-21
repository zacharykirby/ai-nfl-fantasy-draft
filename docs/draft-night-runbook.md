# Draft-Night Runbook

This deployment keeps FastAPI on localhost and exposes it only through private
Tailscale Serve. It never enables Tailscale Funnel.

## One-time setup

Install the project into `venv/`, install Tailscale on the PC and phone, and sign both
devices into the intended tailnet. On Arch Linux, enable the daemon:

```bash
sudo systemctl enable --now tailscaled
sudo tailscale up
sudo tailscale set --operator="$USER"
```

The operator grant lets your normal account configure Serve without repeatedly using
sudo; it does not expose the application publicly. Confirm the phone appears online
with `tailscale status`. Disable PC sleep for the duration of the draft and connect
the PC to reliable power.

On the first Serve attempt, Tailscale may print an account-specific URL asking the
tailnet owner to enable HTTPS certificates and Serve. Open that URL, approve Serve,
then rerun the start command. Do not enable Funnel.

## Start and verify

From the repository root, run:

```bash
scripts/draft-night-server start
```

The command validates `outputs/draft_board.json`, rejects any active Funnel
configuration, starts FastAPI as a transient user systemd service on
`127.0.0.1:8000`, configures Serve, and prints the private
`https://<machine>.<tailnet>.ts.net` URL. Open that URL on the phone while Tailscale
is connected.

Check the deployment at any time:

```bash
scripts/draft-night-server status
ss -ltnp | grep 8000
tailscale funnel status
```

The listener must show `127.0.0.1:8000`, and Funnel status must be empty. Test from
cellular with Wi-Fi disabled; a device outside the tailnet must not connect. Browser
developer tools should show no `OPENROUTER_API_KEY` in assets or responses.

## Recovery

If the phone disconnects, confirm Tailscale is connected, reopen the printed URL, and
refresh. The server reloads the atomically saved session. If the backend stopped, run
`scripts/draft-night-server start` again. Inspect `draft-server.log` for startup
errors. The terminal fallback remains available with:

```bash
venv/bin/python scripts/live_draft.py interactive <session-name>
```

If the PC restarted, confirm `tailscaled` is active and rerun the start command. Do
not use Funnel, router port forwarding, or a public tunnel as a workaround.

## Shutdown

```bash
scripts/draft-night-server stop
```

This stops the repository-managed server and clears its Tailscale Serve configuration.
It does not disconnect the PC from Tailscale or disable `tailscaled`.
