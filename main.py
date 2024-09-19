import atexit
import threading
import time

import controller as ctrl
import interface as intf


def main():
    from multiprocessing.managers import SyncManager

    manager = SyncManager()
    manager.register("Controller", ctrl.Controller)

    manager.start()

    controller: ctrl.Controller = manager.Controller() # type: ignore
    interface = intf.Interface(controller)

    p1 = threading.Thread(target=interface.start)

    p1.start()

    epoch = time.time()

    while True:
        controller.loop()
        interface.loop()

        end = time.time()

        time.sleep(max((epoch + 1000 - end) / 1000, 0))


if __name__ == "__main__":
    main()
