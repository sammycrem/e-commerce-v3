import asyncio
from playwright.async_api import async_playwright

async def verify():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Login
        print("Logging in...")
        await page.goto("http://localhost:5000/login")
        await page.fill('input[name="email"]', 'admin@example.com')
        await page.fill('input[name="password"]', 'adminpass')
        await page.click('button[type="submit"]')
        await page.wait_for_url("http://localhost:5000/")

        # Go to Admin
        print("Navigating to Admin...")
        await page.goto("http://localhost:5000/admin")

        # Verify Categories Tab
        print("Checking Categories Tab...")
        await page.click('#categories-tab')
        await page.wait_for_selector('#tab-categories:not(.d-none)')

        # Add a category
        import random
        cat_name = f"Test Category PW {random.randint(0, 10000)}"
        print(f"Adding a category: {cat_name}")
        await page.fill('#cat_name', cat_name)
        await page.click('#save-category')
        await page.wait_for_selector(f'#category-list >> text={cat_name}')

        # Verify Product Category Dropdown
        print("Checking Product Category Dropdown...")
        await page.click('#products-tab')
        await page.wait_for_selector('#tab-products:not(.d-none)')
        await page.wait_for_selector(f'#category option[value="{cat_name}"]', state="attached")
        print("Category found in product dropdown.")

        # Verify Zoom on Product Page
        print("Checking Zoom on Product Page...")
        await page.goto("http://localhost:5000/product/p-1")

        main_img_wrap = await page.wait_for_selector('.main-image-wrap')
        main_img = await page.wait_for_selector('#main-image')

        # Initial scale
        transform = await main_img.evaluate("el => el.style.transform")
        print(f"Initial transform: {transform}")

        # Click to zoom
        await main_img_wrap.click()
        await asyncio.sleep(0.5)
        transform = await main_img.evaluate("el => el.style.transform")
        print(f"Zoomed transform: {transform}")
        if "scale(2)" in transform:
            print("Zoom successful!")
        else:
            print("Zoom failed!")

        # Click again to unzoom
        await main_img_wrap.click()
        await asyncio.sleep(0.5)
        transform = await main_img.evaluate("el => el.style.transform")
        print(f"Unzoomed transform: {transform}")

        # Verify Dropdown Z-index
        print("Checking Dropdown Z-index...")
        # Need a dropdown to be visible. Maybe the one in the navbar?
        # Actually I can just check the computed style of any .dropdown-menu if it's in the DOM
        z_index = await page.evaluate('''() => {
            const el = document.createElement('div');
            el.className = 'dropdown-menu';
            document.body.appendChild(el);
            const style = window.getComputedStyle(el);
            const z = style.zIndex;
            document.body.removeChild(el);
            return z;
        }''')
        print(f"Dropdown z-index: {z_index}")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(verify())
