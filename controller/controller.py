from serial.tools.list_ports import comports

from controller.comm import (
    Command,
    CommandCode,
    NullTerminatedSerial,
    PicoInfo,
    Response,
)
from controller.models import Pico


class Controller:
    def __init__(self):
        import sqlite3

        self.serials: dict[str, NullTerminatedSerial] = {}
        """serial number to port device"""

        self.conn = sqlite3.connect("controller.db")
        self.conn.row_factory = sqlite3.Row

        self.cursor = self.conn.cursor()
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

        new_picos = [pico for pico in picos if pico[0] not in self.serials.keys()]

        for pico in new_picos:
            self.send_command(Command(code=CommandCode.PlaySound), ser=pico[1])

        self.serials = {pico[0]: pico[1] for pico in picos}

        for pico in picos:
            with self.conn:
                self.cursor.execute(
                    f"""
                    INSERT OR IGNORE INTO units (serial_number, growth_profile)
                    VALUES ('{pico[0]}', '{{}}');
                    """
                )

        return self.serials

    def connected_picos(self) -> list[Pico]:
        serial_numbers = list(self.serials.keys())

        results = self.cursor.execute(
            f"""
            SELECT * FROM units
            WHERE serial_number IN 
            ({", ".join(['"%s"' % x for x in serial_numbers])});
            """
        ).fetchall()

        return [Pico(**row) for row in results]

    def change_pico_name(self, serial_number: str, name: str):
        with self.conn:
            self.cursor.execute(
                """
                UPDATE units
                SET name = ?
                WHERE serial_number = ?;
                """,
                (name, serial_number),
            )


DEFINED_PORT = 3000


def start():
    import socket
    import sys
    import time

    import schedule

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("localhost", DEFINED_PORT))
    except socket.error as message:
        # if any error occurs then with the
        # help of sys.exit() exit from the program
        print("Bind failed. Message " + str(message))
        sys.exit()

    controller = Controller()

    epoch = time.time()

    def start_water(serial_number: str, duration: int):
        controller.send_command(
            serial_number=serial_number,
            cmd=Command(code=CommandCode.StartWater, data={"duration": duration}),
        )

    def start_light(serial_number: str, duration: int):
        controller.send_command(
            serial_number=serial_number,
            cmd=Command(code=CommandCode.StartLight, data={"duration": duration}),
        )

    while True:
        now = time.time()

        if now - epoch > 3:
            try:
                controller.refresh_picos()
                print(controller.connected_picos())
            except Exception as e:
                print(e)
                pass
            epoch = now
