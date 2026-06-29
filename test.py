import asyncio
import json
import pathlib
import tempfile
import shutil
from playwright.async_api import async_playwright

async def run_frontier_check(address_data):
    """
    Automates the address availability check on Frontier.com.
    Returns a dictionary containing the availability status and details.
    """
    tmp_dir = tempfile.mkdtemp()
    results = {
        "address_searched": address_data,
        "available": False,
        "plans": [],
        "error": None
    }

    async with async_playwright() as p:
        try:
            # Launch with unique user data dir to support parallel execution
            browser = await p.chromium.launch_persistent_context(
                user_data_dir=tmp_dir,
                headless=False,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-blink-features=AutomationControlled"
                ]
            )
            
            page = await browser.new_page()
            
            # Set a realistic user agent
            await page.set_extra_http_headers({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
            })

            # Navigate to Frontier
            await page.goto("https://frontier.com/shop/", wait_until="networkidle", timeout=60000)

            # Handle potential cookie banners
            try:
                if await page.locator("#onetrust-accept-btn-handler").is_visible():
                    await page.click("#onetrust-accept-btn-handler")
            except:
                pass

            # Fill in the address
            # Note: Frontier's UI often uses a single autocomplete field or split fields.
            # This logic targets the standard availability check pattern.
            address_input = page.locator("input[name='address'], input#address-input, .address-search-input").first
            await address_input.wait_for(state="visible")
            await address_input.fill(address_data.get("street", ""))
            
            # Wait for and select the first suggestion to ensure valid formatting
            await page.wait_for_timeout(2000)
            await page.keyboard.press("ArrowDown")
            await page.keyboard.press("Enter")

            # Click Check Availability
            submit_btn = page.locator("button[type='submit'], #check-availability-btn").first
            await submit_btn.click()

            # Wait for results or redirection
            await page.wait_for_load_state("networkidle")
            
            # Logic to determine availability based on URL or page content
            current_url = page.url
            if "plans" in current_url or "buy" in current_url:
                results["available"] = True
                # Extract plan names if available
                plan_elements = await page.locator("h2, .plan-name, .offer-title").all_inner_texts()
                results["plans"] = [p.strip() for p in plan_elements if p.strip()]
            elif "not-available" in current_url or await page.locator("text=not available").is_visible():
                results["available"] = False
            
        except Exception as e:
            results["error"] = str(e)
        finally:
            await browser.close()
            # Clean up the temporary profile directory
            shutil.rmtree(tmp_dir, ignore_errors=True)

    return results

async def main():
    # Example input data
    test_address = {
        "street": "123 Main St",
        "zip": "90210"
    }
    
    output = await run_frontier_check(test_address)
    print(json.dumps(output, indent=4))

if __name__ == "__main__":
    asyncio.run(main())