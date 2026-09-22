# Firecrawl Plugin for Claude Code

A complete Claude Code plugin packaging **17 skills** for web scraping, intelligent web search, full-site crawling, browser automation, document parsing, change monitoring, academic research retrieval, and application SDK/API code integration using **Firecrawl**.

Each skill provides clear step-by-step guidance, decision matrices, escalation rules, tool usage instructions (CLI, MCP, and REST API), and guardrails.

---

## Installation

### 1. Register the Plugin Marketplace
```bash
claude plugin marketplace add /home/mejazbese21/Work/RndProjects/AgentSkills/plugins/firecrawl
```

### 2. Install the Plugin
```bash
# Global installation (recommended for all sessions)
claude plugin install firecrawl@firecrawl

# Or project-scoped installation (applies to the current repo only)
claude plugin install firecrawl@firecrawl --scope project
```

To verify the installation:
```bash
claude plugin list
```

To disable or remove:
```bash
claude plugin disable firecrawl@firecrawl
claude plugin uninstall firecrawl@firecrawl
```

---

## Configuration & Environment

Set your credentials in your environment or `.env` file:

```bash
# For hosted Firecrawl Cloud:
export FIRECRAWL_API_KEY="fc-..."

# For local self-hosted Firecrawl instance:
export FIRECRAWL_API_URL="http://localhost:3663"
```

---

## Skills Catalog

Invoke any skill directly in Claude Code as `firecrawl:<skill-name>`.

### 🌐 Session & Web Retrieval Skills

Use these skills during an active coding or research session to gather information from the live web.

| Skill | Invocation | Description |
| :--- | :--- | :--- |
| **Scrape** | `firecrawl:scrape` | Extract clean, LLM-optimized markdown from any URL, including JavaScript-rendered SPAs. |
| **Search** | `firecrawl:search` | Real-time web search returning structured results with optional full-page markdown. |
| **Crawl** | `firecrawl:crawl` | Recursively traverse and extract content across an entire website with path/depth filtering. |
| **Interact** | `firecrawl:interact` | Automate browser actions on complex pages: clicks, typing, dropdowns, form submissions, and login flows. |
| **Map** | `firecrawl:map` | Rapidly discover all URLs and sitemaps for a domain without downloading full page bodies. |
| **Monitor** | `firecrawl:monitor` | Monitor web pages for changes and content diffs over time (supports periodic scheduling). |
| **Parse** | `firecrawl:parse` | Convert local files, PDFs, DOCX, and documents into clean structured markdown. |
| **Download** | `firecrawl:download` | Bulk download entire websites, doc sets, or page lists into organized local directories. |
| **Agent** | `firecrawl:agent` | Autonomous deep research agent that iteratively searches, extracts, validates, and synthesizes multi-source findings. |
| **Research Index** | `firecrawl:research-index` | Specialized academic paper search over arXiv, PubMed, bioRxiv, and medRxiv with HyDE semantic expansion. |
| **Developer Index** | `firecrawl:developer-index` | Search code repositories, GitHub issues, pull requests, release notes, and engineering documentation. |
| **CLI Guide** | `firecrawl:cli` | Master reference and workflow escalation ladder for the Firecrawl CLI and environment setup. |

---

### 🛠️ Product Code Integration Skills

Use these skills when writing application code to integrate Firecrawl SDKs (`@mendable/firecrawl-js`, `firecrawl-py`, Go, REST) into a product or backend service.

| Skill | Invocation | Description |
| :--- | :--- | :--- |
| **Build Architecture** | `firecrawl:build` | Top-level guide for adding Firecrawl into an application: architectural patterns, endpoint selection, SDK setup. |
| **Onboarding** | `firecrawl:build-onboarding` | Setting up API credentials, environment variables, Stripe Projects integration, and client initialization. |
| **Build Scrape** | `firecrawl:build-scrape` | Implementing single-page scraping, structured schema extraction, and cache freshness/liveness in code. |
| **Build Search** | `firecrawl:build-search` | Implementing web search and content discovery pipelines in backend services. |
| **Build Interact** | `firecrawl:build-interact` | Implementing multi-step browser automation and session actions in production workflows. |

---

## Workflow Escalation Pattern

When retrieving web data, follow Firecrawl's recommended escalation ladder:

```text
1. Search       -> Discover candidate URLs when you don't know the exact address
   │
2. Scrape       -> Extract markdown from a known target URL
   │ (if page requires multi-step interaction or login)
3. Interact     -> Click buttons, fill inputs, wait for client renders
   │ (if you need the entire site structure)
4. Map          -> Discover all valid endpoints and sitemaps on the domain
   │ (if you need to ingest the whole site)
5. Crawl        -> Recursively scrape mapped pages with depth and path limits
```

---

## References & Documentation

- [Official Firecrawl Documentation](https://docs.firecrawl.dev)
- [Firecrawl GitHub Repository](https://github.com/firecrawl/firecrawl)
- [Firecrawl SDKs](https://github.com/firecrawl/firecrawl/tree/main/apps)
