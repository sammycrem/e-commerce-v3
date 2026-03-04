document.addEventListener('DOMContentLoaded', () => {
    const logsContainer = document.getElementById('logs-container');
    const refreshBtn = document.getElementById('btn-refresh-logs');
    const clearBtn = document.getElementById('btn-clear-logs');
    const logsTabBtn = document.getElementById('logs-tab');

    async function fetchLogs() {
        logsContainer.textContent = 'Fetching logs...';
        try {
            const response = await fetch('/api/admin/logs');
            if (!response.ok) {
                throw new Error('Failed to fetch logs');
            }
            const data = await response.json();
            if (data.logs) {
                logsContainer.textContent = data.logs;
                // Scroll to bottom
                logsContainer.scrollTop = logsContainer.scrollHeight;
            } else if (data.error) {
                logsContainer.textContent = 'Error: ' + data.error;
            } else {
                logsContainer.textContent = 'No logs found.';
            }
        } catch (error) {
            logsContainer.textContent = 'Error: ' + error.message;
        }
    }

    async function clearLogs() {
        if (!confirm('Are you sure you want to clear the logs? This action cannot be undone.')) {
            return;
        }

        try {
            const response = await fetch('/api/admin/logs/clear', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': getCsrfToken()
                }
            });

            if (!response.ok) {
                throw new Error('Failed to clear logs');
            }

            const data = await response.json();
            alert(data.message || 'Logs cleared successfully');
            fetchLogs();
        } catch (error) {
            alert('Error: ' + error.message);
        }
    }

    function getCsrfToken() {
        // CSRF token is usually in a meta tag or a hidden input in this project
        const csrfInput = document.querySelector('input[name="csrf_token"]');
        return csrfInput ? csrfInput.value : '';
    }

    if (refreshBtn) {
        refreshBtn.addEventListener('click', fetchLogs);
    }

    if (clearBtn) {
        clearBtn.addEventListener('click', clearLogs);
    }

    if (logsTabBtn) {
        logsTabBtn.addEventListener('click', () => {
            fetchLogs();
        });
    }

    // Initial fetch if logs tab is active (unlikely on load unless explicitly set)
    if (logsTabBtn && logsTabBtn.classList.contains('active')) {
        fetchLogs();
    }
});
