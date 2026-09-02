from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services.ai_service import generate_morning_briefing
from app.utils.datetime import utc_isoformat


def test_utc_isoformat_marks_naive_database_timestamp_as_utc():
    assert utc_isoformat(datetime(2026, 8, 26, 8, 30)) == "2026-08-26T08:30:00Z"


def test_utc_isoformat_converts_aware_timestamp_to_utc():
    pakistan_time = timezone(timedelta(hours=5))
    assert utc_isoformat(datetime(2026, 8, 26, 13, 30, tzinfo=pakistan_time)) == "2026-08-26T08:30:00Z"


@patch("app.services.ai_service.get_groq_client")
@patch("app.services.ai_service.get_db_connection")
def test_briefing_uses_profile_expiry_window_and_exact_days(mock_db, mock_groq):
    cursor = MagicMock()
    cursor.fetchone.side_effect = [
        {"expiry_alert_days": 30},
        {"total": 1},
    ]
    cursor.fetchall.side_effect = [
        [],
        [{"name": "Test medicine", "batchNumber": "B-1", "expiryDate": "2026-09-15", "quantity": 5, "days_remaining": 20}],
    ]
    connection = MagicMock()
    connection.cursor.return_value = cursor
    mock_db.return_value = connection

    completion = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="- Test medicine expires in 20 days."))]
    )
    mock_groq.return_value.chat.completions.create.return_value = completion

    result = generate_morning_briefing("owner-1")

    assert result["status"] == "success"
    expiry_call = next(call for call in cursor.execute.call_args_list if "days_remaining" in call.args[0])
    assert expiry_call.args[1] == ("owner-1", 30)
    prompt = mock_groq.return_value.chat.completions.create.call_args.kwargs["messages"][1]["content"]
    assert "30 Day Alert Window" in prompt
    assert "'days_remaining': 20" in prompt

