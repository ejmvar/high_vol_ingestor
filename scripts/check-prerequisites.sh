#!/usr/bin/env bash
# Intention: verify the host tools required for local development.
# Expected result: exit 0 only when the required CLIs are available.
# Safety: read-only; does not start services, change files, or read secrets.
# Usage: ./scripts/check-prerequisites.sh
# Failure: install or repair the reported required tool, then rerun this script.
# Evidence: prints tool names and versions only; no environment values or secrets.

set -Eeuo pipefail

required=(docker mise uv)
missing=0

printf 'Checking local development prerequisites\n'

for tool in "${required[@]}"; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        printf 'MISSING required command: %s\n' "$tool"
        missing=1
        continue
    fi

    case "$tool" in
        docker) version_command=(docker --version) ;;
        mise) version_command=(mise --version) ;;
        uv) version_command=(uv --version) ;;
    esac
    printf 'FOUND %s: %s\n' "$tool" "$("${version_command[@]}")"
done

if command -v terraform >/dev/null 2>&1; then
    printf 'FOUND optional terraform: %s\n' "$(terraform version -json 2>/dev/null | uv run python -c 'import json,sys; print(json.load(sys.stdin)["terraform_version"])' 2>/dev/null || terraform version | awk 'NR==1 {print $2}')"
else
    printf 'NOT FOUND optional terraform: required for cloud stages only\n'
fi

if command -v docker >/dev/null 2>&1; then
    if docker compose version >/dev/null 2>&1; then
        printf 'FOUND docker compose: %s\n' "$(docker compose version --short)"
    else
        printf 'MISSING required Docker Compose plugin\n'
        missing=1
    fi
fi

if (( missing != 0 )); then
    printf 'Prerequisite check failed.\n' >&2
    exit 1
fi

printf 'Prerequisite check passed.\n'
