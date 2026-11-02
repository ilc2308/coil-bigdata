#!/bin/bash
# ============================================================
# DuckDNS Auto-Updater for COIL Big Data (AWS Learner Lab)
# Dominio: coilupbsalud.duckdns.org
# ============================================================

DUCKDNS_DOMAIN="coilupbsalud"
DUCKDNS_TOKEN="2a67e81e-9b03-4e0b-8cdc-c46634951d12"

# DuckDNS detecta la IP pública llamante si se deja ip= vacío
curl -s "https://www.duckdns.org/update?domains=${DUCKDNS_DOMAIN}&token=${DUCKDNS_TOKEN}&ip=" > /dev/null 2>&1
