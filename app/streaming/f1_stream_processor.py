import aiohttp
import asyncio
import json
import base64
import zlib
import urllib.parse
from datetime import datetime, timedelta, timezone
import os

from app.utils.helpers import safe_to_float, time_string_to_seconds, deep_merge

# NEW: A dictionary mapping circuit short names to their official lap counts
GRAND_PRIX_LAPS = {
    "Monte Carlo": 78,
    "Silverstone": 52,
    "Spa-Francorchamps": 44,
    "Monza": 53,
    "Bahrain": 57,
    "Jeddah": 50,
    "Albert Park": 58,
    "Imola": 63,
    "Miami": 57,
    "Catalunya": 66,
    "Gilles-Villeneuve": 70,
    "Red Bull Ring": 71,
    "Hungaroring": 70,
    "Zandvoort": 72,
    "Marina Bay": 62,
    "Suzuka": 53,
    "COTA": 56,
    "Mexico City": 71,
    "Interlagos": 71,
    "Las Vegas": 50,
    "Losail": 57,
    "Yas Marina": 58,
    "Shanghai": 56,
    "Baku": 51
}

class F1StreamProcessor:
    """
    Connects to the F1 SignalR feed, or replays from a file, processes the messages,
    and updates the state via the StateManager.
    """
    F1_BASE_URL = "livetiming.formula1.com/signalr"
    SIGNALR_HUB = '[{"name":"Streaming"}]'

    # Auto-reconnect configuration
    MAX_RETRY_DELAY = 600  # Max delay between retries in seconds (e.g., 10 minutes)
    INITIAL_RETRY_DELAY = 5 # Initial delay in seconds

    def __init__(self, state_manager):
        self.state_manager = state_manager
        self.session = None
        print("F1 Stream Processor initialized.")

    async def connect_and_process_live(self):
        """
        Establishes a LIVE connection to the F1 SignalR feed with auto-reconnect logic.
        """
        retry_delay = self.INITIAL_RETRY_DELAY
        while True: # Keep attempting to connect indefinitely
            try:
                print(f"Connecting to F1 feed. Next attempt in {retry_delay} seconds if failed...")
                hub_encoded = urllib.parse.quote(self.SIGNALR_HUB)
                headers = {"User-Agent": "Mozilla/5.0", "Origin": "https://www.formula1.com"}

                # Ensure session is closed before creating a new one for a retry attempt
                if self.session and not self.session.closed:
                    await self.session.close()
                self.session = aiohttp.ClientSession()

                # Step 1: Negotiate
                negotiate_url = f"https://{self.F1_BASE_URL}/negotiate?clientProtocol=1.5&connectionData={hub_encoded}"
                async with self.session.get(negotiate_url, headers=headers) as resp:
                    resp.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
                    data = await resp.json()
                    token = data.get("ConnectionToken")
                    if not token:
                        raise ConnectionError("Failed to get connection token during negotiation.")

                # Step 2: WebSocket Connection
                ws_url = (
                    f"wss://{self.F1_BASE_URL}/connect?clientProtocol=1.5&transport=webSockets&"
                    f"connectionToken={urllib.parse.quote(token)}&connectionData={hub_encoded}"
                )

                async with self.session.ws_connect(ws_url, headers=headers, max_msg_size=0) as ws:
                    print("Successfully connected to F1 WebSocket. Listening for data...")
                    retry_delay = self.INITIAL_RETRY_DELAY # Reset delay on successful connection
                    await self._subscribe(ws)
                    await self._listen(ws) # This will block until the WebSocket closes or errors

                print("WebSocket connection closed gracefully. Attempting to reconnect.")

            except (aiohttp.ClientError, ConnectionError) as e:
                print(f"Connection or negotiation error: {e}. Retrying in {retry_delay} seconds...")
            except Exception as e:
                print(f"An unexpected error occurred: {e}. Retrying in {retry_delay} seconds...")
            finally:
                if self.session and not self.session.closed:
                    await self.session.close()
                # Wait before retrying
                await asyncio.sleep(retry_delay)
                # Exponential backoff
                retry_delay = min(retry_delay * 2, self.MAX_RETRY_DELAY)

    async def replay_from_file(self, filepath="monaco-race-data.jsonl", speed=1.0):
        """
        Reads data from a log file and processes it to simulate a live session.
        A higher speed value will make the replay faster.
        """
        print(f"--- Starting replay from file: {filepath} ---")
        if not os.path.exists(filepath):
            print(f"Error: Replay file not found at '{filepath}'")
            return

        last_message_time = None
        with open(filepath, 'r') as f:
            for line in f:
                try:
                    log_entry = json.loads(line)
                    
                    # --- Simulate real-world timing ---
                    current_message_time = datetime.fromisoformat(log_entry['timestamp'])
                    if last_message_time:
                        delay = (current_message_time - last_message_time).total_seconds()
                        if delay > 0:
                            await asyncio.sleep(delay / speed)
                    last_message_time = current_message_time
                    
                    # --- Process the data based on its type ---
                    message_type = log_entry.get("type")
                    raw_data = log_entry.get("data")

                    if message_type == "text":
                        # For text messages, the 'data' field is a JSON string
                        # which our processor already handles.
                        await self._process_message(raw_data, current_message_time)
                    elif message_type == "binary":
                        # For binary, the 'data' is a Base64 string.
                        decoded = self._decode_and_decompress(raw_data)
                        if decoded:
                            # NOTE: This part makes an assumption. We don't know the 'feed_name'
                            # from a pure binary message, so we must infer it.
                            # We'll assume 'CarData' for now as it's a likely candidate.
                            self.state_manager.update_state("CarData", decoded)
                            await self.state_manager.broadcast({
                                "type": "CarData",
                                "data": decoded
                            })

                    print(">", end="", flush=True)
                except json.JSONDecodeError:
                    print(f"\nWarning: Skipping line, could not parse as JSON: {line.strip()}")
                except Exception as e:
                    print(f"\nAn error occurred during replay: {e}")


        print("\n--- Replay finished ---")

    async def _subscribe(self, ws):
        """
        Subscribes to all the necessary data feeds.
        """
        subscribe_msg = json.dumps({
            "H": "Streaming", "M": "Subscribe",
            "A": [[
                "Heartbeat", "CarData.z", "Position.z", "ExtrapolatedClock",
                "TopThree", "RcmSeries", "TimingStats", "TimingAppData",
                "WeatherData", "TrackStatus", "SessionStatus", "DriverList",
                "RaceControlMessages", "SessionInfo", "SessionData", "LapCount",
                "TimingData", "TeamRadio"
            ]], "I": 1
        })
        await ws.send_str(subscribe_msg)
        print("Subscribed to F1 data streams.")

    async def _listen(self, ws):
        """
        Listens for incoming messages and passes them to the processor.
        """
        async for msg in ws:
            message_received_time = datetime.now(timezone.utc)
            if msg.type == aiohttp.WSMsgType.TEXT:
                await self._process_message(msg.data, message_received_time)
            elif msg.type == aiohttp.WSMsgType.BINARY:
                # If we get a raw binary message, we can process it directly
                decoded = self._decode_and_decompress(msg.data)
                if decoded:
                    # We would need a way to know which feed this belongs to.
                    # For now, let's assume 'CarData' as an example.
                    self.state_manager.update_state("CarData", decoded)
                    await self.state_manager.broadcast({
                        "type": "CarData",
                        "data": decoded
                    })
            elif msg.type == aiohttp.WSMsgType.ERROR:
                print(f"WebSocket error: {ws.exception()}")
                break
        print("Listener stopped.")

    async def _process_message(self, raw_data_string, timestamp=None):
        """
        Processes a raw JSON string message from the WebSocket.
        """
        data = json.loads(raw_data_string)

        if "R" in data:
            await self._handle_snapshot(data["R"])
        elif "M" in data and isinstance(data["M"], list) and data["M"]:
            await self._handle_feed_update(data["M"], timestamp)

    async def _handle_snapshot(self, snapshot_data):
        """
        Processes the large initial state snapshot ("R" message).
        """
        print("\nProcessing initial state snapshot...")
        for feed_name, feed_data in snapshot_data.items():
            if feed_name.endswith(".z"):
                clean_feed_name = feed_name[:-2]
                decoded_data = self._decode_and_decompress(feed_data)
                if decoded_data:
                    # --- NEW LOGIC (for compressed data) ---
                    # If we find SessionInfo, set the total laps from our map
                    if clean_feed_name == "SessionInfo":
                        circuit_short_name = decoded_data.get("Meeting", {}).get("Circuit", {}).get("ShortName")
                        if circuit_short_name:
                            total_laps = GRAND_PRIX_LAPS.get(circuit_short_name, 0)
                            self.state_manager.state["LapCount"]["TotalLaps"] = total_laps
                    
                    # We completely IGNORE the buggy LapCount feed now
                    if clean_feed_name != "LapCount":
                        self.state_manager.update_state(clean_feed_name, decoded_data)
            else:
                # --- NEW LOGIC (for uncompressed data) ---
                # If we find SessionInfo, set the total laps from our map
                if feed_name == "SessionInfo":
                    circuit_short_name = feed_data.get("Meeting", {}).get("Circuit", {}).get("ShortName")
                    if circuit_short_name:
                        total_laps = GRAND_PRIX_LAPS.get(circuit_short_name, 0)
                        self.state_manager.state["LapCount"]["TotalLaps"] = total_laps
                
                # We completely IGNORE the buggy LapCount feed now
                if feed_name != "LapCount":
                    self.state_manager.update_state(feed_name, feed_data)

        full_state = self.state_manager.get_full_state()
        await self.state_manager.broadcast(full_state)
        print("Initial state snapshot processed and broadcasted.")

    async def _check_and_record_laps(self, timing_data_update, message_timestamp_str):
        """
        Checks a TimingData update to see if any laps have been completed.
        If so, it constructs a lap record and saves it to history.
        This version correctly parses M:S.ms time strings and calculates start time.
        """
        if "Lines" not in timing_data_update:
            return

        for driver_number, update_payload in timing_data_update["Lines"].items():
            last_lap_time_str = update_payload.get("LastLapTime", {}).get("Value")

            if last_lap_time_str:
                lap_duration_seconds = time_string_to_seconds(last_lap_time_str)
                if lap_duration_seconds is None:
                    continue

                driver_state_before_update = self.state_manager.state["TimingData"].get("Lines", {}).get(driver_number, {}).copy()
                fully_merged_driver_data = deep_merge(driver_state_before_update, update_payload)
                
                lap_number = fully_merged_driver_data.get("NumberOfLaps")
                if not lap_number: continue

                # --- NEW: Calculate the lap start time ---
                date_start = None
                if message_timestamp_str:
                    try:
                        # Convert end time and duration to datetime objects
                        end_time_dt = datetime.fromisoformat(message_timestamp_str.replace('Z', '+00:00'))
                        duration_td = timedelta(seconds=lap_duration_seconds)
                        # Calculate start time and format it back to a string
                        start_time_dt = end_time_dt - duration_td
                        date_start = start_time_dt.isoformat()
                    except (ValueError, TypeError):
                        pass # Ignore if there's any issue parsing dates
                # ----------------------------------------

                lap_record = {
                    "date_start": date_start, # <-- Use the calculated value
                    "driver_number": int(driver_number),
                    "lap_number": lap_number,
                    "lap_duration": lap_duration_seconds,
                    "duration_sector_1": time_string_to_seconds(fully_merged_driver_data.get("Sectors", {}).get("0", {}).get("Value")),
                    "duration_sector_2": time_string_to_seconds(fully_merged_driver_data.get("Sectors", {}).get("1", {}).get("Value")),
                    "duration_sector_3": time_string_to_seconds(fully_merged_driver_data.get("Sectors", {}).get("2", {}).get("Value")),
                    "i1_speed": fully_merged_driver_data.get("Speeds", {}).get("I1", {}).get("Value"),
                    "i2_speed": fully_merged_driver_data.get("Speeds", {}).get("I2", {}).get("Value"),
                    "st_speed": fully_merged_driver_data.get("Speeds", {}).get("ST", {}).get("Value"),
                    "is_pit_out_lap": fully_merged_driver_data.get("PitOut", False),
                    "session_key": self.state_manager.state.get("SessionInfo",{}).get("Key"),
                    "meeting_key": self.state_manager.state.get("SessionInfo",{}).get("Meeting",{}).get("Key")
                }
                
                self.state_manager.add_lap_to_history(lap_record)

                # --- ADD THIS DEBUG PRINT ---
                print(f"DEBUG: Recorded Lap {lap_number} for Driver {driver_number}. Data: {lap_record}")

                await self.state_manager.broadcast({"type": "NewLap", "data": lap_record})
                # print(f"\nLap {lap_number} for driver {driver_number} recorded...")
                # print(f"\nLap {lap_number} for driver {driver_number} recorded with duration {lap_duration}s.")
    
    async def _check_and_record_pits(self, timing_data_update, timestamp=None):
        """
        Checks a TimingData update for pit stop events.
        """
        if "Lines" not in timing_data_update:
            return
        
        # --- FIX: Use the provided timestamp, or fall back to now() ---
        event_time = timestamp if timestamp else datetime.now(timezone.utc)

        for driver_number, update in timing_data_update["Lines"].items():
            # Check for a driver entering the pits
            if update.get("InPit") is True:
                # Record the entry time and lap number
                self.state_manager.state["DriversInPits"][driver_number] = {
                    "entry_time": datetime.now(timezone.utc),
                    "lap_number": self.state_manager.state["TimingData"]["Lines"].get(driver_number, {}).get("NumberOfLaps", 0) + 1
                }
                print(f"\nDriver {driver_number} entered pits.")

            # Check for a driver exiting the pits
            if update.get("PitOut") is True:
                if driver_number in self.state_manager.state["DriversInPits"]:
                    pit_entry_data = self.state_manager.state["DriversInPits"].pop(driver_number)
                    # Make sure both times are timezone-aware before subtracting
                    exit_time = event_time.replace(tzinfo=timezone.utc) if event_time.tzinfo is None else event_time
                    entry_time = pit_entry_data["entry_time"]
                    
                    pit_duration = (exit_time - entry_time).total_seconds()
                    
                    pit_record = {
                        "date": exit_time.isoformat(),
                        "driver_number": int(driver_number),
                        "lap_number": pit_entry_data["lap_number"],
                        "pit_duration": round(pit_duration, 2),
                        "session_key": self.state_manager.state.get("SessionInfo", {}).get("Key"),
                        "meeting_key": self.state_manager.state.get("SessionInfo", {}).get("Meeting", {}).get("Key")
                    }
                    
                    self.state_manager.add_pit_stop_to_history(pit_record)
                    await self.state_manager.broadcast({"type": "NewPitStop", "data": pit_record})
                    # print(f"\nPit stop for driver {driver_number} recorded...")
                    print(f"\nPit stop for driver {driver_number} recorded with duration {pit_duration}s.")

    async def _handle_feed_update(self, feed_updates, timestamp=None):
        """
        Processes incremental feed updates ("M" messages).
        """
        for update in feed_updates:
            # Basic validation of the update structure
            if "M" in update and "A" in update and isinstance(update["A"], list) and len(update["A"]) > 1:
                feed_name = update["A"][0]
                payload = update["A"][1]

                # Convert datetime object to ISO string for JSON serialization if it exists
                timestamp_str = timestamp.isoformat() if timestamp else None

                if feed_name == "TimingData":
                    # First, update the main state with the new TimingData.
                    self.state_manager.update_state(feed_name, payload)
                    
                    # 1. First, get the correct TotalLaps that we've already stored in our state.
                    #    This defines the variable and resolves the error.
                    known_total_laps = self.state_manager.state.get("LapCount", {}).get("TotalLaps", 0)

                    # Next, calculate the true current lap from the driver data.
                    all_drivers_timing = self.state_manager.state.get("TimingData", {}).get("Lines", {})
                    max_laps_completed = 0
                    if all_drivers_timing:
                        for driver_data in all_drivers_timing.values():
                            laps = driver_data.get("NumberOfLaps", 0)
                            if laps > max_laps_completed:
                                max_laps_completed = laps
                    
                    # The current lap is the highest completed lap + 1.
                    current_lap = max_laps_completed + 1 if max_laps_completed > 0 else 1

                     # Then we build our own, correct LapCount object and broadcast it
                    correct_lap_data = { "CurrentLap": current_lap, "TotalLaps": known_total_laps }
                    self.state_manager.state["LapCount"] = correct_lap_data

                    # Now, broadcast the complete, corrected LapCount object.
                    await self.state_manager.broadcast({
                        "type": "LapCount",
                        "data": correct_lap_data
                    })

                    # Pass the timestamp to both pit and lap recording functions
                    await self._check_and_record_pits(payload, timestamp)
                    await self._check_and_record_laps(payload, timestamp_str) # This was a missing call
                    
                    await self.state_manager.broadcast({"type": "TimingData", "data": payload})
                
                elif feed_name == "SessionInfo":
                    # This dedicated block for SessionInfo is correct.
                    circuit_short_name = payload.get("Meeting", {}).get("Circuit", {}).get("ShortName")
                    if circuit_short_name:
                        total_laps = GRAND_PRIX_LAPS.get(circuit_short_name, 0)
                        self.state_manager.state["LapCount"]["TotalLaps"] = total_laps
                    
                    self.state_manager.update_state(feed_name, payload)
                    await self.state_manager.broadcast({"type": feed_name, "data": payload})

                 # --- THIS IS THE ONLY CHANGE ---
                # This new block catches the buggy "LapCount" message from the live feed
                # and does absolutely nothing with it. This prevents it from falling
                # into the 'else' block below and corrupting our state.
                elif feed_name == "LapCount":
                    pass # Intentionally do nothing

                else:
                    self.state_manager.update_state(feed_name, payload)
                    if feed_name == "RaceControlMessages":
                        await self.state_manager.broadcast({
                            "type": "RaceControlMessages",
                            "data": payload
                        })
                    
                    elif feed_name == "TeamRadio":
                        for capture in payload.get("Captures", []):
                            await self.state_manager.broadcast({
                                "type": "NewTeamRadio",
                                "data": capture
                            })
                    
                    elif feed_name in ["SessionStatus", "WeatherData", "TimingAppData"]:
                        await self.state_manager.broadcast({
                            "type": feed_name,
                            "data": payload
                        })

    def _decode_and_decompress(self, data_to_process):
        """
        Decodes and decompresses data.
        It robustly handles data that is either a Base64 string or raw bytes.
        """
        try:
            binary_data = None
            if isinstance(data_to_process, str):
                # If it's a string, it needs to be decoded from Base64 first.
                binary_data = base64.b64decode(data_to_process)
            elif isinstance(data_to_process, bytes):
                # If it's already bytes, we can use it directly.
                binary_data = data_to_process
            else:
                return None

            # Decompress the raw binary data
            decompressed_bytes = zlib.decompress(binary_data, -zlib.MAX_WBITS)
            return json.loads(decompressed_bytes.decode('utf-8'))
        except Exception:
            # Fail silently if data is not valid for any reason
            return None