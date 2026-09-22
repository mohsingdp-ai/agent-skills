---
description: Discover user flows per persona, map them in Mermaid, and generate smoke tests
argument-hint: [optional route or module, e.g. /cards, or all]
---

# /pw:discover

Invoke the `playwright:flow-discoverer` skill on `$ARGUMENTS` and follow it exactly.

- Personas come from `specs/personas.md` (asks if missing).
- Writes the map + smoke plan to `specs/flows/<module>.md`, then generates tests after your approval.
