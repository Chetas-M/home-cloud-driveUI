#!/bin/bash
# ================================================================
# Home Cloud Drive - Production Deployment Script
# ================================================================
# Usage: ./deploy.sh [--fresh]
#   --fresh : Clean rebuild (removes old containers and images)
# ================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}"
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║          Home Cloud Drive - Production Deployment         ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Check if running as root (we don't want that)
if [ "$EUID" -eq 0 ]; then
    echo -e "${RED}[ERROR] Do not run this script as root!${NC}"
    echo "Run as your regular user (chetas)"
    exit 1
fi

# Check Docker is installed and running
if ! command -v docker &> /dev/null; then
    echo -e "${RED}[ERROR] Docker is not installed!${NC}"
    exit 1
fi

if ! docker info &> /dev/null; then
    echo -e "${RED}[ERROR] Docker is not running or you don't have permission!${NC}"
    echo "Try: sudo usermod -aG docker \$USER && newgrp docker"
    exit 1
fi

# Parse arguments
FRESH_BUILD=false
if [ "$1" == "--fresh" ]; then
    FRESH_BUILD=true
fi

# ================================================================
# Step 1: Create directories
# ================================================================
echo -e "${YELLOW}[1/5] Creating directories...${NC}"

STORAGE_PATH="${STORAGE_PATH:-/mnt/homecloud/storage}"
DATA_PATH="${DATA_PATH:-/mnt/homecloud/data}"

mkdir -p "$STORAGE_PATH"
mkdir -p "$DATA_PATH"

echo "  ✓ Storage: $STORAGE_PATH"
echo "  ✓ Database: $DATA_PATH"

# ================================================================
# Step 2: Generate/check .env file
# ================================================================
echo -e "${YELLOW}[2/5] Checking environment configuration...${NC}"

if [ ! -f .env ]; then
    echo "  Generating secure .env file..."
    
    # Generate secure random key
    SECRET_KEY=$(openssl rand -hex 32)
    
    cat > .env << EOF
# Auto-generated on $(date)
# SECURITY: Keep this file secret!

SECRET_KEY=${SECRET_KEY}
STORAGE_PATH=${STORAGE_PATH}
DATA_PATH=${DATA_PATH}
MAX_STORAGE_BYTES=0
ACCESS_TOKEN_EXPIRE_MINUTES=1440
CORS_ORIGINS=http://192.168.1.8:3001,http://localhost:3001
EOF
    
    chmod 600 .env
    echo -e "  ${GREEN}✓ Generated new .env with secure secret key${NC}"
else
    echo "  ✓ Using existing .env file"
fi

# ================================================================
# Step 3: Clean up (if fresh build)
# ================================================================
if [ "$FRESH_BUILD" = true ]; then
    echo -e "${YELLOW}[3/5] Cleaning up old containers...${NC}"
    docker compose down --rmi local 2>/dev/null || true
    echo "  ✓ Cleaned up"
else
    echo -e "${YELLOW}[3/5] Stopping existing containers...${NC}"
    docker compose down 2>/dev/null || true
    echo "  ✓ Stopped"
fi

# ================================================================
# Step 4: Build containers
# ================================================================
echo -e "${YELLOW}[4/5] Building Docker containers...${NC}"
echo "  This may take a few minutes on first run..."

docker compose build --no-cache

echo -e "  ${GREEN}✓ Build complete${NC}"

# ================================================================
# Step 5: Start services
# ================================================================
echo -e "${YELLOW}[5/5] Starting services...${NC}"

docker compose up -d

# Wait for health check
echo "  Waiting for services to be ready..."
sleep 5

# Check if containers are running
if docker compose ps | grep -q "Up\|running"; then
    echo -e "  ${GREEN}✓ Services started successfully${NC}"
else
    echo -e "  ${RED}✗ Services failed to start${NC}"
    echo "  Check logs with: docker compose logs"
    exit 1
fi

# ================================================================
# Done!
# ================================================================
echo ""
echo -e "${GREEN}"
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║              Deployment Complete!                         ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo -e "${NC}"
echo ""
echo "  🌐 Access your cloud drive at:"
echo -e "     ${GREEN}http://192.168.1.8:3001${NC}"
echo ""
echo "  📁 Storage location: $STORAGE_PATH"
echo "  🗄️  Database location: $DATA_PATH"
echo ""
echo "  Useful commands:"
echo "    View logs:     docker compose logs -f"
echo "    Stop:          docker compose down"
echo "    Restart:       docker compose restart"
echo "    Status:        docker compose ps"
echo ""
