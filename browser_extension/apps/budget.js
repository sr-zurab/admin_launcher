/**
 * AdminLauncher — Бюджет (budget.gov.ru)
 * Повторяет GUI десктопа budget.py: верхняя строка поиска, строка ключа,
 * сплиттер со списком сохранённых слева, динамические вкладки реквизитов справа.
 */

const SITE_URL = 'https://budget.gov.ru/';

let lastSource = null;
let lastLinkResponses = [];
let requestedInn = null;

const GLOBAL_HIDDEN_KEYS = ['refopenufkcode','refsrvufkcode','contourtypecode','controlnum','cpzcode',
  'firstregguid','lastregguid','reforfkcode','updatenum','isexcluded','isogv',
  'isobosob','isreorg','isuch','egrulnotincluded','citytype','establishmentkindcode',
  'streettype','updatereason','founderkindcode','guid'];

const LABELS_RU = {
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
};

const els = {};

function cacheEls() {
  els.inputQ = document.getElementById('input-q');
  els.btnInn = document.getElementById('btn-inn');
  els.btnName = document.getElementById('btn-name');
  els.btnSaveFound = document.getElementById('btn-save-found');
  els.btnShowRaw = document.getElementById('btn-show-raw');
  els.btnAddManual = document.getElementById('btn-add-manual');
  els.keyInput = document.getElementById('key-input');
  els.btnLoadByKey = document.getElementById('btn-load-by-key');
  els.listWidget = document.getElementById('list-widget');
  els.listSearch = document.getElementById('list-search');
  els.btnOpen = document.getElementById('btn-open');
  els.btnDelete = document.getElementById('btn-delete');
  els.btnExport = document.getElementById('btn-export');
  els.btnRefreshRecord = document.getElementById('btn-refresh-record');
  els.btnReimport = document.getElementById('btn-reimport');
  els.btnExportJson = document.getElementById('btn-export-json');
  els.tabContainer = document.getElementById('tab-container');
  els.hint = document.getElementById('hint');
  els.footer = document.getElementById('footer-status');
}

// ===== СПИСОК СОХРАНЁННЫХ =====
function refreshList(filter) {
  els.listWidget.innerHTML = '';
  (async () => {
    const all = await storeGet('budget');
    const keys = Object.keys(all).sort();
    console.log('[AdminLauncher] budget list: ' + keys.length + ' записей');
    keys.forEach(k => {
      if (filter && k.toLowerCase() !== filter.toLowerCase()) return;
      const li = document.createElement('li');
      li.className = 'result-item';
      li.textContent = k;
      li.addEventListener('click', () => {
        document.querySelectorAll('#list-widget .result-item').forEach(x => x.classList.remove('selected'));
        li.classList.add('selected');
        els.keyInput.value = k;
        loadAndShow(k);
      });
      els.listWidget.appendChild(li);
    });
  })();
}

async function loadAndShow(key) {
  console.log('[AdminLauncher] loadAndShow(' + key + ')');
  const all = await storeGet('budget');
  const rec = all[key];
  if (!rec) {
    setHint('Запись не найдена: ' + key);
    return;
  }
  const source = normalizeSavedRecord(rec);
  console.log('[AdminLauncher] source keys:', Object.keys(source));
  showRecordTabs(source, rec.raw_links || []);
}

// ===== ПОИСК ПО ИНН / НАИМЕНОВАНИЮ =====
async function searchByInn() {
  const q = els.inputQ.value.trim();
  if (!q) { setHint('Введите ИНН'); return; }
  requestedInn = q;
  await runSearch(q, true);
}

async function searchByName() {
  const q = els.inputQ.value.trim();
  if (!q) { setHint('Введите наименование'); return; }
  requestedInn = null;
  await runSearch(q, false);
}

async function runSearch(q, byInn) {
  setHint('Поиск в API...');
  try {
    const result = await searchBudget(q);
    if (!result) {
      setHint('Организация не найдена.');
      clearTabs();
      return;
    }
    lastSource = result.raw;
    lastLinkResponses = [];
    showRecordTabs(result.raw, []);
    setHint('Результат показан. Нажмите "Сохранить" чтобы записать в базу.');
  } catch (err) {
    setHint('Ошибка API: ' + err.message);
    console.error(err);
  }
}

// ===== СОХРАНЕНИЕ ПОСЛЕДНЕГО =====
async function saveLast() {
  if (!lastSource) {
    setHint('Нет результата для сохранения.');
    return;
  }
  const key = prompt('Введите ключ для сохранения:');
  if (key === null || !key.trim()) return;
  const all = await storeGet('budget');
  if (all[key]) {
    if (!confirm('Ключ "' + key + '" уже есть. Перезаписать?')) return;
  }

  const mapped = { INFO: {}, authorities: [], HEADS: [], facialTerritorialAccounts: [], ksAccounts: [], extra: {} };
  const infoSrc = getCI(lastSource, 'info') || lastSource;
  if (typeof infoSrc === 'object' && infoSrc) {
    for (const [k, v] of Object.entries(infoSrc)) {
      if (v != null && (typeof v !== 'string' || v.trim() !== '') && !GLOBAL_HIDDEN_KEYS.includes(k.toLowerCase())) {
        mapped.INFO[k] = v;
      }
    }
  }
  const auths = getCI(lastSource, 'authorities') || getCI(lastSource, 'authority') || [];
  if (typeof auths === 'object' && !Array.isArray(auths)) mapped.authorities = [auths];
  else mapped.authorities = auths;
  const heads = getCI(lastSource, 'heads') || getCI(lastSource, 'HEADS') || [];
  if (typeof heads === 'object' && !Array.isArray(heads)) mapped.HEADS = [heads];
  else mapped.HEADS = heads;
  const facs = findFacialTerritorialBlock(lastSource, lastLinkResponses);
  facs.forEach(f => {
    const rec = {};
    for (const [k, v] of Object.entries(f)) {
      if (v != null && (typeof v !== 'string' || v.trim() !== '') && !GLOBAL_HIDDEN_KEYS.includes(k.toLowerCase())) rec[k] = v;
    }
    mapped.facialTerritorialAccounts.push(rec);
  });
  const kss = getCI(lastSource, 'ksAccounts') || getCI(lastSource, 'ksaccounts') || [];
  if (typeof kss === 'object' && !Array.isArray(kss)) mapped.ksAccounts = [kss];
  else mapped.ksAccounts = kss;
  if (typeof lastSource === 'object' && lastSource) {
    for (const [k, v] of Object.entries(lastSource)) {
      if (['info','authorities','heads','facialaccounts','ksaccounts'].includes(k.toLowerCase())) continue;
      mapped.extra[k] = v;
    }
  }
  mapped.raw_api = lastSource;
  if (lastLinkResponses.length) mapped.raw_links = lastLinkResponses;

  all[key] = mapped;
  await storeSet('budget', all);
  refreshList();
  setHint('Сохранено под ключом "' + key + '".');
}

// ===== RAW ОТВЕТ =====
function showRaw() {
  const parts = [];
  if (lastSource) parts.push('MAIN:\n' + JSON.stringify(lastSource, null, 2));
  if (lastLinkResponses.length) parts.push('LINKS:\n' + JSON.stringify(lastLinkResponses, null, 2));
  if (!parts.length) { setHint('Нет сохранённых raw ответов.'); return; }
  const modal = createModal('Raw API responses', '<pre style="white-space:pre-wrap;font-family:ui-monospace,monospace;font-size:11px;">' + escapeHtml(parts.join('\n\n')) + '</pre>');
  document.body.appendChild(modal);
}

// ===== ДОБАВИТЬ В РУЧНУЮ =====
function addManual() {
  const key = prompt('Введите ключ для пустой записи:');
  if (key === null || !key.trim()) return;
  (async () => {
    const all = await storeGet('budget');
    if (all[key]) { if (!confirm('Перезаписать "' + key + '"?')) return; }
    all[key] = { INFO: {}, authorities: [], HEADS: [], facialTerritorialAccounts: [], ksAccounts: [], extra: {}, key: key };
    await storeSet('budget', all);
    refreshList();
    setHint('Запись "' + key + '" добавлена.');
  })();
}

// ===== ЗАГРУЗКА ПО КЛЮЧУ =====
function loadByKey() {
  const key = els.keyInput.value.trim();
  if (!key) { setHint('Введите ключ'); return; }
  console.log('[AdminLauncher] loadByKey:', key);
  loadAndShow(key);
}

// ===== УДАЛЕНИЕ =====
async function deleteSelected() {
  const li = els.listWidget.querySelector('.result-item.selected');
  if (!li) { setHint('Выберите запись'); return; }
  const key = li.textContent;
  if (!confirm('Удалить "' + key + '"?')) return;
  await storeRemove('budget', key);
  refreshList();
  clearTabs();
  setHint('Удалено.');
}

// ===== ЭКСПОРТ =====
function exportDb() {
  (async () => {
    const all = await storeGet('budget');
    const keys = Object.keys(all);
    if (!keys.length) { setHint('База пуста.'); return; }
    const lines = ['Ключ,Полное наименование,ИНН,КПП,ОГРН'];
    keys.forEach(k => {
      const it = all[k];
      const info = it.INFO || it.info || {};
      lines.push([k, info.fullName, info.inn, info.kpp, info.ogrn].map(v => '"' + String(v == null ? '' : v).replace(/"/g, '""') + '"').join(','));
    });
    const csv = lines.join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = 'budget_organizations.csv'; a.click();
    URL.revokeObjectURL(url);
    setHint('Экспорт завершён.');
  })();
}

// ===== ЭКСПОРТ В JSON (для обновления исходного data/budget.json) =====
function doExportJson() {
  (async () => {
    const all = await storeGet('budget');
    const keys = Object.keys(all);
    if (!keys.length) { setHint('База пуста.'); return; }
    const out = {};
    keys.forEach(k => {
      const it = all[k];
      out[k] = {
        INFO: it.INFO || {},
        HEADS: it.HEADS || [],
        facialTerritorialAccounts: it.facialTerritorialAccounts || [],
        ksAccounts: it.ksAccounts || [],
        authorities: it.authorities || [],
        extra: it.extra || {},
        raw_api: it.raw_api || null,
        raw_links: it.raw_links || []
      };
    });
    const blob = new Blob([JSON.stringify(out, null, 2)], { type: 'application/json;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'budget.json';
    a.click();
    URL.revokeObjectURL(url);
    setHint('Экспорт в budget.json завершён.');
  })();
}

// ===== ОБНОВЛЕНИЕ ЗАПИСИ =====
async function refreshSelected() {
  const li = els.listWidget.querySelector('.result-item.selected');
  if (!li) { setHint('Выберите запись'); return; }
  const key = li.textContent;
  const all = await storeGet('budget');
  const rec = all[key];
  if (!rec) return;
  const inn = (rec.INFO && rec.INFO.inn) || (rec.info && rec.info.inn);
  if (!inn) { setHint('Нет ИНН для обновления.'); return; }
  setHint('Обновление из API...');
  try {
    const result = await searchBudget(inn);
    if (!result) { setHint('Организация не найдена в API.'); return; }
    const raw = result.raw;
    const infoSrc = getCI(raw, 'info') || raw;
    const mapped = {
      INFO: {},
      HEADS: [],
      facialTerritorialAccounts: [],
      ksAccounts: [],
      authorities: [],
      extra: {},
      raw_api: raw
    };
    if (typeof infoSrc === 'object' && infoSrc) {
      for (const [k, v] of Object.entries(infoSrc)) {
        if (v != null && (typeof v !== 'string' || v.trim() !== '') && !GLOBAL_HIDDEN_KEYS.includes(k.toLowerCase())) {
          mapped.INFO[k] = v;
        }
      }
    }
    const heads = getCI(raw, 'heads') || getCI(raw, 'HEADS') || [];
    mapped.HEADS = Array.isArray(heads) ? heads : (heads ? [heads] : []);
    const facs = getCI(raw, 'facialAccounts') || getCI(raw, 'facialTerritorialAccounts') || [];
    mapped.facialTerritorialAccounts = Array.isArray(facs) ? facs : (facs ? [facs] : []);
    const kss = getCI(raw, 'ksAccounts') || getCI(raw, 'ksaccounts') || [];
    mapped.ksAccounts = Array.isArray(kss) ? kss : (kss ? [kss] : []);
    const auths = getCI(raw, 'authorities') || getCI(raw, 'authority') || [];
    mapped.authorities = Array.isArray(auths) ? auths : (auths ? [auths] : []);
    if (typeof raw === 'object' && raw) {
      for (const [k, v] of Object.entries(raw)) {
        if (['info','authorities','heads','facialaccounts','ksaccounts'].includes(k.toLowerCase())) continue;
        mapped.extra[k] = v;
      }
    }
    all[key] = mapped;
    await storeSet('budget', all);
    refreshList();
    loadAndShow(key);
    setHint('Запись "' + key + '" обновлена из API.');
  } catch (err) {
    setHint('Ошибка обновления: ' + err.message);
  }
}

// ===== ДИНАМИЧЕСКИЕ ВКЛАДКИ РЕКВИЗИТОВ =====
function showRecordTabs(source, linkResponses) {
  console.log('[AdminLauncher] showRecordTabs called');
  console.log('[AdminLauncher] source keys:', Object.keys(source));
  console.log('[AdminLauncher] source INFO keys:', source.info ? Object.keys(source.info) : 'no info');
  console.log('[AdminLauncher] source heads:', source.heads);
  console.log('[AdminLauncher] source facialAccounts:', source.facialAccounts);
  console.log('[AdminLauncher] source contacts:', source.contacts);
  console.log('[AdminLauncher] source activities:', source.activities);
  clearTabs();
  const tabs = document.createElement('div');
  tabs.className = 'tabs';

  const tabList = document.createElement('div');
  tabList.className = 'tab-list';

  const tabPanels = document.createElement('div');
  tabPanels.className = 'tab-panels';

  let activeSet = false;

  function addTab(title, itemsHtml, tabId) {
    const btn = document.createElement('button');
    btn.className = 'tab-btn';
    btn.textContent = title;
    const panel = document.createElement('div');
    panel.className = 'tab-panel';
    panel.style.display = activeSet ? 'none' : 'block';
    if (!activeSet) { btn.classList.add('active'); activeSet = true; }
    panel.innerHTML = itemsHtml;
    tabList.appendChild(btn);
    tabPanels.appendChild(panel);
    btn.addEventListener('click', () => {
      tabList.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      tabPanels.querySelectorAll('.tab-panel').forEach(p => { p.classList.remove('active'); p.style.display = 'none'; });
      btn.classList.add('active');
      panel.classList.add('active');
      panel.style.display = 'block';
    });
  }

  const info = sectionInfoData(source);
  if (info && Object.keys(info).length) {
    addTab('Информация', formatDictItems(info, 'Информация'), 'info');
    console.log('[AdminLauncher] вкладка Информация: ' + Object.keys(info).length + ' полей');
  } else {
    console.log('[AdminLauncher] вкладка Информация НЕ создана — info пустой:', info);
  }
  const heads = getCI(source, 'heads') || getCI(source, 'HEADS') || [];
  console.log('[AdminLauncher] heads: ' + (Array.isArray(heads) ? heads.length : typeof heads) + ' элементов');
  if (typeof heads === 'object' && !Array.isArray(heads)) heads = [heads];
  heads.forEach((h, i) => {
    if (typeof h === 'object' && h) {
      console.log('[AdminLauncher] Руководитель ' + i + ' ключи:', Object.keys(h));
      addTab('Руководитель' + (heads.length > 1 ? ' ' + (i+1) : ''), formatDictItems(h, 'Руководитель'), 'head' + i);
    }
  });
  const facs = findFacialTerritorialBlock(source, linkResponses);
  console.log('[AdminLauncher] facialAccounts: ' + (Array.isArray(facs) ? facs.length : typeof facs) + ' элементов');
  facs.forEach((f, i) => {
    if (typeof f === 'object' && f) {
      console.log('[AdminLauncher] Лицевой счёт ' + i + ' ключи:', Object.keys(f));
      addTab('Лицевой счёт ' + (i+1), formatDictItems(f, 'Лицевой счёт'), 'face' + i);
    }
  });
  const kss = getCI(source, 'ksAccounts') || getCI(source, 'ksaccounts') || [];
  console.log('[AdminLauncher] ksAccounts: ' + (Array.isArray(kss) ? kss.length : typeof kss) + ' элементов');
  if (typeof kss === 'object' && !Array.isArray(kss)) kss = [kss];
  kss.forEach((k, i) => {
    if (typeof k === 'object' && k) {
      console.log('[AdminLauncher] Казнач. счёт ' + i + ' ключи:', Object.keys(k));
      addTab('Казнач. счёт' + (kss.length > 1 ? ' ' + (i+1) : ''), formatDictItems(k, 'Казнач. счёт'), 'ks' + i);
    }
  });
  const contacts = getCI(source, 'contacts');
  console.log('[AdminLauncher] contacts: ' + (Array.isArray(contacts) ? contacts.length : typeof contacts) + ' элементов');
  if (contacts) {
    if (typeof contacts === 'object' && !Array.isArray(contacts)) contacts = [contacts];
    contacts.forEach((c, i) => {
      if (typeof c === 'object' && c) {
        console.log('[AdminLauncher] Контакты ' + i + ' ключи:', Object.keys(c));
        addTab('Контакты' + (contacts.length > 1 ? ' ' + (i+1) : ''), formatDictItems(c, 'Контакты'), 'contact' + i);
      }
    });
  }
  const activities = getCI(source, 'activities');
  console.log('[AdminLauncher] activities: ' + (Array.isArray(activities) ? activities.length : typeof activities) + ' элементов');
  if (activities) {
    if (typeof activities === 'object' && !Array.isArray(activities)) activities = [activities];
    activities.forEach((a, i) => {
      if (typeof a === 'object' && a) {
        console.log('[AdminLauncher] Деятельность ' + i + ' ключи:', Object.keys(a));
        addTab('Деятельность' + (activities.length > 1 ? ' ' + (i+1) : ''), formatDictItems(a, 'Деятельность'), 'activity' + i);
      }
    });
  }
  const founders = getCI(source, 'founders');
  console.log('[AdminLauncher] founders: ' + (Array.isArray(founders) ? founders.length : typeof founders) + ' элементов');
  if (founders) {
    if (typeof founders === 'object' && !Array.isArray(founders)) founders = [founders];
    founders.forEach((f, i) => {
      if (typeof f === 'object' && f) {
        console.log('[AdminLauncher] Учредитель ' + i + ' ключи:', Object.keys(f));
        addTab('Учредитель' + (founders.length > 1 ? ' ' + (i+1) : ''), formatDictItems(f, 'Учредитель'), 'founder' + i);
      }
    });
  }

  tabs.appendChild(tabList);
  tabs.appendChild(tabPanels);
  els.tabContainer.appendChild(tabs);
  console.log('[AdminLauncher] showRecordTabs done, tabContainer children:', els.tabContainer.children.length);
}

function clearTabs() {
  els.tabContainer.innerHTML = '';
}

// ---helpers---

function sectionInfoData(src) {
  const infoBlock = getCI(src, 'info') || src;
  if (typeof infoBlock === 'object' && infoBlock && Object.keys(infoBlock).length > 0) {
    return infoBlock;
  }
  return typeof src === 'object' && src ? src : {};
}

function normalizeSavedRecord(saved) {
  if (typeof saved !== 'object' || !saved) return saved;
  const apiLike = {};
  const info = saved.INFO || saved.info || {};
  apiLike.info = typeof info === 'object' ? { ...info } : {};
  apiLike.heads = Array.isArray(saved.HEADS) ? saved.HEADS : (saved.HEADS ? [saved.HEADS] : []);
  apiLike.facialAccounts = Array.isArray(saved.facialTerritorialAccounts) ? saved.facialTerritorialAccounts : (saved.facialTerritorialAccounts ? [saved.facialTerritorialAccounts] : []);
  apiLike.ksAccounts = Array.isArray(saved.ksAccounts) ? saved.ksAccounts : (saved.ksAccounts ? [saved.ksAccounts] : []);
  apiLike.authorities = Array.isArray(saved.authorities) ? saved.authorities : (saved.authorities ? [saved.authorities] : []);
  const extra = saved.extra || {};
  apiLike.contacts = saved.contacts || (typeof extra === 'object' && extra ? extra.contacts : undefined) || [];
  apiLike.activities = saved.activities || (typeof extra === 'object' && extra ? extra.activities : undefined) || [];
  if (typeof apiLike.contacts === 'object' && !Array.isArray(apiLike.contacts)) apiLike.contacts = [apiLike.contacts];
  if (typeof apiLike.activities === 'object' && !Array.isArray(apiLike.activities)) apiLike.activities = [apiLike.activities];
  if (typeof apiLike.authorities === 'object' && !Array.isArray(apiLike.authorities)) apiLike.authorities = [apiLike.authorities];
  return apiLike;
}

function getCI(obj, key) {
  if (!obj || typeof obj !== 'object') return undefined;
  if (obj[key] !== undefined) return obj[key];
  const lk = key.toLowerCase();
  for (const k of Object.keys(obj)) {
    if (k.toLowerCase() === lk) return obj[k];
  }
  return undefined;
}

function findFacialTerritorialBlock(source, linkResponses) {
  const facs = getCI(source, 'facialAccounts') || getCI(source, 'facialTerritorialAccounts') || [];
  return Array.isArray(facs) ? facs : (typeof facs === 'object' ? [facs] : []);
}

function formatDictItems(dict, tabName) {
  if (!dict || typeof dict !== 'object') {
    console.log('[AdminLauncher] formatDictItems(' + tabName + '): не объект');
    return '<div>Нет данных</div>';
  }
  const entries = Object.entries(dict).filter(([k]) => !GLOBAL_HIDDEN_KEYS.includes(k.toLowerCase()));
  console.log('[AdminLauncher] formatDictItems(' + tabName + '): ' + entries.length + ' полей после фильтрации');
  if (entries.length === 0) return '<div>Нет данных</div>';
  let html = '<table class="table">';
  for (const [k, v] of entries) {
    if (v == null) continue;
    const label = LABELS_RU[k] || k;
    let val = String(v);
    if (typeof v === 'object') val = JSON.stringify(v);
    html += '<tr><th style="width:220px">' + escapeHtml(label) + '</th><td>' + escapeHtml(val) + '</td></tr>';
  }
  html += '</table>';
  return html;
}

// ===== ПЕРЕИМПОРТ ИЗ JSON =====
async function doReimport() {
  if (!confirm('Переимпортировать базу из JSON? Текущие сохранённые записи будут заменены.')) return;
  setHint('Переимпорт из JSON...');
  try {
    await storeSet('budget', {});
    await ensureImported('budget');
    refreshList();
    clearTabs();
    setHint('Переимпорт завершён.');
  } catch (e) {
    setHint('Ошибка переимпорта: ' + e.message);
    console.error(e);
  }
}

// ===== СОБЫТИЯ =====
function bindEvents() {
  els.btnInn.addEventListener('click', searchByInn);
  els.btnName.addEventListener('click', searchByName);
  els.inputQ.addEventListener('keydown', e => { if (e.key === 'Enter') searchByInn(); });

  els.btnSaveFound.addEventListener('click', saveLast);
  els.btnShowRaw.addEventListener('click', showRaw);
  els.btnAddManual.addEventListener('click', addManual);

  els.btnLoadByKey.addEventListener('click', loadByKey);
  els.keyInput.addEventListener('keydown', e => { if (e.key === 'Enter') loadByKey(); });
  els.listSearch.addEventListener('input', e => refreshList(e.target.value));

  els.btnOpen.addEventListener('click', () => {
    const li = els.listWidget.querySelector('.result-item.selected');
    if (li) { els.keyInput.value = li.textContent; loadAndShow(li.textContent); }
  });
  els.btnDelete.addEventListener('click', deleteSelected);
  els.btnExport.addEventListener('click', exportDb);
  els.btnRefreshRecord.addEventListener('click', refreshSelected);
  els.btnReimport.addEventListener('click', doReimport);
  els.btnExportJson.addEventListener('click', doExportJson);
}

function setHint(msg) {
  els.hint.textContent = msg;
}

function createModal(title, contentHtml) {
  const m = document.createElement('div');
  m.style.position = 'fixed';
  m.style.top = '0'; m.style.left = '0';
  m.style.width = '100vw'; m.style.height = '100vh';
  m.style.background = 'rgba(0,0,0,0.5)';
  m.style.display = 'flex'; m.style.alignItems = 'center'; m.style.justifyContent = 'center';
  m.style.zIndex = '1000';
  const box = document.createElement('div');
  box.style.background = '#fff'; box.style.padding = '20px'; box.style.borderRadius = '8px';
  box.style.minWidth = '700px'; box.style.maxHeight = '80vh'; box.style.overflow = 'auto';
  box.style.boxShadow = '0 4px 20px rgba(0,0,0,0.3)';
  const t = document.createElement('h3'); t.textContent = title; t.style.marginTop = '0';
  box.appendChild(t);
  box.innerHTML += contentHtml;
  const btn = document.createElement('button');
  btn.textContent = 'Закрыть'; btn.className = 'btn-primary';
  btn.style.marginTop = '12px'; btn.style.float = 'right';
  btn.addEventListener('click', () => m.remove());
  box.appendChild(btn);
  m.appendChild(box);
  return m;
}

// ===== СТАРТ =====
document.addEventListener('DOMContentLoaded', async () => {
  console.log('[AdminLauncher] budget.js DOMContentLoaded');
  cacheEls();
  bindEvents();
  try {
    await ensureImported('budget');
  } catch (e) {
    setHint('Ошибка импорта базы из JSON: ' + e.message);
    console.error(e);
  }
  refreshList();
  els.footer.textContent = 'Готов';
});
