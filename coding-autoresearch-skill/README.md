# coding-autoresearch-skill

Run any coding task as an autonomous loop that stops only when the result is
verified or genuinely blocked.

A port of [Karpathy's autoresearch](https://github.com/karpathy/autoresearch) —
which lets an agent run ML experiments unattended overnight — to general software
work. The loop is the same: inspect, research, plan, implement, test, verify,
evaluate, iterate. Improve and the branch advances; fail and `git reset`.

## Why it needs a different trick than autoresearch

autoresearch works because its metric already exists and lives in a file the agent
is forbidden to edit: `val_bpb`, computed by a read-only `prepare.py`. A bad idea
costs five minutes and a good result cannot be faked.

A coding task has no `val_bpb`. So the first thing this loop does is **manufacture
one**: it writes a task contract before any implementation and SHA-256 locks it.
Change a criterion afterwards and the run is not merely failed — it is void,
because every number collected against a moving objective is worthless.

The second difference: a coding contract *can* be gamed in four keystrokes, so
some checks are held back. The visible criteria drive the loop; the holdout
criteria are scored only at the end, and catch a green reached by skipping tests,
adding `.only`, or editing outside the declared scope.

## Install

### Claude Code (plugin — recommended)

```bash
/plugin marketplace add ./coding-autoresearch-skill
/plugin install coding-autoresearch-skill@coding-autoresearch-skill
```

### Universal path (Codex CLI, Gemini CLI, Kiro, OpenCode, Goose, Cline, Roo Code)

```bash
git clone <repo-url> ~/.agents/skills/coding-autoresearch-skill
```

### Per tool

```bash
./install.sh                          # auto-detect
./install.sh --all                    # every detected platform
./install.sh --platform cursor        # a specific one
./install.sh --dry-run                # show what it would do
```

| Tool | Path |
|---|---|
| Claude Code | `~/.claude/skills/` or `.claude/skills/` |
| GitHub Copilot | `~/.copilot/skills/` or `.github/skills/` |
| Codex CLI | `~/.agents/skills/` or `.agents/skills/` |
| Gemini CLI | `~/.gemini/skills/` |
| Cursor | `.cursor/skills/` (project only) |
| Windsurf | `.windsurf/rules/` |
| Cline / Roo / Kilo | `~/.cline/skills/`, `~/.roo/skills/`, `~/.kilocode/skills/` |

Requires Python 3.9+ and `git`. No third-party packages.

## Use

```bash
/coding-autoresearch-skill fix the login redirect dropping the return URL
/coding-autoresearch-skill --kind refactor simplify the pricing module
/coding-autoresearch-skill --continue      # resume
/coding-autoresearch-skill --report        # what happened overnight
```

Or drive the scripts directly:

```bash
python3 scripts/run_pipeline.py --task "fix the login redirect" --kind bugfix --tag nightly
python3 scripts/run_pipeline.py --continue
```

Eleven task kinds, each with its own definition of done:

| kind | done means |
|---|---|
| `bugfix` | a test that was red before the fix is green after |
| `debug` | a reproducer plus a written root cause with file:line |
| `feature` | acceptance criteria, as tests, pass |
| `missing` | the previously-absent path is exercised and passes |
| `refactor` | tests unchanged and still green, and the code got smaller |
| `perf` | the benchmark beats the baseline measurement |
| `test` | the new tests fail when the code is mutated |
| `docs` | every documented example actually executes |
| `review` | findings anchored to lines inside the diff |
| `research` | every question answered, every claim cited |
| `integration` | the end-to-end path across the seam passes |

## What it writes

Everything lands in `.autoresearch/`, kept untracked (via `.git/info/exclude`) for
the same reason autoresearch keeps `results.tsv` untracked — committing the ledger
would put the last attempt's record inside the next attempt's diff.

```
.autoresearch/
├── contract.json     the locked objective
├── run.json          loop state; resume reads this, not your memory
├── ledger.tsv        one row per attempt — the morning read
├── verdict.json      the last score
├── report.md         rendered summary
├── findings.md       deliverable for review / research / debug kinds
└── logs/             per-criterion output, kept out of the agent's context
```

The ledger, in autoresearch's shape:

```
attempt  commit   score  max  complexity  status    description
0        9a6dea8  0      5    10          baseline  baseline for bugfix
1        9fd450c  0      5    20          discard   no gain
2        fa3bb85  5      5    17          keep      score 0 -> 5
```

## Verify it works

```bash
python3 scripts/selftest.py all
```

Seven behaviours, each driving a throwaway git repo through the real scripts and
making a specific misbehaviour happen on purpose — a reproducer that reproduces
nothing, a contract edited after locking, a suite turned green by skipping the
failing test — then asserting the loop caught it.

```bash
python3 scripts/run_evals.py --validate    # eval spec is well-formed
python3 scripts/evolve.py                  # staleness, dependencies, drift, evals
```

## Honest limits

- **It measures completion, not quality.** Every check can pass on a change that
  is poorly factored or solves the wrong problem well. Read the diff in the morning.
- **The holdout leaks.** Telling the loop which holdout check failed partly spends
  it. Two reveals are allowed, then the run blocks for a human. Bounded, not solved.
- **A mis-specified contract is pursued faithfully.** It is locked at attempt zero;
  the `review_contract` step is the only defence, and it needs your attention for
  about thirty seconds.
- **Toolchain detection guesses.** It reads `package.json`, `pyproject.toml`,
  `go.mod`, `Cargo.toml` and similar. Run the proposed test command once yourself
  before locking.

## Documentation

| File | Contents |
|---|---|
| `SKILL.md` | The skill itself |
| `AGENTS.md` | Companion instruction file (AAIF format) |
| `references/kind-profiles.md` | All eleven kinds and how to choose |
| `references/loop-semantics.md` | Scoring, keep/discard, every transition |
| `references/failure-modes.md` | The traps, including the ones no guard catches |
| `references/autoresearch-mapping.md` | What was ported, what changed, and why |

## Licence

MIT.

Built on the design in <https://github.com/karpathy/autoresearch> — in particular
its `program.md`, whose rules about fixed budgets, keep/discard by git, crashes
versus failures, redirecting output away from the agent's context, and never
pausing to ask are carried over more or less verbatim.
