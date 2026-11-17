/* EduShare front-end behaviour: toasts, dialogs, navigation, filters, PWA. */
(() => {
  'use strict';
  const $ = (selector, scope = document) => scope.querySelector(selector);
  const $$ = (selector, scope = document) => Array.from(scope.querySelectorAll(selector));
  const csrfToken = () => $('meta[name="csrf-token"]')?.content || '';

  function showToast(message, type = 'info') {
    const container = $('#toast-container');
    if (!container) return;
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.setAttribute('role', 'alert');
    toast.innerHTML = '<i class="bi bi-info-circle"></i><span></span>' +
      '<button type="button" class="toast-close" aria-label="Dismiss">&times;</button>';
    $('span', toast).textContent = message;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 5000);
    $('.toast-close', toast)?.addEventListener('click', () => toast.remove());
  }

  // Auto-dismiss server-rendered flash toasts.
  $$('[data-toast]').forEach((toast) => {
    $('.toast-close', toast)?.addEventListener('click', () => toast.remove());
    setTimeout(() => {
      toast.style.transition = 'opacity .3s';
      toast.style.opacity = '0';
      setTimeout(() => toast.remove(), 300);
    }, 6000);
  });

  // Confirmation dialog for destructive actions.
  const modal = $('#confirm-modal');
  let pendingForm = null;
  $$('form[data-confirm]').forEach((form) => {
    form.addEventListener('submit', (event) => {
      if (form.dataset.confirmed === '1') return;
      event.preventDefault();
      pendingForm = form;
      $('#confirm-message').textContent = form.dataset.confirm;
      modal.hidden = false;
      $('#confirm-ok')?.focus();
    });
  });
  $('#confirm-cancel')?.addEventListener('click', () => { modal.hidden = true; pendingForm = null; });
  $('#confirm-ok')?.addEventListener('click', () => {
    if (pendingForm) {
      pendingForm.dataset.confirmed = '1';
      pendingForm.submit();
    }
    modal.hidden = true;
  });
  modal?.addEventListener('click', (event) => {
    if (event.target === modal) { modal.hidden = true; pendingForm = null; }
  });

  // User dropdown.
  const menuButton = $('#user-menu-btn');
  const dropdown = $('#user-dropdown');
  menuButton?.addEventListener('click', () => {
    dropdown.hidden = !dropdown.hidden;
    menuButton.setAttribute('aria-expanded', String(!dropdown.hidden));
  });
  document.addEventListener('click', (event) => {
    if (dropdown && !dropdown.hidden && !event.target.closest('.user-menu')) {
      dropdown.hidden = true;
      menuButton?.setAttribute('aria-expanded', 'false');
    }
  });

  // Mobile filter drawer.
  $$('[data-filter-toggle]').forEach((button) => button.addEventListener('click', () => {
    const drawer = $('#filter-drawer');
    if (drawer) drawer.classList.add('open');
  }));
  $$('[data-filter-close]').forEach((button) => button.addEventListener('click', () => {
    const drawer = $('#filter-drawer');
    if (drawer) drawer.classList.remove('open');
  }));

  // Form tabs for exchange / donation / library pages.
  $$('[data-tabs]').forEach((group) => {
    $$('[data-tab]', group).forEach((tab) => tab.addEventListener('click', () => {
      $$('[data-tab]', group).forEach((item) => item.classList.remove('active'));
      tab.classList.add('active');
      const target = tab.dataset.tab;
      $$('[data-tab-panel]').forEach((panel) => { panel.hidden = panel.dataset.tabPanel !== target; });
      history.replaceState(null, '', '#' + target);
    }));
  });
  if (location.hash) {
    const tab = $(`[data-tab="${location.hash.slice(1)}"]`);
    tab?.click();
  }

  // Auto-submit select filters.
  $$('[data-auto-submit]').forEach((field) => field.addEventListener('change', () => {
    field.closest('form')?.submit();
  }));

  // Optional geolocation, only on explicit user action.
  $$('[data-geolocate]').forEach((button) => button.addEventListener('click', () => {
    if (!navigator.geolocation) { showToast('Geolocation is not supported on this device.', 'warning'); return; }
    button.disabled = true;
    navigator.geolocation.getCurrentPosition((position) => {
      const form = button.closest('form');
      const lat = $('input[name="latitude"]', form);
      const lon = $('input[name="longitude"]', form);
      const place = $('input[name="location"]', form);
      if (lat) lat.value = position.coords.latitude.toFixed(6);
      if (lon) lon.value = position.coords.longitude.toFixed(6);
      if (place && !place.value.trim()) place.value = 'Current location';
      showToast('Location added. You can edit the place name before saving.', 'success');
      button.disabled = false;
    }, () => {
      showToast('Location permission was not granted. You can type your area instead.', 'warning');
      button.disabled = false;
    }, { timeout: 10000 });
  }));

  // Image preview for multi-image upload fields.
  $$('[data-image-preview] input[type="file"]').forEach((input) => input.addEventListener('change', () => {
    const preview = input.closest('[data-image-preview]').querySelector('.image-preview-row');
    if (!preview) return;
    preview.innerHTML = '';
    Array.from(input.files || []).forEach((file) => {
      if (!file.type.startsWith('image/')) return;
      const img = document.createElement('img');
      img.src = URL.createObjectURL(file);
      img.alt = file.name;
      img.className = 'thumb';
      preview.appendChild(img);
    });
  }));

  // Gallery thumbnails.
  $$('.thumb[data-image-url]').forEach((thumb) => thumb.addEventListener('click', () => {
    const main = $('#main-image');
    if (main) main.src = thumb.dataset.imageUrl;
    $$('.thumb[data-image-url]').forEach((item) => item.classList.remove('active'));
    thumb.classList.add('active');
  }));

  // Mark a notification read when opened inline.
  $$('[data-mark-read]').forEach((link) => link.addEventListener('click', async () => {
    try {
      await fetch(`/notifications/${link.dataset.markRead}/read`, {
        method: 'POST',
        headers: { 'X-CSRFToken': csrfToken() }
      });
      link.closest('.notification-item')?.classList.remove('unread');
    } catch (_) { /* navigation still proceeds */ }
  }));

  $('[data-reload-page]')?.addEventListener('click', () => location.reload());

  // Loading state for explicitly marked forms.
  $$('form[data-loading]').forEach((form) => form.addEventListener('submit', () => {
    $('#loading-overlay')?.classList.add('show');
  }));

  // PWA installation prompt.
  let deferredInstallPrompt = null;
  window.addEventListener('beforeinstallprompt', (event) => {
    event.preventDefault();
    deferredInstallPrompt = event;
    const button = $('#install-btn');
    if (button) button.hidden = false;
  });
  $('#install-btn')?.addEventListener('click', async () => {
    if (!deferredInstallPrompt) return;
    deferredInstallPrompt.prompt();
    await deferredInstallPrompt.userChoice;
    deferredInstallPrompt = null;
    $('#install-btn').hidden = true;
  });
  window.addEventListener('appinstalled', () => showToast('EduShare installed successfully!', 'success'));

  // Register the service worker on HTTPS/localhost only.
  if ('serviceWorker' in navigator && (location.protocol === 'https:' || ['localhost', '127.0.0.1'].includes(location.hostname))) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('/service-worker.js').catch(() => {});
    });
  }
})();
