# Backend (app.py) - refactored for Pythonic style
from flask import Flask, render_template, jsonify, request, redirect, url_for, flash
from threading import Thread, Lock
import socket
import re
import maidenhead as mh
import pytz
import time
import argparse
from datetime import datetime as datet
import os  # Added to import os for reading environment variables
from pyhamtools import LookupLib, Callinfo
from werkzeug.utils import secure_filename
import adif_io
import signal
import sys

app = Flask(__name__)
app.secret_key = 'ft8_upload_secret_key'  # Required for flash messages

# Configuration for file uploads
UPLOAD_FOLDER = './uploads'
ALLOWED_EXTENSIONS = {'adi', 'adif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Ensure upload directory exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Parse command-line arguments
parser = argparse.ArgumentParser()
parser.add_argument('mode', nargs='?', default='', help="Mode of operation, e.g., 'debug'")
args = parser.parse_args()

# Set debug mode based on the command-line argument
debug_mode = True

data_lock = Lock()
active_spots = []

# Storage for worked callsigns and ADIF IDs from uploaded ADIF files
worked_callsigns = set()  # Set of callsigns that have been worked before
worked_adif_ids = set()   # Set of ADIF IDs that have been worked before
worked_locators = set()   # Set of locators (grid squares) that have been worked before
worked_lock = Lock()      # Lock for thread-safe access to worked data

def debug_print(message):
    """Prints the message if debug mode is enabled."""
    if debug_mode:
        print(message)

def allowed_file(filename):
    """Check if uploaded file has allowed extension."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def is_callsign_worked(callsign):
    """Check if a callsign has been worked before."""
    with worked_lock:
        return callsign.upper() in worked_callsigns

def is_adif_id_worked(adif_id):
    """Check if an ADIF ID (country) has been worked before."""
    with worked_lock:
        return adif_id in worked_adif_ids

def is_locator_worked(locator):
    """Check if a locator (grid square) has been worked before."""
    with worked_lock:
        return locator.upper() in worked_locators

def add_worked_callsign(callsign, adif_id=None, locator=None):
    """Add a callsign, optionally ADIF ID, and optionally locator to the worked list."""
    with worked_lock:
        worked_callsigns.add(callsign.upper())
        if adif_id and adif_id != 'Unknown':
            worked_adif_ids.add(adif_id)
        if locator and locator != 'Unknown':
            worked_locators.add(locator.upper())

def get_worked_stats():
    """Get statistics about worked callsigns and countries."""
    with worked_lock:
        return {
            'worked_callsigns_count': len(worked_callsigns),
            'worked_countries_count': len(worked_adif_ids),
            'worked_locators_count': len(worked_locators),
            'worked_callsigns': list(worked_callsigns),
            'worked_countries': list(worked_adif_ids),
            'worked_locators': list(worked_locators)
        }

def save_worked_data():
    """Save worked callsigns and ADIF IDs to file."""
    try:
        import json
        worked_data = {
            'callsigns': list(worked_callsigns),
            'adif_ids': list(worked_adif_ids),
            'locators': list(worked_locators)
        }
        with open('./logs/worked_data.json', 'w') as f:
            json.dump(worked_data, f)
        debug_print(f"Saved {len(worked_callsigns)} callsigns, {len(worked_adif_ids)} countries, and {len(worked_locators)} locators to worked_data.json")
    except Exception as e:
        debug_print(f"Error saving worked data: {str(e)}")

def load_worked_data():
    """Load worked callsigns and ADIF IDs from file."""
    try:
        import json
        with open('./logs/worked_data.json', 'r') as f:
            worked_data = json.load(f)
        
        with worked_lock:
            worked_callsigns.update(worked_data.get('callsigns', []))
            worked_adif_ids.update(worked_data.get('adif_ids', []))
            worked_locators.update(worked_data.get('locators', []))
        
        debug_print(f"Loaded {len(worked_callsigns)} callsigns, {len(worked_adif_ids)} countries, and {len(worked_locators)} locators from worked_data.json")
    except FileNotFoundError:
        debug_print("No worked_data.json file found, starting with empty worked list")
    except Exception as e:
        debug_print(f"Error loading worked data: {str(e)}")

def get_unique_adif_ids(adif_file_path):
    """
    Reads an ADIF file and returns a set of unique 'adif_id' fields.

    :param adif_file_path: Path to the ADIF file.
    :return: Set of unique adif_id values.
    """

    calls_set = set()
    list_of_adif_ids = set()

    adif_data, _ = adif_io.read_from_file(adif_file_path)
    
    for record in adif_data:
        calls_set.add(record['CALL'])

    for call in calls_set:
        callinfo = get_callsign_info(call)
        if callinfo and callinfo.get('adif'):
            list_of_adif_ids.add(callinfo['adif'])
        
    return list_of_adif_ids

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload')
def upload_page():
    """Display the ADIF file upload page."""
    return render_template('upload.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle ADIF file upload and processing."""
    if 'file' not in request.files:
        flash('No file selected')
        return redirect(request.url)
    
    file = request.files['file']
    if file.filename == '':
        flash('No file selected')
        return redirect(request.url)
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        try:
            # Check if spots should be displayed on map
            display_on_map = request.form.get('display_on_map') is not None
            
            # Process the ADIF file
            processed_count = process_adif_file(filepath, display_on_map=display_on_map)
            stats = get_worked_stats()
            
            if display_on_map:
                flash(f'Successfully processed {processed_count} records from {filename}. Records added to map display. Total worked: {stats["worked_callsigns_count"]} callsigns, {stats["worked_countries_count"]} countries, {stats["worked_locators_count"]} locators.')
            else:
                flash(f'Successfully processed {processed_count} records from {filename}. Only worked data updated (spots not displayed on map). Total worked: {stats["worked_callsigns_count"]} callsigns, {stats["worked_countries_count"]} countries, {stats["worked_locators_count"]} locators.')
            
            # Optionally remove the uploaded file after processing
            os.remove(filepath)
            
            return redirect(url_for('index'))
        except Exception as e:
            flash(f'Error processing file: {str(e)}')
            return redirect(url_for('upload_page'))
    else:
        flash('Invalid file type. Please upload .adi or .adif files only.')
        return redirect(url_for('upload_page'))


# Retrieve the LimitTime from the environment variable if set, otherwise default to 1800
LIMIT_TIME = int(os.getenv('LimitTime', 1800))

STATION_CALLSIGN = (os.getenv('STATION_CALLSIGN', "SQ2WB"))      #my callsign
MY_GRIDSQUARE    = (os.getenv('MY_GRIDSQUARE', "JO92ES"))         #my grid
ADIF_LOGS        = (os.getenv('ADIF_LOGS', "No"))                 #create adif file or not


my_lookuplib = LookupLib(lookuptype="countryfile")
#my_lookuplib = LookupLib(lookuptype="qrz", username="SQ2WB", pwd="jak1@Qrz")
cic = Callinfo(my_lookuplib)

# Cache for callsign lookups to improve performance
callsign_cache = {}
callsign_cache_lock = Lock()

def get_callsign_info(callsign):
    """Get callsign information with caching to improve performance."""
    callsign_upper = callsign.upper()
    
    # Check cache first
    with callsign_cache_lock:
        if callsign_upper in callsign_cache:
            debug_print(f"Cache hit for {callsign}")
            return callsign_cache[callsign_upper]
    
    # Not in cache, perform lookup
    try:
        callinfo = cic.get_all(callsign)
        # Store in cache
        with callsign_cache_lock:
            callsign_cache[callsign_upper] = callinfo
            debug_print(f"Cached lookup result for {callsign}")
        
        # Save cache periodically (every 10 new entries)
        if len(callsign_cache) % 10 == 0:
            save_callsign_cache()
        
        return callinfo
    except Exception as e:
        debug_print(f"Callsign lookup exception for {callsign}: {str(e)}")
        # Cache the failure result to avoid repeated failed lookups
        with callsign_cache_lock:
            callsign_cache[callsign_upper] = None
        
        # Save cache periodically (every 10 new entries)
        if len(callsign_cache) % 10 == 0:
            save_callsign_cache()
        
        return None

def get_cache_stats():
    """Get callsign cache statistics."""
    with callsign_cache_lock:
        total_entries = len(callsign_cache)
        successful_lookups = sum(1 for v in callsign_cache.values() if v is not None)
        failed_lookups = total_entries - successful_lookups
        return {
            'total_cached_callsigns': total_entries,
            'successful_lookups': successful_lookups,
            'failed_lookups': failed_lookups
        }

def clear_callsign_cache():
    """Clear the callsign lookup cache."""
    with callsign_cache_lock:
        cache_size = len(callsign_cache)
        callsign_cache.clear()
        debug_print(f"Cleared callsign cache ({cache_size} entries)")
        return cache_size

def save_callsign_cache():
    """Save callsign cache to file."""
    try:
        import json
        os.makedirs('./logs', exist_ok=True)
        with callsign_cache_lock:
            cache_data = dict(callsign_cache)
        
        with open('./logs/callsign_cache.json', 'w') as f:
            json.dump(cache_data, f, indent=2)
        debug_print(f"Saved {len(cache_data)} callsign cache entries to callsign_cache.json")
    except Exception as e:
        debug_print(f"Error saving callsign cache: {str(e)}")

def load_callsign_cache():
    """Load callsign cache from file."""
    try:
        import json
        with open('./logs/callsign_cache.json', 'r') as f:
            cache_data = json.load(f)
        
        with callsign_cache_lock:
            callsign_cache.update(cache_data)
        
        debug_print(f"Loaded {len(cache_data)} callsign cache entries from callsign_cache.json")
        return len(cache_data)
    except FileNotFoundError:
        debug_print("No callsign_cache.json file found, starting with empty cache")
        return 0
    except Exception as e:
        debug_print(f"Error loading callsign cache: {str(e)}")
        return 0

def signal_handler(signum, frame):
    """Handle shutdown signals to save cache before exit."""
    print(f"\nReceived signal {signum}, saving cache and shutting down...")
    save_callsign_cache()
    save_worked_data()
    print("Data saved successfully.")
    sys.exit(0)

class FT8Processor:
    def __init__(self):
        self.log_pattern = re.compile(
            r'FT8 DECODE:\s+(\d+\.\d{3})\s+(\w+)\s+([A-R]{2}\d{2}[A-X]{0,2})\s+(-?\d+)\s+(\d+km)\s+([A-Za-z]{3}\s+[A-Za-z]{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}\s+\d{4})'
        )

    def parse_line(self, line):
        """Parse a line of FT8 log and extract relevant information."""
        debug_print(f"Raw input: {line}")
        match = self.log_pattern.search(line)
        if not match:
            debug_print("No pattern match")
            return None
        
        try:
            #Raw input: <14>Feb 26 05:37:01 web-888 : 2d:07:12:58.165 ..2345678....   2           FT8 DECODE: 7074.566 US5EAA KN78 -8 1012km Wed Feb 26 05:36:45 2025
            #New spot added: {'callsign': 'US5EAA', 'frequency': 7074.566, 'timestamp': 1740548205, 'coordinates': [48.0, 34.0], 'humantime': datetime.datetime(2025, 2, 26, 5, 36, 45, tzinfo=<UTC>)
            timestamp = datet.strptime(match.group(6), "%a %b %d %H:%M:%S %Y")
            timestamp = pytz.utc.localize(timestamp)
            unix_time = int(timestamp.timestamp())
            lat, lon = mh.to_location(match.group(3))
            locatorx =  match.group(3)
            
            callsign = match.group(2)
            callinfo = get_callsign_info(callsign)
            
            country = callinfo['country'] if callinfo else 'Unknown'
            adif_id = callinfo['adif'] if callinfo else 'Unknown'
            
            return {
                'callsign': callsign,
                'country': country,
                'adif_id': adif_id,
                'frequency': float(match.group(1)),
                'timestamp': unix_time,
                'coordinates': [lat, lon],
                'humantime': timestamp,
                'locator': locatorx,
                'distance': match.group(5),
                'signal': match.group(4),
                'worked_before': is_callsign_worked(callsign),
                'locator_worked_before': is_locator_worked(locatorx),
                'country_worked_before': is_adif_id_worked(adif_id),
            }
        except Exception as e:
            debug_print(f"Parsing error: {str(e)}")
            return None
        
def process_adif_file(filepath, display_on_map=True):
    """Process uploaded ADIF file and optionally add records to active spots."""
    try:
        # Read ADIF file using adif_io library
        adif_data, _ = adif_io.read_from_file(filepath)
        processed_count = 0
        
        for record in adif_data:
            try:
                # Extract required fields from ADIF record
                callsign = record.get('CALL', '').strip()
                gridsquare = record.get('GRIDSQUARE', 'JO92').strip()
                freq_mhz = record.get('FREQ', '')
                qso_date = record.get('QSO_DATE', '')
                time_on = record.get('TIME_ON', '')
                signal = record.get('RST_RCVD', '-10')  # Default signal if not provided
                
                # Skip invalid records
                if not callsign or not gridsquare or not freq_mhz:
                    continue
                
                # Always add to worked list regardless of display_on_map setting
                # Get country info for callsign
                callinfo = get_callsign_info(callsign)
                country = callinfo['country'] if callinfo else 'Unknown'
                adif_id = callinfo['adif'] if callinfo else 'Unknown'
                
                # Add callsign and ADIF ID to worked list
                add_worked_callsign(callsign, adif_id, gridsquare)
                
                # Only add to active spots if display_on_map is True
                if display_on_map:
                    # Convert frequency from MHz to kHz
                    frequency_khz = float(freq_mhz) * 1000
                    
                    # Convert grid square to coordinates
                    lat, lon = mh.to_location(gridsquare)
                    
                    # Parse date and time to create timestamp
                    if qso_date and time_on:
                        # Pad time_on to 6 digits if needed (HHMMSS)
                        time_on = time_on.ljust(6, '0')
                        datetime_str = f"{qso_date} {time_on}"
                        qso_datetime = datet.strptime(datetime_str, "%Y%m%d %H%M%S")
                        qso_datetime = pytz.utc.localize(qso_datetime)
                        unix_time = int(qso_datetime.timestamp())
                    else:
                        # Use current time if no date/time provided
                        unix_time = int(time.time())
                        qso_datetime = datet.now(pytz.utc)
                    
                    # Calculate distance (placeholder - you might want to implement actual distance calculation)
                    distance = "0km"
                    
                    # Create spot entry
                    spot_entry = {
                        'callsign': callsign,
                        'country': country,
                        'adif_id': adif_id,
                        'frequency': frequency_khz,
                        'timestamp': unix_time,
                        'coordinates': [lat, lon],
                        'humantime': qso_datetime,
                        'locator': gridsquare,
                        'distance': distance,
                        'signal': signal,
                        'worked_before': True,
                        'locator_worked_before': True,
                        'country_worked_before': True,
                    }
                    
                    # Add to active spots with thread safety
                    with data_lock:
                        active_spots.append(spot_entry)
                        debug_print(f"Added ADIF spot to map: {callsign} from {gridsquare}")
                else:
                    debug_print(f"Added ADIF callsign to worked list (not displayed): {callsign} from {gridsquare}")
                
                processed_count += 1
                
            except Exception as e:
                debug_print(f"Error processing ADIF record: {str(e)}")
                continue
        
        # Save worked data after processing all records
        save_worked_data()
        
        # Save callsign cache after processing all records
        save_callsign_cache()
        
        return processed_count
        
    except Exception as e:
        debug_print(f"Error reading ADIF file: {str(e)}")
        raise e

# frequency conversion
def frequency_to_band(frequency_khz):
    """Convert frequency in kHz to amateur radio band name"""
    freq_mhz = frequency_khz / 1000
    if 0.136 <= freq_mhz < 0.478: return '2190m'
    elif 0.478 <= freq_mhz < 2.0: return '630m'
    elif 1.8 <= freq_mhz < 2.0: return '160m'
    elif 3.5 <= freq_mhz < 4.0: return '80m'
    elif 5.1 <= freq_mhz < 5.45: return '60m'
    elif 7.0 <= freq_mhz < 7.3: return '40m'
    elif 10.1 <= freq_mhz < 10.15: return '30m'
    elif 14.0 <= freq_mhz < 14.35: return '20m'
    elif 18.068 <= freq_mhz < 18.168: return '17m'
    elif 21.0 <= freq_mhz < 21.45: return '15m'
    elif 24.89 <= freq_mhz < 24.99: return '12m'
    elif 28.0 <= freq_mhz < 29.7: return '10m'
    elif 50 <= freq_mhz < 54: return '6m'
    elif 144 <= freq_mhz < 148: return '2m'
    else: return 'Unknown'


        
        
#log in adif format for wsjt-x like processing        
def log_adi_entry(entry):
    """Append WSJT-X compatible ADIF entry to log file."""
    directory = './logs/'
    file_path = './logs/wsjtx_log.adi'

    # Ensure the directory exists
    os.makedirs(directory, exist_ok=True)

    # Convert frequency and time formats
    band = frequency_to_band(entry['frequency'])
    freq_mhz = entry['frequency'] / 1000
    qso_date = entry['humantime'].strftime('%Y%m%d')
    time_on = entry['humantime'].strftime('%H%M%S')

    # Build the ADIF record
    adif_entry = f"""<CALL:{len(entry['callsign'])}>{entry['callsign']}
<GRIDSQUARE:{len(entry['locator'])}>{entry['locator']}
<MODE:3>FT8
<RST_SENT:3>-00
<RST_RCVD:{len(entry['signal'])}>{entry['signal']}
<QSO_DATE:8>{qso_date}
<TIME_ON:6>{time_on}
<QSO_DATE_OFF:8>{qso_date}
<TIME_OFF:6>{time_on}
<BAND:{len(band)}>{band}
<FREQ:9>{freq_mhz:.6f}
<STATION_CALLSIGN:{len(STATION_CALLSIGN)}>{STATION_CALLSIGN}
<MY_GRIDSQUARE:{len(MY_GRIDSQUARE)}>{MY_GRIDSQUARE}
<COMMENT:{len(entry['distance'])}>Distance: {entry['distance']}
<EOR>\n"""

    # Append the record to the file
    with open(file_path, 'a', encoding='utf-8') as log_file:
        log_file.write(adif_entry)
        
        

def udp_listener():
    """Listen for incoming UDP packets and process FT8 log data."""
    processor = FT8Processor()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", 5140))
    
    while True:
        data, addr = sock.recvfrom(1024)
        entry = processor.parse_line(data.decode('utf-8'))
        
        if entry:
            with data_lock:
                active_spots.append(entry)
                debug_print(f"New spot added: {entry}")
                if ADIF_LOGS != "No":
                   log_adi_entry(entry)

@app.route('/spots')
def get_spots():
    """Get active spots that have not expired."""
    nowUnix = int(time.time())
    debug_print("====================SPOTS=======================================")

    # Prepare data for the response
    spots = [{
        'coordinates': spot['coordinates'],
        'callsign': spot['callsign'],
        'frequency': spot['frequency'],
        'timestamp': spot['timestamp'],
        'locator': spot['locator'],
        'distance':spot['distance'],
        'signal':spot['signal'],
        'uptime':(nowUnix - spot['timestamp']),
        'worked_before': spot.get('worked_before', False),
        'locator_worked_before': spot.get('locator_worked_before', False),
        'country_worked_before': spot.get('country_worked_before', False),
        'country': spot['country'],
                  
    } for spot in active_spots]
    return jsonify(spots)

@app.route('/worked_stats')
def get_worked_statistics():
    """Get statistics about worked callsigns and countries."""
    return jsonify(get_worked_stats())

@app.route('/cache_stats')
def get_cache_statistics():
    """Get callsign cache statistics."""
    return jsonify(get_cache_stats())

@app.route('/save_cache')
def save_cache_endpoint():
    """Manually save callsign cache."""
    save_callsign_cache()
    stats = get_cache_stats()
    return jsonify({
        'status': 'Cache saved successfully',
        'cache_stats': stats
    })







def cleanup_spots():
    """Clears out spots that are older than the defined LIMIT_TIME."""
    nowUnix = int(time.time())
    with data_lock:
        active_spots[:] = [
            spot for spot in active_spots if nowUnix - spot['timestamp'] <= LIMIT_TIME
        ]
    debug_print(f"Cleared spots older than {LIMIT_TIME} sec. Remaining spots: {len(active_spots)}")
          
    
    
    

def schedule_cleanup():
    """Schedules the cleanup function to run every 30 seconds."""
    while True:
        time.sleep(30)  # Wait for 30 seconds
        cleanup_spots()             

if __name__ == '__main__':
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print("--------------------------------------------------------------------")
    print("Syslog should send data to UDP port: 5140")
    print("  *** LimitTime: We show spots from last: "+str(LIMIT_TIME)+" sec")
    print("  *** Callsign lookup caching: ENABLED")
    print("--------------------------------------------------------------------")
    
    # Load previously worked callsigns and countries
    load_worked_data()
    stats = get_worked_stats()
    print(f"Loaded worked data: {stats['worked_callsigns_count']} callsigns, {stats['worked_countries_count']} countries, {stats['worked_locators_count']} locators")
    
    # Load callsign cache
    cache_entries = load_callsign_cache()
    cache_stats = get_cache_stats()
    print(f"Loaded callsign cache: {cache_entries} entries ({cache_stats['successful_lookups']} successful, {cache_stats['failed_lookups']} failed)")
    
    # Start the UDP listener in a separate thread
    Thread(target=udp_listener, daemon=True).start()
    
    # Start the cleanup scheduler in a separate thread
    Thread(target=schedule_cleanup, daemon=True).start()
    
    try:
        app.run(host='0.0.0.0', port=5019)
    except KeyboardInterrupt:
        print("\nShutting down...")
        # Save cache on shutdown
        save_callsign_cache()
        save_worked_data()
        print("Data saved before exit.")


