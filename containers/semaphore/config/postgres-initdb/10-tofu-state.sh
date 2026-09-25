#!/bin/sh
# Creates the OpenTofu state database beside Semaphore's own, with a role that
# owns only that database. The postgres image runs this once, on the first
# start of an empty data directory, and never again. Changing the password
# later means ALTER ROLE by hand. See docs/semaphore-setup.md.
set -e

: "${TOFU_STATE_POSTGRES_PASSWORD:?TOFU_STATE_POSTGRES_PASSWORD is not set}"

psql -v ON_ERROR_STOP=1 -v pw="$TOFU_STATE_POSTGRES_PASSWORD" \
  --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<'SQL'
CREATE ROLE tofu LOGIN PASSWORD :'pw';
CREATE DATABASE tofu_state OWNER tofu;
SQL
