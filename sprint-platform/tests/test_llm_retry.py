"""Tests that call_llm retries with backoff when providers fail transiently."""
import pytest
from unittest.mock import patch
from services.llm import call_llm


def test_retries_three_times_when_all_providers_fail():
    """call_llm with max_retries=3 should try all providers 3 times."""
    env_attempts = [0]
    def counting_env_call(prompt, timeout):
        env_attempts[0] += 1
        return None
    with patch("services.llm._env_call", side_effect=counting_env_call):
        with patch("services.llm._openrouter_call", return_value=None):
            with patch("services.llm._omniroute_call", return_value=None):
                with patch("time.sleep"):
                    result = call_llm("test", timeout=5, max_retries=3, backoff_base=0.01)
    assert result is None
    assert env_attempts[0] == 3


def test_succeeds_on_second_attempt():
    """If the first attempt fails but second succeeds, result should be returned."""
    call_count = [0]
    def flaky_call(prompt, timeout):
        call_count[0] += 1
        if call_count[0] == 1:
            return None
        return "success on retry"
    with patch("services.llm._env_call", side_effect=flaky_call):
        result = call_llm("test", timeout=5, max_retries=3, backoff_base=0.01)
    assert result == "success on retry"


def test_no_retry_when_first_succeeds():
    """If the first provider succeeds, no retries should happen."""
    call_count = [0]
    def first_success(prompt, timeout):
        call_count[0] += 1
        return "immediate success"
    with patch("services.llm._env_call", side_effect=first_success):
        with patch("time.sleep") as mock_sleep:
            result = call_llm("test", timeout=5, max_retries=3, backoff_base=1)
    assert result == "immediate success"
    assert mock_sleep.call_count == 0
    assert call_count[0] == 1
