import datetime
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
import os


class Controller:
    def __init__(self):
        import sqlite3

        if not __package__:
            raise ValueError("must be in package")

        dirname = os.path.dirname(__package__)
        self.conn = sqlite3.connect(
            os.path.join(dirname, "controller.db"), check_same_thread=False
        )
        self.conn.row_factory = sqlite3.Row

        self.started: bool = False
        self.serials: dict[str, NullTerminatedSerial] = {}

        self.lock = multiprocessing.Lock()

        self.exceptions: list[Exception] = []

        self.cursor = self.conn.cursor()
        with self.lock:
            with self.conn:
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

            with self.conn:
                self.cursor.execute(
                    """
                    INSERT INTO events (serial_number, command_code) VALUES (?, ?)
                    """,
                    (serial_number, cmd.code.value),
                )

            return resp

    def refresh_picos(self):
        def attempt_open(device: str):
            try:
                return NullTerminatedSerial(device)
            except Exception as e:
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
            with self.lock:
                with self.conn:
                    self.cursor.execute(
                        f"""
                        INSERT OR IGNORE INTO units (serial_number, growth_profile)
                        VALUES ('{pico[0]}', '{json.dumps({
                            "watering_interval": 43200,
                            "watering_time": 30,
                            "light_start": "08:00",
                            "light_end": "16:00",
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

        return [Pico(**row, connected=True) for row in results]

    def all_picos(self) -> list[Pico]:
        with self.lock:
            results = self.cursor.execute(
                f"""
                SELECT * FROM units;
                """
            ).fetchall()

        return [
            Pico(**row, connected=row["serial_number"] in self.serials.keys())
            for row in results
        ]

    def change_pico_name(self, serial_number: str, name: str):
        with self.lock:
            with self.conn:
                results = self.cursor.execute(
                    """
                    UPDATE units
                    SET name = ?
                    WHERE serial_number = ?
                    RETURNING *;
                    """,
                    (name, serial_number),
                ).fetchall()
                data = {**results[0]}

                return Pico(
                    **data, connected=data["serial_number"] in self.serials.keys()
                )

    def change_pico_growth_profile(self, serial_number: str, profile: GrowthProfile):
        with self.lock:
            with self.conn:
                results = self.cursor.execute(
                    """
                    UPDATE units
                    SET growth_profile = ?
                    WHERE serial_number = ?
                    RETURNING *;
                    """,
                    (profile.model_dump_json(), serial_number),
                ).fetchall()

                data = {**results[0]}

                return Pico(
                    **data, connected=data["serial_number"] in self.serials.keys()
                )

    def start_water(self, serial_number: str, duration: int):
        """start water for the specified number of milliseconds"""
        self._send_command(
            serial_number=serial_number,
            cmd=Command(code=CommandCode.StartWater, data={"duration": duration}),
        )

    def start_light(self, serial_number: str, duration: int):
        """start light for the specified number of milliseconds"""
        self._send_command(
            serial_number=serial_number,
            cmd=Command(code=CommandCode.StartLight, data={"duration": duration}),
        )

    def play_sound(self, serial_number: str):
        self._send_command(
            serial_number=serial_number,
            cmd=Command(code=CommandCode.PlaySound),
        )

    def get_unit(self, serial_number: str) -> GrowthProfile:
        results = self.cursor.execute(
            """
            SELECT * FROM units WHERE serial_number = ?;
            """,
            (serial_number,),
        ).fetchall()

        return GrowthProfile.model_validate_json(results[0]["growth_profile"])

    def get_last_watered(self, serial_number: str) -> float | None:
        results = self.cursor.execute(
            """
            SELECT CAST(strftime('%s', timestamp) AS INT) as timestamp FROM events WHERE serial_number = ? and command_code = ? ORDER BY timestamp DESC LIMIT 1;
            """,
            (serial_number, CommandCode.StartWater.value),
        ).fetchall()

        if len(results) > 0:
            return float(results[0]["timestamp"])

        return None

    epoch = 0

    def loop(self):
        self.refresh_picos()

        for serial_number, ser in self.serials.items():
            growth_profile = self.get_unit(serial_number)

            now = time.time()
            timestamp = datetime.datetime.now().time()

            if growth_profile.light_end >= timestamp >= growth_profile.light_start:
                self.start_light(serial_number, 10000)

            last_watered = self.get_last_watered(serial_number)

            if (
                not last_watered
                or last_watered + growth_profile.watering_interval > now
            ):
                self.start_water(serial_number, growth_profile.watering_time * 1000)
