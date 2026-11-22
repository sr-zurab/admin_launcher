/**
 * AdminLauncher Background Service Worker
 * - CORS прокси для API запросов
 * - Открытие страниц приложений в новых вкладках
 */

async function handleFetch(message) {
  const { url, options } = message;
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 30000);

    const response = await fetch(url, {
      ...options,
      signal: controller.signal,
      credentials: 'omit',
      mode: 'cors',
      headers: {
        ...(options.headers || {}),
        'User-Agent': 'Mozilla/5.0',
        'Accept': 'application/json'
      }
    });

    clearTimeout(timeoutId);

    const contentType = response.headers.get('content-type') || '';
    let data;
    if (contentType.includes('application/json')) {
      data = await response.json();
    } else {
      data = await response.text();
    }

    return { ok: response.ok, status: response.status, data };
  } catch (err) {
    if (err.name === 'AbortError') return { ok: false, status: 408, error: 'Timeout' };
    return { ok: false, status: 0, error: err.message };
  }
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  const { type } = message;

  const safeSend = (data) => {
    try { sendResponse(data); } catch {}
  };

  switch (type) {
    case 'FETCH':
      handleFetch(message).then(safeSend).catch(() => safeSend({ ok: false, status: 0, error: 'Fetch failed' }));
      return true;

    case 'OPEN_APP':
      chrome.tabs.create({ url: message.url }).then(() => safeSend({ ok: true })).catch(() => safeSend({ ok: false }));
      return true;

    case 'OPEN_SITE':
      chrome.tabs.create({ url: message.url }).then(() => safeSend({ ok: true })).catch(() => safeSend({ ok: false }));
      return true;
  }
});

chrome.runtime.onInstalled.addListener(() => {
  console.log('AdminLauncher background started');
});

console.log('AdminLauncher background SW started');
