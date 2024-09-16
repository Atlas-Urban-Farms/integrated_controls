DEFINED_PORT = 3000


def main():
    import socket
    import sys
    import time

    import schedule

    from controller import Command, CommandCode, Controller

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
                picos = controller.refresh_picos()
                print(list(picos.keys()))
            except Exception as e:
                print(e)
                pass
            epoch = now


if __name__ == "__main__":
    main()
