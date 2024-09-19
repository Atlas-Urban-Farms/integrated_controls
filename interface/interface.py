import json
import sqlite3
import time

import pytermgui as ptg

import controller as ctrl


class Interface:
    def __init__(self, controller: ctrl.Controller) -> None:
        self.manager = ptg.WindowManager()
        self.units_container = ptg.Container()

        self.profile_window = ptg.Window()
        self.main_window = ptg.Window(
            ptg.Label("All Minis"),
            "",
            "",
            ptg.Splitter("Unit Name", "Serial Number", ""),
            self.units_container,
        )

        self.manager.layout.add_slot("Body")

        self.manager.add(self.main_window)
        self.manager.add(self.profile_window)

        self.manager.focus(self.main_window)

        self.controller = controller
        self.picos = None

    def view_profile(self, pico: ctrl.Pico):
        profile: dict = json.loads(pico.growth_profile)

        self.profile_window.set_widgets(
            [ptg.InputField(value, prompt=key) for key, value in profile]
        )
        self.manager.focus(self.profile_window)

    def new_pico_display(self, pico: ctrl.Pico):
        input_field = ptg.InputField(pico.name if pico.name else '"Enter A Name"')

        def on_enter(field: ptg.InputField, key: str):
            self.controller.change_pico_name(pico.serial_number, field.value)

        input_field.bind(ptg.keys.ENTER, on_enter)

        def on_click(_):
            self.view_profile(pico)

        splitter = ptg.Splitter(
            input_field,
            ptg.Label(pico.serial_number),
            ptg.Button(label="Edit Profile", onclick=on_click),
        )

        return splitter

    def update_units(self, picos: list[ctrl.Pico]):
        if picos != self.picos:
            self.picos = picos

            widgets = [self.new_pico_display(pico) for pico in picos]

            self.units_container.set_widgets(widgets)  # type: ignore

    def loop(self):
        self.update_units(self.controller.connected_picos())

    def start(self):
        self.manager.run()
