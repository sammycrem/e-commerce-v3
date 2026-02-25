from flask import Blueprint, render_template, abort, send_from_directory, request, jsonify, redirect, url_for, session, current_app, flash
from flask_login import current_user, login_required, logout_user, login_user
from ..models import User, Product, Promotion, Country, GlobalSetting, AppCurrency, Order, Category, Review, OrderItem
from ..extensions import db, limiter, cache
from sqlalchemy.orm import joinedload
from sqlalchemy import func
from werkzeug.security import check_password_hash, generate_password_hash
from ..utils import generate_id, create_directory, send_emailTls2, convert_to_webp, generate_image_icon, ensure_icon_for_url
import os
import uuid
from werkzeug.utils import secure_filename
from datetime import datetime, timezone

main_bp = Blueprint('main', __name__)

@main_bp.app_template_filter('icon_url')
def icon_url(url):
    if not url:
        return ""
    base, _ = os.path.splitext(url)
    return f"{base}_icon.webp"

@main_bp.app_template_filter('big_url')
def big_url(url):
    if not url:
        return ""
    base, _ = os.path.splitext(url)
    if base.endswith("_big"):
        return url
    return f"{base}_big.webp"

# Constants
ADMIN_USER = 'admin' # Will be overridden by app config context if needed, but here we might need to access config.
# Ideally, access config via current_app.config['APP_ADMIN_USER']

@main_bp.route('/')
def home():
    categories = Category.query.all()
    # Fetch all published products with images to avoid N+1 query issues
    all_published_products = Product.query.filter_by(status='published').options(joinedload(Product.images)).all()

    # Group products by category in memory
    from collections import defaultdict
    products_by_category = defaultdict(list)
    for prod in all_published_products:
        products_by_category[prod.category].append(prod)

    category_data = []
    import random
    for cat in categories:
        cat_products = products_by_category.get(cat.name, [])
        if cat_products:
            # Select 2 random products per category if available
            selected_products = random.sample(cat_products, min(len(cat_products), 2))
            category_data.append({
                'category': cat,
                'products': selected_products
            })
    return render_template('index.html', category_data=category_data)

@main_bp.route('/index')
def index():
    return redirect(url_for('main.home'))

@main_bp.route('/product')
@main_bp.route('/shop')
@cache.cached(timeout=60, query_string=True)
def shop_page():
    category = request.args.get('category')
    group_id = request.args.get('group_id', type=int)
    q = request.args.get('q')
    query = Product.query.filter_by(status='published')

    if group_id:
        from ..models import ProductGroup
        query = query.join(Product.groups).filter(ProductGroup.id == group_id)
    elif category:
        query = query.filter_by(category=category)

    if q:
        query = query.filter(Product.name.ilike(f"%{q}%"))
    products = query.all()
    return render_template('shop.html', products=products)

@main_bp.route('/sitemap.xml')
def sitemap():
    from flask import make_response
    products = Product.query.filter_by(status='published').all()
    # Assuming category is just a string in Product model
    categories = db.session.query(Product.category).filter_by(status='published').distinct().all()

    # Static pages
    pages = [
        {'loc': url_for('main.home', _external=True), 'priority': '1.0'},
        {'loc': url_for('main.shop_page', _external=True), 'priority': '0.9'},
    ]

    # Product pages
    for p in products:
        pages.append({
            'loc': url_for('main.product_page', sku=p.product_sku, _external=True),
            'priority': '0.8',
            'lastmod': datetime.now(timezone.utc).strftime('%Y-%m-%d') # Ideally product.updated_at
        })

    # Category pages (if shop supports category filtering)
    for c in categories:
        if c.category:
            pages.append({
                'loc': url_for('main.shop_page', category=c.category, _external=True),
                'priority': '0.7'
            })

    sitemap_xml = render_template('sitemap.xml', pages=pages)
    response = make_response(sitemap_xml)
    response.headers['Content-Type'] = 'application/xml'
    return response

@main_bp.route('/product/<string:sku>')
def product_page(sku):
    # Only published products are visible
    product = Product.query.filter_by(product_sku=sku, status='published').first_or_404()
    user_review = None
    has_ordered = False

    if product and current_user.is_authenticated:
        user_review = Review.query.filter_by(user_id=current_user.id, product_id=product.id).first()

        # Check if user has ordered this product via variant SKUs
        variant_skus = [v.sku for v in product.variants]
        has_ordered = db.session.query(OrderItem).join(Order).filter(
            Order.user_id == current_user.id,
            OrderItem.variant_sku.in_(variant_skus)
        ).count() > 0

    return render_template('product_detail.html', sku=sku, product=product, user_review=user_review, has_ordered=has_ordered)

@main_bp.route('/profile')
@login_required
def profile():
    countries = Country.query.all()
    # Fetch user's active loyalty rewards (promotions)
    loyalty_promos = Promotion.query.filter_by(user_id=current_user.id, is_active=True).all()
    return render_template('home.html', countries=countries, loyalty_promos=loyalty_promos)

@main_bp.route('/profile/update', methods=['POST'])
@login_required
def update_profile():
    email = request.form.get('email')
    phone = request.form.get('phone')

    if email:
        existing = User.query.filter(User.email == email.lower(), User.id != current_user.id).first()
        if existing:
            flash('Email is already in use.', 'danger')
            return redirect(url_for('main.profile'))
        current_user.email = email.lower()

    current_user.phone = phone
    db.session.commit()
    flash('Profile updated successfully!', 'success')
    return redirect(url_for('main.profile'))

@main_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def login():
    try:
        if request.method == 'POST':
            password = request.form['password']
            email = request.form['email'].lower()

            user = User.query.filter_by(email=email).first()
            if user and check_password_hash(user.password, password):
                login_user(user)
                session['logged_in'] = True
                session['time']  = datetime.now(timezone.utc).strftime("%d_%m_%Y_%H_%M_%S")
                # logger.info('Login: ' + email + ";"  + request.remote_addr) # Logger not avail here directly?

                next_page = request.form.get('next') or request.args.get('next')
                if next_page:
                    return redirect(next_page)
                return redirect(url_for('main.home'))
            else:
                flash('Invalid username or password')
                return render_template('login.html', message_text="Invalid username or password")
        else:
            if current_user.is_authenticated:
                return redirect(url_for('main.home'))
    except Exception as e:
        return render_template('login.html', message_text=e)
    return render_template('login.html', message_text="Please Login or Signup")

@main_bp.route('/logout')
@login_required
def logout():
    session.pop('logged_in', None)
    logout_user()
    return redirect(url_for('main.login'))

@main_bp.route('/signup', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def signup():
    if request.method == 'POST':
        username = request.form['username'].lower()
        password = request.form['password']
        email = request.form['email'].lower()
        user_id=generate_id(3) + '_1'

        if User.query.filter_by(username=username).first() or User.query.filter_by(email=email).first():
            flash('Username already exists')
            return render_template('signup.html', message_text='Username: ' + email +  ' already exists')
        else:
            try:
                from ..utils import encrypt_password
                encryption_key = os.environ.get('ENCRYPTION_KEY')
                encrypted_pw = encrypt_password(password, encryption_key)
                new_user = User(username=username, user_id=user_id , password=generate_password_hash(password), encrypted_password=encrypted_pw, email=email)
                db.session.add(new_user)
                db.session.commit()
                # Email sending logic... simplified for blueprint move
                # We need to access SERVER_URL, etc. from config

                create_directory(os.path.join(current_app.config['APP_WWW'], new_user.user_id) if 'APP_WWW' in current_app.config else 'www') # logic from app.py

                session.pop('logged_in', None)
                logout_user()

                flash('User created successfully. Please login.')
                return redirect(url_for('main.login'))
            except Exception as e:
                print(f"An error occurred: signup  {str(e)}")
                return render_template('signup.html', message_text=str(e))

    return render_template('signup.html')

@main_bp.route('/validate')
def validate_user():
    user_id = request.args.get('id')
    username = request.args.get('username')

    if user_id is None or username is None:
        return jsonify({'error': 'Missing required parameters'}), 400

    user = User.query.filter_by(username=username,user_id=user_id).first()
    if user:
        user.validation = 1
        db.session.commit()
        return jsonify({'message': 'User validated successfully!'})
    else:
        return jsonify({'error': 'Invalid user ID or username'}), 401

#Crud
@main_bp.route("/list")                 #admin only
@login_required
def user_list():
    from flask import current_app
    admin_user = current_app.config.get('APP_ADMIN_USER')
    if current_user.is_authenticated and current_user.username==admin_user:
        users = db.session.execute(db.select(User).order_by(User.username)).scalars()
        return render_template("list.html", users=users, message_text=current_user)
    else:
        return render_template("list.html", message_text="You do not have admin permission to view users list " )

@main_bp.route("/user/<int:id>")
@login_required
def user_detail(id):
    from flask import current_app
    admin_user = current_app.config.get('APP_ADMIN_USER')
    if current_user.is_authenticated and current_user.username==admin_user or current_user.id==id:
        user = db.get_or_404(User, id)
        return render_template("detail.html", user=user)
    else:
        return render_template("login.html", message_text="You do not have permission to view user detail")

@main_bp.route("/user/<int:id>/delete", methods=["GET", "POST"])
@login_required
def user_delete(id):
    from flask import current_app
    admin_user = current_app.config.get('APP_ADMIN_USER')
    if current_user.is_authenticated and (current_user.username==admin_user or current_user.id==id):
        user = db.get_or_404(User, id)

        if request.method == "POST":
            db.session.delete(user)
            db.session.commit()
            return redirect(url_for("main.user_list"))
        else :
            return render_template("delete.html", user=user)

    if current_user.is_authenticated:
        return render_template("login.html", message_text="You are not allowed to delete this user, id=" + str(id))
    else:
        return render_template("login.html", message_text="Please login")

@main_bp.route('/protected/<path:subpath>')
def protected_static(subpath):
    if "static" in subpath or "resource" in subpath:
        return send_from_directory('protected/' ,subpath )
    else:
        if current_user.is_authenticated:
            response = send_from_directory('protected/' ,subpath )
            response.headers['Cache-Control'] = 'no-store'
            response.headers['Expires'] = 'Thu, 01 Jan 1970 00:00:00 GMT'
            response.headers['Pragma'] = 'no-cache'
            return response
        else:
            abort(403)

@main_bp.route('/export/<path:subpath>')
@login_required
def export_static(subpath):
    EXPORT_DIR = "export" # Should be config
    if subpath.startswith(current_user.user_id):
        response = send_from_directory(EXPORT_DIR+'/' ,subpath )
        return response
    else:
        abort(403)

@main_bp.route("/authorized_keys" , methods=['GET', 'POST'])
@login_required
def get_authorized_keys():
    from flask import current_app
    admin_user = current_app.config.get('APP_ADMIN_USER')
    if current_user.username == admin_user:
        return jsonify({'key': "_authorized_keys", '_url': request.remote_addr}), 200
    else:
        return jsonify({'error': "_not_authorized", 'url': request.remote_addr}), 403

# Admin routes
@main_bp.route('/admin')
@login_required
def admin_page():
    from flask import current_app
    admin_user = current_app.config.get('APP_ADMIN_USER')
    if current_user.username != admin_user:
        abort(403)
    return render_template('admin.html')

@main_bp.route('/admin/accounting')
@login_required
def admin_accounting():
    from flask import current_app
    admin_user = current_app.config.get('APP_ADMIN_USER')
    if current_user.username != admin_user:
        abort(403)
    return render_template('admin.html', active_tab='reports')

# Admin Order Routes (HTML)
@main_bp.route("/admin/orders/<string:public_order_id>")
@login_required
def admin_order_detail_by_public(public_order_id):
    from flask import current_app
    admin_user = current_app.config.get('APP_ADMIN_USER')
    if current_user.username != admin_user:
        abort(403)
    order = Order.query.filter_by(public_order_id=public_order_id).first_or_404()
    return render_template("admin_order_detail.html", public_order_id=order.public_order_id)

@main_bp.route("/admin/orders")
@login_required
def admin_orders():
    from flask import current_app
    admin_user = current_app.config.get('APP_ADMIN_USER')
    if current_user.username != admin_user:
        abort(403)
    return render_template("admin_orders.html")

@main_bp.route("/admin/orders/<int:order_id>")
@login_required
def admin_order_detail(order_id):
    from flask import current_app
    admin_user = current_app.config.get('APP_ADMIN_USER')
    if current_user.username != admin_user:
        abort(403)
    order = Order.query.get_or_404(order_id)
    return render_template("admin_order_detail.html", public_order_id=order.public_order_id)
