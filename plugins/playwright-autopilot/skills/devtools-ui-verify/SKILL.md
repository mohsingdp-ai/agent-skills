---
name: devtools-ui-verify
description: Live UI and DOM verification using Chrome DevTools Protocol / CLI. Audits console errors, inspects network payloads, tests edge-case interactions, and enforces the 'Skip Vitest' functional verification rule.
allowed-tools: Read, Grep, Glob, Bash
---

# Chrome DevTools UI Verification (`devtools-ui-verify`)

The **DevTools UI Verification Skill** bridges automated headless testing with real-world browser telemetry. It ensures that code fixes don't just make assertions pass, but also execute cleanly in the browser runtime without silent memory leaks, unhandled rejections, or console warnings.

---

## 🛠️ Verification Procedure

1. **Attach or Launch DevTools:**
   Connect via Chrome DevTools MCP (`chrome-devtools`) or launch with remote debugging.

2. **Console Inspection:**
   Verify that zero unhandled exceptions, zero `console.error` calls, and no React hydrations/render errors occur during user interactions.

3. **Network Payload Auditing:**
   Examine outgoing HTTP requests. Verify headers (`Authorization`, `Content-Type`), request payloads, and status codes (`2xx`).

4. **Edge Case Stress Testing:**
   Test at least 2 edge cases:
   - Empty or null inputs.
   - Rapid double-clicks / debouncing.
   - Session or modal state reset on cancellation.

5. **Skip Vitest:**
   Do not run Vitest or unit test runners. Rely exclusively on live functional browser verification.
