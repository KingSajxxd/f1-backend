import json
from fastapi import FastAPI, Depends, WebSocket, WebSocketDisconnect
from app.utils.helpers import DateTimeEncoder
from typing import List
from datetime import datetime, timezone
from .models import CarData, Driver, Interval, Lap, LeaderboardDriver, Location, Meeting, Pit, Position, RaceControl, Session, Stint, TeamRadio, Weather  # Import our Pydantic model
from ..utils.helpers import safe_to_float, time_string_to_seconds

# This is a placeholder for our StateManager dependency
# We will "inject" the real one when we run the app
def get_state_manager():
    # In a real app, this would be handled by a more robust
    # dependency injection system. For now, this is a placeholder.
    pass 

app = FastAPI()

@app.get("/ping")
def ping():
    return {"status": "ok"}

@app.get("/api/drivers", response_model=List[Driver])
async def get_drivers(state_manager = Depends(get_state_manager)):
    """
    Gets the driver list from our internal state and transforms
    it into the structure the frontend expects.
    """
    driver_list_internal = state_manager.state.get("DriverList", {})
    
    # The transformation happens here!
    drivers_transformed = []
    for driver_number, driver_data in driver_list_internal.items():
        if not isinstance(driver_data, dict): continue # Skip _kf=true
        
        # FastAPI will automatically handle mapping the fields
        # based on our Pydantic model definition
        drivers_transformed.append(Driver.from_orm(driver_data))

    return drivers_transformed

@app.get("/api/cardata", response_model=List[CarData])
async def get_cardata(state_manager=Depends(get_state_manager)):
    """
    Gets the latest car telemetry data, combines it with session info,
    and transforms it into the structure the frontend expects.
    """
    # 1. Get the data feeds we need from the state
    car_data_feed = state_manager.state.get("CarData", {})
    session_info = state_manager.state.get("SessionInfo", {})

    # 2. Extract the session and meeting keys once
    session_key = session_info.get("Key")
    meeting_key = session_info.get("Meeting", {}).get("Key")
    
    # 3. Extract the most recent telemetry snapshot
    if not car_data_feed or not car_data_feed.get("Entries"):
        return []

    latest_snapshot = car_data_feed["Entries"][-1]
    
    # 4. Loop through each car and transform the data
    cardata_transformed = []
    for driver_number, telemetry in latest_snapshot["Cars"].items():
        channels = telemetry.get("Channels", {})
        
        transformed_entry = CarData(
            date=latest_snapshot["Utc"],
            driver_number=int(driver_number),
            rpm=channels.get("0", 0),
            speed=channels.get("2", 0),
            n_gear=channels.get("3", 0),
            throttle=channels.get("4", 0),
            brake=100 if channels.get("5", 0) == 1 else 0,
            drs=channels.get("45", 0),
            # --- ADD THE NEW KEYS TO THE RESPONSE ---
            session_key=session_key,
            meeting_key=meeting_key
        )
        cardata_transformed.append(transformed_entry)

    return cardata_transformed

@app.get("/api/intervals", response_model=List[Interval])
async def get_intervals(state_manager=Depends(get_state_manager)):
    """
    Gets the latest interval and gap data for all drivers.
    """
    # 1. Get the data feeds we need from the state
    timing_data = state_manager.state.get("TimingData", {})
    session_info = state_manager.state.get("SessionInfo", {})

    # 2. Extract session and meeting keys
    session_key = session_info.get("Key")
    meeting_key = session_info.get("Meeting", {}).get("Key")
    
    # 3. Loop through each driver in TimingData and transform
    intervals_transformed = []
    if "Lines" in timing_data:
        for driver_number, driver_data in timing_data["Lines"].items():
            
            # Use our helper to safely convert string gaps to floats
            gap_to_leader_str = driver_data.get("GapToLeader")
            interval_str = driver_data.get("IntervalToPositionAhead", {}).get("Value")

            transformed_entry = Interval(
                date=datetime.now().isoformat(), # Use current time for the 'live' interval
                driver_number=int(driver_number),
                gap_to_leader=safe_to_float(gap_to_leader_str),
                interval=safe_to_float(interval_str),
                meeting_key=meeting_key,
                session_key=session_key
            )
            intervals_transformed.append(transformed_entry)

    return intervals_transformed

@app.get("/api/laps", response_model=List[Lap])
async def get_laps(state_manager=Depends(get_state_manager)):
    """
    Returns the historical list of all completed laps.
    """
    # This is simple because our processor now does the hard work of building the history
    lap_history = state_manager.state.get("LapHistory", [])
    return lap_history

@app.get("/api/location", response_model=List[Location])
async def get_locations(state_manager=Depends(get_state_manager)):
    """
    Gets the latest location data for all drivers.
    """
    # 1. Get the data from the state
    position_data = state_manager.state.get("Position", {})
    session_info = state_manager.state.get("SessionInfo", {})

    # 2. Get session and meeting keys
    session_key = session_info.get("Key")
    meeting_key = session_info.get("Meeting", {}).get("Key")

    # 3. Get the most recent position snapshot
    if not position_data or not position_data.get("Position"):
        return []
    latest_snapshot = position_data["Position"][-1]
    
    # 4. Loop through cars and transform data
    locations_transformed = []
    for driver_number, driver_pos_data in latest_snapshot["Entries"].items():
        transformed_entry = Location(
            date=latest_snapshot["Timestamp"],
            driver_number=int(driver_number),
            x=driver_pos_data["X"],
            y=driver_pos_data["Y"],
            z=driver_pos_data["Z"],
            session_key=session_key,
            meeting_key=meeting_key
        )
        locations_transformed.append(transformed_entry)
        
    return locations_transformed

@app.get("/api/meetings", response_model=List[Meeting])
async def get_meeting(state_manager=Depends(get_state_manager)):
    """
    Gets the current meeting info from the SessionInfo state
    and transforms it into the desired structure.
    """
    session_info = state_manager.state.get("SessionInfo", {})
    if not session_info:
        return []

    meeting_info = session_info.get("Meeting", {})
    country_info = meeting_info.get("Country", {})
    circuit_info = meeting_info.get("Circuit", {})
    
    # Flatten the nested data from SessionInfo into the Meeting model
    transformed_meeting = Meeting(
        circuit_key=circuit_info.get("Key"),
        circuit_short_name=circuit_info.get("ShortName"),
        country_code=country_info.get("Code"),
        country_key=country_info.get("Key"),
        country_name=country_info.get("Name"),
        date_start=session_info.get("StartDate"),
        gmt_offset=session_info.get("GmtOffset"),
        location=meeting_info.get("Location"),
        meeting_key=meeting_info.get("Key"),
        meeting_name=meeting_info.get("Name"),
        meeting_official_name=meeting_info.get("OfficialName"),
        year=datetime.fromisoformat(session_info["StartDate"]).year if session_info.get("StartDate") else None
    )

    # The target structure is a list, so we return our single object in a list
    return [transformed_meeting]

@app.get("/api/pit", response_model=List[Pit])
async def get_pit_stops(state_manager=Depends(get_state_manager)):
    """
    Returns the historical list of all completed pit stops.
    """
    return state_manager.state.get("PitHistory", [])

@app.get("/api/position", response_model=List[Position])
async def get_positions(state_manager=Depends(get_state_manager)):
    """
    Gets the current race position for all drivers.
    """
    timing_data = state_manager.state.get("TimingData", {})
    session_info = state_manager.state.get("SessionInfo", {})

    session_key = session_info.get("Key")
    meeting_key = session_info.get("Meeting", {}).get("Key")

    positions_transformed = []
    if "Lines" in timing_data:
        for driver_number, driver_data in timing_data["Lines"].items():
            current_position = driver_data.get("Position")
            if not current_position: continue

            transformed_entry = Position(
                date=datetime.now(timezone.utc).isoformat(),
                driver_number=int(driver_number),
                position=int(current_position),
                meeting_key=meeting_key,
                session_key=session_key
            )
            positions_transformed.append(transformed_entry)
            
    return sorted(positions_transformed, key=lambda p: p.position)

@app.get("/api/racecontrol", response_model=List[RaceControl])
async def get_race_control(state_manager=Depends(get_state_manager)):
    """Returns the list of all race control messages."""
    messages = state_manager.state.get("RaceControlMessages", [])
    session_info = state_manager.state.get("SessionInfo", {})
    session_key = session_info.get("Key")
    meeting_key = session_info.get("Meeting", {}).get("Key")

    transformed_messages = []
    for msg in messages:
        if isinstance(msg, dict):
            # Add the keys that are not in the source message
            msg["session_key"] = session_key
            msg["meeting_key"] = meeting_key
            
            # The model now handles the rest of the mapping automatically
            transformed_messages.append(RaceControl.model_validate(msg))
            
    return transformed_messages

@app.get("/api/sessions", response_model=List[Session])
async def get_sessions(state_manager=Depends(get_state_manager)):
    """Returns the current session info."""
    session_info = state_manager.state.get("SessionInfo", {})
    if not session_info: return []

    meeting_info = session_info.get("Meeting", {})
    country_info = meeting_info.get("Country", {})
    circuit_info = meeting_info.get("Circuit", {})
    
    start_date = session_info.get("StartDate")
    
    transformed_session = Session(
        circuit_key=circuit_info.get("Key"),
        circuit_short_name=circuit_info.get("ShortName"),
        country_code=country_info.get("Code"),
        country_key=country_info.get("Key"),
        country_name=country_info.get("Name"),
        date_end=session_info.get("EndDate"),
        date_start=start_date,
        gmt_offset=session_info.get("GmtOffset"),
        location=meeting_info.get("Location"),
        meeting_key=meeting_info.get("Key"),
        session_key=session_info.get("Key"),
        session_name=session_info.get("Name"),
        session_type=session_info.get("Type"),
        year=datetime.fromisoformat(start_date).year if start_date else None
    )
    return [transformed_session]

# There should be another one called Stints and this is will be done later
@app.get("/api/stints", response_model=List[Stint])
async def get_stints(state_manager=Depends(get_state_manager)):
    """
    Gets the list of all tyre stints for all drivers.
    """
    # 1. Get the data we need from the state
    timing_app_data = state_manager.state.get("TimingAppData", {})
    session_info = state_manager.state.get("SessionInfo", {})

    # 2. Get session and meeting keys
    session_key = session_info.get("Key")
    meeting_key = session_info.get("Meeting", {}).get("Key")

    stints_transformed = []
    if "Lines" in timing_app_data:
        # Loop through each driver
        for driver_number, driver_app_data in timing_app_data["Lines"].items():
            stints_data_source = driver_app_data.get("Stints", [])

            # FIX: Handle both list and dictionary formats for Stints data
            stints_to_process = []
            if isinstance(stints_data_source, list):
                stints_to_process = stints_data_source
            elif isinstance(stints_data_source, dict):
                stints_to_process = list(stints_data_source.values())
            
            # Loop through each stint for the current driver
            for i, stint_data in enumerate(stints_to_process, 1): # Use enumerate to get the stint_number
                if not isinstance(stint_data, dict): continue

                # Add the extra data needed for the transformation
                stint_data["driver_number"] = int(driver_number)
                stint_data["stint_number"] = i
                stint_data["session_key"] = session_key
                stint_data["meeting_key"] = meeting_key

                # Create the model instance from our prepared dictionary
                stint_model = Stint.model_validate(stint_data)
                stints_transformed.append(stint_model)

    return stints_transformed

@app.get("/api/teamradio", response_model=List[TeamRadio])
async def get_team_radio(state_manager=Depends(get_state_manager)):
    """Returns the list of all captured team radio messages."""
    radio_captures = state_manager.state.get("TeamRadio", [])
    session_info = state_manager.state.get("SessionInfo", {})
    
    session_key = session_info.get("Key")
    meeting_key = session_info.get("Meeting", {}).get("Key")
    # --- THIS IS THE KEY ---
    # Get the session path from the SessionInfo object
    session_path = session_info.get("Path", "")

    transformed_radios = []
    for radio in radio_captures:
        if isinstance(radio, dict) and radio.get("Path"):
            
            # --- THIS IS THE FIX ---
            # Construct the new, full URL using the session_path
            full_url = f"https://livetiming.formula1.com/static/{session_path}{radio.get('Path')}"
            
            # Add the new fields to the source dictionary before validating
            radio["recording_url"] = full_url
            radio["session_key"] = session_key
            radio["meeting_key"] = meeting_key

            radio_model = TeamRadio.model_validate(radio)
            transformed_radios.append(radio_model)

    return transformed_radios

@app.get("/api/weather", response_model=List[Weather])
async def get_weather(state_manager=Depends(get_state_manager)):
    """Returns the latest weather data."""
    weather_data = state_manager.state.get("WeatherData", {})
    if not weather_data: return []

    session_info = state_manager.state.get("SessionInfo", {})
    
    # Add the missing keys to the weather data before validating
    weather_data["session_key"] = session_info.get("Key")
    weather_data["meeting_key"] = session_info.get("Meeting", {}).get("Key")
    weather_data["date"] = datetime.now(timezone.utc).isoformat()
    
    transformed_weather = Weather.model_validate(weather_data)
    
    return [transformed_weather]

@app.get("/api/leaderboard", response_model=List[LeaderboardDriver])
async def get_leaderboard(state_manager=Depends(get_state_manager)):
    """
    Combines data from multiple feeds to construct a full leaderboard object.
    This is the final, corrected version.
    """
    timing_data = state_manager.state.get("TimingData", {}).get("Lines", {})
    app_data = state_manager.state.get("TimingAppData", {}).get("Lines", {})
    driver_list = state_manager.state.get("DriverList", {})
    lap_history = state_manager.state.get("LapHistory", [])

    if not timing_data or not driver_list:
        return []

    leaderboard_entries = []
    for driver_number_str, driver_timing in timing_data.items():
        driver_info = driver_list.get(driver_number_str, {})
        driver_app_data = app_data.get(driver_number_str, {})
        driver_number = int(driver_number_str)

        # 1. Get Last Lap Time from History
        last_lap_for_driver = next((lap for lap in reversed(lap_history) if lap.get("driver_number") == driver_number), None)
        last_lap_time_val = last_lap_for_driver.get("lap_duration") if last_lap_for_driver else None
        
        # 2. Get Interval and set to null for the leader
        interval_val = driver_timing.get("IntervalToPositionAhead", {}).get("Value")
        if driver_timing.get("Position") == "1":
            interval_val = None # This ensures the leader has no interval

        # 3. Get Tyre and Sector data
        current_tyre = None
        stints = driver_app_data.get("Stints")
        if isinstance(stints, list) and stints:
            current_tyre = stints[-1].get("Compound")
        elif isinstance(stints, dict) and stints:
            last_stint_key = sorted(stints.keys(), key=int)[-1]
            current_tyre = stints[last_stint_key].get("Compound")

        sector_times = [None, None, None]
        sectors = driver_timing.get("Sectors", {})
        if isinstance(sectors, dict):
            sector_times[0] = time_string_to_seconds(sectors.get("0", {}).get("Value"))
            sector_times[1] = time_string_to_seconds(sectors.get("1", {}).get("Value"))
            sector_times[2] = time_string_to_seconds(sectors.get("2", {}).get("Value"))
        elif isinstance(sectors, list):
            if len(sectors) > 0: sector_times[0] = time_string_to_seconds(sectors[0].get("Value"))
            if len(sectors) > 1: sector_times[1] = time_string_to_seconds(sectors[1].get("Value"))
            if len(sectors) > 2: sector_times[2] = time_string_to_seconds(sectors[2].get("Value"))

        # 4. Assemble the final object
        entry = LeaderboardDriver(
            position=int(driver_timing.get("Position", 99)),
            name=driver_info.get("FullName", "Unknown"),
            shortName=driver_info.get("Tla", "N/A"),
            driverNumber=driver_number,
            team=driver_info.get("TeamName", "N/A"),
            teamColor=driver_info.get("TeamColour"),
            headshotUrl=driver_info.get("HeadshotUrl"),
            lastLapTime=last_lap_time_val,
            gapToLeader=driver_timing.get("GapToLeader"),
            interval=interval_val,
            tyre=current_tyre,
            sectorTimes=sector_times,
        )
        leaderboard_entries.append(entry)

    leaderboard_entries.sort(key=lambda d: d.position)
    return leaderboard_entries

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, state_manager=Depends(get_state_manager)):
    await websocket.accept()
    state_manager.add_client(websocket)

    # --- THIS IS THE CRITICAL FIX ---
    # Immediately send the complete current state to the newly connected client.
    # This ensures the app is instantly up-to-date.
    print("Client connected. Sending full initial state...")
    full_state = state_manager.get_full_state()
    await websocket.send_text(json.dumps(full_state, cls=DateTimeEncoder))
    # --------------------------------

    try:
        while True:
            # Keep the connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        state_manager.remove_client(websocket)
        print("Client disconnected.")