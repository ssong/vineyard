# Vineyard Factory - Deployment Guide

This guide covers deploying the Vineyard Factory on a Hetzner VPS with Cloudflare for DNS and SSL.

## Architecture Overview

```
┌─────────────────┐     HTTPS      ┌──────────────┐     HTTP      ┌─────────────────┐
│     Linear      │ ──────────────▶│  Cloudflare  │ ─────────────▶│  Hetzner VPS    │
│   (webhooks)    │   Port 443     │   (proxy)    │   Port 8000   │  (factory)      │
└─────────────────┘                └──────────────┘               └─────────────────┘
                                                                          │
                                                                          │ WebSocket
                                                                          ▼
                                                                   ┌─────────────────┐
                                                                   │     Slack       │
                                                                   │  (Socket Mode)  │
                                                                   └─────────────────┘
```

## Prerequisites

- Hetzner VPS (CX21 or larger recommended)
- Domain name with Cloudflare DNS
- Linear workspace (for webhooks)
- Slack workspace with app configured

---

## Step 1: Hetzner VPS Setup

### 1.1 Create Server

1. Log into [Hetzner Cloud Console](https://console.hetzner.cloud)
2. Create new project or select existing
3. Add Server:
   - **Location**: Choose closest to your users
   - **Image**: Ubuntu 24.04
   - **Type**: CX21 (2 vCPU, 4GB RAM) or larger
   - **SSH Key**: Add your public key
   - **Name**: `vineyard-factory`

### 1.2 Initial Server Setup

```bash
# SSH into server
ssh root@<your-server-ip>

# Update system
apt update && apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sh

# Create app user
useradd -m -s /bin/bash vineyard
usermod -aG docker vineyard

# Create app directory
mkdir -p /opt/vineyard
chown vineyard:vineyard /opt/vineyard

# Create state directory with secure permissions
mkdir -p /var/lib/vineyard-factory/state
chown vineyard:vineyard /var/lib/vineyard-factory/state
chmod 700 /var/lib/vineyard-factory/state
```

### 1.3 Configure Firewall

```bash
# Install ufw if not present
apt install ufw -y

# Allow SSH
ufw allow 22/tcp

# Allow HTTP/HTTPS (Cloudflare will proxy to 8000)
ufw allow 80/tcp
ufw allow 443/tcp

# Allow webhook port (optional, for direct access)
ufw allow 8000/tcp

# Enable firewall
ufw enable
```

---

## Step 2: Cloudflare Setup

### 2.1 Add Domain to Cloudflare

1. Log into [Cloudflare Dashboard](https://dash.cloudflare.com)
2. Add your domain if not already added
3. Update nameservers at your registrar to Cloudflare's

### 2.2 Create DNS Record

1. Go to **DNS** → **Records**
2. Add an A record:
   - **Type**: A
   - **Name**: `factory` (or your preferred subdomain)
   - **IPv4 address**: Your Hetzner server IP
   - **Proxy status**: Proxied (orange cloud)
   - **TTL**: Auto

This creates `factory.yourdomain.com`

### 2.3 Configure SSL/TLS

1. Go to **SSL/TLS** → **Overview**
2. Set encryption mode to **Full (strict)**
3. Go to **SSL/TLS** → **Origin Server**
4. Create Origin Certificate:
   - Click **Create Certificate**
   - Keep defaults (RSA 2048, 15 years)
   - Add hostnames: `factory.yourdomain.com`, `*.yourdomain.com`
   - Click **Create**
   - **Save the certificate and private key** (you'll need these)

### 2.4 Configure Cloudflare Settings

1. **SSL/TLS** → **Edge Certificates**:
   - Always Use HTTPS: ON
   - Minimum TLS Version: 1.2

2. **Security** → **WAF**:
   - Consider adding rate limiting for `/webhooks/*`

---

## Step 3: Server SSL Configuration

### 3.1 Install Origin Certificate

```bash
# SSH as root
ssh root@<your-server-ip>

# Create SSL directory
mkdir -p /etc/ssl/cloudflare

# Create certificate file (paste the certificate from Cloudflare)
nano /etc/ssl/cloudflare/origin.pem

# Create private key file (paste the private key from Cloudflare)
nano /etc/ssl/cloudflare/origin.key

# Set permissions
chmod 600 /etc/ssl/cloudflare/origin.key
chmod 644 /etc/ssl/cloudflare/origin.pem
```

### 3.2 Install Nginx as Reverse Proxy

```bash
apt install nginx -y

# Create Nginx config
cat > /etc/nginx/sites-available/vineyard << 'EOF'
server {
    listen 80;
    server_name factory.ssong.dev;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name factory.ssong.dev;

    ssl_certificate /etc/ssl/cloudflare/origin.pem;
    ssl_certificate_key /etc/ssl/cloudflare/origin.key;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
    ssl_prefer_server_ciphers off;

    # Cloudflare IP verification (optional but recommended)
    # set_real_ip_from 103.21.244.0/22;
    # set_real_ip_from 103.22.200.0/22;
    # ... add all Cloudflare IPs
    # real_ip_header CF-Connecting-IP;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        proxy_read_timeout 86400;
    }

    location /health {
        proxy_pass http://127.0.0.1:8000/health;
        access_log off;
    }
}
EOF

# Enable site
ln -s /etc/nginx/sites-available/vineyard /etc/nginx/sites-enabled/
rm /etc/nginx/sites-enabled/default

# Test and reload
nginx -t && systemctl reload nginx
```

---

## Step 4: Deploy Factory

### 4.1 Clone Repository

```bash
# Switch to vineyard user
su - vineyard

# Clone repository
cd /opt/vineyard
git clone https://github.com/your-org/vineyard.git .
# Or copy files via scp/rsync
```

### 4.2 Create Environment File

```bash
cat > /opt/vineyard/factory/.env << 'EOF'
# Slack (Socket Mode)
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_APP_TOKEN=xapp-your-app-token

# Anthropic
ANTHROPIC_API_KEY=sk-ant-your-key

# Linear (REQUIRED for webhooks)
LINEAR_API_KEY=lin_api_your-key
LINEAR_WEBHOOK_SECRET=your-webhook-secret-from-linear

# API Server
API_HOST=0.0.0.0
API_PORT=8000

# State persistence (secure directory)
FACTORY_STATE_DIR=/var/lib/vineyard-factory/state

# Storage backend: "file" (default) or "redis"
# FACTORY_STORAGE_BACKEND=file

# Redis (optional - for production scalability)
# REDIS_URL=redis://localhost:6379/0

# Optional
LOG_LEVEL=INFO
EOF

chmod 600 /opt/vineyard/factory/.env
```

### 4.3 Build Docker Image

```bash
cd /opt/vineyard/factory

# Build the image
docker build -t vineyard-factory:latest .

# Verify image was created
docker images | grep vineyard-factory
```

### 4.4 Run Container

```bash
# Run the factory container
docker run -d \
  --name vineyard-factory \
  --restart unless-stopped \
  -p 127.0.0.1:8000:8000 \
  --env-file /opt/vineyard/factory/.env \
  -v /var/lib/vineyard-factory/state:/var/lib/vineyard-factory/state \
  --health-cmd="curl -f http://localhost:8000/health || exit 1" \
  --health-interval=30s \
  --health-timeout=10s \
  --health-retries=3 \
  --health-start-period=10s \
  vineyard-factory:latest

# Verify container is running
docker ps | grep vineyard-factory

# Check logs
docker logs -f vineyard-factory
```

### 4.5 Create Systemd Service

```bash
# As root
cat > /etc/systemd/system/vineyard-factory.service << 'EOF'
[Unit]
Description=Vineyard Factory
After=docker.service
Requires=docker.service

[Service]
Type=simple
User=vineyard
Restart=always
RestartSec=10

# Stop and remove existing container (if any)
ExecStartPre=-/usr/bin/docker stop vineyard-factory
ExecStartPre=-/usr/bin/docker rm vineyard-factory

# Start the container
ExecStart=/usr/bin/docker run \
  --name vineyard-factory \
  -p 127.0.0.1:8000:8000 \
  --env-file /opt/vineyard/factory/.env \
  -v /var/lib/vineyard-factory/state:/var/lib/vineyard-factory/state \
  vineyard-factory:latest

# Stop container on service stop
ExecStop=/usr/bin/docker stop vineyard-factory

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable vineyard-factory
systemctl start vineyard-factory

# Check status
systemctl status vineyard-factory
```

### 4.6 Redis Setup (Optional)

Redis is optional but recommended for production deployments. It provides:
- Persistent state storage with TTL
- Shared state across multiple instances (if scaling horizontally)
- Better performance for high-volume operations

#### Option A: Install Redis on the VPS

```bash
# Install Redis
apt install redis-server -y

# Configure Redis for security
cat >> /etc/redis/redis.conf << 'EOF'

# Bind to localhost only
bind 127.0.0.1

# Require password
requirepass your-secure-redis-password

# Disable dangerous commands
rename-command FLUSHDB ""
rename-command FLUSHALL ""
rename-command DEBUG ""
rename-command CONFIG ""
EOF

# Restart Redis
systemctl restart redis-server
systemctl enable redis-server

# Verify Redis is running
redis-cli -a your-secure-redis-password ping
# Should return: PONG
```

Update your `.env` file:

```bash
# Enable Redis storage
FACTORY_STORAGE_BACKEND=redis
REDIS_URL=redis://:your-secure-redis-password@127.0.0.1:6379/0
```

#### Option B: Use Managed Redis (Recommended for Production)

For production, consider using a managed Redis service:
- **Hetzner**: No native Redis, but you can use Docker
- **Upstash**: Serverless Redis with generous free tier
- **Redis Cloud**: Managed Redis by Redis Labs
- **AWS ElastiCache** / **GCP Memorystore**: If using cloud providers

Example with Upstash:

```bash
# In your .env file
FACTORY_STORAGE_BACKEND=redis
REDIS_URL=rediss://default:your-password@your-endpoint.upstash.io:6379
```

Note: Use `rediss://` (with double 's') for TLS connections.

#### Option C: Redis in Docker

```bash
# Create Redis data directory
mkdir -p /var/lib/redis-data
chown 999:999 /var/lib/redis-data

# Run Redis container
docker run -d \
  --name vineyard-redis \
  --restart unless-stopped \
  -p 127.0.0.1:6379:6379 \
  -v /var/lib/redis-data:/data \
  redis:7-alpine \
  redis-server --appendonly yes --requirepass your-secure-redis-password

# Update .env
FACTORY_STORAGE_BACKEND=redis
REDIS_URL=redis://:your-secure-redis-password@127.0.0.1:6379/0
```

#### Verify Redis Connection

```bash
# Test from container
docker exec vineyard-factory python -c "
import redis
import os
r = redis.from_url(os.environ.get('REDIS_URL', 'redis://localhost:6379'))
print('Redis connected:', r.ping())
"
```

---

## Step 5: Configure Linear Webhook

### 5.1 Create Webhook in Linear

1. Go to [Linear Settings](https://linear.app/settings) → **API** → **Webhooks**
2. Click **New webhook**
3. Configure:
   - **Label**: `Vineyard Factory`
   - **URL**: `https://factory.yourdomain.com/webhooks/linear`
   - **Events**: Select the following:
     - `Issues` → `Create`, `Update`
     - `Comments` → `Create`
   - **Team**: Select your team (or all teams)
4. Click **Create webhook**
5. **Copy the signing secret** - add this to your `.env` as `LINEAR_WEBHOOK_SECRET`

### 5.2 Verify Webhook

```bash
# Check webhook status endpoint
curl https://factory.yourdomain.com/webhooks/linear/status

# Expected response:
# {"webhook_secret_configured": true, "retry_keywords": ["retry", ...], "status": "ready"}
```

### 5.3 Test Webhook

1. Go to any issue in Linear
2. Add a comment: "retry"
3. Check factory logs:
   ```bash
   docker compose logs -f | grep -i webhook
   ```

---

## Step 6: Monitoring & Maintenance

### 6.1 View Logs

```bash
# Follow all logs
docker logs -f vineyard-factory

# Last 100 lines
docker logs --tail 100 vineyard-factory

# Filter by component
docker logs vineyard-factory 2>&1 | grep -E "(webhook|Linear|retry)"

# With timestamps
docker logs -t vineyard-factory
```

### 6.2 Health Check

```bash
# Container health status
docker inspect --format='{{.State.Health.Status}}' vineyard-factory

# Local health check
curl http://localhost:8000/health

# External health check
curl https://factory.ssong.dev/health

# Webhook status
curl https://factory.ssong.dev/webhooks/linear/status
```

### 6.3 Update Deployment

```bash
cd /opt/vineyard/factory

# Pull latest code
git pull

# Rebuild image
docker build -t vineyard-factory:latest .

# Stop and remove old container
docker stop vineyard-factory
docker rm vineyard-factory

# Start new container
docker run -d \
  --name vineyard-factory \
  --restart unless-stopped \
  -p 127.0.0.1:8000:8000 \
  --env-file /home/vineyard/factory/.env \
  -v /var/lib/vineyard-factory/state:/var/lib/vineyard-factory/state \
  --health-cmd="curl -f http://localhost:8000/health || exit 1" \
  --health-interval=30s \
  --health-timeout=10s \
  --health-retries=3 \
  vineyard-factory:latest

# Or if using systemd
systemctl restart vineyard-factory
```

### 6.4 Backup State

```bash
# Backup state directory
tar czf ~/factory-state-backup-$(date +%Y%m%d).tar.gz /var/lib/vineyard-factory/state

# Restore state
tar xzf factory-state-backup-YYYYMMDD.tar.gz -C /
```

### 6.5 Container Management

```bash
# Restart container
docker restart vineyard-factory

# Stop container
docker stop vineyard-factory

# Start container
docker start vineyard-factory

# Remove container (data persists in state directory)
docker rm vineyard-factory

# View container resource usage
docker stats vineyard-factory

# Execute command inside container
docker exec -it vineyard-factory /bin/bash

# Check container environment
docker exec vineyard-factory env | grep -E "(SLACK|LINEAR|API)"
```

### 6.6 Cleanup

```bash
# Remove old images
docker image prune -f

# Remove all unused images (caution)
docker image prune -a

# View disk usage
docker system df
```

---

## Webhook Retry Logic

The webhook endpoint supports two ways to trigger retries:

### 1. Comment-based Retry

Add any of these keywords to a comment on a failed issue:
- `retry`
- `try again`
- `rerun`
- `re-run`
- `restart`

**Example:**
```
Comment: "retry - fixed the API key issue"
→ Factory automatically resumes
```

### 2. State Change Retry (Drag & Drop)

Simply drag a failed issue back to "Todo" or "In Progress" in Linear's board view.

**Triggers when moving FROM:**
- `Canceled`
- `Cancelled`
- `Blocked`
- `Failed`

**TO any of:**
- `Todo` / `To Do`
- `Backlog`
- `In Progress`
- `Started`

**Example Flow:**
```
1. Factory phase fails → Issue moves to "Canceled" state
2. You investigate and fix the underlying issue
3. Drag the issue back to "Todo" column in Linear
4. Factory automatically detects state change
5. Adds comment: "Issue moved from Canceled to Todo. Resuming..."
6. Factory resumes from failed phase
7. Progress updates appear as comments
```

### How It Works

```
┌─────────────┐     webhook      ┌─────────────┐     resume      ┌─────────────┐
│   Linear    │ ───────────────▶ │   Factory   │ ──────────────▶ │    Agent    │
│  (drag to   │  Issue.update    │  (detect    │                 │  (retry     │
│   Todo)     │                  │   state Δ)  │                 │   phase)    │
└─────────────┘                  └─────────────┘                 └─────────────┘
      │                                │                               │
      │                                ▼                               │
      │                         Add comment:                           │
      │                         "Resuming..."                          │
      │                                │                               │
      │◀───────────────────────────────┴───────────────────────────────┘
      │                         Add comment:
      │                         "Phase completed" / "Failed again"
```

### Requirements

- The issue must be associated with a factory execution (tracked in state)
- The factory execution must be in a `FAILED` state
- Signature verification must pass (if `LINEAR_WEBHOOK_SECRET` is set)

---

## Troubleshooting

### Webhook not receiving events

1. Check Cloudflare is proxying correctly:
   ```bash
   curl -I https://factory.ssong.dev/health
   # Should show cf-ray header
   ```

2. Verify webhook secret is configured:
   ```bash
   curl https://factory.ssong.dev/webhooks/linear/status
   # Should show: "webhook_secret_configured": true
   ```

3. Check Linear webhook status in Linear Settings → API → Webhooks
   - Look for delivery failures
   - Check the signing secret matches

4. Check Nginx logs:
   ```bash
   tail -f /var/log/nginx/error.log
   ```

### Factory not starting

1. Check Docker logs:
   ```bash
   docker logs vineyard-factory
   ```

2. Check container status:
   ```bash
   docker ps -a | grep vineyard-factory
   docker inspect vineyard-factory | grep -A 5 "State"
   ```

3. Verify environment variables:
   ```bash
   docker exec vineyard-factory env | grep -E "(SLACK|LINEAR|API)"
   ```

4. Check state directory permissions:
   ```bash
   ls -la /var/lib/vineyard-factory/state
   # Should be owned by vineyard user with mode 700
   ```

### SSL/TLS errors

1. Verify Cloudflare SSL mode is "Full (strict)"
2. Check origin certificate hasn't expired
3. Ensure certificate hostnames match

### Rate limiting issues

1. Check if you're being rate limited:
   ```bash
   curl -I https://factory.ssong.dev/webhooks/linear/status
   # Look for 429 status or X-RateLimit headers
   ```

2. Default limits:
   - Global: 100 requests/minute per IP
   - Webhook endpoint: 30 requests/minute per IP

### Redis connection issues

1. Check Redis is running:
   ```bash
   # If using system Redis
   systemctl status redis-server

   # If using Docker Redis
   docker ps | grep redis
   docker logs vineyard-redis
   ```

2. Test Redis connectivity:
   ```bash
   # Local Redis
   redis-cli -a your-password ping

   # From factory container
   docker exec vineyard-factory python -c "
   import redis, os
   r = redis.from_url(os.environ.get('REDIS_URL'))
   print('Ping:', r.ping())
   print('Keys:', r.keys('factory:*'))
   "
   ```

3. Check Redis URL format:
   ```bash
   # Standard format
   redis://:password@host:port/db

   # TLS format (for managed Redis)
   rediss://:password@host:port/db
   ```

4. Verify storage backend:
   ```bash
   docker exec vineyard-factory env | grep -E "(REDIS|STORAGE)"
   # Should show:
   # FACTORY_STORAGE_BACKEND=redis
   # REDIS_URL=redis://...
   ```

5. Check state files exist (file backend fallback):
   ```bash
   ls -la /var/lib/vineyard-factory/state/
   ```

6. Redis memory issues:
   ```bash
   redis-cli -a your-password INFO memory
   # Check used_memory_human and maxmemory
   ```

---

## Security Checklist

- [ ] Firewall configured (ufw)
- [ ] SSH key authentication only (disable password auth)
- [ ] Cloudflare proxy enabled (hides origin IP)
- [ ] Origin certificate installed
- [ ] LINEAR_WEBHOOK_SECRET configured
- [ ] Environment file permissions (600)
- [ ] Non-root user running containers
- [ ] Regular security updates scheduled
- [ ] Redis password configured (if using Redis)
- [ ] Redis bound to localhost only (if local)
