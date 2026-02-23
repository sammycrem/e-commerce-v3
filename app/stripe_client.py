from flask import current_app
import stripe

def get_stripe_client():
    api_key = current_app.config.get('APP_STRIPE_SECRET_KEY')
    if not api_key:
        raise ValueError("APP_STRIPE_SECRET_KEY is not configured")
    stripe.api_key = api_key
    return stripe
