#!/usr/bin/env bash
# ==============================================================================
# OpsSentinel Health Check Utility for Docker Containers in WSL
# ==============================================================================
set -euo pipefail

echo "========================================================"
echo " Checking OpsSentinel Service Status inside WSL 2..."
echo "========================================================"

# Check PostgreSQL
echo -n "Checking PostgreSQL with pgvector (localhost:5432)... "
until docker exec opssentinel-postgres pg_isready -U postgres -d opssentinel > /dev/null 2>&1; do
    echo -n "."
    sleep 2
done
echo " [ONLINE & HEALTHY]"

# Check n8n
echo -n "Checking n8n Automation Engine (http://localhost:5678)... "
until curl -s -f http://localhost:5678/healthz > /dev/null 2>&1 || wget -q -O - http://localhost:5678/healthz > /dev/null 2>&1; do
    echo -n "."
    sleep 2
done
echo " [ONLINE & HEALTHY]"

echo ""
echo "All OpsSentinel backing services are online!"
echo "Access n8n at: http://localhost:5678"
echo "PostgreSQL available at: postgresql://postgres:postgres@localhost:5432/opssentinel"
echo "========================================================"
