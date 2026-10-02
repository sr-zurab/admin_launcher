import sys
import os
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QGridLayout, QPushButton,
    QGroupBox, QVBoxLayout, QLabel, QHBoxLayout, QSizePolicy, QStatusBar
)
from PyQt6.QtGui import QIcon, QFont, QAction
from PyQt6.QtCore import Qt, QSize

# Импорты ваших модулей (убедитесь, что файлы находятся рядом и имена модулей верны)
from gmu_information import BusGovApp
from cert_manager import CertManagerApp
from org_pdf import PDFImporter
from budget import Budget
from qt_material import apply_stylesheet

APP_ICON = "cert_mgn.png"  # основная иконка окна (положи рядом с файлом)
ICON_DIR = os.path.dirname(__file__)  # базовая папка с ресурсами


class Launcher(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Инструменты администратора")
        self._set_window_icon()
        self._init_ui()
        self._create_menu()
        self._center_window(200, 200)

    def _set_window_icon(self):
        icon_path = os.path.join(ICON_DIR, APP_ICON)
        if os.path.exists(icon_path):
            try:
                self.setWindowIcon(QIcon(icon_path))
            except Exception:
                pass

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        # Заголовок
        title = QLabel("Панель запуска приложений")
        title.setFont(QFont("", 14, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Группа с кнопками
        group = QGroupBox()
        grid = QGridLayout()
        grid.setSpacing(14)

        btn_style = """
            QPushButton {
                padding: 10px 14px;
                text-align: left;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: gray;
            }
        """

        # Кнопки
        btn2 = QPushButton("  Инфо по организациям bus.gov.ru")
        btn2.setIcon(self._load_icon("list_org.ico"))
        btn2.setIconSize(QSize(28, 28))
        btn2.setToolTip("Информация об учреждении через bus.gov.ru")
        btn2.clicked.connect(self.open_app2)
        btn2.setStyleSheet(btn_style)
        btn2.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        btn3 = QPushButton("  Менеджер сертификатов")
        btn3.setIcon(self._load_icon("cert_mgn.png"))
        btn3.setIconSize(QSize(28, 28))
        btn3.setToolTip("Управление сертификатами")
        btn3.clicked.connect(self.open_app3)
        btn3.setStyleSheet(btn_style)
        btn3.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        btn4 = QPushButton("  Импорт ЕГРЮЛ из PDF")
        btn4.setIcon(self._load_icon("fns.ico"))
        btn4.setIconSize(QSize(28, 28))
        btn4.setToolTip("Импорт организации из PDF")
        btn4.clicked.connect(self.open_app4)
        btn4.setStyleSheet(btn_style)
        btn4.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        btn5 = QPushButton("  Реестр УБП/НУБП из ЭБ")
        btn5.setIcon(self._load_icon("fns.ico"))
        btn5.setIconSize(QSize(28, 28))
        btn5.setToolTip("Реестр УБП/НУБП")
        btn5.clicked.connect(self.open_app5)
        btn5.setStyleSheet(btn_style)
        btn5.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)


        # Расположение в сетке (2x2)
        grid.addWidget(btn2, 0, 0)
        grid.addWidget(btn3, 0, 1)
        grid.addWidget(btn4, 1, 0)
        grid.addWidget(btn5, 1, 1)
        group.setLayout(grid)

        # Подсказка
        hint = QLabel("Выберите приложение для запуска. Все окна работают независимо.")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet("color: gray;")

        # Верстка центральной области
        vbox = QVBoxLayout(central)
        vbox.addWidget(title)
        vbox.addSpacing(8)
        vbox.addWidget(group)
        vbox.addSpacing(10)
        vbox.addWidget(hint)
        vbox.setContentsMargins(16, 12, 16, 12)

        # Статусбар
        status = QStatusBar()
        status.showMessage("Готово")
        self.setStatusBar(status)

        # Хранилище окон, чтобы GC не удалял
        self._windows = {}

    def _load_icon(self, name: str) -> QIcon:
        path = os.path.join(ICON_DIR, name)
        if os.path.exists(path):
            return QIcon(path)
        return QIcon()

    def _create_menu(self):
        menubar = self.menuBar()
        help_menu = menubar.addMenu("Справка")
        about_action = QAction("О программе", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _show_about(self):
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.information(self, "О программе", "Launcher — панель запуска приложений\nВерсия 1.0")

    def _center_window(self, w: int, h: int):
        self.resize(w, h)
        fg = self.frameGeometry()
        screen_center = QApplication.primaryScreen().availableGeometry().center()
        fg.moveCenter(screen_center)
        self.move(fg.topLeft())

    # ---- Открытие приложений ----
    def open_app2(self):
        try:
            self._windows['app2'] = BusGovApp()
            self._windows['app2'].show()
            self.statusBar().showMessage("BusGovApp открыт")
        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Ошибка", f"Не удалось открыть BusGovApp:\n{e}")

    def open_app3(self):
        try:
            self._windows['app3'] = CertManagerApp()
            self._windows['app3'].show()
            self.statusBar().showMessage("CertManager открыт")
        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Ошибка", f"Не удалось открыть CertManager:\n{e}")

    def open_app4(self):
        try:
            self._windows['app4'] = PDFImporter()
            self._windows['app4'].show()
            self.statusBar().showMessage("PDFImporter открыт")
        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Ошибка", f"Не удалось открыть PDFImporter:\n{e}")
    def open_app5(self):
        try:
            self._windows['app5'] = Budget()
            self._windows['app5'].show()
            self.statusBar().showMessage("Budget открыт")
        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Ошибка", f"Не удалось открыть Budget:\n{e}")


def main():
    app = QApplication(sys.argv)

    # Применяем тему Material Design
    apply_stylesheet(app, theme='dark_indigo.xml')  # можно выбрать другую тему

    win = Launcher()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
