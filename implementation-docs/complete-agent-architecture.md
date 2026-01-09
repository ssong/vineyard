# Complete Multi-Agent Micro-SaaS Factory Architecture

## Overview

A comprehensive multi-agent system that mirrors a complete product team: Research → Design → Build → Launch → Grow → Support. This architecture extends beyond engineering to include product discovery, design coordination, marketing automation, and growth operations.

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           FACTORY ORCHESTRATOR                                   │
│                              (LangGraph)                                         │
│  • Project lifecycle management    • Human approval gates                        │
│  • Cross-team coordination         • Slack reporting hub                         │
│  • Linear sync (single source)     • State checkpointing                         │
└─────────────────────────────────────────────────────────────────────────────────┘
                                       │
        ┌──────────────────────────────┼──────────────────────────────┐
        │                              │                              │
        ▼                              ▼                              ▼
┌───────────────────┐    ┌───────────────────┐    ┌───────────────────┐
│  PRODUCT DOMAIN   │    │ ENGINEERING DOMAIN│    │   GTM DOMAIN      │
│                   │    │                   │    │                   │
│ Research Agent    │    │ Code Agent        │    │ Marketing Agent   │
│ Design Agent      │    │ Test Agent        │    │ Launch Agent      │
│ Spec Agent        │    │ Security Agent    │    │ Growth Agent      │
│                   │    │ DevOps Agent      │    │ Support Agent     │
└───────────────────┘    └───────────────────┘    └───────────────────┘
        │                              │                              │
        ▼                              ▼                              ▼
┌───────────────────┐    ┌───────────────────┐    ┌───────────────────┐
│ TOOLS             │    │ TOOLS             │    │ TOOLS             │
│ • Miro API        │    │ • GitHub API      │    │ • Resend API      │
│ • Figma API       │    │ • Vercel/Fly.io   │    │ • Typefully API   │
│ • Linear API      │    │ • Neon API        │    │ • Product Hunt    │
│ • Web Search      │    │ • Stripe API      │    │ • Intercom API    │
│ • Competitor DBs  │    │ • Semgrep/Trivy   │    │ • Analytics APIs  │
└───────────────────┘    └───────────────────┘    └───────────────────┘
```

---

## 1. Product Domain

### 1.1 Research Agent

**Purpose**: Validate ideas, analyze markets, identify opportunities

**Capabilities**:
- Market size estimation via web search + data aggregation
- Competitor analysis (features, pricing, reviews, traffic)
- Problem validation through Reddit/Twitter/forum mining
- Keyword and SEO opportunity analysis
- User persona synthesis

**Tools**:
```python
RESEARCH_TOOLS = {
    "web_search": "Tavily/Serper API for real-time search",
    "similarweb": "Traffic and competitor intelligence",
    "g2_scraper": "B2B software reviews and comparisons",
    "reddit_api": "Problem discovery in target communities",
    "twitter_api": "Sentiment and trend analysis",
    "semrush_api": "Keyword difficulty and search volume",
}
```

**Output → Linear**:
```graphql
mutation CreateResearchIssue {
  issueCreate(input: {
    teamId: "product-team-id"
    title: "Market Research: [Opportunity Name]"
    description: "## Summary\n[findings]\n## Competitors\n[table]\n## Recommendation\n[proceed/skip]"
    labelIds: ["research", "needs-review"]
    priority: 2
  }) {
    issue { id identifier url }
  }
}
```

**Output → Miro**:
```python
# Create competitive landscape board
miro.create_board(name=f"Competitive Analysis: {opportunity_name}")
miro.create_frame(title="Market Map")
for competitor in competitors:
    miro.create_shape(
        type="rectangle",
        content=competitor.name,
        x=competitor.price_position * 100,  # Price axis
        y=competitor.feature_score * 100,   # Feature axis
    )
    miro.create_connector(from_id=our_product_id, to_id=competitor.id)
```

---

### 1.2 Design Agent

**Purpose**: Create specifications, wireframes, and coordinate with Figma

**Capabilities**:
- Generate detailed PRDs from research
- Create text-based wireframes and user flows
- Produce Miro diagrams (architecture, flows, journey maps)
- Coordinate with Figma (read designs, generate specs)
- Write UI copy and microcopy

**Tools**:
```python
DESIGN_TOOLS = {
    "miro_api": {
        "create_board": "Initialize design workspace",
        "create_frame": "Organize by feature/flow",
        "create_shape": "Boxes, circles for wireframes",
        "create_sticky": "Requirements and notes",
        "create_connector": "Flow arrows",
        "create_text": "Labels and descriptions",
    },
    "figma_api": {
        "get_file": "Read existing designs",
        "get_components": "Extract design system",
        "get_images": "Export assets",
        "post_comment": "Leave feedback on designs",
    },
    "linear_api": "Create design tasks and specs",
}
```

**Miro User Flow Generation**:
```python
async def generate_user_flow(feature_spec: dict) -> str:
    """Generate interactive user flow in Miro"""
    board = await miro.create_board(
        name=f"User Flow: {feature_spec['name']}",
        description=feature_spec['description']
    )
    
    # Create swimlanes
    lanes = ["User Action", "Frontend", "Backend", "Database"]
    for i, lane in enumerate(lanes):
        await miro.create_shape(
            board_id=board.id,
            type="rectangle",
            content=lane,
            x=0, y=i * 200,
            width=1600, height=180,
            style={"fillColor": "#f5f5f5"}
        )
    
    # Add flow steps with connectors
    prev_step = None
    for step in feature_spec['flow_steps']:
        shape = await miro.create_shape(
            board_id=board.id,
            type="round_rectangle",
            content=step['description'],
            x=step['sequence'] * 250,
            y=lanes.index(step['lane']) * 200 + 50,
        )
        if prev_step:
            await miro.create_connector(
                board_id=board.id,
                start_item=prev_step.id,
                end_item=shape.id,
            )
        prev_step = shape
    
    return board.url
```

**Figma Integration Pattern**:
```python
async def sync_figma_to_spec(figma_file_key: str) -> dict:
    """Extract design specs from Figma file"""
    
    # Get file structure
    file_data = await figma.get_file(figma_file_key)
    
    # Extract components
    components = []
    for node in traverse_nodes(file_data['document']):
        if node['type'] == 'COMPONENT':
            components.append({
                'name': node['name'],
                'description': node.get('description', ''),
                'properties': extract_properties(node),
                'variants': extract_variants(node),
            })
    
    # Extract design tokens
    tokens = {
        'colors': extract_colors(file_data),
        'typography': extract_typography(file_data),
        'spacing': extract_spacing(file_data),
    }
    
    # Generate implementation spec
    return {
        'components': components,
        'tokens': tokens,
        'assets': await export_assets(figma_file_key),
    }
```

**Figma Limitation Note**: Figma doesn't support programmatic design creation via API. Options:
1. Generate detailed text specs → Human designer creates in Figma
2. Use Figma AI plugins (Magician, Uizard) via browser automation
3. Generate designs in code (React components) → Import to Figma via plugins
4. Use Miro for wireframes → Designer refines in Figma

---

### 1.3 Spec Agent

**Purpose**: Translate designs into engineering-ready specifications

**Capabilities**:
- Break features into implementable tasks
- Write technical specifications
- Define API contracts
- Create acceptance criteria
- Estimate complexity

**Output → Linear**:
```python
async def create_feature_breakdown(feature: dict) -> list[str]:
    """Create hierarchical Linear issues from feature spec"""
    
    # Create parent feature issue
    parent = await linear.issue_create({
        "team_id": ENGINEERING_TEAM_ID,
        "title": f"[Feature] {feature['name']}",
        "description": feature['prd'],
        "label_ids": ["feature", "ready-for-dev"],
        "priority": feature['priority'],
    })
    
    # Create sub-issues for each component
    issue_ids = [parent.id]
    for task in feature['tasks']:
        child = await linear.issue_create({
            "team_id": ENGINEERING_TEAM_ID,
            "title": task['title'],
            "description": f"""
## Acceptance Criteria
{task['acceptance_criteria']}

## Technical Notes
{task['technical_notes']}

## Estimates
- Complexity: {task['complexity']}
- Points: {task['story_points']}
            """,
            "parent_id": parent.id,
            "label_ids": task['labels'],
        })
        issue_ids.append(child.id)
    
    return issue_ids
```

---

## 2. Engineering Domain

### 2.1 Code Agent

**Purpose**: Generate production-quality code from specifications

**Tools**:
- Direct LLM code generation (Claude API)
- GitHub API for repository management
- File system operations

### 2.2 Test Agent

**Purpose**: Automated testing and quality assurance

**Tools**:
```python
TEST_TOOLS = {
    "playwright": "E2E browser testing",
    "qodo": "AI-generated unit tests",
    "percy": "Visual regression testing",
    "mabl": "Self-healing test generation",
}
```

### 2.3 Security Agent

**Purpose**: Automated security scanning and compliance

**Tools**:
```python
SECURITY_TOOLS = {
    "semgrep": "Static analysis with SARIF output",
    "trivy": "Dependency and container scanning",
    "checkov": "Infrastructure-as-code security",
    "zap": "Dynamic application security testing",
}
```

### 2.4 DevOps Agent

**Purpose**: Infrastructure provisioning and deployment

**Tools**:
```python
DEVOPS_TOOLS = {
    "vercel_sdk": "Frontend deployment",
    "fly_io": "Container deployment",
    "neon": "Database provisioning with instant branching",
    "pulumi": "Infrastructure-as-code automation",
    "github_actions": "CI/CD pipeline management",
}
```

### Linear Integration for Engineering
```python
async def sync_build_progress(project_id: str, build_result: dict):
    """Update Linear issues based on build agent output"""
    
    for file_created in build_result['files_created']:
        # Find related issue by component name
        component_name = extract_component_name(file_created)
        issues = await linear.issues(
            filter={"title": {"contains": component_name}}
        )
        
        if issues:
            await linear.issue_update(
                id=issues[0].id,
                state_id=IN_REVIEW_STATE_ID,
                description_append=f"\n\n---\n✅ Implemented in `{file_created}`"
            )
    
    # Update parent feature progress
    await update_feature_progress(project_id)
```

---

## 3. Go-To-Market Domain

### 3.1 Marketing Agent

**Purpose**: Generate and schedule marketing content

**Capabilities**:
- Write landing page copy
- Generate social media content
- Create email sequences
- Produce blog posts and documentation
- A/B test variations

**Tools**:
```python
MARKETING_TOOLS = {
    "resend": {
        "send_email": "Transactional emails",
        "create_broadcast": "Marketing campaigns",
        "manage_audience": "Contact list management",
        "get_analytics": "Open/click tracking",
    },
    "typefully": {
        "create_draft": "Schedule tweets/threads",
        "schedule_post": "Time-based publishing",
        "get_analytics": "Engagement metrics",
    },
    "buffer": {
        "create_post": "Multi-platform scheduling",
        "get_profiles": "Connected accounts",
    },
    "linear": "Track marketing tasks",
}
```

**Content Generation Pipeline**:
```python
async def generate_launch_content(product: dict) -> dict:
    """Generate full marketing content suite"""
    
    content = {}
    
    # Landing page copy
    content['landing_page'] = await llm.generate(
        prompt=LANDING_PAGE_PROMPT,
        context={
            "product": product,
            "competitors": product['competitor_analysis'],
            "target_audience": product['personas'],
        }
    )
    
    # Email sequence
    content['email_sequence'] = []
    for email_type in ['welcome', 'onboarding_1', 'onboarding_2', 'activation']:
        email = await llm.generate(
            prompt=EMAIL_TEMPLATES[email_type],
            context={"product": product}
        )
        content['email_sequence'].append(email)
    
    # Social content
    content['twitter_thread'] = await llm.generate(
        prompt=TWITTER_LAUNCH_THREAD_PROMPT,
        context={"product": product}
    )
    
    content['linkedin_post'] = await llm.generate(
        prompt=LINKEDIN_ANNOUNCEMENT_PROMPT,
        context={"product": product}
    )
    
    return content
```

**Resend Integration**:
```python
from resend import Resend

resend = Resend(api_key=RESEND_API_KEY)

async def setup_email_infrastructure(product: dict):
    """Configure email sending for new product"""
    
    # Create audience for this product
    audience = resend.audiences.create(name=f"{product['name']} Users")
    
    # Set up transactional email templates
    templates = {
        'welcome': product['email_content']['welcome'],
        'password_reset': STANDARD_PASSWORD_RESET,
        'invoice': product['email_content']['invoice'],
    }
    
    return {
        'audience_id': audience.id,
        'templates': templates,
        'domain': product['domain'],
    }

async def send_broadcast(audience_id: str, content: dict):
    """Send marketing email to audience"""
    resend.broadcasts.create(
        audience_id=audience_id,
        from_email=f"updates@{DOMAIN}",
        subject=content['subject'],
        html=content['html'],
        scheduled_at=content.get('scheduled_at'),  # Optional scheduling
    )
```

---

### 3.2 Launch Agent

**Purpose**: Coordinate product launches across channels

**Capabilities**:
- Prepare Product Hunt listing (content, assets, timing)
- Coordinate social media blitz
- Schedule email announcements
- Monitor launch metrics
- Respond to early feedback

**Launch Checklist Automation**:
```python
async def prepare_launch(product: dict, launch_date: datetime) -> dict:
    """Generate launch preparation checklist in Linear"""
    
    launch_project = await linear.project_create({
        "name": f"Launch: {product['name']}",
        "target_date": launch_date.isoformat(),
        "team_ids": [MARKETING_TEAM_ID, ENGINEERING_TEAM_ID],
    })
    
    # Pre-launch tasks (T-7 to T-1 days)
    pre_launch_tasks = [
        {"title": "Finalize landing page copy", "due": -7},
        {"title": "Create Product Hunt listing draft", "due": -5},
        {"title": "Prepare launch tweet thread", "due": -3},
        {"title": "Set up analytics tracking", "due": -3},
        {"title": "Configure email welcome sequence", "due": -2},
        {"title": "Final QA pass", "due": -1},
        {"title": "Prepare support documentation", "due": -1},
    ]
    
    for task in pre_launch_tasks:
        due_date = launch_date + timedelta(days=task['due'])
        await linear.issue_create({
            "project_id": launch_project.id,
            "title": task['title'],
            "due_date": due_date.isoformat(),
            "label_ids": ["launch", "marketing"],
        })
    
    # Launch day tasks
    launch_day_tasks = [
        {"title": "Publish Product Hunt listing", "time": "00:01 PST"},
        {"title": "Send launch tweet thread", "time": "00:05 PST"},
        {"title": "Post LinkedIn announcement", "time": "09:00 local"},
        {"title": "Send email to waitlist", "time": "09:00 EST"},
        {"title": "Monitor and respond to PH comments", "time": "all day"},
    ]
    
    return {
        "project_id": launch_project.id,
        "checklist_url": launch_project.url,
    }
```

**Product Hunt Prep** (API is read-only, but prep is automatable):
```python
async def prepare_product_hunt_listing(product: dict) -> dict:
    """Generate all PH listing content for manual submission"""
    
    listing = {
        "name": product['name'],
        "tagline": await llm.generate(
            prompt="Write a compelling 60-char tagline",
            context=product
        ),
        "description": await llm.generate(
            prompt=PRODUCT_HUNT_DESCRIPTION_PROMPT,
            context=product
        ),
        "first_comment": await llm.generate(
            prompt=MAKER_FIRST_COMMENT_PROMPT,
            context=product
        ),
        "topics": suggest_ph_topics(product),
        "images": {
            "thumbnail": product['assets']['logo'],
            "gallery": product['assets']['screenshots'],
        },
    }
    
    # Create Linear task for human to submit
    await linear.issue_create({
        "title": "Submit Product Hunt listing",
        "description": f"""
## Listing Content (copy-paste ready)

**Name**: {listing['name']}

**Tagline**: {listing['tagline']}

**Description**:
{listing['description']}

**First Comment**:
{listing['first_comment']}

**Topics**: {', '.join(listing['topics'])}

## Assets
- Thumbnail: {listing['images']['thumbnail']}
- Screenshots: {listing['images']['gallery']}

## Instructions
1. Go to producthunt.com/posts/new
2. Fill in the above content
3. Schedule for {launch_date} at 00:01 PST
4. Mark this task complete
        """,
        "label_ids": ["launch", "manual-required"],
        "assignee_id": FOUNDER_USER_ID,
    })
    
    return listing
```

---

### 3.3 Growth Agent

**Purpose**: Post-launch optimization and growth

**Capabilities**:
- Monitor acquisition metrics
- Analyze user behavior
- Optimize conversion funnels
- A/B test variations
- Generate growth experiments

**Tools**:
```python
GROWTH_TOOLS = {
    "posthog": {
        "get_insights": "Query analytics data",
        "create_experiment": "Set up A/B tests",
        "get_feature_flags": "Manage rollouts",
        "get_funnels": "Conversion analysis",
    },
    "stripe": {
        "get_revenue_metrics": "MRR, churn, LTV",
        "get_subscription_analytics": "Plan distribution",
    },
    "intercom": {
        "get_conversations": "Support volume and topics",
        "get_user_attributes": "Engagement data",
    },
}
```

---

### 3.4 Support Agent

**Purpose**: Customer support triage and response

**Capabilities**:
- Categorize incoming tickets
- Draft responses for common issues
- Escalate complex issues
- Update documentation based on patterns
- Correlate support issues with errors

**Tools**:
```python
SUPPORT_TOOLS = {
    "intercom": {
        "list_conversations": "Get support tickets",
        "reply_to_conversation": "Send responses",
        "tag_conversation": "Categorize issues",
        "assign_conversation": "Route to humans",
    },
    "sentry": {
        "get_issues": "Correlate with errors",
        "link_issue": "Connect ticket to bug",
    },
    "linear": {
        "create_issue": "Escalate bugs to engineering",
    },
}
```

---

## 4. Slack Reporting Hub

### Unified Reporting System
```python
class SlackReporter:
    """Centralized Slack reporting for all agents"""
    
    def __init__(self, webhook_url: str):
        self.webhook = webhook_url
        self.channels = {
            "product": "#product-updates",
            "engineering": "#engineering",
            "marketing": "#marketing",
            "alerts": "#alerts",
            "daily": "#daily-standup",
        }
    
    async def daily_standup(self):
        """Generate daily cross-team standup"""
        
        # Gather from all domains
        product_updates = await self.get_product_updates()
        eng_updates = await self.get_engineering_updates()
        marketing_updates = await self.get_marketing_updates()
        
        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"🌅 Daily Standup - {date.today()}"}
            },
            {"type": "divider"},
            
            # Product section
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "*📦 Product*"}
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": product_updates}
            },
            
            # Engineering section
            {
                "type": "section", 
                "text": {"type": "mrkdwn", "text": "*⚙️ Engineering*"}
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": eng_updates}
            },
            
            # Marketing section
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "*📣 Marketing*"}
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": marketing_updates}
            },
            
            # Blockers
            {"type": "divider"},
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": await self.get_blockers()}
            },
        ]
        
        await self.send(self.channels["daily"], blocks)
    
    async def get_product_updates(self) -> str:
        """Pull product updates from Linear"""
        issues = await linear.issues(
            filter={
                "team": {"key": {"eq": "PROD"}},
                "updatedAt": {"gte": yesterday()},
            }
        )
        
        completed = [i for i in issues if i.state.name == "Done"]
        in_progress = [i for i in issues if i.state.name == "In Progress"]
        
        return f"""
• ✅ Completed: {len(completed)} items
• 🔄 In Progress: {len(in_progress)} items
• Top item: {in_progress[0].title if in_progress else 'None'}
        """
    
    async def weekly_report(self):
        """Comprehensive weekly business report"""
        
        # Revenue metrics
        stripe_data = await stripe.get_balance_transactions(
            created={"gte": week_ago()}
        )
        revenue = sum(t.amount for t in stripe_data) / 100
        
        # Product metrics
        posthog_data = await posthog.query({
            "events": [{"id": "user_signed_up"}, {"id": "subscription_created"}],
            "date_from": "-7d"
        })
        
        # Support metrics
        intercom_data = await intercom.conversations.list(
            created_at={"gte": week_ago()}
        )
        
        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "📊 Weekly Business Report"}
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*💰 Revenue*\n${revenue:,.2f}"},
                    {"type": "mrkdwn", "text": f"*📈 New Users*\n{posthog_data['user_signed_up']}"},
                    {"type": "mrkdwn", "text": f"*💳 New Subs*\n{posthog_data['subscription_created']}"},
                    {"type": "mrkdwn", "text": f"*🎫 Support Tickets*\n{len(intercom_data)}"},
                ]
            },
        ]
        
        await self.send(self.channels["daily"], blocks)
```

### Report Types by Domain

| Report | Frequency | Channel | Content |
|--------|-----------|---------|---------|
| Daily Standup | Daily 9am | #daily-standup | Cross-team progress, blockers |
| Sprint Progress | Daily | #engineering | Velocity, burndown, PRs |
| Marketing Metrics | Daily | #marketing | Traffic, signups, email stats |
| Weekly Business | Weekly Mon | #leadership | Revenue, growth, churn |
| Launch Report | On launch | #all-hands | Launch metrics, feedback |
| Incident Alert | Real-time | #alerts | Errors, downtime, security |
| Customer Feedback | Weekly | #product | NPS, feature requests, churn reasons |

---

## 5. Linear as Central Nervous System

### Project Structure
```
Workspace: [Company Name]
├── Team: Product
│   ├── Cycle: Research Sprint
│   │   ├── Issue: Market Research - [Opportunity]
│   │   └── Issue: Competitor Analysis - [Competitor]
│   └── Cycle: Design Sprint  
│       ├── Issue: PRD - [Feature]
│       └── Issue: User Flow - [Feature]
│
├── Team: Engineering
│   ├── Cycle: Sprint 1
│   │   ├── Issue: [Feature] Parent
│   │   │   ├── Sub-issue: Component A
│   │   │   └── Sub-issue: API Endpoint
│   │   └── Issue: Bug fixes
│   └── Project: Infrastructure
│       └── Issue: CI/CD Setup
│
├── Team: Marketing
│   ├── Project: Launch - [Product]
│   │   ├── Issue: Landing page copy
│   │   ├── Issue: Email sequences
│   │   └── Issue: Social content
│   └── Cycle: Content Calendar
│       └── Issue: Blog post - [Topic]
│
└── Team: Operations
    ├── Issue: Support ticket triage
    └── Issue: Documentation updates
```

### Automation Rules
```python
LINEAR_AUTOMATIONS = {
    # When research completes, create design tasks
    "research_to_design": {
        "trigger": {"state": "Done", "label": "research"},
        "action": "create_linked_issue",
        "params": {
            "team": "Product",
            "title_prefix": "[Design] ",
            "label": "design",
        }
    },
    
    # When design completes, create engineering tasks
    "design_to_engineering": {
        "trigger": {"state": "Done", "label": "design"},
        "action": "create_sub_issues_from_spec",
    },
    
    # When all sub-issues done, mark parent done
    "auto_complete_parent": {
        "trigger": {"all_children": "Done"},
        "action": "update_parent_state",
        "params": {"state": "Done"}
    },
    
    # When bug reported, create issue and assign
    "bug_from_sentry": {
        "trigger": "sentry_webhook",
        "action": "create_issue",
        "params": {
            "team": "Engineering",
            "label": "bug",
            "priority": "from_sentry_level",
        }
    },
}
```

---

## 6. Miro as Visual Workspace

### Board Templates
```python
MIRO_TEMPLATES = {
    "competitive_analysis": {
        "frames": ["Market Map", "Feature Comparison", "Pricing Matrix", "SWOT"],
        "auto_populate": True,
    },
    "user_journey": {
        "frames": ["Awareness", "Consideration", "Decision", "Onboarding", "Retention"],
        "swimlanes": ["User", "Touchpoints", "Emotions", "Opportunities"],
    },
    "architecture_diagram": {
        "frames": ["Frontend", "Backend", "Database", "External Services"],
        "connector_style": "curved",
    },
    "sprint_retro": {
        "frames": ["What went well", "What didn't", "Action items"],
        "sticky_colors": ["green", "red", "yellow"],
    },
}
```

### Auto-Generated Diagrams
```python
async def generate_architecture_diagram(codebase_analysis: dict) -> str:
    """Generate architecture diagram from code analysis"""
    
    board = await miro.create_board(
        name=f"Architecture: {codebase_analysis['project_name']}",
        from_template=MIRO_TEMPLATES["architecture_diagram"]
    )
    
    # Frontend layer
    frontend_frame = await miro.get_frame(board.id, "Frontend")
    for component in codebase_analysis['frontend_components']:
        await miro.create_shape(
            board_id=board.id,
            parent_id=frontend_frame.id,
            type="rectangle",
            content=component['name'],
            style={"fillColor": "#e3f2fd"}
        )
    
    # Backend layer
    backend_frame = await miro.get_frame(board.id, "Backend")
    for service in codebase_analysis['backend_services']:
        shape = await miro.create_shape(
            board_id=board.id,
            parent_id=backend_frame.id,
            type="rectangle", 
            content=f"{service['name']}\n{service['tech']}",
            style={"fillColor": "#fff3e0"}
        )
        
        # Connect to database if applicable
        if service.get('database'):
            await miro.create_connector(
                board_id=board.id,
                start_item=shape.id,
                end_item=await get_or_create_db_shape(service['database']),
            )
    
    return board.url
```

---

## 7. Complete Workflow Example

**User says**: "Build a waitlist landing page SaaS that lets people collect emails before launch"

### Phase 1: Research (Research Agent)
1. Search for existing waitlist tools (LaunchRock, Waitlist.me, Viral Loops)
2. Analyze pricing, features, reviews
3. Identify gap (most are expensive for simple use case)
4. Create Linear issue: "Market Research: Waitlist Tool"
5. Create Miro board: competitive landscape
6. **Slack report**: "Research complete. Found gap in simple, developer-friendly waitlist tools. Recommend proceeding."
7. **Human approval gate**

### Phase 2: Design (Design Agent)
1. Write PRD based on research
2. Create user flow in Miro
3. Generate wireframes (text-based or Miro shapes)
4. Define feature scope: landing builder, email capture, referral tracking, analytics
5. Create Linear issues for each feature
6. **Slack report**: "Design specs complete. 4 features, estimated 2-week build."
7. **Human approval gate** (or designer refines in Figma)

### Phase 3: Spec (Spec Agent)
1. Break features into engineering tasks
2. Define API contracts
3. Write acceptance criteria
4. Create Linear sub-issues with estimates
5. Generate database schema in Miro
6. **Slack report**: "Engineering breakdown complete. 12 tasks, 47 story points."

### Phase 4: Build (Code + Test + Security + DevOps Agents)
1. Generate code per spec
2. Run tests, security scans
3. Deploy to staging
4. Update Linear issues as completed
5. **Daily Slack updates**: "Build progress: 8/12 tasks complete"

### Phase 5: Launch Prep (Marketing + Launch Agents)
1. Generate landing page copy
2. Create email sequences in Resend
3. Write Twitter thread, LinkedIn post
4. Prepare Product Hunt listing content
5. Create launch Linear project with checklist
6. **Slack report**: "Launch prep 90% complete. PH listing needs manual submission."
7. **Human approval gate**

### Phase 6: Launch (Launch Agent)
1. Schedule social posts via Typefully/Buffer
2. Queue email broadcast in Resend
3. Alert human to submit PH listing
4. Monitor launch day metrics
5. **Real-time Slack updates**: "Launch update: 127 signups, #4 on PH, 2.3K page views"

### Phase 7: Growth (Growth + Support Agents)
1. Monitor conversion funnel
2. Triage support tickets
3. Analyze user feedback
4. Generate growth experiment hypotheses
5. **Weekly Slack report**: "Week 1: 847 signups, 12% conversion to paid, NPS 47"

---

## 8. Tool Integration Summary

| Tool | Primary Use | Agent(s) | API Capability |
|------|-------------|----------|----------------|
| **Linear** | Task management, sprint tracking | All | Full CRUD, webhooks, GraphQL |
| **Slack** | Reporting, approvals, alerts | Orchestrator | Messages, blocks, interactivity |
| **Miro** | Diagrams, flows, collaboration | Design, Spec | Shapes, connectors, boards |
| **Figma** | UI design (read), specs (read) | Design | Read files, export, comments |
| **Resend** | Email (transactional + marketing) | Marketing, Growth | Full API, broadcasts, audiences |
| **Typefully** | Twitter/LinkedIn scheduling | Marketing, Launch | Create, schedule, analytics |
| **PostHog** | Product analytics | Growth, Ops | Events, funnels, flags |
| **Stripe** | Billing, revenue metrics | Growth, Ops | Full API |
| **Intercom** | Support, user messaging | Support, Growth | Conversations, users |
| **GitHub** | Code repository | Code, DevOps | Full API |
| **Vercel** | Frontend deployment | DevOps | Full SDK |
| **Neon** | Database | DevOps | Branching, provisioning |
| **Semgrep** | Security scanning | Security | SARIF output |
| **Sentry** | Error tracking | Ops, Support | Issues, alerts |

---

## 9. API Capabilities Reference

### Linear GraphQL API
```graphql
# Full capabilities
- issues: CRUD, filtering, pagination
- projects: CRUD, milestones
- cycles: Sprint management
- teams: Organization structure
- labels: Categorization
- comments: Collaboration
- webhooks: Real-time events
- attachments: File linking
```

### Miro REST API v2
```
- boards: Create, read, update, delete
- shapes: Rectangle, circle, triangle, etc.
- sticky_notes: Collaborative notes
- connectors: Lines between items
- frames: Organizational containers
- text: Labels and annotations
- images: Upload and position
- documents: Rich text on canvas
```

### Figma REST API
```
- files: Read file structure
- images: Export rendered images
- components: Extract design system
- styles: Get design tokens
- comments: Post feedback
- versions: Access history
# Note: No write access to design content
```

### Resend API
```
- emails: Send transactional
- broadcasts: Marketing campaigns
- audiences: Contact management
- domains: DNS configuration
- api_keys: Access management
- webhooks: Delivery events
```

---

## 10. Implementation Priorities

### Phase 1: Foundation (Week 1-2)
1. Set up LangGraph orchestrator skeleton
2. Implement Linear integration (read/write)
3. Implement Slack reporting (messages + blocks)
4. Create basic human approval flow

### Phase 2: Product Domain (Week 3-4)
1. Research Agent with web search
2. Design Agent with Miro integration
3. Spec Agent with Linear issue creation

### Phase 3: Engineering Domain (Week 5-6)
1. Code Agent with file generation
2. Test Agent with Playwright
3. DevOps Agent with Vercel/Neon

### Phase 4: GTM Domain (Week 7-8)
1. Marketing Agent with Resend
2. Launch Agent with checklist automation
3. Growth Agent with PostHog

### Phase 5: Polish (Week 9-10)
1. End-to-end workflow testing
2. Error handling and recovery
3. Performance optimization
4. Documentation

---

## 11. Cost Estimates

### API Costs (Monthly)

| Service | Tier | Cost | Notes |
|---------|------|------|-------|
| Claude API | ~500K tokens/project | ~$15-25/project | Main LLM cost |
| Linear | Free tier | $0 | Up to 250 issues |
| Miro | Free tier | $0 | 3 boards |
| Figma | Free tier | $0 | Read-only sufficient |
| Resend | Free tier | $0 | 3K emails/month |
| Slack | Free tier | $0 | Webhooks work |
| PostHog | Free tier | $0 | 1M events/month |
| Vercel | Free tier | $0 | Hobby projects |
| Neon | Free tier | $0 | 10 branches |

**Total for MVP**: ~$25-50/month (primarily LLM costs)

### Scaling Costs
- Linear Team: $8/user/month
- Miro Team: $10/user/month
- Resend Pro: $20/month (50K emails)
- Vercel Pro: $20/month
- PostHog Paid: $0 until 1M events

---

## 12. Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Figma can't create designs | Use Miro for wireframes, human designer for polish |
| Product Hunt API read-only | Generate copy-paste ready content, human submits |
| LLM output quality varies | Human approval gates at each phase |
| API rate limits | Implement backoff, queue system |
| Cost overruns | Token budgets per project, monitoring |
| Tool API changes | Abstract behind interfaces, version pin |
