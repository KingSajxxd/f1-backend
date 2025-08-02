from app.utils.helpers import deep_merge
import json

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
        try:
            # --- Pattern 1: Deep Merging Feeds ---
            if feed_name in ["TimingData", "TimingAppData", "TimingStats", "TopThree", "DriverList"]:
                if isinstance(new_data, dict):
                    # Use the corrected deep_merge from helpers
                    self.state[feed_name] = deep_merge(self.state.get(feed_name, {}), new_data)
                # Optional: You could log a warning here if the payload is not a dict
            
            # --- Pattern 2: Append-Only Feeds ---
            elif feed_name == "RaceControlMessages":
                # Ensure that new messages are always appended, regardless of payload structure.
                # If new_data is a dict containing 'Messages' (which is typically a list),
                # extend the existing list with those messages.
                if isinstance(new_data, dict) and "Messages" in new_data:
                    if isinstance(new_data["Messages"], list):
                        self.state[feed_name].extend(new_data["Messages"])
                    else:
                        # If 'Messages' key contains a single item, append it
                        self.state[feed_name].append(new_data["Messages"])
                # If new_data is directly a list of messages, extend the existing list
                elif isinstance(new_data, list):
                    self.state[feed_name].extend(new_data)
                # If new_data is a single message, append it
                else:
                    self.state[feed_name].append(new_data)
            
            # --- NEW: Pattern for TeamRadio (Append-Only) ---
            elif feed_name == "TeamRadio":
                # Ensure new team radio captures are always appended or extended
                captures_to_add = []
                if isinstance(new_data, dict) and "Captures" in new_data:
                    if isinstance(new_data["Captures"], list):
                        captures_to_add.extend(new_data["Captures"])
                    else:
                        captures_to_add.append(new_data["Captures"])
                elif isinstance(new_data, list):
                    captures_to_add.extend(new_data)
                else:
                    captures_to_add.append(new_data)
                
                self.state[feed_name].extend(captures_to_add)

            # --- Pattern 3: Simple Replacement Feeds ---
            else:
                self.state[feed_name] = new_data
        
        except Exception as e:
            # Silently catch potential errors during state updates to prevent crashes.
            # For production, you would want to log this error to a file.
            # print(f"Error updating state for feed '{feed_name}': {e}")
            pass

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