---
name: contract-docs-verify
description: Just-In-Time third-party API and documentation contract verifier. Consults official documentation (e.g. Equals Money API, Stripe, Modulr) and OpenAPI schemas before writing code fixes to eliminate hallucinated payload keys, incorrect headers, and invalid parameter types.
allowed-tools: Read, Grep, Glob, Bash
---

# Just-In-Time Contract & Docs Verification (`contract-docs-verify`)

The **Contract Docs Verifier Skill** ensures that agents never write code against guessed or hallucinated external API contracts. When dealing with complex fintech, banking, or third-party APIs (like Equals Money, cards, payments, or webhooks), the agent must consult the live documentation before modifying application source code.

---

## 🛑 The Verification Rule

When a defect touches an external integration:
1. **Identify the External Service:** Determine the target API (e.g. Equals Money, Stripe, banking rails).
2. **Consult Official Docs:**
   - For Equals Money: Check `https://docs.equalsmoney.com` or local OpenAPI specifications.
   - For payment cards: Check tokenization, spend controls, and PIN/activation parameters.
   - For payouts: Check domestic vs. cross-border rails (Faster Payments, SEPA, SWIFT).
   - For webhooks: Check signature headers, HMAC secret handling, and payload event names.
3. **Validate Against Implementation:**
   - Compare the expected documentation schema with the implementation in `src/`.
   - Correct field names (e.g., snake_case vs. camelCase, amount in major vs. minor currency units).
   - Ensure proper error handling for 4xx/5xx responses.
