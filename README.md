# Parallel Orchestrator Skill

A vendor-neutral Hermes Agent skill for safe parallel task decomposition and skill-level orchestration.

Use it when a request naturally splits into independent **read-only** subtasks: research, analytics, source/data discovery, comparing protocols/products/games, reviewing several PRs, checking multiple websites, auditing independent modules/files, or collecting information from several sources.

The skill teaches Hermes to:

- classify whether parallel execution is safe;
- split work by independent objects/sources/modules/options;
- prepare self-contained worker prompts and optional durable notes/output folders when needed;
- use `delegate_task(tasks=[...])` batch mode;
- keep child toolsets minimal and read-only;
- synthesize child results into one final answer/document;
- verify high-impact evidence before claiming it is verified;
- avoid automatic parallelization for shared writes or external side effects.

It is a practical workaround for research/audit/document tasks without rewriting Hermes core. It does **not** replace a full async runtime scheduler with persistent worker state, retries, cancellation, and streaming progress.

## Install

### Option 1: clone the full skill repo

Recommended:

```bash
mkdir -p ~/.hermes/skills
rm -rf ~/.hermes/skills/parallel-orchestrator
git clone https://github.com/web3blind/parallel-orchestrator-skill \
  ~/.hermes/skills/parallel-orchestrator
```

### Option 2: copy only SKILL.md

Good for copying only the skill file:

```bash
mkdir -p ~/.hermes/skills/parallel-orchestrator
curl -fsSL https://raw.githubusercontent.com/web3blind/parallel-orchestrator-skill/main/SKILL.md \
  -o ~/.hermes/skills/parallel-orchestrator/SKILL.md
```


