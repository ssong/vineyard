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

# Install Docker Compose
apt install docker-compose-plugin -y

# Create app user
useradd -m -s /bin/bash vineyard
usermod -aG docker vineyard

# Create app directory
mkdir -p /opt/vineyard
chown vineyard:vineyard /opt/vineyard
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

# Linear
LINEAR_API_KEY=lin_api_your-key
LINEAR_WEBHOOK_SECRET=your-webhook-secret-from-linear

# API Server
API_HOST=0.0.0.0
API_PORT=8000

# Optional
LOG_LEVEL=INFO
EOF

chmod 600 /opt/vineyard/factory/.env
```

### 4.3 Docker Compose Setup

```bash
cat > /opt/vineyard/factory/docker-compose.yml << 'EOF'
version: '3.8'

services:
  factory:
    build: .
    container_name: vineyard-factory
    restart: unless-stopped
    ports:
      - "127.0.0.1:8000:8000"
    env_file:
      - .env
    volumes:
      - factory-data:/app/data
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s

volumes:
  factory-data:
EOF
```

### 4.4 Build and Start

```bash
cd /opt/vineyard/factory

# Build image
docker compose build

# Start in background
docker compose up -d

# Check logs
docker compose logs -f
```

### 4.5 Create Systemd Service (Alternative to Docker Compose)

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
WorkingDirectory=/opt/vineyard/factory
ExecStart=/usr/bin/docker compose up
ExecStop=/usr/bin/docker compose down
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable vineyard-factory
systemctl start vineyard-factory
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
# All logs
docker compose logs -f

# Filter by component
docker compose logs -f | grep -E "(webhook|Linear|retry)"
```

### 6.2 Health Check

```bash
# Local health check
curl http://localhost:8000/health

# External health check
curl https://factory.yourdomain.com/health
```

### 6.3 Update Deployment

```bash
cd /opt/vineyard/factory

# Pull latest code
git pull

# Rebuild and restart
docker compose build
docker compose up -d
```

### 6.4 Backup State

```bash
# Factory state is stored in the Docker volume
docker run --rm -v vineyard-factory_factory-data:/data -v $(pwd):/backup alpine tar czf /backup/factory-backup.tar.gz /data
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
   curl -I https://factory.yourdomain.com/health
   # Should show cf-ray header
   ```

2. Check Linear webhook status in Linear Settings → API → Webhooks
   - Look for delivery failures
   - Check the signing secret matches

3. Check Nginx logs:
   ```bash
   tail -f /var/log/nginx/error.log
   ```

### Factory not starting

1. Check Docker logs:
   ```bash
   docker compose logs factory
   ```

2. Verify environment variables:
   ```bash
   docker compose exec factory env | grep -E "(SLACK|LINEAR|API)"
   ```

### SSL/TLS errors

1. Verify Cloudflare SSL mode is "Full (strict)"
2. Check origin certificate hasn't expired
3. Ensure certificate hostnames match

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
