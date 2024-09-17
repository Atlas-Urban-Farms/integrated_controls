import time
import typing
from enum import Enum

import serial
import serial.tools
import serial.tools.list_ports_common
from nanoid import generate
from pydantic import BaseModel, Field
from typing_extensions import Buffer

from controller.models import Pico

PICO_SERIAL_PREFIX = "USB"


class CommandCode(Enum):
    ConfirmIdentity = "CC1"
    StartWater = "CC2"
    EndWater = "CC3"
    StartLight = "CC4"
    EndLight = "CC5"
    PlaySound = "CC6"


class Command(BaseModel):
    code: CommandCode
    id: str = Field(default_factory=generate)
    data: typing.Dict[str, typing.Any] | None = None

    def bytes(self) -> bytes:
        return self.model_dump_json().encode()


class Response(BaseModel):
    serial_number: str
    command_id: str
    data: typing.Dict[str, typing.Any] | None = None
    error: str | None = None


class PicoInfo(BaseModel):
    used_memory: int
    free_memory: int
    total_memory: int


class NullTerminatedSerial(serial.Serial):
    def write(self, b: Buffer) -> int | None:
        """
        Output the given byte string over the serial port.

        Appends an additional null character at the end.
        """
        bytes = bytearray(b)
        bytes.append(0)
        return super().write(b)

    def read_until_null(self, size: int | None = None):
        """
        Read until null, the size is exceeded or until timeout occurs.
        """
        resp = self.read_until("\0".encode(), size)

        return resp[:-1]
