import sys
import requests
import ssl
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
ssl._create_default_https_context = ssl._create_unverified_context
import time
import threading
from threading import Thread  # <--- এটি এখানে থাকতে হবে
import re
import json
import os
import uuid
import base64
import random
from datetime import datetime
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telebot import apihelper

# --- ফ্লাস্ক সার্ভার ---
from flask import Flask
app = Flask('')

@app.route('/')
def home():
    return "VoltX Bot is Alive!"

def run():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()
# -------------------------------------------------------------

_old_inline_dict = InlineKeyboardButton.to_dict
def _new_inline_dict(self):
    d = _old_inline_dict(self)
    if hasattr(self, 'style'):
        d['style'] = self.style
    if hasattr(self, 'custom_copy_text') and self.custom_copy_text:
        d['copy_text'] = {'text': str(self.custom_copy_text)}
        if 'callback_data' in d:
            del d['callback_data']
    return d
InlineKeyboardButton.to_dict = _new_inline_dict

_old_kb_dict = KeyboardButton.to_dict
def _new_kb_dict(self):
    d = _old_kb_dict(self)
    if hasattr(self, 'style'):
        d['style'] = self.style
    return d
KeyboardButton.to_dict = _new_kb_dict

def ibtn(text, callback_data=None, url=None, style=None, copy_text_str=None):
    kwargs = {'text': text}
    if copy_text_str:
        kwargs['callback_data'] = "fake_copy_btn"
    else:
        if callback_data: kwargs['callback_data'] = callback_data
        if url: kwargs['url'] = url
    b = InlineKeyboardButton(**kwargs)
    if style: b.style = style
    if copy_text_str: b.custom_copy_text = copy_text_str
    return b

def rbtn(text, style=None):
    b = KeyboardButton(text=text)
    if style: b.style = style
    return b

TELEGRAM_TOKEN = "8649831949:AAHEw1rk6tMn80ZRm1QY-ci-FbgYPygmV54"
ADMIN_ID = 6876722159
API_BASE_URL = "https://api.2oo9.cloud/MXS47FLFX0U/tnevs/@public/api"
API_KEY = "MTVYKS62I8S"
HEADERS = {
    "mauthapi": API_KEY,
    "Content-Type": "application/json"
}

LOG_GROUP_ID = "-1004336048552"

USER_DB = "users.json"
ACTIVE_NUMBERS_DB = "active_numbers.json"
_ENCODED_NAME = ""

def init_databases():
    files = {
        USER_DB: [],
        ACTIVE_NUMBERS_DB: {}
    }
    for file, default in files.items():
        if not os.path.exists(file):
            with open(file, "w") as f:
                json.dump(default, f)

init_databases()

def get_all_users():
    with open(USER_DB, "r") as f:
        return json.load(f)

def add_user(user_id):
    with open(USER_DB, "r") as f:
        users = json.load(f)
    if user_id not in users:
        users.append(user_id)
        with open(USER_DB, "w") as f:
            json.dump(users, f)

def get_active_numbers():
    with open(ACTIVE_NUMBERS_DB, "r") as f:
        return json.load(f)

def save_active_numbers(numbers):
    with open(ACTIVE_NUMBERS_DB, "w") as f:
        json.dump(numbers, f)

def add_active_number(phone, chat_id, service, range_code):
    data = get_active_numbers()
    data[str(phone)] = {
        "chat_id": chat_id,
        "service": service,
        "range": range_code,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    save_active_numbers(data)

def remove_active_number(phone):
    data = get_active_numbers()
    if str(phone) in data:
        del data[str(phone)]
        save_active_numbers(data)

def mask_number(phone):
    phone_str = str(phone)
    if len(phone_str) >= 10:
        return phone_str[:7] + "XXX" + phone_str[-2:]
    return phone_str

def extract_otp_from_text(text):
    clean_text = re.sub(r'[-\s]', '', text)
    patterns = [
        r'\b(\d{8})\b', r'\b(\d{7})\b', r'\b(\d{6})\b',
        r'\b(\d{5})\b', r'\b(\d{4})\b', r'\b(\d{3})\b',
        r'code[:\s]*(\d+)', r'OTP[:\s]*(\d+)', r'(\d+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, clean_text, re.IGNORECASE)
        if match and len(match.group(1)) >= 3:
            return match.group(1)
    return "N/A"

def get_service_name_from_msg(msg):
    msg_lower = msg.lower()
    if 'facebook' in msg_lower: return "Facebook"
    elif 'whatsapp' in msg_lower: return "WhatsApp"
    elif 'instagram' in msg_lower: return "Instagram"
    return "Unknown"

def get_footer():
    try:
        decoded_name = base64.b64decode(_ENCODED_NAME).decode('utf-8')
        return f"\n\n━━━━━━━━━━━━━━━━━━━━\n{decoded_name.replace(':', '')}"
    except:
        return ""

def voltx_get_live_services():
    url = f"{API_BASE_URL}/liveaccess"
    try:
        res = requests.get(url, headers=HEADERS, timeout=15, verify=False)
        if res.status_code == 200:
            data = res.json()
            if data.get("meta", {}).get("code") == 200:
                services = data.get("data", {}).get("services", [])
                if services: return services
    except Exception as e:
        print(f"Error loading live services: {e}")
    return [
        {"sid": "Facebook", "ranges": ["8801XXX", "23762XXX"]},
        {"sid": "WhatsApp", "ranges": ["8801XXX", "22901XXX"]}
    ]

def voltx_get_ranges_for_service(service_name):
    services = voltx_get_live_services()
    for s in services:
        if s.get("sid", "").lower() == service_name.lower():
            ranges = s.get("ranges", [])
            if ranges: return ranges
    return ["8801XXX", "23762XXX"]

def voltx_fetch_number(range_code):
    rid = range_code.replace("XXX", "").replace("X", "").strip()
    if not rid: rid = "8801"
    url = f"{API_BASE_URL}/getnum"
    payload = {"rid": rid}
    try:
        res = requests.post(url, json=payload, headers=HEADERS, timeout=30, verify=False)
        if res.status_code == 200:
            data = res.json()
            if data.get("meta", {}).get("code") == 200:
                number_data = data.get("data", {})
                full_number = number_data.get("full_number") or number_data.get("no_plus_number")
                if full_number:
                    return str(full_number).replace("+", "").strip()
    except Exception as e:
        print(f"Error fetching number: {e}")
    return None

def voltx_fetch_multiple_numbers(range_code, count=3):
    numbers = []
    for _ in range(count):
        number = voltx_fetch_number(range_code)
        if number and number not in numbers:
            numbers.append(number)
        time.sleep(0.3)
    return numbers

def voltx_check_otp():
    url = f"{API_BASE_URL}/success-otp"
    results = []
    try:
        res = requests.get(url, headers=HEADERS, timeout=15, verify=False)
        if res.status_code == 200:
            data = res.json()
            if data.get("meta", {}).get("code") == 200:
                otps = data.get("data", {}).get("otps", [])
                active = get_active_numbers()
                for phone in active:
                    for otp_item in otps:
                        otp_number = otp_item.get("number", "").replace("+", "").strip()
                        if phone == otp_number:
                            message = otp_item.get("message", "")
                            if message:
                                otp_code = extract_otp_from_text(message)
                                service_name = get_service_name_from_msg(message)
                                if service_name == "Unknown":
                                    service_name = active[phone].get("service", "Unknown")
                                if otp_code != "N/A":
                                    results.append({
                                        "phone": phone, "message": message,
                                        "otp": otp_code, "service": service_name,
                                    })
                                    break
    except Exception as e:
        print(f"Error checking OTP: {e}")
    return results

def get_main_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(rbtn("🎲 GET NUMBER", "primary"), rbtn("📩 CONTACT ADMIN", "primary"))
    return markup

def get_admin_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(rbtn("📢 Broadcast", "primary"), rbtn("📊 Stats", "success"))
    markup.row(rbtn("🔙 Back Main Menu", "danger"))
    return markup

def get_service_keyboard():
    markup = InlineKeyboardMarkup(row_width=2)
    services = voltx_get_live_services()
    for s in services[:4]:
        sid = s.get("sid", "Unknown")
        markup.add(ibtn(f"📘 {sid}", callback_data=f"service_{sid.lower()}", style="primary"))
    markup.row(ibtn("🔄 Refresh Services", callback_data="refresh_services", style="success"))
    markup.row(ibtn("🔙 Back Main Menu", callback_data="back_main_menu", style="danger"))
    return markup

COUNTRY_MAP = {
    "93": ("🇦🇫", "Afghanistan"), "355": ("🇦🇱", "Albania"), "213": ("🇩🇿", "Algeria"), "1684": ("🇦🇸", "American Samoa"), 
    "376": ("🇦🇩", "Andorra"), "244": ("🇦🇴", "Angola"), "1264": ("🇦🇮", "Anguilla"), "672": ("🇦🇶", "Antarctica"), 
    "1268": ("🇦🇬", "Antigua & Barbuda"), "54": ("🇦🇷", "Argentina"), "374": ("🇦🇲", "Armenia"), "297": ("🇦🇼", "Aruba"), 
    "61": ("🇦🇺", "Australia"), "43": ("🇦🇹", "Austria"), "994": ("🇦🇿", "Azerbaijan"), "1242": ("🇧🇸", "Bahamas"), 
    "973": ("🇧🇭", "Bahrain"), "880": ("🇧🇩", "Bangladesh"), "1246": ("🇧🇧", "Barbados"), "375": ("🇧🇾", "Belarus"), 
    "32": ("🇧🇪", "Belgium"), "501": ("🇧🇿", "Belize"), "229": ("🇧🇯", "Benin"), "1441": ("🇧🇲", "Bermuda"), 
    "975": ("🇧🇹", "Bhutan"), "591": ("🇧🇴", "Bolivia"), "387": ("🇧🇦", "Bosnia & Herzegovina"), "267": ("🇧🇼", "Botswana"), 
    "55": ("🇧🇷", "Brazil"), "246": ("🇮🇴", "British Indian Ocean Territory"), "1284": ("🇻🇬", "British Virgin Islands"), 
    "673": ("🇧🇳", "Brunei"), "359": ("🇧🇬", "Bulgaria"), "226": ("🇧🇫", "Burkina Faso"), "257": ("🇧🇮", "Burundi"), 
    "855": ("🇰🇭", "Cambodia"), "237": ("🇨🇲", "Cameroon"), "1": ("🇺🇸", "USA/Canada"), "238": ("🇨🇻", "Cape Verde"), 
    "345": ("🇰🇾", "Cayman Islands"), "236": ("🇨🇫", "Central African Republic"), "235": ("🇹🇩", "Chad"), "56": ("🇨🇱", "Chile"), 
    "86": ("🇨🇳", "China"), "61": ("🇨🇽", "Christmas Island"), "61": ("🇨🇨", "Cocos Islands"), "57": ("🇨🇴", "Colombia"), 
    "269": ("🇰🇲", "Comoros"), "242": ("🇨🇬", "Congo - Brazzaville"), "243": ("🇨🇩", "Congo - Kinshasa"), "682": ("🇨🇰", "Cook Islands"), 
    "506": ("🇨🇷", "Costa Rica"), "225": ("🇨🇮", "Côte d’Ivoire"), "385": ("🇭🇷", "Croatia"), "53": ("🇨🇺", "Cuba"), 
    "599": ("🇨🇼", "Curaçao"), "357": ("🇨🇾", "Cyprus"), "420": ("🇨🇿", "Czechia"), "45": ("🇩🇰", "Denmark"), 
    "253": ("🇩🇯", "Djibouti"), "1767": ("🇩🇲", "Dominica"), "1809": ("🇩🇴", "Dominican Republic"), "593": ("🇪🇨", "Ecuador"), 
    "20": ("🇪🇬", "Egypt"), "503": ("🇸🇻", "El Salvador"), "240": ("🇬🇶", "Equatorial Guinea"), "291": ("🇪🇷", "Eritrea"), 
    "372": ("🇪🇪", "Estonia"), "251": ("🇪🇹", "Ethiopia"), "500": ("🇫🇰", "Falkland Islands"), "298": ("🇫🇴", "Faroe Islands"), 
    "679": ("🇫🇯", "Fiji"), "358": ("🇫🇮", "Finland"), "33": ("🇫🇷", "France"), "594": ("🇬🇫", "French Guiana"), 
    "689": ("🇵🇫", "French Polynesia"), "241": ("🇬🇦", "Gabon"), "220": ("🇬🇲", "Gambia"), "995": ("🇬🇪", "Georgia"), 
    "49": ("🇩🇪", "Germany"), "233": ("🇬🇭", "Ghana"), "350": ("🇬🇮", "Gibraltar"), "30": ("🇬🇷", "Greece"), 
    "299": ("🇬🇱", "Greenland"), "1473": ("🇬🇩", "Grenada"), "590": ("🇬🇵", "Guadeloupe"), "1671": ("🇬🇺", "Guam"), 
    "502": ("🇬🇹", "Guatemala"), "44": ("🇬🇬", "Guernsey"), "224": ("🇬🇳", "Guinea"), "245": ("🇬🇼", "Guinea-Bissau"), 
    "592": ("🇬🇾", "Guyana"), "509": ("🇭🇹", "Haiti"), "504": ("🇭🇳", "Honduras"), "852": ("🇭🇰", "Hong Kong SAR China"), 
    "36": ("🇭🇺", "Hungary"), "354": ("🇮🇸", "Iceland"), "91": ("🇮🇳", "India"), "62": ("🇮🇩", "Indonesia"), 
    "98": ("🇮🇷", "Iran"), "964": ("🇮🇶", "Iraq"), "353": ("🇮🇪", "Ireland"), "44": ("🇮🇲", "Isle of Man"), 
    "972": ("🇮🇱", "Israel"), "39": ("🇮🇹", "Italy"), "1876": ("🇯🇲", "Jamaica"), "81": ("🇯🇵", "Japan"), 
    "44": ("🇯🇪", "Jersey"), "962": ("🇯🇴", "Jordan"), "7": ("🇰🇿", "Kazakhstan"), "254": ("🇰🇪", "Kenya"), 
    "686": ("🇰🇮", "Kiribati"), "381": ("🇽🇰", "Kosovo"), "965": ("🇰🇼", "Kuwait"), "996": ("🇰🇬", "Kyrgyzstan"), 
    "856": ("🇱🇦", "Laos"), "371": ("🇱🇻", "Latvia"), "961": ("🇱🇧", "Lebanon"), "266": ("🇱🇸", "Lesotho"), 
    "231": ("🇱🇷", "Liberia"), "218": ("🇱🇾", "Libya"), "423": ("🇱🇮", "Liechtenstein"), "370": ("🇱🇹", "Lithuania"), 
    "352": ("🇱🇺", "Luxembourg"), "853": ("🇲🇴", "Macao SAR China"), "389": ("🇲🇰", "North Macedonia"), "261": ("🇲🇬", "Madagascar"), 
    "265": ("🇲🇼", "Malawi"), "60": ("🇲🇾", "Malaysia"), "960": ("🇲🇻", "Maldives"), "223": ("🇲🇱", "Mali"), 
    "356": ("🇲🇹", "Malta"), "692": ("🇲🇭", "Marshall Islands"), "596": ("🇲🇶", "Martinique"), "222": ("🇲🇷", "Mauritania"), 
    "230": ("🇲🇺", "Mauritius"), "262": ("🇾🇹", "Mayotte"), "52": ("🇲🇽", "Mexico"), "691": ("🇫🇲", "Micronesia"), 
    "373": ("🇲🇩", "Moldova"), "377": ("🇲🇨", "Monaco"), "976": ("🇲🇳", "Mongolia"), "382": ("🇲🇪", "Montenegro"), 
    "1664": ("🇲🇸", "Montserrat"), "212": ("🇲🇦", "Morocco"), "258": ("🇲🇿", "Mozambique"), "95": ("🇲🇲", "Myanmar (Burma)"), 
    "264": ("🇳🇦", "Namibia"), "674": ("🇳🇷", "Nauru"), "977": ("🇳🇵", "Nepal"), "31": ("🇳🇱", "Netherlands"), 
    "687": ("🇳🇨", "New Caledonia"), "64": ("🇳🇿", "New Zealand"), "505": ("🇳🇮", "Nicaragua"), "227": ("🇳🇪", "Niger"), 
    "234": ("🇳🇬", "Nigeria"), "683": ("🇳🇺", "Niue"), "672": ("🇳🇫", "Norfolk Island"), "850": ("🇰🇵", "North Korea"), 
    "1670": ("🇲🇵", "Northern Mariana Islands"), "47": ("🇳🇴", "Norway"), "968": ("🇴🇲", "Oman"), "92": ("🇵🇰", "Pakistan"), 
    "680": ("🇵🇼", "Palau"), "970": ("🇵🇸", "Palestine"), "507": ("🇵🇦", "Panama"), "675": ("🇵🇬", "Papua New Guinea"), 
    "595": ("🇵🇾", "Paraguay"), "51": ("🇵🇪", "Peru"), "63": ("🇵🇭", "Philippines"), "64": ("🇵🇳", "Pitcairn Islands"), 
    "48": ("🇵🇱", "Poland"), "351": ("🇵🇹", "Portugal"), "1787": ("🇵🇷", "Puerto Rico"), "974": ("🇶🇦", "Qatar"), 
    "262": ("🇷🇪", "Réunion"), "40": ("🇷🇴", "Romania"), "7": ("🇷🇺", "Russia"), "250": ("🇷🇼", "Rwanda"), 
    "590": ("🇧🇱", "Saint Barthélemy"), "290": ("🇸🇭", "Saint Helena"), "1869": ("🇰🇳", "Saint Kitts & Nevis"), 
    "1758": ("🇱🇨", "Saint Lucia"), "590": ("🇲🇫", "Saint Martin"), "508": ("🇵🇲", "Saint Pierre & Miquelon"), 
    "1784": ("🇻🇨", "Saint Vincent & Grenadines"), "685": ("🇼🇸", "Samoa"), "378": ("🇸🇲", "San Marino"), "239": ("🇸🇹", "São Tomé & Príncipe"), 
    "966": ("🇸🇦", "Saudi Arabia"), "221": ("🇸🇳", "Senegal"), "381": ("🇷🇸", "Serbia"), "248": ("🇸🇨", "Seychelles"), 
    "232": ("🇸🇱", "Sierra Leone"), "65": ("🇸🇬", "Singapore"), "1721": ("🇸🇽", "Sint Maarten"), "421": ("🇸🇰", "Slovakia"), 
    "386": ("🇸🇮", "Slovenia"), "677": ("🇸🇧", "Solomon Islands"), "252": ("🇸🇴", "Somalia"), "27": ("🇿🇦", "South Africa"), 
    "500": ("🇬🇸", "South Georgia & South Sandwich Islands"), "82": ("🇰🇷", "South Korea"), "211": ("🇸🇸", "South Sudan"), 
    "34": ("🇪🇸", "Spain"), "94": ("🇱🇰", "Sri Lanka"), "249": ("🇸🇩", "Sudan"), "597": ("🇸🇷", "Suriname"), 
    "47": ("🇸🇻", "Svalbard & Jan Mayen"), "268": ("🇸🇿", "Eswatini"), "46": ("🇸🇪", "Sweden"), "41": ("🇨🇭", "Switzerland"), 
    "963": ("🇸🇾", "Syria"), "886": ("🇹🇼", "Taiwan"), "992": ("🇹🇯", "Tajikistan"), "255": ("🇹🇿", "Tanzania"), 
    "66": ("🇹🇭", "Thailand"), "670": ("🇹🇱", "Timor-Leste"), "228": ("🇹🇬", "Togo"), "690": ("🇹🇰", "Tokelau"), 
    "676": ("🇹🇴", "Tonga"), "1868": ("🇹🇹", "Trinidad & Tobago"), "216": ("🇹🇳", "Tunisia"), "90": ("🇹🇷", "Turkey"), 
    "993": ("🇹🇲", "Turkmenistan"), "1649": ("🇹🇨", "Turks & Caicos Islands"), "688": ("🇹🇻", "Tuvalu"), "256": ("🇺🇬", "Uganda"), 
    "380": ("🇺🇦", "Ukraine"), "971": ("🇦🇪", "United Arab Emirates"), "44": ("🇬🇧", "United Kingdom"), 
    "1": ("🇺🇸", "United States"), "598": ("🇺🇾", "Uruguay"), "998": ("🇺🇿", "Uzbekistan"), "678": ("🇻🇺", "Vanuatu"), 
    "379": ("🇻🇦", "Vatican City"), "58": ("🇻🇪", "Venezuela"), "84": ("🇻🇳", "Vietnam"), "1340": ("🇻🇮", "U.S. Virgin Islands"), 
    "681": ("🇼🇫", "Wallis & Futuna"), "212": ("🇪🇭", "Western Sahara"), "967": ("🇾🇪", "Yemen"), "260": ("🇿🇲", "Zambia"), 
    "263": ("🇿🇼", "Zimbabwe")
}

def get_country_info(range_code):
    digits = re.sub(r'[^0-9]', '', range_code)
    for length in (4, 3, 2, 1):
        prefix = digits[:length]
        if prefix in COUNTRY_MAP: return COUNTRY_MAP[prefix]
    return ("📱", "")

def get_range_keyboard(ranges, service):
    markup = InlineKeyboardMarkup(row_width=1)
    for r in ranges[:15]:
        flag, country = get_country_info(r)
        label = f"{flag} {r} {country}" if country else f"📱 {r}"
        markup.add(ibtn(label, callback_data=f"get_number_{service}_{r}", style="primary"))
    markup.row(ibtn("🔄 Refresh", callback_data=f"refresh_ranges_{service}", style="success"))
    markup.row(ibtn("🔙 Back to Services", callback_data="back_to_services", style="danger"))
    return markup

def get_quantity_keyboard(service, range_code):
    markup = InlineKeyboardMarkup(row_width=3)
    markup.row(
        ibtn("1⚡", callback_data=f"q_{service}_{range_code}_1", style="primary"),
        ibtn("2⚡", callback_data=f"q_{service}_{range_code}_2", style="primary"),
        ibtn("3⚡", callback_data=f"q_{service}_{range_code}_3", style="primary")
    )
    markup.row(
        ibtn("4⚡", callback_data=f"q_{service}_{range_code}_4", style="primary"),
        ibtn("5⚡", callback_data=f"q_{service}_{range_code}_5", style="primary")
    )
    markup.row(ibtn("🔙 Back to Ranges", callback_data="back_to_ranges", style="danger"))
    return markup

def send_otp_notification(chat_id, phone, service, otp, message):
    masked = mask_number(phone)
    footer = get_footer()
    active = get_active_numbers()
    range_code = active.get(str(phone), {}).get("range", None)
    country_line = range_line = ""
    if range_code:
        flag, country_name = get_country_info(range_code)
        country_line = f"\n🌍 Country : {flag} {country_name}" if country_name else f"\n🌍 Country : {flag}"
        range_line = f"\n🌀 Range : `{range_code}`"
        
    dm_msg = f"━━━━━━━━━━━━━━━━━━━━\n⚡ Number: `{phone}`\n🎯 Service: {service}{country_line}{range_line}\n━━━━━━━━━━━━━━━━━━━━\n🔐 OTP Code: `{otp}`💬 Full SMS:\n`{message[:200]}`{footer}"
    group_msg = f"✅ OTP RECEIVED!\n━━━━━━━━━━━━━━━━━━━━\n⚡ Number: `{masked}`\n🎯 Service: {service}{country_line}{range_line}\n━━━━━━━━━━━━━━━━━━━━\n🔐 OTP Code: `{otp}`\n━━━━━━━━━━━━━━━━━━━━\n💬 Full SMS:\n`{message[:200]}`{footer}"
    
    otp_markup = InlineKeyboardMarkup(row_width=1)
    otp_markup.row(ibtn(f" {otp} ", copy_text_str=str(otp), style="success"))
    otp_markup.row(ibtn(f" {phone} ", copy_text_str=str(phone), style="primary"))
    
    
    try:
        bot.send_message(chat_id, dm_msg, parse_mode="Markdown", reply_markup=otp_markup)
        bot.send_message(LOG_GROUP_ID, group_msg, parse_mode="Markdown")
    except Exception as e: print(f"Send error: {e}")

def send_number_received_notification(chat_id, numbers, service_name, range_code=None):
    country_line = range_line = ""
    if range_code:
        flag, country_name = get_country_info(range_code)
        country_line = f"\n🌍 Country : {flag} {country_name}" if country_name else f"\n🌍 Country : {flag}"
        range_line = f"\n🌀 Range : `{range_code}`"
        
    markup = InlineKeyboardMarkup(row_width=1)
    for number in numbers:
        markup.add(ibtn(f" {number} ", copy_text_str=number, style="primary"))
        
    markup.row(ibtn("🔄 Change Numbers", callback_data=f"change_number_{service_name}", style="success"))
    markup.row(ibtn("🌍 Change Country", callback_data=f"back_to_ranges", style="primary"))
    markup.row(ibtn("💬 OTP GROUP🔗", url="https://t.me/+zaDzeTKnXi84NDhl", style="primary"))
    
    msg = f"🎯 NEW NUMBERS RECEIVED!\n━━━━━━━━━━━━━━━━━━━━\n🎯 Service: {service_name}{country_line}{range_line}\n━━━━━━━━━━━━━━━━━━━━\n"
    bot.send_message(chat_id, msg, parse_mode="Markdown", reply_markup=markup)

bot = telebot.TeleBot(TELEGRAM_TOKEN)
user_service = {}
user_last_range = {}

@bot.message_handler(commands=['start'])
def start_cmd(message):
    user = message.from_user
    add_user(user.id)
    
    Welcome_text = (
        f"<code>"
        f" █░░█ █░░█ █▀▀▄ ▀▀█▀▀ █▀▀ █▀▀█ █░░█\n"
        f" █▀▀█ █░░█ █░░█ ░░█░░ █▀▀ █▄▄▀ ▄▀▀▄\n"
        f" ▀░░▀ ░▀▀▀ ▀░░▀ ░░▀░░ ▀▀▀ ▀░▀▀ ▀░░▀\n"
        f"  ─── 𝐕𝟐.𝟔✨ ───\n"
        f"</code>\n"
        f"🔖 Welcome, DEAR USER {user.first_name}! Your VoltX Automated Otp Panel Is Fully Active.\n\n"
        f"🛰️ Mainframe: `VoltX SMS Receive OTP‼️`\n"
        f"⚡ Bypass Status: `Ready to Listen`\n\n"
        f"㊙️ Please Select Your Option From The Menu Below : "
    )
    
    bot.send_message(
        message.chat.id,
        Welcome_text,
        parse_mode="HTML",
        reply_markup=get_main_keyboard()
    )

@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.from_user.id == ADMIN_ID:
        bot.send_message(message.chat.id, "🔧 Admin Panel Open!", reply_markup=get_admin_keyboard())

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    chat_id = call.message.chat.id
    msg_id = call.message.message_id
    data = call.data
    
    if data in ["reply_"] or data.startswith("reply_"):
        admin_callback(call)
        return
        
    if data == "back_main_menu":
        bot.answer_callback_query(call.id)
        try: bot.delete_message(chat_id, msg_id)
        except: pass
        bot.send_message(chat_id, "🏠 Main Menu", reply_markup=get_main_keyboard())
        return
    
    if data == "back_to_services":
        bot.edit_message_text("🔍 Select Service:", chat_id, msg_id, reply_markup=get_service_keyboard())
        bot.answer_callback_query(call.id)
        return
    
    if data == "back_to_ranges":
        service_name = user_service.get(chat_id, "facebook")
        ranges = voltx_get_ranges_for_service(service_name)
        bot.answer_callback_query(call.id)
        try: bot.delete_message(chat_id, msg_id)
        except: pass
        if ranges:
            bot.send_message(chat_id, f"🔥 Live Ranges for {service_name.capitalize()}:", reply_markup=get_range_keyboard(ranges, service_name))
        else:
            bot.send_message(chat_id, "❌ No live ranges found!", reply_markup=get_service_keyboard())
        return
    
    if data == "refresh_services":
        bot.edit_message_text("🔍 Select Service:", chat_id, msg_id, reply_markup=get_service_keyboard())
        bot.answer_callback_query(call.id)
        return
    
    if data.startswith("refresh_ranges_"):
        service_name = data.replace("refresh_ranges_", "")
        ranges = voltx_get_ranges_for_service(service_name)
        if ranges:
            bot.edit_message_text(f"🔥 Live Ranges for {service_name.capitalize()} (Refreshed):", chat_id, msg_id, reply_markup=get_range_keyboard(ranges, service_name))
        else:
            bot.edit_message_text("❌ No live ranges found!", chat_id, msg_id, reply_markup=get_service_keyboard())
        bot.answer_callback_query(call.id)
        return
    
    if data.startswith("service_"):
        service_name = data.replace("service_", "")
        user_service[chat_id] = service_name
        ranges = voltx_get_ranges_for_service(service_name)
        if ranges:
            bot.edit_message_text(f"🔥 Live Ranges for {service_name.capitalize()}:", chat_id, msg_id, reply_markup=get_range_keyboard(ranges, service_name))
        else:
            bot.edit_message_text(f"❌ No live ranges found!", chat_id, msg_id, reply_markup=get_service_keyboard())
        bot.answer_callback_query(call.id)
        return
    
    if data.startswith("get_number_"):
        parts = data.split("_")
        service_name = parts[2]
        range_code = parts[3]
        user_last_range[chat_id] = range_code
        user_service[chat_id] = service_name
        
        bot.edit_message_text(
            f"🎯 Range: `{range_code}`\n\nআপনি এই রেঞ্জ থেকে কয়টি নাম্বার নিতে চান তা নিচে থেকে সিলেক্ট করুন:", 
            chat_id, 
            msg_id, 
            parse_mode="Markdown", 
            reply_markup=get_quantity_keyboard(service_name, range_code)
        )
        bot.answer_callback_query(call.id)
        return

    if data.startswith("q_"):
        parts = data.split("_")
        service_name = parts[1]
        range_code = parts[2]
        count = int(parts[3])
        
        user_last_range[chat_id] = range_code
        user_service[chat_id] = service_name
        
        bot.edit_message_text(f"⏳ Requesting {count} numbers from `{range_code}`...\n\nPlease wait...", chat_id, msg_id, parse_mode="Markdown")
        numbers_found = voltx_fetch_multiple_numbers(range_code, count=count)
        
        if numbers_found:
            for number in numbers_found:
                add_active_number(number, chat_id, service_name.capitalize(), range_code)
            bot.delete_message(chat_id, msg_id)
            send_number_received_notification(chat_id, numbers_found, service_name.capitalize(), range_code)
        else:
            bot.edit_message_text(f"❌ No numbers available from `{range_code}`!\n\nPlease try another range.", chat_id, msg_id, parse_mode="Markdown", reply_markup=get_range_keyboard(voltx_get_ranges_for_service(service_name), service_name))
        
        bot.answer_callback_query(call.id)
        return
    
    if data.startswith("change_number_"):
        service_name = data.replace("change_number_", "")
        range_code = user_last_range.get(chat_id)
        if not range_code:
            bot.answer_callback_query(call.id, "Select range first!", show_alert=True)
            return
        bot.delete_message(chat_id, msg_id)
        loading_msg = bot.send_message(chat_id, f"⏳ Requesting new numbers from `{range_code}`...\n\nPlease wait...", parse_mode="Markdown")
        numbers_found = voltx_fetch_multiple_numbers(range_code, count=3)
        bot.delete_message(chat_id, loading_msg.message_id)
        if numbers_found:
            for number in numbers_found:
                add_active_number(number, chat_id, service_name, range_code)
            send_number_received_notification(chat_id, numbers_found, service_name, range_code)
        else:
            bot.send_message(chat_id, f"❌ No numbers available from `{range_code}`!\n\nPlease try another range.", parse_mode="Markdown", reply_markup=get_service_keyboard())
        bot.answer_callback_query(call.id)
        return

@bot.message_handler(func=lambda m: True)
def handle_text_messages(message):
    chat_id = message.chat.id
    text = message.text.strip()
    
    if text == "🔙 Back Main Menu":
        bot.send_message(chat_id, "🏠 Main Menu", reply_markup=get_main_keyboard())
        return
        
    if message.from_user.id == ADMIN_ID and text in ["📢 Broadcast", "📊 Stats"]:
        if text == "📢 Broadcast":
            msg = bot.send_message(chat_id, "📢 Send broadcast:")
            bot.register_next_step_handler(msg, broadcast_msg)
        elif text == "📊 Stats":
            users = len(get_all_users())
            active = len(get_active_numbers())
            bot.send_message(chat_id, f"📊 Stats\n👥 Users: {users}\n📱 Active: {active}")
        return
        
    if text == "🎲 GET NUMBER":
        bot.send_message(chat_id, "🔍 Select Service:", reply_markup=get_service_keyboard())
        return
        
    if text == "📩 CONTACT ADMIN":
        msg = bot.send_message(chat_id, "📝 Write your message:", parse_mode="Markdown")
        bot.register_next_step_handler(msg, forward_to_admin)
        return
        
    bot.send_message(chat_id, "ℹ️ Please use the buttons below to get started!", reply_markup=get_main_keyboard())

def forward_to_admin(message):
    if message.text:
        markup = InlineKeyboardMarkup()
        markup.row(ibtn("💬 Reply", callback_data=f"reply_{message.chat.id}", style="primary"))
        bot.send_message(ADMIN_ID, f"📩 New Message from {message.from_user.first_name}\nID: {message.chat.id}\n\n{message.text}", reply_markup=markup)
        bot.send_message(message.chat.id, "✅ Message sent to admin!")

def broadcast_msg(message):
    users = get_all_users()
    success = 0
    for uid in users:
        try:
            bot.send_message(uid, f"📢 Broadcast\n\n{message.text}")
            success += 1
            time.sleep(0.05)
        except: pass
    bot.send_message(ADMIN_ID, f"✅ Sent to {success} users!")

def admin_callback(call):
    if call.data.startswith("reply_"):
        user_id = int(call.data.split("_")[1])
        msg = bot.send_message(call.message.chat.id, f"✍️ Reply to {user_id}:")
        bot.register_next_step_handler(msg, send_reply, user_id)
        bot.answer_callback_query(call.id)

def send_reply(message, user_id):
    try:
        bot.send_message(user_id, f"👨‍💻 Admin Reply:\n\n{message.text}")
        bot.send_message(message.chat.id, "✅ Reply sent!")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Failed: {e}")

sent_otps = set()

def otp_monitor():
    global sent_otps
    print("🔄 OTP Monitor Loop Thread Active")
    while True:
        try:
            otps = voltx_check_otp()
            for otp_data in otps:
                phone = otp_data["phone"]
                unique_key = f"{phone}_{otp_data['otp']}"
                if unique_key not in sent_otps:
                    sent_otps.add(unique_key)
                    active = get_active_numbers()
                    if str(phone) in active:
                        chat_id = active[str(phone)]["chat_id"]
                        send_otp_notification(chat_id, phone, otp_data["service"], otp_data["otp"], otp_data["message"])
                        remove_active_number(phone)
            if len(sent_otps) > 2000:
                sent_otps.clear()
        except Exception as e:
            print(f"Monitor Error: {e}")
        time.sleep(5)

if __name__ == "__main__":
    print("=" * 60)
    print("🤖 VOLTX OTP NUMBER PANEL ENGINE")
    print("🚀 Welcome Text & Copy Buttons Fully Configured!")
    print("=" * 60)
    
    # রেন্ডারের জন্য ফ্লাস্ক সার্ভার ব্যাকগ্রাউন্ডে চালু করা হলো
    keep_alive()
    
    threading.Thread(target=otp_monitor, daemon=True).start()
    
    print("✅ System Core Synchronized Successfully!")
    bot.infinity_polling(timeout=60)
