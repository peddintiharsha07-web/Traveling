"""Static homepage content (tips, steps, stories, help types).

Destinations and problems live in the database; see core/seed_data.py.
"""

HELP_TYPES = [
    {"key": "hospital", "icon": "cross", "label": "Hospitals"},
    {"key": "police", "icon": "shield", "label": "Police stations"},
    {"key": "hotel", "icon": "bed", "label": "Hotels"},
    {"key": "restaurant", "icon": "utensils", "label": "Restaurants"},
    {"key": "mechanic", "icon": "wrench", "label": "Mechanics"},
    {"key": "transport", "icon": "bus", "label": "Transport"},
]

SAFETY_TIPS = [
    {"icon": "luggage", "title": "Keep copies of your documents",
     "text": "Store scans of your passport, visa, and insurance in cloud storage, and carry one paper copy apart from the originals."},
    {"icon": "pin", "title": "Share your plan with someone at home",
     "text": "Send your itinerary, hotel names, and flight numbers to a person who will notice if you go quiet."},
    {"icon": "wifi", "title": "Download maps before you leave Wi-Fi",
     "text": "Offline maps for your city and hotel area keep working when the signal does not."},
    {"icon": "card", "title": "Carry two ways to pay",
     "text": "Keep a second card and some local cash in a different bag from your main wallet."},
    {"icon": "pulse", "title": "Know the local emergency number",
     "text": "It is not 911 everywhere. Save it, plus your embassy contact, in your phone before landing."},
    {"icon": "cloud", "title": "Check the forecast the night before",
     "text": "Weather shifts fast in mountains and on coasts. Pack one layer more than you think you need."},
]

STEPS = [
    {"title": "Pick your problem",
     "text": "Choose the situation closest to yours, from lost passports to flight delays."},
    {"title": "Follow the steps",
     "text": "Each guide gives you what to do first, who to call, and what to keep as proof."},
    {"title": "Find help nearby",
     "text": "Look up hospitals, police, mechanics, and transport around your location."},
    {"title": "Report and track",
     "text": "Log the problem in your account, follow its status, and read community replies."},
]

# Sample stories shown with a "sample" caption. Replace with real traveler
# feedback once the community features exist.
STORIES = [
    {"quote": "My bag never reached Lisbon. The checklist told me exactly which form to file before leaving the airport.",
     "name": "Sample story", "trip": "Lisbon, Portugal"},
    {"quote": "A landslide closed our road in the Andes. Knowing who to call turned a bad afternoon into a short detour.",
     "name": "Sample story", "trip": "Cusco, Peru"},
    {"quote": "Offline maps saved us when the signal dropped on the way to a trailhead.",
     "name": "Sample story", "trip": "Dolomites, Italy"},
]
