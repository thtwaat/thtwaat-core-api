"""Admin deployment dashboard service."""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Any, Dict, List
from uuid import UUID

from sqlalchemy.orm import Session

from app.deploy import backup as backup_mod
from app.deploy import health as health_mod
from app.deploy import metrics as metrics_mod
from app.domains.models import CompanyDomain
from app.domains.repository import DomainRepository
from app.ssl.manager import SslManager, normalize_ssl_status
from app.ssl.nginx_gen import conf_dir, reload_nginx

logger = logging.getLogger(__name__)


class DeployDashboardService:
    def __init__(self, db: Session):
        self.db = db
        self.domains = DomainRepository(db)
        self.ssl = SslManager(db)

    async def overview(self, company_id: UUID | None = None) -> Dict[str, Any]:
        health = await health_mod.full_health(self.db)
        snap = metrics_mod.snapshot(self.db)

        q = self.db.query(CompanyDomain)
        if company_id:
            q = q.filter(CompanyDomain.company_id == company_id)
        domains = q.order_by(CompanyDomain.created_at.desc()).limit(100).all()

        domain_rows = []
        for d in domains:
            domain_rows.append({
                "id": str(d.id),
                "hostname": d.hostname,
                "status": d.status.value if hasattr(d.status, "value") else str(d.status),
                "ssl_status": normalize_ssl_status(d.ssl_status),
                "expires_at": d.ssl_expires_at.isoformat() if d.ssl_expires_at else None,
                "nginx_config_path": d.nginx_config_path,
                "renew_attempts": int(d.renew_attempts or 0),
                "renewal_error": d.renewal_error,
            })

        nginx_files = [p.name for p in conf_dir().glob("*.conf")]
        return {
            "health": health,
            "metrics": snap,
            "domains": domain_rows,
            "nginx": {
                "generated_vhosts": nginx_files,
                "conf_dir": str(conf_dir()),
            },
            "containers": self.list_containers(),
            "backups": backup_mod.list_backups()[:20],
        }

    def list_containers(self) -> List[Dict[str, str]]:
        try:
            r = subprocess.run(
                ["docker", "compose", "ps", "--format", "json"],
                capture_output=True,
                text=True,
                timeout=15,
            )
            if r.returncode != 0:
                return [{"error": r.stderr.strip() or "docker compose unavailable"}]
            import json

            lines = [ln for ln in r.stdout.splitlines() if ln.strip()]
            out = []
            for ln in lines:
                try:
                    obj = json.loads(ln)
                    out.append({
                        "name": obj.get("Name") or obj.get("Service"),
                        "state": obj.get("State") or obj.get("Status"),
                        "health": obj.get("Health", ""),
                    })
                except json.JSONDecodeError:
                    # compose may return a JSON array
                    pass
            if not out and r.stdout.strip().startswith("["):
                arr = json.loads(r.stdout)
                for obj in arr:
                    out.append({
                        "name": obj.get("Name") or obj.get("Service"),
                        "state": obj.get("State") or obj.get("Status"),
                        "health": obj.get("Health", ""),
                    })
            return out
        except Exception as exc:
            return [{"error": str(exc)}]

    def restart_service(self, service: str) -> Dict[str, str]:
        allowed = {"api", "nginx", "worker", "scheduler", "redis", "db"}
        if service not in allowed:
            return {"ok": "false", "error": f"service not allowed: {service}"}
        try:
            r = subprocess.run(
                ["docker", "compose", "restart", service],
                capture_output=True,
                text=True,
                timeout=120,
            )
            return {"ok": str(r.returncode == 0), "output": (r.stdout or r.stderr)[:2000]}
        except Exception as exc:
            return {"ok": "false", "error": str(exc)}

    def reload_nginx(self) -> Dict[str, str]:
        ok, msg = reload_nginx()
        return {"ok": str(ok), "message": msg}

    def trigger_backup(self) -> Dict[str, str]:
        return backup_mod.run_full_backup()

    def renew_domain_ssl(self, domain_id: UUID, company_id: UUID, user_id: UUID) -> Dict[str, Any]:
        return self.ssl.renew(domain_id, company_id, user_id)

    def recent_logs(self, service: str = "api", lines: int = 100) -> Dict[str, Any]:
        try:
            r = subprocess.run(
                ["docker", "compose", "logs", "--tail", str(lines), service],
                capture_output=True,
                text=True,
                timeout=30,
            )
            return {"service": service, "logs": r.stdout[-50000:]}
        except Exception as exc:
            return {"service": service, "error": str(exc)}
