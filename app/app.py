from flask import Flask, abort, render_template, request, redirect, url_for, session, flash, jsonify,  send_from_directory
from flask_login import current_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_session import Session
from sqlalchemy.orm import joinedload
from sqlalchemy import desc, event
from sqlalchemy.engine import Engine
from datetime import datetime, timedelta, timezone
import string
import random
import os
import io
import csv
from .utils import check_string_number_inclusion, concatenate_text_files, create_directory, download_file, download_image, encrypt_password, generate_id, generate_key, get_folders_in_directory, get_json_image_id, is_valid_image, rename_image, resize_image, convert_to_webp, generate_image_icon, ensure_icon_for_url, send_email, init_config, send_emailTls2, str_to_bool, process_image_data, translate, icon_url, big_url
import logging
import json
from werkzeug.utils import secure_filename
import uuid
from openai import OpenAI
import requests
from flask_cors import CORS
from math import ceil
from decimal import Decimal, ROUND_HALF_UP

# Extensions
from .extensions import db, login_manager, mail, limiter, cache, csrf
from .models import User, Product, Variant, ProductImage, VariantImage, Order, OrderItem, Promotion, Country, VatRate, ShippingZone, Category, GlobalSetting, AppCurrency, Address, Message, ProductGroup

# SQLite Performance PRAGMAs
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if dbapi_connection.__class__.__module__.startswith("sqlite3"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA cache_size=-64000")
        cursor.close()

# Blueprints
from .blueprints.cart import cart_bp
from .blueprints.checkout import checkout_bp
from .blueprints.countries import countries_bp
from .blueprints.account import account_bp
from .blueprints.main import main_bp
from .blueprints.api import api_bp

# Logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
file_handler = logging.FileHandler('app.log')
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Global Config Loading (for backward compatibility and extensions)
encryption_key = os.environ.get('ENCRYPTION_KEY')
config_dict = init_config("./config.txt","./encrypt_config_file.txt")

# Expose constants for tests/imports
ADMIN_USER = config_dict.get('APP_ADMIN_USER')
ADMIN_EMAIL = config_dict.get('APP_ADMIN_EMAIL')
ADMIN_PASSWORD = config_dict.get('APP_ADMIN_PASSWORD')
ALLOWED_URLS = config_dict.get('APP_ALLOWED_URLS')

def create_app(test_config=None):
    app = Flask(__name__, static_folder='static', template_folder='templates')

    # Map text file config keys to app config
    app.config['SECRET_KEY'] = config_dict['APP_SECRET_KEY']
    app.config['SQLALCHEMY_DATABASE_URI'] = config_dict['APP_SQLALCHEMY_DATABASE_URI']
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SESSION_TYPE'] = config_dict['APP_SESSION_TYPE']
    app.config['SESSION_PERMANENT'] = str_to_bool(config_dict['APP_SESSION_PERMANENT'])
    app.config['PERMANENT_SESSION_LIFETIME'] = int(config_dict['APP_PERMANENT_SESSION_LIFETIME'])

    # Store custom config in app.config for access in blueprints
    for k, v in config_dict.items():
        app.config[k] = v

    # Explicitly set APP_RESET_CODE if missing, for safety
    if 'APP_RESET_CODE' not in app.config:
        app.config['APP_RESET_CODE'] = 'reset_my_app'

    # Security & Performance Config
    app.config['WTF_CSRF_ENABLED'] = True # Explicitly enable

    # SQLAlchemy Pooling
    # Only apply pooling options for non-SQLite databases to avoid TypeError
    if 'sqlite' not in app.config['SQLALCHEMY_DATABASE_URI']:
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            'pool_size': 10,
            'pool_recycle': 3600,
            'pool_pre_ping': True
        }

    # Caching Config (Defaults)
    app.config['CACHE_TYPE'] = 'SimpleCache'
    app.config['CACHE_DEFAULT_TIMEOUT'] = 300

    # Rate Limiting
    app.config['RATELIMIT_DEFAULT'] = "200 per day"
    app.config['RATELIMIT_STORAGE_URI'] = "memory://"

    # Apply test config (overrides defaults)
    # MOVED this to the end of config block to ensure it overrides defaults
    if test_config:
        app.config.update(test_config)

    # Extensions Init
    db.init_app(app)
    Session(app)

    login_manager.init_app(app)
    login_manager.login_view = 'main.login' # Updated endpoint
    login_manager.session_protection = "strong"

    mail.init_app(app)
    limiter.init_app(app)
    cache.init_app(app)
    csrf.init_app(app)

    CORS(app, origins=["http://localhost:8000"]) # Config?

    # Blueprints
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(cart_bp)
    app.register_blueprint(checkout_bp)
    app.register_blueprint(countries_bp)
    app.register_blueprint(account_bp)

    # Exempt API from CSRF if needed (e.g. for simple fetch without token logic yet)
    # But security requirement says "Enable... globally".
    # I should attempt to make it work.
    # To enable fetch requests to work, I need to expose the token.

    # Context Processors
    @app.context_processor
    def inject_global_settings():
        currency_symbol = '€'
        default_vat_rate = 0.0
        vat_calculation_mode = 'SHIPPING_ADDRESS'
        global_promo_message = ''
        global_promo_enabled = False
        categories = []
        active_groups = []

        try:
            currency = GlobalSetting.query.filter_by(key='currency').first()
            if currency:
                currency_symbol = currency.value

            default_country = Country.query.filter_by(is_default=True).first()
            if default_country:
                default_vat_rate = float(default_country.default_vat_rate)

            vat_mode = GlobalSetting.query.filter_by(key='vat_calculation_mode').first()
            if vat_mode:
                vat_calculation_mode = vat_mode.value

            promo_msg_setting = GlobalSetting.query.filter_by(key='global_promo_message').first()
            if promo_msg_setting:
                global_promo_message = promo_msg_setting.value

            promo_enabled_setting = GlobalSetting.query.filter_by(key='global_promo_enabled').first()
            if promo_enabled_setting:
                global_promo_enabled = str_to_bool(promo_enabled_setting.value)

            categories = Category.query.order_by(Category.name).all()
            active_groups = ProductGroup.query.filter_by(is_active=True).order_by(ProductGroup.name).all()
        except Exception:
            # Handle case where tables are not created yet (OperationalError)
            pass

        return {
            'now': datetime.now(timezone.utc),
            'currency_symbol': currency_symbol,
            'default_vat_rate': default_vat_rate,
            'vat_calculation_mode': vat_calculation_mode,
            'admin_user': app.config.get('APP_ADMIN_USER'),
            'global_promo_message': global_promo_message,
            'global_promo_enabled': global_promo_enabled,
            'categories': categories,
            'active_groups': active_groups
        }

    app.template_filter('icon_url')(icon_url)
    app.template_filter('big_url')(big_url)


    # Error Handlers
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('error.html', code=404, name="Page Not Found", description="The page you are looking for does not exist."), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        return render_template('error.html', code=500, name="Internal Server Error", description="Something went wrong on our end. Please try again later."), 500

    @app.errorhandler(403)
    def forbidden(e):
        return render_template('error.html', code=403, name="Forbidden", description="You do not have permission to access this resource."), 403

    # After Request - Security Headers (CSP)
    @app.after_request
    def set_security_headers(response):
        # Basic CSP - allows self, unsafe-inline (often needed for legacy JS), and data: images
        # In production, 'unsafe-inline' should be removed and nonces used.
        # Given the "vanilla JS" nature, unsafe-inline might be required for now.

        allowed_list = ALLOWED_URLS.replace(';',' ')

        # Ensure cdn.jsdelivr.net is there as a baseline if config is empty, but we trust config.txt
        #if not allowed_list:
        #    allowed_list = "https://cdn.jsdelivr.net"

        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com https://cdn.jsdelivr.net https://js.stripe.com; "
            "style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com https://cdn.jsdelivr.net; "
            "img-src 'self' data: https://images.unsplash.com; "
            "font-src 'self' https://cdnjs.cloudflare.com https://cdn.jsdelivr.net; "
            "connect-src 'self' https://cdn.jsdelivr.net https://api.stripe.com; "
            "frame-src 'self' https://js.stripe.com;"
        )       

        response.headers['Content-Security-Policy'] = csp
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        return response

    return app

# Login loader
@login_manager.user_loader
def load_user(user_id):
    try:
        return User.query.get(int(user_id))
    except Exception:
        return None

app = create_app()

# Setup Database Helper (simplified/moved logic)
def setup_database_cli(app_instance=None):
    from .seeder import setup_database
    if app_instance is None:
        # Fallback to global app if not provided (for CLI usage)
        app_instance = app
    setup_database(app_instance)

setup_database = setup_database_cli

# Run setup on import to ensure DB tables exist (e.g. for Docker/Gunicorn)
if os.environ.get("WERKZEUG_RUN_MAIN") != "true":
    # Simple check to avoid double run in reloader, though idempotent
    try:
        setup_database_cli(app)
    except Exception as e:
        logger.warning(f"Database setup failed on import: {e}")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
