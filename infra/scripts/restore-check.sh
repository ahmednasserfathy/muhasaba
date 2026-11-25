#!/usr/bin/env bash
# Restore only into a newly-created disposable database; never overwrite live data.
set -euo pipefail
root="$(cd "$(dirname "$0")/../.." && pwd)"
if [[ $# != 2 ]]; then
  echo 'Usage: restore-check.sh BACKUP.dump NEW_DATABASE_restore_test' >&2
  exit 2
fi
archive="$1"
database="$2"
[[ "$database" =~ ^[a-z][a-z0-9_]*_restore_test$ ]] || { echo 'Use a disposable *_restore_test database' >&2; exit 2; }
[[ -f "$archive" && -r "$archive" ]] || { echo 'Backup is not readable' >&2; exit 2; }
compose=(docker compose --env-file "$root/.env" -f "$root/infra/compose.yml")
"${compose[@]}" exec -T db createdb -U postgres -O muhasaba "$database"
"${compose[@]}" exec -T db pg_restore -U muhasaba --dbname "$database" \
  --no-owner --no-acl --exit-on-error --single-transaction < "$archive"
echo 'Restored into a new disposable database. Run application verification before any cutover.'
