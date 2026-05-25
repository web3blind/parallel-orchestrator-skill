---
name: parallel-orchestrator
description: "Use when a task contains multiple independent read-only research, analytics, data discovery, audit, review, or comparison subtasks that can be safely delegated in parallel; decompose, prepare worker prompts/artifacts, fan out, synthesize, and verify key evidence."
version: 1.3.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
aliases:
  - parallel
  - fanout
  - fan-out
  - parallelize
  - orchestrate
  - параллельно
  - распараллель
  - распараллелить
  - оркестратор
metadata:
  hermes:
    tags: [Delegation, Parallel, Orchestration, Research, Analytics, Audit, Review, Fan-Out]
    related_skills: [hermes-agent, subagent-driven-development]
---

# Parallel Orchestrator

## Overview

Use this skill to speed up broad tasks that naturally split into independent read-only parts. It is a **skill-level orchestration layer**, not a Hermes core rewrite.

The practical pipeline:

1. Classify whether parallelization is safe.
2. Decompose independent research/analytics/audit slices.
3. For large jobs, provision a durable workspace with `scripts/orchestration.py`: resources, assigned files, worker prompts, output placeholders, synthesis prompt, and verification checklist.
4. Run workers via `delegate_task(tasks=[...])` batch mode or separate durable Hermes processes when needed.
5. Save or inspect raw worker outputs when the task is large enough to need artifacts.
6. Synthesize child results into one final answer/document.
7. Verify high-impact evidence before saying the result is verified.

The goal is lower wall-clock time and better coverage for research-like work, not uncontrolled agent swarms. Parallelism is useful when each child can work without mutating the same files, touching shared state, or performing external side effects.

Hermes already supports parallel subagents through `delegate_task` batch mode. This skill teaches when to use that capability and includes a general-purpose `scripts/orchestration.py` helper for provisioning resources, files, worker prompts, output placeholders, synthesis, and verification artifacts. For experiments that need several full Hermes/AIAgent processes instead of one centralized parent call, use `scripts/orchestration_runner.py --mode process`; treat it as a test harness, not a core scheduler.

The primary value of this skill is **delegating without mush**: clear decomposition, evidence discipline, conflict-aware merge, failure handling, privacy boundaries, and explicit stop conditions. It is a quality orchestrator first and a parallel launcher second.

## When to Use

Use this skill when the user asks for a broad task with multiple independent objects, sources, repos, PRs, products, chains, files, documents, or approaches.

Strong triggers:

- Researching 5–10 games, products, companies, protocols, papers, markets, competitors, or tools.
- Analytics across independent sources or datasets.
- Data/source discovery where each source cluster can be handled separately.
- Auditing several independent projects, websites, documents, repos, PRs, or files.
- Comparing several protocols, blockchains, apps, monetization models, or design options.
- Reviewing independent modules read-only.
- Producing a long report where research can fan out but final writing should be centralized.
- “Make this faster if it can be done in parallel.”

Example prompts:

```text
Analyze monetization mechanics in 5-10 Electronic Arts games and produce a professional game-design deconstruction.
```

```text
Распараллель анализ этих документаций и собери общий вывод.
```

```text
Проверь разные файлы проекта read-only и найди архитектурные риски, но ничего не меняй.
```

Do **not** use this skill for:

- A single sequential debugging chain where each step depends on the previous result.
- Code edits that touch the same files in parallel.
- One shared final document edited by several children at once.
- Git operations such as rebase, merge, commit, push, or release unless each worker has an isolated worktree and the user explicitly wants that pattern.
- Wallet, trading, blockchain transaction, deploy, email/post/send-message, database migration, or payment actions.
- Tasks requiring live user decisions inside each child. Children cannot ask the user; prompts must be self-contained.
- Long missions that must survive parent interruption, unless using spawned durable processes instead of synchronous `delegate_task`.

## Safety Contract

### Safe by Default: Read-Only Fan-Out

You may auto-parallelize when all of these are true:

- Subtasks are independent.
- The work is read-only: research, analysis, review, extraction, comparison, summarization, classification, source discovery, or audit findings.
- Children do not need credentials beyond normal read access already available to the parent.
- Children do not write files except their own isolated notes/output artifacts when explicitly instructed.
- Children do not commit, push, deploy, post, trade, send messages, submit forms, or mutate external systems.
- The parent can synthesize results after all children complete.

### Ask or Stay Sequential: Shared Writes

Do not parallelize automatically if children may write to the same repo, directory, file, database, browser profile, config, service, or final document.

For code-changing work, prefer one of these safer patterns:

1. Sequential execution in the parent.
2. One child implements a narrow task, then parent verifies.
3. Isolated git worktrees, one per independent change, with explicit user approval.
4. Read-only parallel review first, then sequential implementation.

### Hard Stop: External Side Effects

Never auto-parallelize external side effects:

- Blockchain transactions or wallet signing.
- Trading, swaps, withdrawals, limit orders, farming actions.
- Deployments, migrations, DNS changes, production config changes.
- Sending email, Telegram/Discord/Slack messages, posts, comments, reviews, or PR comments.
- Purchases, payments, account changes, API key creation, credential rotation.

If side effects are required, ask for explicit scope and run the actions sequentially unless the user has approved a safe isolated plan.

## What This Skill Can and Cannot Solve

This skill can improve Hermes behavior on research/analytics/audit/document tasks without changing Hermes core:

- Better decomposition.
- Parallel worker prompts.
- More systematic raw outputs.
- Explicit synthesis/reducer pass.
- Evidence and coverage verification.
- Script-provisioned resources, file assignments, worker prompts, output placeholders, synthesis prompts, and verification checklists when the parent explicitly needs artifacts.

It does **not** turn Hermes into a full async distributed scheduler. It does not add core-level persistent worker state, cancellation, retries, streaming progress, dependency management, or automatic merge conflict handling. If the task needs those guarantees, use background processes, cron, external orchestration, or core changes.

## Delegate Task Limitations

`delegate_task` is fast, but it is not durable infrastructure.

- Do not use synchronous `delegate_task` for durable or long-running work that must survive interruption. Child work is cancelled if the parent turn is interrupted. Use cron jobs, background terminal processes, or spawned `hermes chat -q` runs for durable work.
- Children cannot clarify with the user. If a child would need a user decision, keep that decision in the parent before delegation or do not delegate that slice.
- Subagent results are leads, not verified facts. For high-impact claims, the parent must verify key evidence directly: source URL, file path/line, command output, PR status, or API response. Do not report “verified” unless the parent checked it or the child returned concrete evidence that can be inspected.
- Subagents are isolated from the parent context. Put all required assumptions, constraints, paths, source preferences, output schema, and forbidden actions into each child prompt.

## Quality Contracts

These contracts are mandatory when using this skill. They prevent the common failure mode where several agents do overlapping work and the parent pastes a messy aggregate.

### 1. Decomposition Contract

Before launching workers, explicitly decide:

- independent branches: which slices can run without waiting for each other;
- dependencies: which questions must be answered sequentially or by the parent before fan-out;
- non-parallelizable parts: shared state, shared files, one final document, credentials, production actions, or a single reasoning chain;
- split axis: object/source/module/option/persona;
- worker uniqueness: why each worker's scope is distinct.

Anti-pattern: “3 agents answer the same full question in different words.” Use redundant agents only for an explicit red-team/steelman design, and label it as such.

### 2. Evidence Contract

Every worker must return findings in this shape:

```text
Claim / finding:
Evidence: URL, file path + line, command output, dataset row, or explicit source note
Confidence: high / medium / low
Risk / caveat:
```

A finding without evidence must be treated as a hypothesis. Do not include unsupported claims in the final answer as facts; either exclude them or label them as unverified/low-confidence.

### 3. Merge Protocol

The parent/reducer must not merely summarize. It must:

- map every worker result back to the original question and rubric;
- deduplicate overlapping findings;
- compare evidence quality across branches;
- detect contradictions and label them as `conflict` instead of choosing the prettier answer;
- state which branch, if any, failed or produced weak evidence;
- produce one integrated answer with practical implications.

### 4. Failure Modes

If a worker times out, fails, returns empty output, or drifts off-scope:

1. Retry only that slice once with a narrower prompt when time/budget allows.
2. If retry is not available or fails again, degrade gracefully: synthesize from completed slices and explicitly mark the missing slice.
3. Never hide a failed branch. The final answer must mention the missing/failed scope if it affects coverage.
4. Do not rerun all workers when only one slice failed.

### 5. Privacy / Blast Radius

Before delegation, minimize what each worker receives. Do not send subagents:

- secrets, API keys, private keys, wallet seeds, auth tokens, cookies, or `.env` contents;
- private chat history unrelated to the assigned slice;
- client/customer data unless explicitly required and approved;
- production infrastructure credentials or privileged commands;
- broader repository or file access than needed for the slice.

If a task requires sensitive data, keep it in the parent and delegate only sanitized summaries or narrow read-only artifacts.

### 6. Task Shapes

Use these standard shapes before inventing a new one:

1. **Research fan-out** — split by product/protocol/source cluster; workers return claims with sources; parent normalizes and recommends.
2. **Codebase inspection** — split by module/subsystem; workers inspect read-only; parent ranks risks and avoids parallel edits.
3. **PR review / triage** — split by PR/repo; workers report CI, scope, mergeability, risks, and evidence; parent prioritizes action.
4. **Strategy red-team / steelman / synthesis** — one worker argues for, one against, one finds constraints/evidence; parent resolves trade-offs. This is the only normal shape where deliberate overlap is allowed.

### 7. Stop Condition

Do not parallelize when:

- the task is small enough that delegation overhead dominates;
- the answer needs one continuous chain of reasoning;
- subtasks share mutable state or the same files;
- workers would need to coordinate live decisions;
- evidence cannot be scoped safely;
- side effects are required;
- user privacy would require copying broad sensitive context into children.

## Decomposition Rules

### Good Split Axes

Split by independent object:

- Game/product/company/protocol/project/paper/market.
- Repo/PR/issue.
- Website/docs/source cluster.
- File/module/page/component, if read-only.
- Source category: official docs, GitHub, forum, news, social, reviews.
- Design option or hypothesis.

### Bad Split Axes

Avoid splits that require children to coordinate shared assumptions:

- “One child edits tests, one edits implementation” in the same files.
- “One child decides architecture, another implements before architecture is settled.”
- “One child updates package lock, another changes dependencies.”
- “Several children scrape/write the same output file.”
- “Several children drive the same browser/login session.”
- “Several children edit one Google Doc at the same time.”

### Chunking More Than the Concurrency Limit

`delegate_task` has a configurable child limit (`delegation.max_concurrent_children`, commonly 3). If there are more objects than the limit:

- Group related objects into balanced bundles.
- Run multiple waves only if the task is still worth it.
- Prefer 2–3 strong subagents over 8 tiny fragmented ones.

Example grouping for 8 games with max 3 children:

- Child 1: sports/live-service games.
- Child 2: shooters/action games.
- Child 3: life-sim/mobile/casual games.

## Execution Pattern

### Step 1 — Classify

Before delegating, classify internally:

- `parallelizable`: yes/no
- `risk`: read-only / isolated-write / shared-write / external-side-effect
- `split_axis`: object/source/module/option/etc.
- `max_children`: from config/tool limit, default 3 unless known otherwise
- `synthesis_goal`: what the final answer must decide or explain
- `artifact_need`: none / raw notes / report / Google Doc / spreadsheet

If `risk` is not read-only or explicitly isolated, do not auto-parallelize.

### Step 2 — Build Self-Contained Child Tasks

Each child must receive enough context to work without reading the parent conversation.

A child prompt should include:

- The specific object(s) assigned to the child.
- The original user question.
- Exact rubric.
- Exact output schema.
- Read-only constraint.
- Source/evidence preferences.
- What not to do.
- Whether the output is a lead or verified evidence.

Do not tell every child to solve the full task. Give each child a bounded slice.

### Step 3 — Provision Worker Prompts, Resources, and Optional Artifacts

For small tasks, build the `delegate_task(tasks=[...])` payload directly in the parent turn.

For larger research/audit/report tasks, use the bundled general helper instead of ad-hoc prompt writing:

```bash
python scripts/orchestration.py \
  --project "EA monetization research" \
  --task-type research \
  --targets "EA Sports FC|Apex Legends|The Sims 4|Madden NFL|Need for Speed" \
  --resource "brief=note:focus on monetization loops and accessibility of evidence" \
  --out ./parallel-orchestration/ea-monetization
```

For local-file audits, assign files/resources explicitly:

```bash
python scripts/orchestration.py \
  --project "Architecture read-only review" \
  --task-type audit \
  --files "src/**/*.py" \
  --files "tests/**/*.py" \
  --max-workers 3 \
  --toolsets terminal,file \
  --out ./parallel-orchestration/architecture-review
```

It creates:

```text
parallel-orchestration/<project>/
├── manifest.json        # packages, resources, policy, schema
├── resources.json       # file/resource inventory with hashes where possible
├── worker_prompts/      # one self-contained prompt per worker
├── workers/             # raw child output placeholders
├── artifacts/           # parent-owned artifacts only
├── logs/                # optional run notes
├── synthesis_prompt.md  # reducer instructions for the parent/final writer
├── verification.md      # coverage/evidence checklist
└── README.md
```

The helper does not call LLMs and does not change Hermes core. It provisions the orchestration workspace so the parent can dispatch workers consistently. Default policy is read-only; the script writes only under `--out` unless `--copy-files` is explicitly used to snapshot inputs into the workspace.

Use this helper when the task needs any of these:

- several targets or files that must be distributed across workers;
- durable prompts/output placeholders;
- resource inventory;
- repeatable synthesis and verification gates;
- evidence tracking for a long report.

### Optional Experiment — Spawn Full Hermes Processes

When you specifically want to compare the normal centralized flow with independent full Hermes/AIAgent worker processes, use the experimental runner:

```bash
python scripts/orchestration_runner.py \
  --mode process \
  --project "VPN protocols and clients comparison" \
  --task-type research \
  --targets "Protocols|Clients|GitHub trends" \
  --toolsets web \
  --out ./parallel-orchestration/vpn-process-test
```

Modes:

- `smart` provisions the workspace and asks one parent `hermes chat` session to use this skill plus `delegate_task` batch mode.
- `process` launches one separate `hermes chat` process per worker prompt, writes outputs to `workers/*.md`, then runs a separate synthesis process.

Mode selection policy:

- Default to normal in-agent `delegate_task` / `smart` behavior for ordinary research, small comparisons, and cases where the user wants one clean answer with minimal overhead.
- Use `process` when the user explicitly asks for full separate AIAgent processes, stronger isolation, durable worker outputs, avoiding a single `delegate_task` timeout, or phrases such as "запусти отдельными процессами", "process mode", "не через одного босса", "чтобы довело до конца без таймаута", or "скопировать AIAgent".
- If the user names a mode, obey it unless it conflicts with safety policy.
- Do not assume `process` is always faster. It can complete more reliably because each worker is an independent `hermes chat` process and outputs are saved, but it has extra process and synthesis overhead.

This is intentionally a test harness. It can show whether process-level fan-out helps a given workload, but it does not add Hermes core features such as live progress, durable worker registry, child-to-child collaboration, cancellation UI, or automatic retries. Do not add a permanent `compare` mode unless it becomes operationally useful; manual comparison from `run_report.json` is enough for now.

### Step 4 — Call `delegate_task` in Batch Mode

Use one tool call with `tasks=[...]` instead of serial child calls.

Research template:

```python
delegate_task(
    tasks=[
        {
            "goal": "Analyze monetization for Apex Legends",
            "context": "Original request: professional game-design monetization deconstruction. Research ONLY Apex Legends. Read-only. Cover: genre/audience, core loop, monetization points, economy, first payment, retention, ethics, adaptable principles. Include URLs and confidence notes.",
            "toolsets": ["web"]
        },
        {
            "goal": "Analyze monetization for The Sims 4",
            "context": "Same rubric, ONLY The Sims 4. Read-only. Include URLs and confidence notes.",
            "toolsets": ["web"]
        },
        {
            "goal": "Analyze monetization for EA Sports FC / FIFA",
            "context": "Same rubric, ONLY EA Sports FC / FIFA. Read-only. Include URLs and confidence notes.",
            "toolsets": ["web"]
        }
    ]
)
```

Read-only code/audit template:

```python
delegate_task(
    tasks=[
        {
            "goal": "Read-only review of authentication module",
            "context": "Inspect files under src/auth and tests/auth. Do not edit files. Return critical issues, important issues, minor issues, and evidence with paths/lines.",
            "toolsets": ["file", "terminal"]
        },
        {
            "goal": "Read-only review of API routing module",
            "context": "Inspect files under src/api and tests/api. Do not edit files. Return critical issues, important issues, minor issues, and evidence with paths/lines.",
            "toolsets": ["file", "terminal"]
        }
    ]
)
```

### Step 5 — Save or Inspect Raw Outputs

For small tasks, the parent can synthesize directly from child summaries.

For large tasks, save outputs into the generated `workers/` files or another durable folder. This prevents losing coverage and makes final review easier.

### Step 6 — Synthesize

After children finish, the parent must synthesize. Do not paste child summaries one after another without integration.

Synthesis should include:

- Direct answer to the original request.
- Cross-comparison and contradictions.
- Confidence level and source/evidence quality.
- Gaps or items not checked.
- Practical recommendation or next step if relevant.
- Methodology and limitations for larger reports.

For final documents, use **one writer** after synthesis. Do not let multiple workers edit the same final Google Doc/DOCX/Markdown file.

### Step 7 — Verify Coverage and Evidence

Before finalizing, check:

- Did every requested object/source get covered?
- Did every rubric item get covered?
- Did any child exceed scope or perform side effects?
- Are high-impact claims grounded in URLs, file paths/lines, command output, or explicit uncertainty?
- Are contradictions resolved or clearly labeled?
- Is the final answer shorter and more useful than raw child outputs?

## Extraction / Evidence Backends

This skill is vendor-neutral and must work with normal Hermes tools. Do not require a second vendor skill.

Preferred order:

1. Native `web_search` / `web_extract` for ordinary web research.
2. Browser automation for JS-heavy pages or when visual/manual verification matters.
3. File and terminal tools for local repositories, raw docs, CSV/JSON, APIs, and command evidence.
4. Optional vendor tools such as Parallel CLI only when the user explicitly wants them or they are already configured.

Whatever backend is used, cite only evidence actually returned or inspected. Parent verification remains mandatory for high-impact claims.

## Output Schemas for Children

### Research / Analytics Child

Ask each child to return:

```text
Object(s):
Summary:
Key findings:
- Claim / finding:
  Evidence / sources:
  Confidence: high / medium / low
  Risk / caveat:
Contradictions or conflicts noticed:
Open questions / gaps:
```

### Code / Project Audit Child

Ask each child to return:

```text
Scope reviewed:
Critical issues:
- Claim / finding:
  Evidence with paths/lines or command output:
  Confidence: high / medium / low
  Risk / caveat:
Important issues:
Minor issues:
Suggested fixes:
Contradictions or conflicts noticed:
Open questions / gaps:
```

### PR / Issue Triage Child

Ask each child to return:

```text
PR/repo:
State:
CI status:
Mergeability/conflicts:
Changed-file scope:
Likely action: merge-ready / fix CI / rebase / rebuild / close
Evidence:
Risks:
Confidence: high / medium / low
Contradictions or conflicts noticed:
Open questions / gaps:
```

### Design Alternatives Child

Ask each child to return:

```text
Option:
Core idea:
Strengths:
Weaknesses:
Implementation complexity:
Accessibility implications:
Best use case:
```

## Recommended Toolsets

Use minimal child toolsets:

- Web research: `["web"]`
- Search-only tasks: `["search"]`
- GitHub/repo read-only inspection: `["terminal", "file"]`
- Browser QA: `["browser"]` only if visual or interactive behavior matters
- Document extraction: `["web"]` for URLs, `["file"]` for local docs
- Mixed research + local files: `["web", "file"]`

Avoid giving children broad toolsets by default. Fewer tools reduce cost, risk, and context noise.

When giving children `terminal`, constrain commands to read-only inspection: `git diff`, `git show`, `git status`, static analysis, test collection, and equivalent non-mutating diagnostics. Do not let children install packages, run formatters, update lockfiles, write reports, run migrations, start mutating services, or execute commands that modify the workspace.

## Output Contract

The parent response must be one synthesized answer, not a concatenation of child reports.

Include:

- The final answer or recommendation.
- The decomposition contract summary: independent slices, dependencies/non-parallelized parts, and why workers were distinct.
- Which slices were delegated and which completed.
- Key evidence that supports high-impact claims.
- Contradictions labeled as `conflict`, uncertainty, and missing slices.
- Any worker failures and whether they were retried or gracefully degraded.
- Any follow-up action that should remain sequential or require explicit approval.

Do not claim a result is verified only because a child said so. Say “child-reported” or “needs parent verification” when evidence was not directly checked by the parent.

## Examples

### EA Game Monetization Deconstruction

Good split:

- Child 1: EA Sports FC / FIFA.
- Child 2: Apex Legends.
- Child 3: The Sims 4.
- Later wave: Madden NFL, Battlefield, Need for Speed, Plants vs. Zombies/mobile.
- Parent: normalize by common game-design rubric, compare monetization principles, ethics, retention, and reusable hypotheses.
- Final writer: one document after synthesis.

### Multi-Blockchain Governance Analysis

User asks:

```text
Compare governance in Ethereum, Solana, Cosmos, Polkadot, and Near.
```

Good plan:

- Child 1: Ethereum and L2 governance.
- Child 2: Solana and Near governance.
- Child 3: Cosmos and Polkadot governance.
- Parent: compare upgrade process, token voting, councils/foundations, validator role, on-chain/off-chain split, decentralization risks.

### Website Accessibility Spot Checks

User asks:

```text
Check these three landing pages for obvious accessibility issues.
```

Good plan:

- One child per page or group pages by domain.
- Children inspect read-only with browser/web tools.
- Parent deduplicates issues and prioritizes fixes.

### Codebase Architecture Read-Only Review

User asks:

```text
Review architecture risks in this repo.
```

Good plan:

- Child 1: entry points and routing.
- Child 2: persistence/config/secrets handling.
- Child 3: tests/CI/deployment scripts.
- Parent: combine into risk-ranked architecture review.

Do not let children edit files unless the user explicitly asked for implementation and isolation is safe.

## Common Pitfalls

1. **Parallelizing sequential debugging.** If each step depends on the previous result, stay sequential.
2. **Giving every child the full task.** That creates duplicate work and inconsistent assumptions. Give each child a slice.
3. **Skipping synthesis.** The parent must integrate results into one answer; raw child dumps are not enough.
4. **Parallel writes in one repo/document.** This causes conflicts and subtle regressions. Use read-only review or isolated worktrees.
5. **Too many children.** More children can be slower and more expensive. Use 2–3 meaningful children unless the task clearly benefits from more.
6. **Broad toolsets by habit.** Children should get only the tools required for their slice.
7. **Letting children perform side effects.** Subagents should not post, send, trade, deploy, merge, or mutate external systems during auto-parallel work.
8. **Forgetting source quality.** Parallel research can amplify weak sources. Require evidence and confidence from each child.
9. **Assuming speedup is free.** Wall-clock time may improve, but token/API usage rises. Use parallelism when the time savings matter.
10. **Ignoring child failures.** If one child fails, synthesize what is known and clearly label the missing slice, or rerun only that slice.
11. **Confusing skill-level orchestration with core async runtime.** This skill improves behavior but does not provide persistent worker state, retries, cancellation, or streaming progress.

## Verification Checklist

Before final response:

- [ ] The task was classified as safe for parallel read-only work, or explicit approval/isolation was used.
- [ ] Decomposition contract is satisfied: independent branches, dependencies, non-parallelizable parts, split axis, and worker uniqueness are clear.
- [ ] Each child had a distinct bounded scope; no accidental duplicate full-task workers.
- [ ] Child prompts were self-contained and privacy-minimized.
- [ ] Child toolsets were minimal.
- [ ] No child received secrets, unrelated private chat history, client data, production credentials, or broader file/repo access than needed.
- [ ] No child was asked to perform external side effects.
- [ ] No child edited shared files or a shared final document.
- [ ] Every substantive child claim includes evidence or is labeled hypothesis/low-confidence.
- [ ] Results were synthesized, not pasted.
- [ ] Merge protocol was applied: deduplication, evidence comparison, conflict labels, missing/weak branch labels.
- [ ] Coverage of the original request was checked.
- [ ] Contradictions and uncertainty were labeled.
- [ ] Failed/empty/off-scope workers were retried narrowly or explicitly degraded.
- [ ] High-impact claims have inspectable evidence or are labeled as unverified child reports.
- [ ] Final answer includes practical next steps when useful.

## Quick Invocation Examples

After loading this skill, suitable user prompts include:

```text
parallel compare governance across Ethereum, Solana, Cosmos, Polkadot, and Near
```

```text
параллельно проверь эти 6 PR и скажи, какие готовы к merge
```

```text
распараллель анализ этих документаций и собери общий вывод
```

```text
быстрее: проверь три сайта на очевидные accessibility-проблемы
```

```text
сделай research по монетизации 8 игр, распараллель сбор данных, потом собери общий документ
```

## Done Criteria

The skill run is complete only when:

- Parallelization was stopped or allowed based on an explicit stop-condition/decomposition check.
- All delegated slices have either completed or are explicitly marked missing/failed.
- Worker claims have evidence, or unsupported claims are excluded/labeled.
- Conflicts between branches are labeled and handled instead of silently resolved.
- The parent synthesized the results into one coherent answer.
- High-impact claims have inspectable evidence or are labeled as unverified child reports.
- No child performed external side effects, saw unnecessary sensitive data, or wrote shared state.
- The final answer addresses the original user request and states any remaining uncertainty.
