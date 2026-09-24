#!/bin/bash
# =============================================================================
# Wait for services to be ready
# =============================================================================
# Usage: ./scripts/wait_for_services.sh

set -e

echo "=== Waiting for services to be ready ==="

# Wait for PostgreSQL
echo "Waiting for PostgreSQL..."
for i in {1..30}; do
    if pg_isready -h localhost -p 5432 -U finance_ai_v3 -d finance_ai_v3 > /dev/null 2>&1; then
        echo "  PostgreSQL is ready!"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "  PostgreSQL failed to start!"
        exit 1
    fi
    echo "  Waiting... ($i/30)"
    sleep 2
done

# Wait for Redis
echo "Waiting for Redis..."
for i in {1..15}; do
    if redis-cli -h localhost -p 6379 ping > /dev/null 2>&1; then
        echo "  Redis is ready!"
        break
    fi
    if [ $i -eq 15 ]; then
        echo "  Redis failed to start!"
        exit 1
    fi
    echo "  Waiting... ($i/15)"
    sleep 2
done

# Wait for Qdrant
echo "Waiting for Qdrant..."
for i in {1..15}; do
    if curl -s http://localhost:6333/health > /dev/null 2>&1; then
        echo "  Qdrant is ready!"
        break
    fi
    if [ $i -eq 15 ]; then
        echo "  Qdrant failed to start!"
        exit 1
    fi
    echo "  Waiting... ($i/15)"
    sleep 2
done

# Wait for LiteLLM
echo "Waiting for LiteLLM..."
for i in {1..15}; do
    if curl -s http://localhost:4000/health > /dev/null 2>&1; then
        echo "  LiteLLM is ready!"
        break
    fi
    if [ $i -eq 15 ]; then
        echo "  LiteLLM failed to start (this is OK for dev)!"
    fi
    sleep 2
done

echo "=== All services ready ==="
