from cherrycola import backends as be
from cherrycola import chats

import pytest


def test_save_load_list_delete(tmp_path):
    a = chats.new_chat("qwen3:4b")
    a.title = "first"
    a.messages = [{"role": "user", "content": "hi"},
                  {"role": "assistant", "content": "hello",
                   "sources": ["https://example.com"]}]
    chats.save(a, tmp_path)
    b = chats.new_chat("qwen3:8b")
    b.id = b.id[:-4] + "beef"
    chats.save(b, tmp_path)
    (tmp_path / "junk.json").write_text("{not json")

    listed = chats.list_chats(tmp_path)
    assert [c.id for c in listed] == [b.id, a.id]
    got = chats.load(a.id, tmp_path)
    assert got.title == "first" and got.messages == a.messages

    chats.delete(a.id, tmp_path)
    assert [c.id for c in chats.list_chats(tmp_path)] == [b.id]


def test_bad_id_refused(tmp_path):
    with pytest.raises(ValueError):
        chats.load("../../etc/passwd", tmp_path)


def test_model_messages_drop_sources():
    c = chats.new_chat("m")
    c.messages = [{"role": "user", "content": "q"},
                  {"role": "assistant", "content": "a", "sources": ["u"]}]
    assert chats.model_messages(c) == [
        {"role": "system", "content": be.SYSTEM_PROMPT},
        {"role": "user", "content": "q"},
        {"role": "assistant", "content": "a"},
    ]


def test_title_for():
    assert chats.title_for("  what   is zram? ") == "what is zram?"
    assert chats.title_for("word " * 20, limit=12) == "word word…"


def test_to_markup():
    text = "Use **pacman** & `yay -S x`:\n```sh\nsudo <cmd>\n```\nok"
    assert chats.to_markup(text) == (
        "Use <b>pacman</b> &amp; <tt>yay -S x</tt>:\n"
        "<tt>sudo &lt;cmd&gt;</tt>\nok")
