/**
 * AdminLauncher Popup — Лаунчер приложений
 * Каждое приложение открывается в отдельной вкладке браузера
 */

const APP_URLS = {
  gmu: 'apps/gmu.html',
  budget: 'apps/budget.html'
};

const SITE_URLS = {
  gmu: 'https://bus.gov.ru/',
  budget: 'https://budget.gov.ru/'
};

document.addEventListener('DOMContentLoaded', () => {
  console.log('[AdminLauncher] Popup загружен');

  document.querySelectorAll('.app-btn').forEach(card => {
    card.addEventListener('click', async (e) => {
      e.preventDefault();
      const app = card.dataset.app;
      console.log('[AdminLauncher] Клик на кнопку:', app);
      if (!app) return;

      try {
        const url = chrome.runtime.getURL(APP_URLS[app]);
        console.log('[AdminLauncher] Открываем:', url);
        await chrome.tabs.create({ url });
      } catch (err) {
        console.error('[AdminLauncher] Ошибка открытия приложения:', err);
      }

      window.close();
    });
  });
});
