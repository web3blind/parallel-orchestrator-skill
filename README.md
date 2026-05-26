# Parallel Orchestrator Skill

A vendor-neutral Hermes Agent skill for safe parallel task decomposition and skill-level orchestration.

Use it when a request naturally splits into independent **read-only** subtasks: research, analytics, source/data discovery, comparing protocols/products/games, reviewing several PRs, checking multiple websites, auditing independent modules/files, or collecting information from several sources.

The skill teaches Hermes to:

- classify whether parallel execution is safe;
- enforce a decomposition contract: independent branches, dependencies, non-parallelizable parts, and distinct worker scopes;
- split work by independent objects/sources/modules/options;
- provision resources, local file assignments, worker prompts, output placeholders, synthesis prompts, and verification checklists with `scripts/orchestration.py` when a job is large enough;
- use `delegate_task(tasks=[...])` batch mode;
- keep child toolsets minimal and read-only;
- require worker evidence: claim → source/file/command → confidence → risk;
- synthesize child results into one conflict-aware final answer/document;
- verify high-impact evidence before claiming it is verified;
- handle worker failure with targeted retry or graceful degradation;
- avoid automatic parallelization for shared writes, sensitive data, or external side effects.

It is a practical quality orchestrator for research/audit/document tasks without rewriting Hermes core. It teaches Hermes to delegate without mush; it does **not** replace a full async runtime scheduler with persistent worker state, retries, cancellation, and streaming progress.

## Install

### Option 1: clone the full skill repo

Recommended if you want the orchestration helper too:

```bash
mkdir -p ~/.hermes/skills
rm -rf ~/.hermes/skills/parallel-orchestrator
git clone https://github.com/web3blind/parallel-orchestrator-skill   ~/.hermes/skills/parallel-orchestrator
```

### Option 2: copy only SKILL.md

Good for instruction-only usage, but this does not install `scripts/orchestration.py`:

```bash
mkdir -p ~/.hermes/skills/parallel-orchestrator
curl -fsSL https://raw.githubusercontent.com/web3blind/parallel-orchestrator-skill/main/SKILL.md   -o ~/.hermes/skills/parallel-orchestrator/SKILL.md
```

### Option 3: copy SKILL.md plus script

```bash
mkdir -p ~/.hermes/skills/parallel-orchestrator/scripts
curl -fsSL https://raw.githubusercontent.com/web3blind/parallel-orchestrator-skill/main/SKILL.md   -o ~/.hermes/skills/parallel-orchestrator/SKILL.md
curl -fsSL https://raw.githubusercontent.com/web3blind/parallel-orchestrator-skill/main/scripts/orchestration.py \
  -o ~/.hermes/skills/parallel-orchestrator/scripts/orchestration.py
chmod +x ~/.hermes/skills/parallel-orchestrator/scripts/orchestration.py
```

## Helper scripts

The bundled provisioning helper is:

```text
scripts/orchestration.py
```

It provisions a local orchestration workspace. It does not call LLMs and does not modify Hermes core.

The experimental runner is:

```text
scripts/orchestration_runner.py
```

It provisions the same workspace and then runs one of two modes:

- `smart` — current centralized Hermes flow: one parent `hermes chat` session uses the `parallel-orchestrator` skill and `delegate_task` batch mode, then synthesizes.
- `process` — experimental process-level fan-out: one independent `hermes chat` process per worker prompt runs concurrently, outputs are saved to `workers/*.md`, then a separate synthesis process creates `final_synthesis.md`.

The runner is still a test harness, not a Hermes core scheduler. It does not add live progress, durable workers, child-to-child communication, or UI-level cancellation. A separate `compare` mode is intentionally not shipped; use two runs plus `run_report.json` when manual comparison is needed.

`process` has two output styles:

- **Full report mode**: default. Workers run first, then a separate synthesis process writes `final_synthesis.md`. Use this for autonomous reports, benchmarks, scheduled jobs, or when the user wants a saved final artifact.
- **Raw workers mode**: add `--no-synthesis`. The runner stops after raw `workers/*.md` outputs and `run_report.json`; the current/main agent should then read the outputs and perform the final merge interactively in chat.

Mode selection policy:

- Use `smart` / normal `delegate_task` by default for ordinary research and smaller comparisons.
- Use `process` when the user explicitly wants full separate AIAgent processes, durable worker output files, stronger isolation, or avoiding a single `delegate_task` timeout.
- Add `--no-synthesis` when the user wants raw worker outputs only, or wants the current/main agent to do the final processing in the active chat instead of a separate reducer process.
- Do not assume `process` is always faster: it can be more reliable for long workers, but has extra process and synthesis overhead.

Generated workspace:

```text
parallel-orchestration/<project>/
├── manifest.json
├── resources.json
├── worker_prompts/
├── workers/
├── artifacts/
├── logs/
├── synthesis_prompt.md
├── verification.md
└── README.md
```

### Research example

```bash
python ~/.hermes/skills/parallel-orchestrator/scripts/orchestration.py \
  --project "EA monetization research" \
  --task-type research \
  --targets "EA Sports FC|Apex Legends|The Sims 4|Madden NFL|Need for Speed" \
  --resource "brief=note:focus on monetization loops and source quality" \
  --out ./parallel-orchestration/ea-monetization
```

### Local file audit example

```bash
python ~/.hermes/skills/parallel-orchestrator/scripts/orchestration.py \
  --project "Architecture read-only review" \
  --task-type audit \
  --files "src/**/*.py" \
  --files "tests/**/*.py" \
  --max-workers 3 \
  --toolsets terminal,file \
  --out ./parallel-orchestration/architecture-review
```

### Resource forms

`--resource` is repeatable and accepts:

```text
label=kind:value
kind:value
plain note text
```

Examples:

```bash
--resource "docs=url:https://example.com/docs"
--resource "repo=path:/workspace/project"
--resource "note:only use official docs and primary sources"
```

## How to use the skill

Example Hermes invocation:

```text
skill parallel-orchestrator compare governance across Ethereum, Solana, Cosmos, Polkadot, and Near
```

Natural-language triggers may also work when text skill aliases are enabled:

```text
параллельно проверь эти 6 PR и скажи, какие готовы к merge
```

## Safety summary

Safe default: independent read-only research, extraction, comparison, audit, review, and synthesis.

Do not auto-parallelize:

- shared writes;
- code edits touching the same files;
- git commit/push/merge/rebase;
- blockchain transactions/trading;
- deployments/migrations/DNS;
- sending messages/posts/comments;
- purchases/payments/account changes.

## Repository contents

- `SKILL.md` — Hermes skill instructions.
- `scripts/orchestration.py` — general workspace provisioner for resources, files, worker prompts, outputs, synthesis, and verification.
- `scripts/orchestration_runner.py` — experimental runner with `smart` and `process` modes for testing centralized vs process-level fan-out.
- `LICENSE` — MIT.
