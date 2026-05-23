# Parallel Orchestrator Skill

A vendor-neutral Hermes Agent skill for safe parallel task decomposition.

Use it when a request naturally splits into independent **read-only** subtasks: comparing protocols, reviewing several PRs, checking multiple websites, auditing independent modules, or collecting information from several sources.

The skill teaches Hermes to:

- classify whether parallel execution is safe;
- split work by independent objects/sources/modules/options;
- use `delegate_task(tasks=[...])` batch mode;
- keep child toolsets minimal;
- synthesize child results into one final answer;
- avoid automatic parallelization for shared writes or external side effects.

## Install

### Option 1: copy into your local Hermes skills directory

```bash
mkdir -p ~/.hermes/skills/parallel-orchestrator
curl -fsSL https://raw.githubusercontent.com/web3blind/parallel-orchestrator-skill/main/SKILL.md \
  -o ~/.hermes/skills/parallel-orchestrator/SKILL.md
```

Then use it by asking Hermes to load the skill, for example:

```text
skill parallel-orchestrator compare governance across Ethereum, Solana, Cosmos, Polkadot, and Near
```

or, if your Hermes build supports text skill activation aliases:

```text
параллельно проверь эти 6 PR и скажи, какие готовы к merge
```

## Example prompts

```text
parallel compare governance across Ethereum, Solana, Cosmos, Polkadot, and Near
```

```text
распараллель анализ этих документаций и собери общий вывод
```

```text
быстрее: проверь три сайта на очевидные accessibility-проблемы
```

## Safety model

Safe by default:

- read-only research;
- read-only code review;
- comparison and summarization;
- independent document/source analysis.

Not auto-parallelized:

- code edits touching shared files;
- git commit/rebase/merge/push;
- deploys and migrations;
- blockchain transactions and trading;
- sending messages, emails, posts, comments, or PR comments;
- payments, purchases, credentials, or account changes.

For write/action tasks, use sequential execution or explicit isolation such as one git worktree per independent change.

## Files

- [`SKILL.md`](./SKILL.md) — the skill itself.

## License

MIT
