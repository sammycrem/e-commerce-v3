from .extensions import db
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import JSON as SA_JSON, asc, desc
from datetime import datetime, timezone
import uuid
from flask_login import UserMixin

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False, index=True) # Indexed
    user_id = db.Column(db.String(20), unique=True, nullable=False)
    password = db.Column(db.String(128), nullable=False)
    encrypted_password = db.Column(db.String(128), nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    validation = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    orders = db.relationship('Order', back_populates='user')
    addresses = db.relationship('Address', back_populates='user', cascade='all, delete-orphan')
    messages = db.relationship('Message', back_populates='user', cascade='all, delete-orphan')
    reviews = db.relationship('Review', back_populates='user', cascade='all, delete-orphan')

class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    product_sku = db.Column(db.Text, nullable=False, unique=True)
    name = db.Column(db.Text, nullable=False)
    slug = db.Column(db.String(255), unique=True, index=True)
    description = db.Column(db.Text)
    meta_title = db.Column(db.String(255))
    meta_description = db.Column(db.Text)
    category = db.Column(db.Text, index=True) # Indexed
    base_price_cents = db.Column(db.BigInteger, nullable=False)
    short_description = db.Column(db.Text)
    product_details = db.Column(db.Text)
    related_products = db.Column(SA_JSON)
    proposed_products = db.Column(SA_JSON)
    tag1 = db.Column(db.Text)
    tag2 = db.Column(db.Text)
    tag3 = db.Column(db.Text)
    weight_grams = db.Column(db.Integer, nullable=True)
    dimensions_json = db.Column(SA_JSON, nullable=True)
    message = db.Column(db.Text, nullable=True)
    # Status: 'draft', 'published', 'decommissioned'
    status = db.Column(db.String(20), default='draft', nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    variants = db.relationship('Variant', back_populates='product', cascade='all, delete-orphan')
    images = db.relationship('ProductImage', back_populates='product', cascade='all, delete-orphan', order_by='ProductImage.display_order')
    reviews = db.relationship('Review', back_populates='product', cascade='all, delete-orphan')

    @property
    def average_rating(self):
        if not self.reviews:
            return 0
        total = sum(r.rating for r in self.reviews)
        return round(total / len(self.reviews), 1)

    @property
    def review_count(self):
        return len(self.reviews)

class Variant(db.Model):
    __tablename__ = 'variants'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete='CASCADE'), nullable=False)
    sku = db.Column(db.Text, nullable=False, unique=True)
    color_name = db.Column(db.Text)
    size = db.Column(db.Text)
    stock_quantity = db.Column(db.Integer, nullable=False, default=0)
    price_modifier_cents = db.Column(db.BigInteger, nullable=False, default=0)
    product = db.relationship('Product', back_populates='variants')
    images = db.relationship('VariantImage', back_populates='variant', cascade='all, delete-orphan', order_by='VariantImage.display_order')

class ProductImage(db.Model):
    __tablename__ = 'product_images'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete='CASCADE'), nullable=False)
    url = db.Column(db.Text, nullable=False)
    alt_text = db.Column(db.Text)
    display_order = db.Column(db.Integer, default=0)
    product = db.relationship('Product', back_populates='images')

class VariantImage(db.Model):
    __tablename__ = 'variant_images'
    id = db.Column(db.Integer, primary_key=True)
    variant_id = db.Column(db.Integer, db.ForeignKey('variants.id', ondelete='CASCADE'), nullable=False)
    url = db.Column(db.Text, nullable=False)
    alt_text = db.Column(db.Text)
    display_order = db.Column(db.Integer, default=0)
    variant = db.relationship('Variant', back_populates='images')

class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.Integer, primary_key=True)
    public_order_id = db.Column(db.Text, nullable=False, unique=True, default=lambda: f"ORD-{str(uuid.uuid4())[:8].upper()}")
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    status = db.Column(db.String(30), nullable=False, default='PENDING', index=True) # Indexed
    subtotal_cents = db.Column(db.BigInteger, nullable=False, default=0)
    discount_cents = db.Column(db.BigInteger, nullable=False, default=0)
    shipping_cost_cents = db.Column(db.BigInteger, nullable=False, default=0)
    vat_cents = db.Column(db.BigInteger, nullable=False, default=0)
    total_cents = db.Column(db.BigInteger, nullable=False, default=0)
    shipping_method = db.Column(db.String(50), nullable=True)
    payment_method = db.Column(db.String(50), nullable=True)
    payment_provider = db.Column(db.String(50), nullable=True)
    payment_transaction_id = db.Column(db.Text, nullable=True)
    comment = db.Column(db.Text, nullable=True)
    shipping_provider = db.Column(db.Text, nullable=True)
    tracking_number = db.Column(db.Text, nullable=True)
    promo_code = db.Column(db.String(50), nullable=True)
    shipping_address_snapshot = db.Column(db.JSON, nullable=True)
    billing_address_snapshot = db.Column(db.JSON, nullable=True)
    shipped_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    user = db.relationship('User', back_populates='orders')
    items = db.relationship('OrderItem', back_populates='order', cascade='all, delete-orphan')
    messages = db.relationship('Message', back_populates='order', cascade='all, delete-orphan')

class OrderItem(db.Model):
    __tablename__ = 'order_items'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id', ondelete='CASCADE'), nullable=False)
    variant_sku = db.Column(db.Text, nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    product_snapshot = db.Column(db.JSON, nullable=False)
    unit_price_cents = db.Column(db.BigInteger, nullable=False)
    order = db.relationship('Order', back_populates='items')

class Promotion(db.Model):
    __tablename__ = 'promotions'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.Text, nullable=False, unique=True)
    description = db.Column(db.Text)
    discount_type = db.Column(db.String(10), nullable=False)
    discount_value = db.Column(db.BigInteger, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    valid_to = db.Column(db.DateTime)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    user = db.relationship('User', backref='promotions')

class Country(db.Model):
    __tablename__ = 'countries'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, nullable=False, unique=True)
    iso_code = db.Column(db.String(2), nullable=False, unique=True)
    default_vat_rate = db.Column(db.Numeric(5,4), nullable=False, default=0.0)
    currency_code = db.Column(db.String(3), nullable=False, default='USD')
    shipping_cost_cents = db.Column(db.BigInteger, nullable=False, default=0)
    free_shipping_threshold_cents = db.Column(db.BigInteger, nullable=True)
    is_default = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))

class VatRate(db.Model):
    __tablename__ = 'vat_rates'
    id = db.Column(db.Integer, primary_key=True)
    country_id = db.Column(db.Integer, db.ForeignKey('countries.id', ondelete='CASCADE'), nullable=False)
    category = db.Column(db.Text)
    vat_rate = db.Column(db.Numeric(5,4), nullable=False)
    country = db.relationship('Country', backref='vat_rates')

class ShippingZone(db.Model):
    __tablename__ = 'shipping_zones'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, nullable=False, unique=True)
    countries_json = db.Column(SA_JSON, nullable=False)
    base_cost_cents = db.Column(db.BigInteger, nullable=False, default=0)
    cost_per_kg_cents = db.Column(db.BigInteger, nullable=False, default=0)
    volumetric_divisor = db.Column(db.Integer, nullable=False, default=5000)
    free_shipping_threshold_cents = db.Column(db.BigInteger, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))

product_group_association = db.Table('product_group_association',
    db.Column('product_id', db.Integer, db.ForeignKey('products.id', ondelete='CASCADE'), primary_key=True),
    db.Column('group_id', db.Integer, db.ForeignKey('product_groups.id', ondelete='CASCADE'), primary_key=True)
)

class ProductGroup(db.Model):
    __tablename__ = 'product_groups'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    slug = db.Column(db.String(120), unique=True, index=True)
    is_active = db.Column(db.Boolean, default=False)
    meta_title = db.Column(db.String(255))
    meta_description = db.Column(db.Text)
    products = db.relationship('Product', secondary=product_group_association, backref=db.backref('groups', lazy='dynamic'))

class Category(db.Model):
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    slug = db.Column(db.String(120), unique=True, index=True)
    meta_title = db.Column(db.String(255))
    meta_description = db.Column(db.Text)

class GlobalSetting(db.Model):
    __tablename__ = 'global_settings'
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.Text, nullable=True)

class AppCurrency(db.Model):
    __tablename__ = 'app_currencies'
    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(10), unique=True, nullable=False)

class Address(db.Model):
    __tablename__ = 'addresses'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    address_type = db.Column(db.String(20), nullable=False)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    address_line_1 = db.Column(db.String(255), nullable=False)
    address_line_2 = db.Column(db.String(255))
    city = db.Column(db.String(100), nullable=False)
    state = db.Column(db.String(100))
    postal_code = db.Column(db.String(20), nullable=False)
    country_iso_code = db.Column(db.String(2), nullable=False)
    phone_number = db.Column(db.String(20))
    is_default = db.Column(db.Boolean, default=False)
    user = db.relationship('User', back_populates='addresses')

class Message(db.Model):
    __tablename__ = 'messages'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id', ondelete='CASCADE'), nullable=False)
    sender_type = db.Column(db.String(10), nullable=False) # 'USER' or 'ADMIN'
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    is_read = db.Column(db.Boolean, default=False)

    user = db.relationship('User', back_populates='messages')
    order = db.relationship('Order', back_populates='messages')

class Review(db.Model):
    __tablename__ = 'reviews'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete='CASCADE'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))

    user = db.relationship('User', back_populates='reviews')
    product = db.relationship('Product', back_populates='reviews')

class PasswordResetToken(db.Model):
    __tablename__ = 'password_reset_tokens'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    token = db.Column(db.String(100), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    expires_at = db.Column(db.DateTime, nullable=False)
    is_used = db.Column(db.Boolean, default=False)

    user = db.relationship('User', backref=db.backref('reset_tokens', lazy='dynamic'))
