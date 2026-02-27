// static/js/admin_orders.js
document.addEventListener('DOMContentLoaded', async () => {
  const listEl = document.getElementById('orders-list');
  const detailEl = document.getElementById('order-detail');
  const titleEl = document.getElementById('order-detail-title');
  const filterStatus = document.getElementById('filter-status');
  const searchInput = document.getElementById('search-order');

  let currentPage = 1;
  let perPage = 30;
  let currentOrders = [];

  async function loadOrders() {
    const status = filterStatus.value || '';
    const q = (searchInput.value || '').trim();
    listEl.innerHTML = '<p>Loading orders…</p>';
    try {
      const params = new URLSearchParams();
      params.set('page', currentPage);
      params.set('per_page', perPage);
      if (status) params.set('status', status);
      if (q) params.set('q', q);
      const res = await fetch('/api/admin/orders?' + params.toString(), { credentials: 'same-origin' });
      if (!res.ok) throw new Error('Failed to load orders');
      const data = await res.json();
      currentOrders = data.orders || [];
      renderList();
    } catch (err) {
      listEl.innerHTML = '<p>Error loading orders.</p>';
      console.error(err);
    }
  }

  async function renderList() {
    listEl.innerHTML = '';
    if (!currentOrders.length) {
      listEl.innerHTML = '<p>No orders found.</p>';
      return;
    }
    currentOrders.forEach(o => {
      const row = document.createElement('div');
      row.style.display = 'flex';
      row.style.justifyContent = 'space-between';
      row.style.alignItems = 'center';
      row.style.padding = '8px';
      row.style.borderBottom = '1px solid #eee';
      row.style.cursor = 'pointer';

      const left = document.createElement('div');
      left.innerHTML = `<strong>${o.public_order_id}</strong><div style="font-size:0.9rem;color:#666">${new Date(o.created_at).toLocaleString()}</div>`;

      const right = document.createElement('div');
      right.style.textAlign = 'right';
      right.innerHTML = `<div>${(o.total_cents/100).toFixed(2)} ${o.currency||''}</div><div style="font-size:0.85rem;color:#333">${o.status}</div>`;

      row.appendChild(left);
      row.appendChild(right);
      row.addEventListener('click', async () => {
      const newStatus = statusSel.value;
      try {
        const res = await fetch(`/api/admin/orders/${encodeURIComponent(o.public_order_id)}/status`, {
          method: 'PUT', credentials: 'same-origin',
          headers: {'Content-Type':'application/json'},
          body: JSON.stringify({ status: newStatus })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'Failed');
        await alert(`Status updated: ${newStatus}`);
        await loadOrders();
        await loadOrderDetails(o.public_order_id);
      } catch (err) {
        await alert('Error updating status: ' + err.message);
      }
    };

    // shipment info
    const shipProv = el('input', { class: 'form-input', placeholder: 'Carrier (e.g. UPS)' }); shipProv.value = o.shipping_provider || '';
    const trackIn = el('input', { class: 'form-input', placeholder: 'Tracking number' }); trackIn.value = o.tracking_number || '';
    const markShippedChk = el('input', { type:'checkbox' }); // mark as shipped
    const markShippedLabel = el('label', {}, 'Mark as shipped');

    const saveShipBtn = el('button', { class: 'btn' }, 'Save Shipment');
    saveShipBtn.onclick = async () => {
      try {
        const res = await fetch(`/api/admin/orders/${encodeURIComponent(o.public_order_id)}/shipment`, {
          method: 'PUT', credentials: 'same-origin',
          headers: {'Content-Type':'application/json'},
          body: JSON.stringify({
            shipping_provider: shipProv.value || null,
            tracking_number: trackIn.value || null,
            mark_as_shipped: markShippedChk.checked
          })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'Failed to save');
        await alert('Shipment info saved.');
        await loadOrders();
        await loadOrderDetails(o.public_order_id);
      } catch (err) {
        await alert('Error saving shipment: ' + err.message);
      }
    };

    // packing slip / printable info
    const packBtn = el('button', { class:'btn' }, 'Print Packing Slip');
    packBtn.onclick = async () => {
      // simple printable view: open a new window with order summary
      const w = window.open('', '_blank', 'width=800,height=600');
      const html = `
        <html><head><title>Packing Slip ${o.public_order_id}</title></head><body>
        <h1>Packing Slip: ${o.public_order_id}</h1>
        <p>Items:</p>
        <ul>
          ${(o.items || []).map(i => `<li>${i.product_snapshot && i.product_snapshot.name ? i.product_snapshot.name : i.variant_sku} — Qty: ${i.quantity}</li>`).join('')}
        </ul>
        <p>Total: $${(o.total_cents/100).toFixed(2)}</p>
        </body></html>`;
      w.document.write(html); w.document.close();
    };

    // assemble right column
    right.appendChild(el('h3', {}, 'Workflow'));
    right.appendChild(statusLabel);
    right.appendChild(statusSel);
    right.appendChild(updStatusBtn);
    right.appendChild(el('hr'));
    right.appendChild(el('h4', {}, 'Shipment'));
    right.appendChild(shipProv);
    right.appendChild(trackIn);
    right.appendChild(el('div', {}, markShippedChk, el('span', {}, ' '), markShippedLabel));
    right.appendChild(saveShipBtn);
    right.appendChild(el('hr'));
    right.appendChild(packBtn);

    wrap.appendChild(left);
    wrap.appendChild(right);

    detailEl.innerHTML = '';
    detailEl.appendChild(wrap);
  }

  // helper element creator (simple)
  async function el(tag, props={}, ...children) {
    const e = document.createElement(tag);
    for (const k in props) {
      if (k === 'class') e.className = props[k];
      else if (k === 'html') e.innerHTML = props[k];
      else if (k === 'for') e.htmlFor = props[k];
      else e.setAttribute(k, props[k]);
    }
    children.forEach(c => { if (typeof c === 'string') e.appendChild(document.createTextNode(c)); else if (c) e.appendChild(c); });
    return e;
  }

  filterStatus.addEventListener('change', loadOrders);
  searchInput.addEventListener ('keyup', (e) => {
    if (e.key === 'Enter') loadOrders();
  });

  // initial load
  loadOrders();
});
