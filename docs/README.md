# TeamSync — Product & Engineering Documentation

**TeamSync** is an AI-powered project management platform for startups and small-to-mid-sized teams (≈5–200 people). It blends the speed and simplicity of Linear, the flexibility of Trello boards, and the structure of Jira — with an AI layer that automates triage, understands natural language, and turns activity into insight.

This folder contains the foundational planning documents. Read them in order:

| # | Document | Purpose |
|---|----------|---------|
| 1 | [Product Requirements Document](./01-PRD.md) | The "what" and "why" — vision, requirements, success metrics |
| 2 | [User Personas](./02-personas.md) | Who we build for and their jobs-to-be-done |
| 3 | [MVP Scope](./03-mvp-scope.md) | What ships first vs. what's deferred |
| 4 | [Feature Prioritization](./04-feature-prioritization.md) | RICE + MoSCoW scoring and sequencing |
| 5 | [Database Design](./05-database-design.md) | PostgreSQL schema, ER model, multi-tenancy |
| 6 | [Technical Architecture](./06-technical-architecture.md) | System design, AI layer, infra |
| 7 | [Development Roadmap](./07-roadmap.md) | Phased plan, milestones, risks |

## At a glance

| Dimension | Decision |
|-----------|----------|
| **Target market** | Startups & SMBs (5–200 people) |
| **Positioning** | Linear-speed + Trello-simplicity + AI-native |
| **Frontend** | Next.js (React, TypeScript) |
| **Backend** | FastAPI (Python 3.12+) |
| **Database** | PostgreSQL 16 |
| **Cache / queues** | Redis |
| **Async / AI jobs** | Celery workers |
| **Core AI** | Smart automation · Natural language · Summaries & insights |

> These are living documents. Terminology is kept consistent across all files:
> **Organization → Workspace → Project → Issue → Sub-issue**, with **Cycles** (sprints), **Views**, **Labels**, and **Comments**.
