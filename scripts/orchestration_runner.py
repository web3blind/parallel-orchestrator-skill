#!/usr/bin/env python3
"""Experimental Hermes orchestration runner.

This script lives next to ``orchestration.py`` but intentionally does not replace it.
It provisions the same durable workspace, then can run it in two modes:

- ``smart``: current centralized Hermes style. One parent ``hermes chat -q`` session
  loads the parallel-orchestrator skill and is instructed to use delegate_task.
- ``process``: experimental process-level fan-out. One independent ``hermes chat -q``
  process is launched per worker prompt concurrently; outputs are written to
  workers/*.md, then a separate synthesizer process creates final_synthesis.md.

The process mode is meant to test whether multiple full AIAgent processes are a
better fit than synchronous delegate_task for broad read-only research. It is not
Hermes core and it does not provide durable worker scheduling, live Telegram
progress, cancellation UI, or child-to-child collaboration.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
PROVISIONER = SCRIPT_DIR / "orchestration.py"


@dataclass
class RunResult:
    role: str
    worker_id: int | None
    command: list[str]
    output_path: str
    status: str
    started_at: float
    finished_at: float
    duration_seconds: float
    returncode: int | None
    timed_out: bool
    error: str | None = None


def now() -> float:
    return time.time()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def shell_join(command: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in command)


def run_command_to_file(command: list[str], output_path: Path, timeout: int, env: dict[str, str]) -> RunResult:
    started = now()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        completed = subprocess.run(
            command,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            env=env,
        )
        finished = now()
        output = completed.stdout or ""
        output_path.write_text(output, encoding="utf-8")
        return RunResult(
            role="worker",
            worker_id=None,
            command=command,
            output_path=str(output_path),
            status="completed" if completed.returncode == 0 else "failed",
            started_at=started,
            finished_at=finished,
            duration_seconds=finished - started,
            returncode=completed.returncode,
            timed_out=False,
            error=None if completed.returncode == 0 else f"exit code {completed.returncode}",
        )
    except subprocess.TimeoutExpired as exc:
        finished = now()
        partial = exc.stdout or ""
        if isinstance(partial, bytes):
            partial = partial.decode("utf-8", errors="replace")
        output_path.write_text(
            partial + f"\n\n[TIMEOUT after {timeout} seconds]\n",
            encoding="utf-8",
        )
        return RunResult(
            role="worker",
            worker_id=None,
            command=command,
            output_path=str(output_path),
            status="timeout",
            started_at=started,
            finished_at=finished,
            duration_seconds=finished - started,
            returncode=None,
            timed_out=True,
            error=f"timeout after {timeout}s",
        )
    except Exception as exc:  # noqa: BLE001 - report experiment errors in JSON
        finished = now()
        output_path.write_text(f"[ERROR] {type(exc).__name__}: {exc}\n", encoding="utf-8")
        return RunResult(
            role="worker",
            worker_id=None,
            command=command,
            output_path=str(output_path),
            status="error",
            started_at=started,
            finished_at=finished,
            duration_seconds=finished - started,
            returncode=None,
            timed_out=False,
            error=f"{type(exc).__name__}: {exc}",
        )


def provision(args: argparse.Namespace) -> dict[str, Any]:
    cmd = [
        sys.executable,
        str(PROVISIONER),
        "--project",
        args.project,
        "--task-type",
        args.task_type,
        "--out",
        args.out,
        "--max-workers",
        str(args.max_workers),
        "--toolsets",
        args.toolsets,
        "--policy",
        args.policy,
    ]
    if args.targets:
        cmd.extend(["--targets", args.targets])
    if args.targets_file:
        cmd.extend(["--targets-file", args.targets_file])
    for pattern in args.files:
        cmd.extend(["--files", pattern])
    for resource in args.resource:
        cmd.extend(["--resource", resource])
    if args.rubric:
        cmd.extend(["--rubric", args.rubric])
    if args.rubric_file:
        cmd.extend(["--rubric-file", args.rubric_file])
    if args.schema_file:
        cmd.extend(["--schema-file", args.schema_file])
    if args.copy_files:
        cmd.append("--copy-files")

    completed = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    if completed.returncode != 0:
        raise SystemExit(completed.stdout)
    return json.loads(completed.stdout)


def hermes_base_command(args: argparse.Namespace) -> list[str]:
    cmd = [args.hermes_bin, "chat"]
    if args.model:
        cmd.extend(["--model", args.model])
    if args.provider:
        cmd.extend(["--provider", args.provider])
    if args.skills:
        cmd.extend(["--skills", args.skills])
    if args.max_turns:
        cmd.extend(["--max-turns", str(args.max_turns)])
    if args.yolo:
        cmd.append("--yolo")
    cmd.extend(["--source", "parallel-orchestrator-runner"])
    cmd.append("-Q")
    return cmd


def append_query(command: list[str], query: str) -> list[str]:
    # argparse expects the argument immediately after -q/--query; keep this last
    # so optional flags are not accidentally consumed as the query string.
    return command + ["-q", query]


def worker_command(args: argparse.Namespace, prompt_path: Path) -> list[str]:
    prompt = prompt_path.read_text(encoding="utf-8")
    query = (
        prompt
        + "\n\nRun this worker task now. Use only the allowed/read-only tools. "
        + "Stay inside your assigned slice; do not solve the other workers' scopes. "
        + "For every substantive claim, include evidence (URL, file path/line, command output, dataset row) or label it as hypothesis/low-confidence. "
        + "Return a concise but evidence-grounded result in the requested schema, including risks, conflicts, and gaps."
    )
    cmd = hermes_base_command(args)
    if args.toolsets:
        cmd.extend(["--toolsets", args.toolsets])
    return append_query(cmd, query)


def synthesis_command(args: argparse.Namespace, out: Path, manifest: dict[str, Any]) -> list[str]:
    worker_outputs: list[str] = []
    for package in manifest["packages"]:
        path = Path(package["output"])
        try:
            content = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            content = "[missing output]"
        worker_outputs.append(f"## Worker {package['id']}: {package['name']}\n\n{content}")

    synthesis_prompt = (out / "synthesis_prompt.md").read_text(encoding="utf-8")
    verification = (out / "verification.md").read_text(encoding="utf-8")
    query = f"""You are the reducer/synthesizer for an experimental Hermes process-level parallel run.

Original project: {manifest['project']}
Task type: {manifest['task_type']}
Policy: {manifest['policy']}

{synthesis_prompt}

Verification checklist to apply:
{verification}

Worker outputs are embedded below. Do not try to read a relative `workers/` directory; use the embedded outputs as the evidence packet. The absolute workspace path is: {out}

Worker outputs:
{chr(10).join(worker_outputs)}

Produce the final answer in Russian. Apply the merge protocol: map findings to the rubric, deduplicate overlaps, compare evidence quality, label contradictions as `conflict`, name missing/failed/timeouted workers, and do not claim verification beyond the supplied evidence.
"""
    cmd = hermes_base_command(args)
    cmd.extend(["--toolsets", "file"])
    return append_query(cmd, query)


def smart_command(args: argparse.Namespace, out: Path, manifest: dict[str, Any]) -> list[str]:
    prompt_paths = [Path(package["prompt"]) for package in manifest["packages"]]
    prompts = []
    for path in prompt_paths:
        prompts.append(f"## {path.name}\n\n{path.read_text(encoding='utf-8')}")
    query = f"""Use the loaded parallel-orchestrator skill to run this task in the current centralized Hermes style.

Project: {manifest['project']}
Workspace: {out}

Dispatch these worker prompts via delegate_task batch mode when safe, then synthesize one final Russian answer. Before dispatch, apply the decomposition contract: name independent slices, dependencies, non-parallelizable parts, and why workers are distinct. If a worker fails, returns empty output, or drifts, retry only that slice once if practical; otherwise label the gap and continue with available evidence. In the final merge, deduplicate overlaps, compare evidence quality, label contradictions as `conflict`, and exclude unsupported claims or mark them low-confidence.

Worker prompts:
{chr(10).join(prompts)}
"""
    cmd = hermes_base_command(args)
    if not args.skills:
        cmd.extend(["--skills", "parallel-orchestrator"])
    # Parent needs delegation plus whatever worker toolsets imply.
    parent_toolsets = sorted(set(["delegation", "file"] + [t.strip() for t in args.toolsets.split(",") if t.strip()]))
    cmd.extend(["--toolsets", ",".join(parent_toolsets)])
    return append_query(cmd, query)


def run_process_mode(args: argparse.Namespace, out: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    env = os.environ.copy()
    worker_results: list[RunResult] = []
    start = now()

    if args.dry_run:
        commands = []
        for package in manifest["packages"]:
            commands.append({
                "worker_id": package["id"],
                "command": shell_join(worker_command(args, Path(package["prompt"]))),
                "output": package["output"],
            })
        synth_cmd = None if args.no_synthesis else shell_join(synthesis_command(args, out, manifest))
        return {"mode": "process", "dry_run": True, "commands": commands, "synthesis_command": synth_cmd}

    with ThreadPoolExecutor(max_workers=min(args.max_workers, len(manifest["packages"]))) as executor:
        futures = {}
        for package in manifest["packages"]:
            cmd = worker_command(args, Path(package["prompt"]))
            output_path = Path(package["output"])
            future = executor.submit(run_command_to_file, cmd, output_path, args.worker_timeout, env)
            futures[future] = package["id"]
        for future in as_completed(futures):
            result = future.result()
            result.worker_id = futures[future]
            worker_results.append(result)

    synthesis_result: RunResult | None = None
    if not args.no_synthesis:
        synth_cmd = synthesis_command(args, out, manifest)
        synth_path = out / "final_synthesis.md"
        synthesis_result = run_command_to_file(synth_cmd, synth_path, args.synthesis_timeout, env)
        synthesis_result.role = "synthesis"

    finish = now()
    return {
        "mode": "process",
        "dry_run": False,
        "started_at": start,
        "finished_at": finish,
        "duration_seconds": finish - start,
        "workers": [asdict(r) for r in sorted(worker_results, key=lambda r: r.worker_id or 0)],
        "synthesis": asdict(synthesis_result) if synthesis_result else None,
    }


def run_smart_mode(args: argparse.Namespace, out: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    cmd = smart_command(args, out, manifest)
    if args.dry_run:
        return {"mode": "smart", "dry_run": True, "command": shell_join(cmd), "output": str(out / "smart_final.md")}
    result = run_command_to_file(cmd, out / "smart_final.md", args.smart_timeout, os.environ.copy())
    result.role = "smart-parent"
    return {"mode": "smart", "dry_run": False, "result": asdict(result)}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run experimental Hermes orchestration modes")
    parser.add_argument("--mode", choices=["smart", "process"], required=True, help="smart=current centralized delegate flow; process=spawn independent Hermes workers")
    parser.add_argument("--project", required=True)
    parser.add_argument("--task-type", default="research")
    parser.add_argument("--targets")
    parser.add_argument("--targets-file")
    parser.add_argument("--files", action="append", default=[])
    parser.add_argument("--resource", action="append", default=[])
    parser.add_argument("--rubric")
    parser.add_argument("--rubric-file")
    parser.add_argument("--schema-file")
    parser.add_argument("--out", required=True)
    parser.add_argument("--max-workers", type=int, default=3)
    parser.add_argument("--toolsets", default="web")
    parser.add_argument("--policy", default="read-only", choices=["read-only", "isolated-write"])
    parser.add_argument("--copy-files", action="store_true")

    parser.add_argument("--hermes-bin", default="hermes")
    parser.add_argument("--model")
    parser.add_argument("--provider")
    parser.add_argument("--skills", default="", help="Comma-separated skills for worker processes")
    parser.add_argument("--max-turns", type=int, default=20)
    parser.add_argument("--worker-timeout", type=int, default=900)
    parser.add_argument("--synthesis-timeout", type=int, default=900)
    parser.add_argument("--smart-timeout", type=int, default=1200)
    parser.add_argument("--no-synthesis", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--yolo", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.mode == "process" and args.max_workers < 1:
        raise SystemExit("--max-workers must be >= 1")

    provision_result = provision(args)
    out = Path(provision_result["out"])
    manifest = load_json(out / "manifest.json")

    if args.mode == "process":
        run_report = run_process_mode(args, out, manifest)
    else:
        run_report = run_smart_mode(args, out, manifest)

    report = {
        "success": True,
        "workspace": str(out),
        "manifest": str(out / "manifest.json"),
        "provision": provision_result,
        "run": run_report,
    }
    write_json(out / "run_report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
