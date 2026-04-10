from __future__ import annotations

from pathlib import Path

import pytest
from django.contrib.auth.models import User

from apps.operations.models import RuntimeActionRun
from apps.operations.services import runtime_control as runtime_control_service


@pytest.mark.django_db
def test_dispatch_runtime_action_run_uses_detached_manage_process(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    action_run = RuntimeActionRun.objects.create(
        provider="local_scripts",
        runtime_id=runtime_control_service.build_runtime_id("orchestrator"),
        runtime_name="orchestrator",
        action_type=RuntimeActionRun.ACTION_RESTART,
        requested_by_username="operator",
        reason="Verify detached dispatch",
    )
    captured: dict[str, object] = {}

    def fake_popen(args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs

        class _DummyProcess:
            pid = 12345

        return _DummyProcess()

    monkeypatch.setattr(runtime_control_service.subprocess, "Popen", fake_popen)

    runtime_control_service.dispatch_runtime_action_run(action_run)

    assert captured["args"][1:4] == [
        "manage.py",
        "execute_runtime_control_action",
        "--action-run-id",
    ]
    assert captured["args"][4] == str(action_run.id)
    assert Path(captured["kwargs"]["cwd"]).name == "orchestrator"
    assert captured["kwargs"]["start_new_session"] is True


@pytest.mark.django_db
def test_create_runtime_action_run_persists_record_when_dispatch_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_id = runtime_control_service.build_runtime_id("worker-workflows")
    actor = User.objects.create_user(username="runtime_dispatch_actor", password="pass", is_staff=True)

    monkeypatch.setattr(
        runtime_control_service,
        "_runtime_inventory_by_id",
        lambda: {runtime_id: {"runtime": "worker-workflows"}},
    )
    monkeypatch.setattr(
        runtime_control_service,
        "dispatch_runtime_action_run",
        lambda action_run: (_ for _ in ()).throw(OSError("spawn failed token=abc123")),
    )

    action_run = runtime_control_service.create_runtime_action_run(
        runtime_id=runtime_id,
        action_type=RuntimeActionRun.ACTION_RESTART,
        actor=actor,
        reason="Restart after config change",
    )
    action_run.refresh_from_db()

    assert action_run.status == RuntimeActionRun.STATUS_FAILED
    assert action_run.requested_by_id == actor.id
    assert "Dispatch failed" in action_run.error_message
    assert "abc123" not in action_run.error_message
    assert "[REDACTED]" in action_run.error_message


@pytest.mark.django_db
def test_execute_tail_logs_action_redacts_sensitive_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(runtime_control_service, "LOGS_DIR", tmp_path)
    log_path = tmp_path / "worker.log"
    log_path.write_text(
        "\n".join(
            [
                "starting worker",
                "password=supersecret",
                "authorization: Bearer secret-token",
                "postgres://svc:dbpassword@example.local/cc1c",
            ]
        ),
        encoding="utf-8",
    )
    action_run = RuntimeActionRun.objects.create(
        provider="local_scripts",
        runtime_id=runtime_control_service.build_runtime_id("worker"),
        runtime_name="worker",
        action_type=RuntimeActionRun.ACTION_TAIL_LOGS,
        requested_by_username="operator",
    )

    runtime_control_service.execute_runtime_action_run(str(action_run.id))
    action_run.refresh_from_db()

    assert action_run.status == RuntimeActionRun.STATUS_SUCCESS
    assert "[REDACTED]" in action_run.result_excerpt
    assert "supersecret" not in action_run.result_excerpt
    assert "secret-token" not in action_run.result_excerpt
    assert "dbpassword" not in action_run.result_excerpt
    assert action_run.result_payload["available"] is True


@pytest.mark.django_db
def test_execute_trigger_now_action_creates_correlated_scheduler_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    action_run = RuntimeActionRun.objects.create(
        provider="local_scripts",
        runtime_id=runtime_control_service.build_runtime_id("worker-workflows"),
        runtime_name="worker-workflows",
        action_type=RuntimeActionRun.ACTION_TRIGGER_NOW,
        target_job_name="pool_factual_active_sync",
        requested_by_username="operator",
    )

    monkeypatch.setitem(
        runtime_control_service.CONTROLLED_SCHEDULER_JOBS["pool_factual_active_sync"],
        "runner",
        lambda: {
            "pools_scanned": 4,
            "checkpoints_touched": 2,
            "checkpoint_contexts_created": 1,
        },
    )

    runtime_control_service.execute_runtime_action_run(str(action_run.id))
    action_run.refresh_from_db()
    scheduler_run = action_run.scheduler_job_run

    assert action_run.status == RuntimeActionRun.STATUS_SUCCESS
    assert scheduler_run is not None
    assert scheduler_run.job_name == "pool_factual_active_sync"
    assert scheduler_run.status == "success"
    assert scheduler_run.job_config["trigger_source"] == "runtime_control"
    assert scheduler_run.job_config["runtime_action_run_id"] == str(action_run.id)
    assert scheduler_run.items_processed == 2
    assert action_run.result_payload["scheduler_job_run_id"] == scheduler_run.id
