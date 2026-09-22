import pytest

from nexivra.adapters import AdapterError, ChatMessage
from nexivra.gateway import ModelProfile, RouterError, UniversalModelGateway
from nexivra.quotas import BudgetExhausted, ModelBudget, QuotaGovernor

from conftest import FailingAdapter, build_gateway


@pytest.mark.asyncio
async def test_chat_routes_through_registered_profile():
    gw, audit, _ = build_gateway(default="hello there")
    result = await gw.chat([ChatMessage(role="user", content="hi")], task="test")
    assert result.text == "hello there"
    assert result.provider == "static"
    assert audit.events_of("model.call")[0]["task"] == "test"


@pytest.mark.asyncio
async def test_fallback_on_retryable_error():
    gw, audit, _ = build_gateway(failing_first=True)
    result = await gw.chat([ChatMessage(role="user", content="hi")], task="test")
    assert result.provider == "static"
    assert len(audit.events_of("model.error")) == 1
    assert audit.events_of("model.call")


@pytest.mark.asyncio
async def test_all_routes_failed_raises_router_error():
    gw = UniversalModelGateway()
    from nexivra.adapters import StaticAdapter
    gw.register_adapter(FailingAdapter())
    gw.add_profile(ModelProfile(provider="failing", model="f-1"))
    with pytest.raises(RouterError):
        await gw.chat([ChatMessage(role="user", content="hi")])


@pytest.mark.asyncio
async def test_quota_exhaustion_blocks_silently_paid_upgrade():
    quotas = QuotaGovernor({"static/*": ModelBudget(requests=1)})
    from nexivra.adapters import StaticAdapter
    gw = UniversalModelGateway(quotas=quotas)
    gw.register_adapter(StaticAdapter(name="static"))
    gw.add_profile(ModelProfile(provider="static", model="static-1"))
    first = await gw.chat([ChatMessage(role="user", content="a")])
    assert first.text == "ok"
    with pytest.raises(BudgetExhausted):
        await gw.chat([ChatMessage(role="user", content="b")])


@pytest.mark.asyncio
async def test_stream_yields_text():
    gw, _, _ = build_gateway(default="chunked text")
    chunks = [c async for c in gw.stream([ChatMessage(role="user", content="hi")])]
    assert chunks == ["chunked text"]


@pytest.mark.asyncio
async def test_capability_filtering():
    gw, _, _ = build_gateway()
    with pytest.raises(RouterError):
        await gw.chat([ChatMessage(role="user", content="hi")], capability="vision")


def test_unknown_provider_models():
    gw, _, _ = build_gateway()
    with pytest.raises(RouterError):
        import asyncio
        asyncio.run(gw.models("unknown"))


@pytest.mark.asyncio
async def test_profiles_sorted_by_priority():
    from nexivra.adapters import StaticAdapter
    gw = UniversalModelGateway()
    gw.register_adapter(StaticAdapter(name="a"))
    gw.register_adapter(StaticAdapter(name="b"))
    gw.add_profile(ModelProfile(provider="b", model="m", priority=1))
    gw.add_profile(ModelProfile(provider="a", model="m", priority=5))
    assert [p.provider for p in gw.profiles()] == ["b", "a"]
