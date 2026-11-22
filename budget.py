# budget.py
"""
Модуль GUI для реестра УБП/НУБП.
Подходит для импорта в лаунчер: вызывает create_app_window(db_path=None, app_already_running=False)
Функция create_app_window возвращает кортеж (app, window) и не вызывает app.exec().
"""

import sys
import json
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin
import re

import requests
from PyQt6.QtCore import QObject, pyqtSignal, QThread, Qt, QSize, QTimer
from PyQt6.QtGui import QFont, QFontMetrics, QGuiApplication
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QListWidget, QTextEdit, QInputDialog, QMessageBox, QFileDialog,
    QFrame, QScrollArea, QGridLayout, QSizePolicy, QToolButton, QTabWidget,
    QSplitter
)

__all__ = ["MainWindow", "create_app_window"]

# --- constants ---
DB_PATH = Path("db.json")
LAST_API_DUMP = Path("last_api_response.json")
LAST_LINK_DUMP = Path("last_link_responses.json")
FOUND_ACCOUNTS_DUMP = Path("found_accounts.json")
API_BASE = "https://budget.gov.ru/epbs/registry/ubpandnubp/data"
API_TIMEOUT = 20

BROWSER_HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json, text/javascript, */*; q=0.01"}

GLOBAL_HIDDEN_KEYS = {
    "refopenufkcode","refsrvufkcode","contourtypecode","controlnum","cpzcode",
    "firstregguid","lastregguid","reforfkcode","updatenum","isexcluded","isogv",
    "isobosob","isreorg","isuch","egrulnotincluded","citytype","establishmentkindcode",
    "streettype","updatereason","founderkindcode","guid"
}

LABELS_RU = {
    "regNum":"Учетный номер","code":"Код организации","ogrn":"ОГРН","fullName":"Полное наименование",
    "shortName":"Краткое наименование","inn":"ИНН","kpp":"КПП","regDate":"Дата постановки на учет",
    "orfkName":"ОрФК (наименование)","orfkCode":"ОрФК (код)","oktmoName":"ОКТМО (наименование)",
    "oktmoCode":"ОКТМО (код)","streetName":"Улица","streetCode":"Код улицы","house":"Дом",
    "postIndex":"Индекс","uoName":"Уполномоченная организация","uoCode":"Код УО",
    "budgetName":"Бюджет (наименование)","budgetCode":"Код бюджета","budgetLvlName":"Уровень бюджета",
    "budgetLvlCode":"Код уровня бюджета","status":"Статус записи","statusCode":"Код статуса организации",
    "statusName":"Наименование статуса организации","recordNum":"Номер записи","guid":"GUID",
    "loadDate":"Дата загрузки","dateUpdate":"Дата обновления","firstRegDate":"Дата первой регистрации",
    "firstRegGuid":"GUID первой регистрации","lastRegDate":"Дата последней регистрации",
    "lastRegGuid":"GUID последней регистрации","nameDocs":"Наименование (nameDocs)","okfsName":"Форма собственности",
    "okfsCode":"Код формы собственности","okopfName":"Организационно-правовая форма","okopfCode":"Код ОКОПФ",
    "okpoCode":"ОКПО","orgTypeName":"Тип организации","orgTypeCode":"Код типа организации",
    "nubpCode":"Учетный номер НУБП","inclusionDate":"Дата включения в реестр","startDate":"Дата начала",
    "lastRegNum":"Номер последней регистрации","updateReason":"Причина обновления","updateNum":"Номер обновления",
    "areaName":"Наименование населенного пункта","areaType":"Тип населенного пункта","cityName":"Наименование населенного пункта",
    "cityType":"Тип населенного пункта","cityCode":"Код населенного пункта","localName":"Наименование (локальное)",
    "localType":"Тип населенного пункта (локальный)","regionCode":"Код региона","regionKladrCode":"КЛАДР региона",
    "regionName":"Наименование региона","founderKindCode":"Код вида основателя","founderKindName":"Вид основателя",
    "founderPlaceCode":"Код места основания","founderPlaceName":"Место основания","kbkCode":"Код КБК","kbkName":"КБК (наименование)",
    "bidNum":"Номер заявки/бид","legalPersonKindCode":"Код вида юридического лица","legalPersonKindName":"Вид юридического лица",
    "fio":"ФИО","post":"Должность","docName":"Документ","docNum":"Номер документа","docDate":"Дата документа","headMain":"Первое лицо",
    "num":"Номер лицевого счета","kindName":"Тип лицевого счета","kindCode":"Код типа лицевого счета",
    "createDate":"Дата открытия","closeDate":"Дата закрытия","openUfkCode":"Код ТОФК открытия",
    "openUfkName":"ТОФК открытия (наименование)","openTofkName":"ТОФК открытия (код по сводному реестру)",
    "srvUfkCode":"Код ОрФК обслуживания","srvUfkName":"ОрФК обслуживания (наименование)","ppocode":"Код ППО",
    "pponame":"ППО (наименование)","accountorgcode":"Код принимающей организации","accountorgfullname":"Наименование принимающей организации",
    "phone":"Телефон","site":"Сайт","mail":"Эл. почта","activityCode":"Код ОКВЭД","activityName":"Наименование вида деятельности",
    "activityKind":"Вид (основной/иной)","code":"Код","name":"Наименование"
}

# ---------------- utils ----------------
def dump_json(path: Path, obj: Any):
    try:
        with path.open("w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def load_db() -> Dict[str, Any]:
    if not DB_PATH.exists():
        return {}
    try:
        with DB_PATH.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_db(db: Dict[str, Any]):
    try:
        with DB_PATH.open("w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def _get_ci(d: Dict[str, Any], key: str, default=None):
    if not isinstance(d, dict):
        return default
    if key in d:
        return d[key]
    lk = key.lower()
    for k, v in d.items():
        if isinstance(k, str) and k.lower() == lk:
            return v
    return default

def find_facial_territorial_block(src: Dict[str, Any], link_responses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    found: List[Dict[str, Any]] = []
    def add_from_val(val):
        if isinstance(val, list):
            for it in val:
                if isinstance(it, dict):
                    found.append(it)
        elif isinstance(val, dict):
            found.append(val)
    if isinstance(src, dict) and "data" in src and isinstance(src["data"], list):
        for rec in src["data"]:
            if not isinstance(rec, dict):
                continue
            if rec.get("facialAccounts"):
                add_from_val(rec["facialAccounts"])
            if rec.get("ksaccounts"):
                add_from_val(rec["ksaccounts"])
            info = rec.get("info")
            if isinstance(info, dict) and info.get("facialAccounts"):
                add_from_val(info["facialAccounts"])
    for k in ("facialAccounts","facialaccounts","faceAccounts","accountfk","accounts","ksaccounts"):
        if k in src and src[k]:
            add_from_val(src[k])
    info = src.get("info")
    if isinstance(info, dict):
        for k in ("facialAccounts","facialaccounts","faceAccounts","accountfk"):
            if k in info and info[k]:
                add_from_val(info[k])
    for lr in (link_responses or []):
        data = lr.get("data")
        if not data:
            continue
        if isinstance(data, dict) and "data" in data and isinstance(data["data"], list):
            for rec in data["data"]:
                if not isinstance(rec, dict):
                    continue
                if rec.get("facialAccounts"):
                    add_from_val(rec["facialAccounts"])
                for alt in ("facialaccounts","faceAccounts","accountfk"):
                    if alt in rec and rec[alt]:
                        add_from_val(rec[alt])
        if isinstance(data, dict):
            for k in ("facialAccounts","facialaccounts","faceAccounts","accountfk","accounts","ksaccounts"):
                if k in data and data[k]:
                    add_from_val(data[k])
        elif isinstance(data, list):
            add_from_val(data)
    def collect_typical(x):
        if isinstance(x, dict):
            keys = set(k.lower() for k in x.keys() if isinstance(k, str))
            if {"num","srvufkcode","ppocode","pponame","kindname"} & keys:
                found.append(x)
            for v in x.values():
                collect_typical(v)
        elif isinstance(x, list):
            for it in x:
                collect_typical(it)
    collect_typical(src)
    for lr in (link_responses or []):
        collect_typical(lr.get("data"))
    uniq: List[Dict[str, Any]] = []
    seen = set()
    for r in found:
        if not isinstance(r, dict):
            continue
        num = str(r.get("num","")).strip()
        srv = str(r.get("srvUfkCode", r.get("srvufkcode",""))).strip()
        open_to = str(r.get("openTofkName", r.get("openTofkname", r.get("openTofkName","")))).strip()
        key = (num, srv, open_to)
        if key in seen:
            continue
        seen.add(key)
        uniq.append(r)
    return uniq

class ApiWorker(QObject):
    finished = pyqtSignal(dict, list)
    error = pyqtSignal(str)
    def __init__(self, query: str, by_inn: bool):
        super().__init__()
        self.query = query
        self.by_inn = by_inn
        self.blocks = "info,authorities,heads,facialAccounts,accountfk,foAccounts,ksAccounts,contacts,activities,nonParticipantPermissions,participantPermissions,procurementPermissions,acceptAuths,successions"
        self.session = requests.Session()
        self.session.headers.update(BROWSER_HEADERS)
    def _safe_get(self, url: str) -> Optional[Any]:
        try:
            r = self.session.get(url, timeout=API_TIMEOUT)
            r.raise_for_status()
            return r.json()
        except Exception:
            return None
    def run(self):
        try:
            params = {"blocks": self.blocks, "pageSize": "100"}
            if self.by_inn:
                params["filterinn"] = self.query
            else:
                params["filtername"] = self.query
            resp = self.session.get(API_BASE, params=params, timeout=API_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            dump_json(LAST_API_DUMP, data)
            
            # Улучшенный поиск списка данных
            candidate_list = None
            if isinstance(data, dict):
                if "data" in data and isinstance(data["data"], list):
                    candidate_list = data["data"]
                else:
                    # Проверяем другие возможные ключи
                    for k in ("result", "items", "response", "records", "list"):
                        if k in data and isinstance(data[k], list) and data[k]:
                            candidate_list = data[k]
                            break
            
            if candidate_list is None:
                # Если это не список, возможно пришел один объект
                if isinstance(data, dict) and any(key in data for key in ("info", "inn", "fullName")):
                    candidate_list = [data]
                else:
                    candidate_list = []

            if not candidate_list:
                # Если данных нет, прерываем с ошибкой
                self.error.emit("API вернул пустой результат. Организация не найдена или доступ к данным ограничен.")
                return

            source_obj = candidate_list[0]
            link_responses = []
            def follow_link(raw_link: str):
                if not raw_link or not isinstance(raw_link, str):
                    return None
                raw = raw_link.strip()
                url = urljoin("https://budget.gov.ru", raw) if raw.startswith("/") else raw
                return self._safe_get(url)
            info_block = _get_ci(source_obj, "info") or source_obj
            ref_fields = ["reforfkCode","refopenUfkCode","refsrvUfkCode","refokoguCode","refokopfCode","refkofkCode"]
            for rk in ref_fields:
                raw = _get_ci(info_block, rk) or _get_ci(source_obj, rk)
                if raw:
                    d = follow_link(raw)
                    if d:
                        link_responses.append({"field": rk, "url": raw, "data": d})
            dump_json(LAST_LINK_DUMP, link_responses)
            found = find_facial_territorial_block(source_obj, link_responses)
            try:
                dump_json(FOUND_ACCOUNTS_DUMP, found)
            except Exception:
                pass
            self.finished.emit(source_obj, link_responses)
        except Exception as e:
            tb = traceback.format_exc()
            self.error.emit(f"{str(e)}\n{tb}")

# ---------------- formatting helpers ----------------
def human_label(key: str) -> str:
    if not isinstance(key, str):
        return str(key)
    for k, v in LABELS_RU.items():
        if k.lower() == key.lower():
            return v
    s = key.replace("_", " ")
    s = re.sub(r"([a-zа-я])([A-ZА-Я])", r"\1 \2", s)
    s = re.sub(r"([A-Z]{2,})([A-Z][a-z])", r"\1 \2", s)
    s = re.sub(r"\s+", " ", s).strip()
    if not s:
        return key
    return s[0].upper() + s[1:]

def is_hidden_key(key: str, extra_excluded: Optional[set] = None) -> bool:
    if not isinstance(key, str):
        return False
    if key.lower() in GLOBAL_HIDDEN_KEYS:
        return True
    if extra_excluded and key.lower() in {x.lower() for x in extra_excluded}:
        return True
    return False

def format_any_dict_items(d: Dict[str, Any], extra_excluded: Optional[set] = None) -> List[Tuple[str, str]]:
    items: List[Tuple[str, str]] = []
    extra_excluded = extra_excluded or set()
    preferred = ["num","kindCode","kindName","status","createDate","openUfkCode","openUfkName","srvUfkCode","srvUfkName","ppocode","pponame"]
    keys_order: List[str] = []
    for k in preferred:
        if k in d and not is_hidden_key(k, extra_excluded):
            keys_order.append(k)
    for k in sorted(d.keys(), key=lambda x: str(x).lower()):
        if k in keys_order or is_hidden_key(k, extra_excluded):
            continue
        keys_order.append(k)
    for k in keys_order:
        if is_hidden_key(k, extra_excluded):
            continue
        v = d.get(k)
        if v is None:
            continue
        if isinstance(v, str) and v.strip() == "":
            continue
        if isinstance(v, list):
            if not v:
                continue
            if all(not isinstance(it, (dict, list)) for it in v):
                val = "; ".join(str(it) for it in v)
            else:
                val = json.dumps(v, ensure_ascii=False)
        elif isinstance(v, dict):
            val = json.dumps(v, ensure_ascii=False)
        else:
            val = str(v)
        label = human_label(k)
        items.append((label, val))
    return items

def scaled_base_font() -> QFont:
    screen = QGuiApplication.primaryScreen()
    dpi = 96
    try:
        dpi = int(screen.logicalDotsPerInch())
    except Exception:
        dpi = 96
    base_pt = max(8, int(10 * dpi / 96))
    font_family = "Segoe UI" if sys.platform.startswith("win") else "Arial"
    return QFont(font_family, base_pt)

# ---------------- UI: single-line values and bold labels ----------------
def make_tab_content_widget_one_column_no_wrap(items: List[Tuple[str, str]]) -> QWidget:
    container = QWidget()
    layout = QGridLayout()
    layout.setHorizontalSpacing(8)
    layout.setVerticalSpacing(8)
    layout.setContentsMargins(8, 8, 8, 8)
    container.setLayout(layout)

    font = scaled_base_font()
    fm = QFontMetrics(font)

    # compute max pixel widths for labels and values (single-line)
    max_label_px = 0
    max_value_px = 0
    pad = 40
    for lab, val in items:
        lw = fm.horizontalAdvance(lab + ":")
        vw = fm.horizontalAdvance(val)
        if lw > max_label_px: max_label_px = lw
        if vw > max_value_px: max_value_px = vw

    screen = QGuiApplication.primaryScreen()
    screen_w = screen.size().width() if screen else 1600
    max_label_px = min(max_label_px + pad, int(screen_w * 0.5))
    max_value_px = min(max_value_px + pad, int(screen_w * 0.9))

    layout.setColumnMinimumWidth(0, 30)  # copy button
    layout.setColumnMinimumWidth(1, max_label_px)
    layout.setColumnMinimumWidth(2, max_value_px)
    layout.setColumnStretch(0, 0)
    layout.setColumnStretch(1, 0)
    layout.setColumnStretch(2, 1)

    btn_style = (
        "QToolButton { padding: 0px; margin: 0px; border: 1px solid transparent; border-radius: 4px; }"
        "QToolButton:hover { background: #eef6ff; border: 1px solid #cfe8ff; }"
        "QToolButton:pressed { background: #cfe8ff; border: 1px solid #7fbfff; }"
        "QToolButton:checked { background: #7fd0ff; border: 1px solid #3faeff; }"
    )

    label_font = QFont(font)
    label_font.setBold(True)

    for row, (label_text, value_text) in enumerate(items):
        copy_btn = QToolButton()
        copy_btn.setAutoRaise(False)
        copy_btn.setText("📋")
        copy_btn.setToolTip("Копировать значение")
        copy_btn.setProperty("copy_text", value_text)
        copy_btn.setCheckable(True)
        copy_btn.setStyleSheet(btn_style)
        copy_btn.setFixedSize(QSize(28, 28))

        def on_copy_clicked(checked, b=copy_btn):
            QApplication.clipboard().setText(b.property("copy_text"))
            b.setChecked(True)
            old_text = b.text()
            b.setText("✓")
            QTimer.singleShot(550, lambda: (b.setChecked(False), b.setText(old_text)))

        copy_btn.clicked.connect(on_copy_clicked)

        lbl = QLabel(f"{label_text}:")
        lbl.setFont(label_font)
        lbl.setWordWrap(False)
        lbl.setSizePolicy(QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed))
        lbl.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        lbl.setToolTip(label_text)

        val_lbl = QLabel(value_text)
        val_lbl.setFont(font)
        val_lbl.setWordWrap(False)
        val_lbl.setSizePolicy(QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed))
        val_lbl.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        val_lbl.setToolTip(value_text)
        val_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        layout.addWidget(copy_btn, row, 0, alignment=Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(lbl, row, 1, alignment=Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(val_lbl, row, 2, alignment=Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)

    spacer = QLabel()
    spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    layout.addWidget(spacer, len(items) + 1, 0, 1, 3)
    return container

def make_tab_widget_from_items_no_wrap(title: str, items: List[Tuple[str, str]]) -> QWidget:
    content = make_tab_content_widget_one_column_no_wrap(items)
    container = QWidget()
    v = QVBoxLayout(container)
    v.setContentsMargins(0, 0, 0, 0)
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    scroll.setWidget(content)
    v.addWidget(scroll)
    return container

# ---------------- normalization / build tabs ----------------
def section_info_data(src: Dict[str, Any]) -> Dict[str, Any]:
    info_block = _get_ci(src, "info") or src
    if isinstance(info_block, dict):
        return info_block
    return {}

def normalize_saved_record_to_api_shape(saved: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(saved, dict):
        return saved
    api_like: Dict[str, Any] = {}
    info = saved.get("INFO") or saved.get("info") or {}
    api_like["info"] = info.copy() if isinstance(info, dict) else {}
    heads = saved.get("HEADS") or saved.get("heads") or []
    if isinstance(heads, dict):
        heads = [heads]
    api_like["heads"] = heads
    fac = saved.get("facialTerritorialAccounts") or saved.get("facialterritorialaccounts") or saved.get("facialAccounts") or saved.get("facialaccounts") or []
    if isinstance(fac, dict):
        fac = [fac]
    api_like["facialAccounts"] = fac
    kss = saved.get("ksAccounts") or saved.get("ksaccounts") or []
    if isinstance(kss, dict):
        kss = [kss]
    api_like["ksAccounts"] = kss
    auths = saved.get("authorities") or saved.get("authority") or []
    if isinstance(auths, dict):
        auths = [auths]
    api_like["authorities"] = auths
    contacts = saved.get("contacts") or saved.get("Contacts")
    activities = saved.get("activities") or saved.get("Activities")
    extra = saved.get("extra") or {}
    if not contacts and isinstance(extra, dict):
        contacts = extra.get("contacts") or extra.get("Contacts")
    if not activities and isinstance(extra, dict):
        activities = extra.get("activities") or extra.get("Activities")
    if isinstance(contacts, dict):
        contacts = [contacts]
    api_like["contacts"] = contacts or []
    if isinstance(activities, dict):
        activities = [activities]
    api_like["activities"] = activities or []
    if isinstance(extra, dict):
        for k, v in extra.items():
            if k.lower() in {"contacts","activities","acceptauths"}:
                continue
            if k not in api_like["info"]:
                api_like["info"][k] = v
    return api_like

def build_tabs_for_record(source: Dict[str, Any], link_responses: List[Dict[str, Any]]) -> QTabWidget:
    tabs = QTabWidget()
    info = section_info_data(source)
    if info:
        tabs.addTab(make_tab_widget_from_items_no_wrap("Информация", format_any_dict_items(info)), "Информация")
    heads = _get_ci(source, "heads") or _get_ci(source, "HEADS") or []
    if isinstance(heads, dict):
        heads = [heads]
    for h in heads:
        if isinstance(h, dict):
            tabs.addTab(make_tab_widget_from_items_no_wrap("Руководитель", format_any_dict_items(h)), "Руководитель")
    facs = find_facial_territorial_block(source, link_responses)
    for i, f in enumerate(facs, 1):
        if isinstance(f, dict):
            tabs.addTab(make_tab_widget_from_items_no_wrap(f"Лицевой счёт {i}", format_any_dict_items(f)), f"Лицевой {i}")
    kss = _get_ci(source, "ksAccounts") or _get_ci(source, "ksaccounts") or []
    if isinstance(kss, dict):
        kss = [kss]
    for k in kss:
        if isinstance(k, dict):
            tabs.addTab(make_tab_widget_from_items_no_wrap("Казнач. счёт", format_any_dict_items(k)), "Казнач. счёт")
    contacts = _get_ci(source, "contacts")
    if contacts:
        if isinstance(contacts, dict):
            contacts = [contacts]
        for c in contacts:
            if isinstance(c, dict):
                tabs.addTab(make_tab_widget_from_items_no_wrap("Контакты", format_any_dict_items(c)), "Контакты")
    activities = _get_ci(source, "activities")
    if activities:
        if isinstance(activities, dict):
            activities = [activities]
        for a in activities:
            if isinstance(a, dict):
                tabs.addTab(make_tab_widget_from_items_no_wrap("Деятельность", format_any_dict_items(a)), "Деятельность")
    auths = _get_ci(source, "authorities") or _get_ci(source, "authority")
    if auths:
        if isinstance(auths, dict):
            auths = [auths]
        for a in auths:
            if isinstance(a, dict):
                tabs.addTab(make_tab_widget_from_items_no_wrap("Учредитель", format_any_dict_items(a)), "Учредитель")
    tabs.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    return tabs

# ---------------- Main window ----------------
class Budget(QWidget):
    def __init__(self, db_path: Optional[str] = None):
        super().__init__()
        if db_path:
            global DB_PATH
            DB_PATH = Path(db_path)
        self.setWindowTitle("Реестр УБП/НУБП")
        self.resize(1400, 820)
        self.db = load_db()
        self.last_source: Dict[str, Any] = {}
        self.last_link_responses: List[Dict[str, Any]] = []
        self.requested_inn: Optional[str] = None

        main = QVBoxLayout(self)
        main.setContentsMargins(6, 0, 6, 6)
        main.setSpacing(4)

        top_row = QHBoxLayout()
        top_row.setSpacing(6)
        top_row.setContentsMargins(0, 4, 0, 4)
        self.input_q = QLineEdit()
        self.input_q.setPlaceholderText("ИНН или наименование")
        self.btn_inn = QPushButton("По ИНН")
        self.btn_name = QPushButton("По наименованию")
        self.btn_save_found = QPushButton("Сохранить")
        self.btn_show_raw = QPushButton("Raw")
        self.btn_add_manual = QPushButton("Добавить")
        top_row.addWidget(self.input_q, 3)
        top_row.addWidget(self.btn_inn)
        top_row.addWidget(self.btn_name)
        top_row.addWidget(self.btn_save_found)
        top_row.addWidget(self.btn_show_raw)
        top_row.addWidget(self.btn_add_manual)
        main.addLayout(top_row)

        key_row = QHBoxLayout()
        key_row.setSpacing(6)
        key_row.setContentsMargins(0, 2, 0, 6)
        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("Введите ключ сохранённой организации")
        self.btn_load_by_key = QPushButton("Загрузить по ключу")
        key_row.addWidget(self.key_input, 3)
        key_row.addWidget(self.btn_load_by_key)
        main.addLayout(key_row)

        main.addWidget(self._sep())

        splitter = QSplitter(Qt.Orientation.Horizontal)
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(6,6,6,6)
        left_layout.setSpacing(6)
        left_layout.addWidget(QLabel("Сохранённые записи"))
        self.list_widget = QListWidget()
        left_layout.addWidget(self.list_widget)
        left_btns = QHBoxLayout()
        self.btn_open = QPushButton("Показать")
        self.btn_delete = QPushButton("Удалить")
        self.btn_export = QPushButton("Экспорт")
        self.btn_refresh_record = QPushButton("Обновить")
        left_btns.addWidget(self.btn_open)
        left_btns.addWidget(self.btn_delete)
        left_btns.addWidget(self.btn_export)
        left_btns.addWidget(self.btn_refresh_record)
        left_layout.addLayout(left_btns)
        left_widget.setMinimumWidth(260)
        splitter.addWidget(left_widget)

        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(6,6,6,6)
        right_layout.setSpacing(6)
        title = QLabel("Реквизиты (вкладки по группам)")
        title.setFont(scaled_base_font())
        right_layout.addWidget(title)
        self.tab_area = QScrollArea()
        self.tab_area.setWidgetResizable(True)
        self.tab_container = QWidget()
        self.tab_layout = QVBoxLayout(self.tab_container)
        self.tab_layout.setContentsMargins(6, 6, 6, 6)
        self.tab_layout.setSpacing(6)
        self.tab_area.setWidget(self.tab_container)
        right_layout.addWidget(self.tab_area)
        splitter.addWidget(right_widget)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([320, 1100])

        main.addWidget(splitter)

        # signals
        self.btn_inn.clicked.connect(self.on_search_inn)
        self.btn_name.clicked.connect(self.on_search_name)
        self.btn_save_found.clicked.connect(self.on_save_last)
        self.btn_show_raw.clicked.connect(self.on_show_raw)
        self.btn_add_manual.clicked.connect(self.on_add_manual)
        self.btn_open.clicked.connect(self.on_open_selected)
        self.btn_delete.clicked.connect(self.on_delete_selected)
        self.btn_export.clicked.connect(self.on_export_db)
        self.btn_refresh_record.clicked.connect(self.on_refresh_selected)
        self.list_widget.itemSelectionChanged.connect(self.on_selection_changed)
        self.btn_load_by_key.clicked.connect(self.on_load_by_key)

        self._refresh_list()

    def _sep(self):
        f = QFrame()
        f.setFrameShape(QFrame.Shape.HLine)
        f.setFrameShadow(QFrame.Shadow.Sunken)
        f.setLineWidth(1)
        return f

    def _refresh_list(self):
        self.list_widget.clear()
        for k in sorted(self.db.keys()):
            self.list_widget.addItem(k)

    def _get_display_source_from_saved(self, saved: Dict[str, Any]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        link_responses: List[Dict[str, Any]] = []
        if not isinstance(saved, dict):
            return saved, link_responses
        raw = saved.get("raw_api")
        if raw:
            if isinstance(raw, dict) and "data" in raw and isinstance(raw["data"], list) and raw["data"]:
                source_obj = raw["data"][0]
            else:
                source_obj = raw if isinstance(raw, dict) else saved
            lr = saved.get("raw_links")
            if isinstance(lr, list):
                link_responses = lr
            return source_obj, link_responses
        normalized = normalize_saved_record_to_api_shape(saved)
        return normalized, link_responses

    def on_load_by_key(self):
        key = self.key_input.text().strip()
        if not key:
            QMessageBox.information(self, "Инфо", "Введите ключ")
            return
        rec = self.db.get(key)
        if not rec:
            QMessageBox.warning(self, "Не найдено", f"Ключ '{key}' не найден в базе")
            return
        source_obj, link_responses = self._get_display_source_from_saved(rec)
        self.show_record_tabs(source_obj, link_responses)

    def on_selection_changed(self):
        it = self.list_widget.currentItem()
        if not it:
            while self.tab_layout.count():
                item = self.tab_layout.takeAt(0)
                w = item.widget()
                if w:
                    w.deleteLater()
            return
        rec = self.db.get(it.text(), {})
        source_obj, link_responses = self._get_display_source_from_saved(rec)
        self.show_record_tabs(source_obj, link_responses)

    def show_record_tabs(self, rec: Dict[str, Any], link_responses: List[Dict[str, Any]] = []):
        while self.tab_layout.count():
            item = self.tab_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        tabs = build_tabs_for_record(rec, link_responses or [])
        tabs.setMinimumHeight(300)
        tabs.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.tab_layout.addWidget(tabs)

    def _start_worker(self, query: str, by_inn: bool, callback):
        self.thread = QThread()
        self.worker = ApiWorker(query=query, by_inn=by_inn)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(callback)
        self.worker.error.connect(self._on_api_error)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.worker.error.connect(self.thread.quit)
        self.thread.start()

    def on_search_inn(self):
        q = self.input_q.text().strip()
        if not q:
            QMessageBox.warning(self, "Ошибка", "Введите ИНН")
            return
        self.requested_inn = q
        try:
            if LAST_API_DUMP.exists(): LAST_API_DUMP.unlink()
            if LAST_LINK_DUMP.exists(): LAST_LINK_DUMP.unlink()
            if FOUND_ACCOUNTS_DUMP.exists(): FOUND_ACCOUNTS_DUMP.unlink()
        except Exception:
            pass
        self._start_worker(q, by_inn=True, callback=self._on_api_finished)

    def on_search_name(self):
        q = self.input_q.text().strip()
        if not q:
            QMessageBox.warning(self, "Ошибка", "Введите наименование")
            return
        self.requested_inn = None
        try:
            if LAST_API_DUMP.exists(): LAST_API_DUMP.unlink()
            if LAST_LINK_DUMP.exists(): LAST_LINK_DUMP.unlink()
            if FOUND_ACCOUNTS_DUMP.exists(): FOUND_ACCOUNTS_DUMP.unlink()
        except Exception:
            pass
        self._start_worker(q, by_inn=False, callback=self._on_api_finished)

    def _on_api_finished(self, source_obj: Dict[str, Any], link_responses: List[Dict[str, Any]]):
        self.last_source = source_obj
        self.last_link_responses = link_responses or []
        actual_inn = None
        try:
            actual_inn = _get_ci(source_obj.get("info", {}), "inn") or _get_ci(source_obj, "inn")
        except Exception:
            actual_inn = None
        if self.requested_inn and actual_inn and str(actual_inn).strip() != str(self.requested_inn).strip():
            QMessageBox.warning(self, "Предупреждение", f"Введённый ИНН: {self.requested_inn}\nВ ответе API INN: {actual_inn}\nПроверьте ввод или откройте raw ответ.")
        while self.tab_layout.count():
            item = self.tab_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        tabs = build_tabs_for_record(source_obj, link_responses or [])
        self.tab_layout.addWidget(tabs)
        msg = "Результат показан."
        if LAST_API_DUMP.exists(): msg += f" Full API response -> {LAST_API_DUMP.name}."
        if LAST_LINK_DUMP.exists(): msg += f" Link responses -> {LAST_LINK_DUMP.name}."
        QMessageBox.information(self, "Найдено", msg + " Нажмите 'Сохранить' чтобы записать в базу.")

    def _on_api_error(self, message: str):
        QMessageBox.critical(self, "Ошибка API", f"Ошибка при запросе:\n{message}")

    def on_save_last(self):
        if not self.last_source:
            QMessageBox.information(self, "Инфо", "Нет результата для сохранения")
            return
        key, ok = QInputDialog.getText(self, "Ключ", "Введите ключ для сохранения:")
        if not ok or not key:
            return
        if key in self.db:
            resp = QMessageBox.question(self, "Перезаписать?", f"Ключ '{key}' уже есть. Перезаписать?")
            if resp != QMessageBox.StandardButton.Yes:
                return
        mapped = {"INFO": {}, "authorities": [], "HEADS": [], "facialTerritorialAccounts": [], "ksAccounts": [], "extra": {}}
        info_src = _get_ci(self.last_source, "info") or self.last_source
        if isinstance(info_src, dict):
            for k, v in info_src.items():
                if v is not None and (not isinstance(v, str) or v.strip() != "") and k.lower() not in GLOBAL_HIDDEN_KEYS:
                    mapped["INFO"][k] = v
        auths = _get_ci(self.last_source, "authorities") or _get_ci(self.last_source, "authority") or []
        if isinstance(auths, dict):
            auths = [auths]
        for a in auths:
            mapped["authorities"].append(a)
        heads = _get_ci(self.last_source, "heads") or _get_ci(self.last_source, "HEADS") or []
        if isinstance(heads, dict):
            heads = [heads]
        for h in heads:
            mapped["HEADS"].append(h)
        facs = find_facial_territorial_block(self.last_source, self.last_link_responses)
        for f in facs:
            rec = {k: v for k, v in f.items() if k.lower() not in GLOBAL_HIDDEN_KEYS and v is not None and (not isinstance(v, str) or v.strip() != "")}
            mapped["facialTerritorialAccounts"].append(rec)
        kss = _get_ci(self.last_source, "ksAccounts") or _get_ci(self.last_source, "ksaccounts") or []
        if isinstance(kss, dict):
            kss = [kss]
        for k in kss:
            mapped["ksAccounts"].append(k)
        if isinstance(self.last_source, dict):
            for k, v in self.last_source.items():
                if k.lower() in {"info","authorities","heads","facialaccounts","ksaccounts"}:
                    continue
                mapped["extra"][k] = v
        raw_api_obj = None
        try:
            if LAST_API_DUMP.exists():
                with LAST_API_DUMP.open("r", encoding="utf-8") as f:
                    raw_api_obj = json.load(f)
        except Exception:
            raw_api_obj = None
        if raw_api_obj:
            mapped["raw_api"] = raw_api_obj
        if self.last_link_responses:
            mapped["raw_links"] = self.last_link_responses
        self.db[key] = mapped
        save_db(self.db)
        self._refresh_list()
        QMessageBox.information(self, "Сохранено", f"Сохранено под ключом '{key}'")

    def on_show_raw(self):
        parts = []
        if LAST_API_DUMP.exists():
            try:
                with LAST_API_DUMP.open("r", encoding="utf-8") as f:
                    jd = json.load(f)
                parts.append("MAIN:\n" + json.dumps(jd, ensure_ascii=False, indent=2))
            except Exception as e:
                parts.append(f"Не удалось прочитать {LAST_API_DUMP.name}: {e}")
        if LAST_LINK_DUMP.exists():
            try:
                with LAST_LINK_DUMP.open("r", encoding="utf-8") as f:
                    jd = json.load(f)
                parts.append("LINKS:\n" + json.dumps(jd, ensure_ascii=False, indent=2))
            except Exception as e:
                parts.append(f"Не удалось прочитать {LAST_LINK_DUMP.name}: {e}")
        if FOUND_ACCOUNTS_DUMP.exists():
            try:
                with FOUND_ACCOUNTS_DUMP.open("r", encoding="utf-8") as f:
                    jd = json.load(f)
                parts.append("FOUND_ACCOUNTS:\n" + json.dumps(jd, ensure_ascii=False, indent=2))
            except Exception:
                pass
        if not parts:
            QMessageBox.information(self, "Raw ответ", "Нет сохранённых raw ответов")
            return
        dlg = QTextEdit()
        dlg.setReadOnly(True)
        dlg.setWindowTitle("Raw API responses")
        dlg.setPlainText("\n\n".join(parts))
        dlg.resize(1000, 700)
        dlg.show()
        self._raw_window = dlg

    def on_add_manual(self):
        key, ok = QInputDialog.getText(self, "Ключ", "Введите ключ для пустой записи:")
        if not ok or not key:
            return
        if key in self.db:
            resp = QMessageBox.question(self, "Перезаписать?", f"Ключ '{key}' уже есть. Перезаписать?")
            if resp != QMessageBox.StandardButton.Yes:
                return
        empty = {"INFO": {}, "authorities": [], "HEADS": [], "facialTerritorialAccounts": [], "ksAccounts": [], "extra": {}}
        self.db[key] = empty
        save_db(self.db)
        self._refresh_list()

    def on_open_selected(self):
        it = self.list_widget.currentItem()
        if not it:
            QMessageBox.information(self, "Инфо", "Выберите запись")
            return
        rec = self.db.get(it.text(), {})
        source_obj, link_responses = self._get_display_source_from_saved(rec)
        self.show_record_tabs(source_obj, link_responses)

    def on_delete_selected(self):
        it = self.list_widget.currentItem()
        if not it:
            QMessageBox.information(self, "Инфо", "Выберите запись")
            return
        key = it.text()
        r = QMessageBox.question(self, "Удалить", f"Удалить запись '{key}'?")
        if r == QMessageBox.StandardButton.Yes:
            self.db.pop(key, None)
            save_db(self.db)
            self._refresh_list()
            while self.tab_layout.count():
                item = self.tab_layout.takeAt(0)
                w = item.widget()
                if w:
                    w.deleteLater()

    def on_export_db(self):
        filename, _ = QFileDialog.getSaveFileName(self, "Экспортировать базу как JSON", "", "JSON files (*.json);;All files (*.*)")
        if not filename:
            return
        try:
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(self.db, f, ensure_ascii=False, indent=2)
            QMessageBox.information(self, "Экспорт", f"База экспортирована в {filename}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось экспортировать: {e}")

    def on_refresh_selected(self):
        it = self.list_widget.currentItem()
        if not it:
            QMessageBox.information(self, "Инфо", "Выберите запись для обновления")
            return
        key = it.text()
        rec = self.db.get(key, {})
        info = rec.get("INFO", {}) if isinstance(rec, dict) else {}
        inn = _get_ci(info, "inn") or None
        name = _get_ci(info, "fullName") or _get_ci(info, "shortName") or None
        if inn:
            query = str(inn)
            by_inn = True
        elif name:
            query = str(name)
            by_inn = False
        else:
            QMessageBox.warning(self, "Невозможно обновить", "В записи нет ИНН или наименования для запроса")
            return
        def callback(source_obj: Dict[str, Any], link_responses: List[Dict[str, Any]]):
            mapped = {"INFO": {}, "authorities": [], "HEADS": [], "facialTerritorialAccounts": [], "ksAccounts": [], "extra": {}}
            info_src = _get_ci(source_obj, "info") or source_obj
            if isinstance(info_src, dict):
                for k, v in info_src.items():
                    if v is not None and (not isinstance(v, str) or v.strip() != "") and k.lower() not in GLOBAL_HIDDEN_KEYS:
                        mapped["INFO"][k] = v
            auths = _get_ci(source_obj, "authorities") or _get_ci(source_obj, "authority") or []
            if isinstance(auths, dict):
                auths = [auths]
            for a in auths:
                mapped["authorities"].append(a)
            heads = _get_ci(source_obj, "heads") or _get_ci(source_obj, "HEADS") or []
            if isinstance(heads, dict):
                heads = [heads]
            for h in heads:
                mapped["HEADS"].append(h)
            facs = find_facial_territorial_block(source_obj, link_responses)
            for f in facs:
                rec_f = {k: v for k, v in f.items() if k.lower() not in GLOBAL_HIDDEN_KEYS and v is not None and (not isinstance(v, str) or v.strip() != "")}
                mapped["facialTerritorialAccounts"].append(rec_f)
            kss = _get_ci(source_obj, "ksAccounts") or _get_ci(source_obj, "ksaccounts") or []
            if isinstance(kss, dict):
                kss = [kss]
            for k in kss:
                mapped["ksAccounts"].append(k)
            if isinstance(source_obj, dict):
                for k, v in source_obj.items():
                    if k.lower() in {"info","authorities","heads","facialaccounts","ksaccounts"}:
                        continue
                    mapped["extra"][k] = v
            mapped["raw_api"] = {"data": [source_obj]} if isinstance(source_obj, dict) else source_obj
            if link_responses:
                mapped["raw_links"] = link_responses
            self.db[key] = mapped
            save_db(self.db)
            self._refresh_list()
            QMessageBox.information(self, "Обновлено", f"Запись '{key}' обновлена из API")
        self._start_worker(query, by_inn, callback)

# ---------------- module API for launcher integration ----------------
def create_app_window(db_path: Optional[str] = None, app_already_running: bool = False) -> Tuple[Optional[QApplication], Budget]:
    """
    Create (or attach to existing) QApplication and MainWindow.
    - db_path: optional path to db.json
    - app_already_running: if True, assume QApplication already exists in caller; function will still create one if missing.
    Returns (app, wnd). The function does NOT call app.exec(); лаунчер запускает цикл сам.
    """
    app = QApplication.instance()
    created_here = False
    if app is None:
        app = QApplication(sys.argv)
        created_here = True

    wnd = Budget(db_path=db_path)
    wnd.show()

    return app, wnd

# Module ends here. No auto-exec on import.