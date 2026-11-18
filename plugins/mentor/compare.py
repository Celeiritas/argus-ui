# Exact comparison for answers that have one right value (4.55): a predicted output, the value after a trace step.
# Only layout is forgiven: spaces at the ends, runs of spaces and line breaks, and spaces beside brackets, commas, colons and
# '='. Everything that changes the meaning is kept: signs (12 vs -12), operators (a+b vs a-b), order (1 2 vs 2 1), case and
# any script (猫 stays 猫). Unicode is put in one form (NFC) first, so a decomposed é equals the composed one.
# No keyword counting and no fuzzy spelling: a near miss is a miss, and the learner sees both.
import re, unicodedata

_TIGHT = re.compile(r'\s*([,()\[\]{}:=])\s*')

def canon(s):
    """The typed text with only its layout (and Unicode form) normalised."""
    s = re.sub(r'\s+', ' ', unicodedata.normalize('NFC', str(s)).strip())
    return _TIGHT.sub(r'\1', s)

def same_value(typed, accepted):
    """True when the typed answer equals one accepted wording, layout aside. An empty answer never matches."""
    t = canon(typed)
    return bool(t) and any(t == canon(a) for a in accepted if str(a).strip())
