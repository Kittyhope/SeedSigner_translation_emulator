from dataclasses import dataclass
from PIL import ImageFont
import os
from seedsigner.gui.components import Button, TextArea, GUIConstants, Fonts
from seedsigner.gui.screens.screen import BaseScreen
from seedsigner.hardware.buttons import HardwareButtonsConstants

@dataclass
class LanguageSelectionScreen(BaseScreen):
    BUTTON_WIDTH = 100
    BUTTON_HEIGHT = 40

    def __post_init__(self):
        super().__post_init__()

        if hasattr(self, 'create_top_nav'):
            self.top_nav = self.create_top_nav()
        else:
            self.top_nav = None

        self.title = "Select Language"

        # Create a TextArea for instructions
        self.instructions_text = TextArea(
            text="Select Language:",
            font_size=GUIConstants.BODY_FONT_MAX_SIZE,
            is_text_centered=True,
            auto_line_break=True,
            screen_y=(self.top_nav.height + GUIConstants.COMPONENT_PADDING) if self.top_nav else GUIConstants.COMPONENT_PADDING
        )
        self.components.append(self.instructions_text)

        # 폰트 경로 설정
        current_dir = os.path.dirname(os.path.abspath(__file__))
        font_dir = os.path.join(current_dir, '..', '..', 'resources', 'fonts')

        # 폰트 파일명과 크기 설정
        fonts = {
            'Korean': ImageFont.truetype(os.path.join(font_dir, 'NotoSansKR-SemiBold.ttf'), GUIConstants.BODY_FONT_MAX_SIZE),
            'English': ImageFont.truetype(os.path.join(font_dir, 'NotoSansEN-SemiBold.ttf'), GUIConstants.BODY_FONT_MAX_SIZE),
            'Japaneese': ImageFont.truetype(os.path.join(font_dir, 'NotoSansJP-SemiBold.ttf'), GUIConstants.BODY_FONT_MAX_SIZE),
            'Chineese': ImageFont.truetype(os.path.join(font_dir, 'NotoSansSC-SemiBold.ttf'), GUIConstants.BODY_FONT_MAX_SIZE),
            'Hongkong': ImageFont.truetype(os.path.join(font_dir, 'NotoSansHK-SemiBold.ttf'), GUIConstants.BODY_FONT_MAX_SIZE),
            'Italic': ImageFont.truetype(os.path.join(font_dir, 'NotoSansIT-SemiBold.ttf'), GUIConstants.BODY_FONT_MAX_SIZE)
        }

        # Create a list of languages
        self.languages = [
            "English", "한국어", "Español", "Français", 
            "Deutsch", "中文", "日本語", "Italiano"
        ]
        self.language_buttons = []

        # Position languages in two columns
        column_1_x = (self.canvas_width // 4) - (self.BUTTON_WIDTH // 2)
        column_2_x = (self.canvas_width * 3 // 4) - (self.BUTTON_WIDTH // 2)
        column_positions = [column_1_x, column_2_x]

        button_y = self.instructions_text.screen_y + self.instructions_text.height + GUIConstants.COMPONENT_PADDING
        for i, language in enumerate(self.languages):
            col = i % 2
            row = i // 2
            button_x = column_positions[col]
            button = Button(
                text=language,
                screen_x=button_x,
                screen_y=button_y + (row * (self.BUTTON_HEIGHT + GUIConstants.COMPONENT_PADDING)),
                width=self.BUTTON_WIDTH,
                height=self.BUTTON_HEIGHT
            )
            # 언어에 따라 폰트 선택 및 적용
            if language == "한국어":
                button.font = fonts['Korean']
            elif language == "English":
                button.font = fonts['English']
            elif language == "日本語":
                button.font = fonts['Japaneese']
            elif language == "中文":
                button.font = fonts['Chineese']
            elif language == "香港":
                button.font = fonts['Hongkong']
            elif language == "Italic":
                button.font = fonts['Italic']
            else:
                button.font = fonts['English']  # 기본 폰트는 English로 설정
            self.language_buttons.append(button)
            self.components.append(button)

        # Initialize selected language index
        self.selected_language_index = 0
        self.language_buttons[self.selected_language_index].is_selected = True

    def _run(self):
        while True:
            input = self.hw_inputs.wait_for(
                [HardwareButtonsConstants.KEY_PRESS, HardwareButtonsConstants.KEY_DOWN, HardwareButtonsConstants.KEY_UP, HardwareButtonsConstants.KEY_LEFT, HardwareButtonsConstants.KEY_RIGHT]
            )

            if input in [HardwareButtonsConstants.KEY_UP, HardwareButtonsConstants.KEY_DOWN,
                         HardwareButtonsConstants.KEY_LEFT, HardwareButtonsConstants.KEY_RIGHT]:
                self.language_buttons[self.selected_language_index].is_selected = False
                self.language_buttons[self.selected_language_index].render()  # 선택 해제 후 다시 그리기

                if input == HardwareButtonsConstants.KEY_UP:
                    if self.selected_language_index >= 2:
                        self.selected_language_index -= 2
                elif input == HardwareButtonsConstants.KEY_DOWN:
                    if self.selected_language_index + 2 < len(self.languages):
                        self.selected_language_index += 2
                elif input == HardwareButtonsConstants.KEY_LEFT:
                    if self.selected_language_index % 2 != 0:
                        self.selected_language_index -= 1
                elif input == HardwareButtonsConstants.KEY_RIGHT:
                    if self.selected_language_index % 2 == 0 and self.selected_language_index + 1 < len(self.languages):
                        self.selected_language_index += 1

                self.language_buttons[self.selected_language_index].is_selected = True
                self.language_buttons[self.selected_language_index].render()  # 선택된 버튼 다시 그리기

                self.renderer.show_image()

            elif input == HardwareButtonsConstants.KEY_PRESS:
                selected_language = self.languages[self.selected_language_index]
                self._apply_language(selected_language)
                return selected_language  # 선택된 언어 반환

    def _apply_language(self, language):
        # Here you can implement the logic to change the language of the application
        print(f"Language selected: {language}")
        # 예: self.settings.language = language
