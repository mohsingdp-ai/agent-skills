---
name: firecrawl-developer-index
description: Search the Firecrawl Developer Index across GitHub issues, pull requests, commits, READMEs, discussions, and technical documentation. Use this skill when answering developer questions about library behavior, API contracts, error messages, known bugs, or integration troubleshooting that live in developer forums and repositories.
---

# Firecrawl Developer Index

Search the developer-focused index of code repositories, GitHub issues, pull requests, release notes, commit messages, and documentation.

## When to use

- Answering developer questions where the solution lives in issues, PRs, or changelogs:
  - Error strings or stack trace diagnoses
  - Unreleased or newly released library behavior
  - Breaking changes and deprecation notices
  - Framework integration patterns not yet covered in official tutorials
- The user asks to search developer forums, GitHub, or open-source discussions
- Escalation from general search when looking for code-level or developer-specific solutions

## Tools and CLI Usage

### CLI
```bash
# Search developer index for issues or errors
firecrawl developer search "<error message or query>"

# Search with specific categories or filters
firecrawl developer search "TypeError: Cannot read properties of undefined" --source github
```

### MCP Tool
```json
{
  "name": "firecrawl_developer_search",
  "arguments": {
    "query": "Next.js 15 cookies() async migration issue",
    "limit": 10
  }
}
```

### REST API
```bash
curl -X POST "https://api.firecrawl.dev/v2/search" \
  -H "Authorization: Bearer $FIRECRAWL_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "FastAPI lifespan context manager exception",
    "categories": ["developer"]
  }'
```

## Workflow Escalation

- If the user wants academic or preprint papers (PubMed, arXiv, bioRxiv), use [firecrawl-research-index](../firecrawl-research-index/SKILL.md).
- If the user wants general web pages or commercial articles, use [firecrawl-search](../firecrawl-search/SKILL.md).
- If you have a specific documentation URL and want its full content, use [firecrawl-scrape](../firecrawl-scrape/SKILL.md).
