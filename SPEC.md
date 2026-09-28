# SPEC: Autonomous Market Scraping & Fast Parity Check

**Idea ID:** 1  
**Status:** In Progress / OpenSpec Approved  
**Tags:** scraping, automation, database  
**Date:** 2026-09-28 08:56:34 UTC  

---

## 1. Context & Background
Ingest marktplaats & ebay listings via Scrapling crawler and use DuckDB/ClickHouse local parity check before triggering apify.

### Reference Resources
- <https://github.com/dreadnode/scrapling>
- <https://duckdb.org>

---

## 2. Requirements & Problem Statement
- **Core Value Proposition:** Build an autonomous, deterministic prototype addressing the problem defined above.
- **Functional Requirements:**
  1. Automated execution with standard CLI interfaces.
  2. Strict isolation, credential protection, and structured logging.
  3. Clean schema and idempotency across recurring executions.
- **Non-Functional Requirements:**
  1. Low latency, zero extraneous heavyweight dependencies.
  2. Explicit failure recovery and graceful error exits.

---

## 3. System Architecture
```
+-------------------------------------------------------------+
|                     User / Automation Run                   |
+------------------------------+------------------------------+
                               |
                               v
               +-------------------------------+
               |       Execution Engine        |
               | (CLI / Background Subprocess) |
               +---------------+---------------+
                               |
        +----------------------+----------------------+
        |                                             |
        v                                             v
+------------------+                        +------------------+
| Ingestion Layer  |                        | Persistence / DB |
| (APIs, Scrapers) |                        | (DuckDB/Supabase)|
+------------------+                        +------------------+
```

### Components
- **CLI Driver:** Command-line entrypoint with arg parsing, check modes, and quiet execution.
- **Service Handler:** Core business logic module handling ingestion, verification, and transformation.
- **Storage/Sync Adapter:** Deterministic persistence layer with error handling.

---

## 4. Phased Implementation Milestones
- [x] **Phase 1: Architecture & OpenSpec Specification** (Completed)
- [x] **Phase 2: Core Scaffold & Dependency Alignment** (Completed: models, DuckDB store, crawler)
- [x] **Phase 3: Business Logic Implementation** (Completed: ParityChecker, ApifyTriggerClient, Rich CLI)
- [x] **Phase 4: Verification & Automated Integration Test Gate (JEV)** (Completed: 6 unit & integration tests passing)

---

## 5. Verification Criteria (JEV Gate)
1. **Security:** Zero secrets or access tokens committed or logged in plaintext. (Verified)
2. **Deterministic Output:** Executing with sample payloads yields reproducible results. (Verified)
3. **Resilience:** Unreachable network or missing credentials fails with structured exit codes. (Verified)
4. **Clean Exit:** All file descriptors, child subprocesses, and temporary artifacts cleaned up. (Verified)

