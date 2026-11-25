# AWS staging deployment

The owner authorized `3.80.112.46` and replacing the existing site at
`ahmedeman.site` with Muhasaba on 25 November 2026 (Africa/Cairo). This is an API
deployment for the Flutter client, not a web version of the app. The shared
Play Hub security group was not edited by the agent. After explicit confirmation,
the dedicated `muhasaba-staging-web-sg` (`sg-05fb30bf6beffa39f`) was attached only
to instance `i-0aa45567ae8196dac` / interface `eni-00a813b3503e120da`. It permits
TCP 80 and 443 from `0.0.0.0/0`; the existing group remains attached for SSH.

## Current checkpoint

- Ubuntu host, SSH user `ubuntu`, application directory `/opt/muhasaba`.
- Application source: commit `7a9115dc7bec1f4967e671be2bd2c1a22633004a`, plus
  the staging configuration files in this directory.
- Docker Engine/Compose, host Nginx and Certbot installed. Database and API are
  healthy. Alembic is at `0006`. Local `/ready` returns 200; unauthenticated
  `/api/v1/me` returns 401. PostgreSQL has no host port binding.
- Fresh random database passwords were generated on the server in `.env`, mode
  0600. Never copy them into Git, logs, documentation or chat.
- DNS-only apex A points to `3.80.112.46`, with no apex AAAA returned. Public
  HTTPS is active using `nginx-staging.conf`; HTTP redirects to HTTPS with 308.
- Let's Encrypt certificate issued with the owner's approved contact/agreement;
  its initial expiry is 22 February 2027. `certbot.timer` is enabled and the deploy
  hook `/etc/letsencrypt/renewal-hooks/deploy/muhasaba-nginx` validates Nginx then
  reloads it. Simulated renewal including the deploy hook passed.
- External checks passed with normal TLS verification: `/`, `/health`, `/ready`
  return 200, unauthenticated `/api/v1/me` returns 401, `/docs` returns 404, and
  each HTTPS response contains `Cache-Control: no-store`.
- No religious catalog was approved or published. No demo fixture was installed.
- No external backup storage, retention schedule or production release is implied.

## Operating the stack

Always include both Compose files when creating or updating staging containers:

```bash
cd /opt/muhasaba
sudo docker compose --env-file .env -f infra/compose.yml -f infra/compose.staging.yml config --quiet
sudo docker compose --env-file .env -f infra/compose.yml -f infra/compose.staging.yml up --build -d --wait
sudo docker compose --env-file .env -f infra/compose.yml -f infra/compose.staging.yml exec -T --interactive=false api alembic upgrade head
curl --fail http://127.0.0.1:8000/ready
```

The overlay removes the database's host port, enables restart after reboot and
caps Docker logs. API port 8000 binds only to loopback. Do not run `up` with the
base Compose file alone. Existing backup/restore scripts use `exec` against the
same project and services; they do not recreate containers. Never run `down -v`
on a database that must be retained.

`FORWARDED_ALLOW_IPS` in the server `.env` is the inspected `muhasaba_default`
network gateway (currently `172.18.0.1`), allowing only the host proxy's forwarded
client address. Recheck it after recreating the network. Nginx replaces incoming
forwarding headers, disables access logging, and applies per-client request limits.
Keep DNS-only mode for this configuration: enabling Cloudflare proxy requires a
separate trusted-proxy configuration review to preserve accurate client limits.

## DNS and HTTPS cutover

1. Point apex `A` at `3.80.112.46`, DNS only. Remove conflicting apex CNAME/AAAA
   entries while preserving mail records. Verify the address is stable before
   relying on it across EC2 stop/start cycles. AWS shows this is an auto-assigned
   address, not an Elastic IP: a stop/start can require a DNS update. No Elastic IP
   was allocated or charged as part of this deployment.
2. Confirm TCP 80 and 443 reach this instance through its security group/NACL.
   Do not open 8000 or 5432. Keep SSH access limited to the operator's needs.
3. Use the HTTP webroot `/var/www/letsencrypt` to issue a certificate for
   `ahmedeman.site` with Certbot. Supply the owner's certificate contact and
   required CA agreement when registering. This step is complete for the current
   host; do not register or force-renew on each application deployment.
4. After `/etc/letsencrypt/live/ahmedeman.site/{fullchain,privkey}.pem` exist,
   install `infra/nginx-staging.conf` as `/etc/nginx/sites-available/muhasaba`,
   run `sudo nginx -t`, then reload Nginx. Retain the HTTP challenge route for
   renewal. The installed deploy hook runs `nginx -t` and `systemctl reload nginx`.
   Check renewal with `sudo certbot renew --dry-run --run-deploy-hooks`.
5. Verify public HTTP redirects, trusted HTTPS, `/health`, `/ready`, unauthenticated
   account rejection, and absence of caching. These checks passed. API base URL:
   `https://ahmedeman.site/api/v1/`. Actual-device acceptance is still pending.

Rollback: restore the previous Nginx configuration and validate before reload.
Record the old DNS target in Cloudflare before replacing it if website rollback
is needed. Preserve database volumes and server `.env`; application rollback
across schema changes requires a separately verified migration/recovery plan.

The host initially has an 8 GiB disk with about 3 GiB free after installation;
monitor space before retaining backups/build layers. The release gates in
`codex/PR-07_RELEASE_READINESS.md` still apply, including actual-device UAT,
approved content and privacy/support/deletion policy.
