---
description: Run the autonomous iterative QA Autopilot loop: pick failing scenario, surgical fix, JIT docs check, verify with Playwright + Chrome DevTools (skip Vitest), atomic commit, and repeat until 0 failures.
argument-hint: "[BASE_URL or spec path]"
---

# /pw-autopilot:loop

Execute the closed-loop autonomous repair loop across all failing test scenarios or backlog issues.

## Loop Lifecycle
1. **Target Selection:** Identify failing spec via `npx playwright test --last-failed` or target from `$ARGUMENTS`.
2. **Diagnostics & JIT Contract Check:** Run with `--trace=on`. If external API (e.g. Equals Money) is involved, verify contract in docs (`https://docs.equalsmoney.com`) before editing code.
3. **Surgical Repair & Test Healing:** Edit only root-cause lines in `src/`. Heal test locators if UI shifted. Zero test skipping allowed.
4. **Dual Verification Gate:** Verify `npx playwright test {target}` passes (code 0). Verify live DOM & console with Chrome DevTools (0 console errors, 2 edge cases tested). **Skip Vitest**.
5. **Atomic Commit:** Commit surgically: `git commit -m "fix({scope}): {description}"`. **Do not push**.
6. **Repeat:** Continue until all tests pass cleanly.
