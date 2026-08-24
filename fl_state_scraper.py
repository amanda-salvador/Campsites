from playwright.sync_api import sync_playwright
import time
from datetime import datetime
import pandas as pd

# ==========================================
# ⚙️ GA STATE PARK TARGET LIST
# ==========================================
START_DATE = "2026-05-15"  # YYYY-MM-DD
NIGHTS = "2"
RIG_LENGTH = "20"

# The Master Target Dictionary
# Add or remove parks here as needed!
GA_PARKS = {
    "Vogel": "530201",
    "Cloudland Canyon": "530148",
    "Fort Mountain": "530158",
    "Skidaway Island": "530190",
    "Tallulah Gorge": "530194",
    "Red Top Mountain": "530184",
    "F.D. Roosevelt": "530156",
    "Stephen C. Foster": "530192"
}


# ==========================================

def sweep_georgia_parks(start_date, nights, length):
    print("\n" + "=" * 50)
    print(f"🍑 INITIATING GEORGIA STATE PARK SWEEP")
    print("=" * 50)

    d = datetime.strptime(start_date, "%Y-%m-%d")
    formatted_date = d.strftime("%m/%d/%Y")

    records = []

    with sync_playwright() as p:
        # Launch the browser ONCE
        browser = p.chromium.launch(headless=False, slow_mo=400)
        context = browser.new_context(viewport={'width': 1280, 'height': 800})
        page = context.new_page()

        # Loop through every park in our dictionary
        for park_name, park_id in GA_PARKS.items():
            print(f"\n🚀 Targeting: {park_name} (ID: {park_id})")

            try:
                url = f"https://gastateparks.reserveamerica.com/campgroundDetails.do?contractCode=GA&parkId={park_id}"
                page.goto(url, wait_until="domcontentloaded", timeout=30000)

                # --- WAKE UP THE FORM ---
                page.wait_for_selector("#unifSearchForm", state="attached", timeout=15000)
                page.click("#unifSearchForm")
                time.sleep(1)

                # 1. SET EQUIPMENT & LENGTH
                page.get_by_label("Looking for").select_option("2001")
                page.get_by_role("textbox", name="Length (ft)").fill(length)

                # 2. SELECT ELECTRIC
                page.get_by_role("checkbox", name="more options...").check()
                page.get_by_role("group", name="Specific Attributes Group").get_by_label(
                    "Electric hookup").select_option("3004")

                # 3. THE CALENDAR BYPASS
                date_box = page.get_by_role("textbox", name="Arrival date")
                date_box.click()
                date_box.fill(formatted_date)

                # Unlock the nights box
                date_box.press("Tab")
                page.locator("body").click()
                page.keyboard.press("Escape")

                time.sleep(1.5)
                page.get_by_role("spinbutton", name="Length of stay:").fill(str(nights))

                # 4. EXECUTE SEARCH
                page.get_by_role("button", name="Search").click()

                # 5. EXTRACTION
                page.wait_for_load_state("networkidle", timeout=20000)
                time.sleep(2)

                # Count how many "Avail" blocks are on the screen
                content = page.content()
                available_spots = content.count("Avail")

                if available_spots > 0:
                    print(f"   ✅ SUCCESS: Found open spots at {park_name}!")
                    records.append({
                        "Park Name": park_name + " State Park (GA)",
                        "Open RV Spots": available_spots,
                        # We will add GPS coordinates later when we merge with the map
                        "Lat": 0.0,
                        "Lon": 0.0,
                        "URL": url
                    })
                else:
                    print(f"   ❌ Booked solid.")

            except Exception as e:
                print(f"   ⚠️ Failed to scan {park_name}. Moving to next target.")
                # We do not crash! We just skip to the next loop iteration.
                continue

            # Be a polite robot: wait 2 seconds before hitting their server again
            time.sleep(2)

        print("\n🛑 Sweep complete. Closing Ghost Browser.")
        browser.close()

    # Convert the results into a Pandas DataFrame
    df = pd.DataFrame(records)
    return df


if __name__ == "__main__":
    results_df = sweep_georgia_parks(START_DATE, NIGHTS, RIG_LENGTH)

    print("\n" + "=" * 50)
    print("📋 FINAL GEORGIA RESULTS")
    print("=" * 50)
    if not results_df.empty:
        print(results_df[["Park Name", "Open RV Spots"]])
    else:
        print("No availability found in Georgia for these dates.")