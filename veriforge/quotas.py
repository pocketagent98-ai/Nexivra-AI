"""QuotaGovernor — free-tier and budget governance.

Rules (build spec sections 10 and 11):
- free-tier numbers are NOT permanent guarantees; budgets are configurable;
- never silently switch to paid usage — a paid model is refused unless it
  was explicitly authorised for the run;
- when the free budget is exhausted the governor raises BudgetExhausted so
  the caller can wait, ask for another authorised key, or stop;
- every decision is auditable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .audit import AuditLogger


class BudgetExhausted(RuntimeError):
    """The authorised free budget is exhausted. Never a silent upgrade."""


class PaidModelBlocked(RuntimeError):
    """A paid model was requested without explicit authorisation."""


@dataclass
class ModelBudget:
    requests: Optional[int] = None        # None = unlimited (but trackable)
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    paid: bool = False                    # must be opted in explicitly

    def clone(self) -> "ModelBudget":
        return ModelBudget(self.requests, self.input_tokens, self.output_tokens, self.paid)


@dataclass
class BudgetState:
    requests: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    failures: int = 0


class QuotaGovernor:
    def __init__(
        self,
        budgets: Dict[str, ModelBudget] | None = None,
        *,
        audit: Optional[AuditLogger] = None,
        default_paid_allowed: bool = False,
    ) -> None:
        self._budgets: Dict[str, ModelBudget] = {k: v.clone() for k, v in (budgets or {}).items()}
        self._state: Dict[str, BudgetState] = {}
        self._audit = audit

    # -- configuration ---------------------------------------------------

    def set_budget(self, provider: str, model: str, budget: ModelBudget) -> None:
        self._budgets[self._key(provider, model)] = budget.clone()

    def allow_paid(self, provider: str, model: str, *, allowed: bool = True) -> None:
        key = self._key(provider, model)
        b = self._budgets.setdefault(key, ModelBudget())
        b.paid = allowed

    # -- checks ------------------------------------------------------------

    @staticmethod
    def _key(provider: str, model: str) -> str:
        return f"{provider}/{model}"

    def _lookup(self, provider: str, model: str) -> Tuple[str, ModelBudget]:
        """Resolve the budget for a model, returning the state key it is
        accounted under (exact key, provider wildcard, or exact key with a
        default budget) so wildcard budgets aggregate across models."""
        key = self._key(provider, model)
        if key in self._budgets:
            return key, self._budgets[key]
        pkey = f"{provider}/*"
        if pkey in self._budgets:
            return pkey, self._budgets[pkey]
        return key, ModelBudget(paid=False)

    def _budget_for(self, provider: str, model: str) -> ModelBudget:
        return self._lookup(provider, model)[1]

    def check(self, provider: str, model: str) -> Tuple[bool, str]:
        """Return (allowed, reason). Never mutates state."""
        key, budget = self._lookup(provider, model)
        if budget.paid is False:
            # paid flag not set: model treated as free-tier unless declared paid
            pass
        state = self._state.get(key, BudgetState())
        if budget.requests is not None and state.requests >= budget.requests:
            return False, f"request budget exhausted ({state.requests}/{budget.requests})"
        if budget.input_tokens is not None and state.input_tokens >= budget.input_tokens:
            return False, "input token budget exhausted"
        if budget.output_tokens is not None and state.output_tokens >= budget.output_tokens:
            return False, "output token budget exhausted"
        return True, "ok"

    def reserve(self, provider: str, model: str) -> None:
        """Called just before a request. Raises when over budget."""
        allowed, reason = self.check(provider, model)
        budget = self._budget_for(provider, model)
        if not allowed:
            if budget.paid:
                raise BudgetExhausted(f"{self._key(provider, model)}: {reason}")
            raise BudgetExhausted(f"{self._key(provider, model)}: {reason}")
        key, _ = self._lookup(provider, model)
        st = self._state.setdefault(key, BudgetState())
        st.requests += 1
        if self._audit:
            self._audit.log("quota.reserve", provider=provider, model=model, requests=st.requests)

    def record(self, provider: str, model: str, *, input_tokens: int = 0, output_tokens: int = 0, failed: bool = False) -> None:
        key, _ = self._lookup(provider, model)
        st = self._state.setdefault(key, BudgetState())
        st.input_tokens += input_tokens
        st.output_tokens += output_tokens
        if failed:
            st.failures += 1

    def assert_paid_allowed(self, provider: str, model: str) -> None:
        """Explicit gate: paid usage must be consciously enabled, never silent."""
        budget = self._budget_for(provider, model)
        if budget.paid is not True:
            raise PaidModelBlocked(
                f"{self._key(provider, model)} is marked paid; enable it explicitly "
                "(QuotaGovernor.allow_paid) or use a free-tier model."
            )

    # -- reporting -----------------------------------------------------------

    def usage(self) -> Dict[str, Dict[str, int]]:
        out: Dict[str, Dict[str, int]] = {}
        for key, st in self._state.items():
            out[key] = {
                "requests": st.requests,
                "input_tokens": st.input_tokens,
                "output_tokens": st.output_tokens,
                "failures": st.failures,
            }
        return out

    def usage_for(self, provider: str, model: str) -> Dict[str, int]:
        return self.usage().get(self._key(provider, model), {
            "requests": 0, "input_tokens": 0, "output_tokens": 0, "failures": 0,
        })
