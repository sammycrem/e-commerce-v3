// static/js/alerts.js
(function() {
    'use strict';

    const overlay = document.getElementById('custom-alert-overlay');
    const messageEl = document.getElementById('custom-alert-message');
    const closeBtn = document.getElementById('custom-alert-close');

    if (!overlay || !messageEl || !closeBtn) return;

    let resolveActiveAlert = null;

    function closeAlert() {
        overlay.classList.remove('show');
        if (resolveActiveAlert) {
            resolveActiveAlert();
            resolveActiveAlert = null;
        }
    }

    // Override the global alert function
    window.alert = function(message) {
        messageEl.textContent = message;
        overlay.classList.add('show');

        return new Promise((resolve) => {
            resolveActiveAlert = resolve;
        });
    };

    closeBtn.addEventListener('click', () => {
        closeAlert();
    });

    // Also close on overlay click
    overlay.addEventListener('click', (e) => {
        if (e.target === overlay) {
            closeAlert();
        }
    });

    // Handle Escape key
    window.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && overlay.classList.contains('show')) {
            closeAlert();
        }
    });
})();
