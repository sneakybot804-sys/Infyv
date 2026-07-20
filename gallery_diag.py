from PySide6.QtWidgets import QApplication
from gui.theme.manager import ThemeManager
from gui.app_theme_preview import build_gallery
import sys

app = QApplication(sys.argv)

theme = ThemeManager()
theme.apply(app)

window = build_gallery(theme)
window.showMaximized()

app.exec()