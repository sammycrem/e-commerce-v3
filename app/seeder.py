from .extensions import db
from .models import User, Product, Variant, ProductImage, VariantImage, Promotion, Country, ShippingZone, Category, GlobalSetting, AppCurrency, ProductGroup
from .utils import encrypt_password, generate_id, ensure_icon_for_url, slugify
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
import logging
import os
from flask import current_app

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
file_handler = logging.FileHandler('app.log')
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Constants
RECREATE_IF_EXISTS = False
BASE_IMAGE_URL = "/static/ec/products/img"
PRODUCT_COUNT = 4
COLORS = [
    {"name": "White", "code": "white", "prefix": "a", "price_modifier_pct": 0.0},
    {"name": "Red",   "code": "red",   "prefix": "b", "price_modifier_pct": 0.20},
    {"name": "Black", "code": "black", "prefix": "c", "price_modifier_pct": 0.10},
]
SIZES = ["S", "M", "L", "XL"]
DEFAULT_STOCK = 10
BASE_PRICES_USD = {
    "p-1": 12.00,
    "p-2": 18.50,
    "p-3": 22.00,
    "p-4": 15.75
}

def usd_to_cents(usd):
    d = Decimal(str(usd)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return int(d * 100)

def create_product_data(product_key, category=None, name=None):
    # New SKU format: T-Shirt_p-1_x5 (example, we'll just append random suffix)
    import random
    import string
    suffix_p = f"{random.choice(string.ascii_lowercase)}{random.randint(0,9)}"
    sku = f"{product_key}_{suffix_p}"

    if not name:
        name = f"T-Shirt {product_key.upper()}"

    if not category:
        category = "Graphic Tees"

    description = f"Comfortable cotton tee — design {product_key.upper()}."
    base_price_usd = BASE_PRICES_USD.get(product_key, 19.99)
    # If product_key matches p-X pattern but we have multiple categories,
    # we reuse the base prices.
    # Extract base key if possible (e.g. p-1 from p-1)
    base_key = product_key.split('_')[0] if '_' in product_key else product_key
    if base_key not in BASE_PRICES_USD and len(base_key) > 2:
         # Try to match just p-X
         pass

    base_price_cents = usd_to_cents(base_price_usd)
    product_image_url = f"{BASE_IMAGE_URL}/{base_key}/a-1.webp"

    variants = []
    for color in COLORS:
        color_prefix = color["prefix"]
        color_name = color["name"]
        modifier_pct = color["price_modifier_pct"]
        variant_images = [
            {"url": f"{BASE_IMAGE_URL}/{base_key}/{color_prefix}-1.webp", "alt_text": f"{color_name} image 1"},
            {"url": f"{BASE_IMAGE_URL}/{base_key}/{color_prefix}-2.webp", "alt_text": f"{color_name} image 2"},
            {"url": f"{BASE_IMAGE_URL}/{base_key}/{color_prefix}-3.webp", "alt_text": f"{color_name} image 3"},
        ]

        for size in SIZES:
            # New Variant SKU format: ProductSKU_Color_Size_Suffix
            # suffix: letter + 0-99
            import string
            suffix_v = f"{random.choice(string.ascii_lowercase)}{random.randint(0,99)}"
            variant_sku = f"{sku}_{color_name}_{size}_{suffix_v}"

            price_modifier_cents = int(round(base_price_cents * modifier_pct))
            variants.append({
                "sku": variant_sku,
                "color_name": color_name,
                "size": size,
                "stock_quantity": DEFAULT_STOCK,
                "price_modifier_cents": price_modifier_cents,
                "images": variant_images
            })

    product_images = [
        {"url": f"{BASE_IMAGE_URL}/{base_key}/a-1.webp", "alt_text": f"{base_key} white 1", "display_order": 0},
        {"url": f"{BASE_IMAGE_URL}/{base_key}/a-2.webp", "alt_text": f"{base_key} white 2", "display_order": 1},
        {"url": f"{BASE_IMAGE_URL}/{base_key}/a-3.webp", "alt_text": f"{base_key} white 3", "display_order": 2},
        {"url": f"{BASE_IMAGE_URL}/{base_key}/b-1.webp", "alt_text": f"{base_key} red 1", "display_order": 3},
        {"url": f"{BASE_IMAGE_URL}/{base_key}/b-2.webp", "alt_text": f"{base_key} red 2", "display_order": 4},
        {"url": f"{BASE_IMAGE_URL}/{base_key}/b-3.webp", "alt_text": f"{base_key} red 3", "display_order": 5},
        {"url": f"{BASE_IMAGE_URL}/{base_key}/c-1.webp", "alt_text": f"{base_key} black 1", "display_order": 6},
        {"url": f"{BASE_IMAGE_URL}/{base_key}/c-2.webp", "alt_text": f"{base_key} black 2", "display_order": 7},
        {"url": f"{BASE_IMAGE_URL}/{base_key}/c-3.webp", "alt_text": f"{base_key} black 3", "display_order": 8},
    ]

    related = []
    proposed = []
    message = "New collection"

    if base_key == "p-1":
        related = ["p-2", "p-3"] # These references might break if SKUs are randomized globally
        proposed = ["p-4"]

    return {
        "product_sku": sku,
        "name": name,
        "slug": slugify(name),
        "category": category,
        "description": description,
        "short_description": f"Short desc for {sku}",
        "product_details": f"Detailed info for {sku}",
        "related_products": related,
        "proposed_products": proposed,
        "tag1": "tag1",
        "tag2": "tag2",
        "tag3": "tag3",
        "message": message,
        "category": category,
        "base_price_cents": base_price_cents,
        "image_url": product_image_url,
        "images": product_images,
        "variants": variants
    }

def safe_delete_product_by_sku(session, sku):
    p = Product.query.filter_by(product_sku=sku).first()
    if p:
        session.delete(p)
        session.flush()

def insert_product(session, pdata):
    sku = pdata["product_sku"]
    product = Product(
        product_sku=sku,
        name=pdata["name"],
        slug=pdata.get("slug"),
        description=pdata.get("description"),
        short_description=pdata.get("short_description"),
        product_details=pdata.get("product_details"),
        related_products=pdata.get("related_products"),
        proposed_products=pdata.get("proposed_products"),
        tag1=pdata.get("tag1"),
        tag2=pdata.get("tag2"),
        tag3=pdata.get("tag3"),
        category=pdata.get("category"),
        message=pdata.get("message"),
        status='published',
        base_price_cents=int(pdata["base_price_cents"])
    )
    session.add(product)
    session.flush()

    for idx, img in enumerate(pdata.get("images", [])):
        url = img["url"]
        ensure_icon_for_url(url, current_app.root_path)
        pi = ProductImage(
            product_id=product.id,
            url=url,
            alt_text=img.get("alt_text", ""),
            display_order=int(img.get("display_order", idx))
        )
        session.add(pi)

    for v in pdata.get("variants", []):
        variant = Variant(
            product_id=product.id,
            sku=v["sku"],
            color_name=v.get("color_name"),
            size=v.get("size"),
            stock_quantity=int(v.get("stock_quantity") or 0),
            price_modifier_cents=int(v.get("price_modifier_cents") or 0)
        )
        session.add(variant)
        session.flush()
        for idx, vi in enumerate(v.get("images", []) or []):
            vurl = vi.get("url")
            ensure_icon_for_url(vurl, current_app.root_path)
            vimg = VariantImage(
                variant_id=variant.id,
                url=vurl,
                alt_text=vi.get("alt_text", ""),
                display_order=idx
            )
            session.add(vimg)

    return product

def create_user(user_name, user_ID, user_email, user_pssword):
    # Retrieve encryption key from env
    encryption_key = os.environ.get('ENCRYPTION_KEY')
    encrypted_Password = encrypt_password(user_pssword, encryption_key)
    xuser = User(username=user_name.lower(), user_id=user_ID, password=generate_password_hash(user_pssword), encrypted_password= encrypted_Password, email=user_email.lower())
    db.session.add(xuser)
    db.session.commit()
    # Directory creation handled elsewhere or skipped
    return xuser

def setup_database(app):
    with app.app_context():
        # Ensure database directory exists for SQLite
        uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
        if uri.startswith('sqlite:///'):
            db_path = uri.replace('sqlite:///', '')
            # Handle absolute paths properly if needed, but for now just dirname
            if db_path != ':memory:':
                db_dir = os.path.dirname(db_path)
                if db_dir and not os.path.exists(db_dir):
                    try:
                        os.makedirs(db_dir, exist_ok=True)
                        print(f"Created database directory: {db_dir}")
                    except OSError as e:
                        logger.error(f"Failed to create database directory {db_dir}: {e}")

        db.create_all()

        ADMIN_USER = app.config.get('APP_ADMIN_USER', 'admin')
        ADMIN_EMAIL = app.config.get('APP_ADMIN_EMAIL', 'admin@example.com')
        ADMIN_PASSWORD = app.config.get('APP_ADMIN_PASSWORD', 'password')

        if not User.query.filter_by(username=ADMIN_USER).first():
            create_user(ADMIN_USER, generate_id(6) + '_1', ADMIN_EMAIL, ADMIN_PASSWORD)
            users = ["jimmy", "rami", "christophe","olivier","majed","clara","aline","oscar","jean"]
            for xuser_name in users:
                if not User.query.filter_by(username=xuser_name).first():
                    create_user(xuser_name, generate_id(6) + '_1', xuser_name+"@nomail.local", '123')

        if not Promotion.query.first():
            promo = Promotion(
                code='SAVE20',
                description='Get 20% off your entire order!',
                discount_type='PERCENT',
                discount_value=20,
                is_active=True,
                valid_to = datetime.now(timezone.utc) + timedelta(days=30)
            )
            db.session.add(promo)
            db.session.commit()

        if not Country.query.first():
            c_us = Country(name='United States', iso_code='US', default_vat_rate=0.07, currency_code='USD', shipping_cost_cents=1500)
            c_de = Country(name='Germany', iso_code='DE', default_vat_rate=0.19, currency_code='EUR', shipping_cost_cents=800, free_shipping_threshold_cents=3900, is_default=True)
            c_fr = Country(name='France', iso_code='FR', default_vat_rate=0.2, currency_code='EUR', shipping_cost_cents=1000, free_shipping_threshold_cents=5000)
            db.session.add_all([c_us, c_de,c_fr])
            db.session.commit()

        if not ShippingZone.query.first():
            zone_na = ShippingZone(name='North America', countries_json=['US','CA'], base_cost_cents=500, cost_per_kg_cents=1000, volumetric_divisor=5000, free_shipping_threshold_cents=10000)
            zone_eu = ShippingZone(name='Europe', countries_json=['DE','FR','IT'], base_cost_cents=700, cost_per_kg_cents=2500, volumetric_divisor=5000, free_shipping_threshold_cents=15000)
            db.session.add_all([zone_na, zone_eu])
            db.session.commit()

        # Seed categories logic updated below in the product loop
        if not Category.query.first():
            db.session.add_all([
                Category(name='Graphic Tees', slug='graphic-tees'),
                Category(name='Accessories', slug='accessories'),
                Category(name='Apparel', slug='apparel')
            ])
            db.session.commit()

        if not AppCurrency.query.first():
            db.session.add_all([
                AppCurrency(symbol='€'),
                AppCurrency(symbol='$'),
                AppCurrency(symbol='CHF'),
                AppCurrency(symbol='£')
            ])
            db.session.commit()

        if not GlobalSetting.query.filter_by(key='currency').first():
            db.session.add(GlobalSetting(key='currency', value='€'))
            db.session.commit()

        if not Product.query.filter_by(product_sku='SAMPLE-SKU').first():
            product = Product(
                product_sku='SAMPLE-SKU',
                name='Sample Product',
                slug='sample-product',
                description='This is a sample product.',
                category='Samples',
                base_price_cents=12345
            )
            db.session.add(product)
            db.session.flush()

            if not Variant.query.filter_by(sku='SAMPLE-SKU-VAR').first():
                variant = Variant(
                    product_id=product.id,
                    sku='SAMPLE-SKU-VAR',
                    color_name='Red',
                    size='M',
                    stock_quantity=10,
                    price_modifier_cents=0
                )
                db.session.add(variant)
            db.session.commit()

        created = []
        try:
            categories = ["Man - Graphic Tees", "Woman Graphic Tees", "Children Graphic Tees", "Mixed Collection"]
            # Base keys to cycle through
            base_keys = ["p-1", "p-2", "p-3", "p-4"]

            # Use index j to loop through categories
            for j in range(len(categories)):
                cat_name = categories[j]

                # Ensure category exists
                if not Category.query.filter_by(name=cat_name).first():
                    db.session.add(Category(name=cat_name, slug=slugify(cat_name)))
                    db.session.commit()

                # Create PRODUCT_COUNT products for EACH category
                for i in range(1, PRODUCT_COUNT + 1):
                    # Cycle through base keys p-1..p-4
                    base_key = base_keys[(i-1) % len(base_keys)]

                    name = f"T-Shirt {base_key.upper()} - {cat_name}"

                    if Product.query.filter_by(name=name).first():
                        continue

                    pdata = create_product_data(base_key, cat_name, name)

                    prod = insert_product(db.session, pdata)
                    created.append(prod.product_sku)

                db.session.commit()

            if not ProductGroup.query.first():
                featured = ProductGroup(name='Featured Collection', slug='featured-collection', is_active=True)
                best_sellers = ProductGroup(name='Best Sellers', slug='best-sellers', is_active=True)
                db.session.add_all([featured, best_sellers])
                db.session.commit()

                # Add some products to groups
                all_prods = Product.query.filter_by(status='published').limit(12).all()
                featured.products = all_prods[:8]
                best_sellers.products = all_prods[4:12]
                db.session.commit()

        except Exception as exc:
            db.session.rollback()
            logger.error(f"Error during seeding: {exc}")