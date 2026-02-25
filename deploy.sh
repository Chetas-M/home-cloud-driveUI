#!/bin/bash
set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}Home Cloud Drive — Deploy${NC}"

# Pre-checks
command -v docker &>/dev/null || { echo -e "${RED}Docker not installed${NC}"; exit 1; }
docker info &>/dev/null || { echo -e "${RED}Docker not running${NC}"; exit 1; }

# Generate .env if missing
if [ ! -f .env ]; then
    SECRET_KEY=$(openssl rand -hex 32)
    cat > .env << EOF
SECRET_KEY=${SECRET_KEY}
MAX_STORAGE_BYTES=0
ACCESS_TOKEN_EXPIRE_MINUTES=1440
CORS_ORIGINS=*
EOF
    chmod 600 .env
    echo -e "${GREEN}✓ Generated .env${NC}"
fi

# Build & deploy
if [ "$1" == "--fresh" ]; then
    docker compose down --rmi local 2>/dev/null || true
    docker compose build --no-cache
else
    docker compose down 2>/dev/null || true
    docker compose build
fi

docker compose up -d
sleep 3

if docker compose ps | grep -qE "Up|running|Healthy"; then
    echo -e "${GREEN}✓ Deployed! Access at http://$(hostname -I | awk '{print $1}'):3001${NC}"
else
    echo -e "${RED}✗ Failed — check: docker compose logs${NC}"
    exit 1
fi
