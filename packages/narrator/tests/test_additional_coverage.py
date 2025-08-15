import logging
import os
import pytest
import pytest_asyncio
from narrator import Thread, Message, Attachment, ThreadStore
from narrator.storage.file_store import FileStore


pytest_plugins = ('pytest_asyncio',)


@pytest.mark.asyncio
async def test_find_by_attributes_boolean_and_null_sqlite():
    store = await ThreadStore.create(":memory:")
    t = Thread(id="tbool", title="Bool/Null")
    t.attributes = {"flag": True, "missing": None, "str": "yes"}
    await store.save(t)

    res_true = await store.find_by_attributes({"flag": True})
    assert len(res_true) == 1 and res_true[0].id == "tbool"

    res_false = await store.find_by_attributes({"flag": False})
    assert len(res_false) == 0

    res_null = await store.find_by_attributes({"missing": None})
    assert len(res_null) == 1 and res_null[0].id == "tbool"


@pytest.mark.asyncio
async def test_find_by_platform_basic_sqlite():
    store = await ThreadStore.create(":memory:")
    t = Thread(id="tplat", title="Plat")
    # platforms inner values must be strings per model typing
    t.platforms = {"slack": {"archived": "false", "ts": "123", "channel": "C1"}}
    await store.save(t)

    res = await store.find_by_platform("slack", {"channel": "C1"})
    assert len(res) == 1 and res[0].id == "tplat"


@pytest.mark.asyncio
async def test_attachment_url_enrichment(tmp_path):
    # Use a temp FileStore
    store = await FileStore.create(base_path=str(tmp_path))

    thread = Thread(id="tatt", title="Attach URL")
    msg = Message(role="user", content="file")
    att = Attachment(filename="x.txt", content=b"abc", mime_type="text/plain")
    msg.attachments.append(att)
    thread.add_message(msg)

    # Persist through SQL backend to trigger process_and_store
    sql_store = await ThreadStore.create(":memory:")
    # Monkeypatch SQLBackend to use our temp FileStore by patching FileStore initializer if needed
    # Instead, we verify attributes.url after normal save (uses default base path)
    await sql_store.save(thread)

    # After save, in-memory object should have storage info and URL in attributes
    saved_att = thread.messages[0].attachments[0]
    assert saved_att.storage_path
    assert saved_att.attributes and "url" in saved_att.attributes

    # Retrieve and ensure the attribute is preserved
    loaded = await sql_store.get(thread.id)
    loaded_att = loaded.messages[0].attachments[0]
    assert loaded_att.attributes and "url" in loaded_att.attributes


def test_logging_does_not_override_global_config(caplog):
    # Configure root logger to WARNING and attach a handler
    logging.getLogger().setLevel(logging.WARNING)
    with caplog.at_level(logging.WARNING):
        # Importing/getting logger should not force basicConfig
        from narrator.utils.logging import get_logger
        logger = get_logger(__name__)
        logger.debug("this should not appear")
        # Ensure no DEBUG records captured
        assert not any(rec.levelno < logging.WARNING for rec in caplog.records)


@pytest.mark.asyncio
async def test_file_store_list_files_reconstructs_ids(tmp_path):
    fs = await FileStore.create(base_path=str(tmp_path))
    m1 = await fs.save(b"hello", "one.txt")
    m2 = await fs.save(b"world", "two.txt")
    ids = await fs.list_files()
    assert m1["id"][:2] + m1["id"][2:] in ids  # reconstructed format (prefix + stem)
    assert m2["id"][:2] + m2["id"][2:] in ids


@pytest.mark.asyncio
async def test_multiple_saves_do_not_duplicate_attachments():
    store = await ThreadStore.create(":memory:")
    thread = Thread(id="tdedup", title="Dedup")
    msg = Message(role="user", content="hi")
    msg.attachments.append(Attachment(filename="a.txt", content=b"x", mime_type="text/plain"))
    thread.add_message(msg)

    await store.save(thread)
    # Save again without modifying attachments
    await store.save(thread)
    loaded = await store.get(thread.id)
    # Should still be exactly one attachment
    assert len(loaded.messages[0].attachments) == 1


