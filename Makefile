.PHONY: help prerequisites test contract analytics-compatibility stack-config stack-up stack-down stack-ps stack-logs check

help:
	./scripts/help.sh

prerequisites:
	./scripts/check-prerequisites.sh

test:
	./scripts/host-test.sh

contract:
	./scripts/verify-telemetry-contract.sh

analytics-compatibility:
	./scripts/verify-analytics-compatibility.sh

stack-config:
	./scripts/local-stack.sh config

stack-up:
	./scripts/local-stack.sh up

stack-down:
	./scripts/local-stack.sh down

stack-ps:
	./scripts/local-stack.sh ps

stack-logs:
	./scripts/local-stack.sh logs

check: test contract stack-config
