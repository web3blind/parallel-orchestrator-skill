# Parallel Orchestrator Skill

A vendor-neutral Hermes Agent skill for safe parallel task decomposition and skill-level orchestration.

Use it when a request naturally splits into independent **read-only** subtasks: research, analytics, source/data discovery, comparing protocols/products/games, reviewing several PRs, checking multiple websites, auditing independent modules/files, or collecting information from several sources.

The skill teaches Hermes to:

- classify whether parallel execution is safe;
- split work by independent objects/sources/modules/options;
- create worker prompts and durable orchestration folders via a helper script;
- use `delegate_task(tasks=[...])` batch mode;
- keep child toolsets minimal and read-only;
- synthesize child results into one final answer/document;
- verify high-impact evidence before claiming it is verified;
- avoid automatic parallelization for shared writes or external side effects.

It is a practical workaround for research/audit/document tasks without rewriting Hermes core. It does **not** replace a full async runtime scheduler with persistent worker state, retries, cancellation, and streaming progress.

## Install

### Option 1: clone the full skill repo

Recommended if you want the helper script too:

```bash
mkdir -p ~/.hermes/skills
rm -rf ~/.hermes/skills/parallel-orchestrator
git clone https://github.com/web3blind/parallel-orchestrator-skill \
  ~/.hermes/skills/parallel-orchestrator
```

### Option 2: copy only SKILL.md

Good enough for instruction-only usage, but this does not install the script:

```bash
mkdir -p ~/.hermes/skills/parallel-orchestrator
curl -fsSL https://raw.githubusercontent.com/web3blind/parallel-orchestrator-skill/main/SKILL.md \
  -o ~/.hermes/skills/parallel-orchestrator/SKILL.md
```

### Option 3: copy SKILL.md plus script

```bash
mkdir -p ~/.hermes/skills/parallel-orchestrator/scripts
curl -fsSL https://raw.githubusercontent.com/web3blind/parallel-orchestrator-skill/main/SKILL.md \
  -o ~/.hermes/skills/parallel-orchestrator/SKILL.md
curl -fsSL https://raw.githubusercontent.com/web3blind/parallel-orchestrator-skill/main/scripts/parallel_orchestration_plan.py \
  -o ~/.hermes/skills/parallel-orchestrator/scripts/parallel_orchestration_plan.py
chmod +x ~/.hermes/skills/parallel-orchestrator/scripts/parallel_orchestration_plan.py
```

Then use it by asking Hermes to load the skill, for example:

```text
skill parallel-orchestrator compare governance across Ethereum, Solana, Cosmos, Polkadot, and Near
```

or, if your Hermes build supports text skill activation aliases:

```text
параллельно проверь эти 6 PR и скажи, какие готовы к merge
```

## Helper script

The bundled script prepares a durable orchestration folder with worker prompts, placeholders, a synthesis prompt, and a verification checklist. It does not call LLMs and does not change Hermes core.

Example:

```bash
python ~/.hermes/skills/parallel-orchestrator/scripts/parallel_orchestration_plan.py \
  --project "EA monetization research" \
  --task-type research \
  --targets "EA Sports FC|Apex Legends|The Sims 4|Madden NFL|Need for Speed" \
  --out ./parallel-orchestration/ea-monetization
```

Output structure:

```text
parallel-orchestration/ea-monetization/
├── plan.json
├── worker_prompts/
├── workers/
├── synthesis_prompt.md
└── verification.md
```

You can pass a custom rubric:

```bash
python ~/.hermes/skills/parallel-orchestrator/scripts/parallel_orchestration_plan.py \
  --project "EA monetization research" \
  --task-type research \
  --targets "EA Sports FC|Apex Legends|The Sims 4" \
  --rubric-file rubric.txt \
  --out ./parallel-orchestration/ea-monetization
```

## Example prompts

```text
parallel compare governance across Ethereum, Solana, Cosmos, Polkadot, and Near
```

```text
распараллель анализ этих документаций и собери общий вывод
```

```text
сделай research по монетизации 8 игр, распараллель сбор данных, потом собери общий документ
```

```text
быстрее: проверь три сайта на очевидные accessibility-проблемы
```

```text
проверь разные файлы проекта read-only и найди архитектурные риски, но ничего не меняй
```

## Safety model

Safe by default:

- read-only research;
- analytics and source/data discovery;
- read-only code/project audits;
- comparison and summarization;
- independent document/source analysis;
- final synthesis by one parent/writer after workers finish.

Not auto-parallelized:

- code edits touching shared files;
- multiple workers editing one final document;
- git commit/rebase/merge/push;
- deploys and migrations;
- blockchain transactions and trading;
- sending messages, emails, posts, comments, or PR comments;
- payments, purchases, credentials, or account changes.

For write/action tasks, use sequential execution or explicit isolation such as one git worktree per independent change.

## Files

- [`SKILL.md`](./SKILL.md) — the skill itself.
- [`scripts/parallel_orchestration_plan.py`](./scripts/parallel_orchestration_plan.py) — helper that creates `plan.json`, worker prompts, output placeholders, synthesis prompt, and verification checklist.

## License

MIT
