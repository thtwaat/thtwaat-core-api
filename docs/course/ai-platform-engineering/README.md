# AI Platform Engineering & Distributed Systems

**Institution framing:** THTWAAT Academy (Chief Architect track)  
**Credential target:** AI Platform Architect (OpenAI / Anthropic / DeepMind / Microsoft / founder-ready)  
**Structure:** 10 semesters × 20 weeks × daily lessons  
**Capstone (Semester 10):** **THTWAAT Cloud** — agents, domains, billing, templates, usage, OpenAI-compatible APIs

## How this degree works

| Cadence | Deliverable |
|---------|-------------|
| Daily | Lesson + lab prompt (45–90 min) |
| Weekly | Production-style project + architecture diagram |
| Mid-semester | Design review (ADR + checklist) |
| End of semester | Production-ready project + code review gate |
| End of degree | THTWAAT Cloud launch + oral architecture defense |

**Teaching mode:** One semester at a time. Do not skip to later semesters until the semester project passes the code review checklist.

## Semester map

| Sem | Title | Core stack / themes | Semester project |
|-----|-------|---------------------|------------------|
| 01 | Systems Foundations for Platform Engineers | Linux, networking, Python, Git, Docker, CI basics | `thtwaat-lab-api` Hello Platform (Dockerized FastAPI + health + CI) |
| 02 | API Design & Data Engineering for AI Platforms | FastAPI, Postgres, SQLAlchemy, Alembic, Redis, OpenAI-compatible gateway | **THTWAAT API Gateway** (4-week intensive) |
| 03 | Inference Engineering | GPU, Ollama, vLLM, streaming, batching | Local inference gateway (Ollama → OpenAI schema) |
| 04 | Distributed Systems & Messaging | CAP, Kafka, NATS, outbox, idempotency | Event-driven agent job worker |
| 05 | Cloud & Kubernetes | AWS/GCP/Azure, K8s, HPA, ingress | Multi-cloud deploy of inference API |
| 06 | Observability & SLOs | Prometheus, Grafana, OpenTelemetry | Full telemetry stack + burn-rate alerts |
| 07 | Security, Tenancy & Compliance | Secrets, isolation, abuse, audit | Hardened multi-tenant control plane |
| 08 | Product Platforms | Domains, billing, marketplace, usage meters | THTWAAT product modules (billing+templates+domains) |
| 09 | Reliability & Scale | DR, chaos, capacity, multi-region | DR runbook + failover drill |
| 10 | Capstone: THTWAAT Cloud | All of the above | Production THTWAAT Cloud + architecture defense |

## Cross-cutting pillars (every semester)

1. **Architecture diagrams** (C4 + sequence + deployment)
2. **Production checklists** (ship gate)
3. **Labs** (hands-on)
4. **Debugging exercises** (failure injection)
5. **Interview questions** (staff+/principal depth)
6. **Reading lists** (papers + books + RFCs)
7. **GitHub milestones** (issues → PRs → tags)
8. **CI/CD** (lint, test, scan, deploy)
9. **Security & DR** mindset

## Current position

**→ Semester 03 — Inference Engineering** (4-week intensive)  
**Current:** Week 1 Day 5 — Security + interview (prompt injection / model exfil)  

See: [`semester-03/week-01/day-05.md`](./semester-03/week-01/day-05.md)

Previous: [`semester-02/`](./semester-02/) API gateway (`sem02-v1.0.0`)

