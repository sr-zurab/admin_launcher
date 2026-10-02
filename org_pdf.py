import sys, json, pdfplumber
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton,
    QFileDialog, QLabel, QLineEdit, QFormLayout,
    QTableWidget, QTableWidgetItem, QDialog, QHBoxLayout,
    QDialogButtonBox
)
import os
from PyQt6.QtGui import QIcon

JSON_FILE = "organizations.json"

def load_json():
    try:
        with open(JSON_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_json(data):
    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def extract_from_tables(pdf_path):
    data = {
        "full_name": None,
        "short_name": None,
        "inn": None,
        "kpp": None,
        "ogrn": None,
        "address": None,
        "head_fio": None,
        "reg_number": None,
        "inn_fl" : None,
        "post" : None
    }

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                for idx, row in enumerate(table):
                    if not row or len(row) < 3:
                        continue

                    label_raw = row[1] or ""
                    value_raw = row[2] or ""

                    label = " ".join(label_raw.splitlines()).strip()
                    value = " ".join(value_raw.splitlines()).strip()

                    if "Полное наименование" in label and not data["full_name"]:
                        data["full_name"] = value.strip("«»\"")

                    elif "Сокращенное наименование" in label and not data["short_name"]:
                        data["short_name"] = value.strip("«»\"")

                    elif "ИНН юридического лица" in label and not data["inn"]:
                        if value.isdigit():
                            data["inn"] = value

                    elif "КПП юридического лица" in label and not data["kpp"]:
                        if value.isdigit():
                            data["kpp"] = value

                    elif "ОГРН" in label and not data["ogrn"]:
                        if value.isdigit():
                            data["ogrn"] = value

                    elif "Адрес" in label and not data["address"]:
                        data["address"] = value

                    elif "Фамилия" in label and not data["head_fio"]:
                        fio_parts = [value]
                        data["head_fio"] = " ".join(fio_parts)

                    elif "Регистрационный номер страхователя" in label and not data["reg_number"]:
                        if value.isdigit():
                            data["reg_number"] = value
                    
                    elif "ИНН" in label and not data["inn_fl"]:
                        if value.isdigit():
                            data["inn_fl"] = value

                    elif "Должность" in label and not data["post"]:
                        data["post"] = value

            if all(data.values()):
                break

    return data


class OrgTableDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Список организаций")
        self.resize(800, 400)

        layout = QVBoxLayout()
        self.table = QTableWidget()
        layout.addWidget(self.table)

        btn_layout = QHBoxLayout()
        self.btn_delete = QPushButton("Удалить выбранную")
        self.btn_delete.clicked.connect(self.delete_selected)
        btn_layout.addWidget(self.btn_delete)
        layout.addLayout(btn_layout)

        self.button_box = QDialogButtonBox()
        self.btn_yes = self.button_box.addButton("Да", QDialogButtonBox.ButtonRole.AcceptRole)
        self.btn_no = self.button_box.addButton("Нет", QDialogButtonBox.ButtonRole.RejectRole)
        self.btn_yes.clicked.connect(self.accept)
        self.btn_no.clicked.connect(self.reject)
        layout.addWidget(self.button_box)

        self.setLayout(layout)
        self.load_data()
        self.selected_key = None
        self.table.cellDoubleClicked.connect(self.select_org)

    def load_data(self):
        data = load_json()
        self.table.setRowCount(len(data))
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Ключ", "ИНН", "Наименование"])

        for i, (key, org) in enumerate(data.items()):
            self.table.setItem(i, 0, QTableWidgetItem(key))
            self.table.setItem(i, 1, QTableWidgetItem(org.get("inn", "")))
            self.table.setItem(i, 2, QTableWidgetItem(org.get("full_name", "")))

    def select_org(self, row, col):
        self.selected_key = self.table.item(row, 0).text()
        self.accept()

    def delete_selected(self):
        row = self.table.currentRow()
        if row < 0:
            return
        key = self.table.item(row, 0).text()
        data = load_json()
        if key in data:
            del data[key]
            save_json(data)
            self.load_data()


class PDFImporter(QWidget):
    def __init__(self):
        super().__init__()
        ICON_PATH = os.path.join(os.path.dirname(__file__), "fns.ico")
        if os.path.exists(ICON_PATH):
            try:
                self.setWindowIcon(QIcon(ICON_PATH))
            except Exception:
                # если что-то пошло не так — пропускаем, приложение продолжит работать
                pass
        self.setWindowTitle("Организации ЕГРЮЛ")
        self.resize(600, 500)

        layout = QVBoxLayout()

        self.label = QLabel("Введите ключ (ИНН или произвольный)")
        layout.addWidget(self.label)

        self.key_field = QLineEdit()
        layout.addWidget(self.key_field)
        self.key_field.returnPressed.connect(self.load_by_key)

        self.button_load = QPushButton("Загрузить по ключу")
        self.button_load.clicked.connect(self.load_by_key)
        layout.addWidget(self.button_load)

        self.button_import = QPushButton("Импорт из PDF")
        self.button_import.clicked.connect(self.import_pdf)
        layout.addWidget(self.button_import)

        self.button_show_table = QPushButton("Открыть список организаций")
        self.button_show_table.clicked.connect(self.show_table)
        layout.addWidget(self.button_show_table)

        self.form = QFormLayout()
        self.fields = {
            "full_name": QLineEdit(),
            "short_name": QLineEdit(),
            "inn": QLineEdit(),
            "kpp": QLineEdit(),
            "ogrn": QLineEdit(),
            "address": QLineEdit(),
            "head_fio": QLineEdit(),
            "reg_number": QLineEdit(),
            "inn_fl": QLineEdit(),
            "post" : QLineEdit()
        }
        self.form.addRow("Полное наименование", self.fields["full_name"])
        self.form.addRow("Сокращенное наименование", self.fields["short_name"])
        self.form.addRow("ИНН", self.fields["inn"])
        self.form.addRow("КПП", self.fields["kpp"])
        self.form.addRow("ОГРН", self.fields["ogrn"])
        self.form.addRow("Адрес", self.fields["address"])
        self.form.addRow("ФИО руководителя", self.fields["head_fio"])
        self.form.addRow("Рег. номер страхователя", self.fields["reg_number"])
        self.form.addRow("ИНН физического лица", self.fields["inn_fl"])
        self.form.addRow("Должность", self.fields["post"])
        layout.addLayout(self.form)

        self.button_save = QPushButton("Сохранить изменения")
        self.button_save.clicked.connect(self.save_changes)
        layout.addWidget(self.button_save)

        self.setLayout(layout)

    def get_current_key(self):
        return self.key_field.text().strip()

    def load_by_key(self):
        key = self.get_current_key()
        if not key:
            self.label.setText("Введите ключ!")
            return

        data = load_json()
        if key in data:
            org = data[key]
            for k, field in self.fields.items():
                field.setText(org.get(k, ""))
            self.label.setText(f"Загружены данные для ключа {key}")
        else:
            self.label.setText(f"Организация с ключом {key} не найдена")

    def import_pdf(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Выбрать PDF", "", "PDF Files (*.pdf)")
        if not file_path:
            return

        result = extract_from_tables(file_path)
        key = self.get_current_key()
        if not key:
            self.label.setText("Введите ключ перед импортом PDF!")
            return

        data = load_json()
        data[key] = result
        save_json(data)

        for k, field in self.fields.items():
            field.setText(result.get(k, ""))

        self.label.setText(f"Импорт завершён. Данные сохранены под ключом {key}")

    def save_changes(self):
        key = self.get_current_key()
        if not key:
            self.label.setText("Введите ключ для сохранения!")
            return

        data = load_json()
        org = {}
        for k, field in self.fields.items():
            org[k] = field.text().strip()

        data[key] = org
        save_json(data)

        self.label.setText(f"Изменения сохранены для ключа {key}")

    def show_table(self):
        dialog = OrgTableDialog(self)
        if dialog.exec():
            if dialog.selected_key:
                self.key_field.setText(dialog.selected_key)
                self.load_by_key()
