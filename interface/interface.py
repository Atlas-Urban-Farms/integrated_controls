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
            "",
            "",
            self.units_container,
        )
        self.main_window.set_title("All Units")

        self.manager.layout.add_slot("Body")

        self.manager.add(self.main_window)

        self.manager.focus(self.main_window)

        self.controller = controller
        self.picos = None

    def view_profile(self, pico: ctrl.Pico):
        window = self.new_profile_view(pico)

        self.manager.add(window)
        self.manager.focus(window)

    def new_profile_view(self, pico: ctrl.Pico):
        profile: dict = json.loads(pico.growth_profile)

        inputs = [
            ptg.InputField(str(value), prompt=key + ": ")
            for key, value in profile.items()
        ]

        def on_save(_):
            old_profile = ctrl.GrowthProfile.model_validate_json(pico.growth_profile)

            new_profile = ctrl.GrowthProfile(
                **{input.prompt[:-2]: int(input.value) for input in inputs}
            )

            if old_profile != new_profile:
                self.controller.change_pico_growth_profile(
                    pico.serial_number, new_profile
                )

                self.display_alert("Profile Saved")

            self.manager.remove(window)

        window = ptg.Window(
            ptg.Container(
                *inputs,
                "",
                ptg.Button(label="Confirm", onclick=on_save),
            )
        )

        window.set_title(pico.name if pico.name else pico.serial_number)

        window.center()

        return window

    def display_alert(self, alert: str):
        window = ptg.Window(alert)
        window.center()

        self.manager.add(window)
        time.sleep(1.5)
        self.manager.remove(window)

    def new_pico_display(self, pico: ctrl.Pico):
        input_field = ptg.InputField(pico.name if pico.name else '"Enter A Name"')

        def on_enter(field: ptg.InputField, key: str):
            if field.value != pico.name and field.value:
                self.controller.change_pico_name(pico.serial_number, field.value)

                self.display_alert("Name Updated")

        input_field.bind(ptg.keys.ENTER, on_enter)

        def on_edit_profile_click(_):
            self.view_profile(pico)

        def on_play_sound_click(_):
            try:
                self.controller.play_sound(serial_number=pico.serial_number)
            except:
                pass

        interactions_buttons = [
            ptg.Button(label="Edit Profile", onclick=on_edit_profile_click),
            ptg.Button(label="Play Sound", onclick=on_play_sound_click),
        ]

        splitter = ptg.Splitter(
            input_field, ptg.Label(pico.serial_number), *interactions_buttons
        )

        return splitter

    def update_units(self, picos: list[ctrl.Pico]):
        if picos != self.picos:
            self.picos = picos

            widgets = [
                ptg.Splitter("Unit Name", "Serial Number", "", ""),
            ] + [self.new_pico_display(pico) for pico in picos]

            
            # widgets = [ptg.Container(widget, border=["bottom"]) for widget in widgets]

            self.units_container.set_widgets(widgets)  # type: ignore

    def loop(self):
        self.update_units(self.controller.connected_picos())

    def start(self):
        self.update_units([])
        self.manager.run()
