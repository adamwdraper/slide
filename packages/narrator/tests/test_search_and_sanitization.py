import pytest
import pytest_asyncio
from narrator import Thread, Message, ThreadStore


pytest_plugins = ('pytest_asyncio',)


@pytest.mark.asyncio
async def test_memory_backend_find_messages_multiple_matches():
    store = await ThreadStore.create()  # Memory backend

    # Thread 1 with two matching messages
    t1 = Thread(id="t1", title="T1")
    t1.add_message(Message(role="user", content="hi", source={"id": "u1", "type": "user"}))
    t1.add_message(Message(role="assistant", content="ok", source={"id": "agent", "type": "agent"}))
    t1.add_message(Message(role="user", content="again", source={"id": "u1", "type": "user"}))
    await store.save(t1)

    # Thread 2 with one matching message
    t2 = Thread(id="t2", title="T2")
    t2.add_message(Message(role="user", content="hello", source={"id": "u1", "type": "user"}))
    await store.save(t2)

    # Search by source.id
    msgs = await store.find_messages_by_attribute("source.id", "u1")
    assert len(msgs) == 3
    assert all(isinstance(m, Message) for m in msgs)


@pytest.mark.asyncio
async def test_sqlite_backend_find_messages_by_attribute_with_and_without_source_prefix():
    store = await ThreadStore.create(":memory:")

    thread = Thread(id="tsql", title="SQL Path Test")
    thread.add_message(Message(role="user", content="one", source={"id": "abc", "type": "user"}))
    thread.add_message(Message(role="assistant", content="two", source={"id": "def", "type": "agent"}))
    await store.save(thread)

    # Using full path with 'source.' prefix
    msgs1 = await store.find_messages_by_attribute("source.id", "abc")
    assert len(msgs1) == 1
    assert msgs1[0].content == "one"

    # Using path relative to source column (without prefix)
    msgs2 = await store.find_messages_by_attribute("id", "def")
    assert len(msgs2) == 1
    assert msgs2[0].content == "two"


@pytest.mark.asyncio
async def test_sqlite_backend_find_by_attributes_key_sanitization_raises():
    store = await ThreadStore.create(":memory:")
    t = Thread(id="ta", title="Attr Test")
    t.attributes = {"safe_key": "value"}
    await store.save(t)

    # Invalid key should raise ValueError due to sanitization
    with pytest.raises(ValueError):
        await store.find_by_attributes({"bad-key": "value"})


@pytest.mark.asyncio
async def test_sqlite_backend_find_by_platform_key_sanitization_raises():
    store = await ThreadStore.create(":memory:")
    t = Thread(id="tp", title="Platform Test")
    t.platforms = {"slack": {"channel": "C123"}}
    await store.save(t)

    # Invalid platform name
    with pytest.raises(ValueError):
        await store.find_by_platform("slack-name", {"channel": "C123"})

    # Invalid property key
    with pytest.raises(ValueError):
        await store.find_by_platform("slack", {"bad-key": "C123"})


