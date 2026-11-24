#!/usr/bin/env bash
# Local Compose backup. Treat the resulting archive as private account data.
set -euo pipefail
umask 077
root="$(cd "$(dirname "$0")/../.." && pwd)"
if [[ $# -lt 1 || $# -gt 2 ]]; then
  echo 'Usage: backup.sh OUTPUT.dump [DATABASE]' >&2
  exit 2
fi
output="$1"
database="${2:-muhasaba}"
[[ "$database" =~ ^[a-z][a-z0-9_]*$ ]] || { echo 'Invalid database name' >&2; exit 2; }
[[ ! -e "$output" ]] || { echo 'Refusing to overwrite an existing backup' >&2; exit 2; }
temporary="$(mktemp "${output}.partial.XXXXXX")"
trap 'rm -f "$temporary"' EXIT
docker compose --env-file "$root/.env" -f "$root/infra/compose.yml" exec -T db \
  pg_dump -U muhasaba --format=custom --no-owner --no-acl --dbname "$database" > "$temporary"
# Hard-link creation is atomic and refuses a competing existing destination.
ln "$temporary" "$output"
echo 'Backup created. Store it encrypted with restricted access.'
