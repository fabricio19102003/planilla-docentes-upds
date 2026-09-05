# Deploy SIPAD safely on the UPDS VPS

SIPAD runs as three private containers—PostgreSQL, FastAPI, and the React/Nginx app—behind the VPS host Nginx. Only the app container publishes a port, and it binds to loopback. Database migration is an explicit, fail-closed gate between an externally copied backup and application startup.

> **Current gate:** do not deploy until the intended source changes and migration files are reviewed, committed, and identified by an immutable release tag.

## Quick path

1. Complete the [read-only VPS preflight](#read-only-vps-preflight).
2. Create `deploy/.env.production`, set mode `0600`, and replace every placeholder.
3. Build the immutable images with `deploy/scripts/build.sh`.
4. Run `deploy/scripts/deploy.sh`. It deliberately stops before migration and prints the fresh backup paths.
5. Copy the backup and checksum to approved encrypted external storage, verify them, and resume with the exact command printed by the script.
6. Install the host vhost only after `nginx -t` passes, then complete the [smoke checks](#smoke-checks).

## Architecture

| Boundary | Production decision |
|---|---|
| Public traffic | Host Nginx terminates TLS and proxies one dedicated hostname to `127.0.0.1:<APP_HOST_PORT>`. |
| Browser/API | App Nginx serves the Vite SPA and proxies `/api`, `/uploads`, `/health`, and `/ready` to FastAPI. |
| Database | PostgreSQL has no published host port and is reachable only on the internal Compose network. |
| Schema | Alembic runs separately, creates the complete runtime schema on an empty DB, and validates compatible legacy `create_all` tables without replacing their data. FastAPI refuses production startup unless the DB exactly matches the packaged Alembic head. |
| Persistence | Dedicated volumes preserve PostgreSQL, uploads, generated output, reports, contracts, schedules, retention letters, and in-app backups. |
| Release | Images use an immutable `IMAGE_TAG`; `latest` is rejected. |
| Rollback | Application image rollback is supported only after schema compatibility is proven. Database restore is a separate human-approved operation. |

## Files operators own

| File | Purpose |
|---|---|
| `deploy/.env.production` | Protected production values; never commit it. |
| `deploy/nginx/host-vhost.conf.example` | Template for the VPS host Nginx vhost. |
| `deploy/state/` | Local release pointers and pre-migration backups; ignored by Git and not an external backup. |
| External backup location | Encrypted storage outside the VPS, with retention and access controls defined by the operator. |

## Prepare the production environment

```bash
cp deploy/.env.production.example deploy/.env.production
chmod 600 deploy/.env.production
```

Resolve these human inputs before continuing:

- `<SIPAD_HOSTNAME>`: a dedicated project-specific DNS name.
- `<UNUSED_LOOPBACK_PORT>`: confirm it is unused on the live VPS.
- `<IMMUTABLE_RELEASE_TAG>`: a reviewed Git tag or commit-derived release identifier, never `latest`.
- PostgreSQL, JWT, bootstrap, and optional email secrets.
- Approved encrypted external backup destination and retention policy.

Generate URL-safe database/JWT secrets. PostgreSQL requires at least 32 URI-safe random
characters; JWT requires at least 32 random bytes (64 hexadecimal characters):

```bash
openssl rand -hex 32
openssl rand -hex 48
```

Do not reuse the development bootstrap passwords documented in `README.md`. Bootstrap
passwords require at least 16 characters with uppercase, lowercase, and a digit; generate
them with an approved password manager rather than the hexadecimal commands above. For a
new empty database, set a unique `ADMIN_DEFAULT_PASSWORD`. After the first administrator
changes it, clear the environment value and redeploy. `DOCENTE_DEFAULT_PASSWORD` must also
be unique and temporary.

Email remains disabled until the provider key and verified sender are ready. Never enable `EMAIL_TEST_MODE` without a dedicated test recipient.

## Read-only VPS preflight

The two VPS reports are historical. Certificate renewal, ports, capacity, services, and the existing application must be verified again without changing the server.

From a trusted workstation:

```bash
ssh <SSH_TARGET> 'hostname; date -u; uptime; df -h; free -h'
ssh <SSH_TARGET> 'docker version; docker compose version; docker ps --format "table {{.Names}}\t{{.Ports}}\t{{.Status}}"'
ssh <SSH_TARGET> 'sudo nginx -t; sudo certbot certificates; sudo ufw status verbose'
ssh <SSH_TARGET> 'systemctl is-active nginx docker fail2ban; systemctl is-enabled certbot.timer unattended-upgrades'
```

After cloning the reviewed release and creating the protected environment file on the VPS, run the bundled read-only check:

```bash
deploy/scripts/vps-preflight-readonly.sh
```

Confirm manually:

- DNS for `<SIPAD_HOSTNAME>` resolves to the intended VPS.
- The documented certificates have actually renewed and the new hostname has a valid certificate.
- `<APP_HOST_PORT>` is unused and does not conflict with the existing UPDS project.
- Disk has room for images, database growth, generated payroll files, and two full backup generations.
- `/srv/apps/<SIPAD_APP_DIRECTORY>` ownership is restricted to the deployment account.
- No PostgreSQL port is exposed publicly.
- Existing host vhosts remain intact; never remove or replace another project's vhost as a shortcut.

## First deploy

Clone or check out only an immutable reviewed release under `/srv/apps/<SIPAD_APP_DIRECTORY>`. The normal preflight rejects a dirty checkout.

```bash
deploy/scripts/build.sh
deploy/scripts/deploy.sh
```

The first `deploy.sh` invocation:

1. Builds images unless `SKIP_BUILD=1` was explicitly supplied.
2. Starts PostgreSQL and waits for health.
3. Stops application traffic.
4. Creates a custom-format PostgreSQL backup plus SHA-256 checksum.
5. Exits **before migration** with a resume command.

Copy both generated files outside the VPS and verify the external checksum. Then run the exact resume command printed by the script. Its shape is:

```bash
SKIP_BUILD=1 \
PREMIGRATION_BACKUP_PATH='<FRESH_LOCAL_BACKUP_PATH>' \
CONFIRM_EXTERNAL_BACKUP=YES \
deploy/scripts/deploy.sh
```

The resumed deployment verifies the portable basename-only checksum manifest and backup
age, runs `alembic upgrade head`, proves `alembic current` is the head packaged in that
image, starts backend and app, and checks loopback readiness. The expected revision is read
from the packaged Alembic graph; operators do not maintain a hardcoded revision value.

### Host Nginx and TLS

Copy `deploy/nginx/host-vhost.conf.example` to a new project-specific host vhost and replace both placeholders. Do not edit another project's file.

```bash
sudo nginx -t
sudo systemctl reload nginx
```

Obtain or expand the certificate using the VPS's established Certbot procedure only after DNS resolves. Run `nginx -t` again before every reload.

## Upgrade

1. Review and tag the release; do not deploy a dirty checkout.
2. Update `IMAGE_TAG` in the protected environment file.
3. Run `deploy/scripts/deploy.sh`.
4. Copy and verify the newly generated backup externally.
5. Resume with the printed command.
6. Complete smoke checks before allowing payroll operations.

The application is intentionally stopped across the backup/migration boundary. This favors data integrity over zero-downtime deployment.

## Smoke checks

Run from the VPS loopback first, then through the public TLS hostname:

```bash
curl --fail --silent http://127.0.0.1:<APP_HOST_PORT>/health
curl --fail --silent http://127.0.0.1:<APP_HOST_PORT>/ready
curl --fail --silent https://<SIPAD_HOSTNAME>/health
curl --fail --silent https://<SIPAD_HOSTNAME>/ready
curl --fail --head https://<SIPAD_HOSTNAME>/login
```

Then verify through the UI with non-destructive actions:

- Login and forced-password-change behavior.
- SPA deep-link refresh, for example `/login` and `/portal`.
- Existing teacher photo retrieval through `/uploads`.
- Read-only history, reports, and planilla detail for an already verified period.
- No planilla generation, approval, publication, email, or destructive restore during smoke testing.

Inspect bounded logs without exposing environment values:

```bash
docker compose --env-file deploy/.env.production -f deploy/compose.production.yml ps
docker compose --env-file deploy/.env.production -f deploy/compose.production.yml logs --tail=100 backend app db
```

## External backup and restore drill

`deploy/state/backups` and the in-app backup volume are **not** disaster recovery because they live on the same VPS.

For every migration:

1. Create the custom-format backup with `deploy/scripts/backup.sh`.
2. Copy the `.dump` and `.sha256` to approved encrypted external storage.
3. Keep both files in the same directory and verify the portable manifest after transfer:
   `sha256sum --check <BACKUP_BASENAME>.dump.sha256`.
4. Record release tag, Alembic revision, timestamp, and retention expiry without recording secrets.

At least once before production, restore into an isolated disposable PostgreSQL instance—not the live DB—and prove:

```bash
createdb <ISOLATED_RESTORE_DATABASE>
pg_restore --exit-on-error --no-owner --no-acl \
  --dbname=<ISOLATED_RESTORE_DATABASE> <BACKUP_FILE>
```

Validate row counts/invariants, Alembic revision, authentication, and representative read-only payroll queries. Delete the isolated instance according to the data-handling policy.

## Rollback

### Application-only rollback

Use only when the older application is proven compatible with the current database schema and both previous images remain locally available:

```bash
CONFIRM_SCHEMA_COMPATIBLE=YES deploy/scripts/rollback.sh <PREVIOUS_IMMUTABLE_TAG>
```

The script creates a current safety backup, changes only backend/app images, and checks readiness. It does not modify the database. Update the protected `IMAGE_TAG` after a successful rollback.

### Database restore boundary

Do **not** assume Alembic downgrade or image rollback reverses destructive data changes. If the previous application cannot start against the current schema:

1. Keep application traffic stopped.
2. Preserve a new backup of the failed state.
3. Select the exact externally verified pre-migration backup.
4. Obtain explicit authorization for the target release and acceptable data-loss window.
5. Restore into an isolated database first and verify it.
6. Replace the production database only through the approved database recovery procedure.

No bundled script automatically restores production.

## Security and data boundaries

- `.dockerignore` excludes environments, backups, databases, spreadsheets, PDFs, tests, local agents, runtime data, and external real-data fixtures from all image contexts.
- The repository uses a committed synthetic designation fixture for automated tests. Real-data E2E inputs are external and explicitly opt-in; never add operational datasets to version control or image contexts. Historical Git objects require a separate sanitation procedure if repository-history removal is ever required.
- Containers drop Linux capabilities, use `no-new-privileges`, bounded logs/resources, and read-only filesystems where practical.
- App Nginx runs non-root; its PID and all client/proxy/FastCGI/uWSGI/SCGI temporary paths are under the container's writable `/tmp` tmpfs.
- PostgreSQL remains internal-only. The app port is loopback-only; host Nginx is the public boundary.
- Generated files are operational records. Include their volumes in backup, retention, access-control, and deletion policies.

## Operator checklist

- [ ] Reviewed commit and immutable release tag exist.
- [ ] Working tree is clean.
- [ ] Production environment is `0600` and contains no placeholders/default credentials.
- [ ] DNS, TLS renewal, port availability, disk, memory, Nginx, Docker, firewall, and existing apps are verified live.
- [ ] Images build and packaged Nginx configuration passes.
- [ ] Fresh database backup and checksum exist externally.
- [ ] Alembic gate passes before API startup.
- [ ] Loopback and public readiness checks pass.
- [ ] Non-destructive application smoke checks pass.
- [ ] Restore drill and rollback owner are documented.

## Official WhatsApp billing rollout and rollback

Keep both official flags `false` until the sender is `ONLINE`, every configured
Content SID is an approved Utility template, Advanced Opt-Out is active, and
canonical HTTPS callback/media URLs resolve through the new vhost. Put Twilio
keys, Auth Token, sender, Content SID, capacity limits, and URLs only in the
private `deploy/.env.production` file; never put them in Git or logs.

For a controlled validation, deploy the API and `official_whatsapp_worker`, run
only a consented small cohort, confirm signed callback and repeated opaque PDF
`HEAD`/`GET` behavior, then inspect bounded worker logs without secrets. Do not
send Sandbox, email, or broad payroll notifications as a substitute.

To roll back: set both official flags to `false`, stop
`official_whatsapp_worker`, then run `docker compose --env-file deploy/.env.production -f deploy/compose.production.yml run --rm backend python -m app.workers.official_whatsapp_runner --rollback-unleased`. This cancels only unleased queued WhatsApp jobs, revokes only their bound media tokens, and preserves batches/events
for audit. There is no email fallback for readiness, opt-out, blocked, pending,
or ambiguous outcomes. These migrations are additive: image rollback is allowed
only after schema compatibility is proven; database restore remains the separate
approved backup-and-restore boundary documented above.
