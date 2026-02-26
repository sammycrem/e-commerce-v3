// static/js/alerts.js
(function() {
    'use strict';

    const overlay = document.getElementById('custom-alert-overlay');
    const messageEl = document.getElementById('custom-alert-message');
    const closeBtn = document.getElementById('custom-alert-close');

    if (!overlay || !messageEl || !closeBtn) return;

    // Override the global alert function
    window.alert = function(message) {
        messageEl.textContent = message;
        overlay.classList.add('show');
    };

    closeBtn.addEventListener('click', () => {
        overlay.classList.remove('show');
    });

    // Also close on overlay click
    overlay.addEventListener('click', (e) => {
        if (e.target === overlay) {
            overlay.classList.remove('show');
        }
    });

    // Handle Escape key
    window.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && overlay.classList.contains('show')) {
            overlay.classList.remove('show');
        }
    });
})();
