"""
Birth-place gazetteer + DST-aware local-time → UTC conversion (v1.3).

Every place carries an IANA timezone, so historical daylight-saving rules are
applied by ``zoneinfo`` (e.g. a London birth on 1990-07-15 10:00 is BST,
UTC+1; the same clock time in January is GMT, UTC+0; India has used IST
+05:30 since 1955 but zoneinfo still knows the 1942-45 war-time offsets).

Coordinates are city-centre values (4 dp) — good to ~1-2 km, i.e. well under
the ~4 minutes of Lagna movement per degree of longitude.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# (name, region, country, lat, lon, iana_tz)
_RAW: List[Tuple[str, str, str, float, float, str]] = [
    # ── India: default native first, then every state / UT capital and major cities ──
    ("Vallabh Vidyanagar", "Gujarat", "India", 22.5347, 73.1300, "Asia/Kolkata"),
    ("Anand", "Gujarat", "India", 22.5645, 72.9289, "Asia/Kolkata"),
    ("Ahmedabad", "Gujarat", "India", 23.0225, 72.5714, "Asia/Kolkata"),
    ("Gandhinagar", "Gujarat", "India", 23.2156, 72.6369, "Asia/Kolkata"),
    ("Vadodara", "Gujarat", "India", 22.3072, 73.1812, "Asia/Kolkata"),
    ("Surat", "Gujarat", "India", 21.1702, 72.8311, "Asia/Kolkata"),
    ("Rajkot", "Gujarat", "India", 22.3039, 70.8022, "Asia/Kolkata"),
    ("Bhavnagar", "Gujarat", "India", 21.7645, 72.1519, "Asia/Kolkata"),
    ("Jamnagar", "Gujarat", "India", 22.4707, 70.0577, "Asia/Kolkata"),
    ("Nadiad", "Gujarat", "India", 22.6916, 72.8634, "Asia/Kolkata"),
    ("Bharuch", "Gujarat", "India", 21.7051, 72.9959, "Asia/Kolkata"),
    ("Junagadh", "Gujarat", "India", 21.5222, 70.4579, "Asia/Kolkata"),
    ("Mumbai", "Maharashtra", "India", 19.0760, 72.8777, "Asia/Kolkata"),
    ("Pune", "Maharashtra", "India", 18.5204, 73.8567, "Asia/Kolkata"),
    ("Nagpur", "Maharashtra", "India", 21.1458, 79.0882, "Asia/Kolkata"),
    ("Nashik", "Maharashtra", "India", 19.9975, 73.7898, "Asia/Kolkata"),
    ("Aurangabad", "Maharashtra", "India", 19.8762, 75.3433, "Asia/Kolkata"),
    ("Thane", "Maharashtra", "India", 19.2183, 72.9781, "Asia/Kolkata"),
    ("Kolhapur", "Maharashtra", "India", 16.7050, 74.2433, "Asia/Kolkata"),
    ("Solapur", "Maharashtra", "India", 17.6599, 75.9064, "Asia/Kolkata"),
    ("New Delhi", "Delhi", "India", 28.6139, 77.2090, "Asia/Kolkata"),
    ("Delhi", "Delhi", "India", 28.7041, 77.1025, "Asia/Kolkata"),
    ("Gurugram", "Haryana", "India", 28.4595, 77.0266, "Asia/Kolkata"),
    ("Faridabad", "Haryana", "India", 28.4089, 77.3178, "Asia/Kolkata"),
    ("Noida", "Uttar Pradesh", "India", 28.5355, 77.3910, "Asia/Kolkata"),
    ("Chandigarh", "Punjab/Haryana", "India", 30.7333, 76.7794, "Asia/Kolkata"),
    ("Ludhiana", "Punjab", "India", 30.9010, 75.8573, "Asia/Kolkata"),
    ("Amritsar", "Punjab", "India", 31.6340, 74.8723, "Asia/Kolkata"),
    ("Jalandhar", "Punjab", "India", 31.3260, 75.5762, "Asia/Kolkata"),
    ("Shimla", "Himachal Pradesh", "India", 31.1048, 77.1734, "Asia/Kolkata"),
    ("Dharamshala", "Himachal Pradesh", "India", 32.2190, 76.3234, "Asia/Kolkata"),
    ("Srinagar", "Jammu & Kashmir", "India", 34.0837, 74.7973, "Asia/Kolkata"),
    ("Jammu", "Jammu & Kashmir", "India", 32.7266, 74.8570, "Asia/Kolkata"),
    ("Leh", "Ladakh", "India", 34.1526, 77.5771, "Asia/Kolkata"),
    ("Dehradun", "Uttarakhand", "India", 30.3165, 78.0322, "Asia/Kolkata"),
    ("Haridwar", "Uttarakhand", "India", 29.9457, 78.1642, "Asia/Kolkata"),
    ("Lucknow", "Uttar Pradesh", "India", 26.8467, 80.9462, "Asia/Kolkata"),
    ("Kanpur", "Uttar Pradesh", "India", 26.4499, 80.3319, "Asia/Kolkata"),
    ("Varanasi", "Uttar Pradesh", "India", 25.3176, 82.9739, "Asia/Kolkata"),
    ("Agra", "Uttar Pradesh", "India", 27.1767, 78.0081, "Asia/Kolkata"),
    ("Prayagraj", "Uttar Pradesh", "India", 25.4358, 81.8463, "Asia/Kolkata"),
    ("Meerut", "Uttar Pradesh", "India", 28.9845, 77.7064, "Asia/Kolkata"),
    ("Ghaziabad", "Uttar Pradesh", "India", 28.6692, 77.4538, "Asia/Kolkata"),
    ("Mathura", "Uttar Pradesh", "India", 27.4924, 77.6737, "Asia/Kolkata"),
    ("Gorakhpur", "Uttar Pradesh", "India", 26.7606, 83.3732, "Asia/Kolkata"),
    ("Jaipur", "Rajasthan", "India", 26.9124, 75.7873, "Asia/Kolkata"),
    ("Jodhpur", "Rajasthan", "India", 26.2389, 73.0243, "Asia/Kolkata"),
    ("Udaipur", "Rajasthan", "India", 24.5854, 73.7125, "Asia/Kolkata"),
    ("Kota", "Rajasthan", "India", 25.2138, 75.8648, "Asia/Kolkata"),
    ("Ajmer", "Rajasthan", "India", 26.4499, 74.6399, "Asia/Kolkata"),
    ("Bikaner", "Rajasthan", "India", 28.0229, 73.3119, "Asia/Kolkata"),
    ("Bhopal", "Madhya Pradesh", "India", 23.2599, 77.4126, "Asia/Kolkata"),
    ("Indore", "Madhya Pradesh", "India", 22.7196, 75.8577, "Asia/Kolkata"),
    ("Ujjain", "Madhya Pradesh", "India", 23.1793, 75.7849, "Asia/Kolkata"),
    ("Gwalior", "Madhya Pradesh", "India", 26.2183, 78.1828, "Asia/Kolkata"),
    ("Jabalpur", "Madhya Pradesh", "India", 23.1815, 79.9864, "Asia/Kolkata"),
    ("Raipur", "Chhattisgarh", "India", 21.2514, 81.6296, "Asia/Kolkata"),
    ("Bilaspur", "Chhattisgarh", "India", 22.0797, 82.1409, "Asia/Kolkata"),
    ("Patna", "Bihar", "India", 25.5941, 85.1376, "Asia/Kolkata"),
    ("Gaya", "Bihar", "India", 24.7914, 85.0002, "Asia/Kolkata"),
    ("Ranchi", "Jharkhand", "India", 23.3441, 85.3096, "Asia/Kolkata"),
    ("Jamshedpur", "Jharkhand", "India", 22.8046, 86.2029, "Asia/Kolkata"),
    ("Dhanbad", "Jharkhand", "India", 23.7957, 86.4304, "Asia/Kolkata"),
    ("Kolkata", "West Bengal", "India", 22.5726, 88.3639, "Asia/Kolkata"),
    ("Howrah", "West Bengal", "India", 22.5958, 88.2636, "Asia/Kolkata"),
    ("Siliguri", "West Bengal", "India", 26.7271, 88.3953, "Asia/Kolkata"),
    ("Durgapur", "West Bengal", "India", 23.5204, 87.3119, "Asia/Kolkata"),
    ("Bhubaneswar", "Odisha", "India", 20.2961, 85.8245, "Asia/Kolkata"),
    ("Cuttack", "Odisha", "India", 20.4625, 85.8830, "Asia/Kolkata"),
    ("Puri", "Odisha", "India", 19.8135, 85.8312, "Asia/Kolkata"),
    ("Guwahati", "Assam", "India", 26.1445, 91.7362, "Asia/Kolkata"),
    ("Dispur", "Assam", "India", 26.1433, 91.7898, "Asia/Kolkata"),
    ("Shillong", "Meghalaya", "India", 25.5788, 91.8933, "Asia/Kolkata"),
    ("Imphal", "Manipur", "India", 24.8170, 93.9368, "Asia/Kolkata"),
    ("Aizawl", "Mizoram", "India", 23.7271, 92.7176, "Asia/Kolkata"),
    ("Agartala", "Tripura", "India", 23.8315, 91.2868, "Asia/Kolkata"),
    ("Kohima", "Nagaland", "India", 25.6751, 94.1086, "Asia/Kolkata"),
    ("Itanagar", "Arunachal Pradesh", "India", 27.0844, 93.6053, "Asia/Kolkata"),
    ("Gangtok", "Sikkim", "India", 27.3389, 88.6065, "Asia/Kolkata"),
    ("Hyderabad", "Telangana", "India", 17.3850, 78.4867, "Asia/Kolkata"),
    ("Warangal", "Telangana", "India", 17.9689, 79.5941, "Asia/Kolkata"),
    ("Amaravati", "Andhra Pradesh", "India", 16.5062, 80.6480, "Asia/Kolkata"),
    ("Visakhapatnam", "Andhra Pradesh", "India", 17.6868, 83.2185, "Asia/Kolkata"),
    ("Vijayawada", "Andhra Pradesh", "India", 16.5062, 80.6480, "Asia/Kolkata"),
    ("Tirupati", "Andhra Pradesh", "India", 13.6288, 79.4192, "Asia/Kolkata"),
    ("Guntur", "Andhra Pradesh", "India", 16.3067, 80.4365, "Asia/Kolkata"),
    ("Bengaluru", "Karnataka", "India", 12.9716, 77.5946, "Asia/Kolkata"),
    ("Mysuru", "Karnataka", "India", 12.2958, 76.6394, "Asia/Kolkata"),
    ("Mangaluru", "Karnataka", "India", 12.9141, 74.8560, "Asia/Kolkata"),
    ("Hubballi", "Karnataka", "India", 15.3647, 75.1240, "Asia/Kolkata"),
    ("Belagavi", "Karnataka", "India", 15.8497, 74.4977, "Asia/Kolkata"),
    ("Chennai", "Tamil Nadu", "India", 13.0827, 80.2707, "Asia/Kolkata"),
    ("Coimbatore", "Tamil Nadu", "India", 11.0168, 76.9558, "Asia/Kolkata"),
    ("Madurai", "Tamil Nadu", "India", 9.9252, 78.1198, "Asia/Kolkata"),
    ("Tiruchirappalli", "Tamil Nadu", "India", 10.7905, 78.7047, "Asia/Kolkata"),
    ("Salem", "Tamil Nadu", "India", 11.6643, 78.1460, "Asia/Kolkata"),
    ("Puducherry", "Puducherry", "India", 11.9416, 79.8083, "Asia/Kolkata"),
    ("Thiruvananthapuram", "Kerala", "India", 8.5241, 76.9366, "Asia/Kolkata"),
    ("Kochi", "Kerala", "India", 9.9312, 76.2673, "Asia/Kolkata"),
    ("Kozhikode", "Kerala", "India", 11.2588, 75.7804, "Asia/Kolkata"),
    ("Thrissur", "Kerala", "India", 10.5276, 76.2144, "Asia/Kolkata"),
    ("Panaji", "Goa", "India", 15.4909, 73.8278, "Asia/Kolkata"),
    ("Margao", "Goa", "India", 15.2832, 73.9862, "Asia/Kolkata"),
    ("Port Blair", "Andaman & Nicobar", "India", 11.6234, 92.7265, "Asia/Kolkata"),
    ("Kavaratti", "Lakshadweep", "India", 10.5593, 72.6358, "Asia/Kolkata"),
    ("Silvassa", "Dadra & Nagar Haveli and Daman & Diu", "India", 20.2766, 73.0083, "Asia/Kolkata"),
    # ── South Asia neighbours ──
    ("Kathmandu", "", "Nepal", 27.7172, 85.3240, "Asia/Kathmandu"),
    ("Dhaka", "", "Bangladesh", 23.8103, 90.4125, "Asia/Dhaka"),
    ("Chittagong", "", "Bangladesh", 22.3569, 91.7832, "Asia/Dhaka"),
    ("Colombo", "", "Sri Lanka", 6.9271, 79.8612, "Asia/Colombo"),
    ("Karachi", "", "Pakistan", 24.8607, 67.0011, "Asia/Karachi"),
    ("Lahore", "", "Pakistan", 31.5204, 74.3587, "Asia/Karachi"),
    ("Islamabad", "", "Pakistan", 33.6844, 73.0479, "Asia/Karachi"),
    ("Thimphu", "", "Bhutan", 27.4728, 89.6390, "Asia/Thimphu"),
    ("Male", "", "Maldives", 4.1755, 73.5093, "Indian/Maldives"),
    # ── United Kingdom & Ireland ──
    ("London", "England", "United Kingdom", 51.5074, -0.1278, "Europe/London"),
    ("Manchester", "England", "United Kingdom", 53.4808, -2.2426, "Europe/London"),
    ("Birmingham", "England", "United Kingdom", 52.4862, -1.8904, "Europe/London"),
    ("Leicester", "England", "United Kingdom", 52.6369, -1.1398, "Europe/London"),
    ("Leeds", "England", "United Kingdom", 53.8008, -1.5491, "Europe/London"),
    ("Liverpool", "England", "United Kingdom", 53.4084, -2.9916, "Europe/London"),
    ("Bristol", "England", "United Kingdom", 51.4545, -2.5879, "Europe/London"),
    ("Sheffield", "England", "United Kingdom", 53.3811, -1.4701, "Europe/London"),
    ("Newcastle upon Tyne", "England", "United Kingdom", 54.9783, -1.6178, "Europe/London"),
    ("Nottingham", "England", "United Kingdom", 52.9548, -1.1581, "Europe/London"),
    ("Coventry", "England", "United Kingdom", 52.4068, -1.5197, "Europe/London"),
    ("Bradford", "England", "United Kingdom", 53.7960, -1.7594, "Europe/London"),
    ("Southampton", "England", "United Kingdom", 50.9097, -1.4044, "Europe/London"),
    ("Oxford", "England", "United Kingdom", 51.7520, -1.2577, "Europe/London"),
    ("Cambridge", "England", "United Kingdom", 52.2053, 0.1218, "Europe/London"),
    ("Reading", "England", "United Kingdom", 51.4543, -0.9781, "Europe/London"),
    ("Milton Keynes", "England", "United Kingdom", 52.0406, -0.7594, "Europe/London"),
    ("Brighton", "England", "United Kingdom", 50.8225, -0.1372, "Europe/London"),
    ("Slough", "England", "United Kingdom", 51.5105, -0.5950, "Europe/London"),
    ("Wembley", "England", "United Kingdom", 51.5588, -0.2817, "Europe/London"),
    ("Harrow", "England", "United Kingdom", 51.5806, -0.3420, "Europe/London"),
    ("Croydon", "England", "United Kingdom", 51.3762, -0.0982, "Europe/London"),
    ("Edinburgh", "Scotland", "United Kingdom", 55.9533, -3.1883, "Europe/London"),
    ("Glasgow", "Scotland", "United Kingdom", 55.8642, -4.2518, "Europe/London"),
    ("Aberdeen", "Scotland", "United Kingdom", 57.1497, -2.0943, "Europe/London"),
    ("Cardiff", "Wales", "United Kingdom", 51.4816, -3.1791, "Europe/London"),
    ("Swansea", "Wales", "United Kingdom", 51.6214, -3.9436, "Europe/London"),
    ("Belfast", "Northern Ireland", "United Kingdom", 54.5973, -5.9301, "Europe/London"),
    ("Dublin", "", "Ireland", 53.3498, -6.2603, "Europe/Dublin"),
    ("Cork", "", "Ireland", 51.8985, -8.4756, "Europe/Dublin"),
    # ── United States ──
    ("New York", "NY", "USA", 40.7128, -74.0060, "America/New_York"),
    ("Jersey City", "NJ", "USA", 40.7178, -74.0431, "America/New_York"),
    ("Edison", "NJ", "USA", 40.5187, -74.4121, "America/New_York"),
    ("Boston", "MA", "USA", 42.3601, -71.0589, "America/New_York"),
    ("Philadelphia", "PA", "USA", 39.9526, -75.1652, "America/New_York"),
    ("Pittsburgh", "PA", "USA", 40.4406, -79.9959, "America/New_York"),
    ("Washington", "DC", "USA", 38.9072, -77.0369, "America/New_York"),
    ("Baltimore", "MD", "USA", 39.2904, -76.6122, "America/New_York"),
    ("Atlanta", "GA", "USA", 33.7490, -84.3880, "America/New_York"),
    ("Miami", "FL", "USA", 25.7617, -80.1918, "America/New_York"),
    ("Orlando", "FL", "USA", 28.5383, -81.3792, "America/New_York"),
    ("Tampa", "FL", "USA", 27.9506, -82.4572, "America/New_York"),
    ("Charlotte", "NC", "USA", 35.2271, -80.8431, "America/New_York"),
    ("Raleigh", "NC", "USA", 35.7796, -78.6382, "America/New_York"),
    ("Detroit", "MI", "USA", 42.3314, -83.0458, "America/Detroit"),
    ("Columbus", "OH", "USA", 39.9612, -82.9988, "America/New_York"),
    ("Cleveland", "OH", "USA", 41.4993, -81.6944, "America/New_York"),
    ("Indianapolis", "IN", "USA", 39.7684, -86.1581, "America/Indiana/Indianapolis"),
    ("Chicago", "IL", "USA", 41.8781, -87.6298, "America/Chicago"),
    ("Houston", "TX", "USA", 29.7604, -95.3698, "America/Chicago"),
    ("Dallas", "TX", "USA", 32.7767, -96.7970, "America/Chicago"),
    ("Austin", "TX", "USA", 30.2672, -97.7431, "America/Chicago"),
    ("San Antonio", "TX", "USA", 29.4241, -98.4936, "America/Chicago"),
    ("Minneapolis", "MN", "USA", 44.9778, -93.2650, "America/Chicago"),
    ("St. Louis", "MO", "USA", 38.6270, -90.1994, "America/Chicago"),
    ("Kansas City", "MO", "USA", 39.0997, -94.5786, "America/Chicago"),
    ("Nashville", "TN", "USA", 36.1627, -86.7816, "America/Chicago"),
    ("New Orleans", "LA", "USA", 29.9511, -90.0715, "America/Chicago"),
    ("Milwaukee", "WI", "USA", 43.0389, -87.9065, "America/Chicago"),
    ("Denver", "CO", "USA", 39.7392, -104.9903, "America/Denver"),
    ("Salt Lake City", "UT", "USA", 40.7608, -111.8910, "America/Denver"),
    ("Phoenix", "AZ", "USA", 33.4484, -112.0740, "America/Phoenix"),
    ("Las Vegas", "NV", "USA", 36.1699, -115.1398, "America/Los_Angeles"),
    ("Los Angeles", "CA", "USA", 34.0522, -118.2437, "America/Los_Angeles"),
    ("San Francisco", "CA", "USA", 37.7749, -122.4194, "America/Los_Angeles"),
    ("San Jose", "CA", "USA", 37.3382, -121.8863, "America/Los_Angeles"),
    ("Fremont", "CA", "USA", 37.5485, -121.9886, "America/Los_Angeles"),
    ("San Diego", "CA", "USA", 32.7157, -117.1611, "America/Los_Angeles"),
    ("Sacramento", "CA", "USA", 38.5816, -121.4944, "America/Los_Angeles"),
    ("Seattle", "WA", "USA", 47.6062, -122.3321, "America/Los_Angeles"),
    ("Portland", "OR", "USA", 45.5152, -122.6784, "America/Los_Angeles"),
    ("Anchorage", "AK", "USA", 61.2181, -149.9003, "America/Anchorage"),
    ("Honolulu", "HI", "USA", 21.3069, -157.8583, "Pacific/Honolulu"),
    # ── Canada ──
    ("Toronto", "ON", "Canada", 43.6532, -79.3832, "America/Toronto"),
    ("Brampton", "ON", "Canada", 43.7315, -79.7624, "America/Toronto"),
    ("Mississauga", "ON", "Canada", 43.5890, -79.6441, "America/Toronto"),
    ("Ottawa", "ON", "Canada", 45.4215, -75.6972, "America/Toronto"),
    ("Montreal", "QC", "Canada", 45.5017, -73.5673, "America/Toronto"),
    ("Quebec City", "QC", "Canada", 46.8139, -71.2080, "America/Toronto"),
    ("Winnipeg", "MB", "Canada", 49.8951, -97.1384, "America/Winnipeg"),
    ("Calgary", "AB", "Canada", 51.0447, -114.0719, "America/Edmonton"),
    ("Edmonton", "AB", "Canada", 53.5461, -113.4938, "America/Edmonton"),
    ("Vancouver", "BC", "Canada", 49.2827, -123.1207, "America/Vancouver"),
    ("Surrey", "BC", "Canada", 49.1913, -122.8490, "America/Vancouver"),
    ("Halifax", "NS", "Canada", 44.6488, -63.5752, "America/Halifax"),
    # ── Australia & NZ ──
    ("Sydney", "NSW", "Australia", -33.8688, 151.2093, "Australia/Sydney"),
    ("Melbourne", "VIC", "Australia", -37.8136, 144.9631, "Australia/Melbourne"),
    ("Brisbane", "QLD", "Australia", -27.4698, 153.0251, "Australia/Brisbane"),
    ("Perth", "WA", "Australia", -31.9505, 115.8605, "Australia/Perth"),
    ("Adelaide", "SA", "Australia", -34.9285, 138.6007, "Australia/Adelaide"),
    ("Canberra", "ACT", "Australia", -35.2809, 149.1300, "Australia/Sydney"),
    ("Hobart", "TAS", "Australia", -42.8821, 147.3272, "Australia/Hobart"),
    ("Darwin", "NT", "Australia", -12.4634, 130.8456, "Australia/Darwin"),
    ("Auckland", "", "New Zealand", -36.8485, 174.7633, "Pacific/Auckland"),
    ("Wellington", "", "New Zealand", -41.2866, 174.7756, "Pacific/Auckland"),
    # ── Gulf & Middle East ──
    ("Dubai", "", "UAE", 25.2048, 55.2708, "Asia/Dubai"),
    ("Abu Dhabi", "", "UAE", 24.4539, 54.3773, "Asia/Dubai"),
    ("Sharjah", "", "UAE", 25.3463, 55.4209, "Asia/Dubai"),
    ("Doha", "", "Qatar", 25.2854, 51.5310, "Asia/Qatar"),
    ("Muscat", "", "Oman", 23.5880, 58.3829, "Asia/Muscat"),
    ("Kuwait City", "", "Kuwait", 29.3759, 47.9774, "Asia/Kuwait"),
    ("Manama", "", "Bahrain", 26.2285, 50.5860, "Asia/Bahrain"),
    ("Riyadh", "", "Saudi Arabia", 24.7136, 46.6753, "Asia/Riyadh"),
    ("Jeddah", "", "Saudi Arabia", 21.4858, 39.1925, "Asia/Riyadh"),
    ("Tehran", "", "Iran", 35.6892, 51.3890, "Asia/Tehran"),
    ("Tel Aviv", "", "Israel", 32.0853, 34.7818, "Asia/Jerusalem"),
    ("Istanbul", "", "Turkey", 41.0082, 28.9784, "Europe/Istanbul"),
    ("Cairo", "", "Egypt", 30.0444, 31.2357, "Africa/Cairo"),
    # ── Europe ──
    ("Paris", "", "France", 48.8566, 2.3522, "Europe/Paris"),
    ("Lyon", "", "France", 45.7640, 4.8357, "Europe/Paris"),
    ("Frankfurt", "", "Germany", 50.1109, 8.6821, "Europe/Berlin"),
    ("Berlin", "", "Germany", 52.5200, 13.4050, "Europe/Berlin"),
    ("Munich", "", "Germany", 48.1351, 11.5820, "Europe/Berlin"),
    ("Hamburg", "", "Germany", 53.5511, 9.9937, "Europe/Berlin"),
    ("Amsterdam", "", "Netherlands", 52.3676, 4.9041, "Europe/Amsterdam"),
    ("Rotterdam", "", "Netherlands", 51.9244, 4.4777, "Europe/Amsterdam"),
    ("Brussels", "", "Belgium", 50.8503, 4.3517, "Europe/Brussels"),
    ("Luxembourg", "", "Luxembourg", 49.6116, 6.1319, "Europe/Luxembourg"),
    ("Zurich", "", "Switzerland", 47.3769, 8.5417, "Europe/Zurich"),
    ("Geneva", "", "Switzerland", 46.2044, 6.1432, "Europe/Zurich"),
    ("Vienna", "", "Austria", 48.2082, 16.3738, "Europe/Vienna"),
    ("Milan", "", "Italy", 45.4642, 9.1900, "Europe/Rome"),
    ("Rome", "", "Italy", 41.9028, 12.4964, "Europe/Rome"),
    ("Madrid", "", "Spain", 40.4168, -3.7038, "Europe/Madrid"),
    ("Barcelona", "", "Spain", 41.3851, 2.1734, "Europe/Madrid"),
    ("Lisbon", "", "Portugal", 38.7223, -9.1393, "Europe/Lisbon"),
    ("Stockholm", "", "Sweden", 59.3293, 18.0686, "Europe/Stockholm"),
    ("Oslo", "", "Norway", 59.9139, 10.7522, "Europe/Oslo"),
    ("Copenhagen", "", "Denmark", 55.6761, 12.5683, "Europe/Copenhagen"),
    ("Helsinki", "", "Finland", 60.1699, 24.9384, "Europe/Helsinki"),
    ("Warsaw", "", "Poland", 52.2297, 21.0122, "Europe/Warsaw"),
    ("Prague", "", "Czechia", 50.0755, 14.4378, "Europe/Prague"),
    ("Budapest", "", "Hungary", 47.4979, 19.0402, "Europe/Budapest"),
    ("Athens", "", "Greece", 37.9838, 23.7275, "Europe/Athens"),
    ("Bucharest", "", "Romania", 44.4268, 26.1025, "Europe/Bucharest"),
    ("Moscow", "", "Russia", 55.7558, 37.6173, "Europe/Moscow"),
    ("Kyiv", "", "Ukraine", 50.4501, 30.5234, "Europe/Kyiv"),
    # ── East & South-East Asia ──
    ("Singapore", "", "Singapore", 1.3521, 103.8198, "Asia/Singapore"),
    ("Kuala Lumpur", "", "Malaysia", 3.1390, 101.6869, "Asia/Kuala_Lumpur"),
    ("Bangkok", "", "Thailand", 13.7563, 100.5018, "Asia/Bangkok"),
    ("Jakarta", "", "Indonesia", -6.2088, 106.8456, "Asia/Jakarta"),
    ("Bali (Denpasar)", "", "Indonesia", -8.6705, 115.2126, "Asia/Makassar"),
    ("Manila", "", "Philippines", 14.5995, 120.9842, "Asia/Manila"),
    ("Ho Chi Minh City", "", "Vietnam", 10.8231, 106.6297, "Asia/Ho_Chi_Minh"),
    ("Hanoi", "", "Vietnam", 21.0278, 105.8342, "Asia/Bangkok"),
    ("Hong Kong", "", "Hong Kong", 22.3193, 114.1694, "Asia/Hong_Kong"),
    ("Shanghai", "", "China", 31.2304, 121.4737, "Asia/Shanghai"),
    ("Beijing", "", "China", 39.9042, 116.4074, "Asia/Shanghai"),
    ("Shenzhen", "", "China", 22.5431, 114.0579, "Asia/Shanghai"),
    ("Taipei", "", "Taiwan", 25.0330, 121.5654, "Asia/Taipei"),
    ("Seoul", "", "South Korea", 37.5665, 126.9780, "Asia/Seoul"),
    ("Tokyo", "", "Japan", 35.6762, 139.6503, "Asia/Tokyo"),
    ("Osaka", "", "Japan", 34.6937, 135.5023, "Asia/Tokyo"),
    # ── Africa & Latin America ──
    ("Johannesburg", "", "South Africa", -26.2041, 28.0473, "Africa/Johannesburg"),
    ("Cape Town", "", "South Africa", -33.9249, 18.4241, "Africa/Johannesburg"),
    ("Durban", "", "South Africa", -29.8587, 31.0218, "Africa/Johannesburg"),
    ("Nairobi", "", "Kenya", -1.2921, 36.8219, "Africa/Nairobi"),
    ("Mombasa", "", "Kenya", -4.0435, 39.6682, "Africa/Nairobi"),
    ("Kampala", "", "Uganda", 0.3476, 32.5825, "Africa/Kampala"),
    ("Dar es Salaam", "", "Tanzania", -6.7924, 39.2083, "Africa/Dar_es_Salaam"),
    ("Lagos", "", "Nigeria", 6.5244, 3.3792, "Africa/Lagos"),
    ("Accra", "", "Ghana", 5.6037, -0.1870, "Africa/Accra"),
    ("Port Louis", "", "Mauritius", -20.1609, 57.5012, "Indian/Mauritius"),
    ("Sao Paulo", "", "Brazil", -23.5505, -46.6333, "America/Sao_Paulo"),
    ("Rio de Janeiro", "", "Brazil", -22.9068, -43.1729, "America/Sao_Paulo"),
    ("Mexico City", "", "Mexico", 19.4326, -99.1332, "America/Mexico_City"),
    ("Buenos Aires", "", "Argentina", -34.6037, -58.3816, "America/Argentina/Buenos_Aires"),
    ("Lima", "", "Peru", -12.0464, -77.0428, "America/Lima"),
    ("Bogota", "", "Colombia", 4.7110, -74.0721, "America/Bogota"),
    ("Port of Spain", "", "Trinidad & Tobago", 10.6549, -61.5019, "America/Port_of_Spain"),
    ("Georgetown", "", "Guyana", 6.8013, -58.1551, "America/Guyana"),
    ("Suva", "", "Fiji", -18.1416, 178.4419, "Pacific/Fiji"),
]


def _label(name: str, region: str, country: str) -> str:
    if country in ("Singapore", "Hong Kong", "Luxembourg") and name == country:
        return name
    return ", ".join(x for x in (name, region, country) if x)


PLACES: List[Dict] = [
    {"name": _label(n, r, c), "city": n, "region": r, "country": c,
     "lat": lat, "lon": lon, "tz_name": tz}
    for (n, r, c, lat, lon, tz) in _RAW
]
DEFAULT_PLACE = PLACES[0]
UJJAIN = next(p for p in PLACES if p["city"] == "Ujjain")

# legacy labels kept resolvable (old localStorage / bookmarks)
_ALIASES = {
    "vallabh vidyanagar, gujarat, india": DEFAULT_PLACE,
    "delhi, india": next(p for p in PLACES if p["city"] == "New Delhi"),
}


def tz_offset_hours(tz_name: str, when_local: datetime) -> float:
    """UTC offset (hours, DST-aware) of ``tz_name`` at the given local wall time."""
    z = ZoneInfo(tz_name)
    off = when_local.replace(tzinfo=z).utcoffset()
    return off.total_seconds() / 3600.0 if off is not None else 0.0


def local_to_utc(date: str, time: str, tz_name: Optional[str] = None,
                 tz_offset: Optional[float] = None) -> Tuple[datetime, float, bool, str]:
    """Convert a birth's local wall-clock time to naive UTC.

    Priority: explicit numeric ``tz_offset`` (manual override, no DST logic)
    > IANA ``tz_name`` (historical DST applied) > IST.
    Returns (utc_naive, offset_hours_used, dst_active, tz_label).
    """
    y, m, d = (int(x) for x in date.split("-"))
    parts = [int(x) for x in time.split(":")]
    hh, mm = parts[0], parts[1] if len(parts) > 1 else 0
    ss = parts[2] if len(parts) > 2 else 0
    local = datetime(y, m, d, hh, mm, ss)
    if tz_offset is not None:
        return local - timedelta(hours=float(tz_offset)), float(tz_offset), False, f"UTC{float(tz_offset):+.2f} (manual)"
    name = tz_name or "Asia/Kolkata"
    try:
        z = ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        z, name = ZoneInfo("Asia/Kolkata"), "Asia/Kolkata"
    aware = local.replace(tzinfo=z)  # fold=0 → first occurrence for ambiguous times
    off = aware.utcoffset() or timedelta(0)
    dst = bool(aware.dst())
    utc = aware.astimezone(timezone.utc).replace(tzinfo=None)
    return utc, off.total_seconds() / 3600.0, dst, name


def search_places(q: str, limit: int = 12) -> List[Dict]:
    ql = (q or "").strip().lower()
    if not ql:
        return [_public(p) for p in PLACES[:limit]]
    city_starts = [p for p in PLACES if p["city"].lower().startswith(ql)]
    name_starts = [p for p in PLACES if p["name"].lower().startswith(ql) and p not in city_starts]
    contains = [p for p in PLACES if ql in p["name"].lower() and p not in city_starts and p not in name_starts]
    return [_public(p) for p in (city_starts + name_starts + contains)[:limit]]


def resolve_place(place: str) -> Optional[Dict]:
    pl = (place or "").strip().lower()
    if not pl:
        return None
    if pl in _ALIASES:
        return dict(_ALIASES[pl])
    for p in PLACES:
        if p["name"].lower() == pl:
            return dict(p)
    for p in PLACES:  # "London" → London, England, United Kingdom
        if p["city"].lower() == pl or pl.startswith(p["city"].lower() + ","):
            return dict(p)
    hits = search_places(place, 1)
    return dict(next(p for p in PLACES if p["name"] == hits[0]["name"])) if hits else None


def _public(p: Dict) -> Dict:
    """Shape returned to the UI (tz = current standard/DST offset for display only)."""
    try:
        now_off = tz_offset_hours(p["tz_name"], datetime.utcnow())
    except Exception:
        now_off = 0.0
    return {"name": p["name"], "lat": p["lat"], "lon": p["lon"], "tz_name": p["tz_name"],
            "tz": round(now_off, 2), "country": p["country"]}
