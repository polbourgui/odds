"""Name normalization used to match team/player/competition names across
providers before falling back to fuzzy matching or the alias tables."""

import re
import unicodedata
from difflib import SequenceMatcher

# Generic club-suffix tokens that vary by source ("Arsenal FC" vs "Arsenal")
# and would otherwise defeat an exact match.
_NOISE_TOKENS = {"fc", "cf", "afc", "sc", "ac", "cd", "ss", "club", "calcio", "cfc"}

_NON_ALNUM_RE = re.compile(r"[^a-z0-9\s]")


def normalize_name(name: str) -> str:
    """Lowercase, strip accents/punctuation, and drop generic club suffixes."""
    text = unicodedata.normalize("NFKD", name)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = _NON_ALNUM_RE.sub(" ", text)
    tokens = [t for t in text.split() if t and t not in _NOISE_TOKENS]
    return " ".join(tokens)


def similarity(a: str, b: str) -> float:
    """Ratio in [0, 1] between two already-normalized strings."""
    return SequenceMatcher(None, a, b).ratio()
