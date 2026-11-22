#!/bin/bash
# Переходим в директорию скрипта
cd "$(dirname "$0")"

# Запускаем через локальное виртуальное окружение
./venv/bin/python launcher_ddo.pyw
