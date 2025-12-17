from flask import Flask, request, render_template, session
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
import base64
from io import BytesIO
import requests

app = Flask(__name__)
app.secret_key = "change_this_secret_key"

# ---------- EXIF FUNCTIONS ----------
def get_exif(img):
    exif_data = img._getexif()
    if not exif_data:
        return None
    exif = {}
    for tag, value in exif_data.items():
        decoded = TAGS.get(tag, tag)
        exif[decoded] = value
    return exif

def get_gps_info(exif):
    if 'GPSInfo' not in exif:
        return None
    gps_info = {}
    for key in exif['GPSInfo'].keys():
        decode = GPSTAGS.get(key, key)
        gps_info[decode] = exif['GPSInfo'][key]
    return gps_info

def convert_to_degrees(value):
    d = float(value[0])
    m = float(value[1])
    s = float(value[2])
    return d + (m / 60.0) + (s / 3600.0)

def get_coordinates(gps_info):
    try:
        lat = convert_to_degrees(gps_info['GPSLatitude'])
        if gps_info['GPSLatitudeRef'] != 'N':
            lat = -lat
        lon = convert_to_degrees(gps_info['GPSLongitude'])
        if gps_info['GPSLongitudeRef'] != 'E':
            lon = -lon
        return lat, lon
    except Exception:
        return None, None

# ---------- REVERSE GEOCODING ----------
def get_address_info(lat, lon):
    try:
        url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}&zoom=18&addressdetails=1"
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        data = response.json()
        address = data.get('display_name', None)
        addr_details = data.get('address', {})

        return {
            "landmark": addr_details.get('attraction') or addr_details.get('tourism') or addr_details.get('building') or '',
            "building": addr_details.get('building', ''),
            "address": addr_details.get('road', '') + ' ' + addr_details.get('house_number', ''),
            "city": addr_details.get('city') or addr_details.get('town') or addr_details.get('village', ''),
            "country": addr_details.get('country', ''),
        }
    except:
        return {"landmark": "", "building": "", "address": "", "city": "", "country": ""}

# ---------- ROUTE ----------
@app.route('/', methods=['GET', 'POST'])
def index():
    lat = lon = error = source = None
    radius = None
    location_info = {"landmark": "", "building": "", "address": "", "city": "", "country": ""}

    if request.method == 'POST':
        img = None

        # 1️⃣ Image upload
        if 'image' in request.files and request.files['image'].filename != '':
            img = Image.open(request.files['image'])
        # 2️⃣ Camera capture
        elif request.form.get('camera_image'):
            data = request.form['camera_image'].split(',')[1]
            img = Image.open(BytesIO(base64.b64decode(data)))

        # 3️⃣ EXIF GPS first
        if img:
            exif = get_exif(img)
            if exif:
                gps_info = get_gps_info(exif)
                if gps_info:
                    lat, lon = get_coordinates(gps_info)
                    source = "exif_gps"
                    session['last_lat'] = lat
                    session['last_lon'] = lon
                    radius = 20  # meters

        # 4️⃣ Browser GPS fallback
        if lat is None and request.form.get('browser_lat') and request.form.get('browser_lon'):
            lat = float(request.form['browser_lat'])
            lon = float(request.form['browser_lon'])
            source = "browser_gps"
            session['last_lat'] = lat
            session['last_lon'] = lon
            radius = 20  # meters

        # 5️⃣ Last known location fallback
        if lat is None:
            if 'last_lat' in session and 'last_lon' in session:
                lat = session['last_lat']
                lon = session['last_lon']
                radius = 100  # meters
                source = "last_known_location"
            else:
                error = "Location not available"

        # 6️⃣ Get address info if coordinates are available
        if lat is not None and lon is no    t None:
            location_info = get_address_info(lat, lon)

    return render_template(
        'index.html', lat=lat, lon=lon, radius=radius, source=source, error=error,
        landmark=location_info['landmark'],
        building=location_info['building'],
        address=location_info['address'],
        city=location_info['city'],
        country=location_info['country']
    )

if __name__ == '__main__':
    app.run(debug=True)
