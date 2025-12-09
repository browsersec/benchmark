import asyncio
import re
from typing import Any
import logging
from playwright.async_api import Page, Playwright, async_playwright, expect, TimeoutError as PlaywrightTimeoutError


async def disconnect_session(page: Page) -> None:
    """Attempt to disconnect the session, forcing click if necessary."""
    try:
        disconnect_btn = page.get_by_role("button", name="Disconnect").nth(1)
        # Try normal click first with short timeout
        await disconnect_btn.click(timeout=5000)
    except PlaywrightTimeoutError:
        logging.warning("Normal disconnect failed, attempting force click...")
        try:
            # Force click even if disabled
            await page.get_by_role("button", name="Disconnect").nth(1).click(force=True, timeout=5000)
        except Exception as e:
            logging.error(f"Force disconnect also failed: {e}")


async def print_chrome_window_dimensions(page: Page):
    """Print the current Chrome window inner and outer dimensions."""
    # JavaScript to get window dimensions
    outer_width = await page.evaluate("window.outerWidth")
    outer_height = await page.evaluate("window.outerHeight")
    inner_width = await page.evaluate("window.innerWidth")
    inner_height = await page.evaluate("window.innerHeight")
    print(f"Chrome Window outer size: {outer_width}x{outer_height}")
    print(f"Chrome Window inner size: {inner_width}x{inner_height}")


async def run(playwright: Playwright, time : float) -> None:
    browser = await playwright.chromium.launch(headless=False)
    context = await browser.new_context()
    page = await context.new_page()
    
    try:
        await page.goto("http://localhost:5173/")
        # Print dimensions after launch and navigation
        await print_chrome_window_dimensions(page)

        await page.get_by_role("link", name="Browser Session").click()
        await page.get_by_role("button", name="Create Browser Session").click()

        await page.locator(".guac-display").press("ControlOrMeta+l")
        await asyncio.sleep(8)  # Use async sleep instead of blocking time.sleep
        await page.locator(".guac-display").type("https://tinyurl.com/ytrickroll", delay=100)
        await asyncio.sleep(5)
        await page.locator(".guac-display").press("Enter")
        await asyncio.sleep(10)
        await page.locator(".guac-display").press("K")
        await asyncio.sleep(2)
        await page.locator(".guac-display").press("K")
        await asyncio.sleep(2)
        await page.locator(".guac-display").press("K")
        await page.locator(".guac-display").press("F")

        logging.info("Pressed ControlOrMeta+F")

        await asyncio.sleep(0.5 * 60)
        logging.info("Video started.")
        await asyncio.sleep(0.5 * 60)

        await page.get_by_role("button", name="Copy connection ID to").click()
        await page.get_by_role("button", name="Copy connection ID to").click()
        await page.get_by_role("button", name="Copy connection ID to").click()

        await asyncio.sleep(time)
        
        await disconnect_session(page)
        logging.info("Disconnected the session.")

    except Exception as e:
        logging.error(f"Error during run: {e}")
        # Always try to disconnect on error
        await disconnect_session(page)
    finally:
        await context.close()
        await browser.close()


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    async with async_playwright() as playwright:
        await run(playwright, time=2*60)


asyncio.run(main())

