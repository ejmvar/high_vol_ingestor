# Check Prerequisites

## Intention

Verify the command-line tools required to start local development without changing the host or accessing secrets.

## Usage

Run from the repository root:

```bash
./scripts/check-prerequisites.sh
```

The script is also the future entry point for a `mise` task.

## Required Tools

- Docker CLI.
- Docker Compose plugin.
- `mise`.
- `uv`.

Terraform is reported as optional until the cloud infrastructure stage begins.

## Expected Result

The command exits with status `0` and prints the detected tool versions. It exits with status `1` when a required command or Docker Compose plugin is unavailable.

## Safety and Side Effects

- Read-only.
- Does not start or stop containers.
- Does not install tools.
- Does not modify files.
- Does not read or print secrets.
- Does not verify Docker daemon health; that belongs to the local-stack health check.

## Failure Interpretation

- `MISSING required command`: install or activate the named tool through the documented `mise`/`uv` workflow.
- `MISSING required Docker Compose plugin`: repair the Docker installation before continuing.
- A version command failure indicates a broken or incomplete tool installation and must not be bypassed.

## Evidence

The output contains tool names, versions, and pass/fail status only. Store it under `artifacts/verification/` only after that evidence directory and its retention policy are defined.
