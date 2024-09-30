import json
import os
import sqlite3
import time

import pydantic
import pytermgui as ptg

import controller as ctrl


class Interface:
    def __init__(self, controller: ctrl.Controller) -> None:
        CONFIG = """
        config:
            InputField:
                styles:
                    prompt: dim italic
                    cursor: '@72'
            Label:
                styles:
                    value: dim bold

            Window:
                styles:
                    border: '60'
                    corner: '60'

            Container:
                styles:
                    border: '96'
                    corner: '96'
        """

        with ptg.YamlLoader() as loader:
            loader.load(CONFIG)

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
                    ptg.InputField.handle_key,
                )

            name_input.bind(ptg.keys.BACKSPACE, delete_all)

        else:
            if pico.connected:
                name_input.styles.value = "green"
            else:
                name_input.styles.value = "red"

        def on_save(_):
            old_profile = ctrl.GrowthProfile.model_validate_json(pico.growth_profile)

            try:
                new_profile = ctrl.GrowthProfile(
                    **{input.prompt[:-2]: input.value for input in inputs}  # type: ignore
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

                change_saved = True

            if change_saved:
                self.display_alert(ptg.Label("Change Saved"), 2)

            self.manager.remove(window)

        def on_play_sound_click(_):
            if pico.connected:
                self.controller.play_sound(serial_number=pico.serial_number)

        def on_start_water_click(_):
            if pico.connected:
                self.controller.start_water(
                    serial_number=pico.serial_number,
                    duration=10,
                )

        confirm_button = ptg.Button(label="Confirm", onclick=on_save)

        def spaced_inputs(inputs: list[ptg.InputField]):
            for input in inputs:
                yield ptg.Label()
                yield input

        window = ptg.Window(
            "[bold]Configure Device",
            "[italic]All field are editable",
            "",
            ptg.Splitter(
                ptg.Container(
                    ptg.Label("[bold]Unit Information"),
                    name_input,
                    *["" for _ in range(0, len(inputs) - 1)],
                ),
                ptg.Container(
                    ptg.Label("[bold]Growth Profile"),
                    *spaced_inputs(inputs),
                ),
            ),
            "",
            ptg.Container(
                "Interactions",
                ptg.Splitter(
                    ptg.Button(label="Play Sound", onclick=on_play_sound_click),
                    ptg.Button(
                        label="Start Pump",
                        onclick=on_start_water_click,
                    ),
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

    def display_alert(
        self,
        alert: ptg.Widget,
        dismiss_in: int | None = None,
        window: ptg.Window | None = None,
    ):
        if not window:
            window = ptg.Window(alert, is_modal=True)

        self.manager.add(window)
        window.center()

        window.bind(ptg.keys.ESC, lambda _, __: self.manager.remove(window))

        if dismiss_in:
            time.sleep(dismiss_in)
            self.manager.remove(window)

    def new_pico_row(self, pico: ctrl.Pico):
        name_label = ptg.Label(pico.name if pico.name else "")

        if not pico.name:
            new_name_prompt = "Enter A Name"

            name_label.styles.value = "white italic"
            name_label.value = new_name_prompt
        else:
            if pico.connected:
                name_label.styles.value = "green"
            else:
                name_label.styles.value = "red"

        def on_edit_profile_click(_):
            self.view_profile(pico)

        interactions_buttons = [
            ptg.Button(label="Configure", onclick=on_edit_profile_click),
        ]

        splitter = ptg.Splitter(
            name_label, ptg.Label(pico.serial_number), *interactions_buttons
        )

        return splitter

    def update_units(self, picos: list[ctrl.Pico]):
        if picos != self.picos:
            self.picos = picos

            widgets = [ptg.Splitter("Unit Name", "Serial Number", "Configure"), ""] + [
                self.new_pico_row(pico) for pico in picos
            ]

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
