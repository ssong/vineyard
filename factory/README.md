# Vineyard Factory

Multi-Agent SaaS Factory for end-to-end product development.

## Quick Start

```bash
cp .env.example .env
# Add your API keys
pip install -e .
python -m src.main
```

## Slack Commands

- `/vineyard build [project-id]` - Start factory for a project
- `/vineyard help` - Show help

## Architecture

```
factory/
├── src/
│   ├── agents/
│   │   ├── product/       # Research, Design, Spec
│   │   ├── engineering/   # Code, Test, Security, DevOps
│   │   └── gtm/           # Marketing, Launch, Growth, Support
│   ├── orchestrator/      # Phase execution
│   ├── slack/             # Command handlers
│   ├── tools/             # LLM, Miro, GitHub, Linear
│   └── models/            # State and outputs
└── Dockerfile
```

## Phase Flow

1. **Research Enrichment** - Personas, SEO, competitor matrix
2. **Design** (checkpoint) - PRD, user flows
3. **Spec** - Tasks, API contracts
4. **Build** (checkpoint) - Code generation
5. **Launch Prep** - Marketing assets
6. **Launch** (checkpoint) - PH listing
7. **Growth** - Analytics, experiments

## Docker Deployment

```bash
docker build -t vineyard-factory .
docker run -d --name vineyard-factory --restart unless-stopped \
  --env-file .env vineyard-factory
```
