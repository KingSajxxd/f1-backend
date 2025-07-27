from app.utils.helpers import deep_merge
import json
import logging # Import logging module

# Configure logging (optional, but good practice for persistent logs)
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class StateManager:
    """
    Manages the live state of the application.
    This is the single source of truth for all F1 data.
    """
    def __init__(self):
        self.state = {
            "DriverList": {},
            "TimingData": {},
            "TimingStats": {},
            "TimingAppData": {},
            "CarData": {},
            "PositionData": {},
            "RaceControlMessages": [],
            "TeamRadio": [],
            "SessionInfo": {},
            "TrackStatus": {},
            "WeatherData": {},
            "LapCount": {"CurrentLap": 0, "TotalLaps": 0},
            "LapHistory": [],
            "PitHistory": [],
            "DriversInPits": {}
        }
        self.clients = []
        print("State Manager initialized.")

    def update_state(self, feed_name, new_data):
        """
        Main method to update state based on the feed type.
        """
        try: # Keep the try block
            # --- Pattern 1: Deep Merging Feeds ---
            if feed_name in ["TimingData", "TimingAppData", "TimingStats", "TopThree", "DriverList"]:
                if isinstance(new_data, dict):
                    self.state[feed_name] = deep_merge(self.state.get(feed_name, {}), new_data)
            
            # --- Pattern 2: Specific handling for RaceControlMessages (replace) and TeamRadio (append) ---
            elif feed_name == "RaceControlMessages":
                key = "Messages"
                if isinstance(new_data, dict) and key in new_data:
                    self.state[feed_name] = new_data[key]
                else:
                    self.state[feed_name].append(new_data)
            elif feed_name == "TeamRadio":
                key = "Captures"
                if isinstance(new_data, dict) and key in new_data:
                    self.state[feed_name].extend(new_data[key])
                else:
                    self.state[feed_name].append(new_data)

            # --- Pattern 3: Simple Replacement Feeds ---
            else:
                self.state[feed_name] = new_data
        
        except Exception as e:
            # MODIFIED: Print the error to console for debugging
            print(f"ERROR: Failed to update state for feed '{feed_name}'. Data: {new_data}. Error: {e}")
            # Consider using logging.error for production logs with traceback:
            # logging.error(f"Failed to update state for feed '{feed_name}'. Data: {new_data}", exc_info=True)


    def get_full_state(self):
        """Returns the entire current state."""
        return self.state
    
    def add_lap_to_history(self, lap_data):
        """Appends a newly completed lap object to the history."""
        self.state["LapHistory"].append(lap_data)

    def add_pit_stop_to_history(self, pit_data):
        """Appends a newly completed pit stop object to the history."""
        self.state["PitHistory"].append(pit_data)
    
    def add_client(self, websocket):
        self.clients.append(websocket)

    def remove_client(self, websocket):
        self.clients.remove(websocket)

    async def broadcast(self, data):
        # Convert dictionary to JSON string before sending
        json_message = json.dumps(data)
        for client in self.clients:
            await client.send_text(json_message)