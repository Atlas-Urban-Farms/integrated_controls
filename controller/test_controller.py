import controller as ctrl


def test_get_last_watered():
    controller = ctrl.Controller()

    picos = controller.all_picos()

    assert isinstance(controller.get_last_watered(picos[0].serial_number), float)
