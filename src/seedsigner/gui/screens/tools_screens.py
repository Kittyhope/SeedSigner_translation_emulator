import time

from dataclasses import dataclass
from typing import Any
from PIL import Image, ImageDraw
from seedsigner.hardware.camera import Camera
from seedsigner.gui.components import FontAwesomeIconConstants, Fonts, GUIConstants, IconTextLine, SeedSignerIconConstants, TextArea

from seedsigner.gui.screens.screen import RET_CODE__BACK_BUTTON, BaseScreen, ButtonListScreen, KeyboardScreen, BaseTopNavScreen
from seedsigner.hardware.buttons import HardwareButtonsConstants
from seedsigner.models.settings_definition import SettingsConstants, SettingsDefinition
from seedsigner.views.language_views import translator


@dataclass
class ToolsImageEntropyLivePreviewScreen(BaseScreen):
    def __post_init__(self):
        # Customize defaults
        self.title = translator("Initializing Camera...")

        # Initialize the base class
        super().__post_init__()

        self.camera = Camera.get_instance()
        self.camera.start_video_stream_mode(resolution=(self.canvas_width, self.canvas_height), framerate=24, format="rgb")


    def _run(self):
        # save preview image frames to use as additional entropy below
        preview_images = []
        max_entropy_frames = 50
        instructions_font = Fonts.get_font(GUIConstants.BODY_FONT_NAME, GUIConstants.BUTTON_FONT_SIZE)

        while True:
            # Check for BACK button press
            if self.hw_inputs.check_for_low(HardwareButtonsConstants.KEY_LEFT):
                # Have to manually update last input time since we're not in a wait_for loop
                self.hw_inputs.update_last_input_time()
                self.words = []
                self.camera.stop_video_stream_mode()
                return RET_CODE__BACK_BUTTON

            frame = self.camera.read_video_stream(as_image=True)

            if frame is None:
                # Camera probably isn't ready yet
                time.sleep(0.01)
                continue

            # Check for joystick click to take final entropy image
            if self.hw_inputs.check_for_low(HardwareButtonsConstants.KEY_PRESS):
                # Have to manually update last input time since we're not in a wait_for loop
                self.hw_inputs.update_last_input_time()
                self.camera.stop_video_stream_mode()

                self.renderer.canvas.paste(frame)

                self.renderer.draw.text(
                    xy=(
                        int(self.renderer.canvas_width/2),
                        self.renderer.canvas_height - GUIConstants.EDGE_PADDING
                    ),
                    text=translator("Capturing image..."),
                    fill=GUIConstants.ACCENT_COLOR,
                    font=instructions_font,
                    stroke_width=4,
                    stroke_fill=GUIConstants.BACKGROUND_COLOR,
                    anchor="ms"
                )
                self.renderer.show_image()

                return preview_images

            # If we're still here, it's just another preview frame loop
            self.renderer.canvas.paste(frame)

            self.renderer.draw.text(
                xy=(
                    int(self.renderer.canvas_width/2),
                    self.renderer.canvas_height - GUIConstants.EDGE_PADDING
                ),
                text=translator("< back  |  click joystick"),
                fill=GUIConstants.BODY_FONT_COLOR,
                font=instructions_font,
                stroke_width=4,
                stroke_fill=GUIConstants.BACKGROUND_COLOR,
                anchor="ms"
            )
            self.renderer.show_image()

            if len(preview_images) == max_entropy_frames:
                # Keep a moving window of the last n preview frames; pop the oldest
                # before we add the currest frame.
                preview_images.pop(0)
            preview_images.append(frame)



@dataclass
class ToolsImageEntropyFinalImageScreen(BaseScreen):
    final_image: Image = None

    def _run(self):
        instructions_font = Fonts.get_font(GUIConstants.BODY_FONT_NAME, GUIConstants.BUTTON_FONT_SIZE)

        self.renderer.canvas.paste(self.final_image)
        self.renderer.draw.text(
            xy=(
                int(self.renderer.canvas_width/2),
                self.renderer.canvas_height - GUIConstants.EDGE_PADDING
            ),
            text=translator(" < reshoot  |  accept > "),
            fill=GUIConstants.BODY_FONT_COLOR,
            font=instructions_font,
            stroke_width=4,
            stroke_fill=GUIConstants.BACKGROUND_COLOR,
            anchor="ms"
        )
        self.renderer.show_image()

        input = self.hw_inputs.wait_for([HardwareButtonsConstants.KEY_LEFT, HardwareButtonsConstants.KEY_RIGHT])
        if input == HardwareButtonsConstants.KEY_LEFT:
            return RET_CODE__BACK_BUTTON



@dataclass
class ToolsDiceEntropyEntryScreen(KeyboardScreen):
    def __post_init__(self):
        # Override values set by the parent class
        self.title = translator("Dice Roll 1/{return_after_n_chars_}",return_after_n_chars_=self.return_after_n_chars)

        # Specify the keys in the keyboard
        self.rows = 3
        self.cols = 3
        self.keyboard_font_name = GUIConstants.ICON_FONT_NAME__FONT_AWESOME
        self.keyboard_font_size = None  # Force auto-scaling to Key height
        self.keys_charset = "".join([
            FontAwesomeIconConstants.DICE_ONE,
            FontAwesomeIconConstants.DICE_TWO,
            FontAwesomeIconConstants.DICE_THREE,
            FontAwesomeIconConstants.DICE_FOUR,
            FontAwesomeIconConstants.DICE_FIVE,
            FontAwesomeIconConstants.DICE_SIX,
        ])

        # Map Key display chars to actual output values
        self.keys_to_values = {
            FontAwesomeIconConstants.DICE_ONE: "1",
            FontAwesomeIconConstants.DICE_TWO: "2",
            FontAwesomeIconConstants.DICE_THREE: "3",
            FontAwesomeIconConstants.DICE_FOUR: "4",
            FontAwesomeIconConstants.DICE_FIVE: "5",
            FontAwesomeIconConstants.DICE_SIX: "6",
        }

        # Now initialize the parent class
        super().__post_init__()
    

    def update_title(self) -> bool:
        self.title = translator("Dice Roll {cursor_position_}/{return_after_n_chars_}",return_after_n_chars_=self.return_after_n_chars,cursor_position_=self.cursor_position + 1)
        return True



@dataclass
class ToolsCalcFinalWordFinalizePromptScreen(ButtonListScreen):
    mnemonic_length: int = None
    num_entropy_bits: int = None

    def __post_init__(self):
        self.title = translator("Build Final Word")
        self.is_bottom_list = True
        self.is_button_text_centered = True
        super().__post_init__()

        self.components.append(TextArea(
            text=translator("The {mnemonic_length_}th word is built from {num_entropy_bits_} more entropy bits plus auto-calculated checksum.",mnemonic_length_=self.mnemonic_length,num_entropy_bits_=self.num_entropy_bits),
            screen_y=self.top_nav.height + int(GUIConstants.COMPONENT_PADDING/2),
            font_name=GUIConstants.REGULAR_FONT_NAME
        ))



@dataclass
class ToolsCoinFlipEntryScreen(KeyboardScreen):
    def __post_init__(self):
        # Override values set by the parent class
        self.title = translator("Coin Flip 1/{return_after_n_chars_}",return_after_n_chars_=self.return_after_n_chars)

        # Specify the keys in the keyboard
        self.rows = 1
        self.cols = 4
        self.key_height = GUIConstants.TOP_NAV_TITLE_FONT_SIZE + 2 + 2*GUIConstants.EDGE_PADDING
        self.keys_charset = "10"

        # Now initialize the parent class
        super().__post_init__()
    
        self.components.append(TextArea(
            text=translator("Heads = 1"),
            screen_y = self.keyboard.rect[3] + 4*GUIConstants.COMPONENT_PADDING,
            font_name=GUIConstants.REGULAR_FONT_NAME
        ))
        self.components.append(TextArea(
            text=translator("Tails = 0"),
            screen_y = self.components[-1].screen_y + self.components[-1].height + GUIConstants.COMPONENT_PADDING,
            font_name=GUIConstants.REGULAR_FONT_NAME
        ))


    def update_title(self) -> bool:
        self.title = translator("Coin Flip {cursor_position_}/{return_after_n_chars_}",cursor_position_=self.cursor_position + 1,return_after_n_chars_=self.return_after_n_chars)
        return True



@dataclass
class ToolsCalcFinalWordScreen(ButtonListScreen):
    selected_final_word: str = None
    selected_final_bits: str = None
    checksum_bits: str = None
    actual_final_word: str = None

    def __post_init__(self):
        self.is_bottom_list = True
        super().__post_init__()

        # First what's the total bit display width and where do the checksum bits start?
        bit_font_size = GUIConstants.BUTTON_FONT_SIZE + 2
        font = Fonts.get_font(GUIConstants.FIXED_WIDTH_EMPHASIS_FONT_NAME, bit_font_size)
        (left, top, bit_display_width, bit_font_height) = font.getbbox("0" * 11, anchor="lt")
        (left, top, checksum_x, bottom) = font.getbbox("0" * (11 - len(self.checksum_bits)), anchor="lt")
        bit_display_x = int((self.canvas_width - bit_display_width)/2)
        checksum_x += bit_display_x

        # Display the user's additional entropy input
        if self.selected_final_word:
            selection_text = self.selected_final_word
            keeper_selected_bits = self.selected_final_bits[:11 - len(self.checksum_bits)]

            # The word's least significant bits will be rendered differently to convey
            # the fact that they're being discarded.
            discard_selected_bits = self.selected_final_bits[-1*len(self.checksum_bits):]
        else:
            # User entered coin flips or all zeros
            selection_text = self.selected_final_bits
            keeper_selected_bits = self.selected_final_bits

            # We'll append spacer chars to preserve the vertical alignment (most
            # significant n bits always rendered in same column)
            discard_selected_bits = "_" * (len(self.checksum_bits))

        self.components.append(TextArea(
            text=translator("Your input: \"{selection_text_}\"",selection_text_=selection_text),
            screen_y=self.top_nav.height + GUIConstants.COMPONENT_PADDING - 2,  # Nudge to last line doesn't get too close to "Next" button
            height_ignores_below_baseline=True,  # Keep the next line (bits display) snugged up, regardless of text rendering below the baseline
            font_name=GUIConstants.REGULAR_FONT_NAME
        ))

        # ...and that entropy's associated 11 bits
        screen_y = self.components[-1].screen_y + self.components[-1].height + GUIConstants.COMPONENT_PADDING
        first_bits_line = TextArea(
            text=keeper_selected_bits,
            font_name=GUIConstants.FIXED_WIDTH_EMPHASIS_FONT_NAME,
            font_size=bit_font_size,
            edge_padding=0,
            screen_x=bit_display_x,
            screen_y=screen_y,
            is_text_centered=False,
        )
        self.components.append(first_bits_line)

        # Render the least significant bits that will be replaced by the checksum in a
        # de-emphasized font color.
        if "_" in discard_selected_bits:
            screen_y += int(first_bits_line.height/2)  # center the underscores vertically like hypens
        self.components.append(TextArea(
            text=discard_selected_bits,
            font_name=GUIConstants.FIXED_WIDTH_EMPHASIS_FONT_NAME,
            font_color=GUIConstants.LABEL_FONT_COLOR,
            font_size=bit_font_size,
            edge_padding=0,
            screen_x=checksum_x,
            screen_y=screen_y,
            is_text_centered=False,
        ))

        # Show the checksum..
        self.components.append(TextArea(
            text=translator("Checksum"),
            edge_padding=0,
            screen_y=first_bits_line.screen_y + first_bits_line.height + 2*GUIConstants.COMPONENT_PADDING,
            font_name=GUIConstants.REGULAR_FONT_NAME
        ))

        # ...and its actual bits. Prepend spacers to keep vertical alignment
        checksum_spacer = "_" * (11 - len(self.checksum_bits))

        screen_y = self.components[-1].screen_y + self.components[-1].height + GUIConstants.COMPONENT_PADDING

        # This time we de-emphasize the prepended spacers that are irrelevant
        self.components.append(TextArea(
            text=checksum_spacer,
            font_name=GUIConstants.FIXED_WIDTH_EMPHASIS_FONT_NAME,
            font_color=GUIConstants.LABEL_FONT_COLOR,
            font_size=bit_font_size,
            edge_padding=0,
            screen_x=bit_display_x,
            screen_y=screen_y + int(first_bits_line.height/2),  # center the underscores vertically like hypens
            is_text_centered=False,
        ))

        # And especially highlight (orange!) the actual checksum bits
        self.components.append(TextArea(
            text=self.checksum_bits,
            font_name=GUIConstants.FIXED_WIDTH_EMPHASIS_FONT_NAME,
            font_size=bit_font_size,
            font_color=GUIConstants.ACCENT_COLOR,
            edge_padding=0,
            screen_x=checksum_x,
            screen_y=screen_y,
            is_text_centered=False,
        ))

        # And now the *actual* final word after merging the bit data
        self.components.append(TextArea(
            text=translator("Final Word: \"{actual_final_word_}\"",actual_final_word_=self.actual_final_word),
            screen_y=self.components[-1].screen_y + self.components[-1].height + 2*GUIConstants.COMPONENT_PADDING,
            height_ignores_below_baseline=True,  # Keep the next line (bits display) snugged up, regardless of text rendering below the baseline
            font_name=GUIConstants.REGULAR_FONT_NAME
        ))

        # Once again show the bits that came from the user's entropy...
        num_checksum_bits = len(self.checksum_bits)
        user_component = self.selected_final_bits[:11 - num_checksum_bits]
        screen_y = self.components[-1].screen_y + self.components[-1].height + GUIConstants.COMPONENT_PADDING
        self.components.append(TextArea(
            text=user_component,
            font_name=GUIConstants.FIXED_WIDTH_EMPHASIS_FONT_NAME,
            font_size=bit_font_size,
            edge_padding=0,
            screen_x=bit_display_x,
            screen_y=screen_y,
            is_text_centered=False,
        ))

        # ...and append the checksum's bits, still highlighted in orange
        self.components.append(TextArea(
            text=self.checksum_bits,
            font_name=GUIConstants.FIXED_WIDTH_EMPHASIS_FONT_NAME,
            font_color=GUIConstants.ACCENT_COLOR,
            font_size=bit_font_size,
            edge_padding=0,
            screen_x=checksum_x,
            screen_y=screen_y,
            is_text_centered=False,
        ))



@dataclass
class ToolsCalcFinalWordDoneScreen(ButtonListScreen):
    final_word: str = None
    mnemonic_word_length: int = 12
    fingerprint: str = None

    def __post_init__(self):
        # Customize defaults
        self.title = translator("{mnemonic_word_length_}th Word",mnemonic_word_length_=self.mnemonic_word_length)
        self.is_bottom_list = True

        super().__post_init__()

        self.components.append(TextArea(
            text=translator(f"""\"{self.final_word}\""""),
            font_size=GUIConstants.TOP_NAV_TITLE_FONT_SIZE + 6,
            is_text_centered=True,
            screen_y=self.top_nav.height + GUIConstants.COMPONENT_PADDING,
        ))

        self.components.append(IconTextLine(
            icon_name=SeedSignerIconConstants.FINGERPRINT,
            icon_color=GUIConstants.INFO_COLOR,
            label_text=translator("fingerprint"),
            value_text=self.fingerprint,
            is_text_centered=True,
            screen_y=self.components[-1].screen_y + self.components[-1].height + 3*GUIConstants.COMPONENT_PADDING,
        ))



@dataclass
class ToolsAddressExplorerAddressTypeScreen(ButtonListScreen):
    fingerprint: str = None
    wallet_descriptor_display_name: Any = None
    script_type: str = None
    custom_derivation_path: str = None

    def __post_init__(self):
        self.title = translator("Address Explorer")
        self.is_bottom_list = True
        super().__post_init__()

        if self.fingerprint:
            self.components.append(IconTextLine(
                icon_name=SeedSignerIconConstants.FINGERPRINT,
                icon_color=GUIConstants.INFO_COLOR,
                label_text=translator("Fingerprint"),
                value_text=self.fingerprint,
                screen_x=GUIConstants.EDGE_PADDING,
                screen_y=self.top_nav.height + GUIConstants.COMPONENT_PADDING,
            ))

            if self.script_type != SettingsConstants.CUSTOM_DERIVATION:
                self.components.append(IconTextLine(
                    icon_name=SeedSignerIconConstants.DERIVATION,
                    label_text=translator("Derivation"),
                    value_text=SettingsDefinition.get_settings_entry(attr_name=SettingsConstants.SETTING__SCRIPT_TYPES).get_selection_option_display_name_by_value(value=self.script_type),
                    screen_x=GUIConstants.EDGE_PADDING,
                    screen_y=self.components[-1].screen_y + self.components[-1].height + 2*GUIConstants.COMPONENT_PADDING,
                    font_name=GUIConstants.BODY_FONT_NAME
                ))
            else:
                self.components.append(IconTextLine(
                    icon_name=SeedSignerIconConstants.DERIVATION,
                    label_text=translator("Derivation"),
                    value_text=self.custom_derivation_path,
                    screen_x=GUIConstants.EDGE_PADDING,
                    screen_y=self.components[-1].screen_y + self.components[-1].height + 2*GUIConstants.COMPONENT_PADDING,
                    font_name=GUIConstants.BODY_FONT_NAME
                ))

        else:
            self.components.append(IconTextLine(
                label_text=translator("Wallet descriptor"),
                value_text=self.wallet_descriptor_display_name,
                is_text_centered=True,
                screen_x=GUIConstants.EDGE_PADDING,
                screen_y=self.top_nav.height + GUIConstants.COMPONENT_PADDING,
            ))

class DoorGrid:
    def __init__(self, canvas, image_draw, width, height, renderer):
        self.canvas = canvas
        self.image_draw = image_draw
        self.width = width
        self.height = height
        self.renderer = renderer
        self.grid_size = 16
        self.door_size = min(width, height) // (self.grid_size) 
        self.grid_start_x = (width - (self.door_size * self.grid_size)) // 2
        self.grid_start_y = (height - (self.door_size * self.grid_size)) // 2 + 46
        self.selected_x = 0
        self.selected_y = 0
        self.number_font = Fonts.get_font(GUIConstants.BODY_FONT_NAME, self.door_size-1)
        self.highlighted_font = Fonts.get_font(GUIConstants.BODY_FONT_NAME, self.door_size+1)

    def render(self):
        for x in range(self.grid_size):
            number = str(x + 1)
            bbox = self.image_draw.textbbox((0, 0), number, font=self.number_font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            if x == self.selected_x:
                font = self.highlighted_font
                color = GUIConstants.ACCENT_COLOR
            else:
                font = self.number_font
                color = GUIConstants.BODY_FONT_COLOR
            
            self.image_draw.text(
                (self.grid_start_x + x * self.door_size + self.door_size // 2, 
                 self.grid_start_y - self.door_size // 2 - 2),
                number,
                font=font,
                fill=color,
                anchor="mm"
            )

        for y in range(self.grid_size):
            number = str(y + 1)
            bbox = self.image_draw.textbbox((0, 0), number, font=self.number_font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            if y == self.selected_y:
                font = self.highlighted_font
                color = GUIConstants.ACCENT_COLOR
            else:
                font = self.number_font
                color = GUIConstants.BODY_FONT_COLOR
            
            self.image_draw.text(
                (self.grid_start_x - self.door_size // 2 - 2,
                 self.grid_start_y + y * self.door_size + self.door_size // 2),
                number,
                font=font,
                fill=color,
                anchor="mm"
            )

        for y in range(self.grid_size):
            for x in range(self.grid_size):
                door_x =  self.grid_start_x + x * self.door_size
                door_y =  self.grid_start_y + y * self.door_size
                color = "#353535"
                if x == self.selected_x and y == self.selected_y:
                    color = GUIConstants.ACCENT_COLOR
                self.image_draw.rectangle(
                    [door_x, door_y, door_x + self.door_size, door_y + self.door_size],
                    outline=color,
                    width=2
                )

    def move_selection(self, dx, dy):
        self.selected_x = (self.selected_x + dx) % self.grid_size
        self.selected_y = (self.selected_y + dy) % self.grid_size

    def get_selected_door(self):
        return self.selected_y * self.grid_size + self.selected_x

    def animate_door_open(self):
        door_x = self.grid_start_x + self.selected_x * self.door_size
        door_y = self.grid_start_y + self.selected_y * self.door_size
        
        # Create a new image for the door
        door_image = Image.new('RGBA', (self.door_size, self.door_size), (0, 0, 0, 0))
        door_draw = ImageDraw.Draw(door_image)

        # Draw the initial closed door
        door_draw.rectangle([0, 0, self.door_size, self.door_size], 
                            fill=GUIConstants.BUTTON_BACKGROUND_COLOR,
                            outline=GUIConstants.ACCENT_COLOR,
                            width=2)

        # Animate the door opening
        for i in range(self.door_size):
            # Clear the door image
            door_draw.rectangle([0, 0, self.door_size, self.door_size], fill=(0, 0, 0, 0))
            
            # Draw the opening door
            door_draw.rectangle([i, 0, self.door_size, self.door_size], 
                                fill=GUIConstants.BUTTON_BACKGROUND_COLOR,
                                outline=GUIConstants.ACCENT_COLOR,
                                width=2)
            
            # Paste the door image onto the main canvas
            self.canvas.paste(door_image, (door_x, door_y), door_image)
            
            # Update the display using the renderer
            self.renderer.show_image(self.canvas)
            time.sleep(0.05)

        self.renderer.show_image(self.canvas)

class ToolsCustomDoorEntropyScreen(BaseTopNavScreen):
    def __init__(self, title):
        super().__init__(title=title, show_back_button=False)
        self.top_nav.title.screen_y = -5
        self.door_grid = DoorGrid(
            canvas=self.canvas,
            image_draw=self.image_draw,
            width=self.canvas_width,
            height=self.canvas_height - self.top_nav.height,
            renderer=self.renderer
        )

    def _render(self):
        super()._render()  # This will render the title and back button
        self.door_grid.render()

    def _run(self):
        while True:
            input_event = self.hw_inputs.wait_for(HardwareButtonsConstants.ALL_KEYS)
            
            if input_event == HardwareButtonsConstants.KEY_PRESS:
                selected_door = self.door_grid.get_selected_door()
                self.door_grid.animate_door_open()
                time.sleep(0.35)
                return selected_door
            elif input_event == HardwareButtonsConstants.KEY_RIGHT:
                self.door_grid.move_selection(1, 0)
            elif input_event == HardwareButtonsConstants.KEY_LEFT:
                self.door_grid.move_selection(-1, 0)
            elif input_event == HardwareButtonsConstants.KEY_UP:
                self.door_grid.move_selection(0, -1)
            elif input_event == HardwareButtonsConstants.KEY_DOWN:
                self.door_grid.move_selection(0, 1)

            self._render()
            self.renderer.show_image()

class TurtleSeedGenerationScreen(BaseScreen):
    def __init__(self, num_moves):
        super().__init__()
        self.title = "Turtle Seed Generation"
        self.grid_size = 11
        self.turtle_x = 5
        self.turtle_y = 5
        self.grid = [[' ' for _ in range(self.grid_size)] for _ in range(self.grid_size)]
        self.moves = ""
        self.num_moves = num_moves
        self.cell_size = 18
        self.grid_start_x = (self.canvas_width - (self.cell_size * self.grid_size)) // 2
        self.grid_start_y = 0

    def draw_turtle(self, cell_x, cell_y):
        # Calculate the center of the cell
        center_x = cell_x + self.cell_size // 2
        center_y = cell_y + self.cell_size // 2

        # Define colors for turtle parts
        turtle_body_color = "#228B22"  # Turtle green color
        turtle_shell_color = "#006400"  # Darker green for shell

        # Reduce overall size slightly by decreasing the radius factors
        body_radius = (self.cell_size // 3) - 1  # Slightly smaller body
        head_radius = body_radius // 2 + 1 # Slightly smaller head
        leg_radius = body_radius // 2  # Slightly smaller legs
        tail_length = body_radius  # Slightly smaller tail

        # Turtle body (a large circle in the center)
        self.image_draw.ellipse(
            [center_x - body_radius, center_y - body_radius, center_x + body_radius, center_y + body_radius],
            fill=turtle_shell_color,
            outline="black"
        )

        # Turtle head (a smaller circle on top of the body)
        head_x = center_x
        head_y = center_y - body_radius - head_radius
        self.image_draw.ellipse(
            [head_x - head_radius, head_y - head_radius + 1, head_x + head_radius, head_y + head_radius + 1],
            fill=turtle_body_color,
            outline="black"
        )

        # Turtle legs (smaller circles at four corners)
        # Top-left leg
        self.image_draw.ellipse(
            [center_x - body_radius - leg_radius, center_y - body_radius - leg_radius, 
            center_x - body_radius + leg_radius, center_y - body_radius + leg_radius],
            fill=turtle_body_color,
            outline="black"
        )
        # Top-right leg
        self.image_draw.ellipse(
            [center_x + body_radius - leg_radius, center_y - body_radius - leg_radius, 
            center_x + body_radius + leg_radius, center_y - body_radius + leg_radius],
            fill=turtle_body_color,
            outline="black"
        )
        # Bottom-left leg
        self.image_draw.ellipse(
            [center_x - body_radius - leg_radius, center_y + body_radius - leg_radius, 
            center_x - body_radius + leg_radius, center_y + body_radius + leg_radius],
            fill=turtle_body_color,
            outline="black"
        )
        # Bottom-right leg
        self.image_draw.ellipse(
            [center_x + body_radius - leg_radius, center_y + body_radius - leg_radius, 
            center_x + body_radius + leg_radius, center_y + body_radius + leg_radius],
            fill=turtle_body_color,
            outline="black"
        )

        # Turtle tail (a small triangle at the bottom of the body)
        tail_x = center_x
        tail_y = center_y + body_radius
        self.image_draw.polygon(
            [(tail_x- (tail_length-2), tail_y), (tail_x + (tail_length-2), tail_y), (tail_x, tail_y + tail_length+1)],
            fill=turtle_body_color,
            outline="black"
        )

    def _render(self):
        super()._render()  # This will render the title
        
        # Render grid
        for y in range(self.grid_size):
            for x in range(self.grid_size):
                char = self.grid[y][x] if self.grid[y][x] != ' ' else ''
                cell_x = self.grid_start_x + x * self.cell_size
                cell_y = self.grid_start_y + y * self.cell_size
                
                # Draw cell border
                self.image_draw.rectangle(
                    [cell_x, cell_y, cell_x + self.cell_size, cell_y + self.cell_size],
                    outline="#B3B3B3"
                )
                
                if x == self.turtle_x and y == self.turtle_y:
                    # Draw the turtle using shapes instead of emoji
                    self.draw_turtle(cell_x, cell_y)
                else:
                    # Draw other characters
                    self.image_draw.text(
                        (cell_x + self.cell_size // 2, cell_y + self.cell_size // 2),
                        char,
                        fill=GUIConstants.BODY_FONT_COLOR,
                        font=Fonts.get_font(GUIConstants.BODY_FONT_NAME, self.cell_size - 4),
                        anchor="mm"
                    )

        # Render instructions
        instructions = "Up, Down, Left, Right | Press: P | Key 1/2/3: Number"
        TextArea(
            image_draw=self.image_draw,
            text=instructions,
            screen_y=self.canvas_height - 37,
            font_size=GUIConstants.BODY_FONT_SIZE - 2
        ).render()

    def _run(self):
        while len(self.moves)//3 < self.num_moves:
            self._render()
            self.renderer.show_image()

            input_event = self.hw_inputs.wait_for(HardwareButtonsConstants.ALL_KEYS)
            
            if input_event == HardwareButtonsConstants.KEY_UP:
                self.turtle_y = max(0, self.turtle_y - 1)
                self.moves += '000'
            elif input_event == HardwareButtonsConstants.KEY_DOWN:
                self.turtle_y = min(self.grid_size - 1, self.turtle_y + 1)
                self.moves += '001'
            elif input_event == HardwareButtonsConstants.KEY_LEFT:
                self.turtle_x = max(0, self.turtle_x - 1)
                self.moves += '010'
            elif input_event == HardwareButtonsConstants.KEY_RIGHT:
                self.turtle_x = min(self.grid_size - 1, self.turtle_x + 1)
                self.moves += '011'
            elif input_event == HardwareButtonsConstants.KEY_PRESS:
                self.grid[self.turtle_y][self.turtle_x] = 'P'
                self.moves += '100'
            elif input_event == HardwareButtonsConstants.KEY1:
                self.grid[self.turtle_y][self.turtle_x] = '1'
                self.moves += '101'
            elif input_event == HardwareButtonsConstants.KEY2:
                self.grid[self.turtle_y][self.turtle_x] = '2'
                self.moves += '110'
            elif input_event == HardwareButtonsConstants.KEY3:
                self.grid[self.turtle_y][self.turtle_x] = '3'
                self.moves += '111'

            if len(self.moves)//3 >= self.num_moves:
                break

        return self.moves