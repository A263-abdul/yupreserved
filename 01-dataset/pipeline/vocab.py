"""
Controlled vocabularies used to clean the raw Goibibo listings.

Everything that turns a messy free-text value into a clean, consistent value
lives here, so the cleaning rules can be read (and defended in the viva) in
one place.
"""
import re

# ── States ─────────────────────────────────────────────────────────────────
# Raw state spellings  ->  state_code in reference/states.csv
STATE_ALIASES = {
    "andaman and nicobar islands": "AN", "andhra pradesh": "AP",
    "arunachal pradesh": "AR", "assam": "AS", "bihar": "BR",
    "chandigarh": "CH", "chhattisgarh": "CG",
    "dadra and nagar haveli": "DH", "daman and diu": "DH",
    "delhi": "DL", "goa": "GA", "gujarat": "GJ", "haryana": "HR",
    "himachal pradesh": "HP", "jammu and kashmir": "JK", "jharkhand": "JH",
    "karnataka": "KA", "kerala": "KL", "ladakh": "LA",
    "madhya pradesh": "MP", "maharashtra": "MH", "manipur": "MN",
    "meghalaya": "ML", "mizoram": "MZ", "nagaland": "NL",
    "orissa": "OD", "odisha": "OD", "pondicherry": "PY", "puducherry": "PY",
    "punjab": "PB", "rajasthan": "RJ", "sikkim": "SK", "tamil nadu": "TN",
    "telangana": "TG", "tripura": "TR", "uttar pradesh": "UP",
    "uttarakhand": "UK", "west bengal": "WB",
}

# The crawl is from 2016: Telangana (2014) was still often filed under Andhra
# Pradesh, Ladakh became a UT in 2019 and Chandigarh is its own UT.
CITY_STATE_OVERRIDES = {
    "Hyderabad": "TG", "Secunderabad": "TG", "Warangal": "TG",
    "Karimnagar": "TG", "Nizamabad": "TG", "Khammam": "TG",
    "Leh": "LA", "Kargil": "LA", "Chandigarh": "CH",
}

CITY_RENAMES = {
    "Cochin": "Kochi", "Ernakulam": "Kochi", "NOIDA": "Noida",
    "Allepey": "Alleppey", "Alappuzha": "Alleppey",
}

METRO_CITIES = {"Mumbai", "Delhi", "Bangalore", "Chennai", "Kolkata",
                "Hyderabad", "Pune", "Ahmedabad"}
TIER2_CITIES = {"Jaipur", "Lucknow", "Kochi", "Chandigarh", "Indore",
                "Bhopal", "Nagpur", "Surat", "Coimbatore", "Mysore",
                "Vishakhapatnam", "Gurgaon", "Noida", "Udaipur", "Agra",
                "Varanasi", "Amritsar", "Goa", "Jodhpur", "Dehradun",
                "Guwahati", "Bhubaneswar", "Madurai", "Mangalore",
                "Thiruvananthapuram", "Vadodara", "Raipur", "Ranchi"}

# ── Property types ─────────────────────────────────────────────────────────
PROPERTY_TYPES = [
    "Hotel", "Resort", "Guest House", "Homestay", "Service Apartment",
    "Lodge", "Houseboat", "Cottage", "Tent", "Villa", "BnB", "Bungalow",
    "Palace", "Hostel", "Motel", "Farm Stay", "Luxury Yacht", "Beach Hut",
    "Heritage Hotel", "Haveli", "Boutique Hotel",
]

# ── Brand filter ───────────────────────────────────────────────────────────
# YupReserved is an independent platform, so listings that belong to large
# hotel chains are excluded (rule C3 in 01-dataset/README.md).
CHAIN_PATTERN = re.compile(
    r"\b(?:taj|vivanta|ginger|oberoi|trident|itc|welcom|marriott|courtyard|"
    r"hyatt|leela|hilton|radisson|novotel|ibis|lemon tree|westin|sheraton|"
    r"holiday inn|crowne|jw|ritz|four seasons|sarovar|fortune|oyo|treebo|"
    r"fab ?hotels?|zostel|club mahindra|clarks|park plaza|the park|keys|"
    r"ramada|mercure|pullman|renaissance|regis|meridien|four points|aloft|"
    r"lalit|shangri|movenpick|wyndham|best western|regenta|royal orchid|"
    r"country inn|days inn|howard johnson|svenska|accor)\b", re.I)

# ── Amenities ──────────────────────────────────────────────────────────────
# canonical name -> (category, regex matched against each raw facility label)
AMENITY_RULES = [
    ("Free Wi-Fi",         "ESSENTIALS", r"internet access free|free internet|wi-?fi|wireless"),
    ("Air Conditioning",   "ESSENTIALS", r"air[- ]?condition|\bac\b"),
    ("Power Backup",       "ESSENTIALS", r"power back"),
    ("Parking",            "ESSENTIALS", r"parking"),
    ("Lift",               "ESSENTIALS", r"lift|elevator"),
    ("Hot Water",          "ESSENTIALS", r"hot ?/? ?cold|hot water|geyser"),
    ("Heating",            "ESSENTIALS", r"heater|heating"),
    ("Room Service 24x7",  "ESSENTIALS", r"room service"),
    ("Housekeeping",       "ESSENTIALS", r"housekeeping|daily room cleaning"),
    ("Front Desk 24x7",    "ESSENTIALS", r"front desk|reception"),
    ("Restaurant",         "DINING",     r"restaurant|food facility|dining"),
    ("Fine Dining",        "DINING",     r"fine dining|specialty restaurant"),
    ("Cafe",               "DINING",     r"coffee shop|cafe"),
    ("Bar / Lounge",       "DINING",     r"\bbar\b|lounge|pub"),
    ("Breakfast Included", "DINING",     r"breakfast"),
    ("Meals Included",     "DINING",     r"all meals|meals included"),
    ("Vegetarian / Jain Food", "DINING", r"vegetarian|jain"),
    ("Swimming Pool",      "WELLNESS",   r"swimming|pool"),
    ("Spa",                "WELLNESS",   r"\bspa\b|massage|ayurved"),
    ("Fitness Centre",     "WELLNESS",   r"gym|fitness|health club"),
    ("Yoga",               "WELLNESS",   r"yoga|meditation"),
    ("Business Centre",    "BUSINESS",   r"business cent"),
    ("Conference Hall",    "BUSINESS",   r"conference|meeting"),
    ("Banquet Hall",       "BUSINESS",   r"banquet|party hall"),
    ("Family Rooms",       "FAMILY",     r"family room|suitable for children|extra person"),
    ("Kids Play Area",     "FAMILY",     r"play area|kids|children'?s? (park|play)"),
    ("Pet Friendly",       "FAMILY",     r"pets? (allowed|friendly)"),
    ("Airport Transfer",   "TRANSPORT",  r"airport"),
    ("Travel Desk",        "TRANSPORT",  r"travel desk|tour|sightseeing|air ?/ ?rail"),
    ("Car Rental",         "TRANSPORT",  r"car rental|taxi|cab"),
    ("Bicycle Rental",     "TRANSPORT",  r"bicycle|cycle"),
    ("Boat Transfer",      "TRANSPORT",  r"boat|shikara"),
    ("Laundry",            "SERVICES",   r"laundry|dry clean|ironing"),
    ("Doctor on Call",     "SERVICES",   r"doctor|medical|first-?aid"),
    ("Concierge",          "SERVICES",   r"concierge|doorman|butler"),
    ("Currency Exchange",  "SERVICES",   r"currency"),
    ("Luggage Storage",    "SERVICES",   r"luggage|baggage"),
    ("CCTV Security",      "SERVICES",   r"cctv|security"),
    ("Garden",             "EXPERIENCE", r"garden|lawn"),
    ("Rooftop Terrace",    "EXPERIENCE", r"roof ?top|terrace"),
    ("Bonfire",            "EXPERIENCE", r"bonfire|camp ?fire"),
    ("Adventure Activities", "EXPERIENCE", r"trek|rafting|adventure|paraglid"),
]
_COMPILED = [(n, c, re.compile(p, re.I)) for n, c, p in AMENITY_RULES]

# Amenities that only appear on curated (signature) properties
EXTRA_AMENITIES = {
    "Sea View": "EXPERIENCE", "Lake View": "EXPERIENCE",
    "River View": "EXPERIENCE", "Mountain View": "EXPERIENCE",
    "Beachfront": "EXPERIENCE", "Heritage Building": "EXPERIENCE",
    "Fireplace": "EXPERIENCE", "Private Deck": "EXPERIENCE",
    "Desert Safari": "EXPERIENCE", "Guided Walks": "EXPERIENCE",
}


def canonical_amenities(raw: str) -> set[str]:
    """'Parking Facility|Room Service (24 Hours)|...' -> {'Parking', 'Room Service 24x7'}"""
    found = set()
    for label in str(raw or "").split("|"):
        label = label.strip()
        if not label:
            continue
        for name, _cat, rx in _COMPILED:
            if rx.search(label):
                found.add(name)
                break
    return found


def amenity_catalogue() -> list[tuple[str, str]]:
    cat = [(n, c) for n, c, _ in AMENITY_RULES]
    cat += sorted(EXTRA_AMENITIES.items())
    return cat


# ── Landmarks ──────────────────────────────────────────────────────────────
# Dataset point_of_interest values that are not useful landmarks
GENERIC_POI = re.compile(
    r"^(others?|bus stand|railway station|airport|main town|city cent(er|re)|"
    r"market|hospital|.*school.*|.*college.*|.*hospital.*|.*bank.*|.*petrol.*|"
    r".*stadium.*|.*bus stand.*|.*police.*|.*office.*|.*university.*|"
    r".*institute.*|.*lane.*|.*road.*|.*area.*|.*nagar$|.*colony.*|north goa|"
    r"south goa|.*super ?market.*|.*mall$|.*sector.*)$", re.I)


def poi_category(name: str) -> str:
    n = name.lower()
    rules = [
        ("BEACH", r"beach"), ("LAKE", r"lake|sagar|dam|falls|talab"),
        ("TEMPLE", r"temple|mandir|ghat|church|mosque|masjid|gurudwara|dargah|monastery|basilica|stupa"),
        ("HERITAGE", r"fort|palace|mahal|tomb|qila|haveli|museum|memorial|gate"),
        ("NATURE", r"park|garden|valley|hill|peak|point|sanctuary|forest|pass|view"),
        ("MARKET", r"bazaar|market|chowk|mall road"),
    ]
    for cat, rx in rules:
        if re.search(rx, n):
            return cat
    return "LANDMARK"


# ── Synthetic people ───────────────────────────────────────────────────────
FIRST_NAMES = (
    "Aarav Vivaan Aditya Arjun Reyansh Ishaan Kabir Rohan Siddharth Karan "
    "Rahul Amit Vikram Nikhil Pranav Harsh Yash Dev Om Varun Abhishek Ankit "
    "Saurabh Manish Gaurav Rajat Tushar Akash Kunal Ritesh Imran Farhan "
    "Zaid Ayaan Arman Sameer Joseph Thomas Jacob Abel Gurpreet Harjot "
    "Manpreet Jaspreet Anirban Sourav Debashish Arnab Subhajit Karthik "
    "Vignesh Suresh Ramesh Prakash Senthil Arvind Naveen Srinivas Venkat "
    "Mohammed Rizwan Aadhya Ananya Diya Saanvi Aanya Ira Myra Kiara Anika "
    "Priya Neha Pooja Sneha Kavya Riya Shreya Isha Tanvi Nisha Meera "
    "Aishwarya Divya Lakshmi Deepika Shalini Swati Ritu Payal Simran "
    "Harleen Navneet Fatima Ayesha Zoya Sana Mariam Anjali Rashmi Sunita "
    "Madhuri Pallavi Moumita Ananya Riddhi Sohini Trisha Keerthi Nandini "
    "Revathi Bhavana Sindhu Jyothi Anusha Mary Teresa Alisha Grace"
).split()

LAST_NAMES_BY_REGION = {
    "NORTH": "Sharma Verma Gupta Agarwal Singh Kapoor Malhotra Chopra Mehra "
             "Bhatia Saxena Srivastava Tiwari Mishra Pandey Yadav Chauhan "
             "Rawat Negi Thakur Dhillon Sandhu Gill Khan Qureshi".split(),
    "WEST": "Patel Shah Mehta Desai Joshi Kulkarni Deshpande Patil Pawar "
            "Jadhav Shinde Naik Bhatt Trivedi Parekh Rathore Shekhawat "
            "Fernandes D'Souza Pereira Gomes".split(),
    "SOUTH": "Iyer Iyengar Nair Menon Pillai Reddy Rao Naidu Krishnan "
             "Subramanian Raman Shetty Hegde Gowda Kumar Varghese Kurian "
             "Thomas Mathew Abraham Chettiar".split(),
    "EAST": "Banerjee Chatterjee Mukherjee Ghosh Bose Das Dutta Sen Roy "
            "Chakraborty Saha Mohanty Patnaik Mahapatra Sinha Jha".split(),
    "NORTHEAST": "Bora Baruah Gogoi Saikia Kalita Sangma Lyngdoh Singha "
                 "Tamang Lepcha Bhutia".split(),
    "CENTRAL": "Tiwari Dubey Chouhan Shukla Tripathi Soni Jain Sahu".split(),
}

REVIEW_TITLES = {
    5: ["Felt like home, only better", "Will come back every winter",
        "Exactly what we needed", "Staff went out of their way",
        "Perfect for the family", "Worth every rupee"],
    4: ["Lovely stay, small niggles", "Great location", "Good value",
        "Comfortable and clean", "Would recommend"],
    3: ["Decent for the price", "Okay for a night or two",
        "Location good, rooms average", "Mixed experience"],
    2: ["Needs maintenance", "Not as pictured", "Service was slow"],
    1: ["Disappointing", "Would not stay again"],
}
REVIEW_BODIES = {
    5: ["Check-in was quick, the room was spotless and breakfast had proper local dishes.",
        "The staff remembered our names from day one. The kids loved it.",
        "Quiet, clean and the view in the morning was unreal."],
    4: ["Good room and helpful staff. Wi-Fi was patchy in the evening.",
        "Great base for sightseeing. Breakfast could have more variety.",
        "Clean, comfortable, and close to everything we wanted to see."],
    3: ["Room was fine but the bathroom needed attention. Location was the best part.",
        "Average stay. Fine for a short trip on a budget."],
    2: ["AC was noisy and the hot water took ages. Front desk tried to help.",
        "Photos look better than the real thing. Would look elsewhere next time."],
    1: ["Booking was not ready when we arrived and we waited two hours.",
        "Room was not clean. Not worth the money."],
}
