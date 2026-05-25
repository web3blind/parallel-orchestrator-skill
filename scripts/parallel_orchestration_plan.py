#!/usr/bin/env python3
"""Prepare a durable parallel orchestration folder for read-only research/audit tasks.

This helper is intentionally skill-level glue: it does not call LLMs and does not
change Hermes core. It creates worker prompts, placeholder output files,
plan.json, synthesis prompt, and verification checklist for the parent agent.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from pathlib import Path


def slugify(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9а-яё]+", "_", text, flags=re.I)
    text = re.sub(r"_+", "_", text).strip("_")
    return text[:48] or "target"


def read_text(path: str | None, default: str = "") -> str:
    if not path:
        return default
    return Path(path).expanduser().read_text(encoding="utf-8")


def worker_prompt(project: str, target: str, task_type: str, rubric: str, source_policy: str, output_schema: str) -> str:
    return f"""You are a specialist worker in a parallel Hermes orchestration run.

Research/audit ONLY this target: {target}
Task type: {task_type}
Parent project: {project}

Rubric:
{rubric.strip()}

Source / evidence policy:
{source_policy.strip()}

Output format:
{output_schema.strip()}

Constraints:
- Do not work on other targets except for brief comparison when necessary.
- Do not edit shared files, git state, deployed services, wallets, or external side effects.
- Do not invent sources, file findings, or citations.
- Include URLs, file paths/line numbers, or command evidence for important claims.
- Mark uncertainty, dated information, weak evidence, and gaps explicitly.
- Return concise but complete Markdown.
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare a parallel orchestration folder")
    parser.add_argument("--project", required=True, help="Project title/goal")
    parser.add_argument("--targets", required=True, help="Targets separated by |")
    parser.add_argument("--task-type", default="research", help="research, audit, comparison, file-inspection, etc.")
    parser.add_argument("--rubric-file", help="File containing the common rubric")
    parser.add_argument("--source-policy-file", help="Optional source/evidence policy file")
    parser.add_argument("--output-schema-file", help="Optional output schema file")
    parser.add_argument("--out", required=True, help="Output directory")
    args = parser.parse_args()

    targets = [t.strip() for t in args.targets.split("|") if t.strip()]
    if not targets:
        raise SystemExit("No targets supplied")

    default_rubric = """
1. Executive summary for this target
2. Key facts / observations
3. Evidence and citations
4. Risks, edge cases, or uncertainty
5. Practical implications
6. Reusable patterns or recommendations
7. Gaps that need parent follow-up
""".strip()

    default_source_policy = """
- Prefer primary sources, official docs/pages, reputable analysis, reviews, forums, dated community evidence, or direct file/command evidence depending on task type.
- Include URLs, file paths/line numbers, or command output references for important claims.
- Separate facts from interpretation.
- Mark weak, outdated, or unverifiable evidence.
""".strip()

    default_output_schema = """
1. Executive summary
2. Findings by rubric section
3. Evidence list: URLs / file paths / command references
4. Confidence notes and gaps
5. Parent follow-up suggestions
""".strip()

    rubric = read_text(args.rubric_file, default_rubric)
    source_policy = read_text(args.source_policy_file, default_source_policy)
    output_schema = read_text(args.output_schema_file, default_output_schema)

    out = Path(args.out).expanduser().resolve()
    workers_dir = out / "workers"
    prompts_dir = out / "worker_prompts"
    workers_dir.mkdir(parents=True, exist_ok=True)
    prompts_dir.mkdir(parents=True, exist_ok=True)

    now = dt.datetime.now(dt.timezone.utc).isoformat()
    packages = []
    seen = set()
    for index, target in enumerate(targets, 1):
        base = slugify(target)
        slug = base
        n = 2
        while slug in seen:
            slug = f"{base}_{n}"
            n += 1
        seen.add(slug)
        prompt_path = prompts_dir / f"{index:02d}_{slug}.md"
        output_path = workers_dir / f"{index:02d}_{slug}.md"
        prompt_path.write_text(worker_prompt(args.project, target, args.task_type, rubric, source_policy, output_schema), encoding="utf-8")
        output_path.write_text(f"# {target}\n\n_Status: pending_\n", encoding="utf-8")
        packages.append({
            "id": slug,
            "target": target,
            "task_type": args.task_type,
            "prompt_file": str(prompt_path),
            "output_file": str(output_path),
            "status": "pending",
        })

    plan = {
        "project": args.project,
        "task_type": args.task_type,
        "created_at": now,
        "targets": targets,
        "packages": packages,
        "rubric": rubric,
        "source_policy": source_policy,
        "output_schema": output_schema,
        "safety_contract": [
            "Only parallelize read-only or isolated work packages.",
            "Do not let multiple workers edit the same final document or shared code state.",
            "Worker outputs are leads; parent verifies high-impact claims before final synthesis.",
        ],
    }
    (out / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    synthesis = f"""# Synthesis Prompt: {args.project}

Synthesize the worker reports from `workers/` into one professional final artifact.

Goals:
- Cover every target and every rubric item.
- Preserve citations, file evidence, and uncertainty notes.
- Add cross-target patterns and differences.
- Do not invent facts beyond worker outputs or parent-verified evidence.
- Use tables only where they improve clarity.

Recommended sections:
1. Executive summary
2. Methodology and source/evidence quality
3. Per-target analysis
4. Cross-target comparison
5. Reusable principles / recommendations
6. Risks, caveats, and what not to copy
7. Follow-up hypotheses / next steps
8. Evidence appendix
"""
    (out / "synthesis_prompt.md").write_text(synthesis, encoding="utf-8")

    checklist = """# Verification Checklist

- [ ] Every target has a worker output.
- [ ] Every requested rubric section is covered.
- [ ] Important claims have URLs, file paths/lines, command evidence, or are marked uncertain.
- [ ] Parent spot-checked strongest and weakest worker outputs.
- [ ] Conflicts between sources/workers are noted, not hidden.
- [ ] Final synthesis distinguishes facts, analysis, and hypotheses.
- [ ] Final document has methodology, limitations, and evidence appendix.
- [ ] No claim says “verified” unless the parent actually verified it.
"""
    (out / "verification.md").write_text(checklist, encoding="utf-8")

    print(json.dumps({"success": True, "out": str(out), "workers": len(packages), "plan": str(out / "plan.json")}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
