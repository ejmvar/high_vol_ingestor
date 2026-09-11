# Verify Telemetry Contract

## Intention

Check that the versioned telemetry schema and representative fixtures remain
valid JSON and continue to demonstrate the intended valid and invalid cases.

## Usage

Run from the repository root:

```bash
./scripts/verify-telemetry-contract.sh
```

## Expected Result

The command exits with status `0`, parses the schema and both fixtures, confirms
that the valid fixture has all schema-required fields, and confirms that the
invalid fixture omits `checksum`.

## Safety and Side Effects

- Read-only.
- Does not start services or access network resources.
- Does not install tools or read secrets.

## Failure Interpretation

- A parse failure means a JSON document is malformed.
- A required-field failure means the fixture or schema changed incompatibly.
- A missing `uv` environment is a tooling failure, not a contract failure.

## Evidence

Output contains paths and validation outcomes only. It does not print payloads,
credentials, or environment values.
