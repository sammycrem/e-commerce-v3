from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, current_app, jsonify
from flask_login import login_required, current_user
from app.models import db, User, Order, Address, Message, Country, OrderItem, Promotion, Variant, GlobalSetting
from app.utils import send_emailTls2
from datetime import datetime, timezone, timedelta
from sqlalchemy import desc
import traceback

account_bp = Blueprint('account', __name__, url_prefix='/account')

@account_bp.route('/')
@login_required
def dashboard():
    # Recent orders
    recent_orders = Order.query.filter_by(user_id=current_user.id).order_by(desc(Order.created_at)).limit(5).all()
    # Default addresses
    default_shipping = Address.query.filter_by(user_id=current_user.id, address_type='shipping', is_default=True).first()
    default_billing = Address.query.filter_by(user_id=current_user.id, address_type='billing', is_default=True).first()

    # Fetch active loyalty rewards
    loyalty_rewards = Promotion.query.filter(
        Promotion.user_id == current_user.id,
        Promotion.code.like('LOYALTY-%'),
        Promotion.is_active == True
    ).order_by(desc(Promotion.valid_to)).all()

    return render_template('account/dashboard.html',
                           recent_orders=recent_orders,
                           default_shipping=default_shipping,
                           default_billing=default_billing,
                           loyalty_rewards=loyalty_rewards)

@account_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        email = request.form.get('email')
        phone = request.form.get('phone')

        if email and email.lower() != current_user.email:
             # Check for uniqueness
             if User.query.filter(User.email == email.lower(), User.id != current_user.id).first():
                 flash('Email already in use.', 'danger')
                 return redirect(url_for('account.profile'))
             current_user.email = email.lower()

        current_user.phone = phone
        db.session.commit()
        flash('Profile updated successfully.', 'success')
        return redirect(url_for('account.profile'))

    return render_template('account/profile.html')

@account_bp.route('/orders')
@login_required
def orders():
    print(f"DEBUG: Orders route. User: {current_user.is_authenticated}, ID: {current_user.id if current_user.is_authenticated else 'None'}")
    page = request.args.get('page', 1, type=int)
    per_page = 10
    pagination = Order.query.filter_by(user_id=current_user.id).order_by(desc(Order.created_at)).paginate(page=page, per_page=per_page, error_out=False)

    # Check grace period window for each order
    now = datetime.now(timezone.utc)
    cancellation_window_minutes = 60 # Default
    # Could load from GlobalSettings if we want to make it configurable

    return render_template('account/orders.html', pagination=pagination, now=now, cancellation_window_minutes=cancellation_window_minutes, timezone=timezone)

@account_bp.route('/orders/<string:public_order_id>')
@login_required
def order_detail(public_order_id):
    print(f"DEBUG: Order Detail {public_order_id}. User: {current_user.id}")
    order = Order.query.filter_by(public_order_id=public_order_id, user_id=current_user.id).first_or_404()
    now = datetime.now(timezone.utc)
    cancellation_window_minutes = 60
    return render_template('account/order_detail.html', order=order, now=now, cancellation_window_minutes=cancellation_window_minutes)

@account_bp.route('/orders/<string:public_order_id>/cancel', methods=['POST'])
@login_required
def cancel_order(public_order_id):
    print(f"DEBUG: Cancel Order {public_order_id} for User {current_user.id} ({current_user.username})")
    # Debug: Check if order exists at all
    check = Order.query.filter_by(public_order_id=public_order_id).first()
    print(f"DEBUG: Global search for {public_order_id}: {check}, User ID: {check.user_id if check else 'None'}")

    order = Order.query.filter_by(public_order_id=public_order_id, user_id=current_user.id).first_or_404()

    # Logic: Status Check
    if order.status not in ['PENDING', 'PAID']:
        flash('Order cannot be canceled in its current status.', 'danger')
        return redirect(url_for('account.orders'))

    # Logic: Time Window Check
    created_at = order.created_at.replace(tzinfo=timezone.utc) if order.created_at.tzinfo is None else order.created_at
    now = datetime.now(timezone.utc)
    if (now - created_at).total_seconds() > 3600: # 60 minutes
        flash('Cancellation period has expired.', 'danger')
        return redirect(url_for('account.orders'))

    try:
        # 1. Update Status
        old_status = order.status
        order.status = 'CANCELLED'

        # 2. Inventory Reversion
        # Iterate items and add back stock
        for item in order.items:
            variant = Variant.query.filter_by(sku=item.variant_sku).first()
            if variant:
                variant.stock_quantity += item.quantity

        # 3. Refund Trigger (Mock/Stub for now, or real call if configured)
        if old_status == 'PAID':
            # In a real scenario:
            # from app.mollie_client import get_mollie_client
            # client = get_mollie_client()
            # client.payments.get(order.payment_transaction_id).refund({...})
            # For now, we just log it as part of the flow
            print(f"Refund triggered for Order {order.public_order_id}")

        db.session.commit()
        flash('Order canceled successfully. Refund has been initiated.', 'success')

    except Exception as e:
        db.session.rollback()
        traceback.print_exc()
        flash('An error occurred while canceling the order.', 'danger')

    return redirect(url_for('account.orders'))

@account_bp.route('/orders/<string:public_order_id>/return', methods=['GET', 'POST'])
@login_required
def request_return(public_order_id):
    order = Order.query.filter_by(public_order_id=public_order_id, user_id=current_user.id).first_or_404()

    if order.status != 'DELIVERED':
        flash('Order must be delivered before requesting a return.', 'danger')
        return redirect(url_for('account.orders'))

    if request.method == 'GET':
        return render_template('account/return_request.html', order=order)

    # Handle POST
    try:
        items = request.form.getlist('return_items')
        reason = request.form.get('return_reason')

        if not items:
            flash('Please select at least one item to return.', 'danger')
            return render_template('account/return_request.html', order=order)

        if not reason:
            flash('Please provide a reason for your return.', 'danger')
            return render_template('account/return_request.html', order=order)

        # Update Status
        order.status = 'RETURN_REQUESTED'

        # Create Message with details
        msg_content = f"RETURN REQUEST\n\nReason: {reason}\n\nItems to Return:\n"
        for sku in items:
            # Find item name/qty for better message
            item = next((i for i in order.items if i.variant_sku == sku), None)
            name = item.product_snapshot.get('name', sku) if item else sku
            msg_content += f"- {name} ({sku})\n"

        msg = Message(
            user_id=current_user.id,
            order_id=order.id,
            sender_type='USER',
            content=msg_content,
            created_at=datetime.now(timezone.utc),
            is_read=False
        )
        db.session.add(msg)

        db.session.commit()
        flash('Return requested successfully. An admin will review your request shortly.', 'success')

    except Exception as e:
        db.session.rollback()
        traceback.print_exc()
        flash('Failed to request return.', 'danger')

    return redirect(url_for('account.order_detail', public_order_id=public_order_id))

@account_bp.route('/orders/<string:public_order_id>/reviews', methods=['GET'])
@login_required
def review_order_page(public_order_id):
    order = Order.query.filter_by(public_order_id=public_order_id, user_id=current_user.id).first_or_404()

    # Augment items with current product images if snapshot is missing them (legacy orders)
    from app.models import Product
    from app.utils import serialize_image

    for item in order.items:
        snapshot = item.product_snapshot or {}
        if 'images' not in snapshot or not snapshot['images']:
            # Fetch current product images
            p = Product.query.filter_by(product_sku=item.variant_sku.split('-')[0] if '-' in item.variant_sku else item.variant_sku).first()
            if not p:
                # Try exact SKU match if variant sku isn't structured or fallback
                p = Product.query.filter_by(product_sku=item.variant_sku).first()

            # If product found (even if variant sku logic is fuzzy), use its images
            # Better: use the product_sku from snapshot if available
            if not p and snapshot.get('product_sku'):
                p = Product.query.filter_by(product_sku=snapshot['product_sku']).first()

            if p and p.images:
                # We need to update the snapshot in memory for the template (not saving to DB to preserve history)
                # snapshot is a dict, we can modify it
                snapshot['images'] = [serialize_image(img) for img in p.images]
                # Update the item object (SQLAlchemy objects track changes, but we won't commit)
                item.product_snapshot = snapshot

    return render_template('account/review_order.html', order=order)

@account_bp.route('/orders/<string:public_order_id>/message', methods=['POST'])
@login_required
def send_order_message(public_order_id):
    order = Order.query.filter_by(public_order_id=public_order_id, user_id=current_user.id).first_or_404()
    content = request.form.get('content')

    if content:
        msg = Message(
            user_id=current_user.id,
            order_id=order.id,
            sender_type='USER',
            content=content,
            created_at=datetime.now(timezone.utc),
            is_read=False # Admin hasn't read it
        )
        db.session.add(msg)
        db.session.commit()
        flash('Message sent to administrator.', 'success')

    else:
        flash('Message cannot be empty.', 'danger')

    return redirect(url_for('account.order_detail', public_order_id=public_order_id))

@account_bp.route('/addresses')
@login_required
def addresses():
    user_addresses = Address.query.filter_by(user_id=current_user.id).order_by(Address.is_default.desc()).all()
    return render_template('account/addresses.html', addresses=user_addresses)

@account_bp.route('/addresses/add', methods=['GET', 'POST'])
@login_required
def add_address():
    countries = Country.query.order_by(Country.name).all()
    if request.method == 'POST':
        # logic to add address
        addr = Address(
            user_id=current_user.id,
            address_type=request.form.get('address_type'),
            first_name=request.form.get('first_name'),
            last_name=request.form.get('last_name'),
            address_line_1=request.form.get('address_line_1'),
            address_line_2=request.form.get('address_line_2'),
            city=request.form.get('city'),
            state=request.form.get('state'),
            postal_code=request.form.get('postal_code'),
            country_iso_code=request.form.get('country_iso_code'),
            phone_number=request.form.get('phone_number'),
            is_default=bool(request.form.get('is_default'))
        )

        if addr.is_default:
            # Unset other defaults of same type
            Address.query.filter_by(user_id=current_user.id, address_type=addr.address_type).update({'is_default': False})

        db.session.add(addr)
        db.session.commit()
        flash('Address added.', 'success')
        return redirect(url_for('account.addresses'))

    return render_template('account/address_form.html', countries=countries, address=None)

@account_bp.route('/addresses/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_address(id):
    address = Address.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    countries = Country.query.order_by(Country.name).all()

    if request.method == 'POST':
        address.address_type = request.form.get('address_type')
        address.first_name = request.form.get('first_name')
        address.last_name = request.form.get('last_name')
        address.address_line_1 = request.form.get('address_line_1')
        address.address_line_2 = request.form.get('address_line_2')
        address.city = request.form.get('city')
        address.state = request.form.get('state')
        address.postal_code = request.form.get('postal_code')
        address.country_iso_code = request.form.get('country_iso_code')
        address.phone_number = request.form.get('phone_number')

        if bool(request.form.get('is_default')):
            Address.query.filter_by(user_id=current_user.id, address_type=address.address_type).update({'is_default': False})
            address.is_default = True

        db.session.commit()
        flash('Address updated.', 'success')
        return redirect(url_for('account.addresses'))

    return render_template('account/address_form.html', countries=countries, address=address)

@account_bp.route('/addresses/<int:id>/delete', methods=['POST'])
@login_required
def delete_address(id):
    address = Address.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    db.session.delete(address)
    db.session.commit()
    flash('Address deleted.', 'success')
    return redirect(url_for('account.addresses'))
