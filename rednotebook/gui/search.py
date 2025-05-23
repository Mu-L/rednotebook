# -----------------------------------------------------------------------
# Copyright (c) 2008-2024 Jendrik Seipp
#
# RedNotebook is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# RedNotebook is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with RedNotebook; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
# -----------------------------------------------------------------------

from xml.sax.saxutils import escape

from gi.repository import GLib, GObject, Gtk

from rednotebook.gui.customwidgets import CustomComboBoxEntry, CustomListView
from rednotebook.util import dates


class SearchComboBox(CustomComboBoxEntry):
    def __init__(self, combo_box, main_window):
        CustomComboBoxEntry.__init__(self, combo_box)

        self.main_window = main_window
        self.journal = main_window.journal

        self.entry.set_icon_from_icon_name(1, "edit-clear-symbolic")
        self.entry.connect("icon-press", lambda *args: self.set_active_text(""))

        self.entry.connect("changed", self.on_entry_changed)
        self.entry.connect("activate", self.on_entry_activated)

    def on_entry_changed(self, entry):
        """Called when the entry changes."""
        search_text = self.get_active_text()
        if self.journal.config.read("instantSearch"):
            self.search(search_text)
        elif not search_text:
            self.search("")

        replace_box = self.main_window.replace_box
        if search_text and self.main_window.search_tree_view.has_results():
            replace_box.old_data = search_text
            replace_box.show()
        else:
            replace_box.hide()
            replace_box.clear()

    def on_entry_activated(self, entry):
        """Called when the user hits enter."""
        search_text = self.get_active_text()
        self.add_entry(search_text)
        self.search(search_text)

    def search(self, search_text):
        # Highlight all occurrences in the current day's text.
        self.main_window.highlight_text(search_text)

        # Scroll to query.
        if search_text:
            GLib.idle_add(self.main_window.day_text_field.scroll_to_text, search_text)

        tags = []
        queries = []
        for part in search_text.split():
            if part.startswith("#"):
                tags.append(part.lstrip("#").lower())
            else:
                queries.append(part)
        # Preserve original white space if there are no tags.
        query = " ".join(queries) if tags else search_text

        self.main_window.search_tree_view.update_data(query, tags)

        # Without the following, showing the search results sometimes lets the
        # search entry lose focus and search phrases are added to a day's text.
        if not self.entry.has_focus():
            self.entry.grab_focus()

    def update_search_results(self):
        self.search(self.get_active_text())


class ReplaceBox(Gtk.Box):
    def __init__(self, main_window, **properties):
        super().__init__(**properties)

        self.old_data = ""

        self.journal = main_window.journal

        self.text_field = Gtk.Entry()
        self.text_field.set_placeholder_text(_("Replace"))
        self.text_field.connect("activate", self.on_entry_activated)
        self.text_field.show()

        self.pack_start(self.text_field, True, True, 0)
        self.set_orientation(Gtk.Orientation.HORIZONTAL)

    def on_entry_activated(self, _):
        """Called when the user hits enter."""

        new_data = self.text_field.get_text()
        if new_data == self.old_data:
            return

        self.journal.replace_all(self.old_data, new_data)

    def clear(self):
        self.text_field.set_text("")
        self.old_data = ""


class SearchTreeView(CustomListView):
    def __init__(self, main_window, always_show_results):
        CustomListView.__init__(self, [(_("Date"), str), (_("Text"), str)])
        self.main_window = main_window
        self.journal = self.main_window.journal
        self.always_show_results = always_show_results
        self.tree_store = self.get_model()

        self.cursor_changed_signal = self.connect(
            "cursor_changed", self.on_cursor_changed
        )

    def has_results(self):
        return len(self.tree_store) > 0

    def clear_search_results(self):
        # Don't switch the current day while clearing the search results.
        with GObject.signal_handler_block(self, self.cursor_changed_signal):
            self.tree_store.clear()

    def update_data(self, search_text, tags):
        self.clear_search_results()

        if not self.always_show_results and not tags and not search_text:
            self.main_window.cloud.show()
            self.main_window.search_scroll.hide()
            return

        self.main_window.cloud.hide()
        self.main_window.search_scroll.show()

        for date_string, entries in self.journal.search(search_text, tags):
            for entry in entries:
                entry = escape(entry)
                entry = entry.replace("STARTBOLD", "<b>").replace("ENDBOLD", "</b>")
                self.tree_store.append([date_string, entry])

    def on_cursor_changed(self, treeview):
        """Move to the selected day when user clicks on it."""
        model, paths = self.get_selection().get_selected_rows()
        if not paths:
            return
        date_string = self.tree_store[paths[0]][0]
        new_date = dates.get_date_from_date_string(date_string)
        self.journal.change_date(new_date)
