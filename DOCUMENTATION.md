# AdminLauncher — Полная документация проекта

> **Единая экосистема для административных задач**: десктопное приложение (Python/PyQt6) + браузерное расширение (Manifest V3)

---

## 📋 Оглавление

1. [Обзор архитектуры](#обзор-архитектуры)
2. [Десктопное приложение (Python)](#десктопное-приложение-python)
3. [Браузерное расширение (Manifest V3)](#браузерное-расширение-manifest-v3)
4. [Синхронизация данных](#синхронизация-данных)
5. [Установка и развёртывание](#установка-и-развёртывание)
6. [API и интеграции](#api-и-интеграции)
7. [Безопасность](#безопасность)
8. [Разработка](#разработка)
9. [Troubleshooting](#troubleshooting)

---

## 🏗️ Обзор архитектуры

```
┌─────────────────────────────────────────────────────────────────┐
                        AdminLauncher Ecosystem
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────────┐         ┌────────────────────────────┐   │
│  │  Desktop App     │         │  Browser Extension         │   │
│  │  (Python/PyQt6)  │  Sync   │  (Manifest V3, JS/TS)      │   │
│  │                  │ ──────► │                             │   │
│  │ • GMU (bus.gov)  │  JSON   │ • Side Panel (main UI)     │   │
│  │ • Budget         │  Files  │ • Popup (quick search)     │   │
│  │ • Cert Manager   │  Import │ • Options (settings)       │   │
│  │ • Launcher       │         │ • Content Scripts          │   │
│  │                  │         │ • Background SW            │   │
│  │ • Native certutil│         │ • Native Messaging Host    │   │
│  └──────────────────┘         └────────────────────────────┘   │
│           │                              │                      │
│           │         ┌────────────────────┘                      │
│           ▼         ▼                                             │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              Data Layer (JSON + IndexedDB)               │    │
│  │  • data.json (GMU)      • db.json (Budget)               │    │
│  │  • organizations.json   • cert_mgn.png (icons)           │    │
│  │  • IndexedDB (Extension): gmu_orgs, budget_orgs, certs   │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Ключевые принципы

| Принцип | Описание |
|---------|----------|
| **Offline-first** | Все данные хранятся локально (JSON / IndexedDB) |
| **No backend** | Работает без сервера, прямо с гос. API |
| **Cross-platform** | Desktop: Windows/Linux/macOS · Extension: Chrome/Edge/Firefox |
| **Native integration** | Windows certutil через Native Messaging |
| **Modern UI** | Desktop: PyQt6 · Extension: Tailwind CSS + Side Panel API |

---

## 🖥️ Десктопное приложение (Python)

### Структура проекта

```
admin_launcher/
├── main.py                    # Точка входа (launcher)
├── requirements.txt           # PyQt6, cryptography, openpyxl, requests, idb
├── run.sh                     # Скрипт запуска
├── admin_launcher.desktop     # .desktop файл для Linux
├── venv/                      # Виртуальное окружение
│
├── Core Modules:
│   ├── gmu_information.py     # GMU (bus.gov.ru) — поиск, сохранение, Excel
│   ├── budget.py              # Budget (budget.gov.ru) — УБП/НУБП реестр
│   ├── cert_manager.py        # Сертификаты — Windows certutil, КриптоПро
│   ├── launcher_ddo.pyw       # Быстрый запуск систем (ГМУ, ФНС, ЭДО)
│   ├── org_pdf.py             # PDF генерация для организаций
│
├── Data Files:
│   ├── data.json              # GMU организации (bus.gov.ru)
│   ├── db.json                # Budget организации (УБП/НУБП)
│   ├── organizations.json     # Справочник МБДОУ
│   ├── found_accounts.json    # Дополнительные счета
│   ├── ddo.json               # ДДО данные
│   ├── last_api_response.json # Кэш последнего API ответа
│   ├── last_link_responses.json
│
├── Icons & Assets:
│   ├── cert_mgn.png           # Иконка сертификатов
│   ├── list_org.ico           # Иконка организаций
│   ├── fns.ico                # ФНС иконка
│   └── Icon.png               # Главная иконка
│
└── export/                    # Папка для экспортов (Excel, PDF)
```

### Основные модули

#### 1. `gmu_information.py` — Модуль ГМУ (bus.gov.ru)

**Функционал:**
- Поиск организации по ИНН (10/12 цифр) и КПП (9 цифр)
- API: `https://bus.gov.ru/public-rest/api/7710568760-Generalinformation`
- Автоформирование Л/С: `20946 + regNum[3:] + 0`
- Классификаторы: ОКФС, ОКОПФ, ОКПО, ОКТМО, ОКОГУ, ОКВЭД
- Банковские реквизиты (фиксированные БИК/Р/С)
- Руководитель и учредитель
- Сохранение в `data.json` с ключом (название орга)
- Таблица сохранённых организаций (QTableWidget)
- Экспорт в Excel (openpyxl) со стилями
- Обновление из API по сохранённому ключу

**Ключевые функции:**
```python
BusGovApp.search_org(inn, kpp)           # Поиск по API
BusGovApp.extract_fields(api_response)   # Парсинг ответа
BusGovApp.build_ls(reg_num)              # Формирование Л/С
BusGovApp.format_requisites_text(data)   # Текст для отображения
BusGovApp.save_data(key)                 # Сохранение в JSON
BusGovApp.export_all_to_excel()          # Экспорт
```

#### 2. `budget.py` — Модуль Бюджет (budget.gov.ru)

**Функционал:**
- Реестр УБП/НУБП
- API: `https://budget.gov.ru/epbs/registry/ubpandnubp/data`
- Поиск по ИНН (`filterinn`) или наименованию (`filtername`)
- Блоки: `info,authorities,heads,facialAccounts,accountfk,foAccounts,ksAccounts,contacts,activities,...`
- Детализация: реквизиты, лицевые счета, казначейские счета, руководители, учредители, контакты, деятельность
- Вкладки (QTabWidget) по группам данных
- Сохранение в `db.json` с нормализацией структуры
- Экспорт/импорт JSON
- Обновление записей из API

**Ключевые структуры:**
```python
LABELS_RU = { "regNum": "Учётный номер", "inn": "ИНН", ... }  # Русские лейблы
GLOBAL_HIDDEN_KEYS = { "guid", "controlnum", ... }            # Скрытые поля

BudgetStore:  # IndexedDB-like операции через JSON
  load_db() / save_db() / search()
```

#### 3. `cert_manager.py` — Менеджер сертификатов

**Функционал (Windows):**
- Чтение `CurrentUser\My` и `LocalMachine\My` через CryptoAPI (crypt32.dll)
- Перечисление сертификатов с извлечением: CN, ИНН, СНИЛС, ОГРН, серийный номер, SHA1, SHA256, сроки
- Подсветка: 🔴 просрочен, 🟡 ≤7 дней, 🟢 действителен
- Экспорт в PEM/DER
- Экспорт PFX через `certutil -exportPFX`
- Импорт через `certutil -importPFX`
- Удаление сертификата + ключа через `certutil -delstore`
- Установка корневых УЦ
- КриптоПро поддержка (Linux): `certmgr -list` парсинг
- Экспорт метаданных в Excel

**Windows CryptoAPI:**
```python
crypt32.CertOpenSystemStoreW(0, "MY")           # Открыть хранилище
crypt32.CertEnumCertificatesInStore()           # Перебор сертификатов
CERT_CONTEXT.pbCertEncoded / cbCertEncoded      # DER данные
```

#### 4. `launcher_ddo.pyw` — Лаунчер систем

**Быстрые кнопки входа:**
- ГМУ (bus.gov.ru)
- Бюджет (budget.gov.ru)
- ФНС (nalog.gov.ru)
- Госуслуги (lkip.gosuslugi.ru)
- Закупки (zakupki.gov.ru)
- ЭДО системы

### Данные (JSON файлы)

#### `data.json` — GMU организации
```json
{
  "75": {
    "initiator": { "regNum": "963Ц8835", "fullName": "...", "inn": "2015002188", "kpp": "201501001" },
    "main": { "shortName": "...", "ogrn": "1112031003578", "classifier": {...}, "complexAddress": {...} },
    "other": { "chief": [{...}], "founder": [{...}], "ogrnData": "2011-12-15" }
  }
}
```

#### `db.json` — Budget организации
```json
{
  "63": {
    "INFO": { "regNum": "LZШ03", "inn": "2013012247", "fullName": "...", ... },
    "HEADS": [{ "fio": "...", "post": "...", ... }],
    "facialTerritorialAccounts": [{ "num": "20946LZШ030", "kindName": "лс БУ", ... }],
    "ksAccounts": [...],
    "authorities": [...]
  }
}
```

#### `organizations.json` — Справочник МБДОУ
```json
{
  "1": { "full_name": "...", "short_name": "...", "inn": "...", "kpp": "...", "ogrn": "...", "address": "...", "head_fio": "...", "post": "..." }
}
```

### Запуск десктопа

```bash
# 1. Активация venv
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate     # Windows

# 2. Установка зависимостей
pip install -r requirements.txt
# PyQt6, cryptography, openpyxl, requests

# 3. Запуск
python main.py
# или через лаунчер
./run.sh
```

### Сборка исполняемого файла (PyInstaller)

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --icon=Icon.png \
  --add-data "data.json:." --add-data "db.json:." \
  --add-data "organizations.json:." \
  --add-data "cert_mgn.png:." --add-data "list_org.ico:." \
  main.py
```

---

## 🌐 Браузерное расширение (Manifest V3)

### Структура

```
browser_extension/
├── manifest.json              # Manifest V3
├── package.json               # NPM скрипты
├── README.md                  # Документация
├── LICENSE                    # MIT
├── DOCUMENTATION.md           # Этот файл
│
├── public/
│   └── icons/                 # icon16/32/48/128.png, promo, marquee
│
├── _locales/
│   ├── ru/messages.json       # Русская локализация
│   └── en/messages.json       # Английская
│
├── src/
│   ├── manifest.json          # (копируется в dist)
│   │
│   ├── background/
│   │   └── background.js      # Service Worker
│   │       ├── CORS Proxy (fetch для API)
│   │       ├── Native Messaging (cert_host)
│   │       ├── Alarms (проверка сертификатов каждые 6ч)
│   │       ├── Context Menus (выделенный текст → поиск)
│   │       └── Notifications
│   │
│   ├── sidepanel/             # Основной UI (Side Panel API)
│   │   ├── sidepanel.html
│   │   └── sidepanel.js       # 4 вкладки: ГМУ, Бюджет, Сертификаты, Настройки
│   │
│   ├── popup/                 # Быстрый доступ
│   │   ├── popup.html
│   │   └── popup.js           # Поиск + быстрые действия
│   │
│   ├── options/               # Полные настройки
│   │   ├── options.html
│   │   └── options.js         # Импорт JSON, экспорт, настройки
│   │
│   ├── content/               # Content Scripts
│   │   ├── content.js         # Автозаполнение, кнопки на сайтах
│   │   └── content.css        # Стили внедряемых элементов
│   │
│   └── shared/                # Общие модули
│       ├── api.js             # API клиенты (GMU, Budget, Cert, Utils)
│       └── storage.js         # IndexedDB (Dexie/idb) слой
│
├── native_host/               # Native Messaging Host
│   ├── cert_host.py           # Python host (certutil wrapper)
│   ├── cert_host.bat          # Windows launcher
│   ├── com.adminlauncher.cert_host.json  # Manifest template
│   ├── install_windows.ps1    # Установка Windows (HKCU/HKLM)
│   └── install_linux.sh       # Установка Linux/macOS
│
└── scripts/
    ├── build.js               # esbuild сборка
    ├── package.js             # Упаковка .zip для магазинов
    └── generate-icons.js      # Генерация иконок (canvas)
```

### Manifest V3 — ключевые разрешения

```json
{
  "manifest_version": 3,
  "permissions": [
    "storage", "sidePanel", "activeTab", "scripting",
    "contextMenus", "alarms", "notifications",
    "downloads", "clipboardWrite", "clipboardRead"
  ],
  "host_permissions": [
    "https://bus.gov.ru/*",
    "https://budget.gov.ru/*",
    "https://api.nalog.ru/*",
    "https://*.gosuslugi.ru/*",
    "https://*.zakupki.gov.ru/*"
  ],
  "background": { "service_worker": "background.js", "type": "module" },
  "side_panel": { "default_path": "sidepanel.html" },
  "action": { "default_popup": "popup.html" },
  "options_page": "options.html",
  "content_scripts": [{
    "matches": ["*://bus.gov.ru/*", "*://budget.gov.ru/*", ...],
    "js": ["content.js"], "css": ["content.css"]
  }]
}
```

### Service Worker (`background.js`)

**Ответственности:**

1. **CORS Proxy** — `chrome.runtime.sendMessage({type: 'FETCH', url, options})`
   ```js
   // Позволяет вызывать гос. API из content script / sidepanel
   // Обходит CORS через background fetch
   ```

2. **Native Messaging** — мост к `cert_host.py`
   ```js
   chrome.runtime.sendNativeMessage('com.adminlauncher.cert_host', {action, payload})
   // Actions: list_stores, list_certs, export_pfx, import_cert, delete_cert, install_root
   ```

3. **Alarms** — фоновая проверка сроков сертификатов
   ```js
   chrome.alarms.create('cert-check', {periodInMinutes: 360})  // 6 часов
   // Проверяет chrome.storage.local.certsCache
   // Показывает Notification с кнопкой "Открыть"
   ```

4. **Context Menus** — правый клик на выделенном тексте
   - "Найти в ГМУ"
   - "Найти в Бюджете"
   - "Проверить ИНН"

### Side Panel (`sidepanel.js`) — Основной UI

**4 вкладки:**

| Вкладка | Функционал |
|---------|------------|
| **ГМУ** | Поиск по ИНН/КПП → список сохранённых → детали: реквизиты, классификаторы, адрес, банк. данные, руководитель, учредитель. Кнопки: копировать, экспорт CSV, удалить, открыть на bus.gov.ru |
| **Бюджет** | Поиск по ИНН/наименованию → вкладки: Информация, Л/с, Каз. счета, Руководители, Контакты, Деятельность, Учредители. Сохранение/обновление из API. |
| **Сертификаты** | Загрузка из Windows Store (Native Host) → фильтры: все/действительные/просроченные → детали: CN, ИНН, СНИЛС, ОГРН, SHA1/256, сроки, контейнер. Экспорт PEM/PFX, удаление. |
| **Настройки** | Тема (system/light/dark), автопоиск, история, уведомления, хранилище сертификатов, API endpoints, импорт/экспорт JSON, очистка данных. |

**Горячие клавиши (в Side Panel):**
| Клавиша | Действие |
|---------|----------|
| `1` | Вкладка ГМУ |
| `2` | Вкладка Бюджет |
| `3` | Вкладка Сертификаты |
| `4` | Настройки |
| `/` | Фокус на поиск |
| `Esc` | Закрыть выпадашки |
| `R` | Обновить сертификаты |

### IndexedDB Storage (`storage.js` — idb/Dexie-like)

**Хранилища:**
```javascript
// gmu_orgs       — GMU организации (key, inn, fullName, ...)
// budget_orgs    — Budget организации (key, regNum, inn, info, heads, accounts...)
// certificates   — Сертификаты (sha1, cn, inn, snils, ogrn, notAfter, raw, source)
// settings       — Настройки (theme, autoSearch, certStore, ...)
// search_history — История поиска (type, query, timestamp)
// api_cache      — Кэш API ответов (key, data, expiresAt)
```

**API:**
```javascript
GmuStore.save(key, data) / get(key) / getAll() / search(query) / export() / import(json)
BudgetStore.* — аналогично
CertStore.save(cert) / getBySha1(sha1) / getExpiring(days) / getExpired()
SettingsStore.get(key) / set(key, value)
HistoryStore.add(type, query) / getRecent(type, limit)
BackupStore.createFullBackup() / restoreFromBackup(json)
```

### Native Messaging Host (`native_host/cert_host.py`)

**Протокол:** stdin/stdout JSON с длиной префиксом (4 байта, little-endian)

**Actions:**
```python
# Список хранилищ
{"action": "list_stores"} 
→ {"stores": ["MY", "ROOT", "CA", ...]}

# Список сертификатов
{"action": "list_certs", "payload": {"store": "MY", "machine": false}}
→ {"certs": [{"sha1": "...", "cn": "...", "inn": "...", "not_after": "2025-12-31", ...}]}

# Экспорт PFX
{"action": "export_pfx", "payload": {"store": "MY", "sha1": "...", "password": ""}}
→ {"success": true, "pfx_base64": "..."}

# Импорт PFX
{"action": "import_cert", "payload": {"store": "MY", "pfx_base64": "...", "password": ""}}

# Удаление
{"action": "delete_cert", "payload": {"store": "MY", "sha1": "..."}}

# Установка корневого УЦ
{"action": "install_root", "payload": {"der_base64": "..."}}
```

**Установка Windows:**
```powershell
# Получение Extension ID из chrome://extensions
.\install_windows.ps1 -AllUsers -ExtensionId "abcdefghijklmnopqrstuvwxyz123456"
```
Создаёт записи в реестре:
- `HKLM\SOFTWARE\Google\Chrome\NativeMessagingHosts\com.adminlauncher.cert_host`
- `HKLM\SOFTWARE\Microsoft\Edge\NativeMessagingHosts\com.adminlauncher.cert_host`

**Установка Linux/macOS:**
```bash
./install_linux.sh EXTENSION_ID
```
Копирует манифест в `~/.config/google-chrome/NativeMessagingHosts/` и аналогичные для Chromium/Edge/Vivaldi/Brave/Opera.

### Content Scripts (`content.js`)

**Поддерживаемые сайты:**
- `bus.gov.ru` — автозаполнение ИНН/КПП, кнопки "Открыть в AdminLauncher", "Сохранить"
- `budget.gov.ru` — поиск по ИНН, подсветка ИНН, кнопки действий
- `nalog.gov.ru` — проверка долгов, копирование ИНН
- `lkip.gosuslugi.ru` — работа с сертификатами
- `zakupki.gov.ru` / `eis2.zakazrf.ru` — контекстное меню для ИНН

**Фичи:**
- Улучшенные инпуты: кнопка очистки, история ИНН (dropdown), валидация контрольной суммы
- Paste handler: "ИНН КПП" → автозаполнение двух полей
- Toolbar на карточках организаций: копировать ИНН, открыть в Side Panel, сохранить
- MutationObserver для динамического контента

---

## 🔄 Синхронизация данных

### Импорт из Desktop JSON → Extension IndexedDB

**Через Options страницу расширения (Вкладка "Данные" → "Импорт из исходного проекта"):**

| Файл | Кнопка | Куда импортируется |
|------|--------|-------------------|
| `data.json` | **Импортировать ГМУ** | `gmu_orgs` (вкладка ГМУ) |
| `db.json` | **Импортировать Бюджет** | `budget_orgs` (вкладка Бюджет) |
| `organizations.json` | **Импортировать Организации** | `gmu_orgs` (дедуп по ИНН) |
| `found_accounts.json` | **Импортировать Счета** | (в разработке) |

**Процесс:**
1. Открыть Options → вкладка "Данные"
2. Выбрать файл через `<input type="file">`
3. Нажать кнопку импорта
4. Наблюдать прогресс-бар и лог
5. Данные сразу доступны в Side Panel

### Экспорт из Extension → JSON

**Options → "Импорт / Экспорт настроек расширения":**
- **Экспорт всего (JSON)** — полная копия: GMU, Budget, Certs, Settings, History
- **Экспорт ГМУ (CSV)** — табличный экспорт организаций
- **Экспорт Бюджет (JSON)** — сырые записи
- **Экспорт Сертификаты (JSON)** — метаданные сертификатов

### Структура полной резервной копии

```json
{
  "version": 1,
  "timestamp": 1700000000000,
  "gmu": [...],
  "budget": [...],
  "certificates": [...],
  "settings": {...},
  "history": [...]
}
```

---

## 🚀 Установка и развёртывание

### Десктоп (Python)

#### Требования
- Python 3.10+
- Windows: Visual C++ Redistributable (для cryptography)
- Linux: `python3-pyqt6`, `python3-cryptography`, `python3-openpyxl`, `libcairo2`, `libpango1.0`

#### Установка
```bash
git clone <repo>
cd admin_launcher

# Linux/macOS
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Windows
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

#### Запуск
```bash
python main.py
# или
./run.sh
```

#### Автозапуск (Linux .desktop)
```bash
cp admin_launcher.desktop ~/.local/share/applications/
# Или системно:
sudo cp admin_launcher.desktop /usr/share/applications/
```

### Браузерное расширение

#### Режим разработчика (для тестов)

**Chrome / Edge / Vivaldi / Brave / Opera:**
1. `chrome://extensions` → Включить "Режим разработчика"
2. "Загрузить распакованное" → выбрать папку `browser_extension/dist`

**Firefox:**
1. `about:debugging` → "Это Firefox" → "Временное расширение"
2. Выбрать `browser_extension/dist/manifest.json`

#### Продакшн сборка

```bash
cd browser_extension
npm install
npm run build        # → dist/
npm run package      # → package/*.zip
```

**Результат:**
- `package/admin-launcher-chrome-v1.0.0.zip` — Chrome Web Store, Edge Add-ons
- `package/admin-launcher-firefox-v1.0.0.zip` — Firefox Add-ons (MV3 адаптирован)

#### Публикация в магазины

**Chrome Web Store:**
1. Загрузить `admin-launcher-chrome-v*.zip`
2. Заполнить описание, скриншоты (promo-440x280.png, marquee-1400x560.png)
3. Добавить политику конфиденциальности
4. Отправить на рассмотрение

**Firefox Add-ons:**
1. Загрузить `admin-launcher-firefox-v*.zip` (или исходники)
2. Подписать через `web-ext sign`

#### Native Messaging Host (обязательно для сертификатов)

**Windows (PowerShell от админа):**
```powershell
cd browser_extension/native_host
.\install_windows.ps1 -AllUsers -ExtensionId "ВАШ_EXTENSION_ID"
```

**Linux/macOS:**
```bash
cd browser_extension/native_host
chmod +x install_linux.sh
./install_linux.sh ВАШ_EXTENSION_ID
```

**Проверка:**
1. Перезапустить браузер
2. Открыть Side Panel → Настройки → Сертификаты → "Проверить Native Host"
3. Должно показать: `✅ Native Host работает. Доступные хранилища: MY, ROOT, CA...`

---

## 🔌 API и интеграции

### Внешние API (используются напрямую)

| API | Endpoint | Метод | Параметры | Использование |
|-----|----------|-------|-----------|---------------|
| **GMU (bus.gov.ru)** | `https://bus.gov.ru/public-rest/api/7710568760-Generalinformation` | GET | `inn`, `kpp` | Поиск организации |
| **Budget (budget.gov.ru)** | `https://budget.gov.ru/epbs/registry/ubpandnubp/data` | GET | `blocks`, `filterinn`, `filtername`, `pageSize` | УБП/НУБП реестр |
| **Налог (api.nalog.ru)** | `https://api.nalog.ru/v1/org` | GET | `inn` | Проверка организации |
| **Госуслуги** | `https://api.gosuslugi.ru/v1/...` | — | — | Интеграция (планируется) |

### Внутренние API (Extension)

#### Background → SidePanel Messages
```javascript
// Поиск
{ type: 'SEARCH', engine: 'gmu'|'budget', query: '2015002188' }

// Открыть вкладку
{ type: 'OPEN_TAB', tab: 'gmu'|'budget'|'certs', key: 'optional' }

// Native Call
{ type: 'NATIVE_CALL', action: 'list_certs', payload: { store: 'MY', machine: false } }

// Обновление сертификатов
{ type: 'REFRESH_CERTS' }
```

#### SidePanel → Background (через runtime.sendMessage)
```javascript
// Fetch через background (CORS proxy)
const resp = await chrome.runtime.sendMessage({ type: 'FETCH', url, options })

// Native Messaging
const resp = await chrome.runtime.sendMessage({ type: 'NATIVE_CALL', action, payload })
```

### Content Script ↔ Extension
```javascript
// Из background/content в content script
chrome.tabs.sendMessage(tabId, { type: 'FILL_INN', inn: '2015002188', kpp: '201501001' })
chrome.tabs.sendMessage(tabId, { type: 'HIGHLIGHT_INN', inn: '2015002188' })
chrome.tabs.sendMessage(tabId, { type: 'EXTRACT_DATA' })
```

---

## 🔐 Безопасность

### Принципы

| Аспект | Реализация |
|--------|------------|
| **Минимальные права** | `host_permissions` только для гос. доменов |
| **CORS Proxy** | Все внешние запросы через background SW |
| **Native Messaging** | Изолированный доступ к certutil (Windows) |
| **CSP** | `script-src 'self' 'wasm-unsafe-eval'; object-src 'self'` |
| **Нет телеметрии** | Никаких внешних запросов, кроме гос. API |
| **Локальное хранение** | IndexedDB + JSON файлы, никаких облаков |

### Native Messaging Security

- **Allowed origins** — только ваш Extension ID в манифесте хоста
- **Input validation** — проверка SHA1 формата, экранирование аргументов certutil
- **No arbitrary commands** — только whitelist actions
- **Timeout** — 30 сек на операцию certutil

### Content Security Policy

```json
"content_security_policy": {
  "extension_pages": "script-src 'self' 'wasm-unsafe-eval'; object-src 'self'; worker-src 'self' blob:;"
}
```

---

## 🛠️ Разработка

### Структура команд

```bash
# Browser Extension
cd browser_extension
npm install              # Зависимости
npm run dev              # Watch режим (esbuild + chokidar)
npm run build            # Production build (minified)
npm run package          # Создание .zip для магазинов
npm run lint             # ESLint
npm run test             # Jest (если добавлены тесты)

# Desktop
cd ..
source venv/bin/activate
python main.py           # Запуск
python -m pytest         # Тесты (если есть)
```

### Добавление нового API модуля

1. **Shared API** (`src/shared/api.js`):
   ```javascript
   export const NewApi = {
     async search(query) { ... },
     formatForUI(data) { ... }
   }
   ```

2. **Storage** (`src/shared/storage.js`):
   ```javascript
   export const NewStore = {
     async save(key, data) { ... },
     async search(query) { ... }
   }
   ```

3. **SidePanel Tab** — добавить в `sidepanel.html` + `sidepanel.js`:
   - Tab button
   - Panel с поиском/списком/деталями
   - Render функции

4. **Manifest** — добавить `host_permissions` для нового домена

### Отладка

| Компонент | Как отладить |
|-----------|--------------|
| **Background SW** | `chrome://extensions` → AdminLauncher → "Service worker" (Inspect) |
| **Side Panel** | Правый клик на панели → "Inspect" |
| **Popup** | Правый клик на иконке → "Inspect popup" |
| **Content Script** | F12 на странице → Console → фильтр "AdminLauncher" |
| **Options** | Открыть options.html → F12 |
| **Native Host** | Логи в stderr (не нарушают протокол), или добавьте файловый логгер в `cert_host.py` |

### Логирование (Debug Mode)

В Options → Advanced → "Режим отладки" включает:
- Подробные `console.log` в background, sidepanel, content
- Вывод storage в консоль (кнопка "Вывести storage в консоль")
- Тест всех API (кнопка "Тест всех API")

---

## 🐛 Troubleshooting

### Расширение не загружается / ошибки в консоли

| Ошибка | Решение |
|--------|---------|
| `Could not resolve "idb"` | `npm install idb` в `browser_extension` |
| `Manifest V3 requires service worker` | Проверьте `background.service_worker` в manifest.json |
| `Side Panel API not supported` | Chrome 114+ / Edge 114+ требуется |
| `Native Messaging host not found` | Установите host через `.ps1` / `.sh`, перезапустите браузер |

### Native Messaging не работает

```powershell
# 1. Проверьте реестр
reg query "HKCU\SOFTWARE\Google\Chrome\NativeMessagingHosts\com.adminlauncher.cert_host"
reg query "HKLM\SOFTWARE\Google\Chrome\NativeMessagingHosts\com.adminlauncher.cert_host"

# 2. Проверьте манифест
type "%LOCALAPPDATA%\Google\Chrome\NativeMessagingHosts\com.adminlauncher.cert_host.json"
# path должен указывать на .bat файл
# allowed_origins должен содержать ваш Extension ID

# 3. Тест вручную
echo '{"action":"list_stores"}' | cert_host.bat
# Должен вернуть JSON со списком хранилищ
```

**Частые проблемы Windows:**
- Python не в PATH → укажите полный путь в `cert_host.bat`
- `certutil` не найден → должен быть в `C:\Windows\System32\certutil.exe`
- Права доступа → запустите установку от Администратора (`-AllUsers`)

### Сертификаты не загружаются

1. Проверьте Native Host: Options → Сертификаты → "Проверить Native Host"
2. Убедитесь, что хранилище выбрано верно (CurrentUser/My vs LocalMachine/My)
3. На Linux: проверьте путь к `certmgr` в настройках (`/opt/cprocsp/bin/amd64/certmgr`)

### API возвращает ошибки

| Код | Причина | Решение |
|-----|---------|---------|
| 403 / CORS | Прямой запрос из content script | Используйте `chrome.runtime.sendMessage({type:'FETCH'})` через background |
| 404 | Организация не найдена | Проверьте ИНН (10/12 цифр), КПП (9 цифр) |
| 500 / Timeout | Перегрузка гос. API | Повторите позже, увеличьте timeout |
| NET::ERR_CERT_AUTHORITY_INVALID | Самостоятельно подписанные сертификаты тестовых контуров | Настройте `apiGmu`/`apiBudget` в Options на тестовые эндпоинты |

### Данные не сохраняются / IndexedDB ошибки

```javascript
// В консоли Side Panel / Options:
await chrome.storage.local.clear()           // Очистить local storage
await idb.deleteDB('AdminLauncherDB')        // Полная очистка IndexedDB (в DevTools Console)
// Или кнопка "ПОЛНОСТЬЮ СБРОСИТЬ ВСЕ ДАННЫЕ" в Options
```

### Десктоп приложение

| Проблема | Решение |
|----------|---------|
| `ModuleNotFoundError: PyQt6` | `pip install PyQt6` в venv |
| `certutil not found` (Windows) | Добавьте `C:\Windows\System32` в PATH |
| `libcairo2` ошибка (Linux) | `sudo apt install libcairo2-dev libpango1.0-dev` |
| Иконки не отображаются | Проверьте пути к `.ico`/`.png` в коде (`os.path.dirname(__file__)`) |

---

## 📝 Лицензия и авторы

**MIT License** — см. [LICENSE](LICENSE)

**Авторы:** AdminLauncher Team

**Компоненты:**
- Desktop: Python 3, PyQt6, cryptography, openpyxl, requests
- Extension: Manifest V3, Tailwind CSS, idb (IndexedDB), esbuild
- Native Host: Python 3, certutil (Windows), certmgr (КриптоПро)

---

## 🔗 Полезные ссылки

- [Chrome Extensions Manifest V3](https://developer.chrome.com/docs/extensions/mv3/)
- [Side Panel API](https://developer.chrome.com/docs/extensions/side-panel/)
- [Native Messaging](https://developer.chrome.com/docs/extensions/mv3/nativeMessaging/)
- [IndexedDB / idb](https://github.com/jakearchibald/idb)
- [bus.gov.ru API](https://bus.gov.ru/)
- [budget.gov.ru API](https://budget.gov.ru/)
- [КриптоПро CSP](https://www.cryptopro.ru/)

---

*Документация актуальна для версии 1.0.0. Последнее обновление: 2026-11-22*

---

## ⚠️ Текущее состояние браузерного расширения

Расширение в папке `browser_extension/` реализовано в упрощённом виде (без шага сборки, загружается как "Распакованное" через `chrome://extensions`). Ниже — пошаговая инструкция по установке.

### Установка браузерного расширения (Chrome / Edge / Vivaldi / Brave / Opera)

1. **Удалите старую версию** (если была установлена ранее):
   - Откройте `chrome://extensions`
   - Найдите AdminLauncher → нажмите "Удалить"
   - Полностью закройте браузер (все окна)

2. **Загрузите расширение**:
   - Снова откройте браузер
   - Перейдите на `chrome://extensions`
   - Включите **"Режим разработчика"** (переключатель в правом верхнем углу)
   - Нажмите кнопку **"Загрузить распакованное"**
   - Выберите папку: `browser_extension/` (папка с `manifest.json`)

3. **Проверка**:
   - AdminLauncher появится в списке расширений
   - Нажмите на иконку расширения на панели инструментов — откроется popup с кнопками "ГМУ" и "Бюджет"

### Что делает расширение

| Приложение | Что делает | API |
|------------|-----------|-----|
| **ГМУ** | Поиск организации по ИНН/КПП, реквизиты, классификаторы (ОКФС, ОКОПФ, ОКПО, ОКТМО, ОКВЭД), банковские реквизиты (Л/С, БИК, Р/С, счета 20/80), сохранение в локальную базу JSON | `bus.gov.ru` |
| **Бюджет** | Поиск по ИНН/наименованию, вкладки реквизитов (Информация, Руководитель, Лицевой счёт, Казнач. счёт, Контакты, Деятельность, Учредитель), сохранение в локальную базу JSON | `budget.gov.ru` |

Данные хранятся в `chrome.storage.local` (ключи `gmu` и `budget`). При первом запуске данные импортируются из `data/gmu.json` и `data/budget.json`.

Иконки: `data/icon16.svg`, `data/icon48.svg`.

### Устранение проблем

- **Расширение не появилось** — убедитесь, что выбрана папка `browser_extension/` (где лежит `manifest.json`), а не корень проекта
- **Кнопка "Обновить из API" не работает** — проверьте консоль сервис-воркера: `chrome://extensions` → AdminLauncher → "Service worker". Возможно, bus.gov.ru или budget.gov.ru недоступны из вашей сети
- **Данные не загрузились** — откройте консоль приложения (F12 на странице приложения) и поищите логи `[AdminLauncher]` о импорте JSON

---
