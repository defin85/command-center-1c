import uuid

from apps.artifacts.refs import contains_artifact_ref, extract_artifact_ids


def test_contains_artifact_ref_finds_id_in_nested_structures():
    artifact_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
    other_id = uuid.UUID("22222222-2222-2222-2222-222222222222")

    payload = {
        "file": f"artifact://artifacts/{artifact_id}/v1/file.txt",
        "nested": [
            {"x": "nope"},
            {"y": [f"artifact://artifacts/{other_id}"]},
        ],
    }

    assert contains_artifact_ref(payload, artifact_id) is True
    assert contains_artifact_ref(payload, other_id) is True

    missing = uuid.UUID("33333333-3333-3333-3333-333333333333")
    assert contains_artifact_ref(payload, missing) is False


def test_contains_artifact_ref_is_case_insensitive():
    artifact_id = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    payload = {"file": f"ARTIFACT://ARTIFACTS/{str(artifact_id).upper()}/v1/file.txt"}
    assert contains_artifact_ref(payload, artifact_id) is True


def test_extract_artifact_ids_collects_all_matches_and_ignores_invalid():
    a = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    b = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

    payload = {
        "one": f"artifact://artifacts/{a}/v1/file.txt",
        "two": [f"artifact://artifacts/{b}", "artifact://artifacts/not-a-uuid/v1/x"],
        "three": {"other": "no refs here"},
    }

    found = extract_artifact_ids(payload)
    assert found == {a, b}

