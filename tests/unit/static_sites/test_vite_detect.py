"""Unit tests for app/static_sites/vite_detect.py — pure, no Docker/subprocess."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.static_sites.vite_detect import ProjectFramework, detect_project_framework


def _write_pkg(root: Path, data: dict) -> None:
    (root / "package.json").write_text(json.dumps(data), encoding="utf-8")


@pytest.mark.unit
def test_no_package_json_is_plain_static(tmp_path: Path):
    (tmp_path / "index.html").write_text("<html></html>")
    result = detect_project_framework(tmp_path)
    assert result.framework == ProjectFramework.STATIC_ZIP


@pytest.mark.unit
def test_vite_detected_via_dependency(tmp_path: Path):
    _write_pkg(tmp_path, {
        "name": "app", "scripts": {"build": "vite build"},
        "devDependencies": {"vite": "^5.0.0"},
    })
    (tmp_path / "package-lock.json").write_text("{}")

    result = detect_project_framework(tmp_path)

    assert result.framework == ProjectFramework.VITE
    assert result.package_manager == "npm"
    assert result.use_ci is True
    assert result.build_command == "npm run build"
    assert result.warnings == []


@pytest.mark.unit
def test_vite_detected_via_config_file_even_without_dependency_entry(tmp_path: Path):
    _write_pkg(tmp_path, {"name": "app", "scripts": {"build": "vite build"}})
    (tmp_path / "vite.config.ts").write_text("export default {}")

    result = detect_project_framework(tmp_path)

    assert result.framework == ProjectFramework.VITE


@pytest.mark.unit
def test_vite_without_lockfile_uses_install_not_ci(tmp_path: Path):
    _write_pkg(tmp_path, {
        "name": "app", "scripts": {"build": "vite build"},
        "devDependencies": {"vite": "^5.0.0"},
    })

    result = detect_project_framework(tmp_path)

    assert result.framework == ProjectFramework.VITE
    assert result.use_ci is False
    assert any("npm install" in w for w in result.warnings)


@pytest.mark.unit
def test_missing_build_script_is_unsupported(tmp_path: Path):
    _write_pkg(tmp_path, {"name": "app", "devDependencies": {"vite": "^5.0.0"}})

    result = detect_project_framework(tmp_path)

    assert result.framework == ProjectFramework.UNSUPPORTED
    assert "build" in result.message.lower()


@pytest.mark.unit
def test_plain_package_json_without_vite_markers_is_unsupported(tmp_path: Path):
    _write_pkg(tmp_path, {"name": "app", "scripts": {"build": "webpack"}})

    result = detect_project_framework(tmp_path)

    assert result.framework == ProjectFramework.UNSUPPORTED
    assert "build environment" in result.message.lower()


@pytest.mark.unit
@pytest.mark.parametrize(
    "marker,label",
    [
        ("nuxt.config.ts", "Nuxt"),
        ("angular.json", "Angular"),
    ],
)
def test_known_unsupported_config_markers_rejected_with_clear_message(tmp_path: Path, marker, label):
    _write_pkg(tmp_path, {"name": "app", "scripts": {"build": "build"}})
    (tmp_path / marker).write_text("{}")

    result = detect_project_framework(tmp_path)

    assert result.framework == ProjectFramework.UNSUPPORTED
    assert label in result.message


@pytest.mark.unit
@pytest.mark.parametrize("dep,label", [("nuxt", "Nuxt"), ("@angular/core", "Angular"), ("express", "Express")])
def test_known_unsupported_dependency_markers_rejected(tmp_path: Path, dep, label):
    _write_pkg(tmp_path, {"name": "app", "scripts": {"build": "build"}, "dependencies": {dep: "1.0.0"}})

    result = detect_project_framework(tmp_path)

    assert result.framework == ProjectFramework.UNSUPPORTED
    assert label in result.message


# ---- Next.js (THTWAAT Phase 3) ---------------------------------------------


@pytest.mark.unit
def test_nextjs_dependency_detected(tmp_path: Path):
    _write_pkg(tmp_path, {
        "name": "app", "scripts": {"build": "next build"}, "dependencies": {"next": "14.2.0"},
    })
    (tmp_path / "package-lock.json").write_text("{}")

    result = detect_project_framework(tmp_path)

    assert result.framework == ProjectFramework.NEXTJS
    assert result.package_manager == "npm"
    assert result.use_ci is True
    assert result.build_command == "npm run build"


@pytest.mark.unit
@pytest.mark.parametrize("config_name", ["next.config.js", "next.config.mjs", "next.config.ts"])
def test_nextjs_config_file_detected_without_dependency(tmp_path: Path, config_name):
    # A next.config.* file is decisive even if the "next" dependency were
    # somehow missing from package.json (e.g. a monorepo hoisting deps
    # elsewhere) — config marker checked first.
    _write_pkg(tmp_path, {"name": "app", "scripts": {"build": "next build"}})
    (tmp_path / config_name).write_text("module.exports = { output: 'standalone' }\n")

    result = detect_project_framework(tmp_path)

    assert result.framework == ProjectFramework.NEXTJS


@pytest.mark.unit
def test_nextjs_project_missing_build_script_is_unsupported(tmp_path: Path):
    _write_pkg(tmp_path, {"name": "app", "dependencies": {"next": "14.2.0"}})

    result = detect_project_framework(tmp_path)

    assert result.framework == ProjectFramework.UNSUPPORTED
    assert "build" in result.message.lower()


@pytest.mark.unit
def test_nextjs_project_without_lockfile_warns_and_uses_install(tmp_path: Path):
    _write_pkg(tmp_path, {"name": "app", "scripts": {"build": "next build"}, "dependencies": {"next": "14.2.0"}})

    result = detect_project_framework(tmp_path)

    assert result.framework == ProjectFramework.NEXTJS
    assert result.use_ci is False
    assert any("npm install" in w for w in result.warnings)


@pytest.mark.unit
@pytest.mark.parametrize("lockfile,pm", [("yarn.lock", "yarn"), ("pnpm-lock.yaml", "pnpm"), ("bun.lockb", "bun")])
def test_nextjs_non_npm_lockfile_rejected(tmp_path: Path, lockfile, pm):
    _write_pkg(tmp_path, {"name": "app", "scripts": {"build": "next build"}, "dependencies": {"next": "14.2.0"}})
    (tmp_path / lockfile).write_text("")

    result = detect_project_framework(tmp_path)

    assert result.framework == ProjectFramework.UNSUPPORTED
    assert pm in result.message


@pytest.mark.unit
@pytest.mark.parametrize("lockfile,pm", [("yarn.lock", "yarn"), ("pnpm-lock.yaml", "pnpm"), ("bun.lockb", "bun")])
def test_non_npm_lockfile_rejected_as_unsupported_package_manager(tmp_path: Path, lockfile, pm):
    _write_pkg(tmp_path, {
        "name": "app", "scripts": {"build": "vite build"}, "devDependencies": {"vite": "^5.0.0"},
    })
    (tmp_path / lockfile).write_text("")

    result = detect_project_framework(tmp_path)

    assert result.framework == ProjectFramework.UNSUPPORTED
    assert pm in result.message.lower()


@pytest.mark.unit
def test_malformed_package_json_is_unsupported_not_a_crash(tmp_path: Path):
    (tmp_path / "package.json").write_text("{not valid json,,,")

    result = detect_project_framework(tmp_path)

    assert result.framework == ProjectFramework.UNSUPPORTED
    assert "package.json" in result.message.lower()


@pytest.mark.unit
def test_oversized_package_json_is_unsupported_not_read_fully(tmp_path: Path):
    (tmp_path / "package.json").write_text("x" * (3 * 1024 * 1024))  # > 2MB cap

    result = detect_project_framework(tmp_path)

    assert result.framework == ProjectFramework.UNSUPPORTED
    assert "too large" in result.message.lower()


@pytest.mark.unit
def test_package_json_scripts_are_never_executed(tmp_path: Path, monkeypatch):
    """Detection must be pure inspection — a malicious build script must
    never run just from being detected."""
    marker = tmp_path / "EXECUTED"
    _write_pkg(tmp_path, {
        "name": "app",
        "scripts": {"build": f"touch {marker} && vite build"},
        "devDependencies": {"vite": "^5.0.0"},
    })

    import subprocess

    def _fail_if_called(*a, **kw):
        raise AssertionError("detection must never invoke subprocess")

    monkeypatch.setattr(subprocess, "run", _fail_if_called)
    monkeypatch.setattr("os.system", _fail_if_called)

    result = detect_project_framework(tmp_path)

    assert result.framework == ProjectFramework.VITE
    assert not marker.exists()


@pytest.mark.unit
def test_package_json_not_a_dict_is_unsupported(tmp_path: Path):
    (tmp_path / "package.json").write_text(json.dumps(["not", "an", "object"]))

    result = detect_project_framework(tmp_path)

    assert result.framework == ProjectFramework.UNSUPPORTED
