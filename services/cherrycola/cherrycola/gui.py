"""CherryCola chat: a GTK4 / libadwaita window for local models.

Saved chats on the left, the conversation on the right, the model picker in
the header and a web search toggle (free DuckDuckGo search, read locally).
Network work runs on threads; widgets are only touched through GLib.idle_add.
"""

from __future__ import annotations

import sys
import threading

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk, Pango  # noqa: E402

from . import backends as be  # noqa: E402
from . import chats, cli, web  # noqa: E402
from . import config as config_mod  # noqa: E402

APP_ID = "org.graceos.CherryCola"
CSS = """
.bubble { padding: 10px 14px; border-radius: 16px; }
.bubble.user { background: alpha(@accent_bg_color, 0.30); }
.bubble.assistant { background: @card_bg_color; }
.sources { font-size: 0.9em; }
.sources button { padding: 2px 6px; min-height: 0; }
"""


def _label(text: str = "", **kw) -> Gtk.Label:
    lbl = Gtk.Label(label=text, wrap=True, selectable=True, xalign=0,
                    wrap_mode=Pango.WrapMode.WORD_CHAR, **kw)
    lbl.set_can_focus(False)  # selectable labels steal focus from the entry
    return lbl


class ChatWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="CherryCola",
                         default_width=980, default_height=720)
        self.cfg = config_mod.load_config()
        self.backend = ""
        self.models: list[str] = []
        self.chat = chats.new_chat(self.cfg.model)
        self._job: threading.Event | None = None  # set = stop the answer
        self._partial = ""
        self._sources: list[str] = []
        self._filling = False
        self._at_bottom = True

        # Sidebar: saved chats.
        self.chat_list = Gtk.ListBox(css_classes=["navigation-sidebar"])
        self.chat_list.connect("row-activated", self._on_row)
        new_btn = Gtk.Button(icon_name="list-add-symbolic",
                             tooltip_text="New chat (Ctrl+N)")
        new_btn.connect("clicked", lambda *_: self.new_chat())
        side_header = Adw.HeaderBar()
        side_header.pack_start(new_btn)
        side = Adw.ToolbarView(content=Gtk.ScrolledWindow(
            child=self.chat_list, vexpand=True))
        side.add_top_bar(side_header)
        self.side = side

        # Conversation.
        self.model_names = Gtk.StringList()
        self.model_drop = Gtk.DropDown(model=self.model_names,
                                       tooltip_text="Model")
        self.model_drop.connect("notify::selected", self._on_model)
        self.web_btn = Gtk.ToggleButton(
            icon_name="web-browser-symbolic",
            tooltip_text="Search the web for each question "
                         "(free, pages are read on this PC)")
        del_btn = Gtk.Button(icon_name="user-trash-symbolic",
                             tooltip_text="Delete this chat")
        del_btn.connect("clicked", self._on_delete)
        header = Adw.HeaderBar(title_widget=self.model_drop)
        header.pack_end(self.web_btn)
        header.pack_end(del_btn)
        self.banner = Adw.Banner()
        self.banner.connect("button-clicked", self._on_banner)

        self.messages = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,
                                spacing=12, margin_top=18, margin_bottom=18,
                                margin_start=18, margin_end=18)
        self.scroller = Gtk.ScrolledWindow(
            vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER,
            child=Adw.Clamp(maximum_size=780, child=self.messages))
        adj = self.scroller.get_vadjustment()
        adj.connect("value-changed", self._on_scrolled)
        adj.connect("changed", self._follow)

        self.entry = Gtk.Entry(placeholder_text="Ask anything", hexpand=True)
        self.entry.connect("activate", self._on_send)
        self.send_btn = Gtk.Button(icon_name="go-up-symbolic",
                                   tooltip_text="Send",
                                   css_classes=["suggested-action", "circular"])
        self.send_btn.connect("clicked", self._on_send)
        row = Gtk.Box(spacing=8, margin_top=6, margin_bottom=12,
                      margin_start=12, margin_end=12)
        row.append(self.entry)
        row.append(self.send_btn)

        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        body.append(self.scroller)
        body.append(Adw.Clamp(maximum_size=780, child=row))
        main = Adw.ToolbarView(content=body)
        main.add_top_bar(header)
        main.add_top_bar(self.banner)

        split = Adw.NavigationSplitView(min_sidebar_width=170, max_sidebar_width=260,
            sidebar=Adw.NavigationPage(title="Chats", child=side),
            content=Adw.NavigationPage(title="CherryCola", child=main))
        self.toasts = Adw.ToastOverlay(child=split)
        self.set_content(self.toasts)

        new = Gio.SimpleAction(name="new")
        new.connect("activate", lambda *_: self.new_chat())
        self.add_action(new)
        app.set_accels_for_action("win.new", ["<Control>n"])

        self.refresh_list()
        self.render()
        self.entry.grab_focus()
        self.probe()

    # ---- backend ---------------------------------------------------------

    def probe(self):
        """Find the engine, start Ollama if needed, list the models."""
        self.banner.set_revealed(False)
        self.entry.set_placeholder_text("Starting the model server…")

        def work():
            backend = be.resolve_backend(self.cfg)
            rc = cli.ensure_running(backend, self.cfg)
            try:
                models = be.list_models(backend, self.cfg) if rc == 0 else []
            except be.BackendError:
                models, rc = [], cli.EXIT_UNREACHABLE
            default = be.resolve_model(backend, self.cfg)
            GLib.idle_add(self._probed, backend, rc, models, default)

        threading.Thread(target=work, daemon=True).start()

    def _probed(self, backend, rc, models, default):
        self.backend, self.models = backend, models
        self.entry.set_placeholder_text("Ask anything")
        if rc != cli.EXIT_OK:
            name = "LM Studio" if backend == "lmstudio" else "Ollama"
            self._banner(f"Can't reach {name}", "Retry")
            return
        if not self.chat.model:
            self.chat.model = default
        names = sorted(set(models) | {self.chat.model, default})
        self._filling = True
        self.model_names.splice(0, self.model_names.get_n_items(), names)
        self.model_drop.set_selected(names.index(self.chat.model))
        self._filling = False
        self._check_model()

    def _check_model(self):
        model = self.chat.model
        if not self.backend or model in self.models:
            self.banner.set_revealed(False)
            return
        size = config_mod.MODEL_SIZES_GB.get(model)
        about = f" (about {size} GB)" if size else ""
        if self.backend == "ollama":
            self._banner(f"{model} isn't downloaded yet{about}", "Download")
        else:
            self._banner(f"Load {model} in the LM Studio app", None)

    def _banner(self, title, button):
        self.banner.set_title(title)
        self.banner.set_button_label(button)
        self.banner.set_revealed(True)

    def _on_banner(self, *_):
        if self.banner.get_button_label() == "Retry":
            self.probe()
        elif self.banner.get_button_label() == "Download":
            self.download(self.chat.model)

    def download(self, model):
        self._banner(f"Downloading {model}…", None)

        def progress(obj):
            total, done = obj.get("total"), obj.get("completed")
            # "pulling <layer hash>" means nothing to people; show the percent.
            what = (f"{100 * done // total}%" if total and done
                    else obj.get("status", ""))
            GLib.idle_add(self.banner.set_title,
                          f"Downloading {model}… {what}")

        def work():
            try:
                be.pull_model(self.backend, self.cfg, model, progress)
                GLib.idle_add(self.probe)
            except be.BackendError as exc:
                GLib.idle_add(self._banner, f"Download failed: {exc}",
                              "Download")

        threading.Thread(target=work, daemon=True).start()

    def _on_model(self, *_):
        item = self.model_drop.get_selected_item()
        if self._filling or item is None:
            return
        self.chat.model = item.get_string()
        if self.chat.messages:
            chats.save(self.chat)
        self._check_model()

    # ---- chats -----------------------------------------------------------

    def refresh_list(self):
        self.chat_list.remove_all()
        for c in chats.list_chats():
            row = Gtk.ListBoxRow(child=Gtk.Label(
                label=c.title, xalign=0, ellipsize=Pango.EllipsizeMode.END))
            row.set_name(c.id)
            self.chat_list.append(row)
            if c.id == self.chat.id:
                self.chat_list.select_row(row)

    def _on_row(self, _box, row):
        try:
            self.chat = chats.load(row.get_name())
        except (OSError, ValueError) as exc:
            self.toast(f"Couldn't open that chat: {exc}")
            return
        self.render()
        self._select_model(self.chat.model)
        self.entry.grab_focus()
        self._scroll_end()

    def new_chat(self):
        if self._job:
            return
        self.chat = chats.new_chat(self._current_model())
        self.chat_list.unselect_all()
        self.render()
        self.entry.grab_focus()

    def _on_delete(self, *_):
        if self._job:
            return
        chats.delete(self.chat.id)
        self.new_chat()
        self.refresh_list()

    def _current_model(self):
        item = self.model_drop.get_selected_item()
        return item.get_string() if item else self.cfg.model

    def _select_model(self, model):
        names = [self.model_names.get_string(i)
                 for i in range(self.model_names.get_n_items())]
        if model and model not in names:
            self.model_names.append(model)
            names.append(model)
        if model:
            self.model_drop.set_selected(names.index(model))
        self._check_model()

    # ---- conversation view ----------------------------------------------

    def render(self):
        while child := self.messages.get_first_child():
            self.messages.remove(child)
        if not self.chat.messages:
            self.messages.append(Adw.StatusPage(
                icon_name="org.graceos.CherryCola", title="Ask CherryCola",
                description="Answers come from a model running on this PC. "
                            "Turn on web search (the globe) to look things "
                            "up for free.", vexpand=True,
                css_classes=["compact"]))
            return
        for m in self.chat.messages:
            lbl = self._bubble(m["role"])
            if m["role"] == "assistant":
                lbl.set_markup(chats.to_markup(m["content"]))
                self._add_sources(m.get("sources") or [])
            else:
                lbl.set_text(m["content"])

    def _bubble(self, role) -> Gtk.Label:
        first = self.messages.get_first_child()
        if isinstance(first, Adw.StatusPage):
            self.messages.remove(first)
        lbl = _label(css_classes=["bubble", role])
        if role == "user":
            lbl.set_halign(Gtk.Align.END)
            lbl.set_margin_start(80)
        else:
            lbl.set_halign(Gtk.Align.START)
        self.messages.append(lbl)
        return lbl

    def _add_sources(self, urls):
        if not urls:
            return
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,
                      css_classes=["sources"], margin_start=8)
        for i, url in enumerate(urls, 1):
            short = url.split("://", 1)[-1]
            short = short if len(short) < 70 else short[:67] + "…"
            link = Gtk.LinkButton(uri=url, label=f"[{i}] {short}",
                                  halign=Gtk.Align.START)
            link.get_child().set_ellipsize(Pango.EllipsizeMode.END)
            box.append(link)
        self.messages.append(box)

    def _on_scrolled(self, adj):
        self._at_bottom = adj.get_value() >= (
            adj.get_upper() - adj.get_page_size() - 40)

    def _follow(self, adj):
        if self._at_bottom:
            adj.set_value(adj.get_upper() - adj.get_page_size())

    def _scroll_end(self):
        # After the next layout pass, so the new rows are counted.
        def go():
            adj = self.scroller.get_vadjustment()
            adj.set_value(adj.get_upper() - adj.get_page_size())
        GLib.timeout_add(120, go)

    def toast(self, text):
        self.toasts.add_toast(Adw.Toast(title=text, timeout=6))

    # ---- asking ----------------------------------------------------------

    def _on_send(self, *_):
        if self._job:
            self._finish(self._job, self._partial, self._sources, None)
            return
        question = self.entry.get_text().strip()
        if not question or not self.backend:
            return
        if self.chat.model not in self.models:
            self._check_model()
            return
        self.entry.set_text("")
        if not self.chat.messages:
            self.chat.title = chats.title_for(question)
        self._bubble("user").set_text(question)
        self.chat.messages.append({"role": "user", "content": question})
        self.answer_label = self._bubble("assistant")
        self.answer_label.set_text("…")
        self._at_bottom = True
        job = self._job = threading.Event()
        self._partial, self._sources = "", []
        self._busy(True)
        threading.Thread(target=self._answer, daemon=True, args=(
            job, question, chats.model_messages(self.chat),
            self.web_btn.get_active())).start()

    def _answer(self, job, question, messages, use_web):
        sources: list[str] = []
        if use_web:
            GLib.idle_add(self._status, job, "Searching the web…")
            try:
                results = web.search(question, self.cfg)
            except be.BackendError as exc:
                GLib.idle_add(self.toast, f"Web search failed: {exc}")
                results = []
            if results:
                n = min(len(results), self.cfg.web_pages)
                GLib.idle_add(self._status, job, f"Reading {n} pages…")
                pages = web.fetch_many([r.url for r in results[:n]],
                                       max_chars=4000)
                # The sources go in the system prompt; history stays plain.
                messages = web.web_messages(question, results, pages)[:1] + \
                    messages[1:]
                sources = [r.url for r in results]
        text, stripper = "", be.ThinkStripper()
        try:
            stream = be.iter_chat_chunks(self.backend, self.cfg,
                                         self.chat.model, messages)
            try:
                for chunk in stream:
                    if job.is_set():
                        return
                    text += stripper.feed(chunk)
                    GLib.idle_add(self._show, job, text, sources)
            finally:
                stream.close()
            text += stripper.flush()
        except be.BackendError as exc:
            GLib.idle_add(self._finish, job, "", [], str(exc))
            return
        GLib.idle_add(self._finish, job, text, sources, None)

    def _status(self, job, text):
        if job is self._job:
            self.answer_label.set_text(text)

    def _show(self, job, text, sources):
        if job is self._job:
            self._partial, self._sources = text, sources
            self.answer_label.set_text(text or "…")

    def _finish(self, job, text, sources, error):
        if job is not self._job:
            return  # already stopped
        job.set()
        self._job = None
        self._busy(False)
        text = text.strip()
        # Failed, or stopped before any answer text: give the question back.
        if error or not text:
            question = self.chat.messages.pop()["content"]
            self.render()
            if not self.entry.get_text():
                self.entry.set_text(question)
            if error:
                self.toast(f"No answer: {error}")
            return
        self.chat.messages.append(
            {"role": "assistant", "content": text, "sources": sources})
        self.answer_label.set_markup(chats.to_markup(text))
        self._add_sources(sources)
        if self._at_bottom:
            self._scroll_end()
        chats.save(self.chat)
        self.refresh_list()

    def _busy(self, busy):
        self.send_btn.set_icon_name(
            "media-playback-stop-symbolic" if busy else "go-up-symbolic")
        self.send_btn.set_tooltip_text("Stop" if busy else "Send")
        self.side.set_sensitive(not busy)
        if not busy:
            self.entry.grab_focus()


class ChatApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID,
                         flags=Gio.ApplicationFlags.DEFAULT_FLAGS)

    def do_startup(self):
        Adw.Application.do_startup(self)
        Adw.StyleManager.get_default().set_color_scheme(
            Adw.ColorScheme.FORCE_DARK)
        css = Gtk.CssProvider()
        css.load_from_string(CSS)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), css,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def do_activate(self):
        win = self.get_active_window() or ChatWindow(self)
        win.present()


def main(argv=None) -> int:
    return ChatApp().run(argv if argv is not None else sys.argv)
