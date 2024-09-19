import datetime
import time

from pydantic import BaseModel


class Pico(BaseModel):
    serial_number: str
    name: str | None
    growth_profile: str


class GrowthProfile(BaseModel):
    light_start: datetime.time
    light_end: datetime.time
    watering_interval: int
    watering_time: int
