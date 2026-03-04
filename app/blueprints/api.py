# Add Import/Export logic to api.py
# (This overwrites previous api.py content, so I must include everything or append)
# I will rewrite api.py with everything included.

from flask import Blueprint, jsonify, request, abort
from flask_login import login_required, current_user
from ..models import Product, Variant, ProductImage, VariantImage, Order, OrderItem, Promotion, Country, VatRate, ShippingZone, Category, GlobalSetting, AppCurrency, Message, Address, User, Review, ProductGroup
from ..extensions import db, cache, limiter
from sqlalchemy.orm import joinedload
from sqlalchemy import desc, func, case
from ..utils import serialize_product, serialize_promotion, generate_image_icon, convert_to_webp, ensure_icon_for_url, serialize_review, process_loyalty_reward, resize_image_max_height, serialize_group, serialize_category, slugify, send_order_status_update_email
from ..product_service import products_to_csv, parse_products_file, _create_product_internal, _update_product_internal
from ..seeder import setup_database
import os
import uuid
import json
import csv
import io
import traceback
from werkzeug.utils import secure_filename
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from flask import current_app

api_bp = Blueprint('api', __name__, url_prefix='/api')

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def check_admin():
    admin_user = current_app.config.get('APP_ADMIN_USER')
    if not current_user.is_authenticated or current_user.username != admin_user:
        abort(403)

# Public Product APIs
@api_bp.route('/products', methods=['GET'])
@cache.cached(timeout=60, query_string=True)
def list_products():
    print("DEBUG: list_products executing query...")
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    category = request.args.get('category', type=str)
    group_id = request.args.get('group_id', type=int)
    group_slug = request.args.get('group_slug', type=str)

    query = Product.query.options(
        joinedload(Product.images),
        joinedload(Product.variants).joinedload(Variant.images)
    )
    # Public API: only published products
    query = query.filter_by(status='published')

    if group_id or group_slug:
        if not group_id:
            g = ProductGroup.query.filter_by(slug=group_slug, is_active=True).first()
            if g: group_id = g.id
            else:
                # Group requested but not found/active
                return jsonify({"products": [], "total": 0, "page": page, "pages": 0}), 200

        query = query.join(Product.groups).filter(ProductGroup.id == group_id)
    elif category:
        # Try to resolve category slug to name
        c = Category.query.filter_by(slug=category).first()
        cat_name = c.name if c else category
        query = query.filter_by(category=cat_name)

    q = request.args.get('q', type=str)
    if q:
        query = query.filter(Product.name.ilike(f"%{q}%"))

    paginated = query.order_by(Product.name).paginate(page=page, per_page=per_page, error_out=False)
    return jsonify({
        "products": [serialize_product(p, include_reviews=False) for p in paginated.items],
        "total": paginated.total,
        "page": paginated.page,
        "pages": paginated.pages
    }), 200

@api_bp.route('/products/<string:sku>', methods=['GET'])
@cache.memoize(timeout=300)
def get_product(sku):
    product = Product.query.options(
        joinedload(Product.images),
        joinedload(Product.variants).joinedload(Variant.images),
        joinedload(Product.reviews).joinedload(Review.user)
    ).filter_by(product_sku=sku, status='published').first_or_404()
    return jsonify(serialize_product(product)), 200

@api_bp.route('/products/batch', methods=['GET'])
def get_products_batch():
    skus = request.args.getlist('sku')
    if not skus:
        return jsonify([]), 200
    products = Product.query.options(
        joinedload(Product.images),
        joinedload(Product.variants)
    ).filter(Product.product_sku.in_(skus)).all()
    product_map = {p.product_sku: serialize_product(p, include_reviews=False) for p in products}
    result = [product_map[sku] for sku in skus if sku in product_map]
    return jsonify(result), 200

@api_bp.route('/products/<string:sku>/reviews', methods=['POST'])
@login_required
def add_product_review(sku):
    product = Product.query.filter_by(product_sku=sku).first_or_404()
    data = request.get_json() or {}

    # Check if user has ordered this product
    variant_skus = [v.sku for v in product.variants]
    has_ordered = db.session.query(OrderItem).join(Order).filter(
        Order.user_id == current_user.id,
        OrderItem.variant_sku.in_(variant_skus)
    ).count() > 0

    if not has_ordered:
        return jsonify({"error": "You must purchase this product to leave a review."}), 403

    rating = int(data.get('rating', 0))
    comment = data.get('comment', '').strip()

    if not (1 <= rating <= 5):
        return jsonify({"error": "Rating must be between 1 and 5"}), 400
    if not comment:
        return jsonify({"error": "Comment is required"}), 400

    # Check if user already reviewed
    existing = Review.query.filter_by(user_id=current_user.id, product_id=product.id).first()
    if existing:
        return jsonify({"error": "You have already reviewed this product"}), 409

    review = Review(
        user_id=current_user.id,
        product_id=product.id,
        rating=rating,
        comment=comment,
        created_at=datetime.now(timezone.utc)
    )
    db.session.add(review)
    db.session.commit()

    # Invalidate product cache
    try:
        cache.delete_memoized(get_product, sku)
    except Exception:
        # Cache invalidation can fail in tests if not properly set up
        pass

    return jsonify(serialize_review(review)), 201

@api_bp.route('/products/<string:sku>/reviews', methods=['PUT'])
@login_required
def update_product_review(sku):
    product = Product.query.filter_by(product_sku=sku).first_or_404()
    data = request.get_json() or {}

    rating = int(data.get('rating', 0))
    comment = data.get('comment', '').strip()

    if not (1 <= rating <= 5):
        return jsonify({"error": "Rating must be between 1 and 5"}), 400
    if not comment:
        return jsonify({"error": "Comment is required"}), 400

    review = Review.query.filter_by(user_id=current_user.id, product_id=product.id).first()
    if not review:
        return jsonify({"error": "Review not found"}), 404

    review.rating = rating
    review.comment = comment
    # Optionally update created_at or add updated_at field
    # review.created_at = datetime.now(timezone.utc)

    db.session.commit()

    try:
        cache.delete_memoized(get_product, sku)
    except Exception:
        pass

    return jsonify(serialize_review(review)), 200

@api_bp.route('/products/<string:sku>/reviews', methods=['GET'])
def get_product_reviews(sku):
    product = Product.query.filter_by(product_sku=sku).first_or_404()
    reviews = Review.query.options(joinedload(Review.user)).filter_by(product_id=product.id).order_by(desc(Review.created_at)).all()
    return jsonify([serialize_review(r) for r in reviews]), 200

@api_bp.route('/categories', methods=['GET'])
@cache.cached(timeout=3600)
def get_public_categories():
    categories = Category.query.order_by(Category.name).all()
    return jsonify([{"id": c.id, "name": c.name, "slug": c.slug} for c in categories]), 200

@api_bp.route('/countries/public', methods=['GET'])
@cache.cached(timeout=3600)
def get_public_countries():
    countries = Country.query.order_by(Country.name).all()
    data = []
    for c in countries:
        data.append({
            "id": c.id,
            "name": c.name,
            "iso_code": c.iso_code,
            "vat_rate": float(c.default_vat_rate)
        })
    return jsonify(data), 200

# Public Settings
@api_bp.route('/settings', methods=['GET'])
@cache.cached(timeout=3600)
def get_public_settings():
    settings = GlobalSetting.query.all()
    data = {s.key: s.value for s in settings}

    # Add Default Country VAT info
    default_country = Country.query.filter_by(is_default=True).first()
    data['default_vat_rate'] = float(default_country.default_vat_rate) if default_country else 0.0

    # Ensure default VAT mode if not set
    if 'vat_calculation_mode' not in data:
        data['vat_calculation_mode'] = 'SHIPPING_ADDRESS'

    return jsonify(data), 200

# -------------------------------------------------------------------------
# Admin APIs
# -------------------------------------------------------------------------

@api_bp.route('/admin/products', methods=['POST'])
@login_required
def admin_create_product():
    check_admin()
    data = request.get_json() or {}
    if not data.get('product_sku'):
        return jsonify({"error": "SKU required"}), 400
    if Product.query.filter_by(product_sku=data['product_sku']).first():
         return jsonify({"error": "SKU exists"}), 409

    try:
        _create_product_internal(data)
        db.session.commit()
        try:
            cache.delete_memoized(list_products)
        except Exception:
            pass

        product = Product.query.filter_by(product_sku=data['product_sku']).one()
        full_product = Product.query.options(
            joinedload(Product.images),
            joinedload(Product.variants).joinedload(Variant.images)
        ).filter_by(id=product.id).one()
        return jsonify(serialize_product(full_product)), 201
    except Exception as e:
        db.session.rollback()
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@api_bp.route('/admin/products', methods=['GET'])
@login_required
def admin_list_products():
    check_admin()
    status_filter = request.args.get('status')
    q = request.args.get('q')

    query = Product.query.options(
        joinedload(Product.images),
        joinedload(Product.variants).joinedload(Variant.images)
    ).order_by(Product.name)

    if status_filter and status_filter != 'all':
        query = query.filter_by(status=status_filter)

    if q:
        query = query.filter(Product.name.ilike(f"%{q}%"))

    products = query.all()
    return jsonify([serialize_product(p, include_reviews=False) for p in products]), 200

@api_bp.route('/admin/products/<string:sku>', methods=['GET'])
@login_required
def admin_get_product(sku):
    check_admin()
    product = Product.query.options(
        joinedload(Product.images),
        joinedload(Product.reviews),
        joinedload(Product.variants).joinedload(Variant.images)
    ).filter_by(product_sku=sku).first_or_404()
    return jsonify(serialize_product(product)), 200

@api_bp.route('/admin/products/<string:sku>', methods=['PUT'])
@login_required
def admin_update_product(sku):
    check_admin()
    data = request.get_json() or {}
    product = Product.query.filter_by(product_sku=sku).first()
    if not product:
        return jsonify({"error": "Product not found"}), 404

    try:
        _update_product_internal(product, data)
        db.session.commit()

        try:
            cache.delete_memoized(list_products)
        except Exception:
            traceback.print_exc()

        try:
            cache.delete_memoized(get_product, sku)
        except Exception:
            # Often fails with blueprints due to naming
            traceback.print_exc()

        full_product = Product.query.options(
            joinedload(Product.images),
            joinedload(Product.variants).joinedload(Variant.images)
        ).filter_by(id=product.id).one()
        return jsonify(serialize_product(full_product)), 200

    except Exception as e:
        db.session.rollback()
        traceback.print_exc()
        return jsonify({"error": "Failed to update product", "details": str(e)}), 500

@api_bp.route('/admin/products/<string:sku>', methods=['DELETE'])
@login_required
@limiter.exempt
def admin_delete_product(sku):
    check_admin()
    product = Product.query.filter_by(product_sku=sku).first()
    if not product:
        return jsonify({"error": "Product not found"}), 404

    try:
        # If product is already decommissioned, try HARD DELETE
        if product.status == 'decommissioned':
            # Check for existing orders with this product's variants
            variant_skus = [v.sku for v in product.variants]
            if variant_skus:
                usage_count = OrderItem.query.filter(OrderItem.variant_sku.in_(variant_skus)).count()
                if usage_count > 0:
                    return jsonify({"error": "Cannot delete product that has been ordered. It must remain decommissioned."}), 409

            # Safe to hard delete (cascade should handle variants/images if configured, else manual)
            # Assuming cascade='all, delete-orphan' is on relationships
            db.session.delete(product)
            db.session.commit()

            try:
                cache.delete_memoized(list_products)
                cache.delete_memoized(get_product, sku)
            except Exception:
                pass

            return jsonify({"message": f"Product {sku} permanently deleted."}), 200

        else:
            # Soft delete (Decommission)
            product.is_active = False
            product.status = 'decommissioned'
            db.session.add(product)
            db.session.commit()
            try:
                cache.delete_memoized(list_products)
            except Exception:
                traceback.print_exc()
            return jsonify({"message": f"Product {sku} deactivated (soft delete)"}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Failed to delete product", "details": str(e)}), 500

@api_bp.route('/admin/upload-image', methods=['POST'])
@login_required
def admin_upload_image():
    check_admin()
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)

        # Check for custom name (for Gallery Upload)
        custom_name = request.form.get('custom_name')
        if custom_name:
            # Clean up custom name: remove extension if user typed it, secure it
            cname = secure_filename(custom_name.strip())
            # Strip extension if present to avoid image.jpg.webp (unless user wants that?)
            # Usually user types "my_image". If they type "my_image.webp", splitext handles it.
            cname_base, _ = os.path.splitext(cname)
            if not cname_base: cname_base = "image" # fallback
            unique_base = cname_base
        else:
            unique_base = f"{uuid.uuid4()}_{os.path.splitext(filename)[0]}"

        unique_filename = unique_base + ".webp"
        filepath = os.path.join(current_app.root_path, 'static', 'uploads', 'products', unique_filename)

        temp_path = os.path.join(current_app.root_path, 'static', 'uploads', 'products', "temp_" + filename)
        file.save(temp_path)

        # 1. Convert to WebP
        convert_to_webp(temp_path, filepath)

        # 2. Resize original if > 2048 height
        resize_image_max_height(filepath, filepath, max_height=2048)

        if os.path.exists(temp_path):
            os.remove(temp_path)

        # 3. Generate _icon (Height 200)
        icon_filename = unique_base + "_icon.webp"
        icon_path = os.path.join(current_app.root_path, 'static', 'uploads', 'products', icon_filename)
        generate_image_icon(filepath, icon_path, height=200)

        # 4. Generate _big (Height 600)
        big_filename = unique_base + "_big.webp"
        big_path = os.path.join(current_app.root_path, 'static', 'uploads', 'products', big_filename)
        generate_image_icon(filepath, big_path, height=600)

        url = f"/static/uploads/products/{unique_filename}"
        return jsonify({"url": url}), 201
    return jsonify({"error": "File type not allowed"}), 400

@api_bp.route('/admin/orders', methods=['GET'])
@login_required
def admin_list_orders():
    check_admin()
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    status = request.args.get('status', type=str)
    q = request.args.get('q', type=str)

    query = Order.query.order_by(desc(Order.created_at))
    if status and status != 'all':
        query = query.filter_by(status=status)
    if q:
        like = f"%{q}%"
        query = query.filter(Order.public_order_id.ilike(like))

    paginated = query.paginate(page=page, per_page=per_page, error_out=False)

    # Bulk fetch unread message counts for the current page
    order_ids = [o.id for o in paginated.items]
    unread_counts_map = {}
    if order_ids:
        unread_counts = db.session.query(
            Message.order_id,
            func.count(Message.id).label('count')
        ).filter(
            Message.order_id.in_(order_ids),
            Message.sender_type == 'USER',
            Message.is_read == False
        ).group_by(Message.order_id).all()
        unread_counts_map = {r.order_id: r.count for r in unread_counts}

    def serialize_order_summary(o):
        unread_count = unread_counts_map.get(o.id, 0)
        return {
            "id": o.id,
            "public_order_id": o.public_order_id,
            "status": o.status,
            "total_cents": o.total_cents,
            "created_at": o.created_at.isoformat(),
            "shipping_provider": o.shipping_provider,
            "tracking_number": o.tracking_number,
            "shipped_at": o.shipped_at.isoformat() if o.shipped_at else None,
            "item_count": sum(i.quantity for i in o.items),
            "unread_messages_count": unread_count
        }

    return jsonify({
        "orders": [serialize_order_summary(o) for o in paginated.items],
        "total": paginated.total,
        "page": paginated.page,
        "pages": paginated.pages
    }), 200

@api_bp.route('/admin/orders/<string:public_order_id>', methods=['GET'])
@login_required
def admin_get_order(public_order_id):
    check_admin()
    order = Order.query.filter_by(public_order_id=public_order_id).options(joinedload(Order.items), joinedload(Order.messages), joinedload(Order.user)).first_or_404()

    unread_messages = Message.query.filter_by(order_id=order.id, sender_type='USER', is_read=False).all()
    if unread_messages:
        for m in unread_messages:
            m.is_read = True
        db.session.commit()

    def serialize_item(it):
        return {
            "variant_sku": it.variant_sku,
            "quantity": it.quantity,
            "unit_price_cents": it.unit_price_cents,
            "product_snapshot": it.product_snapshot
        }

    def serialize_message(m):
        return {
            "id": m.id,
            "sender_type": m.sender_type,
            "content": m.content,
            "created_at": m.created_at.isoformat(),
            "is_read": m.is_read
        }

    return jsonify({
        "public_order_id": order.public_order_id,
        "user": {
            "username": order.user.username,
            "email": order.user.email
        } if order.user else None,
        "status": order.status,
        "subtotal_cents": order.subtotal_cents,
        "discount_cents": order.discount_cents,
        "shipping_cost_cents": order.shipping_cost_cents,
        "vat_cents": order.vat_cents,
        "total_cents": order.total_cents,
        "comment": order.comment,
        "shipping_method": order.shipping_method,
        "payment_method": order.payment_method,
        "promo_code": order.promo_code,
        "shipping_address_snapshot": order.shipping_address_snapshot,
        "billing_address_snapshot": order.billing_address_snapshot,
        "shipping_provider": order.shipping_provider,
        "tracking_number": order.tracking_number,
        "shipped_at": order.shipped_at.isoformat() if order.shipped_at else None,
        "created_at": order.created_at.isoformat(),
        "items": [serialize_item(i) for i in order.items],
        "messages": [serialize_message(m) for m in order.messages]
    }), 200

@api_bp.route('/admin/orders/<string:public_order_id>/message', methods=['POST'])
@login_required
def admin_send_message(public_order_id):
    check_admin()
    order = Order.query.filter_by(public_order_id=public_order_id).first_or_404()
    data = request.get_json() or {}
    content = data.get('content')
    if not content:
        return jsonify({"error": "Message content is required"}), 400

    msg = Message(
        user_id=order.user_id,
        order_id=order.id,
        sender_type='ADMIN',
        content=content,
        created_at=datetime.now(timezone.utc),
        is_read=False
    )
    db.session.add(msg)
    db.session.commit()
    return jsonify({"message": "Message sent"}), 201

@api_bp.route('/admin/orders/<string:public_order_id>/status', methods=['PUT'])
@login_required
def admin_update_order_status(public_order_id):
    check_admin()
    order = Order.query.filter_by(public_order_id=public_order_id).first_or_404()
    data = request.get_json() or {}
    new_status = (data.get('status') or '').strip().upper()
    ORDER_WORKFLOW = ['PENDING','PAID','READY_FOR_SHIPPING','SHIPPED','DELIVERED','CANCELLED','RETURNED', 'RETURN_REQUESTED']
    if not new_status or new_status not in ORDER_WORKFLOW:
        return jsonify({"error": "Invalid status", "allowed": ORDER_WORKFLOW}), 400

    if new_status == 'SHIPPED' and not order.shipped_at:
        order.shipped_at = datetime.now(timezone.utc)

    # Handle Return Completion Logic
    if new_status == 'RETURNED' and order.status == 'RETURN_REQUESTED':
        # Admin approves the physical return receipt -> trigger refund
        # Here we mock the refund trigger
        pass

    order.status = new_status
    db.session.add(order)
    db.session.commit()

    # Trigger loyalty reward and email notification if status is PAID, SHIPPED, or DELIVERED
    if new_status in ['PAID', 'SHIPPED', 'DELIVERED']:
        try:
            process_loyalty_reward(order)
            send_order_status_update_email(order)
        except Exception:
            traceback.print_exc()

    return jsonify({"message": "Status updated"}), 200

@api_bp.route('/admin/orders/<string:public_order_id>/shipment', methods=['PUT'])
@login_required
def admin_update_order_shipment(public_order_id):
    check_admin()
    order = Order.query.filter_by(public_order_id=public_order_id).first_or_404()
    data = request.get_json() or {}
    provider = data.get('shipping_provider')
    tracking = data.get('tracking_number')
    mark_as_shipped = bool(data.get('mark_as_shipped', False))

    if provider is not None:
        order.shipping_provider = str(provider).strip()
    if tracking is not None:
        order.tracking_number = str(tracking).strip()
    if mark_as_shipped:
        order.status = 'SHIPPED'
        order.shipped_at = order.shipped_at or datetime.now(timezone.utc)
        send_order_status_update_email(order)

    db.session.add(order)
    db.session.commit()
    return jsonify({"message": "Shipment updated"}), 200

@api_bp.route('/admin/categories', methods=['GET'])
@login_required
def admin_list_categories():
    check_admin()
    categories = Category.query.order_by(Category.name).all()
    return jsonify([serialize_category(c) for c in categories]), 200

@api_bp.route('/admin/categories', methods=['POST'])
@login_required
def admin_create_category():
    check_admin()
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    if not name: return jsonify({"error": "Name required"}), 400
    if Category.query.filter_by(name=name).first(): return jsonify({"error": "Exists"}), 409
    c = Category(
        name=name,
        slug=data.get('slug'),
        meta_title=data.get('meta_title'),
        meta_description=data.get('meta_description')
    )
    db.session.add(c)
    db.session.commit()
    return jsonify(serialize_category(c)), 201

@api_bp.route('/admin/categories/<int:id>', methods=['PUT', 'DELETE'])
@login_required
def admin_modify_category(id):
    check_admin()
    c = Category.query.get_or_404(id)
    if request.method == 'DELETE':
        if Product.query.filter_by(category=c.name).count() > 0:
            return jsonify({"error": "Category in use"}), 400
        db.session.delete(c)
        db.session.commit()
        return jsonify({"message": "Deleted"}), 200
    else: # PUT
        data = request.get_json() or {}
        name = data.get('name', '').strip()
        if not name: return jsonify({"error": "Name required"}), 400
        existing = Category.query.filter_by(name=name).first()
        if existing and existing.id != id: return jsonify({"error": "Exists"}), 409

        c.name = name
        c.slug = data.get('slug', c.slug)
        c.meta_title = data.get('meta_title', c.meta_title)
        c.meta_description = data.get('meta_description', c.meta_description)

        db.session.commit()
        return jsonify(serialize_category(c)), 200

# -------------------------------------------------------------------------
# Product Group Admin APIs
# -------------------------------------------------------------------------

@api_bp.route('/admin/product-groups', methods=['GET'])
@login_required
def admin_list_product_groups():
    check_admin()
    groups = ProductGroup.query.order_by(ProductGroup.name).all()
    return jsonify([serialize_group(g) for g in groups]), 200

@api_bp.route('/admin/product-groups', methods=['POST'])
@login_required
def admin_create_product_group():
    check_admin()
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    if not name:
        return jsonify({"error": "Group name is required"}), 400
    if ProductGroup.query.filter_by(name=name).first():
        return jsonify({"error": "Group already exists"}), 409

    slug = data.get('slug') or slugify(name)
    group = ProductGroup(
        name=name,
        slug=slug,
        is_active=bool(data.get('is_active', False)),
        meta_title=data.get('meta_title'),
        meta_description=data.get('meta_description')
    )

    if 'product_skus' in data:
        skus = data['product_skus']
        products = Product.query.filter(Product.product_sku.in_(skus)).all()
        group.products = products

    db.session.add(group)
    db.session.commit()
    return jsonify(serialize_group(group)), 201

@api_bp.route('/admin/product-groups/<int:group_id>', methods=['GET'])
@login_required
def admin_get_product_group(group_id):
    check_admin()
    group = ProductGroup.query.get_or_404(group_id)
    return jsonify(serialize_group(group)), 200

@api_bp.route('/admin/product-groups/<int:group_id>', methods=['PUT'])
@login_required
def admin_update_product_group(group_id):
    check_admin()
    group = ProductGroup.query.get_or_404(group_id)
    data = request.get_json() or {}

    if 'name' in data:
        name = data['name'].strip()
        if not name:
            return jsonify({"error": "Group name is required"}), 400
        existing = ProductGroup.query.filter_by(name=name).first()
        if existing and existing.id != group_id:
            return jsonify({"error": "Another group with this name already exists"}), 409
        group.name = name

    if 'is_active' in data:
        group.is_active = bool(data['is_active'])

    if 'slug' in data:
        group.slug = data['slug'] or slugify(group.name)

    if 'meta_title' in data:
        group.meta_title = data['meta_title']

    if 'meta_description' in data:
        group.meta_description = data['meta_description']

    if 'product_skus' in data:
        skus = data['product_skus']
        products = Product.query.filter(Product.product_sku.in_(skus)).all()
        group.products = products

    db.session.commit()
    return jsonify(serialize_group(group)), 200

@api_bp.route('/admin/product-groups/<int:group_id>', methods=['DELETE'])
@login_required
def admin_delete_product_group(group_id):
    check_admin()
    group = ProductGroup.query.get_or_404(group_id)
    db.session.delete(group)
    db.session.commit()
    return jsonify({"message": "Product group deleted"}), 200

@api_bp.route('/admin/product-groups/<int:group_id>/add-product-sku', methods=['POST'])
@login_required
def admin_add_product_to_group_by_sku(group_id):
    check_admin()
    group = ProductGroup.query.get_or_404(group_id)
    data = request.get_json() or {}
    sku = data.get('sku', '').strip()
    if not sku:
        return jsonify({"error": "Product SKU is required"}), 400

    product = Product.query.filter_by(product_sku=sku).first()
    if not product:
        return jsonify({"error": "Product not found"}), 404

    if product not in group.products:
        group.products.append(product)
        db.session.commit()

    return jsonify(serialize_group(group)), 200

@api_bp.route('/admin/products/export', methods=['GET'])
@login_required
def admin_export_products():
    check_admin()
    fmt = request.args.get('format', 'json').lower()
    products = Product.query.options(joinedload(Product.images), joinedload(Product.variants).joinedload(Variant.images)).order_by(Product.name).all()
    serialized = [serialize_product(p) for p in products]
    if fmt == 'csv':
        csv_data = products_to_csv(serialized)
        return csv_data, 200, {'Content-Type': 'text/csv; charset=utf-8', 'Content-Disposition': 'attachment; filename=products_export.csv'}
    return jsonify(serialized), 200, {'Content-Disposition': 'attachment; filename=products_export.json'}

@api_bp.route('/admin/products/import', methods=['POST'])
@login_required
def admin_import_products():
    check_admin()
    if 'file' not in request.files: return jsonify({"error": "No file"}), 400
    file = request.files['file']
    mode = request.form.get('mode', 'skip')
    if file.filename == '': return jsonify({"error": "No selected file"}), 400
    ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
    if ext not in ['json', 'csv']: return jsonify({"error": "Invalid extension"}), 400

    try:
        products_data = parse_products_file(file, ext)
        if mode == 'override':
            db.session.query(ProductImage).delete()
            db.session.query(VariantImage).delete()
            db.session.query(Variant).delete()
            db.session.query(Product).delete()
            for p_data in products_data:
                _create_product_internal(p_data)
        else:
            # Batch fetch existing products to avoid N+1 queries
            import_skus = [p.get('product_sku') for p in products_data if p.get('product_sku')]
            existing_products = Product.query.filter(Product.product_sku.in_(import_skus)).all()
            existing_map = {p.product_sku: p for p in existing_products}

            for p_data in products_data:
                sku = p_data.get('product_sku')
                if not sku: continue

                if sku in existing_map:
                    if mode == 'update':
                        _update_product_internal(existing_map[sku], p_data)
                else:
                    _create_product_internal(p_data)
        db.session.commit()
        # Invalidate cache
        try:
            cache.delete_memoized(list_products)
        except Exception:
            pass
        return jsonify({"message": "Import successful"}), 200
    except Exception as e:
        db.session.rollback()
        traceback.print_exc()
        return jsonify({"error": f"Import failed: {str(e)}"}), 500

# Additional Admin APIs (Settings, Currencies, Users, Promotions)
@api_bp.route('/admin/settings', methods=['GET'])
@login_required
def admin_get_settings():
    check_admin()
    settings = GlobalSetting.query.all()
    return jsonify({s.key: s.value for s in settings}), 200

@api_bp.route('/admin/settings', methods=['POST'])
@login_required
def admin_update_settings():
    check_admin()
    data = request.get_json() or {}
    for key, value in data.items():
        setting = GlobalSetting.query.filter_by(key=key).first()
        if setting:
            setting.value = str(value)
        else:
            setting = GlobalSetting(key=key, value=str(value))
            db.session.add(setting)
    db.session.commit()
    cache.delete_memoized(get_public_settings)
    return jsonify({"message": "Settings updated"}), 200


@api_bp.route('/admin/factory-reset', methods=['POST'])
@login_required
def admin_factory_reset():
    check_admin()
    data = request.get_json() or {}
    code = data.get('code')

    expected_code = current_app.config.get('APP_RESET_CODE', 'reset_my_app')

    if code != expected_code:
        return jsonify({"error": "Invalid reset code"}), 403

    try:
        # Perform factory reset
        # Dropping all tables is the safest way to ensure clean slate
        db.drop_all()
        db.create_all()

        # Re-seed data
        setup_database(current_app)

        # Invalidate all caches
        cache.clear()

        return jsonify({"message": "Application reset to factory defaults. Please log in again."}), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": "Reset failed", "details": str(e)}), 500

@api_bp.route('/admin/currencies', methods=['GET', 'POST'])
@login_required
def admin_currencies():
    check_admin()
    if request.method == 'GET':
        currencies = AppCurrency.query.order_by(AppCurrency.id).all()
        return jsonify([{"id": c.id, "symbol": c.symbol} for c in currencies]), 200
    else:
        data = request.get_json() or {}
        symbol = data.get('symbol', '').strip()
        if not symbol: return jsonify({"error": "Symbol required"}), 400
        if AppCurrency.query.filter_by(symbol=symbol).first(): return jsonify({"error": "Exists"}), 409
        c = AppCurrency(symbol=symbol)
        db.session.add(c)
        db.session.commit()
        return jsonify({"id": c.id, "symbol": c.symbol}), 201

@api_bp.route('/admin/currencies/<int:id>', methods=['DELETE'])
@login_required
def admin_delete_currency(id):
    check_admin()
    c = AppCurrency.query.get_or_404(id)
    active = GlobalSetting.query.filter_by(key='currency').first()
    if active and active.value == c.symbol: return jsonify({"error": "Cannot delete active"}), 400
    db.session.delete(c)
    db.session.commit()
    return jsonify({"message": "Deleted"}), 200

@api_bp.route('/admin/users', methods=['GET'])
@login_required
def admin_list_users_json():
    check_admin()
    users = User.query.order_by(User.username).all()
    return jsonify([{"id": u.id, "username": u.username, "email": u.email} for u in users]), 200

@api_bp.route('/admin/promotions', methods=['GET', 'POST'])
@login_required
def admin_promotions():
    check_admin()
    if request.method == 'GET':
        promos = Promotion.query.order_by(Promotion.id.desc()).all()
        return jsonify([serialize_promotion(p) for p in promos]), 200
    else:
        data = request.get_json() or {}
        try:
            valid_to = None
            if data.get('valid_to'):
                valid_to = datetime.fromisoformat(data['valid_to'].replace('Z', '+00:00'))
            promo = Promotion(
                code=data['code'],
                description=data.get('description'),
                discount_type=data['discount_type'],
                discount_value=int(data['discount_value']),
                is_active=bool(data.get('is_active', True)),
                valid_to=valid_to,
                user_id=data.get('user_id')
            )
            db.session.add(promo)
            db.session.commit()
            return jsonify(serialize_promotion(promo)), 201
        except Exception as e:
            return jsonify({"error": str(e)}), 400

@api_bp.route('/admin/promotions/<int:id>', methods=['PUT', 'DELETE'])
@login_required
def admin_modify_promotion(id):
    check_admin()
    promo = Promotion.query.get_or_404(id)
    if request.method == 'DELETE':
        db.session.delete(promo)
        db.session.commit()
        return jsonify({"message": "Deleted"}), 200
    else:
        data = request.get_json() or {}
        try:
            promo.code = data.get('code', promo.code)
            promo.description = data.get('description', promo.description)
            promo.discount_type = data.get('discount_type', promo.discount_type)
            promo.discount_value = int(data.get('discount_value', promo.discount_value))
            promo.is_active = bool(data.get('is_active', promo.is_active))
            if 'valid_to' in data:
                promo.valid_to = datetime.fromisoformat(data['valid_to'].replace('Z', '+00:00')) if data['valid_to'] else None
            promo.user_id = data.get('user_id', promo.user_id)
            db.session.commit()
            return jsonify(serialize_promotion(promo)), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 400

@api_bp.route('/admin/countries', methods=['GET'])
@login_required
def admin_list_countries():
    check_admin()
    countries = Country.query.order_by(Country.name).all()
    data = []
    for c in countries:
        data.append({
            "id": c.id,
            "name": c.name,
            "iso_code": c.iso_code,
            "default_vat_rate": float(c.default_vat_rate),
            "currency_code": c.currency_code,
            "shipping_cost_cents": c.shipping_cost_cents,
            "free_shipping_threshold_cents": c.free_shipping_threshold_cents,
            "is_default": c.is_default
        })
    return jsonify(data), 200

@api_bp.route('/admin/countries/<int:id>/set-default', methods=['POST'])
@login_required
def admin_set_default_country(id):
    check_admin()
    target = Country.query.get_or_404(id)

    # Unset all others
    Country.query.update({Country.is_default: False})

    target.is_default = True
    db.session.commit()

    return jsonify({"message": f"{target.name} set as default country"}), 200

@api_bp.route('/admin/countries', methods=['POST'])
@login_required
def admin_create_country():
    check_admin()
    data = request.get_json() or {}
    try:
        # Check if exists by ISO
        iso = data.get('iso_code', '').upper().strip()
        if not iso: return jsonify({"error": "ISO code required"}), 400

        c = Country.query.filter_by(iso_code=iso).first()
        if not c:
            c = Country(iso_code=iso)
            db.session.add(c)

        c.name = data.get('name', c.name or iso)
        c.default_vat_rate = float(data.get('default_vat_rate', 0.0))
        c.currency_code = data.get('currency_code', 'USD').upper().strip()
        c.shipping_cost_cents = int(data.get('shipping_cost_cents', 0))

        fs_threshold = data.get('free_shipping_threshold_cents')
        c.free_shipping_threshold_cents = int(fs_threshold) if fs_threshold is not None else None

        db.session.commit()
        return jsonify({"message": "Country saved", "id": c.id}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400

@api_bp.route('/admin/countries/<int:id>', methods=['DELETE'])
@login_required
def admin_delete_country(id):
    check_admin()
    c = Country.query.get_or_404(id)
    db.session.delete(c)
    db.session.commit()
    return jsonify({"message": "Deleted"}), 200

@api_bp.route('/admin/reports', methods=['GET'])
@login_required
def admin_get_reports():
    check_admin()
    report_type = request.args.get('type', 'summary')
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    fmt = request.args.get('format', 'json').lower()

    # Parse dates
    start_date = None
    end_date = None
    if start_date_str:
        try:
            start_date = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
        except ValueError:
            pass
    if end_date_str:
        try:
            # End of day if possible, or exact timestamp
            end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
            # If end_date has no time component (or is midnight), assume user meant "inclusive of this day"
            # So we move to the end of this day (or start of next day)
            if end_date.hour == 0 and end_date.minute == 0 and end_date.second == 0:
                 end_date = end_date + timedelta(days=1)
        except ValueError:
            pass

    # Base query filters
    filters = []
    if start_date:
        filters.append(Order.created_at >= start_date)
    if end_date:
        # Using < end_date because we moved it to the start of the next day (inclusive upper bound logic)
        filters.append(Order.created_at < end_date)

    # Global filter: Exclude CANCELLED orders from all reports
    filters.append(Order.status != 'CANCELLED')

    data = []

    if report_type == 'summary':
        query = db.session.query(
            func.count(Order.id).label('orders_count'),
            func.sum(case((Order.status != 'CANCELLED', Order.subtotal_cents), else_=0)).label('gross_sales'),
            func.sum(case((Order.status != 'CANCELLED', Order.discount_cents), else_=0)).label('discounts'),
            func.sum(case((Order.status != 'CANCELLED', Order.shipping_cost_cents), else_=0)).label('shipping'),
            func.sum(case((Order.status != 'CANCELLED', Order.vat_cents), else_=0)).label('vat'),
            func.sum(case((Order.status == 'RETURNED', Order.subtotal_cents), else_=0)).label('returns'),
            func.sum(case((Order.status != 'CANCELLED', Order.total_cents), else_=0)).label('total_collected')
        )
        if filters:
            query = query.filter(*filters)

        result = query.one()

        gross = int(result.gross_sales or 0)
        discounts = int(result.discounts or 0)
        returns = int(result.returns or 0)
        net_sales = gross - discounts - returns

        data = [{
            "orders_count": result.orders_count,
            "gross_sales": gross,
            "discounts": discounts,
            "shipping": int(result.shipping or 0),
            "vat": int(result.vat or 0),
            "returns": returns,
            "net_sales": net_sales,
            "total_collected": int(result.total_collected or 0)
        }]

    elif report_type == 'daily':
        # SQLite: func.date(Order.created_at)
        date_col = func.date(Order.created_at)
        query = db.session.query(
            date_col.label('date'),
            func.count(Order.id).label('orders_count'),
            func.sum(case((Order.status != 'CANCELLED', Order.subtotal_cents), else_=0)).label('gross_sales'),
            func.sum(case((Order.status != 'CANCELLED', Order.discount_cents), else_=0)).label('discounts'),
            func.sum(case((Order.status != 'CANCELLED', Order.total_cents), else_=0)).label('total_collected'),
            func.sum(case((Order.status == 'RETURNED', Order.subtotal_cents), else_=0)).label('returns'),
             func.sum(case((Order.status != 'CANCELLED', Order.shipping_cost_cents), else_=0)).label('shipping'),
            func.sum(case((Order.status != 'CANCELLED', Order.vat_cents), else_=0)).label('vat')
        ).group_by(date_col).order_by(date_col.desc())

        if filters:
            query = query.filter(*filters)

        results = query.all()
        data = []
        for r in results:
            gross = int(r.gross_sales or 0)
            discounts = int(r.discounts or 0)
            returns = int(r.returns or 0)
            net = gross - discounts - returns
            data.append({
                "date": r.date,
                "orders_count": r.orders_count,
                "gross_sales": gross,
                "discounts": discounts,
                "net_sales": net,
                "shipping": int(r.shipping or 0),
                "vat": int(r.vat or 0),
                "total": int(r.total_collected or 0)
            })

    elif report_type == 'items':
        query = db.session.query(
            OrderItem.variant_sku,
            func.sum(OrderItem.quantity).label('quantity_sold'),
            func.sum(OrderItem.unit_price_cents * OrderItem.quantity).label('gross_revenue')
        ).join(Order).filter(Order.status != 'CANCELLED')

        if filters:
            query = query.filter(*filters)

        query = query.group_by(OrderItem.variant_sku).order_by(desc('gross_revenue'))

        results = query.all()

        all_skus = [r.variant_sku for r in results]
        variants = Variant.query.options(joinedload(Variant.product)).filter(Variant.sku.in_(all_skus)).all()
        variant_map = {v.sku: v.product.name + " (" + (v.color_name or "") + " " + (v.size or "") + ")" for v in variants}

        data = []
        for r in results:
            name = variant_map.get(r.variant_sku, "Unknown Item")
            data.append({
                "sku": r.variant_sku,
                "name": name,
                "sold": r.quantity_sold,
                "revenue": int(r.gross_revenue or 0)
            })

    # CSV Export
    if fmt == 'csv':
        output = io.StringIO()
        writer = csv.writer(output)

        if report_type == 'summary':
            writer.writerow(['Orders', 'Gross Sales', 'Discounts', 'Shipping', 'VAT', 'Returns', 'Net Sales', 'Total Collected'])
            for row in data:
                 writer.writerow([
                     row['orders_count'],
                     "{:.2f}".format(row['gross_sales']/100),
                     "{:.2f}".format(row['discounts']/100),
                     "{:.2f}".format(row['shipping']/100),
                     "{:.2f}".format(row['vat']/100),
                     "{:.2f}".format(row['returns']/100),
                     "{:.2f}".format(row['net_sales']/100),
                     "{:.2f}".format(row['total_collected']/100)
                 ])
        elif report_type == 'daily':
            writer.writerow(['Date', 'Orders', 'Gross Sales', 'Discounts', 'Net Sales', 'Shipping', 'VAT', 'Total'])
            for row in data:
                writer.writerow([
                    row['date'],
                    row['orders_count'],
                    "{:.2f}".format(row['gross_sales']/100),
                    "{:.2f}".format(row['discounts']/100),
                    "{:.2f}".format(row['net_sales']/100),
                    "{:.2f}".format(row['shipping']/100),
                    "{:.2f}".format(row['vat']/100),
                    "{:.2f}".format(row['total']/100)
                ])
        elif report_type == 'items':
            writer.writerow(['SKU', 'Name', 'Sold', 'Revenue'])
            for row in data:
                writer.writerow([
                    row['sku'],
                    row['name'],
                    row['sold'],
                    "{:.2f}".format(row['revenue']/100)
                ])

        return output.getvalue(), 200, {'Content-Type': 'text/csv', 'Content-Disposition': f'attachment; filename=report_{report_type}.csv'}

    return jsonify(data), 200

# -------------------------------------------------------------------------
# Photo Gallery API
# -------------------------------------------------------------------------

@api_bp.route('/admin/gallery', methods=['GET'])
@login_required
def admin_gallery_list():
    check_admin()

    # Paths
    base_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'products')
    if not os.path.exists(base_dir):
        return jsonify([]), 200

    # 1. Fetch all usage from DB
    # Map normalized_filename -> list of usage info
    usage_map = {}

    # Product Images
    p_imgs = ProductImage.query.options(joinedload(ProductImage.product)).all()
    for pi in p_imgs:
        if not pi.url or '/static/uploads/products/' not in pi.url:
            continue
        fname = os.path.basename(pi.url)
        # Normalize (remove _icon, _big if present in DB url, though usually DB has main or specific)
        # Actually DB usually stores the uploaded filename. If upload logic generates _icon separately but stores main in DB.
        # But wait, logic: upload -> returns url. Frontend uses that url.
        # So we should look for exact match of filename?
        # Or if DB has `abc.webp`, it implies usage of `abc.webp` (and maybe icons).
        if fname not in usage_map: usage_map[fname] = []
        usage_map[fname].append({
            "type": "Product",
            "name": pi.product.name,
            "sku": pi.product.product_sku
        })

    # Variant Images
    v_imgs = VariantImage.query.options(joinedload(VariantImage.variant).joinedload(Variant.product)).all()
    for vi in v_imgs:
        if not vi.url or '/static/uploads/products/' not in vi.url:
            continue
        fname = os.path.basename(vi.url)
        if fname not in usage_map: usage_map[fname] = []
        p_name = vi.variant.product.name if vi.variant and vi.variant.product else "Unknown"
        sku = vi.variant.sku if vi.variant else "Unknown"
        usage_map[fname].append({
            "type": "Variant",
            "name": p_name,
            "sku": sku
        })

    # 2. Scan Directory
    files = []
    try:
        all_files = os.listdir(base_dir)
        # Filter for images
        all_files = [f for f in all_files if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.gif'))]

        # Identify main files (not _icon, not _big)
        for f in all_files:
            name, ext = os.path.splitext(f)
            if name.endswith('_icon') or name.endswith('_big'):
                continue

            # This is a main file candidate
            is_linked = f in usage_map
            linked_to = usage_map.get(f, [])

            files.append({
                "filename": f,
                "url": f"/static/uploads/products/{f}",
                "is_linked": is_linked,
                "linked_to": linked_to
            })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

    return jsonify(files), 200

@api_bp.route('/admin/logs', methods=['GET'])
@login_required
def admin_get_logs():
    check_admin()
    log_file = 'app.log'
    if not os.path.exists(log_file):
        return jsonify({"logs": ""}), 200

    try:
        from collections import deque
        with open(log_file, 'r') as f:
            # Get last 100 lines efficiently
            last_lines = deque(f, 100)
            return jsonify({"logs": "".join(last_lines)}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@api_bp.route('/admin/logs/clear', methods=['POST'])
@login_required
def admin_clear_logs():
    check_admin()
    log_file = 'app.log'
    try:
        with open(log_file, 'w') as f:
            f.write(f"--- Log cleared at {datetime.now(timezone.utc).isoformat()} ---\n")
        return jsonify({"message": "Logs cleared"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@api_bp.route('/admin/gallery/<filename>', methods=['DELETE'])
@login_required
def admin_gallery_delete(filename):
    check_admin()

    # Security check: filename should be just a name, no paths
    filename = secure_filename(filename)
    base_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'products')
    file_path = os.path.join(base_dir, filename)

    if not os.path.exists(file_path):
        return jsonify({"error": "File not found"}), 404

    # Check Usage again
    # We need to ensure we don't delete if linked.
    # Searching DB for usage of this filename
    # URL pattern: .../filename
    term = f"%/{filename}"
    in_prod = ProductImage.query.filter(ProductImage.url.ilike(term)).count()
    in_var = VariantImage.query.filter(VariantImage.url.ilike(term)).count()

    if in_prod > 0 or in_var > 0:
        return jsonify({"error": "Cannot delete: Photo is linked to products."}), 409

    try:
        # Delete Main
        os.remove(file_path)

        # Delete Variants (_icon, _big)
        name, ext = os.path.splitext(filename)
        for suffix in ['_icon', '_big']:
            var_path = os.path.join(base_dir, f"{name}{suffix}{ext}")
            if os.path.exists(var_path):
                os.remove(var_path)

        return jsonify({"message": "Photo deleted"}), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
