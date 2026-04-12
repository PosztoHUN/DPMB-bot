"""
Trip Logger for DPMB Vehicles
Logs all vehicle trips from the IDSJMK API with start/end timestamps
Suitable for 24/7 operation on Railway platform
"""

import asyncio
import aiohttp
import json
import os
from datetime import datetime
from pathlib import Path
import sys
import logging

# =======================
# CONFIGURATION
# =======================
API_URL = "https://mapa.idsjmk.cz/api/vehicles.json"
FETCH_INTERVAL = 30  # seconds - adjust based on API rate limits
ACTIVITY_THRESHOLD = 300  # seconds - if inactive for 5 min, consider trip ended
LOG_DIR = "logs"

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# =======================
# STATE TRACKING
# =======================
# Structure: {vehicle_id: {"course": course_id, "last_seen": timestamp, "direction": direction}}
active_vehicles = {}
trip_history = {}  # {vehicle_id: {"start_time": timestamp, "course": course_id, "direction": direction}}

# =======================
# HELPER FUNCTIONS
# =======================

def ensure_directories():
    """Ensure log directories exist"""
    os.makedirs(LOG_DIR, exist_ok=True)
    os.makedirs(f"{LOG_DIR}/veh", exist_ok=True)
    logger.info(f"Directories ensured: {LOG_DIR}")

def get_log_file_path(course_id):
    """Get the log file path for a course ID, organized by date"""
    today = datetime.now().strftime("%Y-%m-%d")
    date_dir = os.path.join(LOG_DIR, today)
    os.makedirs(date_dir, exist_ok=True)
    return os.path.join(date_dir, f"{course_id}.txt")

def log_trip_event(vehicle_id, course_id, event_type, direction, timestamp, location=None):
    """
    Log a trip event (start/end) to file
    
    Args:
        vehicle_id: Vehicle registration number
        course_id: Route/course ID (e.g., "00707")
        event_type: "START" or "END"
        direction: Direction identifier
        timestamp: Event timestamp
        location: Optional location info
    """
    try:
        log_file = get_log_file_path(course_id)
        
        # Format the log entry
        time_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
        location_str = f" | Location: {location}" if location else ""
        
        log_entry = f"{time_str} | {event_type:5} | Vehicle: {vehicle_id} | Direction: {direction}{location_str}\n"
        
        # Append to log file
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(log_entry)
        
        logger.debug(f"Logged {event_type} for vehicle {vehicle_id} on course {course_id}")
        
    except Exception as e:
        logger.error(f"Error logging trip event: {e}")

def parse_vehicle_data(data):
    """
    Parse vehicle data from API response
    
    Returns:
        dict: {vehicle_id: {"course": course_id, "direction": direction, "location": {lat, lon, ...}}}
    """
    vehicles = {}
    
    try:
        if isinstance(data, dict):
            # Handle different possible API response formats
            items = data.get('vehicles', []) or data.get('data', []) or data.get('results', [])
            
            if not items and isinstance(data, dict):
                # If no standard key, iterate all dict values
                items = list(data.values())
        else:
            items = data if isinstance(data, list) else []
        
        for item in items:
            if not isinstance(item, dict):
                continue
            
            # Extract relevant fields
            vehicle_id = item.get('Registration') or item.get('registration') or item.get('id')
            course_id = item.get('Course') or item.get('course') or item.get('route')
            direction = item.get('Direction') or item.get('direction') or "Unknown"
            
            if vehicle_id and course_id:
                vehicles[str(vehicle_id)] = {
                    "course": str(course_id).zfill(5),  # Pad course ID to 5 digits
                    "direction": str(direction),
                    "location": {
                        "lat": item.get('Latitude') or item.get('latitude'),
                        "lon": item.get('Longitude') or item.get('longitude')
                    }
                }
        
        return vehicles
    
    except Exception as e:
        logger.error(f"Error parsing vehicle data: {e}")
        return {}

# =======================
# MAIN FUNCTIONS
# =======================

async def fetch_vehicle_data():
    """Fetch vehicle data from API"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(API_URL, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.warning(f"API returned status code {response.status}")
                    return None
    except asyncio.TimeoutError:
        logger.warning("API request timeout")
        return None
    except Exception as e:
        logger.error(f"Error fetching vehicle data: {e}")
        return None

async def process_vehicles(current_vehicles):
    """
    Process vehicle data and track trip start/end events
    """
    now = datetime.now()
    now_timestamp = now.timestamp()
    
    # Check for new vehicles or course changes (trip starts)
    for vehicle_id, vehicle_info in current_vehicles.items():
        course_id = vehicle_info["course"]
        direction = vehicle_info["direction"]
        location = vehicle_info.get("location", {})
        
        if vehicle_id not in active_vehicles:
            # New vehicle spotted - LOG START
            logger.info(f"Trip START: Vehicle {vehicle_id} on course {course_id} direction {direction}")
            log_trip_event(vehicle_id, course_id, "START", direction, now, location)
            
            active_vehicles[vehicle_id] = {
                "course": course_id,
                "direction": direction,
                "last_seen": now_timestamp
            }
            trip_history[vehicle_id] = {
                "start_time": now,
                "course": course_id,
                "direction": direction
            }
        
        elif (active_vehicles[vehicle_id]["course"] != course_id or 
              active_vehicles[vehicle_id]["direction"] != direction):
            # Course or direction changed - LOG END of previous, START of new
            old_course = active_vehicles[vehicle_id]["course"]
            old_direction = active_vehicles[vehicle_id]["direction"]
            
            logger.info(f"Trip END: Vehicle {vehicle_id} on course {old_course}")
            log_trip_event(vehicle_id, old_course, "END", old_direction, now, location)
            
            logger.info(f"Trip START: Vehicle {vehicle_id} on course {course_id} direction {direction}")
            log_trip_event(vehicle_id, course_id, "START", direction, now, location)
            
            active_vehicles[vehicle_id] = {
                "course": course_id,
                "direction": direction,
                "last_seen": now_timestamp
            }
            trip_history[vehicle_id] = {
                "start_time": now,
                "course": course_id,
                "direction": direction
            }
        else:
            # Same vehicle, same course - just update last seen
            active_vehicles[vehicle_id]["last_seen"] = now_timestamp
    
    # Check for inactive vehicles (haven't been seen in a while)
    vehicles_to_remove = []
    for vehicle_id, vehicle_data in active_vehicles.items():
        if vehicle_id not in current_vehicles:
            time_inactive = now_timestamp - vehicle_data["last_seen"]
            
            if time_inactive > ACTIVITY_THRESHOLD:
                # Vehicle not seen for a while - LOG END
                course_id = vehicle_data["course"]
                direction = vehicle_data["direction"]
                
                logger.info(f"Trip END: Vehicle {vehicle_id} on course {course_id} (inactive)")
                log_trip_event(vehicle_id, course_id, "END", direction, now)
                
                vehicles_to_remove.append(vehicle_id)
    
    # Remove inactive vehicles
    for vehicle_id in vehicles_to_remove:
        del active_vehicles[vehicle_id]
        del trip_history[vehicle_id]

async def main_loop():
    """Main application loop"""
    ensure_directories()
    logger.info("Trip Logger started")
    logger.info(f"API URL: {API_URL}")
    logger.info(f"Fetch interval: {FETCH_INTERVAL} seconds")
    logger.info(f"Activity threshold: {ACTIVITY_THRESHOLD} seconds")
    
    error_count = 0
    max_errors = 10
    
    while True:
        try:
            # Fetch data from API
            api_data = await fetch_vehicle_data()
            
            if api_data:
                error_count = 0  # Reset error counter on success
                
                # Parse vehicle data
                current_vehicles = parse_vehicle_data(api_data)
                logger.info(f"Fetched data for {len(current_vehicles)} vehicles")
                
                # Process vehicles and track trips
                await process_vehicles(current_vehicles)
                
                # Log current state
                if current_vehicles:
                    logger.debug(f"Active vehicles: {list(current_vehicles.keys())}")
            
            else:
                error_count += 1
                if error_count >= max_errors:
                    logger.error(f"Maximum API errors ({max_errors}) reached, restarting...")
                    error_count = 0
            
            # Wait before next fetch
            await asyncio.sleep(FETCH_INTERVAL)
        
        except KeyboardInterrupt:
            logger.info("Trip Logger stopped by user")
            break
        except Exception as e:
            logger.error(f"Unexpected error in main loop: {e}")
            await asyncio.sleep(FETCH_INTERVAL)

# =======================
# ENTRY POINT
# =======================

if __name__ == "__main__":
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        logger.info("Application terminated")
        sys.exit(0)
