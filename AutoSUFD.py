import json
import os
import subprocess
import sys
import ctypes
import tempfile
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QLabel, QLineEdit, QPushButton,
    QVBoxLayout, QHBoxLayout, QSpacerItem,
    QSizePolicy, QCheckBox, QApplication
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon


# -------------------------
# Утилиты для путей и логирования
# -------------------------
def exe_dir() -> Path:
    """
    Папка рядом с выполняемым файлом:
    - если собрано в exe или запущено через python, возвращает папку, где лежит sys.executable
    - если в dev режиме (script), возвращает папку со скриптом
    """
    try:
        return Path(sys.executable).resolve().parent
    except Exception:
        return Path(__file__).resolve().parent


def script_dir() -> Path:
    return Path(__file__).resolve().parent


def get_ddo_path() -> Path:
    """
    Ищем исключительно внешний ddo.json рядом с exe (или рядом со скриптом в dev).
    Никакого использования sys._MEIPASS или временных папок.
    """
    # Сначала папка рядом с исполняемым файлом (для exe)
    try:
        ex_dir = Path(sys.executable).resolve().parent
    except Exception:
        ex_dir = script_dir()

    candidate = ex_dir / "ddo.json"
    if candidate.exists():
        return candidate

    # Затем — папка со скриптом (при запуске через python)
    candidate2 = script_dir() / "ddo.json"
    if candidate2.exists():
        return candidate2

    # Ни один внешний файл не найден — возвращаем путь рядом с exe (возможное место)
    return candidate  # не существует, но это внешний путь, который мы используем


def write_debug(text: str) -> None:
    """
    Пишем лог рядом с exe или в temp, чтобы видеть, что происходит.
    """
    try:
        log_dir = Path(sys.executable).resolve().parent
    except Exception:
        log_dir = script_dir()
    try:
        log_path = log_dir / "autosufd_debug.log"
        with open(log_path, "a", encoding="utf-8") as lf:
            lf.write(text + "\n")
    except Exception:
        try:
            tmp = Path(tempfile.gettempdir()) / "autosufd_debug.log"
            with open(tmp, "a", encoding="utf-8") as lf:
                lf.write(text + "\n")
        except Exception:
            pass


# -------------------------
# Главный класс
# -------------------------
class Auto_sufd(QWidget):
    TEMPLATE = {
        "12345": "CN Example",
        "67890": "CN Another Example"
    }

    def __init__(self):
        super().__init__()
        # Путь к внешнему ddo.json (только внешне). НЕ используем _MEIPASS.
        self._ddo_path = get_ddo_path()
        self._debug_enabled = False
        write_debug(f"INIT: exec={sys.executable} ddo_path={self._ddo_path} frozen={getattr(sys,'frozen',False)}")
        self._setup_ui()

    def _setup_ui(self):
        self.setWindowTitle("Авто SUFD")
        self.setFixedSize(460, 260)
        self._set_window_icon("Icon.png")

        title = QLabel("Авто SUFD")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-weight: 600; font-size: 14px;")

        label = QLabel("№ сада:")
        self.name_edit = QLineEdit()
        self.name_edit.setClearButtonEnabled(True)
        self.name_edit.setPlaceholderText("Введите ключ (например 12345)")
        self.name_edit.returnPressed.connect(self.acceptText)

        input_layout = QHBoxLayout()
        input_layout.addWidget(label)
        input_layout.addWidget(self.name_edit)

        # Контрольные элементы
        self.debug_chk = QCheckBox("Debug (печать payload и логирование)")
        self.debug_chk.stateChanged.connect(self._on_debug_changed)
        self.confirm_chk = QCheckBox("Подтверждение записи в реестр (не используется в автоматическом режиме)")
        self.confirm_chk.setChecked(False)

        # Кнопки действий
        btn_clear = QPushButton("Очистить")
        btn_clear.clicked.connect(self.clearText)

        btn_ok = QPushButton("Открыть")
        btn_ok.clicked.connect(self.acceptText)
        btn_ok.setDefault(True)

        btn_open_folder = QPushButton("ddo.json")
        btn_open_folder.clicked.connect(self.open_ddo_folder)

        btn_create_template = QPushButton("Создать ddo.json")
        btn_create_template.clicked.connect(self.create_template_ddo)

        btn_check_admin = QPushButton("Проверить права администратора")
        btn_check_admin.clicked.connect(self.check_admin_button_clicked)

        # Верстка
        top_btns = QHBoxLayout()
        top_btns.addWidget(btn_open_folder)
        top_btns.addWidget(btn_create_template)
        top_btns.addWidget(btn_check_admin)

        btn_layout = QHBoxLayout()
        btn_layout.addItem(QSpacerItem(10, 10, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))
        btn_layout.addWidget(btn_clear)
        btn_layout.addWidget(btn_ok)

        vbox = QVBoxLayout(self)
        vbox.addWidget(title)
        vbox.addSpacing(6)
        vbox.addLayout(input_layout)
        vbox.addWidget(self.debug_chk)
        vbox.addWidget(self.confirm_chk)
        vbox.addLayout(top_btns)
        vbox.addStretch(1)
        vbox.addLayout(btn_layout)
        vbox.setContentsMargins(12, 12, 12, 12)

    def _set_window_icon(self, icon_name: str):
        # Иконку ищем рядом с exe или рядом со скриптом; если нет — пропускаем
        icon_path = Path(sys.executable).resolve().parent / icon_name
        if not icon_path.exists():
            icon_path = script_dir() / icon_name
        if icon_path.exists():
            try:
                self.setWindowIcon(QIcon(str(icon_path)))
            except Exception:
                write_debug(f"Failed to set icon: {icon_path}")

    def _on_debug_changed(self, state):
        self._debug_enabled = bool(state)
        write_debug(f"Debug set to {self._debug_enabled}")

    def clearText(self):
        self.name_edit.clear()
        self.name_edit.setFocus()

    def open_ddo_folder(self):
        # Открываем папку рядом с exe (там ждём внешний ddo.json)
        folder = str(Path(sys.executable).resolve().parent)
        try:
            if sys.platform.startswith("win"):
                os.startfile(folder)
            elif sys.platform.startswith("darwin"):
                subprocess.run(["open", folder])
            else:
                subprocess.run(["xdg-open", folder])
        except Exception as e:
            if self._debug_enabled:
                write_debug(f"Failed to open folder: {folder} -> {e}")

    def create_template_ddo(self):
        # Создаём внешний ddo.json рядом с exe
        target = Path(sys.executable).resolve().parent / "ddo.json"
        try:
            with open(target, "w", encoding="utf-8") as f:
                json.dump(self.TEMPLATE, f, ensure_ascii=False, indent=2)
            # Обновляем путь к ddo.json на внешний
            self._ddo_path = target
            if self._debug_enabled:
                write_debug(f"Template created at {target}")
        except Exception as e:
            if self._debug_enabled:
                write_debug(f"Failed to create template: {e}")

    def acceptText(self):
        """
        Автоматически применяет настройки и запускает Chromium без диалогов.
        ddo.json читается ТОЛЬКО из внешнего файла рядом с exe или со скриптом.
        """
        key = self.name_edit.text().strip()
        if not key:
            if self._debug_enabled:
                write_debug("No key provided; abort")
            return

        # Внимание: читаем ddo.json только из внешнего пути self._ddo_path
        try:
            if not Path(self._ddo_path).exists():
                if self._debug_enabled:
                    write_debug(f"ddo.json not found at external path: {self._ddo_path}")
                return
            with open(self._ddo_path, "r", encoding="utf-8") as f:
                ddo = json.load(f)
        except Exception as e:
            if self._debug_enabled:
                write_debug(f"Failed to read external ddo.json: {e}")
            return

        if key not in ddo:
            if self._debug_enabled:
                write_debug(f"Key '{key}' not in ddo.json")
            return

        cn_value = str(ddo[key]).replace('"', '\\"')
        payload = '{"pattern":"*", "filter": {"SUBJECT": {"CN": "' + cn_value + '"}}}'

        if self._debug_enabled:
            write_debug(f"Payload: {payload}")
            print("AutoSUFD payload:", payload)

        if sys.platform.startswith("win"):
            # Проверяем права и при необходимости повышаем
            if not self.is_running_as_admin():
                if self._debug_enabled:
                    write_debug("Not running as admin; attempting elevate_and_restart()")
                elevated = self.elevate_and_restart()
                if elevated:
                    return
                else:
                    if self._debug_enabled:
                        write_debug("Failed to elevate; aborting")
                    return

            # Запись в реестр (Windows)
            try:
                import winreg
                reg_path_cookies = r"SOFTWARE\Policies\Chromium\DefaultCookiesSessionSetting"
                reg_path_cert = r"SOFTWARE\Policies\Chromium\AutoSelectCertificateForUrls"

                registry_key_1 = winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, reg_path_cookies, 0, winreg.KEY_ALL_ACCESS)
                winreg.SetValueEx(registry_key_1, "DefaultCookiesSetting", 0, winreg.REG_DWORD, 4)
                winreg.CloseKey(registry_key_1)

                registry_key = winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, reg_path_cert, 0, winreg.KEY_ALL_ACCESS)
                winreg.SetValueEx(registry_key, "1", 0, winreg.REG_SZ, payload)
                winreg.CloseKey(registry_key)

                if self._debug_enabled:
                    write_debug("Registry keys set successfully")
            except Exception as e:
                if self._debug_enabled:
                    write_debug(f"Failed to write registry: {e}")
                return

            # Запуск Chromium (Windows)
            try:
                userprofile = os.getenv("USERPROFILE") or os.getenv("HOME")
                chrome_path = Path(userprofile) / "AppData" / "Local" / "Chromium" / "Application" / "chrome.exe"
                if chrome_path.exists():
                    os.startfile(str(chrome_path))
                    if self._debug_enabled:
                        write_debug(f"Started Chromium: {chrome_path}")
                else:
                    if self._debug_enabled:
                        write_debug(f"Chromium not found at {chrome_path}")
            except Exception as e:
                if self._debug_enabled:
                    write_debug(f"Failed to start Chromium: {e}")
        else:
            # Linux logic
            try:
                policy_dir = "/etc/chromium/policies/managed"
                policy_file = os.path.join(policy_dir, "policy.json")
                
                # Создаём JSON-строку для Linux (как в AutoSUFD_linux_json.py)
                # payload в Windows это просто строка конфига, в Linux это полный JSON объект политики
                linux_json_data = json.dumps({"AutoSelectCertificateForUrls": [payload]})
                
                # Используем sudo -n tee для записи в защищенный файл
                command = f"echo '{linux_json_data}' | sudo -n tee {policy_file} > /dev/null"
                
                if self._debug_enabled:
                    write_debug(f"Linux command: {command}")
                
                # Пытаемся создать директорию если её нет (требует sudo -n)
                subprocess.run(f"sudo -n mkdir -p {policy_dir}", shell=True)
                res = subprocess.run(command, shell=True)
                
                if res.returncode == 0:
                    if self._debug_enabled:
                        write_debug("Policy file written successfully via sudo tee")
                    # Запуск chromium-gost
                    subprocess.Popen(["chromium-gost", "--new-window", "https://ufk94.sufd.budget.gov.ru/index.zul"])
                else:
                    if self._debug_enabled:
                        write_debug(f"Failed to write policy file, return code: {res.returncode}")
            except Exception as e:
                if self._debug_enabled:
                    write_debug(f"Linux execution error: {e}")


    def check_admin_button_clicked(self):
        if self.is_running_as_admin():
            if self._debug_enabled:
                write_debug("Already running as admin")
            return
        if self._debug_enabled:
            write_debug("Attempting to elevate via check_admin_button_clicked()")
        self.elevate_and_restart()

    def elevate_and_restart(self) -> bool:
        """
        Перезапускает текущий exe/interpreter с правами администратора.
        """
        if not sys.platform.startswith("win"):
            if self._debug_enabled:
                write_debug("elevate_and_restart: not Windows")
            return False

        try:
            exe = sys.executable
            if getattr(sys, "frozen", False):
                target = exe
                params = " ".join(f'"{a}"' for a in sys.argv[1:])
            else:
                target = exe
                script = os.path.abspath(sys.argv[0])
                rest = " ".join(f'"{a}"' for a in sys.argv[1:])
                params = f'"{script}"' + ((" " + rest) if rest else "")

            if self._debug_enabled:
                write_debug(f"ShellExecuteW target={target} params={params}")

            ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", target, params, None, 1)
            if self._debug_enabled:
                write_debug(f"ShellExecuteW ret={ret}")

            if int(ret) <= 32:
                if self._debug_enabled:
                    write_debug(f"ShellExecuteW failed with code {ret}")
                return False

            QApplication.quit()
            return True
        except Exception as e:
            if self._debug_enabled:
                write_debug(f"elevate_and_restart exception: {e}")
            return False

    @staticmethod
    def is_running_as_admin() -> bool:
        try:
            if sys.platform.startswith("win"):
                return bool(ctypes.windll.shell32.IsUserAnAdmin())
            else:
                return os.geteuid() == 0
        except Exception:
            return False

    def show_window(self):
        self.show()
