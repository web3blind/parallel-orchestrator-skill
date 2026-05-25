#!/usr/bin/env python3
"""Prepare a durable orchestration workspace for Hermes parallel read-only work.

This is intentionally a local planning/provisioning helper, not an LLM runner.
It creates the resources an orchestrator needs before calling delegate_task:

- a manifest and resource inventory;
- balanced worker task packages;
- self-contained worker prompts;
- worker output placeholders;
- synthesis and verification prompts.

Default policy is read-only. The script may create files only under --out and,
when explicitly requested, copy input files into --out/inputs_snapshot.
"""

from __future__ import annotations

import argparse
import dataclasses
import glob
import hashlib
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


DEFAULT_RESEARCH_SCHEMA = """Object(s):
Summary:
Key facts / findings:
Evidence / sources:
Risks or caveats:
Confidence: high / medium / low
Open questions:
""".strip()

DEFAULT_AUDIT_SCHEMA = """Scope reviewed:
Critical issues:
Important issues:
Minor issues:
Evidence with paths/lines:
Suggested fixes:
Confidence:
""".strip()

DEFAULT_TRIAGE_SCHEMA = """Item:
State:
Evidence:
Likely action:
Risks:
Confidence:
""".strip()


@dataclasses.dataclass(frozen=True)
class Resource:
    kind: str
    value: str
    label: str = ""
    exists: bool | None = None
    sha256: str | None = None
    size_bytes: int | None = None


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9а-яё._-]+", "-", value, flags=re.IGNORECASE)
    value = re.sub(r"-+", "-", value).strip("-._")
    return value[:80] or "orchestration"


def split_items(raw: str | None) -> list[str]:
    if not raw:
        return []
    parts = re.split(r"[|\n]", raw)
    return [p.strip() for p in parts if p.strip()]


def read_list_file(path: str | None) -> list[str]:
    if not path:
        return []
    data = Path(path).read_text(encoding="utf-8")
    return [line.strip() for line in data.splitlines() if line.strip() and not line.strip().startswith("#")]


def expand_file_patterns(patterns: Iterable[str]) -> list[Path]:
    files: list[Path] = []
    seen: set[Path] = set()
    for pattern in patterns:
        for match in glob.glob(pattern, recursive=True):
            path = Path(match).expanduser().resolve()
            if path.is_file() and path not in seen:
                seen.add(path)
                files.append(path)
    return files


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_resource(raw: str) -> Resource:
    # Supported forms:
    #   label=kind:value
    #   kind:value
    #   plain-value  -> note/plain resource
    label = ""
    value = raw.strip()
    if "=" in value and value.split("=", 1)[0].strip():
        label, value = [p.strip() for p in value.split("=", 1)]
    if ":" in value and re.match(r"^[a-zA-Z][a-zA-Z0-9_-]*:", value):
        kind, body = value.split(":", 1)
    else:
        kind, body = "note", value
    return Resource(kind=kind, value=body, label=label)


def resource_from_file(path: Path) -> Resource:
    return Resource(
        kind="file",
        value=str(path),
        label=path.name,
        exists=path.exists(),
        sha256=sha256_file(path) if path.exists() else None,
        size_bytes=path.stat().st_size if path.exists() else None,
    )


def choose_schema(task_type: str, custom: str | None) -> str:
    if custom:
        return Path(custom).read_text(encoding="utf-8").strip()
    normalized = task_type.lower()
    if "audit" in normalized or "review" in normalized:
        return DEFAULT_AUDIT_SCHEMA
    if "triage" in normalized or "pr" in normalized or "issue" in normalized:
        return DEFAULT_TRIAGE_SCHEMA
    return DEFAULT_RESEARCH_SCHEMA


def balanced_chunks(items: list[str], n: int) -> list[list[str]]:
    if not items:
        return []
    n = max(1, min(n, len(items)))
    chunks = [[] for _ in range(n)]
    for idx, item in enumerate(items):
        chunks[idx % n].append(item)
    return [c for c in chunks if c]


def worker_prompt(
    *,
    project: str,
    task_type: str,
    worker_id: int,
    targets: list[str],
    file_paths: list[str],
    resources: list[Resource],
    rubric: str,
    output_schema: str,
    toolsets: str,
    policy: str,
) -> str:
    target_block = "\n".join(f"- {t}" for t in targets) if targets else "- No named targets; use assigned files/resources."
    file_block = "\n".join(f"- {p}" for p in file_paths) if file_paths else "- No assigned local files."
    resource_block = "\n".join(
        f"- {r.label + ': ' if r.label else ''}{r.kind}:{r.value}" for r in resources
    ) or "- No extra resources."
    return f"""You are a specialist worker in a Hermes parallel orchestration run.

Project: {project}
Task type: {task_type}
Worker: {worker_id}
Execution policy: {policy}
Recommended toolsets: {toolsets}

Scope assigned to this worker:
Targets:
{target_block}

Local files assigned:
{file_block}

Shared resources / references:
{resource_block}

Rubric:
{rubric}

Rules:
- Work only on the assigned slice.
- Treat this as read-only unless the parent explicitly says otherwise.
- Do not commit, push, deploy, trade, send messages, submit forms, or mutate external systems.
- Do not edit shared files or a shared final document.
- Return concrete evidence: URLs, file paths/lines, command output, or explicit uncertainty.
- Child output is a lead, not final verification; the parent will synthesize and verify.

Return exactly this schema:

{output_schema}
""".strip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Provision a Hermes parallel orchestration workspace")
    parser.add_argument("--project", required=True, help="Project title / original goal")
    parser.add_argument("--task-type", default="research", help="research, audit, triage, comparison, etc.")
    parser.add_argument("--targets", help="Pipe- or newline-separated targets, e.g. 'A|B|C'")
    parser.add_argument("--targets-file", help="File with one target per line")
    parser.add_argument("--files", action="append", default=[], help="Glob of local files to assign, repeatable")
    parser.add_argument("--resource", action="append", default=[], help="Extra resource: label=kind:value or kind:value")
    parser.add_argument("--rubric", help="Inline rubric")
    parser.add_argument("--rubric-file", help="Markdown/text rubric file")
    parser.add_argument("--schema-file", help="Custom worker output schema")
    parser.add_argument("--out", required=True, help="Output workspace directory")
    parser.add_argument("--max-workers", type=int, default=3, help="Maximum worker packages to prepare")
    parser.add_argument("--toolsets", default="web", help="Recommended child toolsets, e.g. web or terminal,file")
    parser.add_argument("--policy", default="read-only", choices=["read-only", "isolated-write"], help="Worker safety policy")
    parser.add_argument("--copy-files", action="store_true", help="Copy assigned files into inputs_snapshot under --out")
    args = parser.parse_args(argv)

    out = Path(args.out).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    for dirname in ["worker_prompts", "workers", "logs", "artifacts"]:
        (out / dirname).mkdir(exist_ok=True)

    targets = split_items(args.targets) + read_list_file(args.targets_file)
    files = expand_file_patterns(args.files)
    file_resources = [resource_from_file(p) for p in files]
    resources = [parse_resource(r) for r in args.resource] + file_resources

    if args.copy_files and files:
        snap = out / "inputs_snapshot"
        snap.mkdir(exist_ok=True)
        copied_paths: list[Path] = []
        for src in files:
            dest = snap / src.name
            if dest.exists():
                dest = snap / f"{src.stem}-{sha256_file(src)[:8]}{src.suffix}"
            shutil.copy2(src, dest)
            copied_paths.append(dest)
        files = copied_paths
        file_resources = [resource_from_file(p) for p in files]
        resources = [parse_resource(r) for r in args.resource] + file_resources

    if not targets and not files and not resources:
        print("error: provide at least --targets, --targets-file, --files, or --resource", file=sys.stderr)
        return 2

    rubric = args.rubric or (
        Path(args.rubric_file).read_text(encoding="utf-8").strip() if args.rubric_file else
        "Cover the assigned slice thoroughly, cite evidence, label uncertainty, and stay within scope."
    )
    schema = choose_schema(args.task_type, args.schema_file)

    units = targets if targets else [str(p) for p in files]
    chunks = balanced_chunks(units, args.max_workers)
    packages = []
    for idx, chunk in enumerate(chunks, start=1):
        chunk_targets = chunk if targets else []
        chunk_files = [] if targets else chunk
        if targets and files:
            # Shared files/resources are listed for every worker when targets are primary.
            chunk_files = [str(p) for p in files]
        name = slugify("-".join(chunk[:2]))
        prompt_path = out / "worker_prompts" / f"{idx:02d}_{name}.md"
        output_path = out / "workers" / f"{idx:02d}_{name}.md"
        prompt = worker_prompt(
            project=args.project,
            task_type=args.task_type,
            worker_id=idx,
            targets=chunk_targets,
            file_paths=chunk_files,
            resources=resources,
            rubric=rubric,
            output_schema=schema,
            toolsets=args.toolsets,
            policy=args.policy,
        )
        prompt_path.write_text(prompt, encoding="utf-8")
        output_path.write_text(f"# Worker {idx}: {', '.join(chunk)}\n\n_Paste child output here._\n", encoding="utf-8")
        packages.append({
            "id": idx,
            "name": name,
            "targets": chunk_targets,
            "files": chunk_files,
            "prompt": str(prompt_path),
            "output": str(output_path),
            "toolsets": [t.strip() for t in args.toolsets.split(",") if t.strip()],
            "policy": args.policy,
        })

    manifest = {
        "project": args.project,
        "task_type": args.task_type,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "policy": args.policy,
        "max_workers": args.max_workers,
        "packages": packages,
        "resources": [dataclasses.asdict(r) for r in resources],
        "rubric": rubric,
        "output_schema": schema,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "resources.json").write_text(json.dumps(manifest["resources"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    synthesis = f"""# Synthesis prompt for {args.project}

Use the worker outputs in `workers/` to produce one integrated answer.

Required synthesis:
- answer the original request directly;
- compare findings across workers;
- resolve or label contradictions;
- cite strongest evidence;
- list gaps and uncertainty;
- recommend next sequential actions if any.

Do not paste child reports raw. Do not claim verification unless evidence was checked.
"""
    (out / "synthesis_prompt.md").write_text(synthesis, encoding="utf-8")

    verification = """# Verification checklist

- [ ] Every requested target/file/resource is covered or explicitly marked missing.
- [ ] Every worker stayed within its assigned slice.
- [ ] No external side effects were requested or performed.
- [ ] No shared final document or shared source file was edited by workers.
- [ ] High-impact claims have URLs, file paths/lines, command output, or explicit uncertainty.
- [ ] Contradictions are resolved or labeled.
- [ ] Final answer is synthesized, not a concatenation.
"""
    (out / "verification.md").write_text(verification, encoding="utf-8")

    readme = f"""# {args.project}

Generated by `parallel-orchestrator/scripts/orchestration.py`.

Start with:
1. Review `manifest.json`.
2. Dispatch `worker_prompts/*.md` via `delegate_task(tasks=[...])`.
3. Paste raw outputs into `workers/*.md` if the task is large.
4. Use `synthesis_prompt.md`.
5. Complete `verification.md` before final answer.
"""
    (out / "README.md").write_text(readme, encoding="utf-8")

    print(json.dumps({"success": True, "out": str(out), "workers": len(packages), "manifest": str(out / "manifest.json")}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
