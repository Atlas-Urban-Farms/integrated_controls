if __name__ == "__main__":
    import time

    from comm import Controller

    controller = Controller()

    epoch = time.time()

    while True:
        now = time.time()

        if now - epoch > 3:
            try:
                picos = controller.refresh_picos()
                print(list(controller.infos.values()))
            except Exception as e:
                print(e)
                pass
            epoch = now
