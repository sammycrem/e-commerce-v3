document.addEventListener('DOMContentLoaded', async () => {
  const activeCurrencySelect = document.getElementById('active-currency-select');
  const saveSettingsBtn = document.getElementById('save-settings');
  const newCurrencySymbol = document.getElementById('new-currency-symbol');
  const addCurrencyBtn = document.getElementById('add-currency');
  const currenciesList = document.getElementById('currencies-list');

  async function loadSettings() {
    try {
      const res = await fetch('/api/admin/settings');
      const settings = await res.json();

      const currenciesRes = await fetch('/api/admin/currencies');
      const currencies = await currenciesRes.json();

      // Populate select
      activeCurrencySelect.innerHTML = '';
      currencies.forEach(c => {
        const opt = document.createElement('option');
        opt.value = c.symbol;
        opt.textContent = c.symbol;
        if (settings.currency === c.symbol) opt.selected = true;
        activeCurrencySelect.appendChild(opt);
      });

      // Load VAT Mode
      const vatMode = settings.vat_calculation_mode || 'SHIPPING_ADDRESS';
      if (vatMode === 'SHIPPING_ADDRESS') document.getElementById('vat_mode_shipping').checked = true;
      else if (vatMode === 'DEFAULT_COUNTRY') document.getElementById('vat_mode_default').checked = true;

      // Load Loyalty Settings
      const loyaltyEnabled = (settings.loyalty_enabled || '').toLowerCase() === 'true';
      document.getElementById('loyalty_enabled').checked = loyaltyEnabled;
      document.getElementById('loyalty_percentage').value = settings.loyalty_percentage || '0';
      document.getElementById('loyalty_expiration_days').value = settings.loyalty_expiration_days || '60';

      // Load Global Promo Settings
      const promoEnabled = (settings.global_promo_enabled || '').toLowerCase() === 'true';
      document.getElementById('global_promo_enabled').checked = promoEnabled;
      document.getElementById('global_promo_message').value = settings.global_promo_message || '';

      // Populate list
      currenciesList.innerHTML = '';
      currencies.forEach(c => {
        const li = document.createElement('li');
        li.className = 'list-group-item d-flex justify-content-between align-items-center';
        li.textContent = c.symbol;

        const delBtn = document.createElement('button');
        delBtn.className = 'btn btn-sm btn-outline-danger';
        delBtn.innerHTML = '<i class="fas fa-trash"></i>';
        delBtn.onclick = () => deleteCurrency(c.id);

        // Don't allow deleting active currency
        if (settings.currency === c.symbol) {
          delBtn.disabled = true;
          li.innerHTML += ' <span class="badge bg-primary ms-2">Active</span>';
        }

        li.appendChild(delBtn);
        currenciesList.appendChild(li);
      });
    } catch (err) {
      console.error('Failed to load settings:', err);
    }
  }

  saveSettingsBtn.onclick = async () => {
    const currency = activeCurrencySelect.value;
    const vatMode = document.getElementById('vat_mode_shipping').checked ? 'SHIPPING_ADDRESS' : 'DEFAULT_COUNTRY';
    const loyaltyEnabled = document.getElementById('loyalty_enabled').checked;
    const loyaltyPercentage = document.getElementById('loyalty_percentage').value;
    const loyaltyExpirationDays = document.getElementById('loyalty_expiration_days').value;
    const globalPromoEnabled = document.getElementById('global_promo_enabled').checked;
    const globalPromoMessage = document.getElementById('global_promo_message').value;

    try {
      const headers = { 'Content-Type': 'application/json' };
      const csrfToken = document.querySelector('meta[name="csrf-token"]');
      if (csrfToken) headers['X-CSRFToken'] = csrfToken.content;

      const res = await fetch('/api/admin/settings', {
        method: 'POST',
        headers: headers,
        body: JSON.stringify({
            currency: currency,
            vat_calculation_mode: vatMode,
            loyalty_enabled: loyaltyEnabled,
            loyalty_percentage: loyaltyPercentage,
            loyalty_expiration_days: loyaltyExpirationDays,
            global_promo_enabled: globalPromoEnabled,
            global_promo_message: globalPromoMessage
        })
      });
      if (res.ok) {
        await alert('Settings saved! Please refresh to see changes across the dashboard.');
        window.location.reload();
      } else {
        const data = await res.json();
        await alert('Error: ' + data.error);
      }
    } catch (err) {
      await alert('Failed to save settings');
    }
  };

  addCurrencyBtn.onclick = async () => {
    const symbol = newCurrencySymbol.value.trim();
    if (!symbol) return;
    try {
      const headers = { 'Content-Type': 'application/json' };
      const csrfToken = document.querySelector('meta[name="csrf-token"]');
      if (csrfToken) headers['X-CSRFToken'] = csrfToken.content;

      const res = await fetch('/api/admin/currencies', {
        method: 'POST',
        headers: headers,
        body: JSON.stringify({ symbol })
      });
      if (res.ok) {
        newCurrencySymbol.value = '';
        loadSettings();
      } else {
        const data = await res.json();
        await alert('Error: ' + data.error);
      }
    } catch (err) {
      await alert('Failed to add currency');
    }
  };

  async function deleteCurrency(id) {
    if (!await confirm('Are you sure?')) return;
    try {
      const headers = {};
      const csrfToken = document.querySelector('meta[name="csrf-token"]');
      if (csrfToken) headers['X-CSRFToken'] = csrfToken.content;

      const res = await fetch(`/api/admin/currencies/${id}`, {
        method: 'DELETE',
        headers: headers
      });
      if (res.ok) {
        loadSettings();
      } else {
        const data = await res.json();
        await alert('Error: ' + data.error);
      }
    } catch (err) {
      await alert('Failed to delete currency');
    }
  }

  // Factory Reset
  const factoryResetBtn = document.getElementById('btn-factory-reset');
  if (factoryResetBtn) {
      factoryResetBtn.onclick = async () => {
          const code = document.getElementById('reset_code').value.trim();
          if (!code) {
              await alert("Please enter the reset code.");
              return;
          }

          if (!await confirm("DANGER: This will delete ALL data (products, orders, users, etc.) and reset the application to its initial state. This action cannot be undone.\n\nAre you sure you want to proceed?")) {
              return;
          }

          // Double confirmation
          if (!await confirm("Are you REALLY sure? Last warning.")) {
              return;
          }

          try {
              const headers = { 'Content-Type': 'application/json' };
              const csrfToken = document.querySelector('meta[name="csrf-token"]');
              if (csrfToken) headers['X-CSRFToken'] = csrfToken.content;

              const res = await fetch('/api/admin/factory-reset', {
                  method: 'POST',
                  headers: headers,
                  body: JSON.stringify({ code: code })
              });

              const data = await res.json();
              if (res.ok) {
                  await alert(data.message || 'Reset successful. You will be redirected to login.');
                  window.location.href = '/login';
              } else {
                  await alert('Error: ' + (data.error || 'Reset failed'));
              }
          } catch (err) {
              console.error(err);
              await alert('An unexpected error occurred.');
          }
      };
  }

  // Initial load
  loadSettings();
});
