// static/js/admin_orders.js
// Admin Orders UI: list orders, view order detail, update status and shipment via fetch PUT calls.
// Works for /admin/orders (list) and /admin/orders/<public_order_id> (detail).

(function () {
  'use strict';

  // Helper to create elements quickly
  function el(tag, attrs = {}, ...children) {
    const e = document.createElement(tag);
    for (const k in attrs) {
      if (k === 'class') e.className = attrs[k];
      else if (k === 'html') e.innerHTML = attrs[k];
      else if (k === 'for') e.htmlFor = attrs[k];
      else e.setAttribute(k, attrs[k]);
    }
    children.forEach(c => {
      if (typeof c === 'string') e.appendChild(document.createTextNode(c));
      else if (c instanceof Node) e.appendChild(c);
    });
    return e;
  }

  // Simple toast / snackbar
  function showToast(message, type = 'info', timeout = 3500) {
    let node = document.getElementById('admin-toast');
    if (!node) {
      node = el('div', { id: 'admin-toast' });
      Object.assign(node.style, {
        position: 'fixed',
        right: '16px',
        bottom: '16px',
        zIndex: 9999,
        minWidth: '200px',
        fontFamily: 'sans-serif'
      });
      document.body.appendChild(node);
    }
    const msg = el('div', { class: `toast ${type}` }, message);
    Object.assign(msg.style, {
      marginTop: '8px',
      padding: '10px 14px',
      borderRadius: '6px',
      color: '#fff',
      background: type === 'error' ? '#c0392b' : (type === 'success' ? '#2ecc71' : '#333'),
      boxShadow: '0 6px 18px rgba(0,0,0,0.08)'
    });
    node.appendChild(msg);
    setTimeout(() => {
      msg.remove();
      if (!node.hasChildNodes()) node.remove();
    }, timeout);
  }

  // Format cents to currency string (simple)
  function formatPrice(cents) {
    cents = Number(cents || 0);
    const symbol = (window.appConfig && window.appConfig.currencySymbol) || '€';
    return `${symbol}${(cents / 100).toFixed(2)}`;
  }

  // -------------------------------
  // Orders list page logic
  // -------------------------------
  async function loadOrdersList(containerSelector = '#orders-list') {
    const listEl = document.querySelector(containerSelector);
    if (!listEl) return;

    // Optionally read filters if present in DOM
    // Avoid reading #product-filter-status which is for products
    const statusFilter = document.querySelector('#order-filter-status') ? document.querySelector('#order-filter-status').value : '';
    const qFilter = document.querySelector('#search-order') ? document.querySelector('#search-order').value.trim() : '';
    listEl.innerHTML = '<p>Loading orders…</p>';

    try {
      const params = new URLSearchParams();
      params.set('page', 1);
      params.set('per_page', 50);
      if (statusFilter) params.set('status', statusFilter);
      if (qFilter) params.set('q', qFilter);

      const headers = { 'Content-Type': 'application/json' };
      const csrfToken = document.querySelector('meta[name="csrf-token"]');
      if (csrfToken) headers['X-CSRFToken'] = csrfToken.content;

      const res = await fetch('/api/admin/orders?' + params.toString(), {
          credentials: 'same-origin',
          headers: headers
      });
      if (!res.ok) throw new Error('Failed to load orders');
      const data = await res.json();

      const orders = data.orders || [];
      if (!orders.length) {
        listEl.innerHTML = '<p>No orders found.</p>';
        return;
      }

      listEl.innerHTML = '';
      orders.forEach(o => {
        const row = el('div', { class: 'order-row' });
        Object.assign(row.style, { display: 'flex', justifyContent: 'space-between', padding: '10px', borderBottom: '1px solid #eee', cursor: 'pointer' });

        const left = el('div', { class: 'order-left' });
        const idRow = el('div', { class: 'order-id', style: 'display:flex; align-items:center;' }, o.public_order_id);

        if (o.unread_messages_count > 0) {
            const badge = el('span', { class: 'badge bg-danger ms-2', style: 'margin-left:8px; font-size:0.7em;' }, `${o.unread_messages_count} new msg`);
            idRow.appendChild(badge);
        }

        left.appendChild(idRow);
        left.appendChild(el('div', { class: 'order-meta' }, `${new Date(o.created_at).toLocaleString()} • items: ${o.item_count}`));

        const right = el('div', { class: 'order-right' },
          el('div', { class: 'order-total' }, formatPrice(o.total_cents)),
          el('div', { class: 'order-status' }, o.status)
        );
        Object.assign(right.style, { textAlign: 'right' });

        row.appendChild(left);
        row.appendChild(right);

        row.addEventListener('click', () => {
          // Navigate to order detail page - assume route exists /admin/orders/<public_order_id>
          // If your detail page is a SPA panel, you could instead call loadOrderDetails here
          window.location.href = `/admin/orders/${encodeURIComponent(o.public_order_id)}`;
        });

        listEl.appendChild(row);
      });

    } catch (err) {
      console.error('loadOrdersList error', err);
      listEl.innerHTML = '<p>Error loading orders.</p>';
      showToast('Failed to load orders', 'error');
    }
  }

  // -------------------------------
  // Order detail page logic
  // -------------------------------
  async function loadOrderDetail(publicOrderId, detailContainerSelector = '#order-detail') {
    const detailEl = document.querySelector(detailContainerSelector);
    if (!detailEl) return;

    detailEl.innerHTML = '<p>Loading order…</p>';
    try {
      const headers = { 'Content-Type': 'application/json' };
      const csrfToken = document.querySelector('meta[name="csrf-token"]');
      if (csrfToken) headers['X-CSRFToken'] = csrfToken.content;

      const res = await fetch(`/api/admin/orders/${encodeURIComponent(publicOrderId)}`, {
          credentials: 'same-origin',
          headers: headers
      });
      if (!res.ok) {
        if (res.status === 404) detailEl.innerHTML = '<p>Order not found.</p>';
        else throw new Error('Failed to load order');
        return;
      }
      const o = await res.json();
      renderOrderDetail(o, detailEl);
    } catch (err) {
      console.error('loadOrderDetail', err);
      detailEl.innerHTML = '<p>Error loading order details.</p>';
      showToast('Failed to load order details', 'error');
    }
  }

  function renderOrderDetail(o, container) {
    container.innerHTML = ''; // clear

    // header / basic summary
    const header = el('div', { class: 'order-header mb-4' },
      el('h2', { class: 'fw-bold' }, `Order ${o.public_order_id}`),
      el('div', { class: 'text-muted' }, `Created: ${new Date(o.created_at).toLocaleString()}`),
      el('div', { class: 'badge bg-primary mt-2' }, o.status)
    );
    if (o.user) {
        header.appendChild(el('div', { class: 'mt-2' },
            el('strong', {}, 'User: '),
            el('span', {}, `${o.user.username} (${o.user.email})`)
        ));
    }
    container.appendChild(header);

    // Grid for Addresses and Methods
    const grid = el('div', { class: 'row mb-4' });

    // Shipping Address
    const shipCol = el('div', { class: 'col-md-6 mb-3' }, el('h4', { class: 'h6 fw-bold' }, 'Shipping Address'));
    if (o.shipping_address_snapshot) {
      const s = o.shipping_address_snapshot;
      shipCol.appendChild(el('div', { class: 'small' },
        el('div', { class: 'fw-bold' }, `${s.first_name} ${s.last_name}`),
        el('div', {}, s.address_line_1),
        s.address_line_2 ? el('div', {}, s.address_line_2) : '',
        el('div', {}, `${s.city}, ${s.state || ''} ${s.postal_code}`),
        el('div', {}, s.country_iso_code),
        el('div', { class: 'text-muted' }, s.phone_number || '')
      ));
    } else {
      shipCol.appendChild(el('div', { class: 'text-muted small' }, 'No shipping address recorded.'));
    }
    grid.appendChild(shipCol);

    // Billing Address
    const billCol = el('div', { class: 'col-md-6 mb-3' }, el('h4', { class: 'h6 fw-bold' }, 'Billing Address'));
    if (o.billing_address_snapshot) {
      const b = o.billing_address_snapshot;
      billCol.appendChild(el('div', { class: 'small' },
        el('div', { class: 'fw-bold' }, `${b.first_name} ${b.last_name}`),
        el('div', {}, b.address_line_1),
        b.address_line_2 ? el('div', {}, b.address_line_2) : '',
        el('div', {}, `${b.city}, ${b.state || ''} ${b.postal_code}`),
        el('div', {}, b.country_iso_code),
        el('div', { class: 'text-muted' }, b.phone_number || '')
      ));
    } else {
      billCol.appendChild(el('div', { class: 'text-muted small' }, 'No billing address recorded.'));
    }
    grid.appendChild(billCol);

    // Methods
    const methodCol = el('div', { class: 'col-md-12 mb-3' }, el('h4', { class: 'h6 fw-bold border-top pt-3' }, 'Methods & Info'));
    const infoList = el('ul', { class: 'list-unstyled small' });
    infoList.appendChild(el('li', {}, el('span', { class: 'text-muted' }, 'Shipping Method: '), o.shipping_method || 'N/A'));
    infoList.appendChild(el('li', {}, el('span', { class: 'text-muted' }, 'Payment Method: '), o.payment_method || 'N/A'));
    infoList.appendChild(el('li', {}, el('span', { class: 'text-muted' }, 'Promo Code: '), el('span', { class: 'badge bg-light text-dark' }, o.promo_code || 'None')));
    if (o.comment) {
      infoList.appendChild(el('li', { class: 'mt-2' },
        el('div', { class: 'text-muted small fw-bold' }, 'Order Comment:'),
        el('div', { class: 'p-2 bg-light rounded mt-1 border' }, o.comment)
      ));
    }
    methodCol.appendChild(infoList);
    grid.appendChild(methodCol);

    container.appendChild(grid);

    // items list
    const itemsWrap = el('div', { class: 'order-items mb-4' });
    itemsWrap.appendChild(el('h4', { class: 'h6 fw-bold border-bottom pb-2' }, 'Order Items'));
    const table = el('table', { class: 'table table-sm small' },
      el('thead', {}, el('tr', {},
        el('th', {}, 'Item'),
        el('th', {}, 'SKU'),
        el('th', { class: 'text-center' }, 'Qty'),
        el('th', { class: 'text-end' }, 'Unit Price'),
        el('th', { class: 'text-end' }, 'Total')
      )),
      el('tbody', {})
    );
    const tbody = table.querySelector('tbody');
    (o.items || []).forEach(it => {
      const name = (it.product_snapshot && it.product_snapshot.name) ? it.product_snapshot.name : it.variant_sku;
      tbody.appendChild(el('tr', {},
        el('td', {}, name),
        el('td', {}, it.variant_sku),
        el('td', { class: 'text-center' }, it.quantity.toString()),
        el('td', { class: 'text-end' }, formatPrice(it.unit_price_cents)),
        el('td', { class: 'text-end' }, formatPrice(it.unit_price_cents * it.quantity))
      ));
    });
    itemsWrap.appendChild(table);
    container.appendChild(itemsWrap);

    // amounts
    const amounts = el('div', { class: 'order-amounts bg-light p-3 rounded' });
    const addRow = (label, value, isBold = false) => {
      const row = el('div', { class: `d-flex justify-content-between mb-1 ${isBold ? 'fw-bold h5 mt-2 pt-2 border-top' : ''}` },
        el('span', {}, label),
        el('span', {}, value)
      );
      amounts.appendChild(row);
    };
    addRow('Subtotal', formatPrice(o.subtotal_cents));
    if (o.discount_cents > 0) addRow('Discount', `-${formatPrice(o.discount_cents)}`);
    addRow('Shipping', formatPrice(o.shipping_cost_cents));
    addRow('VAT', formatPrice(o.vat_cents));
    addRow('Total Due', formatPrice(o.total_cents), true);

    container.appendChild(amounts);

    // workflow controls
    const workflow = el('div', { class: 'order-workflow', style: 'margin-top:16px;' });
    workflow.appendChild(el('h3', {}, 'Workflow'));

    const statusSelect = el('select', { class: 'form-input', id: 'admin-status-select' });
    const ORDER_WORKFLOW = ['PENDING','PAID','READY_FOR_SHIPPING','SHIPPED','DELIVERED','CANCELLED','RETURNED'];
    ORDER_WORKFLOW.forEach(s => {
      const opt = el('option', { value: s }, s);
      if (s === o.status) opt.selected = true;
      statusSelect.appendChild(opt);
    });
    workflow.appendChild(statusSelect);

    const updateStatusBtn = el('button', { class: 'btn btn-primary', style: 'margin-left:8px;' }, 'Update Status');
    updateStatusBtn.addEventListener('click', async () => {
      const newStatus = statusSelect.value;
      await updateOrderStatus(o.public_order_id, newStatus);
      // refresh
      await loadOrderDetail(o.public_order_id, container);
      await refreshListIfPresent();
    });
    workflow.appendChild(updateStatusBtn);

    container.appendChild(workflow);

    // shipment controls
    const shipWrap = el('div', { class: 'order-shipment', style: 'margin-top:18px;' });
    shipWrap.appendChild(el('h3', {}, 'Shipment'));

    const providerInput = el('input', { class: 'form-input', placeholder: 'Carrier (e.g. UPS)', id: 'admin-shipping-provider' });
    providerInput.value = o.shipping_provider || '';
    const trackingInput = el('input', { class: 'form-input', placeholder: 'Tracking #', id: 'admin-tracking-number' });
    trackingInput.value = o.tracking_number || '';
    const markShippedChk = el('input', { type: 'checkbox', id: 'admin-mark-shipped' });
    const markShippedLabel = el('label', { for: 'admin-mark-shipped', style: 'margin-left:6px;' }, 'Mark as shipped');

    const saveShipmentBtn = el('button', { class: 'btn', style: 'display:block;margin-top:8px;' }, 'Save Shipment');
    saveShipmentBtn.addEventListener('click', async () => {
      const payload = {
        shipping_provider: providerInput.value || null,
        tracking_number: trackingInput.value || null,
        mark_as_shipped: !!markShippedChk.checked
      };
      await updateOrderShipment(o.public_order_id, payload);
      // refresh
      await loadOrderDetail(o.public_order_id, container);
      await refreshListIfPresent();
    });

    const shipmentRow = el('div', {}, providerInput, trackingInput, el('div', { style: 'margin-top:8px;' }, markShippedChk, markShippedLabel), saveShipmentBtn);
    shipWrap.appendChild(shipmentRow);
    container.appendChild(shipWrap);

    // small details (provider/tracking)
    container.appendChild(el('p', {}, `Current shipment: ${o.shipping_provider || '—'} ${o.tracking_number ? ' • ' + o.tracking_number : ''}`));
    if (o.shipped_at) container.appendChild(el('p', {}, `Shipped at: ${new Date(o.shipped_at).toLocaleString()}`));

    // Messages Section
    const msgWrap = el('div', { class: 'order-messages', style: 'margin-top:24px; border-top:1px solid #eee; padding-top:16px;' });
    msgWrap.appendChild(el('h3', {}, 'Messages'));

    const msgList = el('div', { style: 'max-height:300px; overflow-y:auto; margin-bottom:12px; border:1px solid #eee; padding:10px; border-radius:4px;' });
    const messages = (o.messages || []).sort((a,b) => new Date(a.created_at) - new Date(b.created_at));

    if (messages.length === 0) {
        msgList.appendChild(el('div', { class: 'text-muted text-center' }, 'No messages yet.'));
    } else {
        messages.forEach(m => {
            const isUser = m.sender_type === 'USER';
            const bubble = el('div', { class: `message-bubble ${isUser ? 'bg-light border' : 'bg-primary text-white'}` });
            Object.assign(bubble.style, {
                maxWidth: '80%',
                padding: '8px 12px',
                borderRadius: '12px',
                marginBottom: '8px',
                marginLeft: isUser ? '0' : 'auto',
                marginRight: isUser ? 'auto' : '0',
                alignSelf: isUser ? 'flex-start' : 'flex-end'
            });

            const meta = el('div', { style: 'font-size:0.75rem; opacity:0.8; margin-bottom:4px;' },
                `${isUser ? 'User' : 'Admin'} • ${new Date(m.created_at).toLocaleString()}`
            );
            const content = el('div', {}, m.content);

            bubble.appendChild(meta);
            bubble.appendChild(content);
            msgList.appendChild(bubble);
        });
        // Scroll to bottom
        setTimeout(() => msgList.scrollTop = msgList.scrollHeight, 0);
    }
    msgWrap.appendChild(msgList);

    // Reply Form
    const replyArea = el('textarea', { class: 'form-control', rows: 3, placeholder: 'Type a reply...' });
    Object.assign(replyArea.style, { width: '100%', marginBottom: '8px', padding:'8px' });

    const sendBtn = el('button', { class: 'btn btn-primary' }, 'Send Message');
    sendBtn.addEventListener('click', async () => {
        const content = replyArea.value.trim();
        if (!content) return showToast('Message cannot be empty', 'error');

        try {
            await sendAdminMessage(o.public_order_id, content);
            replyArea.value = '';
            // refresh
            await loadOrderDetail(o.public_order_id, container);
        } catch (e) {
            // handled in sendAdminMessage
        }
    });

    msgWrap.appendChild(replyArea);
    msgWrap.appendChild(sendBtn);
    container.appendChild(msgWrap);
  }

  // -------------------------------
  // API calls: update status & shipment
  // -------------------------------
  async function updateOrderStatus(publicOrderId, newStatus) {
    try {
      const headers = { 'Content-Type': 'application/json' };
      const csrfToken = document.querySelector('meta[name="csrf-token"]');
      if (csrfToken) headers['X-CSRFToken'] = csrfToken.content;

      const res = await fetch(`/api/admin/orders/${encodeURIComponent(publicOrderId)}/status`, {
        method: 'PUT',
        credentials: 'same-origin',
        headers: headers,
        body: JSON.stringify({ status: newStatus })
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || 'Failed to update status');
      }
      showToast(`Order ${publicOrderId} status updated to ${newStatus}`, 'success');
      return data;
    } catch (err) {
      console.error('updateOrderStatus error', err);
      showToast('Failed to update status: ' + err.message, 'error');
      throw err;
    }
  }

  async function sendAdminMessage(publicOrderId, content) {
    try {
        const headers = { 'Content-Type': 'application/json' };
        const csrfToken = document.querySelector('meta[name="csrf-token"]');
        if (csrfToken) headers['X-CSRFToken'] = csrfToken.content;

        const res = await fetch(`/api/admin/orders/${encodeURIComponent(publicOrderId)}/message`, {
            method: 'POST',
            credentials: 'same-origin',
            headers: headers,
            body: JSON.stringify({ content })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'Failed to send message');
        showToast('Message sent', 'success');
        return data;
    } catch (err) {
        console.error('sendAdminMessage error', err);
        showToast('Failed to send message: ' + err.message, 'error');
        throw err;
    }
  }

  async function updateOrderShipment(publicOrderId, payload) {
    try {
      const headers = { 'Content-Type': 'application/json' };
      const csrfToken = document.querySelector('meta[name="csrf-token"]');
      if (csrfToken) headers['X-CSRFToken'] = csrfToken.content;

      const res = await fetch(`/api/admin/orders/${encodeURIComponent(publicOrderId)}/shipment`, {
        method: 'PUT',
        credentials: 'same-origin',
        headers: headers,
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || 'Failed to update shipment');
      }
      showToast(`Shipment info saved for ${publicOrderId}`, 'success');
      return data;
    } catch (err) {
      console.error('updateOrderShipment error', err);
      showToast('Failed to save shipment: ' + err.message, 'error');
      throw err;
    }
  }

  // If the list view exists on the page, refresh it after changes
  async function refreshListIfPresent() {
    const listNode = document.querySelector('#orders-list');
    if (listNode) await loadOrdersList('#orders-list');
  }

  // -------------------------------
  // Auto-detect page and init
  // -------------------------------
  document.addEventListener('DOMContentLoaded', () => {
    // If orders list element present, render list
    if (document.querySelector('#orders-list')) {
      loadOrdersList('#orders-list');

      // wire up filter controls if present
      const filterStatus = document.querySelector('#order-filter-status');
      const searchOrder = document.querySelector('#search-order');
      if (filterStatus) filterStatus.addEventListener('change', () => loadOrdersList('#orders-list'));
      if (searchOrder) searchOrder.addEventListener('keydown', (e) => { if (e.key === 'Enter') loadOrdersList('#orders-list'); });
    }

    // If order detail container present and URL contains a public_order_id, load it
    const detailNode = document.querySelector('#order-detail');
    if (detailNode) {
      // Try to extract public_order_id from the URL: /admin/orders/<public_order_id>
      const match = window.location.pathname.match(/\/admin\/orders\/([^\/?#]+)/);
      if (match && match[1]) {
        const publicOrderId = decodeURIComponent(match[1]);
        loadOrderDetail(publicOrderId, '#order-detail');
      } else {
        // If template included order_id in a data attribute, use that (e.g., <div id="order-detail" data-public-order-id="ORD-...">)
        const node = document.getElementById('order-detail');
        const publicOrderId = node ? node.dataset.publicOrderId : null;
        if (publicOrderId) loadOrderDetail(publicOrderId, '#order-detail');
      }
    }
  });

  // expose for debugging
  window.adminOrders = {
    loadOrdersList,
    loadOrderDetail,
    updateOrderStatus,
    updateOrderShipment
  };

})();
