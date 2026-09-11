import json
from pathlib import Path

import pytest

from telemetry_contract import ContractError, StatefulTelemetryValidator, validate_envelope


FIXTURES = Path(__file__).parents[1] / "schemas/telemetry/v1/fixtures"


def valid_envelope() -> dict:
    return json.loads((FIXTURES / "valid-vibration.json").read_text(encoding="utf-8"))


def test_valid_envelope_is_accepted() -> None:
    assert validate_envelope(valid_envelope())["motor_id"] == "MOTOR-c2ad"


def test_non_object_record_is_rejected() -> None:
    with pytest.raises(ContractError) as error:
        validate_envelope([])  # type: ignore[arg-type]

    assert error.value.code == "invalid_record"


def test_missing_checksum_is_rejected() -> None:
    envelope = valid_envelope()
    del envelope["checksum"]

    with pytest.raises(ContractError, match="missing fields") as error:
        validate_envelope(envelope)

    assert error.value.code == "missing_field"


def test_event_end_must_follow_event_start() -> None:
    envelope = valid_envelope()
    envelope["event_end"] = envelope["event_start"]

    with pytest.raises(ContractError) as error:
        validate_envelope(envelope)

    assert error.value.code == "invalid_interval"


def test_payload_length_and_checksum_are_verified() -> None:
    envelope = valid_envelope()
    payload = b"sample"
    envelope["payload_byte_length"] = len(payload)
    envelope["checksum"]["value"] = "a" * 64

    with pytest.raises(ContractError) as error:
        validate_envelope(envelope, payload)

    assert error.value.code == "checksum_mismatch"


def test_duplicate_is_idempotently_acknowledged() -> None:
    validator = StatefulTelemetryValidator()
    envelope = valid_envelope()

    assert validator.accept(envelope).status == "accepted"
    assert validator.accept(envelope).status == "duplicate"


def test_conflicting_duplicate_is_rejected() -> None:
    validator = StatefulTelemetryValidator()
    first = valid_envelope()
    second = valid_envelope()
    second["checksum"]["value"] = "a" * 64

    validator.accept(first)
    with pytest.raises(ContractError) as error:
        validator.accept(second)

    assert error.value.code == "conflicting_duplicate"


def test_out_of_order_sequence_is_rejected_per_producer_and_motor() -> None:
    validator = StatefulTelemetryValidator()
    first = valid_envelope()
    second = valid_envelope()
    second["event_id"] = "evt-000002"
    second["idempotency_key"] = "MOTOR-c2ad/vibration/second"
    second["producer_sequence"] = 0

    validator.accept(first)
    with pytest.raises(ContractError) as error:
        validator.accept(second)

    assert error.value.code == "out_of_order"
