// static/js/alerts.js
(function() {
    'use strict';

    const overlay = document.getElementById('custom-alert-overlay');
    const titleEl = document.getElementById('custom-alert-title');
    const messageEl = document.getElementById('custom-alert-message');
    const okBtn = document.getElementById('custom-alert-ok');
    const cancelBtn = document.getElementById('custom-alert-cancel');

    if (!overlay || !messageEl || !okBtn || !cancelBtn) return;

    let resolveActiveAlert = null;

    function closeAlert(value) {
        overlay.classList.remove('show');
        if (resolveActiveAlert) {
            const resolve = resolveActiveAlert;
            resolveActiveAlert = null;
            resolve(value);
        }
    }

    window.customAlert = function(message, title = 'Message') {
        return new Promise((resolve) => {
            resolveActiveAlert = resolve;
            titleEl.textContent = title;
            messageEl.textContent = message;
            cancelBtn.style.display = 'none';
            okBtn.textContent = 'OK';
            overlay.classList.add('show');
        });
    };

    window.customConfirm = function(message, title = 'Confirmation') {
        return new Promise((resolve) => {
            resolveActiveAlert = resolve;
            titleEl.textContent = title;
            messageEl.textContent = message;
            cancelBtn.style.display = 'inline-block';
            okBtn.textContent = 'OK';
            overlay.classList.add('show');
        });
    };

    // Override the global alert function
    window.alert = function(message) {
        return window.customAlert(message);
    };

    // Override the global confirm function
    window.confirm = function(message) {
        return window.customConfirm(message);
    };

    okBtn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        closeAlert(true);
    });

    cancelBtn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        closeAlert(false);
    });

    // Close on overlay click (defaults to cancel/false)
    overlay.addEventListener('click', (e) => {
        if (e.target === overlay) {
            closeAlert(false);
        }
    });

    // Handle Escape key
    window.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && overlay.classList.contains('show')) {
            closeAlert(false);
        }
        if (e.key === 'Enter' && overlay.classList.contains('show')) {
            closeAlert(true);
        }
    });
})();
