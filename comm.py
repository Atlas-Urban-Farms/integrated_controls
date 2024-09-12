import time
import typing
from enum import Enum

import serial
import serial.tools
import serial.tools.list_ports_common
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
    data: typing.Dict[str, typing.Any] | None = None

    def bytes(self) -> bytes:
        return self.model_dump_json().encode()


class Response(BaseModel):
    serial_number: str
    command_id: str
    data: typing.Dict[str, typing.Any] | None = None


class PicoInfo(BaseModel):
    serial_number: str
    name: str
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


class Controller:
    serials: dict[str, NullTerminatedSerial]
    """serial number to port device"""
    infos: dict[str, PicoInfo]
    """serial number to PicoInfo"""

    def __init__(self):
        self.serials = {}
        self.infos = {}

    def send_command(
        self,
        cmd: Command,
        serial_number: str | None = None,
        ser: NullTerminatedSerial | None = None,
    ) -> Response:
        if not ser:
            if not serial_number:
                raise ValueError(
                    "must specify either serial_number or NullTerminatedSerial instance"
                )

            ser = self.serials[serial_number]

        ser.write(cmd.bytes())

        output = ser.read_until_null().decode()

        resp = Response.model_validate_json(output)

        return resp

    def refresh_picos(self):
        used_ports = [ser.name for ser in self.serials.values()]

        new_ports = [port for port in comports() if port.device not in used_ports]

        new_sers = [NullTerminatedSerial(port.device) for port in new_ports]
        all_sers = new_sers + list(self.serials.values())

        def scan_port_for_pico(
            ser: NullTerminatedSerial,
        ) -> tuple[str, NullTerminatedSerial, PicoInfo] | None:
            """
            Returns a NullTerminatedSerial session if port has a Pico connected, else None.
            """

            try:
                resp = None
                resp = self.send_command(
                    cmd=Command(code=CommandCode.ConfirmIdentity), ser=ser
                )
            except Exception as e:
                print(e)
            finally:
                if not resp:
                    ser.close()

            return (
                (resp.serial_number, ser, PicoInfo.model_validate(resp.data))
                if resp
                else None
            )

        picos = [pico for pico in [scan_port_for_pico(ser) for ser in all_sers] if pico]

        self.serials = {pico[0]: pico[1] for pico in picos}
        self.infos = {pico[0]: pico[2] for pico in picos}

        return self.serials
