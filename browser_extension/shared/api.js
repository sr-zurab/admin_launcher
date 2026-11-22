/**
 * AdminLauncher — Общий модуль API и хранилища
 * Используется всеми тремя приложениями (ГМУ, Бюджет, Налог)
 */

const API_BASE = {
  GMU: 'https://bus.gov.ru/public-rest/api/7710568760-Generalinformation',
  BUDGET: 'https://budget.gov.ru/epbs/registry/ubpandnubp/data'
};

const STORAGE_KEYS = {
  gmu: 'gmu',
  budget: 'budget'
};

const BLOCKS = 'info,authorities,heads,facialAccounts,accountfk,foAccounts,ksAccounts,contacts,activities,nonParticipantPermissions,participantPermissions,procurementPermissions,acceptAuths,successions';

// ===== ХРАНИЛИЩЕ (JSON как в десктопе) =====
async function storeGet(tab) {
  const key = STORAGE_KEYS[tab];
  const res = await chrome.storage.local.get(key);
  return res[key] || {};
}

async function storeSet(tab, data) {
  const key = STORAGE_KEYS[tab];
  await chrome.storage.local.set({ [key]: data });
}

async function storeRemove(tab, keyName) {
  const storageKey = STORAGE_KEYS[tab];
  const all = await storeGet(tab);
  delete all[keyName];
  await storeSet(tab, all);
}

// ===== API ПОИСК (через background proxy для обхода CORS, с fallback на прямой fetch) =====
async function apiFetch(url) {
  let bgErr = null;
  // Пробуем через background service worker
  try {
    const resp = await chrome.runtime.sendMessage({ type: 'FETCH', url, options: { method: 'GET' } });
    if (resp.ok) return resp.data;
    bgErr = new Error(resp.error || `HTTP ${resp.status}`);
  } catch (err) {
    bgErr = err;
  }
  // Fallback: прямой fetch (если CORS позволяет)
  try {
    const response = await fetch(url, {
      method: 'GET',
      mode: 'cors',
      headers: {
        'User-Agent': 'Mozilla/5.0',
        'Accept': 'application/json'
      }
    });
    if (response.ok) {
      const ct = response.headers.get('content-type') || '';
      if (ct.includes('application/json')) return await response.json();
      return await response.text();
    }
    throw new Error(`HTTP ${response.status}`);
  } catch (fetchErr) {
    throw new Error('Не удалось подключиться к серверу расширения: ' + (bgErr ? bgErr.message : 'unknown') + '; прямой fetch: ' + fetchErr.message);
  }
}

async function searchGmu(inn, kpp) {
  const params = new URLSearchParams({ inn });
  if (kpp) params.append('kpp', kpp);
  const url = `${API_BASE.GMU}?${params}`;
  const data = await apiFetch(url);

  const org = data.pagedContent?.content?.[0]?.body?.position;
  if (!org) return null;

  const initiator = org.initiator || {};
  const main = org.main || {};
  const other = org.other || {};
  const addr = (main.complexAddress && main.complexAddress.address) || {};
  const chief = (other.chief && other.chief[0]) || {};
  const founder = (other.founder && other.founder[0]) || {};

  return {
    source: 'gmu',
    key: initiator.fullName || inn,
    inn: initiator.inn || '',
    kpp: initiator.kpp || '',
    ogrn: main.ogrn || '',
    fullName: initiator.fullName || '',
    shortName: main.shortName || '',
    regNum: initiator.regNum || '',
    orgType: main.orgType || '',
    address: [addr.zip, addr.subject && addr.subject.name, addr.city && addr.city.name, addr.street && addr.street.name, addr.building].filter(Boolean).join(', '),
    classifiers: main.classifier || {},
    chief: chief.lastName ? [chief.lastName, chief.firstName, chief.middleName].filter(Boolean).join(' ') + (chief.position ? ' (' + chief.position + ')' : '') : '',
    founder: founder.fullName || '',
    initiator: initiator,
    main: main,
    other: other,
    raw: org
  };
}

async function searchBudget(inn) {
  const params = new URLSearchParams({ blocks: BLOCKS, pageSize: '100', filterinn: inn });
  const url = `${API_BASE.BUDGET}?${params}`;
  const data = await apiFetch(url);

  const list = data.data || (data.result && data.result) || (Array.isArray(data) ? data : []);
  if (!list || !list.length) return null;

  const source = list[0];
  const info = source.info || source;

  return {
    source: 'budget',
    key: info.fullName || info.shortName || inn,
    inn: info.inn || '',
    kpp: info.kpp || '',
    ogrn: info.ogrn || '',
    fullName: info.fullName || '',
    shortName: info.shortName || '',
    regNum: info.regNum || info.code || '',
    orgType: info.orgTypeName || '',
    address: [info.postIndex, info.regionName, info.areaName, info.streetName, info.house].filter(Boolean).join(', '),
    classifiers: {},
    chief: info.fio || '',
    founder: info.nameDocs || '',
    raw: source
  };
}

// ===== ИМПОРТ ИЗ JSON ДЕСКТОПА =====
const DESKTOP_JSON_URLS = {
  gmu: 'data/gmu.json',
  budget: 'data/budget.json'
};

async function fetchJsonUrl(tab) {
  const url = DESKTOP_JSON_URLS[tab];
  let finalUrl = url;
  try { finalUrl = chrome.runtime.getURL(url); } catch (e) { /* ignore */ }
  console.log('[AdminLauncher] fetchJsonUrl(' + tab + '):', finalUrl);
  const resp = await fetch(finalUrl);
  if (!resp.ok) throw new Error('HTTP ' + resp.status + ' при загрузке ' + finalUrl);
  return resp.json();
}

async function importDesktopJson(tab) {
  console.log('[AdminLauncher] importDesktopJson(' + tab + ') start');
  const raw = await fetchJsonUrl(tab);
  console.log('[AdminLauncher] importDesktopJson(' + tab + '): загружено записей из файла = ' + Object.keys(raw).length);
  let count = 0;
  const all = await storeGet(tab);

  if (tab === 'gmu') {
    for (const [key, rec] of Object.entries(raw)) {
      const init = rec.initiator || {};
      const main = rec.main || {};
      const other = rec.other || {};
      const addr = (main.complexAddress && main.complexAddress.address) || {};
      const chief = (other.chief && other.chief[0]) || {};
      const founder = (other.founder && other.founder[0]) || {};
      all[key] = {
        source: 'gmu',
        key: key,
        inn: init.inn || '',
        kpp: init.kpp || '',
        ogrn: main.ogrn || '',
        fullName: init.fullName || '',
        shortName: main.shortName || '',
        regNum: init.regNum || '',
        orgType: main.orgType || '',
        address: [addr.zip, addr.subject && addr.subject.name, addr.city && addr.city.name, addr.street && addr.street.name, addr.building].filter(Boolean).join(', '),
        classifiers: main.classifier || {},
        chief: chief.lastName ? [chief.lastName, chief.firstName, chief.middleName].filter(Boolean).join(' ') + (chief.position ? ' (' + chief.position + ')' : '') : '',
        founder: founder.fullName || ''
      };
      count++;
    }
  } else if (tab === 'budget') {
    for (const [key, rec] of Object.entries(raw)) {
      const info = rec.INFO || rec.info || rec || {};
      const heads = Array.isArray(rec.HEADS) ? rec.HEADS : (rec.HEADS ? [rec.HEADS] : []);
      const facs = Array.isArray(rec.facialTerritorialAccounts) ? rec.facialTerritorialAccounts : (rec.facialTerritorialAccounts ? [rec.facialTerritorialAccounts] : []);
      const kss = Array.isArray(rec.ksAccounts) ? rec.ksAccounts : (rec.ksAccounts ? [rec.ksAccounts] : []);
      const auths = Array.isArray(rec.authorities) ? rec.authorities : (rec.authorities ? [rec.authorities] : []);
      all[key] = {
        source: 'budget',
        key: key,
        inn: info.inn || '',
        kpp: info.kpp || '',
        ogrn: info.ogrn || '',
        fullName: info.fullName || '',
        shortName: info.shortName || '',
        regNum: info.regNum || info.code || '',
        orgType: info.orgTypeName || '',
        address: [info.postIndex, info.regionName, info.areaName, info.streetName, info.house].filter(Boolean).join(', '),
        chief: info.fio || '',
        founder: info.nameDocs || '',
        INFO: info,
        HEADS: heads,
        facialTerritorialAccounts: facs,
        ksAccounts: kss,
        authorities: auths,
        raw_api: { info: info },
        raw_links: rec.raw_links || []
      };
      count++;
    }
  }

  await storeSet(tab, all);
  console.log('[AdminLauncher] importDesktopJson(' + tab + '): импортировано ' + count + ' записей, всего в базе = ' + Object.keys(all).length);
  return count;
}

async function ensureImported(tab) {
  const items = await storeGet(tab);
  console.log('[AdminLauncher] ensureImported(' + tab + '): текущих записей в storage = ' + Object.keys(items).length);
  if (Object.keys(items).length > 0) {
    console.log('[AdminLauncher] Импорт пропущен — база уже не пуста');
    return 0;
  }
  try {
    const count = await importDesktopJson(tab);
    console.log('[AdminLauncher] Импорт завершён для ' + tab + ': ' + count + ' записей');
    return count;
  } catch (e) {
    console.error('[AdminLauncher] ОШИБКА импорта из JSON для ' + tab + ':', e);
    throw e;
  }
}

// ===== УТИЛИТЫ =====
function escapeHtml(s) {
  if (s == null) return '';
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
