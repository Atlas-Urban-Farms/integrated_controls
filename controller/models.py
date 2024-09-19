from pydantic import BaseModel


class Pico(BaseModel):
    serial_number: str
    name: str | None
    growth_profile: str

class GrowthProfile(BaseModel):
    light_duration: int
    watering_interval: int
    watering_time: int