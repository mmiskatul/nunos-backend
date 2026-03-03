from pydantic import BaseModel


class LocationPreferenceUpdate(BaseModel):
    enable_location: bool

