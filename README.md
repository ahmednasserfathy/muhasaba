# Muhasaba | محاسبة النفس

Flutter Android-first application with a Python FastAPI backend and PostgreSQL. This repository is a **documentation-first bootstrap**, prepared for implementation by Codex in small reviewed pull requests. **There is no working mobile app or backend in this initial commit.**

## Current status

- **Product baseline:** Implementation Blueprint v1.4, approved 20 November 2026.
- **Next task:** PR-00 repository foundation only, see [`codex/PR-00_FOUNDATION.md`](codex/PR-00_FOUNDATION.md).
- **Tech:** Flutter, Riverpod, Dio, Drift/SQLite; FastAPI, Python, Pydantic, SQLAlchemy 2, Alembic, PostgreSQL; Docker Compose for local development.
- **Language/time:** Arabic RTL, default timezone `Africa/Cairo`; UTC timestamps for audit.
- **Approach:** Modular monolith. No premature microservices, queues, Redis, Kubernetes or remote website scraping.

## Read before implementation

1. [`AGENTS.md`](AGENTS.md), repository-level Codex engineering instructions.
2. [`docs/blueprint/10_LOCKED_CORE_MVP_AR.md`](docs/blueprint/10_LOCKED_CORE_MVP_AR.md), **authoritative business rules**.
3. [`docs/blueprint/README.md`](docs/blueprint/README.md), guide to all v1.4 specifications.
4. [`docs/blueprint/07_DELIVERY_CODEX.md`](docs/blueprint/07_DELIVERY_CODEX.md), PR roadmap and acceptance criteria.
5. [`codex/PR-00_FOUNDATION.md`](codex/PR-00_FOUNDATION.md), first task, do not proceed to PR-01 without review.

## Non-negotiable score rule

Only the weighted **main daily accountability cards** determine daily score. Official, score-eligible nested adhkar share points **inside their fixed parent card**, granting partial credit as their repetitions are completed. Custom user dua/adhkar and hiding/reordering official defaults **never** add points or change the parent's point budget. Support exact undo and preserve scores from previous days.

## Initial project structure

```text
muhasaba/
  AGENTS.md
  README.md
  docs/blueprint/             # locked product, DB, API and domain specs
  codex/PR-00_FOUNDATION.md  # first Codex task
  codex/WORKFLOW.md          # PR review workflow
  .github/pull_request_template.md
  .gitignore
```

Codex will create `backend/`, `mobile/`, and `infra/` **during PR-00**. These directories are intentionally not scaffolded yet.

## GitHub setup

**Preferred, assisted upload:** Create a **Private** GitHub repository named `muhasaba` owned by `ahmednasserfathy`, **initialize it with a README** so the `main` branch exists, and share the URL in this chat. The assistant can then upload these source files through the connected GitHub integration (updating the starter README). Check that the GitHub app has access to the newly created repository. Never send credentials.

**Alternative, local upload:** Create an **empty Private** repository, without README, license or `.gitignore`; extract this package, open the `muhasaba` directory and execute:

```bash
git init -b main
git add .
git commit -m "docs: initialize Muhasaba v1.4 implementation blueprint"
git remote add origin https://github.com/ahmednasserfathy/muhasaba.git
git push -u origin main
```

If `git init -b main` is unavailable, run `git init` and then `git branch -M main`. Authenticate through GitHub's recommended credential flow; **do not place tokens in files or chat**. Do not mix the two setup paths to avoid an unnecessary merge conflict.

Then connect/select this repository in the [Codex Cloud environment](https://help.openai.com/en/articles/20001545-using-codex-cloud), paste the first task from `codex/PR-00_FOUNDATION.md`, inspect its changes and tests, and create/review a PR before merging.

## Content rights and source verification

The screenshots and public site are functional references, **not authorization to reuse private site APIs, copyrighted assets, or unverified Arabic texts**. Proposed scoring weights and Thursday seed totals are product fixtures rather than proof of the reference site's internal calculations.

## References

- [Flutter architecture](https://docs.flutter.dev/app-architecture)
- [FastAPI docs](https://fastapi.tiangolo.com/)
- [SQLAlchemy](https://docs.sqlalchemy.org/en/20/)
- [Alembic](https://alembic.sqlalchemy.org/en/latest/)
- [GitHub repository creation](https://docs.github.com/en/repositories/creating-and-managing-repositories/creating-a-new-repository)
- [Codex Cloud](https://help.openai.com/en/articles/20001545-using-codex-cloud)