# AdminLauncher

Единая экосистема для административных задач: десктопное приложение (Python/PyQt6) + браузерное расширение (Manifest V3) для работы с гос. реестрами (bus.gov.ru, budget.gov.ru) и сертификатами.

## 📁 Структура проекта

```
admin_launcher/
├── budget.py              # Десктоп: реестр УБП/НУБП (budget.gov.ru)
├── gmu_information.py     # Десктоп: ГМУ (bus.gov.ru)
├── cert_manager.py        # Десктоп: сертификаты (certutil / КриптоПро)
├── launcher_ddo.pyw       # Десктоп: лаунчер систем
├── org_pdf.py             # Десктоп: PDF организации
├── AutoSUFD.py            # Дополнительный модуль
├── run.sh                 # Скрипт запуска
├── admin_launcher.desktop # .desktop для Linux
├── requirements.txt       # Зависимости Python
├── data.json              # GMU организации (рантайм)
├── db.json                # Budget организации (рантайм)
├── organizations.json     # Справочник МБДОУ
├── DOCUMENTATION.md       # Полная документация
├── QUICKSTART.md          # Быстрый старт
├── .gitignore             # Игнорируемые файлы
└── browser_extension/     # Браузерное расширение (Manifest V3)
    ├── manifest.json      # Манифест расширения
    ├── background.js      # Сервис-воркер (CORS-прокси API)
    ├── popup.html         # Главное окно (popup)
    ├── popup.js           # Логика popup
    ├── shared/
    │   ├── api.js         # API клиенты + chrome.storage.local
    │   └── style.css      # Стили
    ├── apps/
    │   ├── gmu.html + gmu.js      # Приложение ГМУ
    │   └── budget.html + budget.js # Приложение Бюджет
    └── data/
        ├── gmu.json       (99 записей — источник импорта)
        ├── budget.json    (102 записи — источник импорта)
        ├── nalog.json     (приложение Налог удалено)
        └── icon16.svg, icon48.svg
```

## 🌐 Браузерное расширение — установка

Расширение загружается как **"Распакованное"** через `chrome://extensions` (без шага сборки).

### Пошаговая установка

1. **Удалите старую версию** (если была):
   - `chrome://extensions` → AdminLauncher → "Удалить"
   - Полностью закройте браузер

2. **Загрузите новую версию**:
   - Откройте браузер → `chrome://extensions`
   - Включите **"Режим разработчика"** (правый верхний угол)
   - Нажмите **"Загрузить распакованное"**
   - Выберите папку: `browser_extension/` (где лежит `manifest.json`)

3. **Проверка**:
   - Нажмите на иконку расширения → popup с кнопками "ГМУ" и "Бюджет"

### Что делает расширение

| Приложение | Возможности | API |
|------------|------------|-----|
| **ГМУ** | Поиск по ИНН/КПП, реквизиты, классификаторы (ОКФС, ОКОПФ, ОКПО, ОКТМО, ОКВЭД), банковские реквизиты (Л/С, БИК, Р/С, счета 20/80), экспорт CSV/JSON | `bus.gov.ru` |
| **Бюджет** | Поиск по ИНН/наименованию, вкладки реквизитов, экспорт CSV/JSON | `budget.gov.ru` |

Данные хранятся в `chrome.storage.local` (ключи `gmu` и `budget`). При первом запуске импортируются из `data/gmu.json` и `data/budget.json`.

## 🖥️ Десктопное приложение

```bash
# Активируйте venv
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate     # Windows

# Установите зависимости
pip install -r requirements.txt

# Запустите
python main.py
# или
./run.sh
```

## 📖 Документация

- `DOCUMENTATION.md` — полная документация (архитектура, API, troubleshooting)
- `QUICKSTART.md` — быстрый старт (5 минут)

## 🔗 Ссылки

- [bus.gov.ru API](https://bus.gov.ru/)
- [budget.gov.ru API](https://budget.gov.ru/)
- [КриптоПро CSP](https://www.cryptopro.ru/)

---

**Лицензия:** MIT — см. [LICENSE](LICENSE)
