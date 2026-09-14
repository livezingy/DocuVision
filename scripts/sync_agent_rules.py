#!/usr/bin/env python3
"""Derive per-agent rule copies from the agent-ops kernel (docs/agent-ops/core).

The kernel files are the single source of truth for shared constraints. This
script generates thin copies into each agent's rules directory and stamps a
`kernel-ref` hash so `audit_agent_ops.py` can detect drift.

Usage:
    python scripts/sync_agent_rules.py            # write generated copies
    python scripts/sync_agent_rules.py --check    # report drift, no writes

Exit code:
    0  success (or no drift when --check)
    1  drift detected (only with --check)

Idempotent: same kernel input -> same generated output.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
KERNEL_DIR = REPO_ROOT / "docs" / "agent-ops" / "core"

# ---------------------------------------------------------------------------
# Mapping: agent -> directory, extension, and (output file, source stems, meta).
# Each entry: "out" filename, "sources" list of kernel stems, "title", and
# optional Cursor-style YAML frontmatter (None for Codebuddy plain md).
# ---------------------------------------------------------------------------
AGENTS = {
    "cursor": {
        "dir": REPO_ROOT / ".cursor" / "rules",
        "ext": ".mdc",
        "files": [
            {
                "out": "001-general.mdc",
                "sources": ["constraints"],
                "title": "通用约束",
                "frontmatter": {
                    "description": "DocuVision 通用约束（思维/沟通/红线/模型/收尾）",
                    "alwaysApply": True,
                },
                "extra": (
                    "\n## 规则文件说明（.cursor/rules/）\n"
                    "- 001-general（本文件，always）：通用约束（kernel: constraints）\n"
                    "- 002-python（globs *.py）：Python 规范（Cursor 专属）\n"
                    "- 003-git（按需）：Git/Actions 规范（Cursor 专属）\n"
                    "- 004-project（always）：项目事实 + 测试验证（kernel: environment + testing）\n"
                    "- 005-code-language（always）：代码语言编码（已并入 kernel constraints，留索引）\n"
                    "- 006-cloud-testing（按需）：Cloud 验证速查（Cursor 专属）\n"
                    "- 007-official-source-first（always）：官方依据优先（已并入 kernel constraints，留索引）\n"
                    "- 008-context-handoff（always）：长对话交接（已并入 kernel constraints，留索引）\n"
                    "- 009-doc-sync（globs docs/代码）：文档同步（kernel: doc-sync）\n"
                    "- SKILLS.md：投标/试用/定制操作流程"
                ),
            },
            {
                "out": "004-project.mdc",
                "sources": ["environment", "testing"],
                "title": "项目事实与测试验证",
                "frontmatter": {
                    "description": "DocuVision 项目目标、事实、工作流、目录卫生、测试验证",
                    "alwaysApply": True,
                },
            },
            {
                "out": "009-doc-sync.mdc",
                "sources": ["doc-sync"],
                "title": "文档同步（强制，防漂移）",
                "frontmatter": {
                    "description": "文档同步机制、归属表、生命周期（改契约代码或文档时触发）",
                    "globs": "docs/**/*.md,backend/app/**/*.py,apps/lite/backend/**/*.py,packages/docuvision-core/**/*.py,frontend/**/*.ts,frontend/**/*.tsx,frontend/**/*.js",
                },
            },
        ],
    },
    "codebuddy": {
        "dir": REPO_ROOT / ".codebuddy" / "rules",
        "ext": ".md",
        "files": [
            {
                "out": "001-general.md",
                "sources": ["constraints"],
                "title": "通用约束",
                "frontmatter": None,
            },
            {
                "out": "004-project.md",
                "sources": ["environment", "testing"],
                "title": "项目事实与测试验证",
                "frontmatter": None,
            },
            {
                "out": "009-doc-sync.md",
                "sources": ["doc-sync"],
                "title": "文档同步（强制，防漂移）",
                "frontmatter": None,
            },
        ],
    },
}


def _kernel_path(stem: str) -> Path:
    return KERNEL_DIR / f"{stem}.md"


def _body(stem: str) -> str:
    """Return the kernel body: drop the leading '# title' + '> ...' header,
    keeping everything from the first '## ' onward."""
    lines = _kernel_path(stem).read_text(encoding="utf-8").splitlines()
    start = 0
    for i, ln in enumerate(lines):
        if ln.startswith("## "):
            start = i
            break
    return "\n".join(lines[start:]).rstrip() + "\n"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _kernel_ref(stems: list[str]) -> str:
    parts = []
    for stem in stems:
        raw = _kernel_path(stem).read_text(encoding="utf-8")
        parts.append(f"{stem}.md:{_sha(raw)}")
    return "<!-- kernel-ref: " + "; ".join(parts) + " -->"


def _render_frontmatter(fm: dict | None) -> str:
    if not fm:
        return ""
    lines = ["---"]
    for key, value in fm.items():
        if isinstance(value, bool):
            lines.append(f"{key}: {str(value).lower()}")
        else:
            lines.append(f"{key}: {value}")
    lines.append("---")
    return "\n".join(lines) + "\n"


def render(spec: dict) -> str:
    parts: list[str] = []
    fm = _render_frontmatter(spec["frontmatter"])
    if fm:
        parts.append(fm)
    parts.append(f"# {spec['title']}")
    parts.append("")
    parts.append(
        "> 生成自 kernel `docs/agent-ops/core/`（"
        + ", ".join(spec["sources"])
        + "）。勿手改副本；改共享约束请编辑 kernel 后重跑 `scripts/sync_agent_rules.py`。"
    )
    parts.append(_kernel_ref(spec["sources"]))
    parts.append("")
    for stem in spec["sources"]:
        parts.append(_body(stem))
    extra = spec.get("extra", "")
    if extra:
        parts.append(extra.rstrip())
    return "\n".join(parts).rstrip() + "\n"


def sync(check: bool = False) -> int:
    drift = 0
    for agent, cfg in AGENTS.items():
        cfg["dir"].mkdir(parents=True, exist_ok=True)
        for spec in cfg["files"]:
            out_path = cfg["dir"] / spec["out"]
            new_content = render(spec)
            if out_path.exists() and out_path.read_text(encoding="utf-8") == new_content:
                print(f"[OK]   {out_path.relative_to(REPO_ROOT)} (unchanged)")
                continue
            if check:
                print(f"[DRIFT] {out_path.relative_to(REPO_ROOT)} differs from kernel")
                drift += 1
                continue
            out_path.write_text(new_content, encoding="utf-8")
            print(f"[SYNC] {out_path.relative_to(REPO_ROOT)}")
    return 1 if drift else 0


def main() -> int:
    check = "--check" in sys.argv[1:]
    return sync(check=check)


if __name__ == "__main__":
    sys.exit(main())
