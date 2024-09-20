import json
import os
import sqlite3
import time

import pydantic
import pytermgui as ptg

import controller as ctrl


class Interface:
    def __init__(self, controller: ctrl.Controller) -> None:
        self.manager = ptg.WindowManager()
        self.units_container = ptg.Container()

        self.main_window = ptg.Window(
            "",
            "",
            self.units_container,
        )
        self.main_window.set_title("All Units")

        self.manager.layout.add_slot("body")

        self.manager.add(self.main_window, "body")

        self.manager.focus(self.main_window)

        self.controller = controller
        self.picos = None

    def view_profile(self, pico: ctrl.Pico):
        window = self.new_profile_view(pico)

        self.manager.add(window, "body")
        self.manager.focus(window)

    def new_profile_view(self, pico: ctrl.Pico):
        profile: dict = json.loads(pico.growth_profile)

        inputs = [
            ptg.InputField(str(value), prompt=key + ": ")
            for key, value in profile.items()
        ]

        name_input = ptg.InputField(
            pico.name if pico.name else "", prompt="Unit Name: "
        )
        if not pico.name:
            name_input.styles.value = "red"

            def delete_all(*args, **kwargs):
                name_input.delete_back(len(name_input.value))
                name_input.bind(
                    ptg.keys.BACKSPACE,
                    lambda _, key: ptg.InputField.handle_key(name_input, key),
                )

            name_input.bind(ptg.keys.BACKSPACE, delete_all)

        def on_save(_):
            old_profile = ctrl.GrowthProfile.model_validate_json(pico.growth_profile)

            try:
                new_profile = ctrl.GrowthProfile(
                    **{input.prompt[1:-2]: input.value for input in inputs}  # type: ignore
                )
            except pydantic.ValidationError as e:
                self.display_alert(
                    ptg.Container(
                        *[
                            ptg.Label(
                                f"For Field \"{'.'.join([str(x) for x in err['loc']])}\": {err['msg']}",
                            )
                            for err in e.errors()
                        ]
                    )
                )
                self.loop()
                return

            change_saved = False

            if old_profile != new_profile:
                self.controller.change_pico_growth_profile(
                    pico.serial_number, new_profile
                )

                change_saved = True

            if name_input.value != pico.name:
                self.controller.change_pico_name(pico.serial_number, name_input.value)

            if change_saved:
                self.display_alert(ptg.Label("Change Saved"), 2000)

            self.manager.remove(window)

        confirm_button = ptg.Button(label="Confirm", onclick=on_save)

        window = ptg.Window(
            ptg.Splitter(
                ptg.Container(
                    ptg.Label("[bold]Unit Information"),
                    name_input,
                ),
                ptg.Container(
                    ptg.Label("[bold]Growth Profile"),
                    *inputs,
                ),
            ),
            "",
            confirm_button,
            is_modal=True,
        )

        window.set_title(pico.serial_number)
        window.bind(ptg.keys.ESC, lambda _, __: self.manager.remove(window))

        window.center()

        return window

    def display_alert(self, alert: ptg.Widget, dismiss_in: int | None = None):
        window = ptg.Window(alert, is_modal=True)

        self.manager.add(window)
        window.center()

        window.bind(ptg.keys.ESC, lambda _, __: self.manager.remove(window))

        if dismiss_in:
            time.sleep(dismiss_in)
            self.manager.remove(window)

    def new_pico_row(self, pico: ctrl.Pico):
        input_label = ptg.Label(pico.name if pico.name else "")

        if not pico.name:
            new_name_prompt = "Enter A Name"

            input_label.styles.value = "red italic"
            input_label.value = new_name_prompt

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
            input_label, ptg.Label(pico.serial_number), *interactions_buttons
        )

        return splitter

    def update_units(self, picos: list[ctrl.Pico]):
        if picos != self.picos:
            self.picos = picos

            widgets = [
                ptg.Splitter("Unit Name", "Serial Number", "", ""),
            ] + [self.new_pico_row(pico) for pico in picos]

            # widgets = [ptg.Container(widget, border=["bottom"]) for widget in widgets]

            self.units_container.set_widgets(widgets)  # type: ignore

    def loop(self):
        if os.environ.get("DEV"):
            self.update_units(self.controller.all_picos())
        else:
            self.update_units(self.controller.connected_picos())

    def start(self):
        self.update_units([])
        self.manager.run()
