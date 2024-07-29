import json
import os

class LanguageTranslation:
    def __init__(self, language_code):
        self.language_code = language_code
        self.translations = self.load_translations()

    def load_translations(self):
        file_path = os.path.join(os.path.dirname(__file__), '..', 'language', f'{self.language_code}.json')
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Translation file {self.language_code}.json not found.")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def translate(self, text):
        return self.translations.get(text, text)
