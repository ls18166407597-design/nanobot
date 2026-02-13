from nanobot.agent.failure_types import FailureEvent, FailureSeverity
from nanobot.agent.incident_manager import IncidentManager
from nanobot.runtime.failures import list_recent_failures


def test_incident_manager_transient_dedupes_user_notify(tmp_path, monkeypatch):
    monkeypatch.setenv("NANOBOT_HOME", str(tmp_path))
    mgr = IncidentManager(dedupe_window_seconds=3600, escalate_threshold=3)
    event = FailureEvent(
        source="tool_executor",
        category="network_error",
        summary="网络抖动",
        severity=FailureSeverity.TRANSIENT,
        retryable=True,
        details={"tool": "browser", "error_type": "ConnectError"},
    )

    d1 = mgr.report(event)
    d2 = mgr.report(event)
    d3 = mgr.report(event)

    assert d1.should_notify_user is False
    assert d2.should_notify_user is False
    assert d3.should_notify_user is False
    assert d3.count_in_window == 3

    items = list_recent_failures(limit=3)
    assert len(items) == 3
    assert items[0]["source"] == "tool_executor"


def test_incident_manager_non_retryable_error_notifies_immediately(tmp_path, monkeypatch):
    monkeypatch.setenv("NANOBOT_HOME", str(tmp_path))
    mgr = IncidentManager(dedupe_window_seconds=3600, escalate_threshold=3)
    event = FailureEvent(
        source="tool_executor",
        category="permission_denied",
        summary="权限拒绝",
        severity=FailureSeverity.ERROR,
        retryable=False,
        details={"tool": "exec", "error_type": "PermissionError"},
    )
    d1 = mgr.report(event)
    assert d1.should_notify_user is True
    assert d1.should_escalate is True
