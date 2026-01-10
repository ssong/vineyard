# Vineyard Research Agent

Autonomous micro-SaaS research agent that discovers, validates, and scores opportunities.

## Quick Start (Local)

```bash
cp .env.example .env
# Add your API keys
pip install -e .
python -m src.main
```

## Docker Deployment (Hetzner)

### Prerequisites

On your Hetzner server:
```bash
# Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# Log out and back in
```

### Build & Run

```bash
# Clone repo to server
git clone <your-repo> && cd vineyard/research-agent

# Create .env with your API keys
cp .env.example .env
nano .env

# Build the image
docker build -t vineyard-research-agent .

# Create outputs directory with correct permissions
mkdir -p outputs
chmod 755 outputs

# Run the container
docker run -d \
  --name vineyard-research-agent \
  --restart unless-stopped \
  --env-file .env \
  -v $(pwd)/outputs:/app/outputs \
  vineyard-research-agent
```

### Volume Mounts

| Host Path | Container Path | Purpose |
|-----------|----------------|---------|
| `./outputs` | `/app/outputs` | Persist generated PDF reports |

### Permission Setup

```bash
# The container runs as UID 1000 (vineyard user)
# Ensure outputs directory is writable
sudo chown -R 1000:1000 outputs
chmod 755 outputs
```

### Management Commands

```bash
# View logs
docker logs -f vineyard-research-agent

# Stop
docker stop vineyard-research-agent

# Restart
docker restart vineyard-research-agent

# Remove and rebuild
docker rm -f vineyard-research-agent
docker build -t vineyard-research-agent .
docker run -d --name vineyard-research-agent --restart unless-stopped \
  --env-file .env -v $(pwd)/outputs:/app/outputs vineyard-research-agent
```

### With Docker Compose

```bash
# Start
docker compose up -d

# View logs
docker compose logs -f

# Rebuild and restart
docker compose up -d --build

# Stop
docker compose down
```

## Slack Commands

- `/vineyard new` - Start a new research cycle
- `/vineyard help` - Show help

## Architecture

```
src/
├── main.py           # Entry point
├── slack/            # Slack Bolt app (socket mode)
├── agents/           # Discovery, Validation, Scoring
├── tools/            # LLM and web search
├── reports/          # PDF generation
├── linear/           # Linear API
└── models/           # Data models
```

