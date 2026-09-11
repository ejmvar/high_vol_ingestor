# Host Test Suite

## Intention

Provide one canonical, task-runner-independent entry point for the repository's
host-side tests.

## Usage

```bash
./scripts/host-test.sh
```

Equivalent task-runner commands are `mise run test`, `make test`, and `just
test`.

## Expected Result

The command runs `uv run pytest` from the repository root and exits `0` when all
available tests pass.

## Safety and Side Effects

- Does not start Docker or Podman services.
- Does not access secrets.
- May create ignored Python test caches.

## Failure Interpretation

A non-zero exit is a test or environment failure. Optional analytics-engine
tests may be skipped when DuckDB or chDB is not installed; use the dedicated
compatibility script to distinguish unavailable engines from parity failure.

## Evidence

Pytest output reports collection, pass, skip, and failure counts only.
