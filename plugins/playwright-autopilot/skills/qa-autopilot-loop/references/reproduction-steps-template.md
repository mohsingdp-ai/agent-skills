# Backlog Bug Report Template

Use this format when filing issues into GitHub Issues (`gh issue create`), Linear, Jira, or a local `BACKLOG.md`:

```markdown
# [Epic: {EPIC_NAME}] {Concise Bug Title}

**Labels:** `bug`, `automated-pw`, `confidence-{SCORE}`

### 📊 Jev Confidence Score
- **Score:** {SCORE}/100
- **Calibration Rationale:** {1-sentence justification verifying determinism and impact}

### 🌐 Environment
- **URL / Route:** `{ENTRY_URL}`
- **Persona / Role:** `{e.g. Authenticated Business User / Guest}`
- **Device / Browser:** `Chromium Desktop`

### 🔁 Deterministic Steps to Reproduce
1. Navigate to `{ENTRY_URL}`.
2. Click on `{Locator / Element name}`.
3. Fill `{Field name}` with `{Payload}`.
4. Click `{Submit / Action button}`.

### ⚖️ Expected vs. Actual Behavior
- **Expected:** {What should happen according to product specs}
- **Actual:** {Observed error, broken UI, or rejected state}

### 🔍 Evidence & Diagnostics
- **Console Errors:**
  ```text
  {Captured unhandled exception or console.error}
  ```
- **Network Failures:**
  ```text
  {HTTP Method} {Endpoint} -> {Status Code} {Response Body}
  ```
- **Playwright Trace Locator:** `{Locator string, e.g. page.getByRole('button', { name: 'Submit' })}`
```
