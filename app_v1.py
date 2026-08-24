import requests
import time
import pandas as pd
import folium
import webbrowser
import os
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright

# --- NEW IMPORTS FOR ADDRESS LOOKUP ---
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut

# --------------------------------------

from dotenv import load_dotenv

# Reads RIDB_API_KEY out of the .env file sitting next to this script.
load_dotenv()

# ==========================================
# ⚙️ YOUR TRIP SETTINGS
# ==========================================
START_DATE = "2026-09-29"  # Format: YYYY-MM-DD
NIGHTS = 7
MIN_RV_LENGTH = 20

# --- REGION TOGGLE ---
# "FL"   = Florida only (federal sites in FL + FL state parks)
# "GA"   = Georgia only (federal sites in GA + GA state parks)
# "BOTH" = Florida and Georgia
SCAN_REGION = "Both"

# --- FEDERAL SCAN SCOPE ---
# True  = discover & check EVERY reservable recreation.gov campground in the SCAN_REGION state(s)
# False = only check the hand-picked spots in federal_watchlist (old behavior)
SCAN_ALL_FEDERAL = True

# Free key from https://ridb.recreation.gov/profile -> API Keys (only needed if SCAN_ALL_FEDERAL = True)
# Put it in .env as RIDB_API_KEY=... — see .env.example. Never paste it in here.
RIDB_API_KEY = os.getenv("RIDB_API_KEY", "YOUR_RIDB_API_KEY_HERE")

# --- (internal) resolves SCAN_REGION into a list of state codes, don't need to touch this ---
_REGION_MAP = {"FL": ["FL"], "GA": ["GA"], "BOTH": ["FL", "GA"]}
FEDERAL_STATES = _REGION_MAP.get(SCAN_REGION.upper(), ["FL", "GA"])
# ==========================================

# --- 1. FEDERAL WATCHLIST ---
federal_watchlist = {
    # 🌴 FLORIDA
    "Midway (Big Cypress)": {"id": "246892", "lat": 25.8454, "lon": -80.9811},
    "Flamingo (Everglades)": {"id": "232463", "lat": 25.1338, "lon": -80.9372},
    "Salt Springs (Ocala)": {"id": "233920", "lat": 29.3514, "lon": -81.7336},
    "Ocean Pond (Osceola)": {"id": "10352022", "lat": 30.3130, "lon": -82.4286},
    "Fort Pickens (Panhandle)": {"id": "234704", "lat": 30.3294, "lon": -87.2346},
    "Ortona South (USACE)": {"id": "233570", "lat": 26.7865, "lon": -81.3090},
    "W.P. Franklin North (USACE)": {"id": "233661", "lat": 26.7225, "lon": -81.6931},
    "St. Lucie South (USACE)": {"id": "233631", "lat": 27.1098, "lon": -80.2842},

    # 🍑 GEORGIA
    "McKinney (Lake Allatoona)": {"id": "232537", "lat": 34.1378, "lon": -84.7214},
    "Bolding Mill (Lake Lanier)": {"id": "232551", "lat": 34.2882, "lon": -83.9298},
    "Old Federal (Lake Lanier)": {"id": "232657", "lat": 34.2541, "lon": -83.9351},
    "Eastbank (Lake Seminole)": {"id": "232580", "lat": 30.7100, "lon": -84.8600},
    "Bluff Creek (Walter F. George)": {"id": "232529", "lat": 32.1852, "lon": -85.0744},
    "R. Shaefer Heard (West Point)": {"id": "232683", "lat": 32.9366, "lon": -85.1851},

    # 🌙 SOUTH CAROLINA
    "Twin Lakes (Hartwell)": {"id": "232727", "lat": 34.6042, "lon": -82.8465},
    "Springfield (Hartwell)": {"id": "233481", "lat": 34.4025, "lon": -82.8361},
    "Watsadler (Hartwell)": {"id": "233483", "lat": 34.3312, "lon": -82.8222},
    "Petersburg (J. Strom Thurmond)": {"id": "232668", "lat": 33.6642, "lon": -82.1956},
    "Buck Hall (Francis Marion)": {"id": "233918", "lat": 32.9961, "lon": -79.5606},

    # 🎸 TENNESSEE
    "Bandy Creek (Big South Fork)": {"id": "232466", "lat": 36.4851, "lon": -84.6978},
    "Defeated Creek (Cordell Hull)": {"id": "232572", "lat": 36.3150, "lon": -85.9328},
    "Floating Mill (Center Hill)": {"id": "232589", "lat": 36.0967, "lon": -85.7656},
    "Dale Hollow Dam (USACE)": {"id": "232609", "lat": 36.5369, "lon": -85.4497},
    "Seven Points (Percy Priest)": {"id": "232596", "lat": 36.0988, "lon": -86.5413},
    "Cove Lake (State/Federal)": {"id": "232474", "lat": 36.3015, "lon": -84.1834}
}

# --- 2. STATE PARK DIRECTORIES ---
GA_PARKS_IDS = {
    # The Mountains & Canyons
    "Vogel": "530201",
    "Cloudland Canyon": "530148",
    "Fort Mountain": "530158",
    "Tallulah Gorge": "530194",
    "Black Rock Mountain": "530146",
    "James H. Floyd": "530170",
    "Moccasin Creek": "530181",

    # The Lakes & Rivers
    "Red Top Mountain": "530184",
    "Elijah Clark": "530155",
    "High Falls": "530168",
    "Mistletoe": "530180",
    "Richard B. Russell": "530186",
    "Tugaloo": "530195",
    "Georgia Veterans": "530161",
    "Fort Yargo": "530159",
    "Seminole": "530188",
    "Florence Marina": "530157",

    # The Forests, Coast, & Historic Sites
    "Skidaway Island": "530190",
    "F.D. Roosevelt": "530153",
    "Stephen C. Foster": "530192",
    "Hard Labor Creek": "530166",
    "Providence Canyon": "530185",
    "Crooked River": "530149",
    "Laura S. Walker": "530177",
    "Indian Springs": "530165",
    "Magnolia Springs": "530179",
    "Watson Mill Bridge": "530199",
    "A.H. Stephens": "530145",
    "George L. Smith": "530162",
    "Jack Hill": "530164"
}

STATE_PARK_GPS = {
    # ==========================================
    # 🌴 FLORIDA STATE PARKS (RV Accessible)
    # ==========================================
    "Big Lagoon State Park": (30.3129, -87.4042),
    "Blackwater River State Park": (30.7061, -86.8797),
    "Dr. Julian G. Bruce St. George Island State Park": (29.7121, -84.7981),
    "Falling Waters State Park": (30.7275, -85.5284),
    "Florida Caverns State Park": (30.8123, -85.2330),
    "Fred Gannon Rocky Bayou State Park": (30.4996, -86.4382),
    "Grayton Beach State Park": (30.3292, -86.1555),
    "Henderson Beach State Park": (30.3831, -86.4428),
    "Ochlockonee River State Park": (30.0000, -84.4789),
    "St. Andrews State Park": (30.1340, -85.7336),
    "T.H. Stone Memorial St. Joseph Peninsula State Park": (29.7547, -85.3970),
    "Three Rivers State Park": (30.7323, -84.9540),
    "Topsail Hill Preserve State Park": (30.3703, -86.2758),
    "Anastasia State Park": (29.8761, -81.2743),
    "Faver-Dykes State Park": (29.6644, -81.2581),
    "Fort Clinch State Park": (30.6976, -81.4443),
    "Gilchrist Blue Springs State Park": (29.8290, -82.7600),
    "Little Talbot Island State Park": (30.4578, -81.4239),
    "Manatee Springs State Park": (29.4897, -82.9772),
    "Mike Roess Gold Head Branch State Park": (29.8370, -81.9566),
    "O'Leno State Park": (29.9144, -82.5765),
    "Paynes Prairie Preserve State Park": (29.5314, -82.2882),
    "Stephen Foster Folk Culture Center State Park": (30.3340, -82.7661),
    "Suwannee River State Park": (30.3888, -83.1706),
    "Alafia River State Park": (27.8285, -82.1384),
    "Blue Spring State Park": (28.9482, -81.3392),
    "Gamble Rogers Memorial State Recreation Area": (29.4346, -81.1097),
    "Highlands Hammock State Park": (27.4705, -81.5315),
    "Hillsborough River State Park": (28.1465, -82.2268),
    "Kissimmee Prairie Preserve State Park": (27.5855, -81.0450),
    "Lake Kissimmee State Park": (27.9497, -81.3508),
    "Lake Louisa State Park": (28.4526, -81.7289),
    "Rainbow Springs State Park": (29.1026, -82.4385),
    "Silver Springs State Park": (29.2155, -82.0543),
    "Tomoka State Park": (29.3444, -81.0833),
    "Wekiwa Springs State Park": (28.7118, -81.4616),
    "Bahia Honda State Park": (24.6617, -81.2729),
    "Collier-Seminole State Park": (25.9922, -81.5878),
    "Curry Hammock State Park": (24.7431, -80.9822),
    "John Pennekamp Coral Reef State Park": (25.1256, -80.4083),
    "Jonathan Dickinson State Park": (27.0051, -80.1009),
    "Koreshan State Park": (26.4332, -81.8154),
    "Long Key State Park": (24.8143, -80.8229),
    "Myakka River State Park": (27.2396, -82.3168),
    "Oscar Scherer State Park": (27.1702, -82.4632),
    "Sebastian Inlet State Park": (27.8604, -80.4485),

    # ==========================================
    # 🍑 GEORGIA STATE PARKS
    # ==========================================
    "Vogel State Park (GA)": (34.7319, -83.9169),
    "Cloudland Canyon State Park (GA)": (34.8344, -85.4800),
    "Fort Mountain State Park (GA)": (34.7634, -84.7153),
    "Tallulah Gorge State Park (GA)": (34.7409, -83.3941),
    "Black Rock Mountain State Park (GA)": (34.9044, -83.4125),
    "James H. Floyd State Park (GA)": (34.4370, -85.3400),
    "Moccasin Creek State Park (GA)": (34.8458, -83.5872),
    "Red Top Mountain State Park (GA)": (34.1436, -84.7042),
    "Elijah Clark State Park (GA)": (33.8545, -82.4195),
    "High Falls State Park (GA)": (33.1811, -84.0158),
    "Mistletoe State Park (GA)": (33.6437, -82.3840),
    "Richard B. Russell State Park (GA)": (34.1780, -82.7613),
    "Tugaloo State Park (GA)": (34.6293, -83.2974),
    "Georgia Veterans State Park (GA)": (31.9563, -83.9161),
    "Fort Yargo State Park (GA)": (33.9835, -83.7347),
    "Seminole State Park (GA)": (30.8050, -84.8740),
    "Florence Marina State Park (GA)": (32.0908, -85.0433),
    "Skidaway Island State Park (GA)": (31.9547, -81.0526),
    "F.D. Roosevelt State Park (GA)": (32.8368, -84.8149),
    "Stephen C. Foster State Park (GA)": (30.8267, -82.3619),
    "Hard Labor Creek State Park (GA)": (33.6547, -83.5968),
    "Providence Canyon State Park (GA)": (32.0644, -84.9216),
    "Crooked River State Park (GA)": (30.8413, -81.5500),
    "Laura S. Walker State Park (GA)": (31.1396, -82.2033),
    "Indian Springs State Park (GA)": (33.2954, -83.9238),
    "Magnolia Springs State Park (GA)": (32.8866, -81.9555),
    "Watson Mill Bridge State Park (GA)": (34.0260, -83.0730),
    "A.H. Stephens State Park (GA)": (33.5633, -82.8966),
    "George L. Smith State Park (GA)": (32.5620, -82.1130),
    "Jack Hill State Park (GA)": (32.0921, -82.1360)
}


# --- 2b. FEDERAL CAMPGROUND DISCOVERY (RIDB API) ---
def get_federal_campgrounds_by_state(states, api_key):
    """
    Queries recreation.gov's own RIDB facility API to find every reservable
    campground in the given states, instead of relying on a hand-picked list.
    Returns a dict shaped like federal_watchlist: {name: {"id","lat","lon"}}
    """
    print("\n" + "=" * 50)
    print(f"🔎 DISCOVERING ALL FEDERAL CAMPGROUNDS IN {', '.join(states)}")
    print("=" * 50)

    if not api_key or api_key == "YOUR_RIDB_API_KEY_HERE":
        print("⚠️ No RIDB_API_KEY set — get a free one at https://ridb.recreation.gov/profile")
        print("⚠️ Falling back to the manual federal_watchlist instead.")
        return federal_watchlist

    campgrounds = {}
    headers = {"apikey": api_key, "User-Agent": "Mozilla/5.0"}
    limit = 50

    for state in states:
        offset = 0
        while True:
            params = {
                "state": state,
                "activity": 9,  # 9 = Camping
                "limit": limit,
                "offset": offset,
            }
            try:
                res = requests.get(
                    "https://ridb.recreation.gov/api/v1/facilities",
                    headers=headers, params=params, timeout=15
                )
                res.raise_for_status()
                data = res.json()
            except Exception as e:
                print(f"⚠️ RIDB lookup failed for {state}: {e}")
                break

            results = data.get("RECDATA", [])
            if not results:
                break

            for fac in results:
                if not fac.get("Reservable") or not fac.get("Enabled"):
                    continue
                if fac.get("FacilityTypeDescription") != "Campground":
                    continue
                name = (fac.get("FacilityName") or "").strip()
                fid = fac.get("FacilityID")
                if not name or not fid:
                    continue
                campgrounds[f"{name} ({state})"] = {
                    "id": str(fid),
                    "lat": fac.get("FacilityLatitude") or 0.0,
                    "lon": fac.get("FacilityLongitude") or 0.0,
                }

            total = data.get("METADATA", {}).get("RESULTS", {}).get("TOTAL_COUNT", 0)
            offset += limit
            print(f"   ...{state}: {min(offset, total)}/{total} facilities scanned")
            if offset >= total:
                break
            time.sleep(0.3)

    print(f"✅ Discovered {len(campgrounds)} reservable federal campgrounds across {', '.join(states)}")
    return campgrounds


# --- 3. THE FEDERAL ENGINE ---
def fetch_federal_data(campground_dict, start_date, nights, rig_length):
    print("\n" + "=" * 50)
    print(f"🇺🇸 SWEEPING FEDERAL NETWORK FOR {start_date}")
    print("=" * 50)
    base_date = datetime.strptime(start_date, "%Y-%m-%d")
    required_dates = [(base_date + timedelta(days=i)).strftime("%Y-%m-%dT00:00:00Z") for i in range(nights)]
    required_months = list(
        set([(base_date + timedelta(days=i)).strftime("%Y-%m-01T00:00:00.000Z") for i in range(nights)]))
    headers = {"User-Agent": "Mozilla/5.0"}
    records = []

    for name, data in campground_dict.items():
        print(f"🔍 Checking {name}...")
        p_id = data['id']
        lat, lon = data.get('lat', 0.0), data.get('lon', 0.0)
        all_sites_data = {}
        for req_month in required_months:
            url = f"https://www.recreation.gov/api/camps/availability/campground/{p_id}/month"
            try:
                res = requests.get(url, params={"start_date": req_month}, headers=headers)
                if res.status_code == 200:
                    month_data = res.json().get('campsites', {})
                    for site_id, site_info in month_data.items():
                        if site_id not in all_sites_data:
                            all_sites_data[site_id] = site_info
                        else:
                            all_sites_data[site_id]['availabilities'].update(site_info['availabilities'])
            except Exception:
                pass
            time.sleep(0.5)

        rv_spots_found = 0
        bad_words = ["GROUP", "TENT", "WALK", "PRIMITIVE", "EQUESTRIAN", "NONELECTRIC", "NON-ELECTRIC", "CABIN", "YURT",
                     "BOAT"]
        for site_id, site_info in all_sites_data.items():
            if all(site_info['availabilities'].get(d) == "Available" for d in required_dates):
                site_type = site_info.get('site_type', '').upper()
                site_length = site_info.get('max_vehicle_length', 0)
                if not any(bw in site_type for bw in bad_words) and (site_length >= rig_length or site_length == 0):
                    rv_spots_found += 1

        records.append({
            "Park Name": name, "Open RV Spots": rv_spots_found,
            "Lat": lat, "Lon": lon,
            "URL": f"https://www.recreation.gov/camping/campgrounds/{p_id}"
        })
    return pd.DataFrame(records)


# --- 4. THE FLORIDA STATE ENGINE ---
def fetch_florida_data(start_date, nights, rig_length):
    print("\n" + "=" * 50)
    print(f"🐊 SWEEPING FLORIDA STATE PARKS FOR {start_date}")
    print("=" * 50)

    def get_fl_date(date_str):
        d = datetime.strptime(date_str, "%Y-%m-%d")
        suffix = 'th' if 11 <= (d.day % 100) <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(d.day % 10, 'th')
        return d.strftime(f"%A, %B {d.day}{suffix},")

    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    arrival_str = get_fl_date(start_date)
    departure_str = get_fl_date((start_dt + timedelta(days=nights)).strftime("%Y-%m-%d"))
    records = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)  # Runs silently
        context = browser.new_context()
        page = context.new_page()
        try:
            page.goto("https://reserve.floridastateparks.org/Web/")
            search_box = page.get_by_role("combobox", name="Enter to search city or park")
            search_box.click()
            search_box.press_sequentially("Anastasia State Park", delay=80)
            option = page.get_by_role("option", name="park Anastasia State Park")
            option.wait_for(state="visible", timeout=15000)
            option.click()
            page.get_by_text("Select Arrival - End Date").click()
            time.sleep(1)
            page.get_by_role("button", name=f"Choose {arrival_str}").click()
            page.get_by_role("button", name=f"Choose {departure_str}").click()
            page.get_by_role("button", name="Select Site Type (optional)").click()
            page.get_by_role("option", name="Camping", exact=True).click()
            page.get_by_role("button", name="Select Camping Equipment (").click()
            page.get_by_role("option", name="Trailer", exact=True).click()
            page.get_by_role("button", name="Select Trailer Length (").click()
            page.get_by_role("option", name=f"> {rig_length} feet").click()
            page.get_by_role("button", name="Show Results").click()

            page.wait_for_selector("text=Available Sites", timeout=20000)
            time.sleep(2)
            lines = [line.strip() for line in page.inner_text("body").split('\n') if line.strip()]

            for i, line in enumerate(lines):
                if line == "Available Sites":
                    try:
                        spots = int(lines[i - 1])
                        park_name = lines[i + 1]
                        if spots > 0:
                            print(f"   ✅ FL Found {spots} spots at {park_name}")
                            lat, lon = STATE_PARK_GPS.get(park_name, (0.0, 0.0))
                            records.append({
                                "Park Name": park_name, "Open RV Spots": spots,
                                "Lat": lat, "Lon": lon, "URL": "https://reserve.floridastateparks.org/Web/"
                            })
                    except:
                        pass
        except Exception as e:
            print(f"⚠️ FL Scraper Error: {e}")
        finally:
            browser.close()
    return pd.DataFrame(records)


# --- 5. THE GEORGIA STATE ENGINE ---
def fetch_georgia_data(start_date, nights, rig_length):
    print("\n" + "=" * 50)
    print(f"🍑 SWEEPING GEORGIA STATE PARKS FOR {start_date}")
    print("=" * 50)
    formatted_date = datetime.strptime(start_date, "%Y-%m-%d").strftime("%m/%d/%Y")
    records = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, slow_mo=200)  # Runs silently
        context = browser.new_context()
        page = context.new_page()

        for raw_name, park_id in GA_PARKS_IDS.items():
            full_name = f"{raw_name} State Park (GA)"
            print(f"🔍 Checking {raw_name}...")
            try:
                url = f"https://gastateparks.reserveamerica.com/campgroundDetails.do?contractCode=GA&parkId={park_id}"
                page.goto(url, wait_until="domcontentloaded", timeout=30000)

                page.wait_for_selector("#unifSearchForm", state="attached", timeout=15000)
                page.click("#unifSearchForm")
                time.sleep(1)

                page.get_by_label("Looking for").select_option("2001")
                page.get_by_role("textbox", name="Length (ft)").fill(str(rig_length))
                page.get_by_role("checkbox", name="more options...").check()
                page.get_by_role("group", name="Specific Attributes Group").get_by_label(
                    "Electric hookup").select_option("3004")

                date_box = page.get_by_role("textbox", name="Arrival date")
                date_box.click()
                date_box.fill(formatted_date)
                date_box.press("Tab")
                page.locator("body").click()
                page.keyboard.press("Escape")

                time.sleep(1.5)
                page.get_by_role("spinbutton", name="Length of stay:").fill(str(nights))
                page.get_by_role("button", name="Search").click()

                page.wait_for_load_state("networkidle", timeout=15000)
                time.sleep(2)

                available_spots = page.content().count("Avail")
                if available_spots > 0:
                    print(f"   ✅ GA Found spots at {raw_name}")
                    lat, lon = STATE_PARK_GPS.get(full_name, (0.0, 0.0))
                    records.append({
                        "Park Name": full_name, "Open RV Spots": available_spots,
                        "Lat": lat, "Lon": lon, "URL": url
                    })
            except Exception:
                pass
            time.sleep(1)
        browser.close()
    return pd.DataFrame(records)


# --- 6. THE UNIFIED MAPPING ENGINE (Now With Reverse Geocoding) ---
def generate_map(df, start_date, nights, rig_length):
    print("\n🗺️ Generating Unified Master Map...")

    available_df = df[df['Open RV Spots'] > 0]

    if available_df.empty:
        print("⚠️ No spots found anywhere! The map will be empty.")
        avg_lat, avg_lon = 30.0, -83.0
    else:
        valid_coords = available_df[(available_df['Lat'] != 0.0) & (available_df['Lon'] != 0.0)]
        avg_lat = valid_coords['Lat'].mean() if not valid_coords.empty else 30.0
        avg_lon = valid_coords['Lon'].mean() if not valid_coords.empty else -83.0

    m = folium.Map(location=[avg_lat, avg_lon], zoom_start=6, control_scale=True)

    # --- INITIALIZE GEOLOCATOR HERE ---
    geolocator = Nominatim(user_agent="rv_radar_app")

    # --- 📡 RADAR PARAMETERS OVERLAY ---
    stats_html = f'''
    <div style="
        position: fixed; bottom: 30px; left: 10px; width: 220px; height: 110px; 
        background-color: white; border:2px solid grey; z-index:9999; font-size:14px;
        padding: 10px; border-radius: 10px; font-family: Arial;
        box-shadow: 3px 3px 5px rgba(0,0,0,0.3);
        ">
        <b>📡 Radar Parameters</b><br>
        📅 <b>Date:</b> {start_date}<br>
        🌙 <b>Nights:</b> {nights}<br>
        🚐 <b>Rig Min:</b> {rig_length} ft<br>
        ✅ <b>Found:</b> {len(available_df)} Parks
    </div>
    '''
    m.get_root().html.add_child(folium.Element(stats_html))

    for index, row in available_df.iterrows():
        spots = row['Open RV Spots']
        name = row['Park Name']
        url = row['URL']
        lat = row['Lat']
        lon = row['Lon']

        # --- THE REVERSE GEOCODING LOGIC ---
        display_address = "Address not available"
        if lat != 0.0 and lon != 0.0:
            print(f"   📍 Translating coordinates to address for {name}...")
            try:
                # We add a 1-second sleep to respect Nominatim's free usage policy
                time.sleep(1)
                location = geolocator.reverse((lat, lon), timeout=10)
                if location:
                    display_address = location.address
            except GeocoderTimedOut:
                display_address = "Address lookup timed out."
            except Exception as e:
                display_address = f"Address lookup failed."

        if "(GA)" in name:
            color = "orange"
        elif "State Park" in name:
            color = "blue"
        else:
            color = "green"

        status_text = f"<b style='color:{color};'>{spots} RV Spots Open!</b>"
        tmobile_link = "https://www.t-mobile.com/coverage/coverage-map"

        # The popup now proudly displays the physical address ready for T-Mobile
        popup_html = f"""
                <div style="width: 250px; font-family: Arial;">
                    <h4 style="margin-bottom:5px;">{name}</h4>
                    <p style="margin-top:0px; margin-bottom:5px;">{status_text}</p>

                    <p style="font-size: 13px; color: #333; margin-top:5px; margin-bottom: 5px;">
                        <b>Address:</b><br>{display_address}
                    </p>

                    <p style="font-size: 10px; color: #999; margin-top:0px; margin-bottom: 12px;"><b>GPS:</b> {lat}, {lon}</p>

                    <a href="{url}" target="_blank" style="display:block; text-align:center; background-color: #007BFF; color: white; padding: 8px 12px; text-decoration: none; border-radius: 5px; font-weight:bold; margin-bottom: 8px;">🏕️ Book Site</a>

                    <a href="{tmobile_link}" target="_blank" style="display:block; text-align:center; background-color: #E20074; color: white; padding: 8px 12px; text-decoration: none; border-radius: 5px; font-weight:bold;">📶 Check T-Mobile</a>
                </div>
                """

        if lat != 0.0 and lon != 0.0:
            folium.Marker(
                location=[lat, lon],
                popup=folium.Popup(popup_html, max_width=300),
                tooltip=f"{name}: {spots} spots",
                icon=folium.Icon(color=color, icon="car", prefix='fa')
            ).add_to(m)

    map_filename = "ultimate_radar.html"
    m.save(map_filename)
    webbrowser.open('file://' + os.path.realpath(map_filename))
    print("✅ Master Map launched successfully!")


# --- EXECUTION ---
if __name__ == "__main__":
    if SCAN_ALL_FEDERAL:
        active_federal_sites = get_federal_campgrounds_by_state(FEDERAL_STATES, RIDB_API_KEY)
    else:
        active_federal_sites = federal_watchlist

    df_fed = fetch_federal_data(active_federal_sites, START_DATE, NIGHTS, MIN_RV_LENGTH)

    df_fl = pd.DataFrame()
    df_ga = pd.DataFrame()

    if "FL" in FEDERAL_STATES:
        df_fl = fetch_florida_data(START_DATE, NIGHTS, MIN_RV_LENGTH)

    if "GA" in FEDERAL_STATES:
        df_ga = fetch_georgia_data(START_DATE, NIGHTS, MIN_RV_LENGTH)

    df_master = pd.concat([df_fed, df_fl, df_ga], ignore_index=True)

    generate_map(df_master, START_DATE, NIGHTS, MIN_RV_LENGTH)