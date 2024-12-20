import os
import sys

parent_dir = os.path.abspath(os.path.dirname(__file__))
vendor_dir = os.path.join(parent_dir, "vendor/Lib/site-packages")
sys.path.append(vendor_dir)

import atexit
import threading
import time
from dotenv import load_dotenv

import controller as ctrl
import interface as intf

load_dotenv()


def main():
    controller: ctrl.Controller = ctrl.Controller()  # type: ignore
    interface = intf.Interface(controller)

    p1 = threading.Thread(target=interface.start, daemon=True)

    p1.start()

    epoch = time.time()

    while True:
        controller.loop()
        interface.loop()

        end = time.time()

        time.sleep(max((epoch + 1000 - end) / 1000, 0))

        epoch = end


if __name__ == "__main__":
    main()
