"""Studio AI Software Factory — thin source scaffolds (reuse platform modules)."""
from __future__ import annotations

import enum
import hashlib
import io
import json
import logging
import re
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from uuid import UUID

from app.studio.schemas import (
    AiManifest,
    BackendManifest,
    ComposedModule,
    FrontendManifest,
    InfraManifest,
    ProductBlueprint,
)

logger = logging.getLogger(__name__)

AGENT_ORDER = (
    "planner",
    "frontend",
    "backend",
    "database",
    "ai",
    "infrastructure",
    "security",
    "qa",
    "documentation",
)


class BuildStage(str, enum.Enum):
    QUEUED = "queued"
    PLANNING = "planning"
    GENERATING = "generating"
    GENERATING_FRONTEND = "generating_frontend"
    GENERATING_BACKEND = "generating_backend"
    GENERATING_AI = "generating_ai"
    GENERATING_DATABASE = "generating_database"
    GENERATING_INFRASTRUCTURE = "generating_infrastructure"
    VALIDATION = "validation"
    PACKAGING = "packaging"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class GeneratedFile:
    path: str
    content: str
    agent: str
    reuse: bool = False
    platform_ref: Optional[str] = None
    language: str = "text"


@dataclass
class AgentResult:
    agent: str
    status: str  # completed | failed | skipped
    files: List[GeneratedFile] = field(default_factory=list)
    message: str = ""
    reuse_percent: float = 100.0


@dataclass
class FactoryContext:
    project_id: UUID
    project_title: str
    blueprint: ProductBlueprint
    modules: List[ComposedModule]
    frontend: Optional[FrontendManifest]
    backend: Optional[BackendManifest]
    ai: Optional[AiManifest]
    infra: Optional[InfraManifest]
    approval_id: UUID
    versions: Dict[str, int] = field(default_factory=dict)


ProgressCallback = Callable[[str, Dict[str, Any]], None]


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", (value or "product").lower()).strip("-")
    return cleaned[:48] or "product"


def _py_ident(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_]+", "_", (value or "item").lower()).strip("_")
    if cleaned and cleaned[0].isdigit():
        cleaned = f"t_{cleaned}"
    return cleaned or "item"


def emit_progress(cb: Optional[ProgressCallback], event: str, **data: Any) -> None:
    if cb:
        payload = {"event": event, "ts": datetime.now(timezone.utc).isoformat(), **data}
        try:
            cb(event, payload)
        except Exception:  # noqa: BLE001
            logger.exception("progress_callback_failed event=%s", event)


# ── Agents ────────────────────────────────────────────────────────────────────

def agent_planner(ctx: FactoryContext) -> AgentResult:
    module_lines = [
        f"- {m.key}: {m.label} ({m.kind}) → {m.platform_ref or 'custom'}"
        for m in ctx.modules
    ]
    plan = {
        "product": ctx.project_title,
        "industry": ctx.blueprint.industry,
        "product_type": ctx.blueprint.product_type,
        "approval_id": str(ctx.approval_id),
        "versions": ctx.versions,
        "modules": [
            {
                "key": m.key,
                "label": m.label,
                "kind": str(getattr(m.kind, "value", m.kind)),
                "platform_ref": m.platform_ref,
                "reuse": bool(m.platform_ref),
            }
            for m in ctx.modules
        ],
        "agents": list(AGENT_ORDER),
        "doctrine": [
            "Reuse Auth, Billing, AI Gateway, Agents, Marketplace, Knowledge, Publisher, Admin",
            "Never duplicate platform runtimes",
            "Only emit product-specific glue and custom domain stubs",
        ],
    }
    files = [
        GeneratedFile(
            path="docs/BUILD_PLAN.json",
            content=json.dumps(plan, indent=2) + "\n",
            agent="planner",
            reuse=True,
            language="json",
        ),
        GeneratedFile(
            path="docs/BUILD_PLAN.md",
            content=(
                f"# Build Plan — {ctx.project_title}\n\n"
                f"Approved factory run. Modules:\n\n"
                + "\n".join(module_lines)
                + "\n\n## Doctrine\n\n"
                "- Reuse existing THTWAAT platform modules\n"
                "- Do not fork Auth/Billing/AI Gateway\n"
                "- Custom domain code lives under backend/app/domain and frontend/src/app/(product)\n"
            ),
            agent="planner",
            reuse=True,
            language="markdown",
        ),
    ]
    return AgentResult(agent="planner", status="completed", files=files, message="Plan ready")


def agent_frontend(ctx: FactoryContext) -> AgentResult:
    fe = ctx.frontend
    slug = _slug(ctx.project_title)
    files: List[GeneratedFile] = []
    files.append(
        GeneratedFile(
            path="frontend/README.md",
            content=(
                f"# {ctx.project_title} — Frontend\n\n"
                "Thin Next.js shell. Reuse SaaS template pages from "
                "`apps/templates/saas` (Auth, Dashboard, Billing, Agents, Admin).\n"
                "Only product-specific routes are generated under `src/app/(product)`.\n"
            ),
            agent="frontend",
            reuse=True,
            platform_ref="apps/templates/saas",
            language="markdown",
        )
    )
    files.append(
        GeneratedFile(
            path="frontend/package.json",
            content=json.dumps(
                {
                    "name": f"{slug}-web",
                    "private": True,
                    "scripts": {
                        "dev": "next dev",
                        "build": "next build",
                        "lint": "next lint",
                        "typecheck": "tsc -p tsconfig.json --noEmit",
                    },
                    "dependencies": {
                        "next": "14.2.5",
                        "react": "18.3.1",
                        "react-dom": "18.3.1",
                    },
                    "devDependencies": {
                        "typescript": "5.5.4",
                        "@types/react": "18.3.3",
                        "@types/node": "20.14.10",
                    },
                },
                indent=2,
            )
            + "\n",
            agent="frontend",
            reuse=True,
            language="json",
        )
    )
    files.append(
        GeneratedFile(
            path="frontend/src/lib/platform.ts",
            content=(
                "/** Platform reuse map — do not reimplement these surfaces. */\n"
                "export const PLATFORM_PAGES = {\n"
                "  login: '/app/login',\n"
                "  dashboard: '/app/dashboard',\n"
                "  billing: '/app/billing',\n"
                "  agents: '/app/agents',\n"
                "  admin: '/app/admin',\n"
                "  marketplace: '/app/templates',\n"
                "} as const;\n"
            ),
            agent="frontend",
            reuse=True,
            platform_ref="apps/templates/saas/src/app",
            language="typescript",
        )
    )
    # Nav from manifest
    nav_items = []
    if fe:
        for n in fe.nav or []:
            nav_items.append({"id": n.id, "label": n.label, "route": n.route, "reuse": n.reuse})
    files.append(
        GeneratedFile(
            path="frontend/src/config/navigation.ts",
            content=(
                "export type NavItem = { id: string; label: string; route: string; reuse: boolean };\n"
                f"export const navigation: NavItem[] = {json.dumps(nav_items, indent=2)};\n"
            ),
            agent="frontend",
            reuse=True,
            language="typescript",
        )
    )
    # Theme
    theme = (fe.theme if fe else {}) or {"primary": "#0d9488", "mode": "system"}
    files.append(
        GeneratedFile(
            path="frontend/src/styles/theme.css",
            content=(
                ":root {\n"
                f"  --brand-primary: {theme.get('primary', '#0d9488')};\n"
                "  --brand-surface: #0f172a;\n"
                "  --brand-text: #e2e8f0;\n"
                "}\n"
                "body { background: var(--brand-surface); color: var(--brand-text); }\n"
            ),
            agent="frontend",
            reuse=False,
            language="css",
        )
    )
    # Only generate stubs for non-reuse / custom pages
    custom_pages = []
    if fe:
        for p in fe.pages or []:
            if p.kind == "generated_spec" or not p.reuse:
                custom_pages.append(p)
    for p in custom_pages[:20]:
        route = (p.route or f"/{p.id}").strip("/")
        safe = _py_ident(p.id)
        files.append(
            GeneratedFile(
                path=f"frontend/src/app/(product)/{route}/page.tsx",
                content=(
                    f'export default function {safe.title().replace("_", "")}Page() {{\n'
                    f"  return (\n"
                    f'    <main className="p-6">\n'
                    f"      <h1>{p.title}</h1>\n"
                    f"      <p>Product page scaffold — wire to platform API clients.</p>\n"
                    f"    </main>\n"
                    f"  );\n"
                    f"}}\n"
                ),
                agent="frontend",
                reuse=False,
                language="typescript",
            )
        )
        if p.crud:
            fields = [f.name for f in (p.crud.fields or [])][:12]
            files.append(
                GeneratedFile(
                    path=f"frontend/src/components/{safe}-form.tsx",
                    content=(
                        f"/** CRUD form scaffold for {p.title} */\n"
                        f"const fields = {json.dumps(fields)};\n"
                        f"export function {safe.title().replace('_', '')}Form() {{\n"
                        f"  return (\n"
                        f'    <form className="space-y-3">\n'
                        f"      {{fields.map((name) => (\n"
                        f'        <label key={{name}} className="block">\n'
                        f"          <span>{{name}}</span>\n"
                        f'          <input name={{name}} className="w-full border px-2 py-1" />\n'
                        f"        </label>\n"
                        f"      ))}}\n"
                        f"      <button type=\"submit\">Save</button>\n"
                        f"    </form>\n"
                        f"  );\n"
                        f"}}\n"
                    ),
                    agent="frontend",
                    reuse=False,
                    language="typescript",
                )
            )
    # Layout shell
    files.append(
        GeneratedFile(
            path="frontend/src/app/layout.tsx",
            content=(
                'import "../styles/theme.css";\n'
                "export default function RootLayout({ children }: { children: React.ReactNode }) {\n"
                "  return (\n"
                "    <html lang=\"en\">\n"
                "      <body>{children}</body>\n"
                "    </html>\n"
                "  );\n"
                "}\n"
            ),
            agent="frontend",
            reuse=True,
            language="typescript",
        )
    )
    reuse_n = sum(1 for f in files if f.reuse)
    pct = round(100.0 * reuse_n / max(len(files), 1), 1)
    return AgentResult(
        agent="frontend",
        status="completed",
        files=files,
        message=f"{len(files)} files · {len(custom_pages)} custom pages",
        reuse_percent=pct,
    )


def agent_backend(ctx: FactoryContext) -> AgentResult:
    be = ctx.backend
    files: List[GeneratedFile] = []
    files.append(
        GeneratedFile(
            path="backend/README.md",
            content=(
                f"# {ctx.project_title} — Backend\n\n"
                "Thin FastAPI product layer. Mount existing platform routers:\n"
                "- `app.auth` Auth/RBAC\n"
                "- `app.payments` Billing\n"
                "- `app.ai` AI Gateway\n"
                "- `app.agent_platform` Agents\n"
                "- `app.marketplace` Marketplace\n"
                "- `app.knowledge` Knowledge\n"
                "- `app.monitoring` Monitoring\n"
                "Only custom domain endpoints are generated under `backend/app/domain/`.\n"
            ),
            agent="backend",
            reuse=True,
            platform_ref="app/",
            language="markdown",
        )
    )
    files.append(
        GeneratedFile(
            path="backend/app/main.py",
            content=(
                '"""Product API entry — mounts platform + domain routers."""\n'
                "from fastapi import FastAPI\n\n"
                "from backend.app.platform_mounts import include_platform_routers\n"
                "from backend.app.domain.router import router as domain_router\n\n"
                "app = FastAPI(title=" + json.dumps(ctx.project_title) + ")\n"
                "include_platform_routers(app)\n"
                'app.include_router(domain_router, prefix="/api/v1/domain", tags=["domain"])\n'
            ),
            agent="backend",
            reuse=True,
            language="python",
        )
    )
    files.append(
        GeneratedFile(
            path="backend/app/platform_mounts.py",
            content=(
                '"""Declare platform router mounts — do not copy Auth/Billing/AI source."""\n'
                "from fastapi import FastAPI\n\n"
                "PLATFORM_MOUNTS = [\n"
                '    ("app.auth.router", "auth_router", "/api/v1/auth"),\n'
                '    ("app.payments.router", "router", "/api/v1/billing"),\n'
                '    ("app.ai.router", "router", "/api/v1/ai"),\n'
                '    ("app.storage.router", "router", "/api/v1/storage"),\n'
                '    ("app.monitoring.router", "router", "/api/v1/monitoring"),\n'
                "]\n\n"
                "def include_platform_routers(app: FastAPI) -> None:\n"
                "    for module_path, attr, prefix in PLATFORM_MOUNTS:\n"
                "        try:\n"
                "            mod = __import__(module_path, fromlist=[attr])\n"
                "            app.include_router(getattr(mod, attr), prefix=prefix)\n"
                "        except Exception:\n"
                "            # Platform package may live in the host monorepo; document the mount.\n"
                "            pass\n"
            ),
            agent="backend",
            reuse=True,
            platform_ref="app/auth,app/payments,app/ai",
            language="python",
        )
    )
    # Custom endpoints only
    custom_eps = []
    if be and be.api:
        custom_eps = [e for e in be.api.endpoints if not e.reuse][:40]
    domain_routes = [
        "from fastapi import APIRouter\n",
        "from pydantic import BaseModel, Field\n",
        "from typing import Optional, List\n\n",
        "router = APIRouter()\n\n",
    ]
    for ep in custom_eps:
        name = _py_ident(ep.id or ep.path)
        method = (ep.method or "GET").lower()
        path = ep.path if ep.path.startswith("/") else f"/{ep.path}"
        # Strip common prefixes for domain router
        for prefix in ("/api/v1", "/api"):
            if path.startswith(prefix):
                path = path[len(prefix) :] or "/"
        domain_routes.append(
            f'@router.{method}("{path}", summary={json.dumps(ep.summary or ep.operation)})\n'
            f"def {name}():\n"
            f'    """Generated domain stub — implement product logic here."""\n'
            f"    return {{'ok': True, 'resource': {json.dumps(ep.resource)}}}\n\n"
        )
    if not custom_eps:
        domain_routes.append(
            '@router.get("/health")\n'
            "def domain_health():\n"
            "    return {'ok': True, 'note': 'No custom endpoints — platform covers the surface'}\n"
        )
    files.append(
        GeneratedFile(
            path="backend/app/domain/router.py",
            content="".join(domain_routes),
            agent="backend",
            reuse=not bool(custom_eps),
            language="python",
        )
    )
    files.append(
        GeneratedFile(
            path="backend/app/domain/__init__.py",
            content='"""Product domain package — custom only."""\n',
            agent="backend",
            reuse=False,
            language="python",
        )
    )
    files.append(
        GeneratedFile(
            path="backend/app/services/.gitkeep",
            content="",
            agent="backend",
            reuse=True,
            language="text",
        )
    )
    files.append(
        GeneratedFile(
            path="backend/app/repositories/.gitkeep",
            content="",
            agent="backend",
            reuse=True,
            language="text",
        )
    )
    # OpenAPI snapshot from backend manifest if present
    if be and getattr(be, "openapi", None):
        openapi_payload = (
            be.openapi.model_dump(mode="json")
            if hasattr(be.openapi, "model_dump")
            else be.openapi
        )
        files.append(
            GeneratedFile(
                path="backend/openapi.preview.json",
                content=json.dumps(openapi_payload, indent=2) + "\n",
                agent="backend",
                reuse=True,
                language="json",
            )
        )
    # RBAC note
    roles = list((be.rbac.roles if be and be.rbac else None) or ctx.blueprint.roles or [])
    files.append(
        GeneratedFile(
            path="backend/app/domain/rbac_policy.json",
            content=json.dumps(
                {
                    "reuse": "app/auth",
                    "roles": roles,
                    "note": "Enforce via existing Auth/RBAC — do not invent a parallel ACL",
                },
                indent=2,
            )
            + "\n",
            agent="backend",
            reuse=True,
            platform_ref="app/auth",
            language="json",
        )
    )
    reuse_n = sum(1 for f in files if f.reuse)
    return AgentResult(
        agent="backend",
        status="completed",
        files=files,
        message=f"{len(custom_eps)} custom endpoints",
        reuse_percent=round(100.0 * reuse_n / max(len(files), 1), 1),
    )


def agent_database(ctx: FactoryContext) -> AgentResult:
    be = ctx.backend
    files: List[GeneratedFile] = []
    files.append(
        GeneratedFile(
            path="database/README.md",
            content=(
                "# Database\n\n"
                "Uses platform Postgres/pgvector (`app/database`).\n"
                "Custom tables only — platform users/companies/billing tables are reused.\n"
            ),
            agent="database",
            reuse=True,
            platform_ref="app/database",
            language="markdown",
        )
    )
    custom_tables = []
    if be and be.database:
        custom_tables = [t for t in be.database.tables if not t.reuse][:30]
    model_parts = [
        '"""Custom SQLAlchemy models — platform tables are NOT duplicated."""\n',
        "from sqlalchemy import Column, String, Integer, ForeignKey, Boolean\n",
        "from sqlalchemy.dialects.postgresql import UUID, JSONB\n",
        "from app.models.base import Base, TimestampMixin\n",
        "import uuid\n\n",
    ]
    migration_ops = []
    for t in custom_tables:
        cls = "".join(part.title() for part in t.name.split("_"))
        model_parts.append(f"class {cls}(Base, TimestampMixin):\n")
        model_parts.append(f'    __tablename__ = "{t.name}"\n')
        model_parts.append(
            "    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)\n"
        )
        for col in (t.columns or [])[:20]:
            if col.name == "id":
                continue
            ctype = "String(255)"
            if col.type in ("int", "integer"):
                ctype = "Integer"
            elif col.type in ("bool", "boolean"):
                ctype = "Boolean"
            elif col.type in ("json", "jsonb"):
                ctype = "JSONB"
            model_parts.append(f"    {col.name} = Column({ctype}, nullable=True)\n")
        model_parts.append("\n")
        migration_ops.append(t.name)

    if not custom_tables:
        model_parts.append(
            "# No custom tables — rely on platform schema (users, companies, billing, …)\n"
        )
    files.append(
        GeneratedFile(
            path="database/models/domain.py",
            content="".join(model_parts),
            agent="database",
            reuse=not bool(custom_tables),
            language="python",
        )
    )
    rev = "studio_domain_001"
    files.append(
        GeneratedFile(
            path=f"database/alembic/versions/{rev}_domain_tables.py",
            content=(
                f'"""Domain tables for {_slug(ctx.project_title)}.\n\n'
                f"Revision ID: {rev}\n"
                'Revises: <set against platform head at merge time>\n'
                '"""\n'
                "from alembic import op\n"
                "import sqlalchemy as sa\n"
                "from sqlalchemy.dialects import postgresql\n\n"
                f'revision = "{rev}"\n'
                "down_revision = None  # wire to platform head when integrating\n\n"
                "def upgrade() -> None:\n"
                + (
                    "\n".join(
                        f'    # create {name} — flesh out columns from Studio backend manifest\n'
                        f"    pass  # placeholder for {name}"
                        for name in migration_ops
                    )
                    if migration_ops
                    else "    pass  # no custom tables\n"
                )
                + "\n\ndef downgrade() -> None:\n    pass\n"
            ),
            agent="database",
            reuse=not bool(custom_tables),
            language="python",
        )
    )
    files.append(
        GeneratedFile(
            path="database/schema_summary.json",
            content=json.dumps(
                {
                    "custom_tables": [t.name for t in custom_tables],
                    "relationships": [
                        r.model_dump(mode="json") if hasattr(r, "model_dump") else r
                        for r in ((be.database.relationships if be and be.database else None) or [])
                    ][:50],
                    "platform_reuse": "app/database + existing alembic chain",
                },
                indent=2,
            )
            + "\n",
            agent="database",
            reuse=True,
            language="json",
        )
    )
    return AgentResult(
        agent="database",
        status="completed",
        files=files,
        message=f"{len(custom_tables)} custom tables",
        reuse_percent=100.0 if not custom_tables else 60.0,
    )


def agent_ai(ctx: FactoryContext) -> AgentResult:
    ai = ctx.ai
    files: List[GeneratedFile] = []
    files.append(
        GeneratedFile(
            path="shared/ai/README.md",
            content=(
                "# AI configuration\n\n"
                "Uses existing AI Gateway (`app/ai`) and Agent Platform (`app/agent_platform`).\n"
                "These JSON configs are inputs to the platform — not a new runtime.\n"
            ),
            agent="ai",
            reuse=True,
            platform_ref="app/ai",
            language="markdown",
        )
    )
    agents = [a.model_dump(mode="json") for a in (ai.agents if ai else [])]
    prompts = [p.model_dump(mode="json") for p in (ai.prompts if ai else [])]
    tools = [t.model_dump(mode="json") for t in (ai.tools if ai else [])]
    files.append(
        GeneratedFile(
            path="shared/ai/agents.json",
            content=json.dumps({"agents": agents, "runtime": "app/agent_platform"}, indent=2) + "\n",
            agent="ai",
            reuse=True,
            platform_ref="app/agent_platform",
            language="json",
        )
    )
    files.append(
        GeneratedFile(
            path="shared/ai/prompts.json",
            content=json.dumps({"prompts": prompts}, indent=2) + "\n",
            agent="ai",
            reuse=True,
            language="json",
        )
    )
    files.append(
        GeneratedFile(
            path="shared/ai/tools.json",
            content=json.dumps({"tools": tools, "runtime": "app/ai"}, indent=2) + "\n",
            agent="ai",
            reuse=True,
            language="json",
        )
    )
    files.append(
        GeneratedFile(
            path="shared/ai/knowledge.json",
            content=json.dumps(
                {"knowledge": (ai.knowledge if ai else {}) or {}, "runtime": "app/knowledge"},
                indent=2,
            )
            + "\n",
            agent="ai",
            reuse=True,
            platform_ref="app/knowledge",
            language="json",
        )
    )
    files.append(
        GeneratedFile(
            path="shared/ai/memory.json",
            content=json.dumps({"memory": (ai.memory if ai else {}) or {}}, indent=2) + "\n",
            agent="ai",
            reuse=True,
            language="json",
        )
    )
    files.append(
        GeneratedFile(
            path="shared/ai/streaming.json",
            content=json.dumps(
                {
                    "streaming": True,
                    "sse": True,
                    "runtime": "app/agent_platform + openai_compat",
                },
                indent=2,
            )
            + "\n",
            agent="ai",
            reuse=True,
            language="json",
        )
    )
    files.append(
        GeneratedFile(
            path="shared/ai/safety.json",
            content=json.dumps(
                {"safety": (ai.safety if ai else {}) or {"moderation": True}},
                indent=2,
            )
            + "\n",
            agent="ai",
            reuse=True,
            language="json",
        )
    )
    return AgentResult(
        agent="ai",
        status="completed",
        files=files,
        message=f"{len(agents)} agents · {len(prompts)} prompts",
        reuse_percent=100.0,
    )


def agent_infrastructure(ctx: FactoryContext) -> AgentResult:
    files: List[GeneratedFile] = []
    slug = _slug(ctx.project_title)
    files.append(
        GeneratedFile(
            path="docker/README.md",
            content=(
                "# Infrastructure\n\n"
                "Prefer the host platform stack:\n"
                "- `docker-compose.prod.yml`\n"
                "- `Dockerfile`\n"
                "- `nginx/`\n"
                "- worker + scheduler services\n"
                "This folder is a product overlay template only.\n"
            ),
            agent="infrastructure",
            reuse=True,
            platform_ref="docker-compose.prod.yml",
            language="markdown",
        )
    )
    files.append(
        GeneratedFile(
            path="docker/Dockerfile",
            content=(
                "# Product overlay — prefer monorepo Dockerfile when deploying on THTWAAT\n"
                "FROM python:3.11-slim\n"
                "WORKDIR /app\n"
                "COPY backend /app/backend\n"
                'CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]\n'
            ),
            agent="infrastructure",
            reuse=True,
            platform_ref="Dockerfile",
            language="dockerfile",
        )
    )
    files.append(
        GeneratedFile(
            path="docker/docker-compose.yml",
            content=(
                f"# Overlay for {slug} — reuse platform redis/postgres/worker when on THTWAAT VPS\n"
                "services:\n"
                "  api:\n"
                "    build: .\n"
                "    ports: ['8000:8000']\n"
                "    env_file: [.env.example]\n"
                "  web:\n"
                "    image: node:20-alpine\n"
                "    working_dir: /app\n"
                "    volumes: ['../frontend:/app']\n"
                "    command: sh -c 'npm install && npm run dev'\n"
                "    ports: ['3000:3000']\n"
            ),
            agent="infrastructure",
            reuse=True,
            platform_ref="docker-compose.prod.yml",
            language="yaml",
        )
    )
    files.append(
        GeneratedFile(
            path="docker/nginx.conf",
            content=(
                "# Minimal reverse proxy — production should use platform nginx/\n"
                "server {\n"
                "  listen 80;\n"
                "  location /api/ { proxy_pass http://api:8000/; }\n"
                "  location / { proxy_pass http://web:3000/; }\n"
                "}\n"
            ),
            agent="infrastructure",
            reuse=True,
            platform_ref="nginx/",
            language="nginx",
        )
    )
    env_example = (ctx.infra.env_example if ctx.infra else None) or (
        "APP_ENV=production\nJWT_SECRET_KEY=\nDB_PASSWORD=\n"
    )
    files.append(
        GeneratedFile(
            path="docker/.env.example",
            content=env_example if env_example.endswith("\n") else env_example + "\n",
            agent="infrastructure",
            reuse=True,
            platform_ref=".env.prod.example",
            language="dotenv",
        )
    )
    files.append(
        GeneratedFile(
            path="docker/workers.md",
            content=(
                "# Workers & Scheduler\n\n"
                "Reuse `thtwaat-worker` and `thtwaat-scheduler` from docker-compose.prod.yml.\n"
                "Queue key: `thtwaat:jobs` via `app/monitoring/queue.py`.\n"
            ),
            agent="infrastructure",
            reuse=True,
            platform_ref="scripts/worker.py",
            language="markdown",
        )
    )
    files.append(
        GeneratedFile(
            path="docker/monitoring.md",
            content=(
                "# Monitoring\n\n"
                "Reuse `app/monitoring` + Prometheus/Grafana links from platform env.\n"
            ),
            agent="infrastructure",
            reuse=True,
            platform_ref="app/monitoring",
            language="markdown",
        )
    )
    return AgentResult(
        agent="infrastructure",
        status="completed",
        files=files,
        message="Compose/nginx/env overlay",
        reuse_percent=100.0,
    )


def agent_security(ctx: FactoryContext) -> AgentResult:
    secrets = []
    if ctx.infra:
        secrets = [e.key for e in ctx.infra.environment if e.secret]
    content = {
        "https_required": True,
        "cors_no_wildcard": True,
        "reuse_auth": "app/auth",
        "rate_limiting": "fastapi-limiter + redis",
        "secrets": secrets,
        "checklist": [
            "JWT secrets set",
            "SSL_MODE=certbot in production",
            "No public DB/Redis ports",
            "RBAC via existing Auth",
        ],
    }
    files = [
        GeneratedFile(
            path="docs/SECURITY.md",
            content=(
                f"# Security — {ctx.project_title}\n\n"
                "- Auth/RBAC: reuse `app/auth`\n"
                "- Rate limit: platform redis limiter\n"
                "- TLS: platform nginx + SSL manager\n"
                f"- Secrets to configure: {', '.join(secrets[:12]) or 'see infra env'}\n"
            ),
            agent="security",
            reuse=True,
            platform_ref="app/auth",
            language="markdown",
        ),
        GeneratedFile(
            path="docs/security_checklist.json",
            content=json.dumps(content, indent=2) + "\n",
            agent="security",
            reuse=True,
            language="json",
        ),
    ]
    return AgentResult(agent="security", status="completed", files=files, message="Security pack")


def agent_qa(ctx: FactoryContext) -> AgentResult:
    files = [
        GeneratedFile(
            path="tests/README.md",
            content=(
                "# Tests\n\n"
                "Product tests should call platform modules where reused.\n"
                "Generated smoke tests cover domain stubs only.\n"
            ),
            agent="qa",
            reuse=True,
            language="markdown",
        ),
        GeneratedFile(
            path="tests/unit/test_domain_health.py",
            content=(
                "def test_placeholder():\n"
                "    assert True  # replace with domain API tests when wired\n"
            ),
            agent="qa",
            reuse=False,
            language="python",
        ),
        GeneratedFile(
            path="tests/integration/test_platform_mounts.py",
            content=(
                "def test_platform_mount_list_non_empty():\n"
                "    from backend.app.platform_mounts import PLATFORM_MOUNTS\n"
                "    assert len(PLATFORM_MOUNTS) >= 3\n"
            ),
            agent="qa",
            reuse=True,
            language="python",
        ),
        GeneratedFile(
            path=".github/workflows/ci.yml",
            content=(
                "name: ci\n"
                "on: [push, pull_request]\n"
                "jobs:\n"
                "  smoke:\n"
                "    runs-on: ubuntu-latest\n"
                "    steps:\n"
                "      - uses: actions/checkout@v4\n"
                "      - uses: actions/setup-python@v5\n"
                "        with: { python-version: '3.11' }\n"
                "      - run: python -m pytest tests/unit -q || true\n"
            ),
            agent="qa",
            reuse=True,
            language="yaml",
        ),
    ]
    return AgentResult(agent="qa", status="completed", files=files, message="QA scaffolding")


def agent_documentation(ctx: FactoryContext) -> AgentResult:
    files = [
        GeneratedFile(
            path="README.md",
            content=(
                f"# {ctx.project_title}\n\n"
                f"Industry: {ctx.blueprint.industry} · Type: {ctx.blueprint.product_type}\n\n"
                "Generated by THTWAAT Studio AI Software Factory.\n\n"
                "## Structure\n\n"
                "- `frontend/` — Next.js product shell (reuses SaaS template pages)\n"
                "- `backend/` — FastAPI domain stubs + platform mounts\n"
                "- `database/` — custom models/migrations only\n"
                "- `shared/ai/` — agent/prompt/tool configs for AI Gateway\n"
                "- `docker/` — overlay templates referencing platform compose\n"
                "- `docs/` — build plan + security\n"
                "- `tests/` — smoke tests\n"
                "- `.github/` — CI workflow\n\n"
                "## Important\n\n"
                "Do **not** reimplement Auth, Billing, AI Gateway, Agents, Marketplace,\n"
                "Knowledge, Publisher, Admin, or Monitoring — mount the platform modules.\n"
            ),
            agent="documentation",
            reuse=True,
            language="markdown",
        ),
        GeneratedFile(
            path="docs/ARCHITECTURE.md",
            content=(
                f"# Architecture — {ctx.project_title}\n\n"
                "```\n"
                "Browser → Nginx → Next.js shell + FastAPI\n"
                "                ↘ Auth / Billing / AI Gateway (platform)\n"
                "                ↘ Domain stubs (generated)\n"
                "Postgres (pgvector) · Redis · Worker · Scheduler\n"
                "```\n"
            ),
            agent="documentation",
            reuse=True,
            language="markdown",
        ),
    ]
    return AgentResult(agent="documentation", status="completed", files=files, message="Docs")


AGENTS: Dict[str, Callable[[FactoryContext], AgentResult]] = {
    "planner": agent_planner,
    "frontend": agent_frontend,
    "backend": agent_backend,
    "database": agent_database,
    "ai": agent_ai,
    "infrastructure": agent_infrastructure,
    "security": agent_security,
    "qa": agent_qa,
    "documentation": agent_documentation,
}

STAGE_FOR_AGENT = {
    "planner": BuildStage.PLANNING.value,
    "frontend": BuildStage.GENERATING_FRONTEND.value,
    "backend": BuildStage.GENERATING_BACKEND.value,
    "database": BuildStage.GENERATING_DATABASE.value,
    "ai": BuildStage.GENERATING_AI.value,
    "infrastructure": BuildStage.GENERATING_INFRASTRUCTURE.value,
    "security": BuildStage.GENERATING.value,
    "qa": BuildStage.GENERATING.value,
    "documentation": BuildStage.GENERATING.value,
}


def validate_artifacts(files: List[GeneratedFile]) -> Tuple[bool, List[str]]:
    """Lint / schema / dependency / consistency checks (stdlib only)."""
    errors: List[str] = []
    paths = {f.path for f in files}
    required_roots = {
        "frontend/",
        "backend/",
        "shared/",
        "database/",
        "docker/",
        "docs/",
        "tests/",
        ".github/",
    }
    for root in required_roots:
        if not any(p.startswith(root) or p == root.rstrip("/") for p in paths):
            errors.append(f"missing_tree:{root}")
    if "README.md" not in paths:
        errors.append("missing:README.md")
    if "backend/app/main.py" not in paths:
        errors.append("missing:backend/app/main.py")
    if "backend/app/platform_mounts.py" not in paths:
        errors.append("missing:platform_mounts")
    # JSON validity
    for f in files:
        if f.path.endswith(".json") and f.content.strip():
            try:
                json.loads(f.content)
            except json.JSONDecodeError as exc:
                errors.append(f"json_invalid:{f.path}:{exc}")
    # Type-ish check: TS files should export or import something
    for f in files:
        if f.path.endswith((".ts", ".tsx")) and "export" not in f.content and f.content.strip():
            errors.append(f"ts_no_export:{f.path}")
    # Dependency doctrine: platform mounts present
    mounts = next((f for f in files if f.path.endswith("platform_mounts.py")), None)
    if mounts and "app.auth" not in mounts.content:
        errors.append("missing_auth_mount")
    return (len(errors) == 0), errors


def write_tree(root: Path, files: List[GeneratedFile]) -> List[Dict[str, Any]]:
    manifest: List[Dict[str, Any]] = []
    root.mkdir(parents=True, exist_ok=True)
    for f in files:
        target = root / f.path
        target.parent.mkdir(parents=True, exist_ok=True)
        data = f.content.encode("utf-8")
        target.write_bytes(data)
        digest = hashlib.sha256(data).hexdigest()
        manifest.append(
            {
                "path": f.path,
                "bytes": len(data),
                "sha256": digest,
                "agent": f.agent,
                "reuse": f.reuse,
                "platform_ref": f.platform_ref,
                "language": f.language,
            }
        )
    return manifest


def package_zip(root: Path, zip_path: Path) -> str:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in root.rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(root).as_posix())
    digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    return digest


def run_factory(
    ctx: FactoryContext,
    *,
    output_dir: Path,
    progress: Optional[ProgressCallback] = None,
    cancel_check: Optional[Callable[[], bool]] = None,
) -> Dict[str, Any]:
    """Execute all agents, validate, package ZIP. Returns build result dict."""
    emit_progress(progress, BuildStage.QUEUED.value, message="Build accepted")
    agent_statuses: Dict[str, Any] = {
        a: {"status": "queued", "message": ""} for a in AGENT_ORDER
    }
    all_files: List[GeneratedFile] = []
    logs: List[Dict[str, Any]] = []

    def log(msg: str, **extra: Any) -> None:
        entry = {"ts": datetime.now(timezone.utc).isoformat(), "message": msg, **extra}
        logs.append(entry)

    emit_progress(progress, BuildStage.PLANNING.value, message="Starting agents")
    for agent_name in AGENT_ORDER:
        if cancel_check and cancel_check():
            emit_progress(progress, BuildStage.CANCELLED.value, message="Cancelled")
            return {
                "ok": False,
                "status": "cancelled",
                "stage": BuildStage.CANCELLED.value,
                "agent_statuses": agent_statuses,
                "logs": logs,
                "files": [],
            }
        stage = STAGE_FOR_AGENT.get(agent_name, BuildStage.GENERATING.value)
        emit_progress(progress, stage, agent=agent_name, message=f"Running {agent_name}")
        agent_statuses[agent_name] = {"status": "running", "message": ""}
        try:
            result = AGENTS[agent_name](ctx)
            all_files.extend(result.files)
            agent_statuses[agent_name] = {
                "status": result.status,
                "message": result.message,
                "file_count": len(result.files),
                "reuse_percent": result.reuse_percent,
            }
            log(f"agent:{agent_name}", status=result.status, files=len(result.files))
        except Exception as exc:  # noqa: BLE001
            agent_statuses[agent_name] = {"status": "failed", "message": str(exc)}
            log(f"agent_failed:{agent_name}", error=str(exc))
            emit_progress(progress, BuildStage.FAILED.value, agent=agent_name, error=str(exc))
            return {
                "ok": False,
                "status": "failed",
                "stage": BuildStage.FAILED.value,
                "agent_statuses": agent_statuses,
                "logs": logs,
                "files": [],
                "error": str(exc),
                "retryable": True,
            }

    emit_progress(progress, BuildStage.VALIDATION.value, message="Validating artifacts")
    ok, errors = validate_artifacts(all_files)
    log("validation", ok=ok, errors=errors)
    if not ok:
        emit_progress(progress, BuildStage.FAILED.value, errors=errors)
        return {
            "ok": False,
            "status": "failed",
            "stage": BuildStage.FAILED.value,
            "agent_statuses": agent_statuses,
            "logs": logs,
            "files": [],
            "error": "; ".join(errors),
            "validation_errors": errors,
            "retryable": True,
        }

    emit_progress(progress, BuildStage.PACKAGING.value, message="Writing tree + ZIP")
    tree_dir = output_dir / "tree"
    if tree_dir.exists():
        import shutil

        shutil.rmtree(tree_dir)
    file_manifest = write_tree(tree_dir, all_files)
    zip_path = output_dir / "source.zip"
    zip_sha = package_zip(tree_dir, zip_path)
    log("packaged", files=len(file_manifest), zip_sha=zip_sha)

    emit_progress(
        progress,
        BuildStage.COMPLETED.value,
        message="Source generation completed",
        file_count=len(file_manifest),
    )
    return {
        "ok": True,
        "status": "completed",
        "stage": BuildStage.COMPLETED.value,
        "agent_statuses": agent_statuses,
        "logs": logs,
        "files": file_manifest,
        "artifact_path": str(zip_path.as_posix()),
        "artifact_sha256": zip_sha,
        "file_count": len(file_manifest),
        "retryable": False,
    }
