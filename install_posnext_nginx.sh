#!/usr/bin/env bash

set -Eeuo pipefail

SW_LOCATION='location = /assets/pos_next/pos/sw.js'

log() {
    echo "[POSNext Nginx] $*"
}

fail() {
    echo "[POSNext Nginx] ERROR: $*" >&2
    exit 1
}

if [ "${EUID}" -ne 0 ]; then
    fail "Run this script with sudo."
fi

for cmd in nginx python3 cp grep date; do
    command -v "${cmd}" >/dev/null 2>&1 || fail "Required command not found: ${cmd}"
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BENCH_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
NGINX_CONF="${BENCH_DIR}/config/nginx.conf"

if [ ! -f "${NGINX_CONF}" ]; then
    fail "Bench Nginx config not found: ${NGINX_CONF}"
fi

log "Bench directory: ${BENCH_DIR}"
log "Nginx config: ${NGINX_CONF}"

#
# Already installed: do not modify anything.
#
if grep -Fq "${SW_LOCATION}" "${NGINX_CONF}"; then
    log "POSNext Service Worker configuration already installed."

    if nginx -t; then
        log "Nginx configuration is valid."
        log "No changes required."
        exit 0
    fi

    fail "Existing Nginx configuration is invalid."
fi

#
# Verify that this looks like a Bench-generated config with
# the standard assets location.
#
if ! grep -Eq '^[[:space:]]*location /assets[[:space:]]*\{' "${NGINX_CONF}"; then
    fail 'Could not find "location /assets {" in the Bench Nginx config.'
fi

TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="${NGINX_CONF}.before-posnext-${TIMESTAMP}"

cp -a "${NGINX_CONF}" "${BACKUP}"

log "Backup created: ${BACKUP}"

restore_backup() {
    log "Restoring original Nginx configuration..."
    cp -a "${BACKUP}" "${NGINX_CONF}"
}

#
# Insert the POSNext Service Worker location immediately before
# the standard Bench /assets location.
#
if ! python3 - "${NGINX_CONF}" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
text = path.read_text()

if "location = /assets/pos_next/pos/sw.js" in text:
    print("POSNext Service Worker block already exists.")
    raise SystemExit(0)

lines = text.splitlines(keepends=True)

insert_at = None
indent = ""

for index, line in enumerate(lines):
    if line.strip() == "location /assets {":
        insert_at = index
        indent = line[: len(line) - len(line.lstrip())]
        break

if insert_at is None:
    raise SystemExit('Could not locate "location /assets {"')

block = (
    f'{indent}location = /assets/pos_next/pos/sw.js {{\n'
    f'{indent}\ttry_files $uri =404;\n'
    f'{indent}\tadd_header Cache-Control "no-cache, no-store, must-revalidate";\n'
    f'{indent}\tadd_header Service-Worker-Allowed "/pos" always;\n'
    f'{indent}}}\n\n'
)

lines.insert(insert_at, block)
path.write_text("".join(lines))

print("POSNext Service Worker block inserted.")
PY
then
    restore_backup
    fail "Could not update the Bench Nginx configuration."
fi

log "POSNext Service Worker configuration added."

#
# Never reload an invalid configuration.
#
if ! nginx -t; then
    log "Nginx validation failed."
    restore_backup

    if nginx -t; then
        log "Original configuration restored successfully."
    else
        fail "Original configuration was restored, but nginx -t is still failing."
    fi

    exit 1
fi

log "Nginx configuration test passed."

#
# Reload only after successful validation.
#
if command -v systemctl >/dev/null 2>&1; then
    if ! systemctl reload nginx; then
        restore_backup
        fail "Nginx reload failed. Original configuration restored."
    fi
else
    if ! nginx -s reload; then
        restore_backup
        fail "Nginx reload failed. Original configuration restored."
    fi
fi

log "Nginx reloaded successfully."
log "POSNext Service Worker is allowed to control /pos."
log "Installation complete."
