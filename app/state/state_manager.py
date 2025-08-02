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
                messages_to_process = []
                if isinstance(new_data, dict):
                    if "Messages" in new_data:
                        # Case 1: new_data is {'Messages': [...]} or {'Messages': {...}}
                        if isinstance(new_data["Messages"], list):
                            messages_to_process.extend(new_data["Messages"])
                        elif isinstance(new_data["Messages"], dict):
                            # If 'Messages' key contains a dictionary of messages (e.g., indexed by numbers)
                            messages_to_process.extend(new_data["Messages"].values())
                        else:
                            # If 'Messages' key contains a single message (not list/dict)
                            messages_to_process.append(new_data["Messages"])
                    else:
                        # Case 2: new_data is a dict like {'1': {...}, '2': {...}} (numeric keys directly)
                        # Assume values are the actual message dictionaries
                        messages_to_process.extend(new_data.values())
                elif isinstance(new_data, list):
                    # Case 3: new_data is directly a list of messages
                    messages_to_process.extend(new_data)
                else:
                    # Case 4: new_data is a single message dictionary
                    messages_to_process.append(new_data)

                # Append only valid message dictionaries that contain required fields
                for msg_item in messages_to_process:
                    if isinstance(msg_item, dict) and \
                       all(k in msg_item for k in ["Utc", "Category", "Message"]):
                        self.state[feed_name].append(msg_item)
                    # Optional: Add logging here for skipped invalid messages for debugging
                    # else:
                    #     print(f"DEBUG: Skipping invalid RaceControlMessage format: {msg_item}")
            
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