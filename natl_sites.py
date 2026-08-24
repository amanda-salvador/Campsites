import requests
import time
import pandas as pd
import folium
import webbrowser
import os
from datetime import datetime, timedelta

# ==========================================
# ⚙️ YOUR TRIP SETTINGS (Change these!)
# ==========================================
START_DATE = "2026-05-05"  # Format: YYYY-MM-DD
NIGHTS = 3  # Must be available for this many nights in a row
MIN_RV_LENGTH = 20  # Minimum driveway length required
# ==========================================

# --- 1. THE HYBRID WATCHLIST ---
# The "Golden Record" list of the best RV-friendly Federal parks in the SE.
# Because we provide 'lat' and 'lon', the script skips the slow GPS API checks.
watchlist = {
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


# --- 2. THE DYNAMIC GPS ENGINE ---
def get_park_coordinates(park_data):
    """Uses your Golden Record if available. If not, asks the API."""
    if 'lat' in park_data and 'lon' in park_data:
        return park_data['lat'], park_data['lon']

    park_id = park_data['id']
    url = f"https://www.recreation.gov/api/camps/campgrounds/{park_id}"
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        res = requests.get(url, headers=headers)
        if res.status_code == 200:
            data = res.json()
            lat = data.get('campground', {}).get('facility_latitude') or data.get('facility_latitude', 0.0)
            lon = data.get('campground', {}).get('facility_longitude') or data.get('facility_longitude', 0.0)
            return float(lat), float(lon)
    except Exception:
        pass
    return 0.0, 0.0


# --- 3. THE DATA ENGINE ---
def fetch_park_data(start_date, nights):
    print(f"📡 Sweeping Southeast VIP Network for a {nights}-night stay starting {start_date}...")
    print(f"📏 Rig Requirement: >{MIN_RV_LENGTH}ft\n")

    base_date = datetime.strptime(start_date, "%Y-%m-%d")
    required_dates = [(base_date + timedelta(days=i)).strftime("%Y-%m-%dT00:00:00Z") for i in range(nights)]
    required_months = list(
        set([(base_date + timedelta(days=i)).strftime("%Y-%m-01T00:00:00.000Z") for i in range(nights)]))

    headers = {"User-Agent": "Mozilla/5.0"}
    park_records = []

    for name, data in watchlist.items():
        print(f"🔍 Checking {name}...")
        p_id = data['id']

        # Get coordinates via Hybrid Engine
        lat, lon = get_park_coordinates(data)

        # Download availability data
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
            time.sleep(1)  # IP Protection

        # Filter the Results
        rv_spots_found = 0
        bad_words = ["GROUP", "TENT", "WALK", "PRIMITIVE", "EQUESTRIAN", "NONELECTRIC", "NON-ELECTRIC", "CABIN", "YURT",
                     "BOAT", "HIKE", "SHELTER"]

        for site_id, site_info in all_sites_data.items():
            is_available_entire_trip = all(site_info['availabilities'].get(d) == "Available" for d in required_dates)

            if is_available_entire_trip:
                site_type = site_info.get('site_type', '').upper()
                site_length = site_info.get('max_vehicle_length', 0)

                passes_denylist = not any(bw in site_type for bw in bad_words)
                fits_rig = (site_length >= MIN_RV_LENGTH or site_length == 0)

                if passes_denylist and fits_rig:
                    rv_spots_found += 1

        # Save to Master Record
        park_records.append({
            "Park Name": name,
            "Open RV Spots": rv_spots_found,
            "Lat": lat,
            "Lon": lon,
            "URL": f"https://www.recreation.gov/camping/campgrounds/{p_id}"
        })

    return pd.DataFrame(park_records)


# --- 4. THE MAPPING ENGINE ---
def generate_map(df, start_date, nights):
    print("\n🗺️ Generating Interactive Map...")

    # Dynamically center the map based on the parks we just scanned
    valid_coords = df[(df['Lat'] != 0.0) & (df['Lon'] != 0.0)]
    avg_lat = valid_coords['Lat'].mean() if not valid_coords.empty else 32.0
    avg_lon = valid_coords['Lon'].mean() if not valid_coords.empty else -83.0

    m = folium.Map(location=[avg_lat, avg_lon], zoom_start=6)

    for index, row in df.iterrows():
        spots = row['Open RV Spots']
        name = row['Park Name']
        url = row['URL']

        if spots > 0:
            color = "green"
            icon = "check"
            status_text = f"<b style='color:green;'>{spots} RV Spots Open!</b><br>Available for all {nights} nights."
        else:
            color = "red"
            icon = "times"
            status_text = f"Booked for requested dates."

        popup_html = f"""
        <div style="width: 220px; font-family: Arial;">
            <h4>{name}</h4>
            <p>{status_text}</p>
            <a href="{url}" target="_blank" style="background-color: #007BFF; color: white; padding: 5px 10px; text-decoration: none; border-radius: 3px;">Book Now</a>
        </div>
        """

        # Only plot the pin if we successfully grabbed the GPS coordinates
        if row['Lat'] != 0.0 and row['Lon'] != 0.0:
            folium.Marker(
                location=[row['Lat'], row['Lon']],
                popup=folium.Popup(popup_html, max_width=250),
                tooltip=name,
                icon=folium.Icon(color=color, icon=icon, prefix='fa')
            ).add_to(m)

    map_filename = "southeast_radar.html"
    m.save(map_filename)
    webbrowser.open('file://' + os.path.realpath(map_filename))
    print("✅ Map launched successfully!")


# --- EXECUTION ---
if __name__ == "__main__":
    df_results = fetch_park_data(START_DATE, NIGHTS)
    generate_map(df_results, START_DATE, NIGHTS)