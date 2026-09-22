import pytest

from nexivra.quotas import BudgetExhausted, ModelBudget, PaidModelBlocked, QuotaGovernor


def test_reserve_and_record_usage():
    gov = QuotaGovernor({"p/m": ModelBudget(requests=3)})
    for _ in range(3):
        gov.reserve("p", "m")
    with pytest.raises(BudgetExhausted):
        gov.reserve("p", "m")
    assert gov.usage_for("p", "m")["requests"] == 3


def test_token_budgets():
    gov = QuotaGovernor({"p/m": ModelBudget(output_tokens=100)})
    gov.reserve("p", "m")
    gov.record("p", "m", output_tokens=90)
    gov.reserve("p", "m")
    gov.record("p", "m", output_tokens=20)
    with pytest.raises(BudgetExhausted):
        gov.reserve("p", "m")


def test_provider_wildcard_budget():
    gov = QuotaGovernor({"nvidia/*": ModelBudget(requests=1)})
    gov.reserve("nvidia", "any-model")
    with pytest.raises(BudgetExhausted):
        gov.reserve("nvidia", "other-model")


def test_paid_model_blocked_by_default():
    gov = QuotaGovernor()
    with pytest.raises(PaidModelBlocked):
        gov.assert_paid_allowed("zai", "glm-5-max")
    gov.allow_paid("zai", "glm-5-max")
    gov.assert_paid_allowed("zai", "glm-5-max")


def test_failed_requests_tracked():
    gov = QuotaGovernor()
    gov.reserve("p", "m")
    gov.record("p", "m", failed=True)
    assert gov.usage_for("p", "m")["failures"] == 1


def test_check_is_read_only():
    gov = QuotaGovernor({"p/m": ModelBudget(requests=1)})
    allowed, _ = gov.check("p", "m")
    assert allowed
    assert gov.usage_for("p", "m")["requests"] == 0
