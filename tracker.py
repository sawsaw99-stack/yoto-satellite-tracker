import os
import requests
from datetime import datetime, timedelta
import timezonefinder
import pytz
from gtts import gTTS

# 1. Configuration
API_KEY = os.getenv("N2YO_API_KEY", "7M42XK-7U28CH-KGNPE2-5RXX")
LATITUDE = os.getenv("HOME_LAT", "44.58")
LONGITUDE = os.getenv("HOME_LONG", "103.46")
ALTITUDE = os.getenv("HOME_ALT", "100")
OUTPUT_FILENAME = "satellite_feed.mp3"
FEED_FILENAME = "podcast.xml"
ARCHIVE_DIR = "archives" # Name of your rolling bucket folder

# Ensure the archive folder exists
os.makedirs(ARCHIVE_DIR, exist_ok=True)

SATELLITE_FLEET = [
    [27607, "The S O 50 amateur radio satellite", False],
    [43017, "The A O 91 Fox 1B satellite", False],
    [43678, "The P O 101 Diwata satellite", False],
    [40931, "The I O 86 LAPAN satellite", False],
    [61781, "The A O 123 satellite", True],
    [68446, "The S O 127 Hades satellite", False],
    [25544, "The International Space Station", False]
]

tf = timezonefinder.TimezoneFinder()
LOCAL_TZ = pytz.timezone(tf.timezone_at(lng=LONGITUDE, lat=LATITUDE))

# Date Targets
now_local = datetime.now(LOCAL_TZ)
today_date = now_local.date()
tomorrow_date = (now_local + timedelta(days=1)).date()

current_date_str = now_local.strftime("%A, %B %d")
speech_text = f"Space update complete! Today is {current_date_str}. Looking at the sky: "

today_reports = []
tomorrow_reports = []

print("Scanning fleet for structured daily schedules...")

for satellite in SATELLITE_FLEET:
    norad_id = satellite[0]
    common_name = satellite[1]
    needs_daylight = satellite[2]
    
    url = f"https://api.n2yo.com/rest/v1/satellite/visualpasses/{norad_id}/{LATITUDE}/{LONGITUDE}/{ALTITUDE}/10/300/&apiKey={API_KEY}"
    
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            
            if "passes" in data and len(data["passes"]) > 0:
                sat_today_passes = []
                sat_tomorrow_passes = []
                
                for pass_data in data["passes"]:
                    start_ts = pass_data["startUTC"]
                    max_ts = pass_data["maxUTC"]
                    
                    start_dt = datetime.fromtimestamp(start_ts, tz=pytz.utc).astimezone(LOCAL_TZ)
                    max_dt = datetime.fromtimestamp(max_ts, tz=pytz.utc).astimezone(LOCAL_TZ)
                    
                    if not (7 <= start_dt.hour < 23):
                        continue
                    
                    duration_seconds = pass_data["duration"]
                    duration_minutes = max(1, round(duration_seconds / 60))
                    min_word = "minute" if duration_minutes == 1 else "minutes"
                    
                    start_time_str = start_dt.strftime("%I:%M %p").lstrip("0")
                    max_time_str = max_dt.strftime("%I:%M %p").lstrip("0")
                    
                    pass_sentence = f"{start_time_str} for {duration_minutes} {min_word}, peaking at {max_time_str}. "
                    
                    if start_dt.date() == today_date:
                        sat_today_passes.append(pass_sentence)
                    elif start_dt.date() == tomorrow_date:
                        sat_tomorrow_passes.append(pass_sentence)
                
                if len(sat_today_passes) > 0:
                    pass_word = "pass" if len(sat_today_passes) == 1 else "passes"
                    report = f"{common_name} has {len(sat_today_passes)} {pass_word}. " + "".join(sat_today_passes)
                    today_reports.append(report)
                    
                if len(sat_tomorrow_passes) > 0:
                    pass_word = "pass" if len(sat_tomorrow_passes) == 1 else "passes"
                    report = f"{common_name} has {len(sat_tomorrow_passes)} {pass_word}. " + "".join(sat_tomorrow_passes)
                    tomorrow_reports.append(report)
                    
    except Exception as e:
        print(f"Error processing {norad_id}: {e}")

# Build Chronological Speech
speech_text += "For today. "
if len(today_reports) > 0:
    speech_text += "".join(today_reports)
else:
    speech_text += "The skies are quiet. "

speech_text += "For tomorrow. "
if len(tomorrow_reports) > 0:
    speech_text += "".join(tomorrow_reports)
else:
    speech_text += "No operational passes predicted. "

speech_text += "That is all for today's orbital report. Keep your ears on the airwaves!"

# Save Main Audio File for Yoto
tts = gTTS(text=speech_text, lang='en')
tts.save(OUTPUT_FILENAME)

# --- NEW: SAVE TO ARCHIVE BUCKET ---
archive_filename = f"archive_{now_local.strftime('%Y-%m-%d')}.mp3"
archive_filepath = os.path.join(ARCHIVE_DIR, archive_filename)
tts.save(archive_filepath)
print(f"Stored daily copy in archives: {archive_filename}")

# --- NEW: PURGE OLD ARCHIVES (OLDER THAN 30 DAYS) ---
print("Checking archive bucket for files older than 30 days...")
purge_threshold = now_local - timedelta(days=30)

for file in os.listdir(ARCHIVE_DIR):
    if file.startswith("archive_") and file.endswith(".mp3"):
        try:
            # Extract date from filename (archive_YYYY-MM-DD.mp3)
            date_str = file.replace("archive_", "").replace(".mp3", "")
            file_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            
            if file_date < purge_threshold.date():
                os.remove(os.path.join(ARCHIVE_DIR, file))
                print(f"🗑️ Deleted expired 30-day archive: {file}")
        except Exception as purge_err:
            print(f"Could not parse archive file date {file}: {purge_err}")

# Generate XML
xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
  <channel>
    <title>Amateur Radio Satellite Tracker</title>
    <link>https://sawsaw99-stack.github.io/yoto-satellite-tracker/</link>
    <language>en-us</language>
    <description>Daily orbital pass predictions for Wisconsin</description>
    <item>
      <title>Daily Briefing - {current_date_str}</title>
      <pubDate>{now_local.strftime("%a, %d %b %Y %H:%M:%S %z")}</pubDate>
      <enclosure url="https://sawsaw99-stack.github.io/yoto-satellite-tracker/satellite_feed.mp3" type="audio/mpeg"/>
      <guid isPermaLink="false">satellite-pass-{now_local.strftime("%Y-%m-%d")}</guid>
      <itunes:duration>180</itunes:duration>
    </item>
  </channel>
</rss>"""

with open(FEED_FILENAME, "w", encoding="utf-8") as f:
    f.write(xml_content)

print("🎉 Audio tracking and rolling archive maintenance complete!")
