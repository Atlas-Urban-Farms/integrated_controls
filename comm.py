import time
import typing
from enum import Enum

import serial
import serial.tools
import serial.tools.list_ports_common
from _typeshed import ReadableBuffer
from nanoid import generate
from pydantic import BaseModel, Field, Json
from serial.tools.list_ports import comports
from typing_extensions import Buffer

PICO_SERIAL_PREFIX = "USB"


class CommandCode(Enum):
    ConfirmIdentity = "CC1"
    StartWater = "CC2"
    EndWater = "CC3"
    StartLight = "CC4"
    EndLight = "CC5"


class Command(BaseModel):
    code: CommandCode
    id: str = Field(default_factory=generate)
    data: Json | None = None

    def bytes(self) -> bytes:
        return self.model_dump_json().encode()


class Response(BaseModel):
    serial_number: str
    command_id: str
    data: Json | None = None


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
        return self.read_until("\0".encode(), size)


class Controller:
    picos: dict[str, NullTerminatedSerial]
    """serial number to port device"""

    def __init__(self):
        pass

    def send_command(self, serial_number: str, cmd: Command) -> Response:
        ser = self.picos[serial_number]

        ser.write(cmd.bytes())

        output = ser.read_until_null().decode()

        resp = Response.model_validate_json(output)

        return resp

    def discover_picos(
        self,
    ):
        ports = comports()
        picos = [
            x for x in [self.scan_port_for_pico(port.device) for port in ports] if x
        ]

        picos = {pico[0]: pico[1] for pico in picos}

        return self.picos

    def scan_port_for_pico(self, port: str) -> tuple[str, NullTerminatedSerial] | None:
        """
        Returns a NullTerminatedSerial session if port has a Pico connected, else None.
        """
        ser = NullTerminatedSerial(port=port, baudrate=115200, timeout=2)

        cmd = Command(code=CommandCode.ConfirmIdentity)

        ser.write(cmd.bytes())

        output = ser.read_until_null().decode()

        resp = Response.model_validate_json(output)

        return (resp.serial_number, ser) if resp.command_id == cmd.id else None
