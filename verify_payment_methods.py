
from playwright.sync_api import sync_playwright, expect
import time

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport={'width': 1280, 'height': 800})
        page = context.new_page()

        try:
            # Login
            print("Logging in...")
            page.goto("http://localhost:5000/login")
            page.fill("input[name='email']", "admin@example.com")
            page.fill("input[name='password']", "adminpass")
            page.click("button:has-text('Login')")
            page.wait_for_url("http://localhost:5000/")
            print("Logged in.")

            # Add to cart
            print("Going to product page...")
            page.goto("http://localhost:5000/product/p-1")
            page.wait_for_selector(".size-btn", timeout=5000)
            print("Adding to cart...")
            page.click("#add-to-cart")
            expect(page.locator("#add-to-cart")).to_have_text("Added ✓")
            print("Added to cart.")

            # Go to checkout
            print("Going to cart page...")
            page.goto("http://localhost:5000/cart")
            page.wait_for_selector("#checkout-btn")
            print("Clicking checkout...")
            page.click("#checkout-btn")

            # Shipping Address
            print("Checking URL...")
            # If we are at shipping address and no address exists (alert visible)
            if "shipping-address" in page.url:
                print("At Shipping Address page.")
                if page.locator("button:has-text('New Address')").is_visible():
                    print("Opening New Address modal...")
                    page.click("button:has-text('New Address')")
                    page.wait_for_selector("#addAddressModal", state="visible")

                    print("Filling address...")
                    page.select_option("select[name='address_type']", "shipping")
                    page.fill("input[name='first_name']", "Test")
                    page.fill("input[name='last_name']", "User")
                    page.fill("input[name='address_line_1']", "123 Test St")
                    page.fill("input[name='city']", "Test City")
                    page.fill("input[name='postal_code']", "12345")
                    # Assuming Country select has values like 'US', 'DE', etc.
                    # Seeding creates US, DE, FR.
                    page.select_option("select[name='country']", "US")
                    page.fill("input[name='phone_number']", "555-1234")

                    page.click("button:has-text('Save Address')")
                    print("Address saved.")
                    # Wait for reload
                    page.wait_for_load_state("networkidle")

                # Now proceed
                print("Clicking Proceed to Checkout (to Shipping Methods)...")
                # The button text is PROCEED TO CHECKOUT but it's a link to shipping-methods
                page.click("a[href*='shipping-methods']")

            # Shipping Methods
            print("Waiting for Shipping Methods page...")
            page.wait_for_url("**/checkout/shipping-methods")
            print("At Shipping Methods page.")

            # Continue to Payment
            # Assuming there is a form or button.
            # In shipping_methods.html (not read but assumed standard), there is a 'Continue' button usually.
            # Let's inspect the page content or guess.
            # Usually it lists methods and has a form.
            # If I can't find 'Continue', I'll print page content.
            # But earlier logs didn't fail there, it failed waiting for payment-methods.
            # So I assume there is a way to proceed.
            # I'll look for "Continue" or "Proceed".
            # Or "Payment Methods" link?
            # Actually, `checkout_bp.shipping_methods` renders `shipping_methods.html`.
            # I haven't read that file.
            # But the layout usually has a primary button.
            # I will try to click the primary button in the summary card or form.

            # Check for form submission button
            if page.locator("button[type='submit']").count() > 0:
                 page.click("button[type='submit']")
            elif page.locator("a[href*='payment-methods']").count() > 0:
                 page.click("a[href*='payment-methods']")
            else:
                 # Fallback: try to find any primary button
                 page.click(".btn-primary")

            # Payment methods
            print("Waiting for Payment Methods page...")
            page.wait_for_url("**/checkout/payment-methods")

            # Verify Stripe and Mollie
            print("Verifying payment options...")
            expect(page.locator("label:has-text('Stripe')")).to_be_visible()
            expect(page.locator("label:has-text('Mollie')")).to_be_visible()

            # Take screenshot
            page.screenshot(path="verification_payment.png", full_page=True)
            print("Screenshot taken: verification_payment.png")

        except Exception as e:
            print(f"Error: {e}")
            page.screenshot(path="verification_error.png")
            raise e
        finally:
            browser.close()

if __name__ == "__main__":
    run()
