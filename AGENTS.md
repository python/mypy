# Agent Requirements

All agents must follow these rules:

1) Fully test your changes before submitting a PR (run the full suite or all relevant tests).
2) PR titles must be descriptive and follow Conventional Commits-style prefixes:
   - Common: `feat:`, `fix:`, `chore:`, `refactor:`, `docs:`, `test:`, `perf:`
   - Support titles: `fix(docs):`, `fix(benchmarks):`, `fix(cicd):`
3) Commit messages must follow the same Conventional Commits-style prefixes and include a short functional description plus a user-facing value proposition.
4) PR descriptions must include Summary, Rationale, and Details sections.
5) Run relevant Python tests for changes (pytest/unittest or the repo's configured runner).
6) Follow formatting/linting configured in pyproject.toml, setup.cfg, tox.ini, or ruff.toml.
7) Update dependency lockfiles when adding or removing Python dependencies.
8) If the repo uses mypyc, verify tests run against compiled extensions (not interpreted Python) and note how you confirmed.
9) Keep base image tags pinned.

Reference: https://www.conventionalcommits.org/en/v1.0.0/
