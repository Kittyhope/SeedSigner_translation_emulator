from typing import List
from seedsigner.models.seed import Seed, ElectrumSeed, InvalidSeedException
from seedsigner.models.settings_definition import SettingsConstants



class SeedStorage:
    def __init__(self) -> None:
        self.seeds: List[Seed] = []
        self.pending_seed: Seed = None
        self._pending_mnemonic: List[str] = []
        self._pending_is_electrum : bool = False


    def set_pending_seed(self, seed: Seed):
        self.pending_seed = seed


    def get_pending_seed(self) -> Seed:
        return self.pending_seed


    def finalize_pending_seed(self) -> int:
        # Finally store the pending seed and return its index
        if self.pending_seed in self.seeds:
            index = self.seeds.index(self.pending_seed)
        else:
            self.seeds.append(self.pending_seed)
            index = len(self.seeds) - 1
        self.pending_seed = None
        return index


    def clear_pending_seed(self):
        self.pending_seed = None


    def validate_mnemonic(self, mnemonic: List[str]) -> bool:
        try:
            Seed(mnemonic=mnemonic)
        except InvalidSeedException as e:
            return False
        
        return True


    def num_seeds(self):
        return len(self.seeds)
    

    @property
    def pending_mnemonic(self) -> List[str]:
        # Always return a copy so that the internal List can't be altered
        return list(self._pending_mnemonic)


    @property
    def pending_mnemonic_length(self) -> int:
        return len(self._pending_mnemonic)


    def init_pending_mnemonic(self, num_words:int = 12, is_electrum:bool = False):
        self._pending_mnemonic = [None] * num_words
        self._pending_is_electrum = is_electrum


    def update_pending_mnemonic(self, word: str, index: int):
        """
        Replaces the nth word in the pending mnemonic.

        * may specify a negative `index` (e.g. -1 is the last word).
        """
        if index >= len(self._pending_mnemonic):
            raise Exception(f"index {index} is too high")
        self._pending_mnemonic[index] = word
    

    def get_pending_mnemonic_word(self, index: int) -> str:
        if index < len(self._pending_mnemonic):
            return self._pending_mnemonic[index]
        return None
    

    def get_pending_mnemonic_fingerprint(self, network: str = SettingsConstants.MAINNET) -> str:
        try:
            if self._pending_is_electrum:
                seed = ElectrumSeed(self._pending_mnemonic)
            else:
                seed = Seed(self._pending_mnemonic)
            return seed.get_fingerprint(network)
        except InvalidSeedException:
            return None


    def convert_pending_mnemonic_to_pending_seed(self):
        if self._pending_is_electrum:
            self.pending_seed = ElectrumSeed(self._pending_mnemonic)
        else:
            self.pending_seed = Seed(self._pending_mnemonic)
        self.discard_pending_mnemonic()
    

    def discard_pending_mnemonic(self):
        self._pending_mnemonic = []
        self._pending_is_electrum = False

class EntropyStorage:
    ENTROPY_COMBINE_ORDER = [
        "ID", "PASSWORD", "DOOR", "TURTLE", "SEEDSIGNER_SETTINGS", "MNEMONIC",
        "ID_AUTO", "PASSWORD_AUTO", "DOOR_AUTO", "TURTLE_AUTO", "SEEDSIGNER_SETTINGS_AUTO", "MNEMONIC_AUTO"
    ]

    def __init__(self):
        self.entropy_sources = {}

    def add_entropy(self, source: str, entropy: str):
        """
        Adds or updates the entropy for a given source.
        """
        self.entropy_sources[source] = entropy

    def get_entropy(self, source: str):
        """
        Retrieves the entropy for a given source.
        """
        return self.entropy_sources.get(source, "")

    def remove_entropy(self, source: str):
        """
        Removes the entropy for a given source.
        """
        self.entropy_sources.pop(source, None)

    def get_all_entropy_sources(self):
        """
        Returns a list of all entropy sources that have been added.
        """
        return list(self.entropy_sources.keys())

    def clear_all_entropy(self):
        """
        Clears all stored entropy.
        """
        self.entropy_sources.clear()

    def get_combined_entropy(self):
        """
        Returns all entropy sources combined in the specified order.
        Only includes sources that have been added.
        """
        return "".join(self.entropy_sources.get(source, "") for source in self.ENTROPY_COMBINE_ORDER if source in self.entropy_sources)
    
    def has_valid_entropy(self, source: str) -> bool:
        """
        Checks if the given source has a non-None entropy value.
        
        Args:
            source (str): The entropy source to check.
        
        Returns:
            bool: True if the source exists and has a non-None entropy value, False otherwise.
        """
        return source in self.entropy_sources and self.entropy_sources[source] is not None
    
    def get_entropy_length(self, source: str) -> int:
        entropy_len = self.get_entropy(source)
        return len(entropy_len) if entropy_len else 0
    
entropy_storage_instance = EntropyStorage()