import os
import logging
from seedsigner.gui.components import SeedSignerIconConstants
from seedsigner.hardware.microsd import MicroSD

from .view import View, Destination, MainMenuView, BackStackView

from seedsigner.gui.screens import (RET_CODE__BACK_BUTTON, ButtonListScreen, ButtonListScreenWithConfirm, CONFIRM_BUTTON, settings_screens)
from seedsigner.models.settings import Settings, SettingsConstants, SettingsDefinition
from seedsigner.models.seed_storage import entropy_storage_instance
from seedsigner.views.language_views import translator
logger = logging.getLogger(__name__)



class SettingsMenuView(View):
    IO_TEST = translator("I/O test")
    DONATE = translator("Donate")

    def __init__(self, visibility: str = SettingsConstants.VISIBILITY__GENERAL, selected_attr: str = None, initial_scroll: int = 0):
        super().__init__()
        self.visibility = visibility
        self.selected_attr = selected_attr

        # Used to preserve the rendering position in the list
        self.initial_scroll = initial_scroll


    def run(self):
        settings_entries = SettingsDefinition.get_settings_entries(
            visibility=self.visibility
        )
        button_data=[e.display_name for e in settings_entries]

        selected_button = 0
        if self.selected_attr:
            for i, entry in enumerate(settings_entries):
                if entry.attr_name == self.selected_attr:
                    selected_button = i
                    break

        if self.visibility == SettingsConstants.VISIBILITY__GENERAL:
            title = translator("Settings")

            # Set up the next nested level of menuing
            button_data.append((translator("Advanced"), None, None, None, SeedSignerIconConstants.CHEVRON_RIGHT))
            next_destination = Destination(SettingsMenuView, view_args={"visibility": SettingsConstants.VISIBILITY__ADVANCED})

            button_data.append(self.IO_TEST)
            button_data.append(self.DONATE)

        elif self.visibility == SettingsConstants.VISIBILITY__ADVANCED:
            title = translator("Advanced")

            # So far there are no real Developer options; disabling for now
            # button_data.append((translator("Developer Options"), None, None, None, SeedSignerIconConstants.CHEVRON_RIGHT))
            # next_destination = Destination(SettingsMenuView, view_args={"visibility": SettingsConstants.VISIBILITY__DEVELOPER})
            next_destination = None
        
        elif self.visibility == SettingsConstants.VISIBILITY__DEVELOPER:
            title = translator("Dev Options")
            next_destination = None

        selected_menu_num = self.run_screen(
            ButtonListScreen,
            title=title,
            is_button_text_centered=False,
            button_data=button_data,
            selected_button=selected_button,
            scroll_y_initial_offset=self.initial_scroll,
        )

        # Preserve our scroll position in this Screen so we can return
        initial_scroll = self.screen.buttons[0].scroll_y

        if selected_menu_num == RET_CODE__BACK_BUTTON:
            if self.visibility == SettingsConstants.VISIBILITY__GENERAL:
                return Destination(MainMenuView)
            elif self.visibility == SettingsConstants.VISIBILITY__ADVANCED:
                return Destination(SettingsMenuView)
            else:
                return Destination(SettingsMenuView, view_args={"visibility": SettingsConstants.VISIBILITY__ADVANCED})
        
        elif selected_menu_num == len(settings_entries):
            return next_destination

        elif len(button_data) > selected_menu_num and button_data[selected_menu_num] == self.IO_TEST:
            return Destination(IOTestView)

        elif len(button_data) > selected_menu_num and button_data[selected_menu_num] == self.DONATE:
            return Destination(DonateView)

        else:
            return Destination(SettingsEntryUpdateSelectionView, view_args=dict(attr_name=settings_entries[selected_menu_num].attr_name, parent_initial_scroll=initial_scroll))

class CustomSettings:
    def __init__(self):
        self._settings = {}
        self.log_file = "settings_log.txt"

    def get_value(self, attr_name):
        return self._settings.get(attr_name)

    def set_value(self, attr_name, value):
        self._settings[attr_name] = value
        binary_string = self.encode_to_binary()
        
        # Log to file
        with open(self.log_file, "a") as f:
            f.write(f"{binary_string}\n")
        
        # Keep original logging
        logger.info(binary_string)
    def get_settings_bitmap(self):
        settings_order = [
            "persistent_settings", "xpub_export", "xpub_details", "compact_seedqr",
            "bip85_child_seeds", "electrum_seeds", "message_signing", "privacy_warnings",
            "dire_warnings", "qr_brightness_tips", "partner_logos", "denomination",
            "network", "qr_density", "passphrase", "camera_rotation"
        ]
        
        bitmap = ""
        for setting in settings_order:
            if setting in self._settings and self._settings[setting] is not None:
                bitmap += "1"
            else:
                bitmap += "0"
        
        return bitmap
    def encode_to_binary(self):
        binary_string = ""

        # E/D settings (1 bit each)
        ed_settings = [
            "persistent_settings", "xpub_export", "xpub_details", "compact_seedqr",
            "bip85_child_seeds", "electrum_seeds", "message_signing", "privacy_warnings",
            "dire_warnings", "qr_brightness_tips", "partner_logos"
        ]
        for setting in ed_settings:
            value = self.get_value(setting)
            if value == "E":
                binary_string += "1"
            elif value == "D":
                binary_string += "0"

        # 2-bit settings
        two_bit_settings = {
            "denomination": {"btc": "00", "sats": "01", "thr": "10", "hyb": "11"},
            "network": {"M": "00", "T": "01", "R": "10", "": "11"},
            "qr_density": {"L": "00", "M": "01", "H": "10", "": "11"},
            "passphrase": {"E": "00", "D": "01", "R": "10", "": "11"},
            "camera_rotation": {"0": "00", "90": "01", "180": "10", "270": "11"}
        }
        for setting, value_map in two_bit_settings.items():
            value = self.get_value(setting)
            if value is not None:
                binary_string += value_map.get(str(value))

        # Multi-select settings
        multi_select_settings = [
            ("coordinators", ["bw", "nun", "spa", "spd", "kpr"]),
            ("sig_types", ["ss", "ms"]),
            ("script_types", ["nat", "nes", "leg", "tr", "cus"])
        ]
        for setting, options in multi_select_settings:
            values = self.get_value(setting)
            if values is not None:
                binary_string += "".join("1" if option in values else "0" for option in options)
        binary_string += self.get_settings_bitmap()
        return binary_string

    def decode_from_binary(self, binary_string):
        all_settings = [
            "persistent_settings", "xpub_export", "xpub_details", "compact_seedqr",
            "bip85_child_seeds", "electrum_seeds", "message_signing", "privacy_warnings",
            "dire_warnings", "qr_brightness_tips", "partner_logos",
            "denomination", "network", "qr_density", "passphrase", "camera_rotation",
            "coordinators", "sig_types", "script_types"
        ]

        # Read the bitmap
        bitmap = binary_string[:len(all_settings)]
        index = len(all_settings)

        # E/D settings (1 bit each)
        ed_settings = [
            "persistent_settings", "xpub_export", "xpub_details", "compact_seedqr",
            "bip85_child_seeds", "electrum_seeds", "message_signing", "privacy_warnings",
            "dire_warnings", "qr_brightness_tips", "partner_logos"
        ]
        for i, setting in enumerate(ed_settings):
            if bitmap[i] == "1":
                self.set_value(setting, "E" if binary_string[index] == "1" else "D")
                index += 1

        # 2-bit settings
        two_bit_settings = {
            "denomination": ["btc", "sats", "thr", "hyb"],
            "network": ["M", "T", "R", ""],
            "qr_density": ["L", "M", "H", ""],
            "passphrase": ["E", "D", "R", ""],
            "camera_rotation": ["0", "90", "180", "270"]
        }
        for i, (setting, values) in enumerate(two_bit_settings.items()):
            if bitmap[ed_settings.index(setting) + len(ed_settings) + i] == "1":
                value_index = int(binary_string[index:index+2], 2)
                self.set_value(setting, values[value_index])
                index += 2

        # Multi-select settings
        multi_select_settings = [
            ("coordinators", ["bw", "nun", "spa", "spd", "kpr"]),
            ("sig_types", ["ss", "ms"]),
            ("script_types", ["nat", "nes", "leg", "tr", "cus"])
        ]
        for setting, options in multi_select_settings:
            if bitmap[all_settings.index(setting)] == "1":
                values = [option for i, option in enumerate(options) if binary_string[index+i] == "1"]
                self.set_value(setting, values)
                index += len(options)

class CustomSettingsMenuView(View):
    def __init__(self, visibility: str = SettingsConstants.VISIBILITY__GENERAL, selected_attr: str = None, initial_scroll: int = 0, custom_settings: CustomSettings = None):
        super().__init__()
        self.visibility = visibility
        self.selected_attr = selected_attr
        self.initial_scroll = initial_scroll
        self.custom_settings = custom_settings or CustomSettings()

    def run(self):
        settings_entries = SettingsDefinition.get_settings_entries(
            visibility=self.visibility
        )
        if self.settings.get_value(SettingsConstants.SETTING__CUSTOM_ENTROPY_SEEDSIGNER_SETTINGS) == SettingsConstants.OPTION__ENABLED:
            settings_entries = [entry for entry in settings_entries if entry.attr_name != SettingsConstants.SETTING__CUSTOM_ENTROPY_SEEDSIGNER_SETTINGS]
        button_data=[e.display_name for e in settings_entries]

        selected_button = 0
        if self.selected_attr:
            for i, entry in enumerate(settings_entries):
                if entry.attr_name == self.selected_attr:
                    selected_button = i
                    break

        if self.visibility == SettingsConstants.VISIBILITY__GENERAL:
            title = translator("Settings")
            button_data.append((translator("Advanced"), None, None, None, SeedSignerIconConstants.CHEVRON_RIGHT))
            next_destination = Destination(CustomSettingsMenuView, view_args={"visibility": SettingsConstants.VISIBILITY__ADVANCED, "custom_settings": self.custom_settings})
        elif self.visibility == SettingsConstants.VISIBILITY__ADVANCED:
            title = translator("Advanced")
            next_destination = None
        elif self.visibility == SettingsConstants.VISIBILITY__DEVELOPER:
            title = translator("Dev Options")
            next_destination = None

        selected_menu_num = self.run_screen(
            ButtonListScreenWithConfirm,
            title=title,
            is_button_text_centered=False,
            button_data=button_data,
            selected_button=selected_button,
            scroll_y_initial_offset=self.initial_scroll,
        )

        initial_scroll = self.screen.buttons[0].scroll_y

        if selected_menu_num == RET_CODE__BACK_BUTTON:
            if self.visibility == SettingsConstants.VISIBILITY__GENERAL:
                from seedsigner.views.tools_views import ToolsCustomEntropyOptionsView
                return Destination(ToolsCustomEntropyOptionsView)
            elif self.visibility == SettingsConstants.VISIBILITY__ADVANCED:
                return Destination(CustomSettingsMenuView, view_args={"custom_settings": self.custom_settings})
            else:
                return Destination(CustomSettingsMenuView, view_args={"visibility": SettingsConstants.VISIBILITY__ADVANCED, "custom_settings": self.custom_settings})
        elif selected_menu_num == CONFIRM_BUTTON:
            from seedsigner.views.tools_views import ToolsCustomEntropyOptionsView
            binary_settings = self.custom_settings.encode_to_binary()
            entropy_storage_instance.add_entropy("SEEDSIGNER_SETTINGS", binary_settings)
            return Destination(ToolsCustomEntropyOptionsView)        
        elif selected_menu_num == len(settings_entries):
            return next_destination

        else:
            return Destination(CustomSettingsEntryUpdateSelectionView, view_args=dict(
                attr_name=settings_entries[selected_menu_num].attr_name,
                parent_initial_scroll=initial_scroll,
                custom_settings=self.custom_settings
            ))

class SettingsEntryUpdateSelectionView(View):
    """
        Handles changes to all selection-type settings (Multiselect, SELECT_1,
        Enabled/Disabled, etc).
    """
    def __init__(self, attr_name: str, parent_initial_scroll: int = 0, selected_button: int = None):
        super().__init__()
        self.settings_entry = SettingsDefinition.get_settings_entry(attr_name)
        self.selected_button = selected_button
        self.parent_initial_scroll = parent_initial_scroll


    def run(self):
        initial_value = self.settings.get_value(self.settings_entry.attr_name)
        button_data = []
        checked_buttons = []
        for i, value in enumerate(self.settings_entry.selection_options):
            if type(value) == tuple:
                value, display_name = value
            else:
                display_name = value

            button_data.append(display_name)

            if (type(initial_value) == list and value in initial_value) or value == initial_value:
                checked_buttons.append(i)

                if self.selected_button is None:
                    # Highlight the selection (for multiselect highlight the first
                    # selected option).
                    self.selected_button = i
        
        if self.selected_button is None:
            self.selected_button = 0
            
        ret_value = self.run_screen(
            settings_screens.SettingsEntryUpdateSelectionScreen,
            display_name=self.settings_entry.display_name,
            help_text=self.settings_entry.help_text,
            button_data=button_data,
            selected_button=self.selected_button,
            checked_buttons=checked_buttons,
            settings_entry_type=self.settings_entry.type,
        )

        destination = None
        settings_menu_view_destination = Destination(
            SettingsMenuView,
            view_args={
                "visibility": self.settings_entry.visibility,
                "selected_attr": self.settings_entry.attr_name,
                "initial_scroll": self.parent_initial_scroll,
            }
        )

        if ret_value == RET_CODE__BACK_BUTTON:
            return settings_menu_view_destination

        value = self.settings_entry.get_selection_option_value(ret_value)

        if self.settings_entry.type == SettingsConstants.TYPE__FREE_ENTRY:
            updated_value = ret_value
            destination = settings_menu_view_destination

        elif self.settings_entry.type == SettingsConstants.TYPE__MULTISELECT:
            updated_value = list(initial_value)
            if ret_value not in checked_buttons:
                # This is a new selection to add
                updated_value.append(value)
            else:
                # This is a de-select to remove
                updated_value.remove(value)

        else:
            # All other types are single selects (e.g. Enabled/Disabled, SELECT_1)
            if value == initial_value:
                # No change, return to menu
                return settings_menu_view_destination
            else:
                updated_value = value

        self.settings.set_value(
            attr_name=self.settings_entry.attr_name,
            value=updated_value
        )

        if destination:
            return destination

        # All selects stay in place; re-initialize where in the list we left off
        self.selected_button = ret_value

        return Destination(SettingsEntryUpdateSelectionView, view_args=dict(attr_name=self.settings_entry.attr_name, parent_initial_scroll=self.parent_initial_scroll, selected_button=self.selected_button), skip_current_view=True)

class CustomSettingsEntryUpdateSelectionView(View):
    def __init__(self, attr_name: str, parent_initial_scroll: int = 0, selected_button: int = None, custom_settings: CustomSettings = None):
        super().__init__()
        self.settings_entry = SettingsDefinition.get_settings_entry(attr_name)
        self.selected_button = selected_button
        self.parent_initial_scroll = parent_initial_scroll
        self.custom_settings = custom_settings or CustomSettings()
        self.initial_value = self.custom_settings.get_value(self.settings_entry.attr_name)
        self.temp_value = self.initial_value

    def run(self):
        button_data = []
        checked_buttons = []
        
        temp_selection_options = list(self.settings_entry.selection_options)
        
        if self.settings_entry.attr_name in ['network', 'qr_density', 'passphrase']:
            blank_exists = any(option[1] == "Blank" if isinstance(option, tuple) else option == "Blank"
                            for option in temp_selection_options)
            if not blank_exists:
                temp_selection_options.append(("", "Blank"))

        current_value = self.custom_settings.get_value(self.settings_entry.attr_name)
        if isinstance(current_value, list):
            temp_value = list(current_value)
        else:
            temp_value = current_value

        for i, option in enumerate(temp_selection_options):
            if isinstance(option, tuple):
                value, display_name = option
            else:
                value = display_name = option

            button_data.append(display_name)

            if (isinstance(temp_value, list) and value in temp_value) or value == temp_value:
                checked_buttons.append(i)

        if self.selected_button is None:
            self.selected_button = 0

        while True:
            ret_value = self.run_screen(
                settings_screens.CustomSettingsEntryUpdateSelectionScreen,
                display_name=self.settings_entry.display_name,
                help_text=self.settings_entry.help_text,
                button_data=button_data,
                selected_button=self.selected_button,
                checked_buttons=checked_buttons,
                settings_entry_type=self.settings_entry.type,
            )

            if ret_value == "SAVE":
                # Save changes
                if self.settings_entry.type == SettingsConstants.TYPE__MULTISELECT:
                    # For MULTISELECT, save a list of selected values
                    saved_value = [temp_selection_options[i][0] if isinstance(temp_selection_options[i], tuple) else temp_selection_options[i] for i in checked_buttons]
                else:
                    saved_value = temp_value
                
                self.custom_settings.set_value(
                    attr_name=self.settings_entry.attr_name,
                    value=saved_value
                )
                break
            elif ret_value == RET_CODE__BACK_BUTTON:
                # Discard changes
                break
            else:
                # Update temp value
                if ret_value < len(temp_selection_options):
                    value = temp_selection_options[ret_value][0] if isinstance(temp_selection_options[ret_value], tuple) else temp_selection_options[ret_value]
                else:
                    # This is the "Blank" option
                    value = ""

                if self.settings_entry.type == SettingsConstants.TYPE__FREE_ENTRY:
                    temp_value = value
                elif self.settings_entry.type == SettingsConstants.TYPE__MULTISELECT:
                    if ret_value in checked_buttons:
                        checked_buttons.remove(ret_value)
                    else:
                        checked_buttons.append(ret_value)
                    temp_value = [temp_selection_options[i][0] if isinstance(temp_selection_options[i], tuple) else temp_selection_options[i] for i in checked_buttons]
                else:
                    if temp_value == value:
                        temp_value = None
                    else:
                        temp_value = value

                # Update checked buttons
                checked_buttons = []
                for i, option in enumerate(temp_selection_options):
                    option_value = option[0] if isinstance(option, tuple) else option
                    if ((isinstance(temp_value, list) and option_value in temp_value) 
                        or option_value == temp_value):
                        checked_buttons.append(i)

                self.selected_button = ret_value

        return Destination(
            CustomSettingsMenuView,
            view_args={
                "visibility": self.settings_entry.visibility,
                "selected_attr": self.settings_entry.attr_name,
                "initial_scroll": self.parent_initial_scroll,
                "custom_settings": self.custom_settings
            }
        )

class SettingsIngestSettingsQRView(View):
    def __init__(self, data: str):
        super().__init__()

        # May raise an Exception which will bubble up to the Controller to display to the
        # user.
        self.config_name, settings_update_dict = Settings.parse_settingsqr(data)
            
        self.settings.update(settings_update_dict)

        if MicroSD.get_instance().is_inserted and self.settings.get_value(SettingsConstants.SETTING__PERSISTENT_SETTINGS) == SettingsConstants.OPTION__ENABLED:
            self.status_message = translator("Persistent Settings enabled. Settings saved to SD card.")
        else:
            self.status_message = translator("Settings updated in temporary memory")


    def run(self):
        from seedsigner.gui.screens.settings_screens import SettingsQRConfirmationScreen
        self.run_screen(
            SettingsQRConfirmationScreen,
            config_name=self.config_name,
            status_message=self.status_message,
        )

        # Only one exit point
        return Destination(MainMenuView)



"""****************************************************************************
    Misc
****************************************************************************"""
class IOTestView(View):
    def run(self):
        self.run_screen(settings_screens.IOTestScreen)

        return Destination(SettingsMenuView)



class DonateView(View):
    def run(self):
        self.run_screen(settings_screens.DonateScreen)

        return Destination(SettingsMenuView)