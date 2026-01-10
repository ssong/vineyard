# Vineyard Bot Deployment Guide

Complete guide to deploying the unified Vineyard Bot using Docker CLI.

## Prerequisites

- Docker installed on your server
- Slack App with Socket Mode enabled
- API keys: Anthropic, Linear, Tavily
- Redis server (running on host or separate container)

## Quick Start

```bash
# 1. Clone the repository
git clone <your-repo> && cd vineyard

# 2. Create .env file from template
cp .env.example .env

# 3. Edit .env with your API keys
nano .env

# 4. Create required directories
mkdir -p outputs state
chmod 755 outputs state

# 5. Build the Docker image
docker build -t vineyard .

# 6. Create Docker network for container communication
docker network create vineyard-net 2>/dev/null || true

# 7. Start Redis container
docker run -d \
  --name vineyard-redis \
  --network vineyard-net \
  --restart unless-stopped \
  redis:7-alpine

# 8. Run the Vineyard bot
docker run -d \
  --name vineyard \
  --network vineyard-net \
  --restart unless-stopped \
  --env-file .env \
  -e REDIS_URL=redis://vineyard-redis:6379 \
  -v $(pwd)/outputs:/app/outputs \
  -v $(pwd)/state:/app/state \
  -p 8000:8000 \
  vineyard

# 9. Check it's running
docker logs -f vineyard

# 10. Verify health check
curl http://localhost:8000/health
```

---

## Detailed Commands

### Building the Image

```bash
# Build with default tag
docker build -t vineyard .

# Build with version tag
docker build -t vineyard:1.0.0 .

# Build with no cache (useful after dependency updates)
docker build --no-cache -t vineyard .
```

### Running the Container

**Full deployment (Slack bot + API server + Redis):**
```bash
# Create network and start Redis (if not already running)
docker network create vineyard-net 2>/dev/null || true
docker run -d --name vineyard-redis --network vineyard-net --restart unless-stopped redis:7-alpine 2>/dev/null || true

# Start Vineyard bot
docker run -d \
  --name vineyard \
  --network vineyard-net \
  --restart unless-stopped \
  --env-file .env \
  -e REDIS_URL=redis://vineyard-redis:6379 \
  -v $(pwd)/outputs:/app/outputs \
  -v $(pwd)/state:/app/state \
  -p 8000:8000 \
  vineyard
```

**Slack-only mode (no API server):**
```bash
docker run -d \
  --name vineyard \
  --restart unless-stopped \
  --env-file .env \
  -v $(pwd)/outputs:/app/outputs \
  vineyard python main.py --mode slack
```

**API-only mode (for webhooks only):**
```bash
docker run -d \
  --name vineyard-api \
  --restart unless-stopped \
  --env-file .env \
  -p 8000:8000 \
  vineyard python main.py --mode api
```

### Volume Mounts Explained

| Host Path | Container Path | Purpose |
|-----------|----------------|---------|
| `./outputs` | `/app/outputs` | Research reports (PDFs) |
| `./state` | `/app/state` | Factory execution state |
| `./data` | `/root/.vineyard` | SQLite databases (research-agent, factory) |

**Setting up volumes:**
```bash
# Create directories with correct permissions
mkdir -p outputs state data/research-agent data/factory
chmod 700 data data/research-agent data/factory  # Secure DB directories
chmod 755 outputs state

# If permission denied errors occur:
sudo chown -R 1000:1000 outputs state data
```

### Updated Docker Run Command

```bash
docker run -d \
  --name vineyard \
  --network vineyard-net \
  --restart unless-stopped \
  --env-file .env \
  -e REDIS_URL=redis://vineyard-redis:6379 \
  -e VINEYARD_DATA_DIR=/root/.vineyard/research-agent \
  -e FACTORY_STATE_DIR=/root/.vineyard/factory \
  -v $(pwd)/outputs:/app/outputs \
  -v $(pwd)/state:/app/state \
  -v $(pwd)/data:/root/.vineyard \
  -p 8000:8000 \
  vineyard
```

### Port Mapping

| Port | Purpose |
|------|---------|
| 8000 | Linear webhook endpoint (`POST /webhooks/linear`) |

---

## Management Commands

### View Logs

```bash
# Follow logs in real-time
docker logs -f vineyard

# Show last 100 lines
docker logs --tail 100 vineyard

# Show logs with timestamps
docker logs -t vineyard
```

### Stop and Start

```bash
# Stop the container
docker stop vineyard

# Start it again
docker start vineyard

# Restart
docker restart vineyard
```

### Updating the Bot

```bash
# Pull latest code
git pull origin main

# Rebuild image
docker build -t vineyard .

# Stop and remove old container
docker stop vineyard
docker rm vineyard

# Run new container
docker run -d \
  --name vineyard \
  --restart unless-stopped \
  --env-file .env \
  -v $(pwd)/outputs:/app/outputs \
  -v $(pwd)/state:/app/state \
  -p 8000:8000 \
  vineyard
```

### One-liner Update Script

```bash
git pull && \
docker build -t vineyard . && \
docker rm -f vineyard && \
docker network create vineyard-net 2>/dev/null || true && \
docker run -d --name vineyard-redis --network vineyard-net --restart unless-stopped redis:7-alpine 2>/dev/null || true && \
docker run -d \
  --name vineyard \
  --network vineyard-net \
  --restart unless-stopped \
  --env-file .env \
  -e REDIS_URL=redis://vineyard-redis:6379 \
  -v $(pwd)/outputs:/app/outputs \
  -v $(pwd)/state:/app/state \
  -p 8000:8000 \
  vineyard && \
docker logs -f vineyard
```

---

## Environment Variables

### Required

| Variable | Description |
|----------|-------------|
| `SLACK_BOT_TOKEN` | Bot token (`xoxb-...`) |
| `SLACK_APP_TOKEN` | App-level token for Socket Mode (`xapp-...`) |
| `ANTHROPIC_API_KEY` | Claude API key |
| `TAVILY_API_KEY` | Web search API key |
| `LINEAR_API_KEY` | Linear API key |

### Optional

| Variable | Default | Description |
|----------|---------|-------------|
| `OPERATOR_SLACK_USER_ID` | - | Auto-added to opportunity channels |
| `LINEAR_WEBHOOK_SECRET` | - | For verifying webhook signatures |
| `API_HOST` | `0.0.0.0` | API server bind address |
| `API_PORT` | `8000` | API server port |
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `FACTORY_STORAGE_BACKEND` | `file` | `file` or `redis` |
| `REDIS_URL` | - | Redis connection URL |

---

## Health Check

The container includes a health check hitting `GET /health`:

```bash
# Check health status
docker inspect --format='{{.State.Health.Status}}' vineyard

# View health logs
docker inspect --format='{{json .State.Health}}' vineyard | jq
```

---

## Troubleshooting

### "Permission denied" on outputs

```bash
# Fix permissions (container runs as UID 1000)
sudo chown -R 1000:1000 outputs state
chmod 755 outputs state
```

### Container keeps restarting

```bash
# Check what's wrong
docker logs --tail 50 vineyard

# Common issues:
# - Missing API keys in .env
# - Invalid Slack tokens
# - Network connectivity issues
```

### Port 8000 already in use

```bash
# Find what's using it
lsof -i :8000

# Use a different port
docker run ... -p 8001:8000 vineyard
```

### Slack commands not responding

1. Check container is running: `docker ps | grep vineyard`
2. Check logs for errors: `docker logs vineyard`
3. Verify Socket Mode is enabled in Slack App settings
4. Confirm `SLACK_APP_TOKEN` starts with `xapp-`

---

## Migrating from Separate Containers

If you previously ran research-agent and factory as separate containers:

```bash
# 1. Stop old containers
docker stop vineyard-research-agent vineyard-factory
docker rm vineyard-research-agent vineyard-factory

# 2. Merge your .env files
cat research-agent/.env factory/.env | sort -u > .env
# Then edit .env to remove duplicates

# 3. Build and run unified bot
docker build -t vineyard .
docker run -d \
  --name vineyard \
  --restart unless-stopped \
  --env-file .env \
  -v $(pwd)/outputs:/app/outputs \
  -v $(pwd)/state:/app/state \
  -p 8000:8000 \
  vineyard
```
