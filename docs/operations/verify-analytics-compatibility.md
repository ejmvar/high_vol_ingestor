# Verify Analytics Compatibility

## Intention

Run the same canonical analytical fixture through the dependency-free reference
adapter and any explicitly installed DuckDB or chDB adapters.

## Usage

```bash
./scripts/verify-analytics-compatibility.sh
```

## Expected Result

- Exit `0`: every available adapter matches the reference result.
- Exit `2`: the reference passes but one or more optional engines are not
  installed; this is a bounded capability result, not a parity pass.
- Exit `1`: an available adapter fails result parity or the reference fixture is
  inconsistent.

## Safety and Side Effects

- Uses in-memory databases only.
- Does not start Docker, connect to services, write files, or access secrets.
- Does not measure throughput, durability, or multi-process behavior.

## Evidence

Output names the adapter and reports `PASS`, `UNAVAILABLE`, or `FAIL`. It does
not print payloads or environment values.
