#!/usr/bin/env python3
# cert_manager.py
#
# Полный GUI менеджер сертификатов на PyQt6.
# Поддерживает:
#  - чтение сертификатов из CurrentUser\\My (Windows) или из папки с файлами (Linux/macOS/файлы),
#  - просмотр деталей сертификата по двойному клику,
#  - поиск и сортировка,
#  - подсветку просроченных (красным) и почти просроченных (<=7 дней) (оранжевым),
#  - экспорт в PEM/DER и экспорт PFX через certutil (Windows),
#  - установка (импорт) сертификата (.pfx/.p12/.cer/.crt/.pem) через certutil (Windows),
#  - удаление сертификата + ключ (через certutil на Windows),
#  - экспорт метаданных в Excel (.xlsx).
#
# Комментарии возле каждой логической секции и основных функций.
#
# Требования:
#   pip install PyQt6 cryptography openpyxl
#
# Запуск:
#   python cert_manager.py
#
# Замечание по безопасности:
#   Операции с приватными ключами и удаление сертификатов критичны — убедитесь, что понимаете последствия.
#   На Windows приложения используют certutil; certutil требует соответствующих прав для операций в LocalMachine.
#
import sys
import os
import subprocess
import tempfile
import traceback
import shutil
import warnings
from typing import List, Tuple, Optional
from functools import partial
from datetime import datetime, timedelta, timezone

# PyQt6 интерфейс
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QListWidget, QListWidgetItem, QFileDialog, QMessageBox,
    QComboBox, QCheckBox, QProgressDialog, QDialog, QTextEdit, QInputDialog
)
from PyQt6.QtGui import QColor
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon

# cryptography для работы с X.509
from cryptography import x509
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.backends import default_backend

# openpyxl для экспорта метаданных в Excel
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill

# Для вызова WinAPI через ctypes (используется при чтении CurrentUser\\My на Windows)
import ctypes
from ctypes import wintypes

# Определяем платформу (Windows / non-Windows)
IS_WINDOWS = sys.platform.startswith("win")

# -------------------------------------------------------------------------------
# ------------------------------ Windows CAPI helpers ---------------------------
# -------------------------------------------------------------------------------
# На Windows используем криптоапи (crypt32.dll) для перечисления сертификатов
# из системного хранилища CurrentUser\\My. Это даёт доступ к DER-данным сертификата.
if IS_WINDOWS:
    crypt32 = ctypes.WinDLL("crypt32.dll")
    kernel32 = ctypes.WinDLL("kernel32.dll")

    # Определение аргументов и возвращаемых типов для некоторых API
    crypt32.CertOpenSystemStoreW.argtypes = (wintypes.HANDLE, wintypes.LPCWSTR)
    crypt32.CertOpenSystemStoreW.restype = wintypes.HANDLE

    crypt32.CertEnumCertificatesInStore.argtypes = (wintypes.HANDLE, ctypes.c_void_p)
    crypt32.CertEnumCertificatesInStore.restype = ctypes.c_void_p

    crypt32.CertCloseStore.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    crypt32.CertCloseStore.restype = wintypes.BOOL

    crypt32.CertFreeCertificateContext.argtypes = (ctypes.c_void_p,)

    # Определяем минимальную структуру CERT_CONTEXT, чтобы извлечь pbCertEncoded и cbCertEncoded
    class CERT_CONTEXT(ctypes.Structure):
        _fields_ = [
            ("dwCertEncodingType", wintypes.DWORD),
            ("pbCertEncoded", ctypes.POINTER(ctypes.c_ubyte)),
            ("cbCertEncoded", wintypes.DWORD),
            ("pCertInfo", ctypes.c_void_p),
            ("hCertStore", wintypes.HANDLE)
        ]

    PCCERT_CONTEXT = ctypes.POINTER(CERT_CONTEXT)

    # Обёртка открытия системного хранилища (CurrentUser\\My)
    def open_store_handle(store_name: str):
        """
        Открывает системное хранилище по имени (например, "MY") для текущего пользователя.
        Возвращает HANDLE или None при ошибке.
        """
        h = crypt32.CertOpenSystemStoreW(0, store_name)
        if not h:
            return None
        return h

    # Итератор по сертификатам в открытом хранилище
    def iter_certs_from_store_handle(hstore):
        """
        Итератор, возвращающий байты DER каждого сертификата из открытого хранилища.
        Использует CertEnumCertificatesInStore. Не освобождает контексты вручную,
        так как следующий вызов CertEnumCertificatesInStore освобождает предыдущий.
        """
        prev = ctypes.c_void_p(0)
        while True:
            p = crypt32.CertEnumCertificatesInStore(hstore, prev)
            if not p:
                break
            ctx = ctypes.cast(p, PCCERT_CONTEXT).contents
            size = ctx.cbCertEncoded
            buf = ctypes.string_at(ctx.pbCertEncoded, size)
            prev = p
            yield buf

# -------------------------------------------------------------------------------
# ------------------------------ Utility functions -----------------------------
# -------------------------------------------------------------------------------
# Устойчивый запуск certutil и декодирование вывода под разными локалями и кодировками

def run_certutil_cmd(cmd: List[str]) -> str:
    """
    Выполняет команду certutil (или любую другую), возвращает строковый вывод.
    Сначала пробует получить текст в utf-8, при ошибке пробует cp866 (обычно OEM в русской Windows),
    затем utf-8 с заменой ошибок.
    """
    try:
        return subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True, encoding="utf-8")
    except UnicodeDecodeError:
        raw = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
        try:
            return raw.decode("cp866")
        except Exception:
            return raw.decode("utf-8", errors="replace")
    except subprocess.CalledProcessError as e:
        raw = getattr(e, "output", None)
        if isinstance(raw, bytes):
            try:
                return raw.decode("cp866")
            except Exception:
                return raw.decode("utf-8", errors="replace")
        return str(e)
    except Exception as e:
        # На случай других неожиданных ошибок
        try:
            raw = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
            try:
                return raw.decode("cp866")
            except Exception:
                return raw.decode("utf-8", errors="replace")
        except Exception:
            return str(e)

# Функции для загрузки сертификатов, вычисления отпечатков и извлечения информации

def load_x509_from_der(der_bytes: bytes) -> Optional[x509.Certificate]:
    """
    Пытается загрузить X.509 сертификат из DER или PEM данных.
    Возвращает объект cryptography.x509.Certificate или None.
    """
    try:
        return x509.load_der_x509_certificate(der_bytes, backend=default_backend())
    except Exception:
        try:
            return x509.load_pem_x509_certificate(der_bytes, backend=default_backend())
        except Exception:
            return None

def fingerprint_sha1(cert: x509.Certificate) -> str:
    """Возвращает SHA1 отпечаток в виде HEX (без двоеточий, верхний регистр)."""
    try:
        return cert.fingerprint(hashes.SHA1()).hex().upper()
    except Exception:
        return ""

def fingerprint_sha256(cert: x509.Certificate) -> str:
    """Возвращает SHA256 отпечаток в виде HEX (без двоеточий, верхний регистр)."""
    try:
        return cert.fingerprint(hashes.SHA256()).hex().upper()
    except Exception:
        return ""

def get_cn(cert: x509.Certificate) -> str:
    """Возвращает Common Name (CN) из subject сертификата, если есть."""
    try:
        for attr in cert.subject:
            # OID 2.5.4.3 = commonName
            if getattr(attr.oid, "dotted_string", "") == "2.5.4.3" or getattr(attr.oid, "_name", "") == "commonName":
                return attr.value
    except Exception:
        pass
    return ""

def issuer_str(cert: x509.Certificate) -> str:
    """Формирует строковое представление издателя (issuer)."""
    try:
        return ", ".join([f"{attr.oid._name or attr.oid.dotted_string}={attr.value}" for attr in cert.issuer])
    except Exception:
        return ""

def period_str(cert: x509.Certificate) -> str:
    """Возвращает период действия сертификата в ISO формате."""
    try:
        # Используем aware datetimes, если есть
        if hasattr(cert, "not_valid_after_utc"):
            start = cert.not_valid_before_utc.isoformat()
            end = cert.not_valid_after_utc.isoformat()
        else:
            start = cert.not_valid_before.replace(tzinfo=timezone.utc).isoformat()
            end = cert.not_valid_after.replace(tzinfo=timezone.utc).isoformat()
        return f"{start} — {end}"
    except Exception:
        return ""

def serial_hex(cert: x509.Certificate) -> str:
    """Возвращает серийный номер сертификата в HEX-формате."""
    try:
        return hex(cert.serial_number).upper()
    except Exception:
        return ""

# -------------------------------------------------------------------------------
# -------------------------- Enumeration of certificates -----------------------
# -------------------------------------------------------------------------------
# Функция enumerate_certificates возвращает список кортежей:
# (cert_obj_or_None, raw_der_bytes, meta_dict)
# meta_dict содержит предвычисленные поля: sha1, sha256, cn, serial, issuer, not_after (если есть)

def enumerate_certificates(store_name: str = "MY", machine: bool = False) -> List[Tuple[Optional[x509.Certificate], bytes, dict]]:
    """
    Собирает список сертификатов из указанного хранилища.
    Если IS_WINDOWS и machine=False, используем CryptoAPI для CurrentUser\\My.
    Если IS_WINDOWS and machine=True, используем certutil -store для чтения метаданных LocalMachine (ограничено).
    В других случаях, если store_name — путь к директории, читаем файлы .pem/.cer/.der внутри неё.
    """
    result = []

    # Windows: CurrentUser\My (полный доступ к DER)
    if IS_WINDOWS and not machine:
        h = open_store_handle(store_name)
        if not h:
            return result
        try:
            for der in iter_certs_from_store_handle(h):
                cert = load_x509_from_der(der)
                if cert is None:
                    continue
                # Используем безопасное извлечение not_after (aware)
                if hasattr(cert, "not_valid_after_utc"):
                    not_after = cert.not_valid_after_utc
                else:
                    not_after = cert.not_valid_after.replace(tzinfo=timezone.utc)
                meta = {
                    "sha1": fingerprint_sha1(cert),
                    "sha256": fingerprint_sha256(cert),
                    "cn": get_cn(cert),
                    "serial": serial_hex(cert),
                    "issuer": issuer_str(cert),
                    "not_after": not_after
                }
                result.append((cert, der, meta))
        finally:
            crypt32.CertCloseStore(h, 0)
        return result

    # Windows: LocalMachine\My (через certutil — только метаданные)
    if IS_WINDOWS and machine:
        try:
            out = run_certutil_cmd(["certutil", "-store", "My"])
        except Exception:
            return []
        # Парсим вывод certutil нестрого — собираем блоки с Serial, SHA1, Subject, Issuer
        items = []
        current = {}
        for line in out.splitlines():
            line = line.rstrip()
            if not line:
                if current:
                    items.append(current)
                    current = {}
                continue
            if line.lstrip().startswith("Serial Number:"):
                current["serial"] = line.split(":", 1)[1].strip()
            elif "SHA1 Hash" in line:
                parts = line.split(":", 1)
                if len(parts) > 1:
                    current["sha1"] = parts[1].strip().replace(" ", "")
            elif line.lstrip().startswith("Issuer:"):
                current["issuer"] = line.split(":", 1)[1].strip()
            elif line.lstrip().startswith("Subject:"):
                current["subject"] = line.split(":", 1)[1].strip()
            elif "Private key is present" in line or "Private Key is present" in line:
                current["has_private_key"] = True
        if current:
            items.append(current)
        for it in items:
            meta = {"sha1": it.get("sha1",""), "sha256": "", "cn": it.get("subject",""), "serial": it.get("serial",""), "issuer": it.get("issuer",""), "not_after": None}
            if it.get("has_private_key"):
                meta["has_private_key"] = True
            result.append((None, b"", meta))
        return result

    # Linux: CryptoPro (через certmgr -list)
    if not IS_WINDOWS and store_name == "cryptopro":
        certmgr_paths = [
            "/opt/cprocsp/bin/amd64/certmgr",
            "/opt/cprocsp/bin/ia32/certmgr",
            "certmgr"
        ]
        exe = None
        for p in certmgr_paths:
            if shutil.which(p):
                exe = p
                break
        
        if not exe:
            return result

        try:
            # Вызываем личные сертификаты пользователя
            out = subprocess.check_output([exe, "-list"], stderr=subprocess.STDOUT, text=True, errors="replace")
            # Разделяем по номерным разделителям (напр. 1-------)
            import re
            blocks = re.split(r'\d+-------', out)
            for block in blocks:
                if "Субъект" not in block and "Subject" not in block: continue
                meta = {"sha1": "", "sha256": "", "cn": "", "serial": "", "issuer": "", "not_after": None, "inn": "", "snils": "", "passport": "", "ogrn": "", "birth_date": "", "container": ""}
                for line in block.splitlines():
                    line = line.strip()
                    # Ищем значения вне зависимости от языка (RU/EN)
                    if ":" in line:
                        parts = line.split(":", 1)
                        if len(parts) < 2: continue
                        key_part, val = parts[0].strip(), parts[1].strip()
                        
                        if key_part in ("Субъект", "Subject"):
                            # Извлекаем CN из строки субъекта
                            cn_match = re.search(r'CN=([^,]+)', val)
                            meta["cn"] = cn_match.group(1).strip() if cn_match else val
                            
                            # Извлекаем ИНН, СНИЛС, ОГРН, Паспорт, Дату рождения
                            inn_match = re.search(r'ИНН(?: ЮЛ)?=([\d]+)', val)
                            if inn_match: meta["inn"] = inn_match.group(1)
                            
                            snils_match = re.search(r'СНИЛС=([\d]+)', val)
                            if snils_match: meta["snils"] = snils_match.group(1)

                            ogrn_match = re.search(r'ОГРН(?: ЮЛ)?=([\d]+)', val)
                            if ogrn_match: meta["ogrn"] = ogrn_match.group(1)

                            def decode_val(raw_v):
                                raw_v = raw_v.strip().strip('"')
                                if re.fullmatch(r'[0-9A-Fa-f]{4,}', raw_v) and len(raw_v) % 2 == 0:
                                    try:
                                        b = bytes.fromhex(raw_v)
                                        for enc in ('utf-16-be', 'utf-16-le', 'utf-8'):
                                            try: return b.decode(enc).strip('\x00')
                                            except: continue
                                    except: pass
                                return raw_v

                            passport_match = re.search(r'(?:1\.2\.643\.100\.5|identityDocument)=([^,]+)', val)
                            if passport_match: meta["passport"] = decode_val(passport_match.group(1))

                            birth_match = re.search(r'(?:1\.2\.643\.100\.128|birthDate)=([^,]+)', val)
                            if birth_match: meta["birth_date"] = decode_val(birth_match.group(1))

                        elif key_part in ("Издатель", "Issuer"):
                            meta["issuer"] = val
                        elif key_part in ("Серийный номер", "Serial"):
                            meta["serial"] = val
                        elif key_part in ("SHA1 отпечаток", "SHA1 Hash"):
                            meta["sha1"] = val.replace(" ", "")
                        elif key_part in ("Контейнер", "Container"):
                            meta["container"] = val
                        elif key_part in ("Истекает", "Not valid after"):
                            try:
                                # Парсим дату (ДД/ММ/ГГГГ)
                                date_str = val.split()[0]
                                meta["not_after"] = datetime.strptime(date_str, "%d/%m/%Y").replace(tzinfo=timezone.utc)
                            except: pass
                result.append((None, b"", meta))
        except Exception:
            pass
        return result

    # Non-Windows или папка: читаем файлы сертификатов в директории
    if os.path.isdir(store_name):
        for fname in sorted(os.listdir(store_name)):
            path = os.path.join(store_name, fname)
            if not os.path.isfile(path):
                continue
            try:
                with open(path, "rb") as f:
                    data = f.read()
                cert = None
                der = b""
                # Определяем PEM или DER
                if b"-----BEGIN CERTIFICATE-----" in data:
                    cert = x509.load_pem_x509_certificate(data, backend=default_backend())
                    der = cert.public_bytes(serialization.Encoding.DER)
                else:
                    try:
                        cert = x509.load_der_x509_certificate(data, backend=default_backend())
                        der = data
                    except Exception:
                        continue
                if hasattr(cert, "not_valid_after_utc"):
                    not_after = cert.not_valid_after_utc
                else:
                    not_after = cert.not_valid_after.replace(tzinfo=timezone.utc)
                meta = {"sha1": fingerprint_sha1(cert), "sha256": fingerprint_sha256(cert), "cn": get_cn(cert), "serial": serial_hex(cert), "issuer": issuer_str(cert), "not_after": not_after}
                result.append((cert, der, meta))
            except Exception:
                continue
    return result

# -------------------------------------------------------------------------------
# --------------------------- Certificate details dialog -----------------------
# -------------------------------------------------------------------------------
# Диалог для отображения полного текста и метаданных сертификата. Позволяет экспортировать
# отдельный сертификат в PEM или PFX (через certutil на Windows).

class CertDetailsDialog(QDialog):
    """
    Диалог, отображающий подробные сведения о выбранном сертификате.
    Имеет кнопки экспорта PEM и PFX (PFX только на Windows).
    """
    def __init__(self, parent, cert_tuple):
        super().__init__(parent)
        self.setWindowTitle("Детали сертификата")
        self.resize(600, 500)

        # Ссылка на главный объект (для доступа к export_folder и другим методам)
        self.parent = parent
        self.cert_tuple = cert_tuple  # (cert, der, meta)

        # Основной вертикальный layout
        v = QVBoxLayout(self)

        cert, der, meta = cert_tuple

        # Формируем многострочный текст с подробностями
        details = []
        details.append(f"Владелец (CN): {meta.get('cn') or ''}")
        if meta.get('inn'): details.append(f"ИНН: {meta.get('inn')}")
        if meta.get('snils'): details.append(f"СНИЛС: {meta.get('snils')}")
        if meta.get('ogrn'): details.append(f"ОГРН: {meta.get('ogrn')}")
        if meta.get('passport'): details.append(f"Паспорт: {meta.get('passport')}")
        if meta.get('birth_date'): details.append(f"Дата рождения: {meta.get('birth_date')}")
        
        details.append(f"Серийный номер: {meta.get('serial') or ''}")
        details.append(f"Издатель: {meta.get('issuer') or ''}")
        details.append(f"SHA1: {meta.get('sha1') or ''}")
        
        # Срок действия
        exp_str = ""
        if cert: exp_str = period_str(cert)
        elif meta.get('not_after'): exp_str = meta['not_after'].strftime("%d.%m.%Y")
        details.append(f"Период действия: {exp_str}")

        if cert:
            details.append("")
            details.append("Subject (полный):")
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", category=UserWarning)
                    details.append(cert.subject.rfc4514_string())
            except Exception:
                details.append(str(cert.subject))
            details.append("Issuer (полный):")
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", category=UserWarning)
                    details.append(cert.issuer.rfc4514_string())
            except Exception:
                details.append(str(cert.issuer))
            # Распечатать расширения (extensions) — аккуратно
            try:
                details.append("")
                details.append("Extensions:")
                for ext in cert.extensions:
                    # Некоторые экстеншены имеют сложные значения, преобразуем их в строку
                    details.append(f"  {ext.oid._name or ext.oid.dotted_string}: {ext.value}")
            except Exception:
                pass

        details.append("")
        details.append(f"Raw DER size: {len(der) if der else 0} bytes")

        # Многострочный QTextEdit для отображения деталей (только чтение)
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setPlainText("\n".join(details))
        v.addWidget(self.text_edit, stretch=1)

        # Кнопки: экспорт PEM, экспорт PFX (Windows), закрыть
        btn_row = QHBoxLayout()
        self.export_pem_btn = QPushButton("Экспорт в PEM")
        self.export_pem_btn.clicked.connect(self.on_export_pem)
        btn_row.addWidget(self.export_pem_btn)

        self.export_pfx_btn = QPushButton("Экспорт в PFX (Windows certutil)")
        self.export_pfx_btn.clicked.connect(self.on_export_pfx)
        if not IS_WINDOWS:
            self.export_pfx_btn.setEnabled(False)  # на non-Windows выключаем
        btn_row.addWidget(self.export_pfx_btn)

        self.close_btn = QPushButton("Закрыть")
        self.close_btn.clicked.connect(self.accept)
        btn_row.addWidget(self.close_btn)

        v.addLayout(btn_row)

    def on_export_pem(self):
        """
        Экспорт текущего сертификата в PEM-файл.
        Если сертификат был извлечён как cryptography объект — используем его,
        иначе пробуем загрузить DER и конвертировать в PEM.
        """
        cert, der, meta = self.cert_tuple
        try:
            if cert:
                pem = cert.public_bytes(serialization.Encoding.PEM)
            else:
                if der:
                    c = load_x509_from_der(der)
                    if not c:
                        QMessageBox.warning(self, "Экспорт PEM", "Невозможно распарсить сертификат для экспорта.")
                        return
                    pem = c.public_bytes(serialization.Encoding.PEM)
                else:
                    QMessageBox.warning(self, "Экспорт PEM", "Нет данных сертификата.")
                    return
            # Предлагаем сохранить файл (по умолчанию в папку экспорта приложения)
            default_fn = os.path.join(self.parent.export_folder, "cert.pem")
            fn, _ = QFileDialog.getSaveFileName(self, "Сохранить PEM", default_fn, "PEM Files (*.pem)")
            if not fn:
                return
            with open(fn, "wb") as f:
                f.write(pem)
            QMessageBox.information(self, "Экспорт PEM", f"Сертификат экспортирован в {fn}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка экспорта PEM", str(e))

    def on_export_pfx(self):
        """
        Экспорт в PFX/P12 через certutil. Работает только на Windows.
        Запрашивает пароль (опционально) и вызывает certutil -exportPFX.
        """
        if not IS_WINDOWS:
            QMessageBox.information(self, "PFX экспорт", "Экспорт PFX доступен только в Windows.")
            return
        cert, der, meta = self.cert_tuple
        sha1 = (meta.get("sha1") or (fingerprint_sha1(cert) if cert else "")).replace(" ", "")
        if not shutil.which("certutil"):
            QMessageBox.critical(self, "certutil не найден", "certutil не найден в PATH. Нельзя экспортировать PFX.")
            return
        password, ok = QInputDialog.getText(self, "Пароль PFX", "Введите пароль для PFX (оставь пустым для без пароля):")
        if not ok:
            return
        cn = meta.get("cn") or (get_cn(cert) if cert else "cert")
        safe = "".join(ch for ch in cn if ch.isalnum() or ch in (" ", "_", "-")).strip().replace(" ", "_")
        default_out = os.path.join(self.parent.export_folder, f"{safe}.pfx")
        out_path, _ = QFileDialog.getSaveFileName(self, "Сохранить PFX", default_out, "PFX Files (*.pfx *.p12)")
        if not out_path:
            return
        # Формируем команду certutil; используем -user (CurrentUser), если приложение так выбрано
        cmd = ["certutil"]
        if password:
            cmd += ["-p", password]
        # Добавляем -user, если текущая опция store соответствует CurrentUser
        store_info = self.parent.store_combo.currentData()
        store_key, machine_flag = store_info
        if not machine_flag:
            cmd.append("-user")
        # команда exportPFX My <sha1> <out>
        cmd += ["-exportPFX", "My", sha1, out_path]
        try:
            out = run_certutil_cmd(cmd)
            # certutil иногда пишет текст в OEM кодировке, но run_certutil_cmd уже обработал это
            QMessageBox.information(self, "Экспорт PFX", f"PFX сохранён: {out_path}\n{out}")
        except Exception as e:
            QMessageBox.warning(self, "Ошибка certutil", f"Ошибка при запуске certutil:\n{e}")

# -------------------------------------------------------------------------------
# ------------------------------- Main GUI App ---------------------------------
# -------------------------------------------------------------------------------
# Основной виджет приложения: CertManagerApp
# Содержит элементы управления, список сертификатов и все функции экспорта/импорта/удаления.

class CertManagerApp(QWidget):
    def __init__(self):
        """
        Инициализация GUI: создаём элементы управления, лэйауты, привязываем обработчики.
        """
        super().__init__()
        ICON_PATH = os.path.join(os.path.dirname(__file__), "cert_mgn.png")
        if os.path.exists(ICON_PATH):
            try:
                self.setWindowIcon(QIcon(ICON_PATH))
            except Exception:
                # если что-то пошло не так — пропускаем, приложение продолжит работать
                pass

        self.setWindowTitle("Cert Manager")
        self.resize(700, 700)  # Сделал окно выше, но уже

        # Основной вертикальный layout
        v = QVBoxLayout(self)

        # ---------------- Первая строка: Хранилище и путь ----------------
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Хранилище:"))
        self.store_combo = QComboBox()
        if IS_WINDOWS:
            self.store_combo.addItem("CurrentUser\\My", ("MY", False))
            self.store_combo.addItem("LocalMachine\\My", ("MY", True))
        else:
            self.store_combo.addItem("КриптоПро: Личные (uMy)", ("cryptopro", False))
            self.store_combo.addItem("Папка с сертификатами", ("folder", False))
            self.store_combo.addItem("Пользовательские (~/.pki/nssdb)", (os.path.expanduser("~/.pki/nssdb"), False))
        row1.addWidget(self.store_combo)
        
        self.path_edit = QLineEdit()
        if not IS_WINDOWS: self.path_edit.setText(os.path.expanduser("~"))
        self.path_edit.setPlaceholderText("Путь к папке")
        row1.addWidget(self.path_edit)
        
        self.refresh_btn = QPushButton("Обновить")
        self.refresh_btn.clicked.connect(self.refresh_list)
        row1.addWidget(self.refresh_btn)
        v.addLayout(row1)

        # ---------------- Вторая строка: Поиск и Сортировка ----------------
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Поиск:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Фильтр...")
        self.search_edit.textChanged.connect(self.apply_filter_sort)
        row2.addWidget(self.search_edit)

        row2.addWidget(QLabel("Сортировка:"))
        self.sort_combo = QComboBox()
        self.sort_combo.addItem("Имя (А-Я)", "cn_asc")
        self.sort_combo.addItem("Имя (Я-А)", "cn_desc")
        self.sort_combo.addItem("Срок: сначала старые", "exp_asc")
        self.sort_combo.addItem("Срок: сначала новые", "exp_desc")
        self.sort_combo.currentIndexChanged.connect(self.apply_filter_sort)
        row2.addWidget(self.sort_combo)
        v.addLayout(row2)

        # ---------------- Список ----------------
        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.list_widget.itemDoubleClicked.connect(self.on_item_double_clicked)
        v.addWidget(self.list_widget, stretch=1)

        # ---------------- Кнопки экспорта ----------------
        btn_row_exp = QHBoxLayout()
        self.export_pem_btn = QPushButton("Экспорт в PEM")
        self.export_pem_btn.clicked.connect(self.export_selected_pem)
        btn_row_exp.addWidget(self.export_pem_btn)

        self.export_pfx_btn = QPushButton("Экспорт в PFX")
        self.export_pfx_btn.clicked.connect(self.export_selected_pfx)
        btn_row_exp.addWidget(self.export_pfx_btn)

        self.export_excel_btn = QPushButton("В Excel")
        self.export_excel_btn.clicked.connect(self.export_metadata_excel)
        btn_row_exp.addWidget(self.export_excel_btn)
        v.addLayout(btn_row_exp)

        # ---------------- Кнопки управления ----------------
        btn_row_mgn = QHBoxLayout()
        self.install_cert_btn = QPushButton("Установить")
        self.install_cert_btn.clicked.connect(self.install_certificate_dialog)
        btn_row_mgn.addWidget(self.install_cert_btn)

        self.delete_btn = QPushButton("Удалить")
        self.delete_btn.clicked.connect(self.delete_selected)
        btn_row_mgn.addWidget(self.delete_btn)

        self.open_folder_btn = QPushButton("Папка экспорта")
        self.open_folder_btn.clicked.connect(self.choose_export_folder)
        btn_row_mgn.addWidget(self.open_folder_btn)
        v.addLayout(btn_row_mgn)

        # ---------------- Папка экспорта и опции ----------------
        self.export_folder_label = QLabel("Папка: ./export")
        self.export_folder_label.setStyleSheet("font-size: 10px; color: gray;")
        v.addWidget(self.export_folder_label)

        opt_row = QHBoxLayout()
        self.include_der_cb = QCheckBox("Сохранять DER")
        self.include_der_cb.setToolTip("Сохранять DER формат помимо PEM")
        self.open_after_export_cb = QCheckBox("Открыть папку")
        self.open_after_export_cb.setToolTip("Открыть папку в проводнике после экспорта")
        opt_row.addWidget(self.include_der_cb)
        opt_row.addWidget(self.open_after_export_cb)
        v.addLayout(opt_row)

        # ---------------- Footer: статус ---------------------------------------------------------------
        footer = QHBoxLayout()
        self.status_label = QLabel("Готов")
        footer.addWidget(self.status_label)
        footer.addStretch()
        v.addLayout(footer)

        # ---------------- Internal state ---------------------------------------------------------------
        # all_certs хранит полный список сертификатов: [(cert_or_None, der_bytes, meta_dict), ...]
        self.all_certs: List[Tuple[Optional[x509.Certificate], bytes, dict]] = []
        # filtered_indices — индексы в all_certs, которые сейчас отображаются в list_widget
        self.filtered_indices: List[int] = []
        # папка для экспорта (по умолчанию ./export)
        self.export_folder = os.path.abspath("export")
        os.makedirs(self.export_folder, exist_ok=True)
        self.export_folder_label.setText(f"Папка экспорта: {self.export_folder}")

        # Инициируем первичную загрузку сертификатов
        self.refresh_list()

    # ------------------------- UI helper / status ----------------------------------
    def set_status(self, text: str):
        """Обновляет строку состояния и обрабатывает события GUI."""
        self.status_label.setText(text)
        QApplication.processEvents()

    # ------------------------- Refresh / load list --------------------------------
    def refresh_list(self):
        """
        Перечитывает хранилище сертификатов в соответствии с выбором пользователя
        (CurrentUser\\My, LocalMachine\\My или папка) и обновляет отображение.
        """
        self.list_widget.clear()
        self.all_certs = []
        self.filtered_indices = []
        store_info = self.store_combo.currentData()
        store_key, machine_flag = store_info

        # Если выбран режим "папка", используем path_edit как путь к директории
        if store_key == "folder":
            folder = self.path_edit.text().strip()
            if not folder:
                QMessageBox.warning(self, "Ошибка", "Укажите путь к папке с сертификатами")
                return
            self.set_status("Сканирование папки...")
            self.all_certs = enumerate_certificates(folder, machine=False)
        else:
            self.set_status("Чтение хранилища...")
            self.all_certs = enumerate_certificates(store_key, machine=machine_flag)

        # После загрузки применим фильтр и сортировку для отображения
        self.apply_filter_sort()
        self.set_status(f"Найдено сертификатов: {len(self.all_certs)}")

    # ------------------------- Filter & Sort -------------------------------------
    def apply_filter_sort(self):
        """
        Применяет поиск (filter) и сортировку (sort) к self.all_certs и обновляет list_widget.
        Также применяет подсветку: красный — просрочен, оранжевый — осталось <= 7 дней.
        """
        query = (self.search_edit.text() or "").strip().lower()
        sort_key = self.sort_combo.currentData()

        # Создаём список кортежей (orig_index, cert, der, meta)
        indexed = [(i, *t) for i, t in enumerate(self.all_certs)]

        # Фильтрация по запросу (по CN, serial, sha1, issuer)
        if query:
            def matches(meta, cert):
                q = query
                if meta.get("cn") and q in meta.get("cn", "").lower():
                    return True
                if meta.get("serial") and q in meta.get("serial", "").lower():
                    return True
                if meta.get("sha1") and q in meta.get("sha1", "").lower():
                    return True
                if meta.get("issuer") and q in meta.get("issuer", "").lower():
                    return True
                if cert:
                    cn = get_cn(cert) or ""
                    if q in cn.lower():
                        return True
                    if q in issuer_str(cert).lower():
                        return True
                return False
            indexed = [it for it in indexed if matches(it[3], it[1])]

        # Сортировка — на основе выбранного ключа sort_key
        reverse = False
        keyfunc = None
        if sort_key == "cn_asc":
            keyfunc = lambda it: (it[3].get("cn") or "").lower()
            reverse = False
        elif sort_key == "cn_desc":
            keyfunc = lambda it: (it[3].get("cn") or "").lower()
            reverse = True
        elif sort_key == "serial_asc":
            keyfunc = lambda it: (it[3].get("serial") or "")
            reverse = False
        elif sort_key == "serial_desc":
            keyfunc = lambda it: (it[3].get("serial") or "")
            reverse = True
        elif sort_key == "exp_asc":
            def _exp(it):
                cert = it[1]
                try:
                    if cert and hasattr(cert, "not_valid_after_utc"):
                        return cert.not_valid_after_utc
                    return cert.not_valid_after.replace(tzinfo=timezone.utc) if cert else datetime.max.replace(tzinfo=timezone.utc)
                except Exception:
                    return datetime.max.replace(tzinfo=timezone.utc)
            keyfunc = _exp
            reverse = False
        elif sort_key == "exp_desc":
            def _exp2(it):
                cert = it[1]
                try:
                    if cert and hasattr(cert, "not_valid_after_utc"):
                        return cert.not_valid_after_utc
                    return cert.not_valid_after.replace(tzinfo=timezone.utc) if cert else datetime.min.replace(tzinfo=timezone.utc)
                except Exception:
                    return datetime.min.replace(tzinfo=timezone.utc)
            keyfunc = _exp2
            reverse = True
        elif sort_key == "sha1_asc":
            keyfunc = lambda it: (it[3].get("sha1") or "").lower()
            reverse = False
        elif sort_key == "sha1_desc":
            keyfunc = lambda it: (it[3].get("sha1") or "").lower()
            reverse = True

        if keyfunc:
            try:
                indexed.sort(key=keyfunc, reverse=reverse)
            except Exception:
                pass

        # Обновляем list_widget: формат каждой строки — "№. CN | Серийный: ... | SHA1: ... | Издатель: ... | exp: ..."
        self.list_widget.clear()
        self.filtered_indices = []
        now = datetime.now(timezone.utc)
        soon_threshold = now + timedelta(days=10)  # Порог 10 дней
        for display_idx, (orig_idx, cert, der, meta) in enumerate(indexed, 1):
            title = meta.get("cn") or (get_cn(cert) if cert else "(no CN)")
            sha1 = (meta.get("sha1") or (fingerprint_sha1(cert) if cert else "")).upper()
            serial = meta.get("serial") or (serial_hex(cert) if cert else "")
            issuer = meta.get("issuer") or (issuer_str(cert) if cert else "")
            exp = ""
            color = None
            
            # Определяем дату окончания (из объекта сертификата или из метаданных КриптоПро)
            exp_dt = None
            if cert:
                try:
                    if hasattr(cert, "not_valid_after_utc"):
                        exp_dt = cert.not_valid_after_utc
                    else:
                        exp_dt = cert.not_valid_after.replace(tzinfo=timezone.utc)
                except: pass
            elif meta.get("not_after"):
                exp_dt = meta["not_after"]

            if exp_dt:
                try:
                    exp = exp_dt.strftime("%d.%m.%Y")
                    if exp_dt < now:
                        color = QColor("#FF0000") # Красный
                    elif exp_dt <= soon_threshold:
                        color = QColor("#FFD700") # Золотисто-желтый (лучше видно чем просто yellow)
                except Exception: pass

            # Возвращаем полную информацию: №. Имя | До: Дата | S/N: ... | SHA1: ... | Издатель: ...
            item_text = f"{display_idx}. {title}  |  До: {exp}  |  S/N: {serial}  |  SHA1: {sha1}  |  Издатель: {issuer}"
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, orig_idx)  # храним оригинальный индекс
            if color:
                item.setForeground(color)
            self.list_widget.addItem(item)
            self.filtered_indices.append(orig_idx)

    # ------------------------- Export PEM / DER ----------------------------------
    def choose_export_folder(self):
        """Открывает диалог выбора папки для сохранения экспорта и обновляет метку."""
        d = QFileDialog.getExistingDirectory(self, "Выбрать папку для экспорта", self.export_folder)
        if d:
            self.export_folder = d
            self.export_folder_label.setText(f"Папка экспорта: {self.export_folder}")

    def get_selected_original_indices(self) -> List[int]:
        """
        Возвращает список оригинальных индексов (в self.all_certs) для выбранных элементов в list_widget.
        Это нужно, т.к. list_widget показывает индекс filtered view, а оригинальные данные лежат в all_certs.
        """
        items = self.list_widget.selectedItems()
        orig_idxs = []
        for it in items:
            v = it.data(Qt.ItemDataRole.UserRole)
            if isinstance(v, int):
                orig_idxs.append(v)
        return orig_idxs

    def export_selected_pem(self):
        """
        Экспортирует выбранные сертификаты в PEM (и опционно DER) в папку self.export_folder.
        """
        orig_idxs = self.get_selected_original_indices()
        if not orig_idxs:
            QMessageBox.information(self, "Экспорт PEM", "Выберите хотя бы один сертификат.")
            return
        self.set_status("Экспорт PEM...")
        exported = 0
        for orig in orig_idxs:
            try:
                cert, der, meta = self.all_certs[orig]
            except Exception:
                continue
            try:
                # Получаем PEM из объекта cert если он есть, иначе пробуем загрузить из der
                if cert:
                    pem = cert.public_bytes(serialization.Encoding.PEM)
                else:
                    if der:
                        c = load_x509_from_der(der)
                        if not c:
                            continue
                        pem = c.public_bytes(serialization.Encoding.PEM)
                    else:
                        continue
                cn = meta.get("cn") or (get_cn(cert) if cert else f"cert_{orig+1}")
                safe = "".join(ch for ch in cn if ch.isalnum() or ch in (" ", "_", "-")).strip().replace(" ", "_")
                pem_path = os.path.join(self.export_folder, f"{safe}_{orig+1}.pem")
                with open(pem_path, "wb") as f:
                    f.write(pem)
                exported += 1
                # Дополнительно сохраняем DER, если пользователь выбрал опцию
                if self.include_der_cb.isChecked():
                    der_path = os.path.join(self.export_folder, f"{safe}_{orig+1}.der")
                    raw_der = der if der else cert.public_bytes(serialization.Encoding.DER)
                    with open(der_path, "wb") as f:
                        f.write(raw_der)
            except Exception as e:
                # логируем и показываем предупреждение
                traceback.print_exc()
                QMessageBox.warning(self, "Ошибка экспорта PEM", f"Не удалось экспортировать сертификат #{orig+1}: {e}")
        self.set_status(f"Экспортировано PEM: {exported}")
        if self.open_after_export_cb.isChecked():
            self.open_export_folder()

    def open_export_folder(self):
        """Открывает папку экспорта в файловом менеджере (платформенно-зависимо)."""
        if IS_WINDOWS:
            os.startfile(self.export_folder)
        elif sys.platform == "darwin":
            subprocess.call(["open", self.export_folder])
        else:
            subprocess.call(["xdg-open", self.export_folder])

    def export_selected_pfx(self):
        """
        Экспорт выбранных сертификатов в PFX.
        На Windows: через certutil -exportPFX.
        На Linux: через КриптоПро certmgr -export -pfx.
        """
        orig_idxs = self.get_selected_original_indices()
        if not orig_idxs:
            QMessageBox.information(self, "Экспорт PFX", "Выберите хотя бы один сертификат.")
            return

        # Просим пароль
        password, ok = QInputDialog.getText(self, "Пароль PFX", "Введите пароль для PFX (обязательно для КриптоПро):")
        if not ok: return

        exported = 0
        errors = []

        # Определяем исполняемый файл certmgr для Linux
        linux_exe = None
        if not IS_WINDOWS:
            for p in ["/opt/cprocsp/bin/amd64/certmgr", "/opt/cprocsp/bin/ia32/certmgr", "certmgr"]:
                if shutil.which(p):
                    linux_exe = p
                    break

        progress = QProgressDialog("Экспорт PFX...", "Отмена", 0, len(orig_idxs), self)
        
        for idx_i, orig in enumerate(orig_idxs):
            if progress.wasCanceled(): break
            progress.setValue(idx_i)
            cert, der, meta = self.all_certs[orig]
            
            cn = meta.get("cn") or f"cert_{orig+1}"
            safe = "".join(ch for ch in cn if ch.isalnum() or ch in (" ", "_", "-")).strip().replace(" ", "_")
            out_path = os.path.join(self.export_folder, f"{safe}_{orig+1}.pfx")

            if IS_WINDOWS:
                # --- Логика Windows ---
                sha1 = meta.get("sha1", "").replace(" ", "")
                store_info = self.store_combo.currentData()
                machine_flag = store_info[1]
                cmd = ["certutil"]
                if password: cmd += ["-p", password]
                if not machine_flag: cmd.append("-user")
                cmd += ["-exportPFX", "My", sha1, out_path]
                try:
                    run_certutil_cmd(cmd)
                    exported += 1
                except Exception as e: errors.append((orig, str(e)))
            else:
                # --- Логика Linux (КриптоПро) ---
                if not linux_exe:
                    errors.append((orig, "certmgr не найден"))
                    continue
                
                container = meta.get("container", "")
                if not container:
                    errors.append((orig, "Контейнер не найден для этого сертификата"))
                    continue
                
                try:
                    # certmgr -export -pfx -container <name> -dest <path> -password <pwd>
                    cmd = [linux_exe, "-export", "-pfx", "-container", container, "-dest", out_path]
                    if password:
                        cmd += ["-password", password]
                    
                    subprocess.run(cmd, check=True)
                    exported += 1
                except Exception as e:
                    errors.append((orig, str(e)))

        progress.setValue(len(orig_idxs))
        QMessageBox.information(self, "Экспорт PFX", f"Завершено. Успешно: {exported}. Ошибок: {len(errors)}.")
        if self.open_after_export_cb.isChecked(): self.open_export_folder()

    # ------------------------- Install / Import certificate ------------------------
    def install_certificate_dialog(self):
        """
        Открывает диалог выбора файла сертификата и устанавливает его в выбранное хранилище.
        Поддерживаемые форматы: .pfx/.p12 (с паролем), .cer/.crt/.pem (сертификат).
        На Windows используем certutil -importPFX / -addstore.
        На non-Windows просто копируем файл в export-folder и показываем инструкцию.
        """
        fn, _ = QFileDialog.getOpenFileName(self, "Выберите файл сертификата для установки", "", "Certificates (*.pfx *.p12 *.cer *.crt *.pem);;All files (*)")
        if not fn:
            return

        # Получаем текущий выбор хранилища (CurrentUser/LocalMachine/Folder)
        store_key, machine_flag = self.store_combo.currentData()
        is_windows = IS_WINDOWS
        lower = fn.lower()

        # Обработка PFX/P12 — содержит приватный ключ, обычно нужно вводить пароль
        if lower.endswith((".pfx", ".p12")):
            pwd, ok = QInputDialog.getText(self, "Пароль PFX", "Введите пароль PFX (оставь пустым, если нет):")
            if not ok:
                return
            if is_windows:
                # Формируем команду certutil -importPFX [-user] <file>
                cmd = ["certutil"]
                if pwd:
                    cmd += ["-p", pwd]
                # Для CurrentUser добавляем -user; для LocalMachine опцию не добавляем (требует elevation)
                if not machine_flag:
                    cmd.append("-user")
                cmd += ["-importPFX", fn]
                try:
                    out = run_certutil_cmd(cmd)
                    QMessageBox.information(self, "Установка сертификата", "PFX успешно установлен.\n" + out)
                    # Перечитываем список сертификатов после успешной установки
                    self.refresh_list()
                except Exception as e:
                    QMessageBox.critical(self, "Ошибка установки PFX", f"Ошибка certutil:\n{e}")
            else:
                # Non-Windows: копируем файл в папку экспорта и даём инструкцию по ручной установке
                dest = os.path.join(self.export_folder, os.path.basename(fn))
                try:
                    shutil.copyfile(fn, dest)
                    QMessageBox.information(self, "Установка сертификата", f"PFX сохранён в {dest}.\nДля установки импортируйте его вручную в систему (Keychain/PKCS#11).")
                except Exception as e:
                    QMessageBox.critical(self, "Ошибка", str(e))
            return

        # Обработка CER/CRT/PEM (только публичный сертификат)
        if lower.endswith((".cer", ".crt", ".pem")):
            if is_windows:
                # certutil -addstore [-user] My file.cer
                cmd = ["certutil"]
                if not machine_flag:
                    cmd.append("-user")
                cmd += ["-addstore", "My", fn]
                try:
                    out = run_certutil_cmd(cmd)
                    QMessageBox.information(self, "Установка сертификата", "Сертификат успешно добавлен в хранилище.\n" + out)
                    self.refresh_list()
                except Exception as e:
                    QMessageBox.critical(self, "Ошибка установки", f"Ошибка certutil:\n{e}")
            else:
                dest = os.path.join(self.export_folder, os.path.basename(fn))
                try:
                    shutil.copyfile(fn, dest)
                    QMessageBox.information(self, "Установка сертификата", f"Файл сертификата скопирован в {dest}.\nИмпортируйте его в систему средствами ОС (Keychain / trust store).")
                except Exception as e:
                    QMessageBox.critical(self, "Ошибка", str(e))
            return

        # Неподдерживаемый формат
        QMessageBox.warning(self, "Формат не поддерживается", "Поддерживаемые форматы: .pfx, .p12, .cer, .crt, .pem")

    # ------------------------- Delete certificate + key (Windows only) ------------
    def delete_selected(self):
        """
        Удаляет выбранные сертификаты. 
        На Windows: через certutil -delstore.
        На Linux: через КриптоПро certmgr -delete.
        """
        orig_idxs = self.get_selected_original_indices()
        if not orig_idxs:
            QMessageBox.information(self, "Удаление", "Выберите хотя бы один сертификат для удаления.")
            return

        # Подтверждение (удаление необратимо)
        reply = QMessageBox.question(self, "Подтвердите удаление",
                                     f"Удалить {len(orig_idxs)} выбранных сертификатов вместе с закрытыми ключами? Действие необратимо.",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return

        errors = []
        deleted = 0

        # Определяем исполняемый файл certmgr для Linux
        linux_exe = None
        if not IS_WINDOWS:
            for p in ["/opt/cprocsp/bin/amd64/certmgr", "/opt/cprocsp/bin/ia32/certmgr", "certmgr"]:
                if shutil.which(p):
                    linux_exe = p
                    break

        progress = QProgressDialog("Удаление сертификатов...", "Отмена", 0, len(orig_idxs), self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        
        for idx_i, orig in enumerate(orig_idxs):
            if progress.wasCanceled(): break
            progress.setValue(idx_i)
            cert, der, meta = self.all_certs[orig]
            
            if IS_WINDOWS:
                # --- Логика Windows (уже была, оставляем) ---
                sha1 = meta.get("sha1", "").replace(" ", "")
                store_info = self.store_combo.currentData()
                machine_flag = store_info[1]
                cmd = ["certutil"]
                if not machine_flag: cmd.append("-user")
                cmd += ["-delstore", "My", sha1]
                try:
                    run_certutil_cmd(cmd)
                    deleted += 1
                except Exception as e:
                    errors.append((orig, str(e)))
            else:
                # --- Логика Linux (КриптоПро) ---
                if not linux_exe:
                    errors.append((orig, "certmgr не найден"))
                    continue
                
                sha1 = meta.get("sha1", "")
                container = meta.get("container", "")
                
                try:
                    # 1. Удаляем сам сертификат по отпечатку
                    if sha1:
                        subprocess.run([linux_exe, "-delete", "-thumbprint", sha1], check=True)
                    
                    # 2. Удаляем контейнер, если он известен
                    if container:
                        # Используем -silent чтобы не спрашивал подтверждения в терминале
                        subprocess.run([linux_exe, "-delete", "-container", container, "-silent"], check=False)
                    
                    deleted += 1
                except Exception as e:
                    errors.append((orig, str(e)))

        progress.setValue(len(orig_idxs))
        msg = f"Удалено: {deleted}."
        if errors: msg += f" Ошибок: {len(errors)}."
        QMessageBox.information(self, "Удаление завершено", msg)
        self.refresh_list()

    # ------------------------- Export metadata to Excel --------------------------------
    def export_metadata_excel(self):
        """
        Экспортирует метаданные всех (self.all_certs) сертификатов в Excel файл (.xlsx).
        Включает CN, серийный номер, SHA1, SHA256, издателя, период действия.
        """
        if not self.all_certs:
            QMessageBox.information(self, "Экспорт Excel", "Нет сертификатов для экспорта.")
            return
        filename, _ = QFileDialog.getSaveFileName(self, "Сохранить Excel", os.path.join(self.export_folder, "certs_metadata.xlsx"), "Excel Files (*.xlsx)")
        if not filename:
            return
        wb = Workbook()
        ws = wb.active
        ws.title = "Certificates"
        headers = ["Index", "CN", "Serial", "SHA1", "SHA256", "Issuer", "Period", "Notes"]
        ws.append(headers)
        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill("solid", fgColor="4F81BD")
        for col_idx in range(1, len(headers) + 1):
            cell = ws.cell(row=1, column=col_idx)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center")
        for i, (cert, der, meta) in enumerate(self.all_certs):
            cn = meta.get("cn") or (get_cn(cert) if cert else "")
            serial = meta.get("serial") or (serial_hex(cert) if cert else "")
            sha1 = meta.get("sha1") or (fingerprint_sha1(cert) if cert else "")
            sha256 = meta.get("sha256") or (fingerprint_sha256(cert) if cert else "")
            issuer = meta.get("issuer") or (issuer_str(cert) if cert else "")
            period = period_str(cert) if cert else ""
            notes = ""
            ws.append([i+1, cn, serial, sha1, sha256, issuer, period, notes])
        # автоматическая ширина колонок
        for column_cells in ws.columns:
            length = max(len(str(cell.value)) if cell.value else 0 for cell in column_cells)
            ws.column_dimensions[column_cells[0].column_letter].width = min(60, length + 2)
        try:
            wb.save(filename)
            QMessageBox.information(self, "Экспорт Excel", f"Экспорт метаданных завершён: {filename}")
            if self.open_after_export_cb.isChecked():
                self.open_file(filename)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка Excel", str(e))

    def open_file(self, path):
        """Открывает файл/папку в файловом менеджере — платформенно-зависимо."""
        if IS_WINDOWS:
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.call(["open", path])
        else:
            subprocess.call(["xdg-open", path])

    # ------------------------- Double click to view details ---------------------------
    def on_item_double_clicked(self, item: QListWidgetItem):
        """
        Обработчик двойного клика по элементу списка — открывает CertDetailsDialog.
        Подставляем оригинальный индекс и соответствующий кортеж (cert, der, meta).
        """
        orig_idx = item.data(Qt.ItemDataRole.UserRole)
        if orig_idx is None:
            return
        cert_tuple = self.all_certs[orig_idx]
        dlg = CertDetailsDialog(self, cert_tuple)
        dlg.exec()

# -------------------------------------------------------------------------------
# --------------------------------- Helpers -------------------------------------
# -------------------------------------------------------------------------------
def shutil_which(name):
    """Обёртка над shutil.which: возвращает путь к исполняемому или None."""
    from shutil import which
    return which(name)

# -------------------------------------------------------------------------------
# --------------------------------- Main ---------------------------------------
# -------------------------------------------------------------------------------