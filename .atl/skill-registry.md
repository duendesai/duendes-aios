# Skill Registry

**Duendes AIOS — Skill Registry**
Project: duendes-aios
Last Updated: 2026-04-03

---

## Project Structure

| Location | Type | Count |
|----------|------|-------|
| User skills | `~/.claude/skills/` | 20+ available |
| Project skills | `.claude/skills/` | 0 (none defined yet) |
| Convention files | Project root | CLAUDE.md |
| Department Agents | `modulos/` | 6 agents + orchestrator |

---

## Available User Skills

### SDD Workflow Skills
- **sdd-init** — Initialize Spec-Driven Development context (stack detection, testing capabilities, persistence bootstrap)
- **sdd-explore** — Investigate a feature area or change topic
- **sdd-propose** — Create change proposals with architectural decisions
- **sdd-spec** — Write formal specifications for changes
- **sdd-design** — Design implementation approach
- **sdd-tasks** — Break design into executable tasks
- **sdd-apply** — Implement tasks in batches
- **sdd-verify** — Validate implementation against specs
- **sdd-archive** — Close changes and persist final state

### Infrastructure & Automation
- **supabase-automation** — Supabase project and database operations
- **langfuse** — LLM observability and tracing
- **azure-monitor-opentelemetry-ts** — OpenTelemetry monitoring for Azure
- **mailchimp-automation** — Email marketing automation

### Development Standards
- **cc-skill-coding-standards** — Code quality and style enforcement
- **ask-questions-if-underspecified** — Requirement clarification workflow

### Specialized Agents
- **steve-jobs** — Strategic visioning and positioning
- **dwarf-expert** — Domain expertise focus
- **bug-hunter** — Defect analysis and prevention
- **kaizen** — Continuous improvement methodology
- **saas-mvp-launcher** — SaaS rapid launch patterns

### Frontend & Design
- **javascript-typescript-typescript-scaffold** — TypeScript project scaffolding
- **mobile-design** — Mobile UI/UX patterns
- **azure-storage-blob-ts** — TypeScript Azure Storage integration

### Additional Tools
- **cal-com-automation** — Calendar automation
- **metasploit-framework** — Security testing (authorized use only)
- **customer-support** — Support workflow patterns
- **expo-dev-client** — React Native/Expo development
- **task-intelligence** — Smart task management

---

## Convention Files

### Project-Level CLAUDE.md
- **Location**: `/CLAUDE.md`
- **Scope**: Duendes AIOS 3-level agent system specification
- **Contains**:
  - Business context (3-level hierarchy, Department Agents routing table)
  - Engram mandatory usage rules
  - Language and tone guidelines (Spanish/Rioplatense)
  - Department Agent activation protocol

### Department Agent CLAUDE.md Files
Located in `modulos/{agent}/CLAUDE.md`:
- `modulos/cmo/CLAUDE.md` — Chief Marketing Officer instructions
- `modulos/sdr/CLAUDE.md` — Sales Development Rep instructions
- `modulos/ae/CLAUDE.md` — Account Executive instructions
- `modulos/coo/CLAUDE.md` — Chief Operating Officer instructions
- `modulos/cfo/CLAUDE.md` — Chief Financial Officer instructions
- `modulos/cs/CLAUDE.md` — Customer Success instructions
- `modulos/orchestrator/CLAUDE.md` — Orchestrator instructions

---

## Project Context Files

Located in `context/`:
- `negocio.md` — Business model and strategy
- `clientes-ideales.md` — Target customer profiles
- `competencia.md` — Competitive landscape
- `estrategia.md` — Go-to-market strategy
- `ofertas.md` — Product offerings and pricing
- `voz-tono.md` — Brand voice and messaging

---

## Tech Stack & Scripts

**Language**: Python (scripts/)
**Key Dependencies**:
- python-telegram-bot >= 20.7 (Telegram bot integration)
- anthropic >= 0.34.0 (Claude API)
- openai >= 1.40.0 (OpenAI integrations)
- python-dotenv >= 1.0.0 (Environment config)
- httpx >= 0.27.0 (Async HTTP client)

**Scripts**:
- `bot.py` — Telegram bot (long-polling, Oscar-only whitelist)
- `aios_monitor.py` — System monitoring
- `cmo_content.py` / `cmo_content_writer.py` — CMO content automation
- `cfo_invoices.py` — CFO invoice management
- `cs_clients.py` — CS client management
- `ae_deals.py` / `ae_proposal_writer.py` — AE deal and proposal handling
- `coo_tasks.py` — COO task management
- `airtable_client.py` / `airtable_sync.py` — Airtable integration
- `instantly_client.py` — Instantly.ai (email automation) integration

---

## Notes

- **No traditional test runner detected** (pytest, jest, vitest, cargo test, etc.)
- **Strict TDD Mode**: NOT AVAILABLE (no test infrastructure)
- **Primary artifact type**: Agent instructions (CLAUDE.md files)
- **Secondary artifact type**: Python automation scripts
- **Persistence backend**: Engram (MANDATORY per project guidelines)

---

## How to Use This Registry

1. **When delegating to sub-agents**: Inject relevant skill compact rules from this registry based on task context
2. **When looking up a skill**: Find the skill name in this registry and locate its full SKILL.md in `~/.claude/skills/{skill-name}/SKILL.md`
3. **When adding new project-level skills**: Create `.claude/skills/{skill-name}/SKILL.md` and add an entry to "Project Skills"
4. **When updating conventions**: Modify the relevant CLAUDE.md file and note the update date

---

**Registry generation**: SDD Initialization (sdd-init skill)
