/**
 * AdminLauncher — ГМУ (bus.gov.ru)
 * Повторяет GUI десктопа gmu_information.py: поля ИНН/КПП, поиск, реквизиты,
 * ключ хранения, кнопки сохранить/загрузить/обновить/удалить/показать таблицу.
 */

const SITE_URL = 'https://bus.gov.ru/';

let currentData = null;   // последний результат поиска (как current_data в десктопе)
let currentKey = null;    // ключ текущей записи в базе

const FIXED_BIC = '019690001';
const FIXED_RS = '03234643967010009400';

// ===== Л/С (счёт 20) по правилу десктопа =====
function buildLs(regNum) {
  if (!regNum) return '';
  const s = String(regNum);
  if (s.length <= 3) return '';
  return '20946' + s.substring(3) + '0';
}

// ===== Счёт 80 по правилу десктопа =====
function buildLs80(regNum) {
  if (!regNum) return '';
  const s = String(regNum);
  if (s.length <= 3) return '';
  return '803' + s.substring(3) + '000';
}

// ===== ЭЛЕМЕНТЫ =====
const els = {};

function cacheEls() {
  els.inn = document.getElementById('inn');
  els.kpp = document.getElementById('kpp');
  els.btnSearch = document.getElementById('btn-search');
  els.result = document.getElementById('result');
  els.key = document.getElementById('key');
  els.btnSave = document.getElementById('btn-save');
  els.btnSave = document.getElementById('btn-save');
  els.btnLoad = document.getElementById('btn-load');
  els.btnUpdate = document.getElementById('btn-update');
  els.btnTable = document.getElementById('btn-table');
  els.btnDelete = document.getElementById('btn-delete');
  els.btnExport = document.getElementById('btn-export');
  els.btnReimport = document.getElementById('btn-reimport');
  els.btnExportJson = document.getElementById('btn-export-json');
  els.hint = document.getElementById('hint');
  els.footer = document.getElementById('footer-status');
}

// ===== ПОИСК (как search_org в десктопе) =====
async function doSearch() {
  const inn = els.inn.value.trim();
  const kpp = els.kpp.value.trim() || null;

  if (!/^\d+$/.test(inn) || ![10, 12].includes(inn.length)) {
    setHint('Введите корректный ИНН (10 или 12 цифр).');
    return;
  }
  if (kpp && (!/^\d+$/.test(kpp) || kpp.length !== 9)) {
    setHint('КПП должен быть 9 цифр или оставьте поле пустым.');
    return;
  }

  setHint('Поиск по ИНН/КПП...');
  els.btnSearch.disabled = true;

  try {
    const data = await searchGmu(inn, kpp);
    if (!data) {
      setHint('Организация не найдена.');
      els.result.innerHTML = '<div style="color:#6b7280;">Организация не найдена.</div>';
      currentData = null;
      return;
    }
    currentData = data;
    displayRequisites(data);
    setHint('Найдено: ' + (data.shortName || data.fullName));
  } catch (err) {
    setHint('Ошибка поиска: ' + err.message);
    console.error(err);
  } finally {
    els.btnSearch.disabled = false;
  }
}

// ===== ОТОБРАЖЕНИЕ РЕКВИЗИТОВ (как display_requisites в десктопе) =====
function displayRequisites(data) {
  const cls = data.classifiers || {};

  let html = '';
  html += '<div style="margin-bottom:10px;"><strong>Источник:</strong> ' + escapeHtml(data.source) + '</div>';
  html += kv('Полное наименование', data.fullName);
  html += kv('Краткое наименование', data.shortName);
  html += kv('ИНН', data.inn);
  html += kv('КПП', data.kpp);
  html += kv('ОГРН', data.ogrn);
  html += kv('Реестровый номер', data.regNum);
  html += kv('Тип организации', data.orgType);
  html += kv('Адрес', data.address);
  html += kv('Руководитель', data.chief);
  html += kv('Учредитель', data.founder);

  const ls = buildLs(data.regNum);
  const ls80 = buildLs80(data.regNum);
  html += '<div style="margin-top:10px;font-weight:600;">💳 Банковские реквизиты:</div>';
  html += kv('Л/С (счёт 20)', ls);
  html += kv('БИК', FIXED_BIC);
  html += kv('Р/С', FIXED_RS);
  if (ls80) html += kv('Счёт 80', ls80);

  if (cls && Object.keys(cls).length) {
    html += '<div style="margin-top:12px;font-weight:600;">Классификаторы:</div>';
    const okfs = cls.okfs || {};
    if (okfs.code) html += kv('ОКФС', okfs.code + (okfs.name ? ' — ' + okfs.name : ''));
    const okopf = cls.okopf || {};
    if (okopf.code) html += kv('ОКОПФ', okopf.code + (okopf.name ? ' — ' + okopf.name : ''));
    const okpo = cls.okpo;
    if (okpo) html += kv('ОКПО', String(okpo));
    const oktmo = cls.oktmo || {};
    if (oktmo.code) html += kv('ОКТМО', oktmo.code + (oktmo.name ? ' — ' + oktmo.name : ''));
    const okved = cls.okved || [];
    if (Array.isArray(okved) && okved.length) {
      const okvedLines = okved.map(v => {
        const c = v.code || '';
        const n = v.name || '';
        const t = v.type ? ' (' + v.type + ')' : '';
        return c + (n ? ' — ' + n : '') + t;
      });
      html += kv('ОКВЭД', okvedLines.join('; '));
    }
    // Остальные классификаторы
    for (const [k, v] of Object.entries(cls)) {
      if (['okfs','okopf','okpo','oktmo','okved'].includes(k.toLowerCase())) continue;
      html += kv(k, formatClassifier(v));
    }
  }

  html += '<div style="margin-top:16px;font-weight:600;color:#6b7280;cursor:pointer;" id="btn-show-raw">Показать raw JSON ответа API</div>';
  html += '<div id="raw-area" style="display:none;margin-top:6px;background:#f3f4f6;border:1px solid #e5e7eb;border-radius:6px;padding:8px;font-family:ui-monospace,monospace;font-size:11px;overflow:auto;max-height:300px;">' +
    escapeHtml(JSON.stringify(data.raw || data, null, 2)) + '</div>';

  els.result.innerHTML = html;

  document.getElementById('btn-show-raw').addEventListener('click', () => {
    const area = document.getElementById('raw-area');
    area.style.display = area.style.display === 'none' ? 'block' : 'none';
  });
}

function kv(label, value) {
  if (value == null || value === '') return '';
  return '<div style="margin-bottom:4px;"><strong>' + escapeHtml(label) + ':</strong> <span style="font-family:ui-monospace,monospace;">' + escapeHtml(String(value)) + '</span></div>';
}

function formatClassifier(v) {
  if (v == null) return '';
  if (typeof v === 'object') {
    if (v.code !== undefined) return v.code + (v.name ? ' — ' + v.name : '');
    return JSON.stringify(v);
  }
  return String(v);
}

// ===== СОХРАНЕНИЕ (как save_data в десктопе — QInputDialog ключ) =====
els.btnSave = null; // переопределим после кэша

async function doSave() {
  if (!currentData) {
    setHint('Нет данных для сохранения.');
    return;
  }
  const key = prompt('Введите ключ хранения (название организации):', currentData.shortName || currentData.fullName || currentData.inn);
  if (key === null || !key.trim()) return;

  const all = await storeGet('gmu');
  const record = { ...currentData, key: key.trim(), source: 'gmu', savedAt: new Date().toISOString() };
  all[record.key] = record;
  await storeSet('gmu', all);
  currentKey = record.key;
  els.key.value = currentKey;
  setHint('Сохранено под ключом "' + currentKey + '".');
}

// ===== ЗАГРУЗКА ПО КЛЮЧУ (как load_data в десктопе) =====
async function doLoad() {
  const key = els.key.value.trim();
  if (!key) { setHint('Введите ключ для загрузки.'); return; }
  const all = await storeGet('gmu');
  const rec = all[key];
  if (!rec) { setHint('Ключ "' + key + '" не найден в базе.'); return; }
  currentData = rec;
  displayRequisites(rec);
  setHint('Загружено под ключом "' + key + '".');
}

// ===== ОБНОВЛЕНИЕ ИЗ API ПО КЛЮЧУ (как update_data в десктопе) =====
async function doUpdate() {
  const key = els.key.value.trim();
  if (!key) { setHint('Введите ключ для обновления.'); return; }
  const all = await storeGet('gmu');
  const rec = all[key];
  if (!rec) { setHint('Ключ "' + key + '" не найден в базе.'); return; }
  const inn = rec.inn;
  if (!inn) { setHint('Нет ИНН для обновления.'); return; }
  setHint('Обновление из API...');
  try {
    const updated = await searchGmu(inn, rec.kpp || '');
    if (!updated) { setHint('Организация не найдена в API.'); return; }
    updated.key = key;
    updated.source = 'gmu';
    updated.savedAt = new Date().toISOString();
    all[key] = updated;
    await storeSet('gmu', all);
    currentData = updated;
    displayRequisites(updated);
    setHint('Данные по ключу "' + key + '" обновлены из API.');
  } catch (err) {
    setHint('Ошибка обновления: ' + err.message);
  }
}

// ===== ПОКАЗАТЬ ТАБЛИЦУ ОРГАНИЗАЦИЙ (как show_organizations_table в десктопе) =====
function doShowTable() {
  // Создаём модальное окно с таблицей всех сохранённых организаций
  const modal = document.createElement('div');
  modal.style.position = 'fixed';
  modal.style.top = '0'; modal.style.left = '0';
  modal.style.width = '100vw'; modal.style.height = '100vh';
  modal.style.background = 'rgba(0,0,0,0.5)';
  modal.style.display = 'flex';
  modal.style.alignItems = 'center';
  modal.style.justifyContent = 'center';
  modal.style.zIndex = '1000';

  const box = document.createElement('div');
  box.style.background = '#fff';
  box.style.padding = '20px';
  box.style.borderRadius = '8px';
  box.style.minWidth = '700px';
  box.style.maxHeight = '80vh';
  box.style.overflow = 'auto';
  box.style.boxShadow = '0 4px 20px rgba(0,0,0,0.3)';

  const title = document.createElement('h3');
  title.textContent = 'Таблица организаций (ГМУ)';
  title.style.marginTop = '0';
  box.appendChild(title);

  const table = document.createElement('table');
  table.className = 'table';
  table.innerHTML =
    '<thead><tr><th>Ключ</th><th>Полное наименование</th><th>ИНН</th><th>КПП</th><th>ОГРН</th><th>Адрес</th><th>Действие</th></tr></thead>' +
    '<tbody></tbody>';
  const tbody = table.querySelector('tbody');

  (async () => {
    const all = await storeGet('gmu');
    const keys = Object.keys(all).sort();
    keys.forEach(k => {
      const it = all[k];
      const tr = document.createElement('tr');
      tr.innerHTML =
        '<td>' + escapeHtml(k) + '</td>' +
        '<td>' + escapeHtml(it.fullName || it.shortName || '') + '</td>' +
        '<td>' + escapeHtml(it.inn) + '</td>' +
        '<td>' + escapeHtml(it.kpp) + '</td>' +
        '<td>' + escapeHtml(it.ogrn) + '</td>' +
        '<td>' + escapeHtml(it.address) + '</td>' +
        '<td><button class="btn-ghost load-row" data-key="' + escapeHtml(k) + '">Загрузить</button></td>';
      tbody.appendChild(tr);
    });
    tbody.querySelectorAll('.load-row').forEach(btn => {
      btn.addEventListener('click', () => {
        els.key.value = btn.dataset.key;
        doLoad();
        modal.remove();
      });
    });
  })();

  const close = document.createElement('button');
  close.textContent = 'Закрыть';
  close.className = 'btn-primary';
  close.style.marginTop = '12px';
  close.style.float = 'right';
  close.addEventListener('click', () => modal.remove());

  box.appendChild(table);
  box.appendChild(close);
  modal.appendChild(box);
  document.body.appendChild(modal);
}

// ===== УДАЛЕНИЕ (как delete_organization в десктопе) =====
async function doDelete() {
  const key = els.key.value.trim();
  if (!key) { setHint('Введите ключ для удаления.'); return; }
  const all = await storeGet('gmu');
  if (!all[key]) { setHint('Ключ "' + key + '" не найден.'); return; }
  if (!confirm('Удалить организацию с ключом "' + key + '"?')) return;
  await storeRemove('gmu', key);
  els.key.value = '';
  els.result.innerHTML = '';
  currentData = null;
  currentKey = null;
  setHint('Удалено.');
}

// ===== ЭКСПОРТ В EXCEL (CSV) =====
function doExport() {
  (async () => {
    const all = await storeGet('gmu');
    const keys = Object.keys(all);
    if (!keys.length) { setHint('База пуста.'); return; }
    const rows = keys.map(k => {
      const it = all[k];
      const ls = buildLs(it.regNum);
      const ls80 = buildLs80(it.regNum);
      return [
        k, it.fullName, it.shortName, it.inn, it.kpp, it.ogrn,
        it.regNum, it.orgType, it.address, ls, FIXED_BIC, FIXED_RS,
        ls80,
        it.chief, it.founder
      ];
    });
    const csv = ['Ключ,Полное наименование,Краткое наименование,ИНН,КПП,ОГРН,Реестровый номер,Тип организации,Адрес,Л/С (счёт 20),БИК,Р/С,Счёт 80,Руководитель,Учредитель',
      ...rows.map(r => r.map(v => '"' + String(v == null ? '' : v).replace(/"/g, '""') + '"').join(','))].join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'gmu_organizations.csv';
    a.click();
    URL.revokeObjectURL(url);
    setHint('Экспорт завершён.');
  })();
}

// ===== ЭКСПОРТ В JSON (для обновления исходного data/gmu.json) =====
function doExportJson() {
  (async () => {
    const all = await storeGet('gmu');
    const keys = Object.keys(all);
    if (!keys.length) { setHint('База пуста.'); return; }
    const out = {};
    keys.forEach(k => {
      const it = all[k];
      out[k] = {
        initiator: it.initiator || { fullName: it.fullName || '', inn: it.inn || '', kpp: it.kpp || '', regNum: it.regNum || '' },
        main: it.main || { shortName: it.shortName || '', ogrn: it.ogrn || '', orgType: it.orgType || '', address: it.address || '' },
        other: it.other || { chief: it.chief ? [{ lastName: it.chief, firstName: '', middleName: '', position: '' }] : [], founder: it.founder ? [{ fullName: it.founder }] : [] }
      };
    });
    const blob = new Blob([JSON.stringify(out, null, 2)], { type: 'application/json;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'gmu.json';
    a.click();
    URL.revokeObjectURL(url);
    setHint('Экспорт в gmu.json завершён.');
  })();
}

// ===== ПЕРЕИМПОРТ ИЗ JSON =====
async function doReimport() {
  if (!confirm('Переимпортировать базу из JSON? Текущие сохранённые записи будут заменены.')) return;
  setHint('Переимпорт из JSON...');
  try {
    await storeSet('gmu', {});
    await ensureImported('gmu');
    await loadList();
    setHint('Переимпорт завершён.');
  } catch (e) {
    setHint('Ошибка переимпорта: ' + e.message);
    console.error(e);
  }
}

// ===== СОБЫТИЯ =====
function bindEvents() {
  els.btnSearch.addEventListener('click', doSearch);
  els.inn.addEventListener('keydown', e => { if (e.key === 'Enter') doSearch(); });
  els.kpp.addEventListener('keydown', e => { if (e.key === 'Enter') doSearch(); });

  els.btnSave.addEventListener('click', doSave);
  els.btnLoad.addEventListener('click', doLoad);
  els.btnUpdate.addEventListener('click', doUpdate);
  els.btnTable.addEventListener('click', doShowTable);
  els.btnDelete.addEventListener('click', doDelete);
  els.btnExport.addEventListener('click', doExport);
  els.btnReimport.addEventListener('click', doReimport);
  els.btnExportJson.addEventListener('click', doExportJson);
}

function setHint(msg) {
  els.hint.textContent = msg;
}

// ===== СТАРТ =====
document.addEventListener('DOMContentLoaded', async () => {
  cacheEls();
  bindEvents();
  try {
    await ensureImported('gmu');
  } catch (e) {
    setHint('Ошибка импорта базы из JSON: ' + e.message);
    console.error(e);
  }
  (async () => {
    const all = await storeGet('gmu');
    els.footer.textContent = 'Записей в базе: ' + Object.keys(all).length;
  })();
});
