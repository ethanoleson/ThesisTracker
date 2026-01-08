# todo_projects_pyqt6.py
# Run: python todo_projects_pyqt6.py
# Requires: pip install PyQt6

from __future__ import annotations

import os
import sys
import json
import random
from pathlib import Path
from dataclasses import dataclass, field
from datetime import date

# ------------------------------------------------------------
# macOS: FORCE in-window menu bar (NOT the Apple top bar)
# Must be set BEFORE importing any PyQt6 modules.
# ------------------------------------------------------------
if sys.platform == "darwin":
    os.environ["QT_MAC_DISABLE_NATIVE_MENUBAR"] = "1"

from PyQt6.QtCore import Qt, QDate, QEvent, pyqtSignal, QTimer
from PyQt6.QtGui import QKeySequence, QTextDocument
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QCheckBox, QScrollArea, QFrame,
    QStackedWidget, QInputDialog, QDialog, QDialogButtonBox,
    QLineEdit, QDateEdit, QMessageBox, QFileDialog, QMenu
)
from PyQt6.QtPrintSupport import QPrinter

# ============================================================
# Quotes
# ============================================================
QUOTES = [
    "“Opportunity is missed by most people because it is dressed in overalls and looks like work.”",
    "“I can do hard things.”",
    "“We've tried nothing, and we're all out of ideas.”",
    "“No shoulda, woulda, coulda.”",
    "“The best thesis is a done thesis.”",
    "“Fuck it. Work harder.”",
]

# ============================================================
# Data model
# ============================================================
@dataclass
class Task:
    title: str
    due_date: date | None = None
    completed: bool = False


@dataclass
class Project:
    name: str
    tasks: list[Task] = field(default_factory=list)


class AppState:
    def __init__(self) -> None:
        self.projects: list[Project] = []


# ============================================================
# Persistence / config
# ============================================================
CONFIG_DIR = Path.home() / "Library" / "Application Support" / "ThesisTracker"
CONFIG_FILE = CONFIG_DIR / "config.json"
MAX_RECENT = 8


def resolve_user_path(p: Path) -> Path:
    return p.expanduser().resolve()


def load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_config(cfg: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def serialize_state(state: AppState) -> dict:
    return {
        "version": 1,
        "projects": [
            {
                "name": p.name,
                "tasks": [
                    {
                        "title": t.title,
                        "due_date": t.due_date.isoformat() if t.due_date else None,
                        "completed": bool(t.completed),
                    }
                    for t in p.tasks
                ],
            }
            for p in state.projects
        ],
    }


def deserialize_state(data: dict) -> AppState:
    state = AppState()
    for p in data.get("projects", []):
        proj = Project(name=p.get("name", "Untitled"))
        for t in p.get("tasks", []):
            proj.tasks.append(
                Task(
                    title=t.get("title", "").strip() or "Untitled Task",
                    due_date=date.fromisoformat(t["due_date"]) if t.get("due_date") else None,
                    completed=bool(t.get("completed", False)),
                )
            )
        state.projects.append(proj)
    return state


def choose_existing_file(parent) -> Path | None:
    path, _ = QFileDialog.getOpenFileName(
        parent,
        "Select Project File",
        str(Path.home()),
        "Project Files (*.json)",
    )
    return resolve_user_path(Path(path)) if path else None


def create_new_file(parent) -> Path | None:
    path, _ = QFileDialog.getSaveFileName(
        parent,
        "Create Project File",
        str(Path.home() / "ThesisTracker.json"),
        "Project Files (*.json)",
    )
    return resolve_user_path(Path(path)) if path else None


def conflict_candidates(folder: Path, basefile: Path) -> list[Path]:
    """
    Heuristic: detect common cloud 'conflicted copy' duplicates near the file.
    """
    name = basefile.stem.lower()
    out: list[Path] = []
    try:
        for p in folder.glob("*.json"):
            s = p.name.lower()
            if p == basefile:
                continue
            if name in s and ("conflict" in s or "conflicted copy" in s or "duplicate" in s):
                out.append(p)
    except Exception:
        pass
    return out

def export_todo_list(
    projects: list[Project],
    selected_names: list[str],
    include_completed: bool,
    path: Path
):
    lines: list[str] = []

    today = date.today().isoformat()
    lines.append("ThesisTracker – To-Do List")
    lines.append(f"Generated: {today}")
    lines.append("")

    for p in projects:
        if p.name not in selected_names:
            continue

        tasks = [
            t for t in p.tasks
            if include_completed or not t.completed
        ]

        if not tasks:
            continue

        lines.append("=" * 32)
        lines.append(f"PROJECT: {p.name}")
        lines.append("-" * 32)

        for t in sorted(tasks, key=lambda x: (x.due_date is None, x.due_date or date.max)):
            box = "[x]" if t.completed else "[ ]"
            due = f"  Due: {t.due_date.isoformat()}" if t.due_date else ""
            lines.append(f"{box} {t.title}{due}")

        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


# ============================================================
# Add/edit task dialog
# ============================================================

class SelectProjectsDialog(QDialog):
    def __init__(self, projects: list[Project], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Projects to Export")

        layout = QVBoxLayout(self)
        self.checks = []

        for p in projects:
            cb = QCheckBox(p.name)
            cb.setChecked(True)
            self.checks.append((cb, p))
            layout.addWidget(cb)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected_projects(self) -> list[Project]:
        return [p for cb, p in self.checks if cb.isChecked()]

class ExportProjectsDialog(QDialog):
    def __init__(self, projects: list[Project], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Export To-Do List")

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Select projects to include:"))

        self.checkboxes: dict[str, QCheckBox] = {}
        for p in projects:
            cb = QCheckBox(p.name)
            cb.setChecked(True)
            self.checkboxes[p.name] = cb
            layout.addWidget(cb)

        self.include_completed = QCheckBox("Include completed tasks")
        self.include_completed.setChecked(False)
        layout.addWidget(self.include_completed)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected_projects(self) -> list[str]:
        return [
            name for name, cb in self.checkboxes.items()
            if cb.isChecked()
        ]
class AddTaskDialog(QDialog):
    def __init__(self, parent: QWidget | None = None, task: Task | None = None):
        super().__init__(parent)
        self._task = task
        self.setWindowTitle("Edit Task" if task else "Add Task")
        self.setModal(True)

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Task title:"))
        self.title_edit = QLineEdit()
        layout.addWidget(self.title_edit)

        layout.addWidget(QLabel("Due date (optional):"))
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        layout.addWidget(self.date_edit)

        self.no_due_checkbox = QCheckBox("No due date")
        self.no_due_checkbox.toggled.connect(lambda c: self.date_edit.setEnabled(not c))
        layout.addWidget(self.no_due_checkbox)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if task:
            self.title_edit.setText(task.title)
            if task.due_date is None:
                self.no_due_checkbox.setChecked(True)
            else:
                self.date_edit.setDate(QDate(task.due_date.year, task.due_date.month, task.due_date.day))
        else:
            self.date_edit.setDate(QDate.currentDate())

        self.title_edit.setFocus()

    def get_task(self) -> Task | None:
        if self.exec() != QDialog.DialogCode.Accepted:
            return None

        title = self.title_edit.text().strip()
        if not title:
            QMessageBox.warning(self, "Missing title", "Please enter a task title.")
            return None

        due = None
        if not self.no_due_checkbox.isChecked():
            qd = self.date_edit.date()
            due = date(qd.year(), qd.month(), qd.day())

        if self._task:
            self._task.title = title
            self._task.due_date = due
            return self._task

        return Task(title=title, due_date=due)


# ============================================================
# Task widget
# ============================================================
class TaskWidget(QWidget):
    changed = pyqtSignal()
    activated = pyqtSignal()

    def __init__(self, project: Project, task: Task, parent: QWidget | None = None):
        super().__init__(parent)
        self.project = project
        self.task = task

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)

        self.checkbox = QCheckBox()
        self.checkbox.setChecked(bool(task.completed))
        self.checkbox.stateChanged.connect(self._on_checked)
        layout.addWidget(self.checkbox)

        self.title_label = QLabel(task.title)
        layout.addWidget(self.title_label, 1)

        due = f"Due: {task.due_date.isoformat()}" if task.due_date else ""
        self.due_label = QLabel(due)
        layout.addWidget(self.due_label)

        self.setObjectName("TaskWidget")
        self.setStyleSheet("""
            QWidget#TaskWidget {
                border: 1px solid rgba(0,0,0,0.15);
                border-radius: 8px;
            }
        """)

    def mousePressEvent(self, e):
        self.activated.emit()
        super().mousePressEvent(e)

    def mouseDoubleClickEvent(self, e):
        self.activated.emit()
        dlg = AddTaskDialog(self, self.task)
        if dlg.get_task():
            self.changed.emit()

    def _on_checked(self, state: int):
        self.task.completed = (state == Qt.CheckState.Checked.value)
        self.changed.emit()

    def contextMenuEvent(self, e):
        self.activated.emit()

        menu = QMenu(self)
        act_edit = menu.addAction("Edit Task")
        act_delete = menu.addAction("Delete Task")
        act = menu.exec(e.globalPos())

        if act == act_edit:
            dlg = AddTaskDialog(self, self.task)
            if dlg.get_task():
                self.changed.emit()

        elif act == act_delete:
            box = QMessageBox(self)
            box.setWindowTitle("Delete Task")
            box.setText(f"Delete task '{self.task.title}'?")
            delete_btn = box.addButton("Delete", QMessageBox.ButtonRole.DestructiveRole)
            box.addButton(QMessageBox.StandardButton.Cancel)
            box.exec()

            if box.clickedButton() == delete_btn:
                # actually remove from project
                try:
                    self.project.tasks.remove(self.task)
                except ValueError:
                    pass
                self.changed.emit()


# ============================================================
# Project column (card)
# ============================================================
class ProjectColumn(QFrame):
    requestAddTask = pyqtSignal(str)
    changed = pyqtSignal()
    activated = pyqtSignal(str)
    deleteRequested = pyqtSignal(str)
    renamed = pyqtSignal(str, str)  # old, new

    def __init__(self, project: Project, show_completed: bool, parent: QWidget | None = None):
        super().__init__(parent)
        self.project = project
        self.show_completed = show_completed

        self.setObjectName("ProjectCard")
        self.setProperty("active", False)
        self.setStyleSheet("""
            QFrame#ProjectCard {
                background-color: palette(window);
                border: 1px solid palette(mid);
                border-radius: 12px;
                padding: 6px;
            }
            QFrame#ProjectCard:hover {
                border-color: palette(highlight);
            }
            QFrame#ProjectCard[active="true"] {
                background-color: palette(base);
                border: 2px solid palette(highlight);
            }
        """)

        self.installEventFilter(self)

        outer = QVBoxLayout(self)

        header = QHBoxLayout()
        self.name_label = QLabel(f"<b>{project.name}</b>")
        header.addWidget(self.name_label)
        header.addStretch()

        self.add_btn = None
        if not show_completed:
            self.add_btn = QPushButton("Add Task")
            self.add_btn.clicked.connect(lambda: self.requestAddTask.emit(project.name))
            header.addWidget(self.add_btn)
            self.add_btn.installEventFilter(self)

        outer.addLayout(header)

        self.tasks_layout = QVBoxLayout()
        outer.addLayout(self.tasks_layout)
        outer.addStretch()

        self.name_label.installEventFilter(self)

        self.populate()

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.MouseButtonPress:
            self.activated.emit(self.project.name)
        return super().eventFilter(obj, event)

    def set_active(self, active: bool):
        self.setProperty("active", bool(active))
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def populate(self):
        while self.tasks_layout.count():
            w = self.tasks_layout.takeAt(0).widget()
            if w:
                w.deleteLater()

        tasks = [t for t in self.project.tasks if t.completed == self.show_completed]

        def sort_key(t: Task):
            return (t.due_date is None, t.due_date or date.max)

        for task in sorted(tasks, key=sort_key):
            w = TaskWidget(self.project, task)
            w.changed.connect(self.changed.emit)
            w.activated.connect(lambda p=self.project.name: self.activated.emit(p))
            w.installEventFilter(self)
            self.tasks_layout.addWidget(w)

    def contextMenuEvent(self, e):
        menu = QMenu(self)
        act_rename = menu.addAction("Rename Project")
        act_delete = menu.addAction("Delete Project")
        act = menu.exec(e.globalPos())

        if act == act_rename:
            old = self.project.name
            name, ok = QInputDialog.getText(self, "Rename Project", "New project name:", text=old)
            if ok and name.strip():
                new = name.strip()
                self.project.name = new
                self.renamed.emit(old, new)
                self.changed.emit()

        elif act == act_delete:
            box = QMessageBox(self)
            box.setWindowTitle("Delete Project")
            box.setText("Are you sure you want to permanently delete this project?\n\nAll tasks will be lost.")
            delete_btn = box.addButton("Delete", QMessageBox.ButtonRole.DestructiveRole)
            box.addButton(QMessageBox.StandardButton.Cancel)
            box.exec()
            if box.clickedButton() == delete_btn:
                self.deleteRequested.emit(self.project.name)


# ============================================================
# Board (Active or Completed)
# ============================================================
class ProjectBoard(QWidget):
    requestAddTask = pyqtSignal(str)
    changed = pyqtSignal()
    projectActivated = pyqtSignal(str)
    projectDeleteRequested = pyqtSignal(str)
    projectRenamed = pyqtSignal(str, str)

    def __init__(self, show_completed: bool, parent: QWidget | None = None):
        super().__init__(parent)
        self.show_completed = show_completed
        self._active_project_name: str | None = None
        self._columns: list[ProjectColumn] = []

        root = QVBoxLayout(self)
        root.addWidget(QLabel("<h2>Completed Tasks</h2>" if show_completed else "<h2>Active Tasks</h2>"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        root.addWidget(scroll)

        inner = QWidget()
        scroll.setWidget(inner)

        self.hbox = QHBoxLayout(inner)
        self.hbox.setSpacing(14)
        self.hbox.addStretch()

    def set_active_project(self, name: str | None):
        self._active_project_name = name
        for col in self._columns:
            col.set_active(bool(name) and col.project.name == name)

    def populate(self, projects: list[Project]):
        while self.hbox.count() > 1:
            item = self.hbox.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        self._columns = []
        for p in projects:
            col = ProjectColumn(p, self.show_completed)
            col.requestAddTask.connect(self.requestAddTask.emit)
            col.changed.connect(self.changed.emit)
            col.activated.connect(self.projectActivated.emit)
            col.deleteRequested.connect(self.projectDeleteRequested.emit)
            col.renamed.connect(self.projectRenamed.emit)

            self._columns.append(col)
            self.hbox.insertWidget(self.hbox.count() - 1, col)

        self.set_active_project(self._active_project_name)


# ============================================================
# Main window
# ============================================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ThesisTracker")
        self.resize(1100, 650)

        self.cfg = load_config()
        self.state = AppState()
        self.data_file: Path | None = None
        self.active_project_name: str | None = None

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.active = ProjectBoard(False)
        self.completed = ProjectBoard(True)
        self.stack.addWidget(self.active)
        self.stack.addWidget(self.completed)

        # wiring
        self.active.requestAddTask.connect(self.add_task_to_project)
        self.active.changed.connect(self.save_and_rebuild)
        self.active.projectActivated.connect(self.set_active_project)
        self.active.projectDeleteRequested.connect(self.delete_project_by_name)
        self.active.projectRenamed.connect(self.on_project_renamed)

        self.completed.changed.connect(self.save_and_rebuild)
        self.completed.projectActivated.connect(self.set_active_project)
        self.completed.projectDeleteRequested.connect(self.delete_project_by_name)
        self.completed.projectRenamed.connect(self.on_project_renamed)

        self._build_status_quote()
        self._build_menus()

        self._startup_file_selection()
        self.active_project_name = self.state.projects[0].name if self.state.projects else None
        self.rebuild()

    # --------------------------------------------------------
    # Status bar quote
    # --------------------------------------------------------
    def _build_status_quote(self):
        status = self.statusBar()
        status.setSizeGripEnabled(False)

        self.quote_label = QLabel()
        self.quote_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # palette(windowText) is white in dark mode, dark in light mode
        self.quote_label.setStyleSheet("""
            QLabel {
                color: palette(windowText);
                font-style: italic;
                padding: 4px;
            }
        """)
        status.addPermanentWidget(self.quote_label, 1)

        self.set_random_quote()
        self.quote_timer = QTimer(self)
        self.quote_timer.timeout.connect(self.set_random_quote)
        self.quote_timer.start(60_000)

    def set_random_quote(self):
        self.quote_label.setText(random.choice(QUOTES))

    # --------------------------------------------------------
    # Menu
    # --------------------------------------------------------
    def _build_menus(self):
        bar = self.menuBar()
        # FORCE in-window menu bar (critical for macOS + app bundle)
        bar.setNativeMenuBar(False)

        proj = bar.addMenu("Project")

        act_add_project = proj.addAction("Add Project")
        act_add_project.setShortcut(QKeySequence.StandardKey.New)
        act_add_project.triggered.connect(self.add_project)

        act_add_task = proj.addAction("Add Task")
        act_add_task.setShortcut(QKeySequence("Ctrl+T"))
        act_add_task.triggered.connect(self.add_task_shortcut)

        proj.addSeparator()

        act_change_file = proj.addAction("Change Project File…")
        act_change_file.setShortcut(QKeySequence("Ctrl+O"))
        act_change_file.triggered.connect(self.change_project_file)

        # Recent files submenu
        self.recent_menu = proj.addMenu("Recent Files")
        self.recent_menu.aboutToShow.connect(self.populate_recent_menu)

        view = bar.addMenu("View")

        act_view_active = view.addAction("Active Tasks")
        act_view_active.setShortcut(QKeySequence("Ctrl+1"))
        act_view_active.triggered.connect(lambda: self.stack.setCurrentWidget(self.active))

        act_view_completed = view.addAction("Completed Tasks")
        act_view_completed.setShortcut(QKeySequence("Ctrl+2"))
        act_view_completed.triggered.connect(lambda: self.stack.setCurrentWidget(self.completed))

        proj.addSeparator()


        act_export = proj.addAction("Export To-Do List (PDF)…")
        act_export.setShortcut(QKeySequence("Ctrl+P"))
        act_export.triggered.connect(self.export_todo_list_pdf)

    def populate_recent_menu(self):
        self.recent_menu.clear()
        rec = self.cfg.get("recent", [])
        if not rec:
            a = self.recent_menu.addAction("(No recent files)")
            a.setEnabled(False)
            return

        for p in rec:
            pp = Path(p)
            a = self.recent_menu.addAction(pp.name)
            a.triggered.connect(lambda _, x=p: self.load_project_file(Path(x), rebuild=True))

    # --------------------------------------------------------
    # Startup / file handling
    # --------------------------------------------------------
    def _startup_file_selection(self):
        path = self.cfg.get("data_file")
        if path and Path(path).exists():
            self.load_project_file(Path(path), rebuild=False)
            return

        choice = QMessageBox.question(
            self,
            "Project Storage",
            "Choose where to store your project file.\n\nUse Dropbox / iCloud to sync across computers.",
            QMessageBox.StandardButton.Open | QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Cancel
        )

        if choice == QMessageBox.StandardButton.Open:
            p = choose_existing_file(self)
        elif choice == QMessageBox.StandardButton.Save:
            p = create_new_file(self)
        else:
            sys.exit(0)

        if not p:
            sys.exit(0)

        self.load_project_file(p, rebuild=False)

    def load_project_file(self, path: Path, rebuild: bool = True):
        self.data_file = resolve_user_path(path)

        # update config + recents
        recent = self.cfg.get("recent", [])
        recent = [str(self.data_file)] + [x for x in recent if x != str(self.data_file)]
        self.cfg["recent"] = recent[:MAX_RECENT]
        self.cfg["data_file"] = str(self.data_file)
        save_config(self.cfg)

        # load/create
        try:
            if self.data_file.exists():
                data = json.loads(self.data_file.read_text(encoding="utf-8"))
                self.state = deserialize_state(data)
            else:
                self.state = AppState()
                self.data_file.write_text(json.dumps(serialize_state(self.state), indent=2), encoding="utf-8")
        except Exception as e:
            QMessageBox.critical(self, "Project File Error", f"Could not load:\n\n{e}")
            self.state = AppState()

        # warn conflicts
        self.detect_conflicts()

        if rebuild:
            self.active_project_name = self.state.projects[0].name if self.state.projects else None
            self.rebuild()

    def detect_conflicts(self):
        if not self.data_file:
            return
        folder = self.data_file.parent
        hits = conflict_candidates(folder, self.data_file)
        if hits:
            QMessageBox.warning(
                self,
                "Sync conflict detected",
                "A conflicting file was found (cloud sync duplicate). "
                "Please pick the correct one from Project → Change Project File…\n\n"
                f"Example:\n{hits[0].name}"
            )

    def change_project_file(self):
        p = choose_existing_file(self)
        if p:
            self.load_project_file(p, rebuild=True)

    # --------------------------------------------------------
    # Save / rebuild
    # --------------------------------------------------------
    def save_state(self):
        if not self.data_file:
            return
        try:
            self.data_file.write_text(json.dumps(serialize_state(self.state), indent=2), encoding="utf-8")
        except Exception:
            QMessageBox.warning(
                self,
                "Read-only / locked",
                "Could not save the project file.\n\n"
                "This can happen if the file is read-only, locked by sync software, or you opened a conflict copy.\n"
                "Try a different location via Project → Change Project File…"
            )

    def save_and_rebuild(self):
        self.save_state()
        self.rebuild()

    def rebuild(self):
        self.active.populate(self.state.projects)
        self.completed.populate(self.state.projects)

        # keep highlight consistent
        if self.active_project_name:
            self.active.set_active_project(self.active_project_name)
            self.completed.set_active_project(self.active_project_name)

    # --------------------------------------------------------
    # Selection / active project
    # --------------------------------------------------------
    def set_active_project(self, name: str):
        self.active_project_name = name
        self.active.set_active_project(name)
        self.completed.set_active_project(name)

    def get_target_project(self) -> Project | None:
        if self.active_project_name:
            for p in self.state.projects:
                if p.name == self.active_project_name:
                    return p
        return self.state.projects[0] if self.state.projects else None

    # --------------------------------------------------------
    # Actions
    # --------------------------------------------------------
    def add_project(self):
        name, ok = QInputDialog.getText(self, "Add Project", "Project name:")
        if ok and name.strip():
            self.state.projects.append(Project(name.strip()))
            if not self.active_project_name:
                self.active_project_name = name.strip()
            self.save_and_rebuild()

    def add_task_shortcut(self):
        p = self.get_target_project()
        if not p:
            QMessageBox.information(self, "No project", "Create a project first.")
            return
        dlg = AddTaskDialog(self)
        t = dlg.get_task()
        if t:
            p.tasks.append(t)
            self.save_and_rebuild()

    def add_task_to_project(self, project_name: str):
        p = next((x for x in self.state.projects if x.name == project_name), None)
        if not p:
            return
        dlg = AddTaskDialog(self)
        t = dlg.get_task()
        if t:
            p.tasks.append(t)
            self.save_and_rebuild()

    def delete_project_by_name(self, project_name: str):
        p = next((x for x in self.state.projects if x.name == project_name), None)
        if not p:
            return
        try:
            self.state.projects.remove(p)
        except ValueError:
            return

        if self.active_project_name == project_name:
            self.active_project_name = self.state.projects[0].name if self.state.projects else None

        self.save_and_rebuild()

    def on_project_renamed(self, old: str, new: str):
        # keep highlight and active selection stable after rename
        if self.active_project_name == old:
            self.active_project_name = new
        # also rebuild highlight without forcing a different project
        self.save_and_rebuild()

    def export_todo_list_pdf(self):
        if not self.state.projects:
            QMessageBox.information(self, "No projects", "There are no projects to export.")
            return

        dlg = SelectProjectsDialog(self.state.projects, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        projects = dlg.selected_projects()
        if not projects:
            QMessageBox.information(self, "Nothing selected", "No projects were selected.")
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export To-Do List (PDF)",
            str(Path.home() / "Todo_List.pdf"),
            "PDF Files (*.pdf)"
        )
        if not path:
            return

        html = """
        <html>
        <head>
            <style>
                body {
                    font-family: Helvetica, Arial, sans-serif;
                    font-size: 11pt;
                }
                h1 {
                    font-size: 14pt;
                    margin-bottom: 10px;
                }
                h2 {
                    font-size: 12pt;
                    margin-top: 18px;
                    margin-bottom: 6px;
                }
                ul {
                    list-style-type: none;
                    padding-left: 0;
                    margin-left: 0;
                }
                li {
                    margin-bottom: 6px;
                }
            </style>
        </head>
        <body>
            <h1>To-Do List</h1>
        """

        for p in projects:
            html += f"<h2>{p.name}</h2><ul>"
            for t in p.tasks:
                if not t.completed:
                    due = f" — due {t.due_date.isoformat()}" if t.due_date else ""
                    html += f"<li>☐ {t.title}{due}</li>"
            html += "</ul>"

        html += "</body></html>"

        doc = QTextDocument()
        doc.setHtml(html)

        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(path)

        doc.print(printer)

# ============================================================
# Entry
# ============================================================
def main():
    QApplication.setApplicationName("ThesisTracker")
    QApplication.setApplicationDisplayName("ThesisTracker")
    QApplication.setOrganizationName("ThesisTracker")

    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()