from flask import current_app
from mollie.api.client import Client

def get_mollie_client():
    mollie_client = Client()
    api_key = current_app.config.get('APP_MOLLIE_CLIENT_API_KEY')
    # Remove quotes if they exist, as the config parser might not handle them for all keys
    if api_key:
        # Handle potential quotes
        api_key = api_key.strip().strip('"').strip("'")

        # Handle the specific format mentioned by the user if it appears literally
        # "mollie_client.set_api_key" (which is not a valid key itself)
        # We'll assume if it looks like a function call, we might need to extract,
        # but the prompt likely implies the value IS the key or we should just use it.
        # However, a real Mollie key starts with test_ or live_.

        # If the key is literally the placeholder string, we can't use it.
        if api_key == "mollie_client.set_api_key":
             # Try to see if there's a real key in env or fallback
             # But for now, we must raise or log.
             # Let's try to be resilient: maybe it's a mistake in the prompt description
             # and we should just look for a valid pattern.
             pass

        # Robust check
        if not api_key.startswith(('test_', 'live_')):
             # If it doesn't start with test_ or live_, it might be the function call string with an arg?
             # E.g. mollie_client.set_api_key('test_...')
             if 'test_' in api_key:
                 import re
                 match = re.search(r'(test_\w+)', api_key)
                 if match:
                     api_key = match.group(1)
             elif 'live_' in api_key:
                 import re
                 match = re.search(r'(live_\w+)', api_key)
                 if match:
                     api_key = match.group(1)

        if not api_key.startswith(('test_', 'live_')):
             # Detailed error for debugging
             raise ValueError(f"Invalid Mollie API Key format: '{api_key}'. Key must start with 'test_' or 'live_'.")

        mollie_client.set_api_key(api_key)
    else:
        raise ValueError("Mollie API Key is missing.")

    return mollie_client
