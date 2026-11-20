# Codex collaboration workflow

1. GitHub `main` = reviewed, stable code and approved specs. No direct auto-merge by agent.
2. Give Codex exactly **one** PR task at a time, starting at [`PR-00`](PR-00_FOUNDATION.md).
3. Codex creates a feature branch, implements only that scope, runs tests, and prepares a draft PR.
4. Human reviews diff, assumptions, `.env`/secret hygiene and tests. Request revisions in the **same** task/PR if needed.
5. Merge to `main` only after acceptance criteria pass. Then proceed to the next PR in `docs/blueprint/07_DELIVERY_CODEX.md`.
6. Any change to score rules must be decided in writing, recorded in a new design version, and backed by regression fixtures.

## Codex Cloud setup

- Create and publish an environment for the correct private GitHub repo `ahmednasserfathy/muhasaba` using your connected GitHub account. Repository permissions and environment access both matter.
- Choose a supported environment with access to Python tooling and Flutter toolchain (or have Codex/CI install Flutter). Docker availability may differ; record missing checks as NOT_RUN.
- Paste `codex/PR-00_FOUNDATION.md` as the initial task. Never grant real production credentials to bootstrap tasks.
- Review the resulting draft PR and GitHub Actions status.

Reference: https://help.openai.com/en/articles/20001545-using-codex-cloud
