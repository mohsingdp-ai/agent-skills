# Chrome DevTools UI Verification Guide

Before any fix is considered ready to commit, it must pass this live browser runtime checklist using Chrome DevTools (via `chrome-devtools` MCP, CDP CLI, or remote debugging session).

---

## 📋 Verification Checklist

1. **Console Hygiene:**
   - [ ] Confirm **zero unhandled exceptions** (`TypeError`, `ReferenceError`).
   - [ ] Confirm **zero unhandled promise rejections**.
   - [ ] Check for silent React rendering errors (`Cannot update a component while rendering a different component`).

2. **Network Payload Validation:**
   - [ ] Confirm outgoing API requests contain all mandatory headers (`Authorization`, `Content-Type`).
   - [ ] Confirm payloads match expected schema without missing or misspelled keys.
   - [ ] Confirm responses return `200 OK` or expected `2xx` status.

3. **DOM & State Inspection:**
   - [ ] Inspect targeted elements in the DOM tree.
   - [ ] Verify accessibility attributes (`aria-hidden`, `aria-busy`, `role`) reflect current state.
   - [ ] Verify buttons reflect proper loading/disabled states during in-flight network requests.

4. **Edge-Case Stress Testing (Execute at least 2):**
   - **Boundary Inputs:** Pass empty strings, extremely long strings, or non-ASCII characters into inputs.
   - **Double-Click / Debounce:** Rapidly trigger submit buttons to test for duplicate submission bugs.
   - **State Reset:** Cancel a modal or navigate back and forth to ensure state does not leak across sessions.

---

## 🚫 The Skip Vitest Rule

- Do not execute unit test runners (`vitest` / `jest`).
- Rely strictly on live browser execution in Playwright and DevTools runtime inspection.
