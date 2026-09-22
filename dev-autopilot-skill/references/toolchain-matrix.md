# Toolchain Matrix

What the skill detects, per language and per tool. Everything here is best-effort
detection with an explicit override, because a wrong guess that cannot be corrected
is worse than no guess.

## Test command detection

`record_check.py --check tests --auto` resolves in this order. First match wins.

| Marker | Runner | Command |
|---|---|---|
| `package.json` with a `test` script | node | `npm test --silent` (or `pnpm`/`yarn`/`bun` by lockfile) |
| `pyproject.toml` / `pytest.ini` / `setup.cfg` | pytest | `python3 -m pytest -q` |
| `go.mod` | go | `go test ./...` |
| `Cargo.toml` | cargo | `cargo test` |
| `build.gradle[.kts]` | gradle | `./gradlew test` |
| `pom.xml` | maven | `mvn -q test` |
| `composer.json` | phpunit | `./vendor/bin/phpunit` |
| `Gemfile` | rspec | `bundle exec rspec` |
| `tests/` or `test/` directory | pytest | `python3 -m pytest -q` |

Package manager is resolved from the lockfile: `pnpm-lock.yaml` → pnpm,
`yarn.lock` → yarn, `bun.lockb` → bun, `package-lock.json` → npm.

Override any time with `--command`. Detection is a convenience, not a constraint.

## Lint and typecheck detection

| Marker | Tool | Command |
|---|---|---|
| `ruff.toml` / `.ruff.toml` | ruff | `ruff check .` |
| `.eslintrc.json` / `.eslintrc.js` / `eslint.config.{js,mjs}` | eslint | `npx eslint .` |
| `.golangci.yml` | golangci-lint | `golangci-lint run` |
| `.rubocop.yml` | rubocop | `bundle exec rubocop` |
| `Cargo.toml` | clippy | `cargo clippy -- -D warnings` |
| `tsconfig.json` | tsc | `npx tsc --noEmit` |
| `mypy.ini` | mypy | `mypy .` |
| `pyrightconfig.json` | pyright | `npx pyright` |

When a project has neither, record the absence explicitly:

```bash
python3 scripts/record_check.py --check lint --none --reason "no linter configured"
```

Absence of a tool is a real observation. Absence of a *run* is not.

## Suppression markers by language

Counted against **added lines only**. `kind` is one of `skip`, `fixme`, `todo`,
`xfail`, `ignore`.

| Language | Markers |
|---|---|
| JS / TS | `it.skip` `test.skip` `describe.skip` `suite.skip` `xit` `xdescribe` `xtest` `test.fixme` `it.fixme` `test.todo` `it.todo` `test.step.skip` `this.skip()` |
| Python | `@pytest.mark.skip` `@pytest.mark.skipif` `@unittest.skip{If,Unless}` `pytest.skip()` `@pytest.mark.xfail` `pytest.xfail()` |
| Go | `t.Skip()` `t.SkipNow()` `t.Skipf()` |
| Rust | `#[ignore]` |
| Java / Kotlin / Scala | `@Disabled` `@Ignore` `Assume.assumeX()` |
| Ruby | `skip` `xit` `pending` |
| C# | `[Ignore]` `Skip =` |
| PHP | `markTestSkipped()` `markTestIncomplete()` |

## Focus markers — always blocking

These narrow the run while still exiting 0. Tracked separately from suppression
because the consequence is different in kind, not degree.

| Language | Markers |
|---|---|
| JS / TS | `it.only` `test.only` `describe.only` `suite.only` `bench.only` `fit` `fdescribe` `ftest` `test.step.only` |
| Ruby | `fit` `:focus => true` `focus: true` |
| Go | `//go:build focus` |

Python, Java, Rust and C# have no standard focus primitive, so none is scanned.

## Comment handling

An obvious trailing line comment is stripped before matching, so a commented-out
`// test.only(...)` does not trip the focus gate. The stripper is not a parser: a
string literal containing `//` survives intact, which is the safe direction to be
wrong in — a false positive costs one investigation, a false negative costs the
whole guarantee.

## Risk tags

Path-matched, additive, capped at 100. `high` at ≥40, `medium` at ≥15.

| Tag | Weight | Matches |
|---|---|---|
| `auth` | 25 | auth, login, session, token, jwt, oauth, saml, password, credential, permission, rbac, acl |
| `secrets` | 25 | secret, vault, keystore, `.env`, credentials |
| `crypto` | 20 | crypto, cipher, encrypt, decrypt, hash, signature, tls, ssl |
| `migration` | 20 | `migrations/`, `schema.{sql,rb,prisma}`, alembic, flyway, liquibase |
| `money` | 20 | payment, billing, invoice, charge, refund, stripe, paypal, ledger, pricing, checkout |
| `pii` | 15 | gdpr, pii, personal_data, anonymise, redact |
| `infra` | 12 | terraform, `.tf`, helm, k8s, kubernetes, docker-compose, Dockerfile |
| `ci` | 12 | `.github/workflows/`, `.gitlab-ci`, Jenkinsfile, azure-pipelines |
| `deps` | 10 | package.json, lockfiles, requirements.txt, pyproject.toml, go.mod, Gemfile, Cargo.toml |
| `concurrency` | 10 | worker, queue, thread, async, scheduler, cron, lock, mutex, semaphore |
| `public-api` | 10 | `routes/`, `controllers/`, `handlers/`, `endpoints/`, `api/`, graphql |

Risk drives the review credibility bar: a high-risk change cannot pass review with
an unexplained clean result, regardless of how few lines it touches. Twenty lines in
an auth guard is not twenty lines in a README.

## Test file detection

A path is a test file when it contains `/test/`, `/tests/`, `/spec/`, `/specs/`,
`/__tests__/`, `/e2e/`, `/integration/`, `/testing/`, or its filename matches
`test_*`, `*_test.*`, `*.test.*`, `*.spec.*`, `testSomething.*`.

Deliberately generous. A false positive slightly weakens the `changed-code-tested`
signal; a false negative would let a change claim it shipped tests when it did not.

## Test count parsers

| Runner | Parsed from |
|---|---|
| pytest | `5 passed, 1 failed, 2 skipped in 0.4s` |
| jest / vitest | `Tests: 1 failed, 12 passed, 13 total` |
| playwright | `12 passed (3.2s)` |
| mocha | `12 passing`, `1 failing`, `2 pending` |
| go | `--- PASS:` / `--- FAIL:` / `--- SKIP:` line counts |
| cargo | `test result: ok. 5 passed; 0 failed; 1 ignored` |

An unparsed count is recorded as `null`, never `0` — "unknown" and "zero" mean
different things to the vacuous-run check.

## Harness error signatures

Output patterns meaning the tests never ran, so the exit code describes the harness
rather than the code:

`ModuleNotFoundError` · `No module named` · `ImportError` · `command not found` ·
`is not recognized as an internal or external command` · `MODULE_NOT_FOUND` ·
`Cannot find module` · `no tests ran` · `No tests found` · `collected 0 items` ·
`ERROR collecting` · `Permission denied`

Plus exit 127 (not found), exit 124 (timeout), and pytest exit codes 2 (interrupted),
3 (internal error), 4 (usage error), 5 (no tests collected) — none of which is a test
failure.
