# Proposal: VAT Toggle Switch (Excl. VAT / Incl. VAT)

## Overview
This proposal introduces a user-facing toggle switch to allow customers (specifically individuals vs. professionals) to view product prices either **excluding VAT** (current default) or **including VAT**. This enhances the user experience for B2C customers who expect transparent pricing.

## Functionality

### 1. Global VAT Preference
- A switch (e.g., "Show Prices with VAT") will be added to the site header/navigation.
- The user's preference (`show_vat_inclusive`: `true`/`false`) will be stored in the browser (e.g., `localStorage` or cookie) to persist across sessions.

### 2. Price Display Logic
- **Excl. VAT Mode (Default/Professional):** Prices display the base price (e.g., "€100.00").
- **Incl. VAT Mode (Individual):** Prices are dynamically recalculated to include VAT.
    - **VAT Rate Source:**
        1.  **Global Admin Setting:** If "VAT Calculation Mode" is set to "Based on Default Country", use the Default Country's VAT rate.
        2.  **Shipping Address Mode:** If "Based on Shipping Address":
            -   Use the user's selected shipping country (if available via a new "Ship To" selector).
            -   Fallback to the Default Country's VAT rate if no shipping country is selected.

### 3. "Ship To" Country Selector
- To ensure accurate VAT display when in "Incl. VAT" mode (and "Shipping Address" mode is active), a "Ship To" dropdown will be added to the header.
- Changing this updates the session's context for VAT calculations on product pages.

### 4. Checkout Consistency
- The actual charge at checkout remains governed by the rigorous backend logic (based on actual shipping address or admin strict mode).
- The display toggle is purely visual for the browsing experience.

## Implementation Plan

### Backend Changes
1.  **API Update (`app/blueprints/api.py` & `app/utils.py`):**
    -   Update `serialize_product` to include a `vat_rate` field or a `price_incl_vat_cents` field based on the context.
    -   However, strictly speaking, the backend serves the *product*, and the *frontend* usually handles display formatting. A better approach is to expose the **Default Country VAT Rate** via a public configuration endpoint (`/api/settings` or included in the page context) so the frontend can do the math (Price * (1 + VAT)).

### Frontend Changes
1.  **UI Components:**
    -   **Toggle Switch:** Add a toggle in the navbar (`layout.html`).
    -   **Country Selector:** Add a dropdown in the navbar to select the reference country for VAT display.
2.  **JavaScript Logic (`app/static/js/pricing.js`):**
    -   Listen for toggle changes.
    -   Fetch the applicable VAT rate:
        -   From `window.appConfig.defaultVatRate` (injected server-side).
        -   Or via API if the user changes the "Ship To" country.
    -   **Dynamic Price Rendering:**
        -   Update all elements with a class like `.product-price` to render either the base price or `base_price * (1 + vat_rate)`.
        -   Format currency correctly.

## Data Flow Example
1.  Admin sets Default Country = Germany (19%).
2.  User visits Home Page. Default view: **Excl. VAT**. Price: €100.
3.  User toggles "Show VAT".
4.  JS calculates: €100 * 1.19 = €119. Updates DOM to show "€119 (incl. VAT)".
5.  User changes "Ship To" to France (20%).
6.  JS recalculates: €100 * 1.20 = €120. Updates DOM.

## Improvements
- **Badging:** Explicitly label prices as "Excl. VAT" or "Incl. VAT" to avoid confusion.
- **Micro-caching:** Cache VAT rates for countries to avoid repeated API calls.

---
**Next Steps:** Upon approval, we will proceed with the implementation starting with the frontend toggle and context injection.
