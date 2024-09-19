import functools
import json
import multiprocessing
import threading
import time
import typing

from serial.tools.list_ports import comports

from controller.comm import (
    Command,
    CommandCode,
    NullTerminatedSerial,
    PicoInfo,
    Response,
)
from controller.models import GrowthProfile, Pico


class Controller:

    def __init__(self):
        import sqlite3

        self.conn = sqlite3.connect("controller.db", check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

        self.started: bool = False
        self.serials: dict[str, NullTerminatedSerial] = {}

        self.lock = multiprocessing.Lock()

        self.exceptions: list[Exception] = []

        self.cursor = self.conn.cursor()
        with self.lock:
            self.cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS units (
                    name TEXT UNIQUE, 
                    serial_number TEXT NOT NULL, 
                    growth_profile TEXT NOT NULL,
                    PRIMARY KEY (serial_number)
                ) 
                """
            )

            self.cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
                    serial_number TEXT NOT NULL, 
                    command_code TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(serial_number) REFERENCES units(serial_number)
                ) 
                """
            )

    def _send_command(
        self,
        cmd: Command,
        serial_number: str | None = None,
        ser: NullTerminatedSerial | None = None,
    ) -> Response:
        with self.lock:
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
        def attempt_open(device: str):
            try:
                return NullTerminatedSerial(device)
            except:
                return None

        used_ports = [ser for ser in self.serials.values()]

        new_ports = [
            x
            for x in [
                attempt_open(port.device)
                for port in comports()
                if port.device not in [x.name for x in used_ports]
            ]
            if x
        ]
        

        all_ports = used_ports + new_ports

        def scan_port_for_pico(
            ser: NullTerminatedSerial,
        ) -> tuple[str, NullTerminatedSerial, PicoInfo] | None:
            """
            Returns a tuple containing serial number, port, and PicoInfo if port has a Pico connected, else None.
            """

            resp = None

            try:
                resp = self._send_command(
                    cmd=Command(code=CommandCode.ConfirmIdentity), ser=ser
                )
            except Exception as e:
                self.exceptions.append(e)
            finally:
                if not resp:
                    ser.close()

            return (
                (resp.serial_number, ser, PicoInfo.model_validate(resp.data))
                if resp
                else None
            )

        picos = [
            pico for pico in [scan_port_for_pico(port) for port in all_ports] if pico
        ]

        new_picos = [pico for pico in picos if pico[0] not in self.serials.keys()]

        for pico in new_picos:
            self._send_command(Command(code=CommandCode.PlaySound), ser=pico[1])

        self.serials = {pico[0]: pico[1] for pico in picos}

        for pico in picos:
            with self.conn:
                with self.lock:
                    self.cursor.execute(
                        f"""
                        INSERT OR IGNORE INTO units (serial_number, growth_profile)
                        VALUES ('{pico[0]}', '{json.dumps({
                            "watering_interval": 43200,
                            "watering_time": 30,
                            "light_duration": 28800,

                        })}');
                        """
                    )

        return self.serials

    def connected_picos(self) -> list[Pico]:
        serial_numbers = list(self.serials.keys())

        with self.lock:
            results = self.cursor.execute(
                f"""
                SELECT * FROM units
                WHERE serial_number IN 
                ({", ".join(['"%s"' % x for x in serial_numbers])});
                """
            ).fetchall()

        return [Pico(**row) for row in results]

    def all_picos(self) -> list[Pico]:
        with self.lock:
            results = self.cursor.execute(
                f"""
                SELECT * FROM units;
                """
            ).fetchall()

        return [Pico(**row) for row in results]

    def change_pico_name(self, serial_number: str, name: str):
        with self.conn:
            with self.lock:
                self.cursor.execute(
                    """
                    UPDATE units
                    SET name = ?
                    WHERE serial_number = ?;
                    """,
                    (name, serial_number),
                )

    def change_pico_growth_profile(self, serial_number: str, profile: GrowthProfile):
        with self.conn:
            with self.lock:
                self.cursor.execute(
                    """
                    UPDATE units
                    SET growth_profile = ?
                    WHERE serial_number = ?;
                    """,
                    (profile.model_dump_json(), serial_number),
                )

    def start_water(self, serial_number: str, duration: int):
        self._send_command(
            serial_number=serial_number,
            cmd=Command(code=CommandCode.StartWater, data={"duration": duration}),
        )

    def start_light(self, serial_number: str, duration: int):
        self._send_command(
            serial_number=serial_number,
            cmd=Command(code=CommandCode.StartLight, data={"duration": duration}),
        )

    def play_sound(self, serial_number: str):
        self._send_command(
            serial_number=serial_number,
            cmd=Command(code=CommandCode.PlaySound),
        )

    epoch = 0

    def loop(self):
        self.refresh_picos()