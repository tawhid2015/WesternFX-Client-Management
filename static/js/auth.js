/**
 * WesternFX Auth — Password Protection Overlay
 * ============================================
 * Full-page login overlay. No redirects. IP whitelisting.
 */

(function() {
  'use strict';

  let authChecked = false;

  // ── DOM Elements ──────────────────────────────────────
  function getEl(id) { return document.getElementById(id); }

  // ── Auth Check ────────────────────────────────────────
  async function checkAuth() {
    try {
      const res = await fetch('/api/auth-check', { method: 'POST' });
      const data = await res.json();
      if (data.success && data.authenticated) {
        hideOverlay();
        return true;
      }
    } catch (e) {
      // Network error — keep overlay up
    }
    showOverlay();
    return false;
  }

  // ── Show/Hide Overlay ─────────────────────────────────
  function showOverlay() {
    const overlay = getEl('auth-overlay');
    if (overlay) {
      overlay.style.display = 'flex';
    }
    // Prevent body scroll while overlay is up
    document.body.style.overflow = 'hidden';
  }

  function hideOverlay() {
    const overlay = getEl('auth-overlay');
    if (overlay) {
      overlay.style.display = 'none';
    }
    document.body.style.overflow = '';
    authChecked = true;
  }

  // ── Login ─────────────────────────────────────────────
  async function doLogin() {
    const input = getEl('auth-password');
    const errorDiv = getEl('auth-error');
    const btn = getEl('auth-submit');
    const password = (input.value || '').trim();

    if (!password) {
      showError('Please enter a password.');
      input.focus();
      return;
    }

    // Disable button during submit
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Checking...';
    hideError();

    try {
      const res = await fetch('/api/auth-login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password }),
      });
      const data = await res.json();

      if (data.success) {
        // Success — reload to load all data fresh
        hideOverlay();
        window.location.reload();
      } else {
        showError(data.error || 'Incorrect password. Please try again.');
        input.value = '';
        input.focus();
      }
    } catch (e) {
      showError('Network error. Please try again.');
    } finally {
      btn.disabled = false;
      btn.innerHTML = '<i class="fas fa-unlock"></i> Unlock';
    }
  }

  // ── Error Display ─────────────────────────────────────
  function showError(msg) {
    const errorDiv = getEl('auth-error');
    if (errorDiv) {
      errorDiv.textContent = msg;
      errorDiv.style.display = 'block';
      // Shake animation on the card
      const card = errorDiv.closest('div[style*="border-radius:12px"]');
      if (card) {
        card.style.animation = 'none';
        card.offsetHeight; // trigger reflow
        card.style.animation = 'authShake 0.4s ease-in-out';
      }
    }
  }

  function hideError() {
    const errorDiv = getEl('auth-error');
    if (errorDiv) {
      errorDiv.style.display = 'none';
      errorDiv.textContent = '';
    }
  }

  // ── Logout ────────────────────────────────────────────
  window.logout = async function logout() {
    try {
      await fetch('/api/auth-logout', { method: 'POST' });
    } catch (e) {
      // Ignore errors
    }
    window.location.reload();
  };

  // ── Event Listeners ───────────────────────────────────
  function init() {
    const submitBtn = getEl('auth-submit');
    const passwordInput = getEl('auth-password');

    if (submitBtn) {
      submitBtn.addEventListener('click', function(e) {
        e.preventDefault();
        doLogin();
      });
    }

    if (passwordInput) {
      passwordInput.addEventListener('keydown', function(e) {
        if (e.key === 'Enter') {
          e.preventDefault();
          doLogin();
        }
      });
      // Auto-focus on load
      setTimeout(() => passwordInput.focus(), 100);
    }

    // Check auth immediately
    checkAuth();
  }

  // ── Global click handler to intercept clicks while locked ──
  // This is a safety net — the overlay covers everything, but just in case
  function blockInteraction(e) {
    if (authChecked) return;
    const overlay = getEl('auth-overlay');
    if (overlay && overlay.style.display !== 'none') {
      // Click is outside overlay content — refocus password
      const input = getEl('auth-password');
      if (input) input.focus();
    }
  }

  // ── Boot ──────────────────────────────────────────────
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // Add shake animation styles
  const style = document.createElement('style');
  style.textContent = `
    @keyframes authShake {
      0%, 100% { transform: translateX(0); }
      20% { transform: translateX(-8px); }
      40% { transform: translateX(8px); }
      60% { transform: translateX(-5px); }
      80% { transform: translateX(5px); }
    }
    #auth-overlay input::placeholder { color: #64748b; }
    #auth-overlay input::-webkit-input-placeholder { color: #64748b; }
    #auth-overlay input::-moz-placeholder { color: #64748b; }
  `;
  document.head.appendChild(style);

})();
