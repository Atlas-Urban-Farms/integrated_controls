import controller
import interface


def controller_start():
    from contextlib import redirect_stdout

    with open("logs.txt", "w+") as f:
        with redirect_stdout(f):
            controller.start()


def main():
    import multiprocessing

    p1 = multiprocessing.Process(target=interface.start)
    p2 = multiprocessing.Process(target=controller_start)

    p1.start()
    p2.start()

    p1.join()
    p2.join()


if __name__ == "__main__":
    main()
