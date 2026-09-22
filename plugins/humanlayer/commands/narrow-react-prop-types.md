---
description: Narrow React component prop types to match live code paths
---

# /narrow-react-prop-types

Audit React components and narrow broad prop types (such as wide unions, `any`, or unused optional fields) to match actual live code paths.

## Instructions
1. Invoke and follow the guidelines in the `narrow-react-prop-types` skill.
2. Locate the targeted React component(s) and all call sites in production code.
3. Distinguish live production call paths from test/storybook-only usages.
4. Refactor TypeScript interfaces/types so that props accurately reflect the runtime contract without unnecessary bloat.
