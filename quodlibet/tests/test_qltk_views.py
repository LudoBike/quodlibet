# -*- coding: utf-8 -*-
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as
# published by the Free Software Foundation

from tests import TestCase
from quodlibet.qltk.views import AllTreeView, BaseView, TreeViewColumn, \
    DragScroll, MultiDragTreeView, RCMTreeView, DragIconTreeView
import quodlibet.config
from quodlibet.util import is_windows
from gi.repository import Gtk, Gdk

from . import skipIf
from .helper import send_key_click, visible, send_button_click, realized


def _fill_view(view):
    """Adds a model with 100 text rows and a column to display them.

    Returns the model.
    """

    model = Gtk.ListStore(str)
    column = Gtk.TreeViewColumn("foo")
    title = Gtk.CellRendererText()
    column.pack_start(title, True)
    column.add_attribute(title, "text", 0)
    view.append_column(column)
    for x in xrange(100):
        model.append(row=["foo"])
    view.set_model(model)
    return model


class THintedTreeView(TestCase):
    def setUp(self):
        quodlibet.config.init()
        self.c = AllTreeView()

    def test_exists(self):
        self.failUnless(self.c)

    def tearDown(self):
        self.c.destroy()
        quodlibet.config.quit()


class TBaseView(TestCase):
    def setUp(self):
        self.m = Gtk.ListStore(str)
        self.c = BaseView(model=self.m)

    def test_selection_changed(self):
        events = []

        def on_selection_changed(*args):
            events.append(args)

        self.c.connect("selection-changed", on_selection_changed)

        self.m.append(row=["foo"])
        self.c.get_selection().set_mode(Gtk.SelectionMode.MULTIPLE)
        self.c.get_selection().select_all()
        self.assertTrue(events)

    def test_remove(self):
        self.m.append(row=["foo"])
        self.c.remove_iters([self.m[0].iter])
        self.failIf(len(self.m))

        self.m.append(row=["foo"])
        self.c.remove_iters([])
        self.failUnless(len(self.m))

        self.c.remove_paths([self.m[0].path])
        self.failIf(len(self.m))

    def test_key_events(self):
        with visible(self.c):
            send_key_click(self.c, "<Primary>Right")
            send_key_click(self.c, "<Primary>Left")

    def test_select_func(self):
        self.m.append(row=["foo"])
        self.m.append(row=["bar"])
        self.failUnless(self.c.select_by_func(lambda r: True))
        self.failIf(self.c.select_by_func(lambda r: False))
        self.c.select_by_func(lambda r: False, scroll=False, one=True)

    def test_iter_select_func(self):
        # empty
        self.assertFalse(self.c.iter_select_by_func(lambda r: False))
        self.assertFalse(self.c.iter_select_by_func(lambda r: True))

        self.m.append(row=["foo"])
        self.m.append(row=["bar"])
        self.m.append(row=["foo"])
        self.c.remove_selection()
        self.assertTrue(self.c.iter_select_by_func(lambda r: r[0] == "foo"))
        selection = self.c.get_selection()
        model, iter_ = selection.get_selected()
        self.assertEqual(model.get_path(iter_)[:], [0])
        self.assertTrue(self.c.iter_select_by_func(lambda r: r[0] == "foo"))
        model, iter_ = selection.get_selected()
        self.assertEqual(model.get_path(iter_)[:], [2])
        self.assertTrue(self.c.iter_select_by_func(lambda r: r[0] == "foo"))
        model, iter_ = selection.get_selected()
        self.assertEqual(model.get_path(iter_)[:], [0])
        self.assertTrue(self.c.iter_select_by_func(lambda r: r[0] == "bar"))
        model, iter_ = selection.get_selected()
        self.assertEqual(model.get_path(iter_)[:], [1])
        self.assertFalse(self.c.iter_select_by_func(lambda r: r[0] == "bar"))

    def test_remove_select_single(self):
        # empty
        self.c.remove_selection()

        model = _fill_view(self.c)

        # select first and remove
        selection = self.c.get_selection()
        length = len(model)
        selection.select_path(model[0].path)
        self.c.remove_selection()
        self.assertEqual(len(model), length - 1)
        model, iter_ = selection.get_selected()

        # afterwards the first is selected
        self.assertEqual(model[iter_].path, model[0].path)

    def test_remove_select_multiple(self):
        selection = self.c.get_selection()
        selection.set_mode(Gtk.SelectionMode.MULTIPLE)

        # empty
        self.c.remove_selection()

        model = _fill_view(self.c)

        # select first two and remove
        selection = self.c.get_selection()
        length = len(model)
        selection.select_range(model[0].path, model[1].path)
        self.c.remove_selection()
        self.assertEqual(len(model), length - 2)

        # afterwards the first is selected
        model, paths = selection.get_selected_rows()
        self.assertEqual(paths, [model[0].path])

    def test_without_model(self):
        column = TreeViewColumn()
        self.c.append_column(column)

        column = self.c.get_columns()[0]
        column.set_sort_indicator(True)
        self.c.set_search_column(0)

        with self.c.without_model() as model:
            self.assertEqual(model, self.m)
            self.assertTrue(self.c.get_model() is None)

        self.assertEqual(self.c.get_search_column(), 0)
        column = self.c.get_columns()[0]
        self.assertTrue(column.get_sort_indicator())

    def test_set_drag_dest(self):
        x, y = self.c.convert_bin_window_to_widget_coords(0, 0)

        # empty model
        self.c.unset_rows_drag_dest()
        self.c.set_drag_dest(x, y)
        path, pos = self.c.get_drag_dest_row()
        self.assertTrue(path is None)

        # filled model but not realized, fall back to last path
        model = _fill_view(self.c)
        self.c.set_drag_dest(x, y)
        path, pos = self.c.get_drag_dest_row()
        self.assertEqual(model[-1].path, path)

        # realized now, so the first path
        with realized(self.c):
            x, y = self.c.convert_bin_window_to_widget_coords(0, 0)

            self.c.unset_rows_drag_dest()
            self.c.set_drag_dest(x, y, into_only=False)
            path, pos = self.c.get_drag_dest_row()
            self.assertEqual(model[0].path, path)
            self.assertEqual(pos, Gtk.TreeViewDropPosition.BEFORE)

            self.c.unset_rows_drag_dest()
            self.c.set_drag_dest(x, y, into_only=True)
            path, pos = self.c.get_drag_dest_row()
            self.assertEqual(model[0].path, path)
            self.assertEqual(pos, Gtk.TreeViewDropPosition.INTO_OR_BEFORE)

    def tearDown(self):
        self.c.destroy()


class TMultiDragTreeView(TestCase):

    def setUp(self):
        self.c = MultiDragTreeView()
        _fill_view(self.c)

    def test_click(self):
        with visible(self.c):
            send_button_click(self.c, Gdk.BUTTON_PRIMARY)
            send_button_click(self.c, Gdk.BUTTON_PRIMARY, primary=True)


class TRCMTreeView(TestCase):

    def setUp(self):
        self.c = RCMTreeView()
        _fill_view(self.c)

    def test_right_click(self):
        with visible(self.c):
            send_button_click(self.c, Gdk.BUTTON_SECONDARY)
            send_button_click(self.c, Gdk.BUTTON_SECONDARY, primary=True)

    def test_popup(self):
        menu = Gtk.Menu()
        selection = self.c.get_selection()
        selection.set_mode(Gtk.SelectionMode.MULTIPLE)

        with visible(self.c):
            # the popup only shows if the underlying row is selected,
            # so select all first
            selection.select_all()
            self.assertTrue(self.c.popup_menu(menu, Gdk.BUTTON_SECONDARY, 0))


class TDragIconTreeView(TestCase):

    def setUp(self):
        self.c = DragIconTreeView()
        _fill_view(self.c)

    def test_create_drag_icon(self):
        model = self.c.get_model()
        all_paths = [row.path for row in model]

        self.assertFalse(self.c.create_multi_row_drag_icon(all_paths, 1))
        with visible(self.c):
            self.assertTrue(self.c.create_multi_row_drag_icon(all_paths, 1))
            self.assertFalse(self.c.create_multi_row_drag_icon([], 1))
            self.assertTrue(
                self.c.create_multi_row_drag_icon([all_paths[0]], 10))


class TDragScroll(TestCase):

    def setUp(self):
        class ScrollClass(BaseView, DragScroll):
            pass
        self.c = ScrollClass()
        _fill_view(self.c)

    @skipIf(is_windows(), "fixme")
    def test_basic(self):
        self.c.scroll_motion(0, 0)
        self.c.scroll_motion(42, 42)
        self.c.scroll_motion(999, 999)
        self.c.scroll_disable()


class TTreeViewColumn(TestCase):

    def test_main(self):
        TreeViewColumn(title="foo")
        area = Gtk.CellAreaBox()
        tvc = TreeViewColumn(cell_area=area)
        self.assertEqual(tvc.get_area(), area)
