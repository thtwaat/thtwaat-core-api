"""THTWAAT Deploy — project framework detection (static vs Vite vs Next.js).

Reads package.json and marker files ONLY as data (json.loads / text search).
Nothing in this module ever executes, imports, or evaluates anything from
the uploaded project — package.json "scripts" are inspected as strings,
never run.

Next.js detection (THTWAAT Phase 3) recognizes `next` in
dependencies/devDependencies (per-instructions: dependencies.next OR
devDependencies.next) or a next.config.* file, and is checked BEFORE the
generic "has package.json but isn't Vite" rejection below — it no longer
routes into _UNSUPPORTED_DEP_MARKERS/_UNSUPPORTED_CONFIG_MARKERS. Whether the
project actually produced a `next.config.*` with `output: "standalone"` is
NOT decidable from package.json alone (next.config.js is often a JS module,
never evaluated here) — that is verified after the build, on the real build
output, by app/static_sites/nextjs_build.py.
"""
from __future__ import annotations

import enum
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

MAX_PACKAGE_JSON_BYTES = 2 * 1024 * 1024  # package.json is never legitimately larger

_VITE_CONFIG_NAMES = (
    "vite.config.js", "vite.config.ts", "vite.config.mjs", "vite.config.cjs",
)

_NEXTJS_CONFIG_NAMES = ("next.config.js", "next.config.mjs", "next.config.ts")

# Marker file -> human-readable framework name for a clear rejection message.
# next.config.* deliberately NOT listed here — see module docstring.
_UNSUPPORTED_CONFIG_MARKERS = {
    "nuxt.config.js": "Nuxt",
    "nuxt.config.ts": "Nuxt",
    "angular.json": "Angular",
}

# dependency/devDependency name -> human-readable framework name.
# "next" deliberately NOT listed here — see module docstring.
_UNSUPPORTED_DEP_MARKERS = {
    "nuxt": "Nuxt",
    "nuxt3": "Nuxt",
    "@angular/core": "Angular",
    "@nestjs/core": "a Node.js backend (NestJS)",
    "express": "a Node.js backend (Express)",
    "fastify": "a Node.js backend (Fastify)",
    "koa": "a Node.js backend (Koa)",
}

_LOCKFILE_TO_PM = {
    "package-lock.json": "npm",
    "yarn.lock": "yarn",
    "pnpm-lock.yaml": "pnpm",
    "bun.lockb": "bun",
}

_UNSUPPORTED_PM_NAMES = {"yarn", "pnpm", "bun"}


class ProjectFramework(str, enum.Enum):
    STATIC_HTML = "static_html"
    STATIC_ZIP = "static_zip"
    VITE = "vite"
    NEXTJS = "nextjs"
    UNSUPPORTED = "unsupported"


@dataclass
class FrameworkDetection:
    framework: ProjectFramework
    message: str
    package_manager: Optional[str] = None
    use_ci: bool = False
    build_command: Optional[str] = None
    warnings: List[str] = field(default_factory=list)


def _read_package_json(root: Path) -> Optional[dict]:
    pkg_path = root / "package.json"
    if not pkg_path.is_file():
        return None
    try:
        if pkg_path.stat().st_size > MAX_PACKAGE_JSON_BYTES:
            return {"__invalid__": "package.json is too large"}
        raw = pkg_path.read_text(encoding="utf-8", errors="replace")
        data = json.loads(raw)
        if not isinstance(data, dict):
            return {"__invalid__": "package.json is not a JSON object"}
        return data
    except (OSError, json.JSONDecodeError):
        return {"__invalid__": "package.json is not valid JSON"}


def _dep_names(pkg: dict) -> set[str]:
    names: set[str] = set()
    for key in ("dependencies", "devDependencies", "peerDependencies"):
        section = pkg.get(key)
        if isinstance(section, dict):
            names.update(str(k) for k in section.keys())
    return names


def detect_project_framework(
    root: Path, *, default_static_framework: ProjectFramework = ProjectFramework.STATIC_ZIP
) -> FrameworkDetection:
    """Inspect an already safely-extracted project tree and classify it.

    Never touches anything outside `root`; never executes any file.
    """
    pkg = _read_package_json(root)

    if pkg is None:
        # No package.json at all — a plain static site. Existing behavior,
        # completely unchanged: caller still requires index.html.
        return FrameworkDetection(framework=default_static_framework, message="Static site")

    if "__invalid__" in pkg:
        return FrameworkDetection(
            framework=ProjectFramework.UNSUPPORTED,
            message=f"package.json could not be read ({pkg['__invalid__']}).",
        )

    dep_names = _dep_names(pkg)

    for marker, label in _UNSUPPORTED_CONFIG_MARKERS.items():
        if (root / marker).is_file():
            return FrameworkDetection(
                framework=ProjectFramework.UNSUPPORTED,
                message=(
                    f"This project contains {marker} and requires a {label} server runtime. "
                    "Currently THTWAAT Deploy supports static HTML/ZIP, Vite, and Next.js projects only."
                ),
            )
    for dep, label in _UNSUPPORTED_DEP_MARKERS.items():
        if dep in dep_names:
            return FrameworkDetection(
                framework=ProjectFramework.UNSUPPORTED,
                message=(
                    f"This project depends on {dep} and appears to be {label}. "
                    "Currently THTWAAT Deploy supports static HTML/ZIP, Vite, and Next.js projects only."
                ),
            )

    has_next_config = any((root / name).is_file() for name in _NEXTJS_CONFIG_NAMES)
    is_nextjs = has_next_config or "next" in dep_names

    has_vite_config = any((root / name).is_file() for name in _VITE_CONFIG_NAMES)
    scripts = pkg.get("scripts") if isinstance(pkg.get("scripts"), dict) else {}
    build_script = scripts.get("build") if isinstance(scripts, dict) else None
    build_script_mentions_vite = isinstance(build_script, str) and "vite" in build_script.lower()
    looks_like_vite = has_vite_config or "vite" in dep_names or build_script_mentions_vite

    if not is_nextjs and not looks_like_vite:
        return FrameworkDetection(
            framework=ProjectFramework.UNSUPPORTED,
            message=(
                "This project contains package.json and requires a build environment. "
                "Currently THTWAAT Deploy supports static HTML/ZIP, Vite, and Next.js projects only."
            ),
        )

    # Package manager: only npm is supported this phase (both Vite and Next.js).
    present_lockfiles = [name for name in _LOCKFILE_TO_PM if (root / name).is_file()]
    non_npm = [name for name in present_lockfiles if _LOCKFILE_TO_PM[name] in _UNSUPPORTED_PM_NAMES]
    if non_npm:
        pm = _LOCKFILE_TO_PM[non_npm[0]]
        return FrameworkDetection(
            framework=ProjectFramework.UNSUPPORTED,
            message=(
                f"This project uses {pm} ({non_npm[0]}). "
                "Currently THTWAAT Deploy only supports npm for Vite and Next.js projects."
            ),
        )
    has_npm_lockfile = "package-lock.json" in present_lockfiles
    warnings: List[str] = []
    if not has_npm_lockfile:
        warnings.append("No package-lock.json found — using `npm install` instead of `npm ci`.")

    if is_nextjs:
        if not isinstance(build_script, str) or not build_script.strip():
            return FrameworkDetection(
                framework=ProjectFramework.UNSUPPORTED,
                message="This Next.js project is missing a \"build\" script in package.json.",
            )
        return FrameworkDetection(
            framework=ProjectFramework.NEXTJS,
            message="Next.js project detected",
            package_manager="npm",
            use_ci=has_npm_lockfile,
            build_command="npm run build",
            warnings=warnings,
        )

    if not isinstance(build_script, str) or not build_script.strip():
        return FrameworkDetection(
            framework=ProjectFramework.UNSUPPORTED,
            message="This Vite project is missing a \"build\" script in package.json.",
        )

    return FrameworkDetection(
        framework=ProjectFramework.VITE,
        message="Vite project detected",
        package_manager="npm",
        use_ci=has_npm_lockfile,
        build_command="npm run build",
        warnings=warnings,
    )
