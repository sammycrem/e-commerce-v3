from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_mail import Mail
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_caching import Cache
from flask_wtf import CSRFProtect

db = SQLAlchemy()
login_manager = LoginManager()
mail = Mail()
limiter = Limiter(key_func=get_remote_address)
cache = Cache()
csrf = CSRFProtect()
