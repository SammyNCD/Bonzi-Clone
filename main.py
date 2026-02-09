import sys
import random
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication, QWidget, QLabel, QSystemTrayIcon, QMenu, QStyle


def base_dir() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)  # PyInstaller temp dir
    return Path(__file__).resolve().parent

BASE_DIR = base_dir()

def resource_path(*parts: str) -> Path:
    return BASE_DIR.joinpath(*parts)

class Buddy(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setStyleSheet("background: transparent;")

        self._drag_offset = None
        self.TOP_PAD = 60

        self.label = QLabel(self)

        self.bubble = QLabel(self)
        self.bubble.setWordWrap(True)
        self.bubble.setStyleSheet("""
            QLabel {
                color: black;
                background: rgba(255,255,255,235);
                border-radius: 10px;
                padding: 8px 10px;
            }
        """)
        self.bubble.hide()

        self.bubble_timer = QTimer(self)
        self.bubble_timer.setSingleShot(True)
        self.bubble_timer.timeout.connect(self.bubble.hide)

        self.anims: dict[str, list[QPixmap]] = {}
        for name in self.list_anim_folders():
            self.anims[name] = self.load_frames(name)

        if not self.anims.get("idle"):
            sprite_path = resource_path("assets", "sprites", "buddy.png")
            if not self.set_sprite(sprite_path):
                self.label.setText("Missing: assets/sprites/buddy.png")
                self.label.setStyleSheet("color: white; background: rgba(0,0,0,160); padding: 10px;")
                self.label.adjustSize()
                self.resize(self.label.size())
            return

        self.canvas_w, self.canvas_h = self.compute_canvas_size(self.anims)
        self.setFixedSize(self.canvas_w, self.canvas_h + self.TOP_PAD)

        self.anim_speeds = {
            "idle": 300,
            "_default": 100
        }

        self.current_anim = "idle"
        self.current_frames = self.anims["idle"]
        self.current_loop = True
        self.anim_i = 0

        self.frame_ms = self.anim_speeds["idle"]
        self.set_pixmap(self.current_frames[0])

        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self.tick_anim)
        self.anim_timer.start(self.frame_ms)

        self.behavior_timer = QTimer(self)
        self.behavior_timer.setSingleShot(True)
        self.behavior_timer.timeout.connect(self.do_random_action)
        self.schedule_next_action()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_offset is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_offset = None
        event.accept()

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.addAction("Say hi", lambda: self.say("hi :)"))
        menu.addAction("Do random action now", self.do_random_action)
        menu.addAction("Return to idle", lambda: self.play("idle", loop=True))
        quit_action = menu.addAction("Quit")
        quit_action.triggered.connect(QApplication.quit)
        menu.exec(event.globalPos())

    def set_sprite(self, path: Path) -> bool:
        if not path.exists():
            return False
        pix = QPixmap(str(path))
        if pix.isNull():
            return False
        self.set_pixmap(pix)
        return True

    def set_pixmap(self, pix: QPixmap):
        self.label.setPixmap(pix)
        self.label.resize(pix.size())

        x = (self.canvas_w - pix.width()) // 2
        if x < 0:
            x = 0

        y = self.TOP_PAD + (self.canvas_h - pix.height())
        if y < self.TOP_PAD:
            y = self.TOP_PAD

        self.label.move(x, y)

    def say(self, text: str, ms: int = 2500):
        self.bubble.setText(text)
        self.bubble.adjustSize()

        x = (self.width() - self.bubble.width()) // 2
        y = self.TOP_PAD - self.bubble.height() - 8
        if y < 0:
            y = 0
        self.bubble.move(x, y)

        self.bubble.show()
        self.bubble.raise_()
        self.bubble_timer.start(ms)

    def list_anim_folders(self) -> list[str]:
        sprites_dir = resource_path("assets", "sprites")
        if not sprites_dir.exists():
            return []
        return sorted([p.name for p in sprites_dir.iterdir() if p.is_dir()])

    def load_frames(self, anim_name: str) -> list[QPixmap]:
        folder = resource_path("assets", "sprites", anim_name)
        order_file = folder / "order.txt"

        paths: list[Path] = []
        if order_file.exists():
            for line in order_file.read_text(encoding="utf-8").splitlines():
                name = line.strip()
                if not name or name.startswith("#"):
                    continue
                paths.append(folder / name)
        else:
            paths = sorted(folder.glob("*.png"))

        frames: list[QPixmap] = []
        for p in paths:
            if not p.exists():
                continue
            pix = QPixmap(str(p))
            if not pix.isNull():
                frames.append(pix)

        return frames

    def compute_canvas_size(self, anims: dict[str, list[QPixmap]]) -> tuple[int, int]:
        max_w = 1
        max_h = 1
        for frames in anims.values():
            for pix in frames:
                if pix.width() > max_w:
                    max_w = pix.width()
                if pix.height() > max_h:
                    max_h = pix.height()
        return max_w, max_h

    def play(self, anim_name: str, loop: bool):
        frames = self.anims.get(anim_name, [])
        if not frames:
            return

        self.current_anim = anim_name
        self.current_frames = frames
        self.current_loop = loop
        self.anim_i = 0

        self.set_pixmap(self.current_frames[0])

        ms = self.anim_speeds.get(anim_name, self.anim_speeds["_default"])
        self.frame_ms = ms
        print("PLAY", anim_name, "ms =", ms)
        self.anim_timer.start(ms)

    def tick_anim(self):
        if not self.current_frames:
            return

        self.anim_i += 1

        if self.anim_i >= len(self.current_frames):
            if self.current_loop:
                self.anim_i = 0
            else:
                self.play("idle", loop=True)
                self.schedule_next_action()
                return

        self.set_pixmap(self.current_frames[self.anim_i])

    def schedule_next_action(self):
        delay_ms = random.randint(8000, 25000)
        self.behavior_timer.start(delay_ms)

    def do_random_action(self):
        choices = [name for name, frames in self.anims.items() if name != "idle" and frames]
        if not choices:
            self.schedule_next_action()
            return
        self.play(random.choice(choices), loop=False)

app = QApplication(sys.argv)

buddy = Buddy()
buddy.show()

tray = QSystemTrayIcon(app)
tray.setIcon(app.style().standardIcon(QStyle.SP_MessageBoxInformation))
menu = QMenu()
menu.addAction("Show", lambda: (buddy.show(), buddy.raise_(), buddy.activateWindow()))
menu.addAction("Quit", app.quit)
tray.setContextMenu(menu)
tray.show()

sys.exit(app.exec())
