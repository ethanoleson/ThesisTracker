# todo_projects_pyqt6.py
# Run: python todo_projects_pyqt6.py
# Requires: pip install PyQt6

from __future__ import annotations

import os
os.environ["QT_MAC_DISABLE_NATIVE_MENUBAR"] = "1"

import sys
import json
import random
from pathlib import Path
from dataclasses import dataclass, field
from datetime import date

from PyQt6.QtCore import Qt, QDate, QEvent, pyqtSignal, QTimer
from PyQt6.QtGui import QKeySequence, QAction
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QCheckBox, QScrollArea, QFrame,
    QStackedWidget, QInputDialog, QDialog, QDialogButtonBox,
    QLineEdit, QDateEdit, QMessageBox, QFileDialog, QMenu
)


# random quote

QUOTES = [
    "“Opportunity is missed by most people because it is dressed in overalls and looks like work.”",
    "“I can do hard things”",
    "“We've tried nothing, and we're all out of ideas”",
    "“No shoulda, woulda, coulda”",
    "“The best thesis is a done thesis.”",
    "“Fuck it. Work Harder.”"
]
# ============================================================
# Data model
# ============================================================
@dataclass
class Task:
    title: str
    due_date: date | None = None
    completed: bool = False  # NOTE: we may temporarily set to None as a "deleted" marker


@dataclass
class Project:
    name: str
    tasks: list[Task] = field(default_factory=list)


class AppState:
    def __init__(self) -> None:
        self.projects: list[Project] = []


# ============================================================
# Persistence helpers
# ============================================================
CONFIG_DIR = Path.home() / ".project_todo"
CONFIG_FILE = CONFIG_DIR / "config.json"
MAX_RECENT = 5


def load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text())
        except Exception:
            pass
    return {}


def save_config(cfg: dict):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2))


def serialize_state(state: AppState) -> dict:
    # Skip deleted tasks (completed == None)
    return {
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
                    if t.completed is not None
                ],
            }
            for p in state.projects
        ]
    }


def deserialize_state(data: dict) -> AppState:
    state = AppState()
    for p in data.get("projects", []):
        proj = Project(name=p["name"])
        for t in p.get("tasks", []):
            proj.tasks.append(
                Task(
                    title=t["title"],
                    due_date=date.fromisoformat(t["due_date"]) if t["due_date"] else None,
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
        "Project Files (*.json)"
    )
    return Path(path) if path else None


def create_new_file(parent) -> Path | None:
    path, _ = QFileDialog.getSaveFileName(
        parent,
        "Create Project File",
        str(Path.home() / "projects.json"),
        "Project Files (*.json)"
    )
    return Path(path) if path else None


# ============================================================
# Dialog to add/edit a task
# ============================================================
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
        self.no_due_checkbox.toggled.connect(self._toggle_due_enabled)
        layout.addWidget(self.no_due_checkbox)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if task:
            self.title_edit.setText(task.title)
            if task.due_date is None:
                self.no_due_checkbox.setChecked(True)
            else:
                self.date_edit.setDate(
                    QDate(task.due_date.year, task.due_date.month, task.due_date.day)
                )
        else:
            self.date_edit.setDate(QDate.currentDate())

        self.title_edit.setFocus()

    def _toggle_due_enabled(self, checked: bool):
        self.date_edit.setEnabled(not checked)

    def apply(self) -> bool:
        title = self.title_edit.text().strip()
        if not title:
            QMessageBox.warning(self, "Missing title", "Please enter a task title.")
            return False

        due = None
        if not self.no_due_checkbox.isChecked():
            qd = self.date_edit.date()
            due = date(qd.year(), qd.month(), qd.day())

        if self._task:
            self._task.title = title
            self._task.due_date = due
        else:
            self._task = Task(title=title, due_date=due)

        return True

    def get_task(self) -> Task | None:
        if self.exec() != QDialog.DialogCode.Accepted:
            return None
        if not self.apply():
            return None
        return self._task


# ============================================================
# Task widget
# ============================================================
class TaskWidget(QWidget):
    completionToggled = pyqtSignal()
    editRequested = pyqtSignal(Task)

    def __init__(self, task: Task):
        super().__init__()
        self.task = task

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)

        self.checkbox = QCheckBox()
        self.checkbox.setChecked(bool(task.completed))
        self.checkbox.stateChanged.connect(self._on_checked)
        layout.addWidget(self.checkbox)

        layout.addWidget(QLabel(task.title), 1)

        due = f"Due: {task.due_date.isoformat()}" if task.due_date else ""
        layout.addWidget(QLabel(due))

    def mouseDoubleClickEvent(self, event):
        self.editRequested.emit(self.task)

    def _on_checked(self, state: int):
        self.task.completed = (state == Qt.CheckState.Checked.value)
        self.completionToggled.emit()

    def contextMenuEvent(self, event):
        menu = QMenu(self)

        edit = menu.addAction("Edit Task")
        delete = menu.addAction("Delete Task")

        action = menu.exec(event.globalPos())

        if action == edit:
            self.editRequested.emit(self.task)
        elif action == delete:
            self._delete_task()

    def _delete_task(self):
        # PyQt6 has no StandardButton.Delete, so use a custom destructive button
        box = QMessageBox(self)
        box.setWindowTitle("Delete Task")
        box.setText(f"Delete task '{self.task.title}'?")

        delete_btn = box.addButton("Delete", QMessageBox.ButtonRole.DestructiveRole)
        box.addButton(QMessageBox.StandardButton.Cancel)

        box.exec()

        if box.clickedButton() == delete_btn:
            self.task.completed = None  # marker for deletion
            self.completionToggled.emit()


# ============================================================
# Project column (card)
# ============================================================
class ProjectColumn(QFrame):
    requestAddTask = pyqtSignal(str)
    taskCompletionChanged = pyqtSignal()
    taskEdited = pyqtSignal()
    activated = pyqtSignal(str)

    # NEW: bubble up project deletion to MainWindow
    projectDeleteRequested = pyqtSignal(str)

    def __init__(self, project: Project, show_completed: bool):
        super().__init__()
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
            QFrame#ProjectCard[active="true"] {
                border: 2px solid palette(highlight);
                background-color: palette(base);
            }
        """)

        self.installEventFilter(self)

        outer = QVBoxLayout(self)

        header = QHBoxLayout()
        header.addWidget(QLabel(f"<b>{project.name}</b>"))
        header.addStretch()

        if not show_completed:
            btn = QPushButton("Add Task")
            btn.clicked.connect(lambda: self.requestAddTask.emit(project.name))
            header.addWidget(btn)
            btn.installEventFilter(self)

        outer.addLayout(header)

        self.tasks_layout = QVBoxLayout()
        outer.addLayout(self.tasks_layout)
        outer.addStretch()

        self.populate()

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.MouseButtonPress:
            self.activated.emit(self.project.name)
        return super().eventFilter(obj, event)

    def set_active(self, active: bool):
        self.setProperty("active", active)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def populate(self):
        while self.tasks_layout.count():
            w = self.tasks_layout.takeAt(0).widget()
            if w:
                w.deleteLater()

        # Remove deleted tasks (completed == None)
        self.project.tasks = [t for t in self.project.tasks if t.completed is not None]

        tasks = [t for t in self.project.tasks if t.completed == self.show_completed]
        for t in sorted(tasks, key=lambda x: (x.due_date is None, x.due_date or date.max)):
            w = TaskWidget(t)
            w.completionToggled.connect(self.taskCompletionChanged.emit)
            w.editRequested.connect(self._edit_task)
            w.installEventFilter(self)
            self.tasks_layout.addWidget(w)

    def _edit_task(self, task: Task):
        if AddTaskDialog(self, task).get_task():
            self.taskEdited.emit()

    def contextMenuEvent(self, event):
        menu = QMenu(self)

        rename = menu.addAction("Rename Project")
        delete = menu.addAction("Delete Project")

        action = menu.exec(event.globalPos())

        if action == rename:
            self._rename_project()
        elif action == delete:
            self._delete_project()

    def _rename_project(self):
        name, ok = QInputDialog.getText(
            self,
            "Rename Project",
            "New project name:",
            text=self.project.name
        )
        if ok and name.strip():
            self.project.name = name.strip()
            self.taskEdited.emit()  # triggers save + rebuild

    def _delete_project(self):
        box = QMessageBox(self)
        box.setWindowTitle("Delete Project")
        box.setText("Are you sure you want to permanently delete this project?\n\nAll tasks will be lost.")

        delete_btn = box.addButton("Delete", QMessageBox.ButtonRole.DestructiveRole)
        box.addButton(QMessageBox.StandardButton.Cancel)

        box.exec()

        if box.clickedButton() == delete_btn:
            # emit to MainWindow (the owner of state + saving)
            self.projectDeleteRequested.emit(self.project.name)


# ============================================================
# Board
# ============================================================
class ProjectBoard(QWidget):
    requestAddTask = pyqtSignal(str)
    taskChanged = pyqtSignal()
    projectActivated = pyqtSignal(str)

    # NEW: bubble up deletion to MainWindow
    projectDeleteRequested = pyqtSignal(str)

    def __init__(self, show_completed: bool):
        super().__init__()
        self.show_completed = show_completed
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
        for c in self._columns:
            c.set_active(name == c.project.name)

    def populate(self, projects: list[Project]):
        while self.hbox.count() > 1:
            w = self.hbox.takeAt(0).widget()
            if w:
                w.deleteLater()

        self._columns = []
        for p in projects:
            col = ProjectColumn(p, self.show_completed)
            col.requestAddTask.connect(self.requestAddTask.emit)
            col.taskCompletionChanged.connect(self.taskChanged.emit)
            col.taskEdited.connect(self.taskChanged.emit)
            col.activated.connect(self.projectActivated.emit)

            # NEW: deletion plumbing
            col.projectDeleteRequested.connect(self.projectDeleteRequested.emit)

            self._columns.append(col)
            self.hbox.insertWidget(self.hbox.count() - 1, col)


# ============================================================
# Main window
# ============================================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ThesisTracker")
        self.resize(1100, 650)

        self.cfg = load_config()
        self.data_file: Path | None = None

        self._startup_file_selection()

        self.active_project_name = self.state.projects[0].name if self.state.projects else None

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.active = ProjectBoard(False)
        self.completed = ProjectBoard(True)

        self.stack.addWidget(self.active)
        self.stack.addWidget(self.completed)

        self.active.requestAddTask.connect(self.add_task_to_project)
        self.active.taskChanged.connect(self.save_and_rebuild)
        self.active.projectActivated.connect(self.set_active_project)
        self.active.projectDeleteRequested.connect(self.delete_project_by_name)

        self.completed.taskChanged.connect(self.save_and_rebuild)
        self.completed.projectActivated.connect(self.set_active_project)
        self.completed.projectDeleteRequested.connect(self.delete_project_by_name)


        # ----------------------------
        # Status bar quote (Level 3)
        # ----------------------------
        status = self.statusBar()
        status.setSizeGripEnabled(False)

        self.quote_label = QLabel()
        self.quote_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.quote_label.setStyleSheet("""
            QLabel {
                color: palette(highlight);
                font-style: italic;
                padding: 4px;
            }
        """)
        status.addPermanentWidget(self.quote_label, 1)

        self.set_random_quote()

        self.quote_timer = QTimer(self)
        self.quote_timer.timeout.connect(self.set_random_quote)
        self.quote_timer.start(60_000)
        self._build_menus()
        self.rebuild()

    # --------------------------------------------------------
    # Startup + file loading
    # --------------------------------------------------------
    def _startup_file_selection(self):
        path = self.cfg.get("data_file")
        if path and Path(path).exists():
            self.load_project_file(Path(path))
            return

        choice = QMessageBox.question(
            self,
            "Project Storage",
            "Choose where to store your project file.\n\n"
            "Use Dropbox / iCloud to sync across computers.",
            QMessageBox.StandardButton.Open |
            QMessageBox.StandardButton.Save |
            QMessageBox.StandardButton.Cancel
        )

        if choice == QMessageBox.StandardButton.Open:
            p = choose_existing_file(self)
        elif choice == QMessageBox.StandardButton.Save:
            p = create_new_file(self)
        else:
            sys.exit(0)

        if not p:
            sys.exit(0)

        self.load_project_file(p)

    def load_project_file(self, path: Path):
        self.data_file = path

        recent = self.cfg.get("recent", [])
        recent = [str(path)] + [p for p in recent if p != str(path)]
        self.cfg["recent"] = recent[:MAX_RECENT]
        self.cfg["data_file"] = str(path)
        save_config(self.cfg)

        try:
            if path.exists():
                self.state = deserialize_state(json.loads(path.read_text()))
            else:
                self.state = AppState()
                path.write_text(json.dumps(serialize_state(self.state), indent=2))
        except Exception:
            QMessageBox.critical(self, "Error", "Could not load project file.")
            self.state = AppState()

        self.detect_conflicts()

    def detect_conflicts(self):
        # crude but useful: warn if a typical Dropbox/Drive "conflict" file exists
        for f in self.data_file.parent.glob("*conflict*"):
            QMessageBox.warning(
                self,
                "Sync conflict detected",
                f"A conflicting file was found:\n\n{f.name}"
            )
            break

    def set_quote(self, text: str):
        self.quote_label.setText(text)

    def set_random_quote(self):
        self.set_quote(random.choice(QUOTES))

    # --------------------------------------------------------
    # Menus
    # --------------------------------------------------------
    def _build_menus(self):
        bar = self.menuBar()
        bar.setNativeMenuBar(False)

        # ------------------
        # Project menu
        # ------------------
        proj = bar.addMenu("Project")

        # Add Project (⌘N / Ctrl+N)
        self.act_add_project = proj.addAction("Add Project")
        self.act_add_project.setShortcut(QKeySequence.StandardKey.New)
        self.act_add_project.triggered.connect(self.add_project)

        # Add Task (⌘T / Ctrl+T)
        self.act_add_task = proj.addAction("Add Task")
        self.act_add_task.setShortcut(QKeySequence("Ctrl+T"))
        self.act_add_task.triggered.connect(self.add_task_shortcut)

        proj.addSeparator()

        # Change Project File…
        self.act_change_file = proj.addAction("Change Project File…")
        self.act_change_file.triggered.connect(self.change_project_file)

        # ------------------
        # View menu
        # ------------------
        view = bar.addMenu("View")

        self.act_view_active = view.addAction("Active Tasks")
        self.act_view_active.setShortcut(QKeySequence("Ctrl+1"))
        self.act_view_active.triggered.connect(
            lambda: self.stack.setCurrentWidget(self.active)
        )

        self.act_view_completed = view.addAction("Completed Tasks ")
        self.act_view_completed.setShortcut(QKeySequence("Ctrl+2"))
        self.act_view_completed.triggered.connect(
            lambda: self.stack.setCurrentWidget(self.completed)
        )

    def populate_recent_menu(self):
        menu = self.sender()
        menu.clear()
        for p in self.cfg.get("recent", []):
            act = menu.addAction(Path(p).name)
            act.triggered.connect(lambda _, x=p: self.load_project_file(Path(x)))

    # --------------------------------------------------------
    # Editing
    # --------------------------------------------------------
    def save_state(self):
        try:
            self.data_file.write_text(json.dumps(serialize_state(self.state), indent=2))
        except PermissionError:
            QMessageBox.warning(self, "Read-only", "Project file is read-only.")

    def save_and_rebuild(self):
        self.save_state()
        self.rebuild()

    def set_active_project(self, name: str):
        self.active_project_name = name
        self.active.set_active_project(name)
        self.completed.set_active_project(name)

    def get_target_project(self) -> Project | None:
        for p in self.state.projects:
            if p.name == self.active_project_name:
                return p
        return None

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
        t = AddTaskDialog(self).get_task()
        if t:
            p.tasks.append(t)
            self.save_and_rebuild()

    def add_task_to_project(self, name: str):
        for p in self.state.projects:
            if p.name == name:
                t = AddTaskDialog(self).get_task()
                if t:
                    p.tasks.append(t)
                    self.save_and_rebuild()
                return

    def rebuild(self):
        self.active.populate(self.state.projects)
        self.completed.populate(self.state.projects)
        if self.active_project_name:
            self.active.set_active_project(self.active_project_name)
            self.completed.set_active_project(self.active_project_name)

    def change_project_file(self):
        path = choose_existing_file(self)
        if not path:
            return
        self.load_project_file(path)
        self.rebuild()

    # --------------------------------------------------------
    # Correct project deletion (state lives here)
    # --------------------------------------------------------
    def delete_project_by_name(self, project_name: str):
        project = next((p for p in self.state.projects if p.name == project_name), None)
        if not project:
            return

        self.state.projects.remove(project)

        if self.active_project_name == project_name:
            self.active_project_name = (
                self.state.projects[0].name
                if self.state.projects else None
            )

        self.save_and_rebuild()

    # (kept for compatibility; unused in this wiring)
    def delete_project(self, project: Project):
        if project in self.state.projects:
            self.state.projects.remove(project)

            if self.active_project_name == project.name:
                self.active_project_name = (
                    self.state.projects[0].name
                    if self.state.projects else None
                )

            self.save_and_rebuild()


# ============================================================
# Entry point
# ============================================================
def main():
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()