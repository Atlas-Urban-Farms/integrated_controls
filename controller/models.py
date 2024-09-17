from pydantic import BaseModel


class Pico(BaseModel):
    serial_number: str
    name: str | None
