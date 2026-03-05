from flask import Blueprint, request, jsonify, session, render_template, flash, redirect, url_for
from flask_login import login_required, current_user
from ..extensions import db, csrf
from ..models import Promotion, Order, OrderItem, Variant
from ..utils import calculate_totals_internal, process_loyalty_reward, send_emailTls2, send_order_status_update_email
from ..mollie_client import get_mollie_client
from ..stripe_client import get_stripe_client
from datetime import datetime, timezone
from math import ceil
import logging
from flask import current_app

logger = logging.getLogger('app.' + __name__)

checkout_bp = Blueprint('checkout_bp', __name__)

from ..models import Address

def get_effective_shipping_address(user_id):
    """Retrieves the session-selected shipping address or falls back to the first available one (prioritizing default)."""
    shipping_address_id = session.get('shipping_address_id')
    if shipping_address_id:
        # Use .get() if possible, but stay compatible with standard query if needed
        addr = Address.query.filter_by(id=shipping_address_id, user_id=user_id, address_type='shipping').first()
        if addr:
            return addr

    # Fallback: find default shipping address, otherwise first available
    addr = Address.query.filter_by(user_id=user_id, address_type='shipping', is_default=True).first()
    if not addr:
        addr = Address.query.filter_by(user_id=user_id, address_type='shipping').first()
    return addr

@checkout_bp.route('/api/create-payment-intent', methods=['POST'])
@login_required
def create_payment_intent():
    try:
        data = request.get_json() or {}
        items = data.get('items', [])
        shipping_country_iso = data.get('shipping_country_iso')
        shipping_method = data.get('shipping_method') or session.get('shipping_method', 'standard')
        promo_code = data.get('promo_code') or session.get('promo_code')

        if not shipping_country_iso:
            address = get_effective_shipping_address(current_user.id)
            if address:
                shipping_country_iso = address.country_iso_code

        # Calculate amount securely on server
        calc_res = calculate_totals_internal(items, shipping_country_iso=shipping_country_iso, shipping_method=shipping_method, promo_code=promo_code, user_id=current_user.id)
        total_amount = calc_res['total_cents']

        stripe = get_stripe_client()
        intent = stripe.PaymentIntent.create(
            amount=total_amount,
            currency=current_app.config.get('APP_DEFAULT_CURRENCY', 'eur').lower(),
            automatic_payment_methods={
                'enabled': True,
            },
            metadata={
                'user_id': current_user.id
            }
        )
        return jsonify({'clientSecret': intent.client_secret}), 200
    except Exception as e:
        logger.exception("Stripe Intent Creation Failed")
        return jsonify({'error': str(e)}), 403

@checkout_bp.route('/api/apply-promo', methods=['POST'])
def apply_promo():
    data = request.get_json() or {}
    code = data.get('code')
    cart_subtotal = data.get('cart_subtotal_cents')
    user_id = current_user.id if current_user.is_authenticated else None

    if not code or cart_subtotal is None:
        return jsonify({"error": "Promo code and cart subtotal are required"}), 400

    promo = Promotion.query.filter_by(code=code, is_active=True).first()
    if not promo:
        return jsonify({"error": "Invalid promotion code"}), 404

    promo_valid_to = promo.valid_to
    # Ensure timezone-aware comparison to avoid TypeError regarding aware vs naive datetimes
    if promo_valid_to and promo_valid_to.tzinfo is None:
        promo_valid_to = promo_valid_to.replace(tzinfo=timezone.utc)

    if promo_valid_to and promo_valid_to < datetime.now(timezone.utc):
        return jsonify({"error": "Promotion code has expired"}), 404

    if promo.user_id is not None and promo.user_id != user_id:
        return jsonify({"error": "This promotion code is not valid for your account"}), 403

    if user_id:
        existing_usage = Order.query.filter_by(user_id=user_id, promo_code=code).first()
        if existing_usage:
            return jsonify({"error": "You have already used this promotion code"}), 403

    discount_cents = 0
    if promo.discount_type == 'PERCENT':
        from ..utils import cents_to_decimal, decimal_to_cents
        from decimal import Decimal
        pct = Decimal(promo.discount_value) / Decimal(100)
        discount_decimal = cents_to_decimal(cart_subtotal) * pct
        discount_cents = decimal_to_cents(discount_decimal)
    elif promo.discount_type == 'FIXED':
        discount_cents = int(promo.discount_value)

    # Store promo code in session for persistence across checkout steps
    session['promo_code'] = promo.code
    session.modified = True
    return jsonify({"code": promo.code, "discount_cents": discount_cents, "new_total_cents": cart_subtotal - discount_cents}), 200

@checkout_bp.route('/api/checkout', methods=['POST'])
def checkout():
    body = request.get_json() or {}
    shipping_country_iso = body.get('shipping_country_iso') or body.get('country_iso')
    user_id = current_user.id if current_user.is_authenticated else None

    # get cart from session
    cart_info = session.get('cart', {})
    if not cart_info:
        return jsonify({"error": "Cannot checkout with an empty cart"}), 400

    # create simple items list for calculation
    items = [{"sku": sku, "quantity": qty} for sku, qty in cart_info.items()]

    # calculate totals using helper
    promo_code = body.get('promo_code')
    shipping_method = body.get('shipping_method', 'standard')
    payment_method = body.get('payment_method')
    calc_res = calculate_totals_internal(items, shipping_country_iso=shipping_country_iso, promo_code=promo_code, shipping_method=shipping_method, user_id=user_id)

    subtotal = calc_res['subtotal_cents']
    discount = calc_res['discount_cents']
    vat = calc_res['vat_cents']
    shipping_cost = calc_res['shipping_cost_cents']
    total = calc_res['total_cents']

    try:
        with db.session.begin_nested():
            new_order = Order(
                status='PENDING',
                subtotal_cents=subtotal,
                discount_cents=discount,
                vat_cents=vat,
                shipping_cost_cents=shipping_cost,
                total_cents=total,
                promo_code=promo_code,
                shipping_method=shipping_method,
                payment_method=payment_method,
                payment_provider=payment_method
            )
            # optionally store shipping country or address fields here
            db.session.add(new_order)
            db.session.flush()

            for item_data in items:
                variant = Variant.query.filter_by(sku=item_data['sku']).with_for_update().first()
                if not variant:
                    raise ValueError(f"Variant not found: {item_data['sku']}")

                if variant.product.status != 'published':
                    raise ValueError(f"Product '{variant.product.name}' is no longer available")

                if variant.stock_quantity < item_data['quantity']:
                    raise ValueError(f"Insufficient stock for {item_data['sku']}")
                variant.stock_quantity -= item_data['quantity']

                product_snapshot = {
                    "name": variant.product.name,
                    "product_sku": variant.product.product_sku,
                    "category": variant.product.category,
                    "weight_grams": variant.product.weight_grams,
                    "dimensions_json": variant.product.dimensions_json
                }
                unit_price = int((variant.product.base_price_cents or 0) + (variant.price_modifier_cents or 0))
                order_item = OrderItem(
                    order_id=new_order.id,
                    variant_sku=item_data['sku'],
                    quantity=item_data['quantity'],
                    unit_price_cents=unit_price,
                    product_snapshot=product_snapshot
                )
                db.session.add(order_item)

        db.session.commit()
        session.pop('cart', None)
        return jsonify({
            "message": "Order created successfully",
            "order_id": new_order.public_order_id,
            "subtotal_cents": subtotal,
            "discount_cents": discount,
            "vat_cents": vat,
            "shipping_cost_cents": shipping_cost,
            "total_cents": total
        }), 201

    except ValueError as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        db.session.rollback()
        logger.exception("Checkout failed")
        return jsonify({"error": "An internal error occurred", "details": str(e)}), 500

@checkout_bp.route('/webhooks/payment', methods=['POST'])
def handle_payment_webhook():
    data = request.get_json() or {}
    order_id = data.get('metadata', {}).get('public_order_id')
    event_type = data.get('type')
    if event_type == 'charge.succeeded' and order_id:
        order = Order.query.filter_by(public_order_id=order_id).first()
        if order and order.status == 'PENDING':
            order.status = 'PAID'
            db.session.commit()
            process_loyalty_reward(order)
            send_order_status_update_email(order)
            logger.info("Webhook: Order %s set to PAID", order.public_order_id)
            return jsonify({"status": "success"}), 200
        elif order:
            return jsonify({"status": "already_processed"}), 200
    return jsonify({"status": "ignored"}), 200

@checkout_bp.route('/api/calculate-totals', methods=['POST'])
def api_calculate_totals():
    data = request.get_json() or {}
    items = data.get('items', [])
    country_iso = data.get('shipping_country_iso')
    promo_code = data.get('promo_code')
    shipping_method = data.get('shipping_method', 'standard')
    user_id = current_user.id if current_user.is_authenticated else None

    result = calculate_totals_internal(items, shipping_country_iso=country_iso, promo_code=promo_code, shipping_method=shipping_method, user_id=user_id)
    return jsonify(result), 200

@checkout_bp.route('/checkout/login', methods=['GET'])
def checkout_login():
    return render_template('checkout_login.html')

from ..models import Address, Country
from flask_login import current_user

@checkout_bp.route('/checkout/shipping-address', methods=['GET', 'POST'])
@login_required
def shipping_address():
    if request.method == 'POST':
        # Check if the request is for selecting an address
        if 'select_address' in request.form:
            address_id = request.form.get('address_id')
            address = Address.query.get_or_404(address_id)
            if address.user_id == current_user.id and address.address_type == 'shipping':
                session['shipping_address_id'] = address.id
                session.modified = True
                flash('Shipping address selected.', 'success')
                return redirect(url_for('checkout_bp.shipping_methods'))
            else:
                flash('Invalid address selection.', 'danger')
                return redirect(url_for('checkout_bp.shipping_address'))

        # Check if the request is for deleting an address
        if 'delete_address' in request.form:
            address_id = request.form.get('address_id')
            address_to_delete = Address.query.get_or_404(address_id)
            if address_to_delete.user_id == current_user.id:
                if session.get('shipping_address_id') == address_to_delete.id:
                    session.pop('shipping_address_id', None)
                db.session.delete(address_to_delete)
                db.session.commit()
                flash('Address deleted successfully!', 'success')
            else:
                flash('You are not authorized to delete this address.', 'danger')
            return redirect(url_for('checkout_bp.shipping_address'))

        # Handle adding a new address
        address = Address(
            user_id=current_user.id,
            address_type=request.form.get('address_type'),
            first_name=request.form.get('first_name'),
            last_name=request.form.get('last_name'),
            address_line_1=request.form.get('address_line_1'),
            address_line_2=request.form.get('address_line_2'),
            city=request.form.get('city'),
            state=request.form.get('state'),
            postal_code=request.form.get('postal_code'),
            country_iso_code=request.form.get('country'),
            phone_number=request.form.get('phone_number')
        )
        db.session.add(address)
        db.session.commit()
        flash('Address added successfully!', 'success')
        return redirect(url_for('checkout_bp.shipping_address'))

    addresses = Address.query.filter_by(user_id=current_user.id).all()
    countries = Country.query.all()
    cart_info = session.get('cart', {})
    items = [{"sku": sku, "quantity": qty} for sku, qty in cart_info.items()]
    promo_code = session.get('promo_code')
    user_id = current_user.id if current_user.is_authenticated else None
    cart_summary = calculate_totals_internal(items, promo_code=promo_code, user_id=user_id)
    return render_template('shipping_address.html', addresses=addresses, cart_summary=cart_summary, countries=countries)

@checkout_bp.route('/checkout/edit-address/<int:address_id>', methods=['GET', 'POST'])
@login_required
def edit_address(address_id):
    address = Address.query.get_or_404(address_id)
    if address.user_id != current_user.id:
        flash('You are not authorized to edit this address.', 'danger')
        return redirect(url_for('checkout_bp.shipping_address'))

    if request.method == 'POST':
        address.address_type = request.form.get('address_type')
        address.first_name = request.form.get('first_name')
        address.last_name = request.form.get('last_name')
        address.address_line_1 = request.form.get('address_line_1')
        address.address_line_2 = request.form.get('address_line_2')
        address.city = request.form.get('city')
        address.state = request.form.get('state')
        address.postal_code = request.form.get('postal_code')
        address.country_iso_code = request.form.get('country')
        address.phone_number = request.form.get('phone_number')
        db.session.commit()
        flash('Address updated successfully!', 'success')
        return redirect(url_for('checkout_bp.shipping_address'))

    countries = Country.query.all()
    return render_template('edit_address.html', address=address, countries=countries)

@checkout_bp.route('/checkout/shipping-methods', methods=['GET'])
@login_required
def shipping_methods():
    cart_info = session.get('cart', {})
    if not cart_info:
        return redirect(url_for('cart_bp.cart_page'))

    items = [{"sku": sku, "quantity": qty} for sku, qty in cart_info.items()]

    # Get the user's shipping address
    shipping_address = get_effective_shipping_address(current_user.id)

    if not shipping_address:
        flash('Please add a shipping address before proceeding.', 'warning')
        return redirect(url_for('checkout_bp.shipping_address'))

    country_iso = shipping_address.country_iso_code

    selected_shipping = session.get('shipping_method', 'standard')
    promo_code = session.get('promo_code')
    user_id = current_user.id if current_user.is_authenticated else None
    cart_summary = calculate_totals_internal(items, shipping_country_iso=country_iso, shipping_method=selected_shipping, promo_code=promo_code, user_id=user_id)
    return render_template('shipping_methods.html', cart_summary=cart_summary, selected_shipping=selected_shipping)

@checkout_bp.route('/checkout/shipping-methods-save', methods=['POST'])
@login_required
def shipping_methods_save():
    shipping_method = request.form.get('shipping_method')
    if shipping_method:
        session['shipping_method'] = shipping_method
        return redirect(url_for('checkout_bp.payment_methods'))
    flash('Please select a shipping method.', 'danger')
    return redirect(url_for('checkout_bp.shipping_methods'))

@checkout_bp.route('/checkout/payment-methods', methods=['GET', 'POST'])
@login_required
def payment_methods():
    cart_info = session.get('cart', {})
    if not cart_info:
        return redirect(url_for('cart_bp.cart_page'))

    if request.method == 'POST':
        payment_method = request.form.get('payment_method')
        if payment_method:
            session['payment_method'] = payment_method
            return redirect(url_for('checkout_bp.summary'))
        flash('Please select a payment method.', 'danger')

    items = [{"sku": sku, "quantity": qty} for sku, qty in cart_info.items()]

    # Get the user's shipping address for calculation
    shipping_address_obj = get_effective_shipping_address(current_user.id)

    if not shipping_address_obj:
        flash('Please add a shipping address before proceeding.', 'warning')
        return redirect(url_for('checkout_bp.shipping_address'))

    billing_address_obj = Address.query.filter_by(user_id=current_user.id, address_type='billing').first()
    # Fallback to shipping address if billing address is not set
    if not billing_address_obj:
        billing_address_obj = shipping_address_obj

    country_iso = shipping_address_obj.country_iso_code

    # We also need the shipping cost from the previous step
    # For now, we'll just recalculate based on standard or get from session if stored
    # Ideally, we should have the selected shipping method in session
    selected_shipping = session.get('shipping_method', 'standard')
    promo_code = session.get('promo_code')
    user_id = current_user.id if current_user.is_authenticated else None

    cart_summary = calculate_totals_internal(items, shipping_country_iso=country_iso, shipping_method=selected_shipping, promo_code=promo_code, user_id=user_id)

    return render_template('payment_methods.html', cart_summary=cart_summary, country_iso=country_iso, selected_shipping=selected_shipping)

@checkout_bp.route('/checkout/summary', methods=['GET', 'POST'])
@login_required
def summary():
    cart_info = session.get('cart', {})
    if not cart_info:
        return redirect(url_for('cart_bp.cart_page'))

    items_list = [{"sku": sku, "quantity": qty} for sku, qty in cart_info.items()]

    shipping_address_obj = get_effective_shipping_address(current_user.id)

    if not shipping_address_obj:
        flash('Please add a shipping address before proceeding.', 'warning')
        return redirect(url_for('checkout_bp.shipping_address'))

    billing_address_obj = Address.query.filter_by(user_id=current_user.id, address_type='billing').first()
    if not billing_address_obj:
        billing_address_obj = shipping_address_obj

    country_iso = shipping_address_obj.country_iso_code

    selected_shipping = session.get('shipping_method', 'standard')
    selected_payment = session.get('payment_method', 'card')
    promo_code = session.get('promo_code') # Assuming promo_code might be in session
    user_id = current_user.id if current_user.is_authenticated else None

    cart_summary = calculate_totals_internal(items_list, shipping_country_iso=country_iso, shipping_method=selected_shipping, promo_code=promo_code, user_id=user_id)

    if request.method == 'POST':
        comment = request.form.get('comment')

        # Resolve variants for order items
        skus = [it.get('sku') for it in items_list]
        variants = Variant.query.filter(Variant.sku.in_(skus)).all()
        variant_map = {v.sku: v for v in variants}

        def serialize_address(addr):
            return {
                "first_name": addr.first_name,
                "last_name": addr.last_name,
                "address_line_1": addr.address_line_1,
                "address_line_2": addr.address_line_2,
                "city": addr.city,
                "state": addr.state,
                "postal_code": addr.postal_code,
                "country_iso_code": addr.country_iso_code,
                "phone_number": addr.phone_number
            }

        try:
            with db.session.begin_nested():
                # Allow overriding payment intent via JSON if needed for Stripe
                payment_intent_id = request.form.get('payment_intent_id') or (request.json.get('payment_intent_id') if request.is_json else None)

                new_order = Order(
                    user_id=current_user.id,
                    status='PENDING',
                    subtotal_cents=cart_summary['subtotal_cents'],
                    discount_cents=cart_summary['discount_cents'],
                    vat_cents=cart_summary['vat_cents'],
                    shipping_cost_cents=cart_summary['shipping_cost_cents'],
                    total_cents=cart_summary['total_cents'],
                    shipping_method=selected_shipping,
                    payment_method=selected_payment,
                    payment_provider=selected_payment,
                    payment_transaction_id=payment_intent_id if selected_payment == 'stripe' else None,
                    comment=comment,
                    promo_code=promo_code,
                    shipping_address_snapshot=serialize_address(shipping_address_obj),
                    billing_address_snapshot=serialize_address(billing_address_obj)
                )
                db.session.add(new_order)
                db.session.flush()

                for it in items_list:
                    v = variant_map.get(it['sku'])
                    if not v: continue

                    product_snapshot = {
                        "name": v.product.name,
                        "product_sku": v.product.product_sku,
                        "category": v.product.category,
                        "weight_grams": v.product.weight_grams,
                        "dimensions_json": v.product.dimensions_json
                    }
                    unit_price = int((v.product.base_price_cents or 0) + (v.price_modifier_cents or 0))
                    order_item = OrderItem(
                        order_id=new_order.id,
                        variant_sku=it['sku'],
                        quantity=it['quantity'],
                        unit_price_cents=unit_price,
                        product_snapshot=product_snapshot
                    )
                    db.session.add(order_item)

                    # Update stock
                    if v.stock_quantity < it['quantity']:
                        raise ValueError(f"Insufficient stock for {v.sku}")
                    v.stock_quantity -= it['quantity']

            db.session.commit()

            # Send order confirmation email
            try:
                sender_email = current_app.config.get('APP_EMAIL_SENDER')
                smtp_password = current_app.config.get('APP_EMAIL_PASSWORD')
                smtp_server = current_app.config.get('APP_SMTP_SERVER')
                smtp_port = int(current_app.config.get('APP_SMTP_PORT', 587))

                if sender_email and smtp_password:
                    subject = f"Order Confirmation - {new_order.public_order_id}"
                    symbol = current_app.config.get('currency_symbol', '€')

                    body = render_template('emails/order_confirmation.html',
                                           order=new_order,
                                           currency_symbol=symbol)

                    send_emailTls2(sender_email, smtp_password, smtp_server, smtp_port, current_user.email, subject, body)
                    logger.debug(f"Email sent to: {current_user.email}")
            except Exception as email_err:
                logger.error(f"Failed to send order confirmation email: {email_err}")

            if selected_payment == 'mollie':
                try:
                    mollie_client = get_mollie_client()
                    currency = current_app.config.get('APP_DEFAULT_CURRENCY', 'EUR').upper()
                    amount_val = "{:.2f}".format(new_order.total_cents / 100)
                    payment = mollie_client.payments.create({
                        'amount': {
                            'currency': currency,
                            'value': amount_val
                        },
                        'description': f'Order {new_order.public_order_id}',
                        'redirectUrl': url_for('checkout_bp.mollie_return', order_id=new_order.public_order_id, _external=True),
                        'webhookUrl': url_for('checkout_bp.handle_mollie_webhook', _external=True),
                        'metadata': {
                            'order_id': new_order.public_order_id
                        }
                    })

                    new_order.payment_transaction_id = payment.id
                    db.session.commit()

                    # Do not clear session yet, wait for payment confirmation (return url)
                    # so user can retry if payment fails/cancels.

                    return redirect(payment.checkout_url)
                except ValueError as e:
                    logger.error(f"Mollie configuration error: {e}")
                    flash(f'Payment configuration error: {str(e)}. Please try another payment method.', 'danger')
                    return redirect(url_for('checkout_bp.payment_methods'))
                except Exception as e:
                    logger.error(f"Mollie payment creation failed: {e}")
                    flash(f'Payment initiation failed. Please try again or contact support. Error: {str(e)}', 'danger')
                    return redirect(url_for('checkout_bp.payment_methods'))

            elif selected_payment == 'stripe':
                # The frontend has already created the payment intent and just submitted the form
                # to create the order record. The frontend will then handle the confirmPayment call.
                # We need to return JSON if this is an AJAX request from our new Stripe flow.

                if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    # Return success for AJAX so frontend can proceed with stripe.confirmPayment
                    # We might want to update the PaymentIntent with the Order ID here for webhook reconciliation
                    try:
                        stripe = get_stripe_client()
                        stripe.PaymentIntent.modify(
                            new_order.payment_transaction_id,
                            metadata={'public_order_id': new_order.public_order_id}
                        )
                    except Exception as e:
                        logger.error(f"Failed to update Stripe metadata: {e}")

                    # Clear session as order is created (payment pending confirmation)
                    session.pop('cart', None)
                    return jsonify({'success': True, 'order_id': new_order.public_order_id}), 200
                else:
                    # Fallback for non-JS flow (unlikely for Stripe Elements)
                    pass

            session.pop('cart', None)
            session.pop('shipping_method', None)
            session.pop('payment_method', None)
            flash('Order placed successfully!', 'success')
            return redirect(url_for('checkout_bp.order_success', order_id=new_order.public_order_id))
        except Exception as e:
            db.session.rollback()
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'error': str(e)}), 400
            flash(f'An error occurred: {str(e)}', 'danger')

    # Get actual objects for display
    display_items = []
    for sku, qty in cart_info.items():
        v = Variant.query.filter_by(sku=sku).first()
        if v:
            display_items.append({'variant': v, 'quantity': qty})

    return render_template('summary.html',
                           cart_summary=cart_summary,
                           shipping_address=shipping_address_obj,
                           display_items=display_items,
                           selected_shipping=selected_shipping,
                           selected_payment=selected_payment)

@checkout_bp.route('/checkout/mollie-return/<order_id>')
@login_required
def mollie_return(order_id):
    order = Order.query.filter_by(public_order_id=order_id, user_id=current_user.id).first_or_404()

    try:
        mollie_client = get_mollie_client()
        if order.payment_transaction_id:
            payment = mollie_client.payments.get(order.payment_transaction_id)

            if payment.is_paid():
                if order.status != 'PAID':
                    order.status = 'PAID'
                    db.session.commit()
                    process_loyalty_reward(order)
                    send_order_status_update_email(order)
                # Clear session now that payment is confirmed
                session.pop('cart', None)
                session.pop('shipping_method', None)
                session.pop('payment_method', None)
                return redirect(url_for('checkout_bp.order_success', order_id=order_id))

            elif payment.is_canceled():
                 if order.status == 'PENDING':
                    order.status = 'CANCELLED'
                    db.session.commit()
                 flash('Payment was cancelled. You can try again with a different method.', 'warning')
                 return redirect(url_for('checkout_bp.payment_methods'))

            elif payment.is_failed():
                 if order.status == 'PENDING':
                    order.status = 'FAILED'
                    db.session.commit()
                 flash('Payment failed. Please try again.', 'danger')
                 return redirect(url_for('checkout_bp.payment_methods'))

            elif payment.is_open() or payment.is_pending():
                 # For open/pending, we usually clear cart because order is placed.
                 # User shouldn't re-submit.
                 session.pop('cart', None)
                 session.pop('shipping_method', None)
                 session.pop('payment_method', None)
                 return redirect(url_for('checkout_bp.order_success', order_id=order_id))

    except Exception as e:
        logger.error(f"Error checking Mollie payment status: {e}")
        flash('Could not verify payment status. Please check your email for confirmation.', 'warning')

    return redirect(url_for('checkout_bp.order_success', order_id=order_id))

@checkout_bp.route('/webhooks/mollie', methods=['POST'])
@csrf.exempt
def handle_mollie_webhook():
    try:
        if 'id' not in request.form:
            return '', 200

        payment_id = request.form['id']
        mollie_client = get_mollie_client()
        payment = mollie_client.payments.get(payment_id)

        order_id = payment.metadata.get('order_id')
        if not order_id:
            logger.warning(f"Mollie webhook: No order_id in metadata for payment {payment_id}")
            return '', 200

        order = Order.query.filter_by(public_order_id=order_id).first()
        if not order:
            logger.warning(f"Mollie webhook: Order {order_id} not found")
            return '', 200

        if payment.is_paid():
            if order.status != 'PAID':
                order.status = 'PAID'
                db.session.commit()
                process_loyalty_reward(order)
                send_order_status_update_email(order)
                logger.info(f"Order {order_id} paid via Mollie")
        elif payment.is_canceled() or payment.is_expired():
             if order.status == 'PENDING':
                order.status = 'CANCELLED'
                db.session.commit()
                logger.info(f"Order {order_id} canceled/expired via Mollie")
        elif payment.is_failed():
             if order.status == 'PENDING':
                order.status = 'FAILED'
                db.session.commit()
                logger.info(f"Order {order_id} failed via Mollie")

        return '', 200
    except Exception as e:
        logger.error(f"Mollie webhook error: {e}")
        return '', 500

@checkout_bp.route('/webhooks/stripe', methods=['POST'])
@csrf.exempt
def handle_stripe_webhook():
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')

    try:
        stripe = get_stripe_client()
        # You'd typically verify the signature here with a webhook secret from config
        # event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
        # For MVP/Sandbox without configured secret, we trust the event structure (or parse directly)
        event = stripe.Event.construct_from(request.json, stripe.api_key)
    except ValueError as e:
        return 'Invalid payload', 400
    except stripe.error.SignatureVerificationError as e:
        return 'Invalid signature', 400

    if event.type == 'payment_intent.succeeded':
        payment_intent = event.data.object
        # The order ID should be in metadata if we updated it during checkout/summary
        order_id = payment_intent.metadata.get('public_order_id')

        if order_id:
            order = Order.query.filter_by(public_order_id=order_id).first()
            if order and order.status != 'PAID':
                order.status = 'PAID'
                db.session.commit()
                process_loyalty_reward(order)
                send_order_status_update_email(order)
                logger.info(f"Order {order_id} paid via Stripe")
        else:
             logger.warning(f"Stripe webhook: No order_id in metadata for payment {payment_intent.id}")

    return jsonify({'status': 'success'}), 200

@checkout_bp.route('/checkout/success/<order_id>')
@login_required
def order_success(order_id):
    order = Order.query.filter_by(public_order_id=order_id, user_id=current_user.id).first_or_404()
    return render_template('order_success.html', order=order, order_id=order_id)
