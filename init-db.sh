#!/bin/bash
set -e
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    SELECT 'CREATE DATABASE fss_db' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'fss_db')\gexec
    SELECT 'CREATE DATABASE fas_db' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'fas_db')\gexec
EOSQL
logger() {
  echo "[init-db.sh] $1"
}
logger "Finished ensuring fss_db and fas_db exist." 