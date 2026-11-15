#!/bin/sh
set -eu
if [ -z "$ODOO_URL" ]; then ODOO_URL=$(awk '$1=="ODOO_URL" {print $2}' /opt/releases.txt); fi
if [ -z "$PGADMIN_URL" ]; then PGADMIN_URL=$(awk '$1=="PGADMIN_URL" {print $2}' /opt/releases.txt); fi
export ODOO_URL PGADMIN_URL
exec python /opt/app.py
