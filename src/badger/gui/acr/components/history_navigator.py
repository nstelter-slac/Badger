import os
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QTreeWidget,
    QTreeWidgetItem,
    QMenu,
    QAction,
    QApplication,
    QToolTip,
)
from PyQt5.QtGui import QFont, QDesktopServices, QCursor
from PyQt5.QtCore import Qt, QUrl, QTimer
from badger.archive import get_base_run_filename, get_runs
from badger.utils import run_names_to_dict


class HistoryNavigator(QWidget):
    def __init__(self):
        super().__init__()

        # Layout for the widget
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.tree_widget = QTreeWidget()

        self.tree_widget.setHeaderLabels(["History Navigator"])
        header = self.tree_widget.header()
        # Set the font of the header to bold
        bold_font = QFont()
        bold_font.setBold(True)
        header.setFont(bold_font)

        self.tree_widget.setMinimumHeight(256)

        self.tree_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree_widget.customContextMenuRequested.connect(self.show_context_menu)

        layout.addWidget(self.tree_widget)

        self.runs = None  # all runs to be shown in the tree widget
        self.setStyleSheet("""
            QTreeWidget {
                background-color: #37414F;
            }
        """)

    def show_context_menu(self, position):
        selected_item = self.tree_widget.itemAt(position)
        if selected_item is None:
            return  # user didn't click on any menu item
        run_filename = selected_item.text(0)
        if not run_filename.endswith(
            ".yaml"
        ):  # only type of file we display in history!
            return  # user clicked on a directory item in tree

        menu = QMenu(self.tree_widget)
        # for visibility of gray context-menu on gray background
        menu.setStyleSheet("""
        QMenu {
            border: 4px solid yellow;
        }
        """)

        # funcs that execute the context-menu actions
        def copy_fullpath_to_clipboard():
            clip = QApplication.clipboard()
            clip.setText(fullpath)
            # we need to delay the menu's closing for a bit after getting clicked, so tooltip has time to render
            QTimer.singleShot(
                50,  # ms
                lambda: QToolTip.showText(
                    QCursor.pos(),
                    "Text Copied!",
                    self.tree_widget,
                ),
            )

        def open_file():
            QDesktopServices.openUrl(QUrl.fromLocalFile(fullpath))

        def open_file_location():
            QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(fullpath)))

        # get full path to run file
        runs = get_runs()
        fullpath = self.find_run_by_name(runs, run_filename)

        open_file_item = menu.addAction("Open File")
        open_file_item.triggered.connect(open_file)

        open_file_dir_item = menu.addAction("Open File Directory")
        open_file_dir_item.triggered.connect(open_file_location)

        # menu item which when hovered on displays submenu with file's full path
        fullpath_item = QMenu("File Path", menu)
        sub_fullpath_item = QAction(fullpath, fullpath_item)
        sub_fullpath_item.triggered.connect(copy_fullpath_to_clipboard)
        fullpath_item.addAction(sub_fullpath_item)
        menu.addMenu(fullpath_item)

        menu.popup(self.tree_widget.viewport().mapToGlobal(position))

    def find_run_by_name(self, runs, filename):
        """
        Search in run_list (full paths) for a file matching filename.
        Returns the full path if found, else None.
        """
        for r in runs:
            if r.endswith(filename):
                return r
        return None

    def _firstSelectableItem(self, parent=None):
        """
        Internal recursive function for finding the first selectable item.
        """
        if parent is None:
            parent = self.tree_widget.invisibleRootItem()

        for i in range(parent.childCount()):
            item = parent.child(i)
            if item.flags() & Qt.ItemIsSelectable:
                return item
            result = self._firstSelectableItem(item)
            if result:
                return result
        return None

    def updateItems(self, runs=None):
        self.tree_widget.clear()
        self.runs = runs  # store the runs for navigation
        if runs is None:
            return

        runs_dict = run_names_to_dict(runs)
        first_items = []
        flag_first_item = True

        for year, dict_year in runs_dict.items():
            item_year = QTreeWidgetItem([year])
            item_year.setFlags(item_year.flags() & ~Qt.ItemIsSelectable)

            if flag_first_item:
                first_items.append(item_year)

            for month, dict_month in dict_year.items():
                item_month = QTreeWidgetItem([month])
                item_month.setFlags(item_month.flags() & ~Qt.ItemIsSelectable)

                if flag_first_item:
                    first_items.append(item_month)

                for day, list_day in dict_month.items():
                    item_day = QTreeWidgetItem([day])
                    item_day.setFlags(item_day.flags() & ~Qt.ItemIsSelectable)

                    if flag_first_item:
                        first_items.append(item_day)
                        flag_first_item = False

                    for file in list_day:
                        item_file = QTreeWidgetItem([file])
                        item_day.addChild(item_file)
                    item_month.addChild(item_day)
                item_year.addChild(item_month)
            self.tree_widget.addTopLevelItem(item_year)

        # Expand the first set of items
        for item in first_items:
            item.setExpanded(True)

    def selectNextItem(self):
        run_curr = get_base_run_filename(self.currentText())
        idx = self.runs.index(run_curr)
        if idx < len(self.runs) - 1:
            self._selectItemByRun(self.runs[idx + 1])

    def selectPreviousItem(self):
        run_curr = get_base_run_filename(self.currentText())
        idx = self.runs.index(run_curr)
        if idx > 0:
            self._selectItemByRun(self.runs[idx - 1])

    def _selectItemByRun(self, run):
        """
        Internal function to select a tree widget item by run name.
        """
        for i in range(self.tree_widget.topLevelItemCount()):
            year_item = self.tree_widget.topLevelItem(i)
            for j in range(year_item.childCount()):
                month_item = year_item.child(j)
                for k in range(month_item.childCount()):
                    day_item = month_item.child(k)
                    for _l in range(day_item.childCount()):
                        file_item = day_item.child(_l)
                        if get_base_run_filename(file_item.text(0)) == run:
                            self.tree_widget.setCurrentItem(file_item)
                            return

    def currentText(self):
        current_item = self.tree_widget.currentItem()
        if current_item:
            return current_item.text(0)
        return ""

    def count(self):
        if self.runs is None:
            return 0

        return len(self.runs)
