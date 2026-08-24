import asyncio
from playwright.async_api import async_playwright


async def check_fl_parks():
    async with async_playwright() as p:
        # Launch a 'headless' browser (runs in background)
        browser = await p.chromium.launch(headless=False)  # Set to True once working
        page = await browser.new_page()

        # Go to the FL State Parks booking engine
        # Note: They often use ReserveAmerica / FloridaStateParks.org
        await page.goto("https://www.floridastateparks.org/stay-night")

        # Wait for the search box to appear
        await page.wait_for_selector('input[placeholder="Search by park name"]')

        # Take a screenshot so the AI can "see" what's available
        await page.screenshot(path="fl_state_parks.png")
        print("I've captured the current state park availability page!")

        await browser.close()


asyncio.run(check_fl_parks())