from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional

# This class defines the structure for a single driver
class Driver(BaseModel):
    """
    Defines the data structure for the /api/drivers endpoint.
    Uses validation_alias to map from our internal PascalCase names
    to the desired snake_case output names.
    """
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )

    # Map all the fields from our internal data to the desired output names
    broadcast_name: str = Field(validation_alias="BroadcastName")
    country_code: Optional[str] = None # We don't have this, so it remains optional
    driver_number: int = Field(validation_alias="RacingNumber")
    first_name: Optional[str] = Field(validation_alias="FirstName")
    full_name: str = Field(validation_alias="FullName")
    headshot_url: Optional[str] = Field(default=None, validation_alias="HeadshotUrl")
    last_name: Optional[str] = Field(validation_alias="LastName")
    name_acronym: str = Field(validation_alias="Tla")
    team_colour: Optional[str] = Field(validation_alias="TeamColour")
    team_name: Optional[str] = Field(validation_alias="TeamName")
    
class CarData(BaseModel):
    """
    Defines the data structure for the /api/cardata endpoint.
    """
    model_config = ConfigDict(from_attributes=True)

    brake: int
    date: str
    driver_number: int
    drs: int
    # --- ADD THESE TWO LINES ---
    meeting_key: Optional[int] = None
    session_key: Optional[int] = None
    # ---------------------------
    n_gear: int
    rpm: int
    speed: int
    throttle: int

class Interval(BaseModel):
    """
    Defines the data structure for the /api/intervals endpoint.
    """
    date: str
    driver_number: int
    gap_to_leader: Optional[float] = None
    interval: Optional[float] = None
    meeting_key: Optional[int] = None
    session_key: Optional[int] = None

class Lap(BaseModel):
    """
    Defines the structure for a single completed lap record.
    """
    model_config = ConfigDict(from_attributes=True)
    
    date_start: Optional[str] = None
    driver_number: int
    duration_sector_1: Optional[float] = None
    duration_sector_2: Optional[float] = None
    duration_sector_3: Optional[float] = None
    i1_speed: Optional[str] = None # Keeping as string as source is string
    i2_speed: Optional[str] = None
    st_speed: Optional[str] = None
    is_pit_out_lap: Optional[bool] = False
    lap_duration: Optional[float] = None
    lap_number: int
    meeting_key: Optional[int] = None
    # We will skip segments for now as they are complex to store historically
    # segments_sector_1: Optional[List[int]] = [] 
    session_key: Optional[int] = None

class Location(BaseModel):
    """
    Defines the data structure for the /api/location endpoint.
    """
    model_config = ConfigDict(from_attributes=True)

    date: str
    driver_number: int
    meeting_key: Optional[int] = None
    session_key: Optional[int] = None
    x: int
    y: int
    z: int

class Meeting(BaseModel):
    """
    Defines the data structure for the /api/meetings endpoint.
    """
    circuit_key: Optional[int] = None
    circuit_short_name: Optional[str] = None
    country_code: Optional[str] = None
    country_key: Optional[int] = None
    country_name: Optional[str] = None
    date_start: Optional[str] = None
    gmt_offset: Optional[str] = None
    location: Optional[str] = None
    meeting_key: Optional[int] = None
    meeting_name: Optional[str] = None
    meeting_official_name: Optional[str] = None
    year: Optional[int] = None

class Pit(BaseModel):
    """
    Defines the structure for a single pit stop record.
    """
    date: str
    driver_number: int
    lap_number: int
    meeting_key: Optional[int] = None
    pit_duration: Optional[float] = None
    session_key: Optional[int] = None

class Position(BaseModel):
    """
    Defines the data structure for the /api/position endpoint.
    """
    date: str
    driver_number: int
    position: int
    meeting_key: Optional[int] = None
    session_key: Optional[int] = None

class RaceControl(BaseModel):
    """Defines the structure for the /api/racecontrol endpoint."""
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    # Required fields that are always present
    category: str = Field(validation_alias="Category")
    date: str = Field(validation_alias="Utc")
    message: str = Field(validation_alias="Message")
    
    # Optional fields that might be missing entirely from some messages
    driver_number: Optional[int] = Field(default=None)
    flag: Optional[str] = Field(default=None, validation_alias="Flag")
    lap_number: Optional[int] = Field(default=None, validation_alias="Lap")
    scope: Optional[str] = Field(default=None, validation_alias="Scope")
    sector: Optional[int] = Field(default=None, validation_alias="Sector")
    
    # Keys we add manually
    meeting_key: Optional[int] = None
    session_key: Optional[int] = None

class Session(BaseModel):
    """Defines the structure for the /api/sessions endpoint."""
    circuit_key: Optional[int] = None
    circuit_short_name: Optional[str] = None
    country_code: Optional[str] = None
    country_key: Optional[int] = None
    country_name: Optional[str] = None
    date_end: Optional[str] = None
    date_start: Optional[str] = None
    gmt_offset: Optional[str] = None
    location: Optional[str] = None
    meeting_key: Optional[int] = None
    session_key: Optional[int] = None
    session_name: Optional[str] = None
    session_type: Optional[str] = None
    year: Optional[int] = None

# there should be antoher one called Stints which will be done later
class Stint(BaseModel):
    """
    Defines the data structure for the /api/stints endpoint.
    """
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    compound: Optional[str] = Field(default=None, validation_alias="Compound")
    driver_number: int
    lap_end: Optional[int] = Field(default=None, validation_alias="TotalLaps") # We can use TotalLaps for now
    lap_start: int = Field(validation_alias="StartLaps")
    meeting_key: Optional[int] = None
    session_key: Optional[int] = None
    stint_number: int
    tyre_age_at_start: Optional[int] = None # We don't have this data

class TeamRadio(BaseModel):
    """Defines the structure for the /api/teamradio endpoint."""
    date: str = Field(validation_alias="Utc")
    driver_number: int = Field(validation_alias="RacingNumber")
    meeting_key: Optional[int] = None
    recording_url: str # We will construct this field manually
    session_key: Optional[int] = None

class Weather(BaseModel):
    """Defines the structure for the /api/weather endpoint."""
    air_temperature: float = Field(validation_alias="AirTemp")
    date: str
    humidity: float = Field(validation_alias="Humidity")
    meeting_key: Optional[int] = None
    pressure: float = Field(validation_alias="Pressure")
    rainfall: int = Field(validation_alias="Rainfall")
    session_key: Optional[int] = None
    track_temperature: float = Field(validation_alias="TrackTemp")
    wind_direction: int = Field(validation_alias="WindDirection")
    wind_speed: float = Field(validation_alias="WindSpeed")

class LeaderboardDriver(BaseModel):
    """
    Defines the combined data structure for the /api/leaderboard endpoint.
    """
    position: int
    name: str
    shortName: str
    driverNumber: int
    team: str
    teamColor: Optional[str] = None
    headshotUrl: Optional[str] = None
    lastLapTime: Optional[float] = None
    gapToLeader: Optional[str] = None # Can be a time string or "LAP X"
    interval: Optional[str] = None
    hasFastestLap: bool = False # We will default this to False for now
    tyre: Optional[str] = None
    sectorTimes: List[Optional[float]] = []