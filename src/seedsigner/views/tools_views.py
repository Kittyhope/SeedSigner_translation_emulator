from dataclasses import dataclass
import hashlib
import logging
import os
import time
import subprocess
import nacl.utils

from embit.descriptor import Descriptor
from PIL import Image
from PIL.ImageOps import autocontrast

from seedsigner.controller import Controller
from seedsigner.gui.components import FontAwesomeIconConstants, GUIConstants, SeedSignerIconConstants
from seedsigner.gui.screens import (RET_CODE__BACK_BUTTON, ButtonListScreen, WarningScreen, ButtonListScreenWithConfirm, CONFIRM_BUTTON, DireWarningScreen, AutomodeStartScreen)
from seedsigner.gui.screens.seed_screens import SeedTurtleMovementNumberScreen, SeedDoorNumberScreen, SeedRandomMnemonicNumberScreen, SeedBIP85SelectChildIndexScreen
from seedsigner.gui.screens.tools_screens import (ToolsCalcFinalWordDoneScreen, ToolsCalcFinalWordFinalizePromptScreen,
    ToolsCalcFinalWordScreen, ToolsCoinFlipEntryScreen, ToolsDiceEntropyEntryScreen, ToolsImageEntropyFinalImageScreen,
    ToolsImageEntropyLivePreviewScreen, ToolsAddressExplorerAddressTypeScreen,ToolsCustomDoorEntropyScreen, TurtleSeedGenerationScreen)
from seedsigner.helpers import embit_utils, mnemonic_generation
from seedsigner.models.encode_qr import GenericStaticQrEncoder
from seedsigner.models.seed import Seed
from seedsigner.models.seed_storage import entropy_storage_instance
from seedsigner.models.settings_definition import SettingsConstants
from seedsigner.views.seed_views import SeedDiscardView, SeedFinalizeView, SeedMnemonicEntryView, SeedOptionsView, SeedWordsWarningView, SeedExportXpubScriptTypeView, SeedAddIDView, SeedAddPASSWORDView, AutoEntropyResultView
from seedsigner.views.language_views import translator
from seedsigner.views.settings_views import CustomSettingsMenuView
from .view import View, Destination, BackStackView, MainMenuView

logger = logging.getLogger(__name__)

class ToolsMenuView(View):
    GENERATE_SEED = (translator("Generate New Seed"), SeedSignerIconConstants.PLUS)
    KEYBOARD = (translator("Calc 12th/24th word"), FontAwesomeIconConstants.KEYBOARD)
    ADDRESS_EXPLORER = translator("Address Explorer")
    VERIFY_ADDRESS = translator("Verify address")

    def run(self):
        button_data = [self.GENERATE_SEED, self.KEYBOARD, self.ADDRESS_EXPLORER, self.VERIFY_ADDRESS]

        selected_menu_num = self.run_screen(
            ButtonListScreen,
            title=translator("Tools"),
            is_button_text_centered=False,
            button_data=button_data,
        )

        if selected_menu_num == RET_CODE__BACK_BUTTON:
            return Destination(BackStackView)

        elif button_data[selected_menu_num] == self.GENERATE_SEED:
            from seedsigner.views.generate_seed_views import GenerateSeedMenuView
            return Destination(GenerateSeedMenuView)

        elif button_data[selected_menu_num] == self.KEYBOARD:
            return Destination(ToolsCalcFinalWordNumWordsView)

        elif button_data[selected_menu_num] == self.ADDRESS_EXPLORER:
            return Destination(ToolsAddressExplorerSelectSourceView)

        elif button_data[selected_menu_num] == self.VERIFY_ADDRESS:
            from seedsigner.views.scan_views import ScanAddressView
            return Destination(ScanAddressView)



"""****************************************************************************
    Image entropy Views
****************************************************************************"""
class ToolsImageEntropyLivePreviewView(View):
    def run(self):
        self.controller.image_entropy_preview_frames = None
        ret = ToolsImageEntropyLivePreviewScreen().display()

        if ret == RET_CODE__BACK_BUTTON:
            return Destination(BackStackView)
        
        self.controller.image_entropy_preview_frames = ret
        return Destination(ToolsImageEntropyFinalImageView)



class ToolsImageEntropyFinalImageView(View):
    def run(self):
        if not self.controller.image_entropy_final_image:
            from seedsigner.hardware.camera import Camera
            # Take the final full-res image
            camera = Camera.get_instance()
            camera.start_single_frame_mode(resolution=(720, 480))
            time.sleep(0.25)
            self.controller.image_entropy_final_image = camera.capture_frame()
            camera.stop_single_frame_mode()

        # Prep a copy of the image for display. The actual image data is 720x480
        # Present just a center crop and resize it to fit the screen and to keep some of
        #   the data hidden.
        display_version = autocontrast(
            self.controller.image_entropy_final_image,
            cutoff=2
        ).crop(
            (120, 0, 600, 480)
        ).resize(
            (self.canvas_width, self.canvas_height), Image.BICUBIC
        )
        
        ret = ToolsImageEntropyFinalImageScreen(
            final_image=display_version
        ).display()

        if ret == RET_CODE__BACK_BUTTON:
            # Go back to live preview and reshoot
            self.controller.image_entropy_final_image = None
            return Destination(BackStackView)
        
        return Destination(ToolsImageEntropyMnemonicLengthView)



class ToolsImageEntropyMnemonicLengthView(View):
    def run(self):
        TWELVE_WORDS = translator("12 words")
        TWENTYFOUR_WORDS = translator("24 words")
        button_data = [TWELVE_WORDS, TWENTYFOUR_WORDS]

        selected_menu_num = ButtonListScreen(
            title=translator("Mnemonic Length?"),
            button_data=button_data,
        ).display()

        if selected_menu_num == RET_CODE__BACK_BUTTON:
            return Destination(BackStackView)
        
        if button_data[selected_menu_num] == TWELVE_WORDS:
            mnemonic_length = 12
        else:
            mnemonic_length = 24

        preview_images = self.controller.image_entropy_preview_frames
        seed_entropy_image = self.controller.image_entropy_final_image

        # Build in some hardware-level uniqueness via CPU unique Serial num
        try:
            stream = os.popen("cat /proc/cpuinfo | grep Serial")
            output = stream.read()
            serial_num = output.split(":")[-1].strip().encode('utf-8')
            serial_hash = hashlib.sha256(serial_num)
            hash_bytes = serial_hash.digest()
        except Exception as e:
            logger.info(repr(e), exc_info=True)
            hash_bytes = b'0'

        # Build in modest entropy via millis since power on
        millis_hash = hashlib.sha256(hash_bytes + str(time.time()).encode('utf-8'))
        hash_bytes = millis_hash.digest()

        # Build in better entropy by chaining the preview frames
        for frame in preview_images:
            img_hash = hashlib.sha256(hash_bytes + frame.tobytes())
            hash_bytes = img_hash.digest()

        # Finally build in our headline entropy via the new full-res image
        final_hash = hashlib.sha256(hash_bytes + seed_entropy_image.tobytes()).digest()

        if mnemonic_length == 12:
            # 12-word mnemonic only uses the first 128 bits / 16 bytes of entropy
            final_hash = final_hash[:16]

        # Generate the mnemonic
        mnemonic = mnemonic_generation.generate_mnemonic_from_bytes(final_hash)

        # Image should never get saved nor stick around in memory
        seed_entropy_image = None
        preview_images = None
        final_hash = None
        hash_bytes = None
        self.controller.image_entropy_preview_frames = None
        self.controller.image_entropy_final_image = None

        # Add the mnemonic as an in-memory Seed
        seed = Seed(mnemonic, wordlist_language_code=self.settings.get_value(SettingsConstants.SETTING__WORDLIST_LANGUAGE))
        self.controller.storage.set_pending_seed(seed)
        
        # Cannot return BACK to this View
        return Destination(SeedWordsWarningView, view_args={"seed_num": None}, clear_history=True)



"""****************************************************************************
    Dice rolls Views
****************************************************************************"""
class ToolsDiceEntropyMnemonicLengthView(View):
    def run(self):
        translated_TWELVE = translator("12 words")
        translated_rolls = translator("rolls")
        translated_TWENTY_FOUR = translator("24 words")
        TWELVE = f"{translated_TWELVE} ({mnemonic_generation.DICE__NUM_ROLLS__12WORD} {translated_rolls})"
        TWENTY_FOUR = f"{translated_TWENTY_FOUR} ({mnemonic_generation.DICE__NUM_ROLLS__24WORD} {translated_rolls})"
        
        button_data = [TWELVE, TWENTY_FOUR]
        selected_menu_num = ButtonListScreen(
            title=translator("Mnemonic Length"),
            is_bottom_list=True,
            is_button_text_centered=True,
            button_data=button_data,
        ).display()

        if selected_menu_num == RET_CODE__BACK_BUTTON:
            return Destination(BackStackView)

        elif button_data[selected_menu_num] == TWELVE:
            return Destination(ToolsDiceEntropyEntryView, view_args=dict(total_rolls=mnemonic_generation.DICE__NUM_ROLLS__12WORD))

        elif button_data[selected_menu_num] == TWENTY_FOUR:
            return Destination(ToolsDiceEntropyEntryView, view_args=dict(total_rolls=mnemonic_generation.DICE__NUM_ROLLS__24WORD))



class ToolsDiceEntropyEntryView(View):
    def __init__(self, total_rolls: int):
        super().__init__()
        self.total_rolls = total_rolls
    

    def run(self):
        ret = ToolsDiceEntropyEntryScreen(
            return_after_n_chars=self.total_rolls,
        ).display()

        if ret == RET_CODE__BACK_BUTTON:
            return Destination(BackStackView)
        
        dice_seed_phrase = mnemonic_generation.generate_mnemonic_from_dice(ret)

        # Add the mnemonic as an in-memory Seed
        seed = Seed(dice_seed_phrase, wordlist_language_code=self.settings.get_value(SettingsConstants.SETTING__WORDLIST_LANGUAGE))
        self.controller.storage.set_pending_seed(seed)

        # Cannot return BACK to this View
        return Destination(SeedWordsWarningView, view_args={"seed_num": None}, clear_history=True)



"""****************************************************************************
    Calc final word Views
****************************************************************************"""
class ToolsCalcFinalWordNumWordsView(View):
    TWELVE = translator("12 words")
    TWENTY_FOUR = translator("24 words")

    def run(self):
        button_data = [self.TWELVE, self.TWENTY_FOUR]

        selected_menu_num = self.run_screen(
            ButtonListScreen,
            title=translator("Mnemonic Length"),
            is_bottom_list=True,
            is_button_text_centered=True,
            button_data=button_data,
        )

        if selected_menu_num == RET_CODE__BACK_BUTTON:
            return Destination(BackStackView)

        elif button_data[selected_menu_num] == self.TWELVE:
            self.controller.storage.init_pending_mnemonic(12)

            # return Destination(SeedMnemonicEntryView, view_args=dict(is_calc_final_word=True))
            return Destination(SeedMnemonicEntryView, view_args=dict(is_calc_final_word=True))

        elif button_data[selected_menu_num] == self.TWENTY_FOUR:
            self.controller.storage.init_pending_mnemonic(24)

            # return Destination(SeedMnemonicEntryView, view_args=dict(is_calc_final_word=True))
            return Destination(SeedMnemonicEntryView, view_args=dict(is_calc_final_word=True))



class ToolsCalcFinalWordFinalizePromptView(View):
    def run(self):
        mnemonic = self.controller.storage.pending_mnemonic
        mnemonic_length = len(mnemonic)
        if mnemonic_length == 12:
            num_entropy_bits = 7
        else:
            num_entropy_bits = 3

        COIN_FLIPS = translator("Coin flip entropy")
        SELECT_WORD = translator("Word selection entropy")
        ZEROS = translator("Finalize with zeros")

        button_data = [COIN_FLIPS, SELECT_WORD, ZEROS]
        selected_menu_num = ToolsCalcFinalWordFinalizePromptScreen(
            mnemonic_length=mnemonic_length,
            num_entropy_bits=num_entropy_bits,
            button_data=button_data,
        ).display()

        if selected_menu_num == RET_CODE__BACK_BUTTON:
            return Destination(BackStackView)

        elif button_data[selected_menu_num] == COIN_FLIPS:
            return Destination(ToolsCalcFinalWordCoinFlipsView)

        elif button_data[selected_menu_num] == SELECT_WORD:
            # Clear the final word slot, just in case we're returning via BACK button
            self.controller.storage.update_pending_mnemonic(None, mnemonic_length - 1)
            return Destination(SeedMnemonicEntryView, view_args=dict(is_calc_final_word=True, cur_word_index=mnemonic_length - 1))

        elif button_data[selected_menu_num] == ZEROS:
            # User skipped the option to select a final word to provide last bits of
            # entropy. We'll insert all zeros and piggy-back on the coin flip attr
            wordlist_language_code = self.settings.get_value(SettingsConstants.SETTING__WORDLIST_LANGUAGE)
            self.controller.storage.update_pending_mnemonic(Seed.get_wordlist(wordlist_language_code)[0], mnemonic_length - 1)
            return Destination(ToolsCalcFinalWordShowFinalWordView, view_args=dict(coin_flips="0" * num_entropy_bits))



class ToolsCalcFinalWordCoinFlipsView(View):
    def run(self):
        mnemonic_length = len(self.controller.storage.pending_mnemonic)

        if mnemonic_length == 12:
            total_flips = 7
        else:
            total_flips = 3
        
        ret_val = ToolsCoinFlipEntryScreen(
            return_after_n_chars=total_flips,
        ).display()

        if ret_val == RET_CODE__BACK_BUTTON:
            return Destination(BackStackView)
        
        else:
            return Destination(ToolsCalcFinalWordShowFinalWordView, view_args=dict(coin_flips=ret_val))



class ToolsCalcFinalWordShowFinalWordView(View):
    def __init__(self, coin_flips: str = None):
        super().__init__()
        # Construct the actual final word. The user's selected_final_word
        # contributes:
        #   * 3 bits to a 24-word seed (plus 8-bit checksum)
        #   * 7 bits to a 12-word seed (plus 4-bit checksum)
        from seedsigner.helpers import mnemonic_generation

        wordlist_language_code = self.settings.get_value(SettingsConstants.SETTING__WORDLIST_LANGUAGE)
        wordlist = Seed.get_wordlist(wordlist_language_code)

        # Prep the user's selected word / coin flips and the actual final word for
        # the display.
        if coin_flips:
            self.selected_final_word = None
            self.selected_final_bits = coin_flips
        else:
            # Convert the user's final word selection into its binary index equivalent
            self.selected_final_word = self.controller.storage.pending_mnemonic[-1]
            self.selected_final_bits = format(wordlist.index(self.selected_final_word), '011b')

        if coin_flips:
            # fill the last bits (what will eventually be the checksum) with zeros
            binary_string = coin_flips + "0" * (11 - len(coin_flips))

            # retrieve the matching word for the resulting index
            wordlist_index = int(binary_string, 2)
            wordlist = Seed.get_wordlist(self.controller.settings.get_value(SettingsConstants.SETTING__WORDLIST_LANGUAGE))
            word = wordlist[wordlist_index]

            # update the pending mnemonic with our new "final" (pre-checksum) word
            self.controller.storage.update_pending_mnemonic(word, -1)

        # Now calculate the REAL final word (has a proper checksum)
        final_mnemonic = mnemonic_generation.calculate_checksum(
            mnemonic=self.controller.storage.pending_mnemonic,
            wordlist_language_code=wordlist_language_code,
        )

        # Update our pending mnemonic with the real final word
        self.controller.storage.update_pending_mnemonic(final_mnemonic[-1], -1)

        mnemonic = self.controller.storage.pending_mnemonic
        mnemonic_length = len(mnemonic)

        # And grab the actual final word's checksum bits
        self.actual_final_word = self.controller.storage.pending_mnemonic[-1]
        num_checksum_bits = 4 if mnemonic_length == 12 else 8
        self.checksum_bits = format(wordlist.index(self.actual_final_word), '011b')[-num_checksum_bits:]


    def run(self):
        NEXT = translator("Next")
        button_data = [NEXT]
        selected_menu_num = self.run_screen(
            ToolsCalcFinalWordScreen,
            title=translator("Final Word Calc"),
            button_data=button_data,
            selected_final_word=self.selected_final_word,
            selected_final_bits=self.selected_final_bits,
            checksum_bits=self.checksum_bits,
            actual_final_word=self.actual_final_word,
        )

        if selected_menu_num == RET_CODE__BACK_BUTTON:
            return Destination(BackStackView)

        elif button_data[selected_menu_num] == NEXT:
            return Destination(ToolsCalcFinalWordDoneView)



class ToolsCalcFinalWordDoneView(View):
    def run(self):
        mnemonic = self.controller.storage.pending_mnemonic
        mnemonic_word_length = len(mnemonic)
        final_word = mnemonic[-1]

        LOAD = translator("Load seed")
        DISCARD = (translator("Discard"), None, None, translator("red"))
        button_data = [LOAD, DISCARD]

        selected_menu_num = ToolsCalcFinalWordDoneScreen(
            final_word=final_word,
            mnemonic_word_length=mnemonic_word_length,
            fingerprint=self.controller.storage.get_pending_mnemonic_fingerprint(self.settings.get_value(SettingsConstants.SETTING__NETWORK)),
            button_data=button_data,
        ).display()

        if selected_menu_num == RET_CODE__BACK_BUTTON:
            return Destination(BackStackView)
        
        self.controller.storage.convert_pending_mnemonic_to_pending_seed()

        if button_data[selected_menu_num] == LOAD:
            return Destination(SeedFinalizeView)
        
        elif button_data[selected_menu_num] == DISCARD:
            return Destination(SeedDiscardView)


"""****************************************************************************
    Address Explorer Views
****************************************************************************"""
class ToolsAddressExplorerSelectSourceView(View):
    SCAN_SEED = (translator("Scan a seed"), SeedSignerIconConstants.QRCODE)
    SCAN_DESCRIPTOR = (translator("Scan wallet descriptor"), SeedSignerIconConstants.QRCODE)
    TYPE_12WORD = (translator("Enter 12-word seed"), FontAwesomeIconConstants.KEYBOARD)
    TYPE_24WORD = (translator("Enter 24-word seed"), FontAwesomeIconConstants.KEYBOARD)
    TYPE_ELECTRUM = (translator("Enter Electrum seed"), FontAwesomeIconConstants.KEYBOARD)

    def run(self):
        seeds = self.controller.storage.seeds
        button_data = []
        for seed in seeds:
            button_str = seed.get_fingerprint(self.settings.get_value(SettingsConstants.SETTING__NETWORK))
            button_data.append((button_str, SeedSignerIconConstants.FINGERPRINT))
        button_data = button_data + [self.SCAN_SEED, self.SCAN_DESCRIPTOR, self.TYPE_12WORD, self.TYPE_24WORD]
        if self.settings.get_value(SettingsConstants.SETTING__ELECTRUM_SEEDS) == SettingsConstants.OPTION__ENABLED:
            button_data.append(self.TYPE_ELECTRUM)
                
        selected_menu_num = self.run_screen(
            ButtonListScreen,
            title=translator("Address Explorer"),
            button_data=button_data,
            is_button_text_centered=False,
            is_bottom_list=True,
        )

        if selected_menu_num == RET_CODE__BACK_BUTTON:
            return Destination(BackStackView)

        # Most of the options require us to go through a side flow(s) before we can
        # continue to the address explorer. Set the Controller-level flow so that it
        # knows to re-route us once the side flow is complete.        
        self.controller.resume_main_flow = Controller.FLOW__ADDRESS_EXPLORER

        if len(seeds) > 0 and selected_menu_num < len(seeds):
            # User selected one of the n seeds
            return Destination(
                SeedExportXpubScriptTypeView,
                view_args=dict(
                    seed_num=selected_menu_num,
                    sig_type=SettingsConstants.SINGLE_SIG,
                )
            )

        elif button_data[selected_menu_num] == self.SCAN_SEED:
            from seedsigner.views.scan_views import ScanSeedQRView
            return Destination(ScanSeedQRView)

        elif button_data[selected_menu_num] == self.SCAN_DESCRIPTOR:
            from seedsigner.views.scan_views import ScanWalletDescriptorView
            return Destination(ScanWalletDescriptorView)

        elif button_data[selected_menu_num] in [self.TYPE_12WORD, self.TYPE_24WORD]:
            from seedsigner.views.seed_views import SeedMnemonicEntryView
            if button_data[selected_menu_num] == self.TYPE_12WORD:
                self.controller.storage.init_pending_mnemonic(num_words=12)
            else:
                self.controller.storage.init_pending_mnemonic(num_words=24)
            return Destination(SeedMnemonicEntryView)

        elif button_data[selected_menu_num] == self.TYPE_ELECTRUM:
            from seedsigner.views.seed_views import SeedElectrumMnemonicStartView
            return Destination(SeedElectrumMnemonicStartView)



class ToolsAddressExplorerAddressTypeView(View):
    RECEIVE = translator("Receive Addresses")
    CHANGE = translator("Change Addresses")


    def __init__(self, seed_num: int = None, script_type: str = None, custom_derivation: str = None):
        """
            If the explorer source is a seed, `seed_num` and `script_type` must be
            specified. `custom_derivation` can be specified as needed.

            If the source is a multisig or single sig wallet descriptor, `seed_num`,
            `script_type`, and `custom_derivation` should be `None`.
        """
        super().__init__()
        self.seed_num = seed_num
        self.script_type = script_type
        self.custom_derivation = custom_derivation
    
        network = self.settings.get_value(SettingsConstants.SETTING__NETWORK)

        # Store everything in the Controller's `address_explorer_data` so we don't have
        # to keep passing vals around from View to View and recalculating.
        data = dict(
            seed_num=seed_num,
            network=self.settings.get_value(SettingsConstants.SETTING__NETWORK),
            embit_network=SettingsConstants.map_network_to_embit(network),
            script_type=script_type,
        )
        if self.seed_num is not None:
            self.seed = self.controller.storage.seeds[seed_num]
            data["seed_num"] = self.seed
            seed_derivation_override = self.seed.derivation_override(sig_type=SettingsConstants.SINGLE_SIG)

            if self.script_type == SettingsConstants.CUSTOM_DERIVATION:
                derivation_path = self.custom_derivation
            elif seed_derivation_override:
                derivation_path = seed_derivation_override                
            else:
                derivation_path = embit_utils.get_standard_derivation_path(
                    network=self.settings.get_value(SettingsConstants.SETTING__NETWORK),
                    wallet_type=SettingsConstants.SINGLE_SIG,
                    script_type=self.script_type,
                )

            data["derivation_path"] = derivation_path
            data["xpub"] = self.seed.get_xpub(derivation_path, network=network)
        
        else:
            data["wallet_descriptor"] = self.controller.multisig_wallet_descriptor

        self.controller.address_explorer_data = data


    def run(self):
        data = self.controller.address_explorer_data

        wallet_descriptor_display_name = None
        if "wallet_descriptor" in data:
            wallet_descriptor_display_name = data["wallet_descriptor"].brief_policy.replace(" (sorted)", "")

        script_type = data["script_type"] if "script_type" in data else None

        button_data = [self.RECEIVE, self.CHANGE]

        selected_menu_num = self.run_screen(
            ToolsAddressExplorerAddressTypeScreen,
            button_data=button_data,
            fingerprint=self.seed.get_fingerprint() if self.seed_num is not None else None,
            wallet_descriptor_display_name=wallet_descriptor_display_name,
            script_type=script_type,
            custom_derivation_path=self.custom_derivation,
        )

        if selected_menu_num == RET_CODE__BACK_BUTTON:
            # If we entered this flow via an already-loaded seed's SeedOptionsView, we
            # need to clear the `resume_main_flow` so that we don't get stuck in a 
            # SeedOptionsView redirect loop.
            # TODO: Refactor to a cleaner `BackStack.get_previous_View_cls()`
            if len(self.controller.back_stack) > 1 and self.controller.back_stack[-2].View_cls == SeedOptionsView:
                # The BackStack has the current View on the top with the real "back" in second position.
                self.controller.resume_main_flow = None
                self.controller.address_explorer_data = None
            return Destination(BackStackView)
        
        elif button_data[selected_menu_num] in [self.RECEIVE, self.CHANGE]:
            return Destination(ToolsAddressExplorerAddressListView, view_args=dict(is_change=button_data[selected_menu_num] == self.CHANGE))



class ToolsAddressExplorerAddressListView(View):
    def __init__(self, is_change: bool = False, start_index: int = 0, selected_button_index: int = 0, initial_scroll: int = 0):
        super().__init__()
        self.is_change = is_change
        self.start_index = start_index
        self.selected_button_index = selected_button_index
        self.initial_scroll = initial_scroll


    def run(self):
        self.loading_screen = None

        addresses = []
        button_data = []
        data = self.controller.address_explorer_data
        addrs_per_screen = 10

        addr_storage_key = "receive_addrs"
        if self.is_change:
            addr_storage_key = "change_addrs"

        if addr_storage_key in data and len(data[addr_storage_key]) >= self.start_index + addrs_per_screen:
            # We already calculated this range of addresses; just retrieve them
            addresses = data[addr_storage_key][self.start_index:self.start_index + addrs_per_screen]

        else:
            try:
                from seedsigner.gui.screens.screen import LoadingScreenThread
                self.loading_screen = LoadingScreenThread(text=translator("Calculating addrs..."))
                self.loading_screen.start()

                if addr_storage_key not in data:
                    data[addr_storage_key] = []

                if "xpub" in data:
                    # Single sig explore from seed
                    if "script_type" in data and data["script_type"] != SettingsConstants.CUSTOM_DERIVATION:
                        # Standard derivation path
                        for i in range(self.start_index, self.start_index + addrs_per_screen):
                            address = embit_utils.get_single_sig_address(xpub=data["xpub"], script_type=data["script_type"], index=i, is_change=self.is_change, embit_network=data["embit_network"])
                            addresses.append(address)
                            data[addr_storage_key].append(address)
                    else:
                        # TODO: Custom derivation path
                        raise Exception(translator("Custom Derivation address explorer not yet implemented"))
                
                elif "wallet_descriptor" in data:
                    descriptor: Descriptor = data["wallet_descriptor"]
                    if descriptor.is_basic_multisig:
                        for i in range(self.start_index, self.start_index + addrs_per_screen):
                            address = embit_utils.get_multisig_address(descriptor=descriptor, index=i, is_change=self.is_change, embit_network=data["embit_network"])
                            addresses.append(address)
                            data[addr_storage_key].append(address)

                    else:
                        raise Exception(translator("Single sig descriptors not yet supported"))
            finally:
                # Everything is set. Stop the loading screen
                self.loading_screen.stop()

        for i, address in enumerate(addresses):
            cur_index = i + self.start_index

            # Adjust the trailing addr display length based on available room
            # (the index number will push it out on each order of magnitude)
            if cur_index < 10:
                end_digits = -6
            elif cur_index < 100:
                end_digits = -5
            else:
                end_digits = -4
            button_data.append(f"{cur_index}:{address[:8]}...{address[end_digits:]}")

        button_data.append((translator("Next {}").format(addrs_per_screen), None, None, None, SeedSignerIconConstants.CHEVRON_RIGHT))

        selected_menu_num = self.run_screen(
            ButtonListScreen,
            title=translator("{} Addrs").format("Receive" if not self.is_change else "Change"),
            button_data=button_data,
            button_font_name=GUIConstants.FIXED_WIDTH_EMPHASIS_FONT_NAME,
            button_font_size=GUIConstants.BUTTON_FONT_SIZE + 2,
            is_button_text_centered=False,
            is_bottom_list=True,
            selected_button=self.selected_button_index,
            scroll_y_initial_offset=self.initial_scroll,
        )

        if selected_menu_num == RET_CODE__BACK_BUTTON:
            return Destination(BackStackView)
        
        if selected_menu_num == len(addresses):
            # User clicked NEXT
            return Destination(ToolsAddressExplorerAddressListView, view_args=dict(is_change=self.is_change, start_index=self.start_index + addrs_per_screen))
        
        # Preserve the list's current scroll so we can return to the same spot
        initial_scroll = self.screen.buttons[0].scroll_y

        index = selected_menu_num + self.start_index
        return Destination(ToolsAddressExplorerAddressView, view_args=dict(index=index, address=addresses[selected_menu_num], is_change=self.is_change, start_index=self.start_index, parent_initial_scroll=initial_scroll), skip_current_view=True)



class ToolsAddressExplorerAddressView(View):
    def __init__(self, index: int, address: str, is_change: bool, start_index: int, parent_initial_scroll: int = 0):
        super().__init__()
        self.index = index
        self.address = address
        self.is_change = is_change
        self.start_index = start_index
        self.parent_initial_scroll = parent_initial_scroll

    
    def run(self):
        from seedsigner.gui.screens.screen import QRDisplayScreen
        qr_encoder = GenericStaticQrEncoder(data=self.address)
        self.run_screen(
            QRDisplayScreen,
            qr_encoder=qr_encoder,
        )
    
        # Exiting/Cancelling the QR display screen always returns to the list
        return Destination(ToolsAddressExplorerAddressListView, view_args=dict(is_change=self.is_change, start_index=self.start_index, selected_button_index=self.index - self.start_index, initial_scroll=self.parent_initial_scroll), skip_current_view=True)

def get_openssl_random(n):
    try:
        return subprocess.check_output(["openssl", "rand", str(n)], stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        raise RuntimeError("OpenSSL random generation failed")

def get_dev_random(n):
    try:
        with open("/dev/random", "rb") as f:
            return f.read(n)
    except IOError:
        raise RuntimeError("Failed to read from /dev/random")

def get_libsodium_random(n):
    return nacl.utils.random(n)

def sha3_256_hash(data):
    return hashlib.sha3_256(data).digest()

def xor_bytes(a, b):
    return bytes(x ^ y for x, y in zip(a, b))

def extract_bits(hash_value, num_bits):
    if num_bits > 256:
        raise ValueError("요청된 비트 수가 해시의 길이를 초과합니다.")
    
    bit_string = ''.join(format(byte, '08b') for byte in hash_value)
    return bit_string[:num_bits]

def generate_random_entropy(num_bits):
    ENTROPY_SIZE = 48

    openssl_bytes = get_openssl_random(ENTROPY_SIZE)
    dev_random_bytes = get_dev_random(ENTROPY_SIZE)
    libsodium_bytes = get_libsodium_random(ENTROPY_SIZE)

    openssl_hash = sha3_256_hash(openssl_bytes)
    dev_random_hash = sha3_256_hash(dev_random_bytes)
    libsodium_hash = sha3_256_hash(libsodium_bytes)

    xor_result = xor_bytes(xor_bytes(openssl_hash, dev_random_hash), libsodium_hash)

    final_hash = sha3_256_hash(xor_result)

    return final_hash[:num_bits // 8 + (1 if num_bits % 8 else 0)]

class ToolsRandomEntropyMnemonicLengthView(View):
    def run(self):
        TWELVE_WORDS = translator("12 words")
        TWENTY_FOUR_WORDS = translator("24 words")
        button_data = [TWELVE_WORDS, TWENTY_FOUR_WORDS]

        selected_menu_num = self.run_screen(
            ButtonListScreen,
            title=translator("Mnemonic Length"),
            button_data=button_data,
        )

        if selected_menu_num == RET_CODE__BACK_BUTTON:
            return Destination(BackStackView)
        
        if button_data[selected_menu_num] == TWELVE_WORDS:
            num_bits = 128
        else:
            num_bits = 256

        entropy = generate_random_entropy(num_bits)
        mnemonic = mnemonic_generation.generate_mnemonic_from_bytes(entropy)

        seed = Seed(mnemonic, wordlist_language_code=self.settings.get_value(SettingsConstants.SETTING__WORDLIST_LANGUAGE))
        self.controller.storage.set_pending_seed(seed)
        
        from seedsigner.views.seed_views import SeedWordsWarningView
        return Destination(SeedWordsWarningView, view_args={"seed_num": None}, clear_history=True)
"""
class ToolsCustomEntropyMnemonicLengthView(View):
    def run(self):
        TWELVE_WORDS = translator("12 words")
        TWENTY_FOUR_WORDS = translator("24 words")
        button_data = [TWELVE_WORDS, TWENTY_FOUR_WORDS]

        selected_menu_num = self.run_screen(
            ButtonListScreen,
            title=translator("Mnemonic Length"),
            button_data=button_data,
        )

        if selected_menu_num == RET_CODE__BACK_BUTTON:
            return Destination(BackStackView)
        
        if button_data[selected_menu_num] == TWELVE_WORDS:
            num_bits = 128
        else:
            num_bits = 256

        return Destination(ToolsCustomEntropyOptionsView)
"""
class ToolsCustomEntropyOptionsView(View):
    def __init__(self):
        super().__init__()

    def run(self):
        # 각 소스에 대한 엔트로피 길이를 확인
        sources = [
            ("ID", "ID", SeedSignerIconConstants.FINGERPRINT),
            ("PASSWORD", "Password", SeedSignerIconConstants.PASSPHRASE),
            ("DOOR", "Door", SeedSignerIconConstants.QRCODE),
            ("TURTLE", "Turtle", SeedSignerIconConstants.BITCOIN),
            ("MNEMONIC", "Mnemonic", SeedSignerIconConstants.SEEDS)
        ]

        if self.settings.get_value(SettingsConstants.SETTING__CUSTOM_ENTROPY_SEEDSIGNER_SETTINGS) == SettingsConstants.OPTION__ENABLED:
            sources.append(("SEEDSIGNER_SETTINGS", "Setting Entropy", SeedSignerIconConstants.SETTINGS))

        button_data = []
        for source, label, left_icon in sources:
            entropy_length = entropy_storage_instance.get_entropy_length(source)
            right_icon = SeedSignerIconConstants.CHECK if entropy_length > 0 else None
            text = translator(label) + (f" ({entropy_length} bits)" if entropy_length > 0 else "")
            button_data.append((text, left_icon, "", "", right_icon))  # icon_color, button_label_color에 빈 문자열

        selected_menu_num = self.run_screen(
            ButtonListScreenWithConfirm,
            title=translator("Custom"),
            is_bottom_list=True,
            is_button_text_centered=False,
            button_data=button_data,
        )

        # 선택된 메뉴 처리
        if selected_menu_num == RET_CODE__BACK_BUTTON:
            return Destination(CustomModeExitDialogView)
        elif selected_menu_num == CONFIRM_BUTTON:
            combined_entropy = entropy_storage_instance.get_combined_entropy()
            entropy_length = len(combined_entropy)
            logger.info(combined_entropy)
            logger.info(entropy_length)
            
            if 0 < entropy_length <= 128:
                return Destination(ConfirmAutoModeView)
            elif entropy_length > 128:
                return Destination(CustomEntropyWarningView)
            else:
                return Destination(CustomEntropyEmptyWarningView)

        # 선택된 소스에 맞는 뷰로 이동
        source_views = {
            "ID": SeedAddIDView,
            "PASSWORD": SeedAddPASSWORDView,
            "DOOR": ToolsCustomDoorEntropyView,
            "TURTLE": TurtleSeedGenerationView,
            "MNEMONIC": ToolsCustomMnemonicView
        }

        if self.settings.get_value(SettingsConstants.SETTING__CUSTOM_ENTROPY_SEEDSIGNER_SETTINGS) == SettingsConstants.OPTION__ENABLED:
            source_views["SEEDSIGNER_SETTINGS"] = CustomSettingsMenuView

        selected_source = sources[selected_menu_num][0]
        return Destination(source_views[selected_source])
        
class CustomModeExitDialogView(View):
    CONTINUE = translator("Continue Custom Mode")
    MAIN_MENU = (translator("Return to Main Menu"), None, None, "red")

    def __init__(self):
        super().__init__()

    def run(self):
        button_data = [self.CONTINUE, self.MAIN_MENU]
        
        selected_menu_num = self.run_screen(
            WarningScreen,
            title=translator("Exit Custom Mode?"),
            status_headline=None,
            text=translator("All progress in Custom Mode will be erased"),
            show_back_button=False,
            button_data=button_data,
        )

        if button_data[selected_menu_num] == self.CONTINUE:
            return Destination(BackStackView)
        elif button_data[selected_menu_num] == self.MAIN_MENU:
            entropy_storage_instance.clear_all_entropy()
            return Destination(MainMenuView)

additional_entropy = ''

class ConfirmAutoModeView(View):
    def run(self):
        AUTO_MODE = translator("Continue")
        GO_BACK = translator("Go Back")
        
        button_data = [AUTO_MODE, GO_BACK]
        
        selected_menu_num = self.run_screen(
            AutomodeStartScreen,
        )

        if button_data[selected_menu_num] == GO_BACK:
            return Destination(ToolsCustomEntropyOptionsView)
        elif button_data[selected_menu_num] == AUTO_MODE:
            existing_entropy = entropy_storage_instance.get_combined_entropy()
            existing_entropy_length = len(existing_entropy)
            required_entropy_bits = 256 - existing_entropy_length
            random_entropy_bytes = generate_random_entropy(256)
            random_entropy_bits = ''.join(format(byte, '08b') for byte in random_entropy_bytes)
            additional_entropy = random_entropy_bits[:required_entropy_bits]
            logger.info(f"Additional entropy set: {additional_entropy}")
            return Destination(ToolsAutoEntropyOptionsView)

class CustomEntropyWarningView(View):
    def run(self):
        button_data = [translator("Back to Custom")]
        
        selected_menu_num = self.run_screen(
            DireWarningScreen,
            title=translator("Entropy Warning"),
            status_headline=None,
            text=translator("Custom entropy must be 128 bits or less. Please reduce the amount of entropy."),
            show_back_button=False,
            button_data=button_data,
        )

        return Destination(ToolsCustomEntropyOptionsView)

class CustomEntropyEmptyWarningView(View):
    def run(self):
        button_data = [translator("Back to Custom")]
        
        selected_menu_num = self.run_screen(
            DireWarningScreen,
            title=translator("No Entropy"),
            status_headline=None,
            text=translator("No entropy has been added. Please add some entropy before confirming."),
            show_back_button=False,
            button_data=button_data,
        )

        return Destination(ToolsCustomEntropyOptionsView)

class ToolsCustomDoorEntropyView(View):
    def __init__(self):
        super().__init__()

    def door_to_binary(selfr, selected_door):        
        binary = format(selected_door, '08b')
        return binary

    def run(self):
        ret = self.run_screen(
            SeedDoorNumberScreen,
        )

        if ret == RET_CODE__BACK_BUTTON:
            return Destination(BackStackView)

        try:
            num_doors = int(ret)
        except ValueError:
            # Handle invalid input
            return Destination(WarningScreen, view_args={"text": translator("Invalid number of doors")})

        selected_doors = ""
        for i in range(num_doors):
            door_screen = ToolsCustomDoorEntropyScreen(
                title=translator("Select Door {}/{}").format(i+1, num_doors)
            )
            selected_door = door_screen.display()

            if selected_door == RET_CODE__BACK_BUTTON:
                return Destination(BackStackView)

            selected_doors += self.door_to_binary(selected_door)

        entropy_storage_instance.add_entropy("DOOR", selected_doors)
        selected_doors=""
        return Destination(BackStackView)
    
class TurtleSeedGenerationView(View):
    def run(self):
        # First, run SeedTurtleMovementNumberScreen to get the number of moves
        ret = self.run_screen(
            SeedTurtleMovementNumberScreen,
        )

        if ret == RET_CODE__BACK_BUTTON:
            return Destination(BackStackView)

        try:
            num_moves = int(ret)
        except ValueError:
            # Handle invalid input
            return Destination(WarningScreen, view_args={"text": translator("Invalid number of moves")})

        # Now run TurtleSeedGenerationScreen with the specified number of moves
        turtle_screen = TurtleSeedGenerationScreen(num_moves=num_moves)
        moves = turtle_screen.display()

        entropy_storage_instance.add_entropy("TURTLE", moves)
        return Destination(BackStackView)
class ToolsCustomMnemonicView(View):
    def run(self):
        ret = self.run_screen(
            SeedRandomMnemonicNumberScreen,
        )

        if ret == RET_CODE__BACK_BUTTON:
            return Destination(BackStackView)

        try:
            num_words = int(ret)
            if num_words < 0 or num_words > 24:
                raise ValueError
        except ValueError:
            return Destination(WarningScreen, view_args={"text": translator("Invalid number of words. Please enter a number between 0 and 24.")})
        if num_words == 0:
            entropy_storage_instance.remove_entropy("MNEMONIC")
            return Destination(ToolsCustomEntropyOptionsView)
        # Generate a full 24-word mnemonic
        entropy = generate_random_entropy(256)  # 256 bits for 24 words
        full_mnemonic = mnemonic_generation.generate_mnemonic_from_bytes(entropy)

        seed = Seed(full_mnemonic, wordlist_language_code=self.settings.get_value(SettingsConstants.SETTING__WORDLIST_LANGUAGE))
        self.controller.storage.set_pending_seed(seed)

        mnemonic_words = full_mnemonic[:num_words]
        mnemonic_bits = mnemonic_generation.mnemonic_to_bits(mnemonic_words, wordlist_language_code=self.settings.get_value(SettingsConstants.SETTING__WORDLIST_LANGUAGE))
        entropy_storage_instance.add_entropy("MNEMONIC", mnemonic_bits)
        return Destination(SeedWordsWarningView, view_args={"seed_num": None, "total_words": num_words}, clear_history=True)

def get_and_remove_entropy(num_bits):
    global additional_entropy
    if len(additional_entropy) < num_bits:
        raise ValueError("Not enough entropy available")
    entropy = additional_entropy[:num_bits]
    additional_entropy = additional_entropy[num_bits:]
    return entropy

class ToolsAutoEntropyOptionsView(View):
    def __init__(self):
        super().__init__()

    def run(self):
        global additional_entropy, auto_entropy_bits_num

        ID_AUTO = (translator("ID"), SeedSignerIconConstants.FINGERPRINT)
        PASSWORD_AUTO = (translator("Password"), SeedSignerIconConstants.PASSPHRASE)
        DOOR_AUTO = (translator("Door"), SeedSignerIconConstants.QRCODE)
        TURTLE_AUTO = (translator("Turtle"), SeedSignerIconConstants.BITCOIN)
        MNEMONIC_AUTO = (translator("Mnemonic"), SeedSignerIconConstants.SEEDS)

        button_data = []
        for source, (label, icon) in [
            ("ID", ID_AUTO),
            ("PASSWORD", PASSWORD_AUTO),
            ("DOOR", DOOR_AUTO),
            ("TURTLE", TURTLE_AUTO),
            ("MNEMONIC", MNEMONIC_AUTO)
        ]:
            num_bits = auto_entropy_bits_num.get(source, 0)
            text = translator(label)
            if num_bits > 0:
                text += f" ({num_bits} bits)"
            right_icon = SeedSignerIconConstants.CHECK if num_bits > 0 else None
            button_data.append((text, icon, "", "", right_icon))

        if self.settings.get_value(SettingsConstants.SETTING__CUSTOM_ENTROPY_SEEDSIGNER_SETTINGS) == SettingsConstants.OPTION__ENABLED:
            SEEDSIGNER_SETTINGS_AUTO = (translator("Setting Entropy"), SeedSignerIconConstants.SETTINGS)
            button_data.append(SEEDSIGNER_SETTINGS_AUTO)

        selected_menu_num = self.run_screen(
            ButtonListScreenWithConfirm,
            title=translator("Auto"),
            is_bottom_list=True,
            is_button_text_centered=False,
            button_data=button_data,
        )

        if selected_menu_num == RET_CODE__BACK_BUTTON:
            return Destination(ToolsCustomEntropyOptionsView)

        if selected_menu_num == CONFIRM_BUTTON:
            return Destination(BackStackView)

        selected_option = button_data[selected_menu_num][0].split(' ')[0].upper()

        if selected_option == "DOOR":
            title = "Number of Doors"
        elif selected_option == "TURTLE":
            title = "Number of Moves"
        elif selected_option == "MNEMONIC":
            title = "Number of Mnemonics"
        elif selected_option == "ID":
            title = "Length of ID"
        elif selected_option == "PASSWORD":
            title = "Length of Password"
        elif selected_option == "SETTING":
            selected_option = "SEEDSIGNER_SETTINGS"
            title = "Setting Entropy"

        return Destination(AutoEntropyNumberSelectionView, view_args={"title": title, "source": selected_option})
    
auto_entropy_bits_num = {}

class AutoEntropyNumberSelectionView(View):
    def __init__(self, title, source):
        super().__init__()
        self.title = title
        self.source = source

    def run(self):
        ret = self.run_screen(
            SeedBIP85SelectChildIndexScreen,
            title=self.title,
        )

        if ret == RET_CODE__BACK_BUTTON:
            return Destination(ToolsAutoEntropyOptionsView)

        try:
            number = int(ret)

            # Define the number of bits for each source
            bits_per_unit = {
                "ID": 6,
                "PASSWORD": 6,
                "DOOR": 8,
                "TURTLE": 3,
                "MNEMONIC": 11
            }

            if self.source in bits_per_unit:
                num_bits = number * bits_per_unit[self.source]
                auto_entropy_bits_num[self.source] = num_bits
                logger.info(f"Stored {num_bits} bits for {self.source} in auto mode")

            return Destination(ToolsAutoEntropyOptionsView)
        except ValueError:
            return Destination(WarningScreen, view_args={"text": translator("Invalid number entered")})
"""
        source_views = {
            "ID_AUTO": SeedAddIDAutoView,
            "PASSWORD_AUTO": SeedAddPASSWORDAutoView,
            "DOOR_AUTO": ToolsCustomDoorEntropyAutoView,
            "TURTLE_AUTO": TurtleSeedGenerationAutoView,
            "MNEMONIC_AUTO": ToolsCustomMnemonicAutoView
        }

        if self.settings.get_value(SettingsConstants.SETTING__CUSTOM_ENTROPY_SEEDSIGNER_SETTINGS) == SettingsConstants.OPTION__ENABLED:
            source_views["SEEDSIGNER_SETTINGS_AUTO"] = CustomSettingsMenuAutoView

        selected_source = button_data[selected_menu_num][0].split(' ')[0].upper() + '_AUTO'
        return Destination(source_views[selected_source])
"""