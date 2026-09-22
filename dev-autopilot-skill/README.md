# dev-autopilot-skill

Take a plain-language intent — a new feature, a change to an existing one, or a bug
— and drive it to a pull request that is already self-verified.

```
/dev-autopilot-skill fix the login redirect dropping the return URL
```

## What makes it different

Most "autonomous development" loops end with the agent declaring success. This one
ends with a **verdict it cannot fake**.

> A gate is green only when something ran and left evidence. Silence is never
> success.

The agent that wrote a change is the worst judge of it — it concluded the code was
correct while writing it, so re-reading its own reasoning reproduces that
conclusion. No gate here reads anything the agent asserts. Each reads a
machine-produced observation: a real exit code captured by executing the command, a
parsed git diff, a review record that survived a credibility audit. A gate with
nothing to read reports `skip`, and a skipped required gate makes `pr_ready`
unreachable by construction.

## The gates

| Gate | Catches |
|---|---|
| `focus-guard` | A `.only` / `fit` / `fdescribe` narrowing the suite to nothing while exiting 0 |
| `suppression-budget` | Tests skipped or `fixme`'d to reach green |
| `tests-pass` | Red suites, vacuous runs (exit 0, zero tests), and broken test commands |
| `red-green-proof` | A bug "fix" never proven to fix the bug |
| `changed-code-tested` | Source changed and no test did |
| `review-credible` | An agent rubber-stamping its own change |
| `scope` | A small approved change quietly growing |

## Origins

Composed from three workflows, all of which are human-in-the-loop by design:

- [Augment deep code reviewer](https://www.augmentcode.com/workflows/coding/deep-code-reviewer) — the review dimensions and context-gathering
- [Playwright Test Agents](https://playwright.dev/docs/test-agents) — planner/generator/healer, and the `test.fixme` trapdoor that motivated the suppression budget
- [OpenSpec workflows](https://github.com/Fission-AI/OpenSpec/blob/main/docs/workflows.md) — plan-before-code, and `verify` before archive

Take the human out of all three and you get an agent grading its own homework. The
gate engine is what replaces that human.

## Install

### Claude Code (plugin — recommended)

```bash
/plugin marketplace add <repo-url>
/plugin install dev-autopilot-skill
```

### Any platform (auto-detect)

```bash
git clone <repo-url> dev-autopilot-skill
cd dev-autopilot-skill && ./install.sh
```

`./install.sh --all` installs everywhere detected, `--dry-run` shows what it would
do, `--platform <name>` targets one tool.

### Manual — native paths

| Platform | Path |
|---|---|
| Claude Code | `~/.claude/skills/dev-autopilot-skill` |
| GitHub Copilot | `~/.copilot/skills/` or `.github/skills/` |
| Codex CLI / universal | `~/.agents/skills/dev-autopilot-skill` |
| Gemini CLI | `~/.gemini/skills/dev-autopilot-skill` |
| Cursor | `.cursor/skills/dev-autopilot-skill` (project only) |
| Windsurf | `.windsurf/rules/` or `~/.codeium/windsurf/skills/` |
| OpenCode | `~/.config/opencode/skills/` |
| Goose | `~/.config/goose/skills/` |
| Cline / Roo | `~/.cline/skills/` · `~/.roo/skills/` |

```bash
git clone <repo-url> ~/.claude/skills/dev-autopilot-skill
```

## Requirements

Python 3.9+ and git. **No third-party Python dependencies.** Your project's own test
runner and linter are detected automatically (pytest, jest, vitest, playwright, go,
cargo, gradle, maven, phpunit, rspec — see `references/toolchain-matrix.md`).

`gh` or `glab` is optional; without one the loop reaches PR-ready and you open the
PR yourself.

## Usage

```bash
python3 scripts/dev_preflight.py --root .                    # seconds; catches late failures early
python3 scripts/run_pipeline.py --intent "add pagination"    # the loop
python3 scripts/run_pipeline.py --continue                   # resume
python3 scripts/dev_state.py status --root .                 # the gate table
```

The pipeline stops with `needs_agent` at the four steps that need judgement — plan,
write the regression test, implement, review — and does everything else itself.

## Composition

Delegates rather than reimplements, and degrades gracefully:

| Phase | Uses when installed | Standalone |
|---|---|---|
| Plan | `openspec-autopilot-skill` | `.dev-autopilot/plan.md` |
| Browser tests | `playwright-test-autopilot-skill` | Unit tests only |
| Post-PR review | `github-pr-triage-skill` | Human review |

This skill owns everything **before** the PR exists. `github-pr-triage-skill` owns
everything **after**.

## Evals

```bash
python3 scripts/run_evals.py --validate
python3 scripts/run_evals.py --rollout
```

Five golden cases over the deterministic audit mode, including a holdout that is
never fed to an optimization loop. See `evals/dev-autopilot-skill.eval.md`.

## Documentation

| File | Contents |
|---|---|
| `SKILL.md` | The skill itself — what the agent reads |
| `references/self-verification-contract.md` | Why evidence outranks assertion; full gate semantics |
| `references/deep-review-protocol.md` | Review dimensions, severity rubric, credibility audit |
| `references/state-machine.md` | Every action, payload, and transition |
| `references/failure-modes.md` | The twelve ways an unattended run goes wrong |
| `references/toolchain-matrix.md` | Detection tables, suppression markers, risk weights |

## Notes

- State lives in `.dev-autopilot/` — add it to your `.gitignore`
- Logs of every executed command are kept under `.dev-autopilot/logs/`
- Runs are resumable; interruption costs nothing

## License

MIT
