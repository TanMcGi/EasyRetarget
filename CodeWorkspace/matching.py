# =====================================================================
# EasyRetarget - matching.py
# AutoPopulate bone matching algorithm.
#
# Pipeline per bone name:
#   1. Strip known rig prefixes (DEF-, ORG-, mixamorig:, etc.)
#   2. Strip known rig suffixes (_jnt, _bind, etc.)
#   3. Extract and remove side token → 'L', 'R', or ''
#   4. Extract and remove trailing segment number → int or None
#   5. Tokenize: split camelCase, lowercase, remove separators
#   6. Detect pole/aim/target bones
#   7. Detect finger identity (named or numbered)
#   8. Detect toe identity (named or numbered, only if not a finger)
#   9. Synonym lookup → canonical anatomical name + confidence level
#
# Matching rules:
#   - Side must match exactly.
#   - Pole/aim status must match (pole only matches pole).
#   - Finger bones match on (finger_identity, segment) compound key.
#   - Toe bones match on (toe_identity, segment) compound key.
#   - Regular bones match on canonical name.
#   - Low-confidence synonyms (bare 'arm', bare 'leg') produce WARNING.
#   - Multiple candidates produce WARNING; zero candidates produce ERROR.
# =====================================================================

import re
from typing import Optional


# ── Rig prefix / suffix stripping ────────────────────────────────────

# Longer / more-specific prefixes must come before shorter ones.
RIG_PREFIXES = (
    'mixamorig:',
    'Bip01_',
    'CC_Base_',
    'ValveBiped_',
    'DEF-',
    'ORG-',
    'MCH-',
    'CTRL-',
    'b_',
)

RIG_SUFFIXES = ('_jnt', '_jt', '_bind', '_bone', '_def')


# ── Pole / aim keyword set ────────────────────────────────────────────

POLE_KEYWORDS = frozenset({'pole', 'target', 'aim'})


# ── Synonym table ─────────────────────────────────────────────────────
# Maps a canonical anatomical name to the set of accepted normalized
# tokens (all lowercase, separators removed).

SYNONYM_TABLE: dict[str, frozenset] = {
    'thigh':    frozenset({'thigh', 'upperleg', 'upleg'}),
    'shin':     frozenset({'shin', 'knee', 'lowerleg', 'lowleg', 'calf'}),
    'foot':     frozenset({'foot', 'ankle'}),
    'toe':      frozenset({'toe', 'toes', 'ball'}),
    'hips':     frozenset({'hips', 'hip', 'pelvis'}),
    'spine':    frozenset({'spine', 'back'}),
    'chest':    frozenset({'chest', 'thorax', 'upperchest'}),
    'neck':     frozenset({'neck'}),
    'head':     frozenset({'head'}),
    'jaw':      frozenset({'jaw', 'mandible'}),
    'shoulder': frozenset({'shoulder', 'clavicle', 'collar', 'collarbone'}),
    'upperarm': frozenset({'upperarm'}),
    'forearm':  frozenset({'forearm', 'lowerarm', 'elbow'}),
    'hand':     frozenset({'hand', 'wrist'}),
    'eye':      frozenset({'eye'}),
}

# Tokens that match but with low confidence — user should confirm.
LOW_CONFIDENCE_SYNONYMS: dict[str, str] = {
    'arm': 'upperarm',   # ambiguous without 'upper' qualifier
    'leg': 'thigh',      # ambiguous without 'upper' qualifier
}

# ── Finger synonym table ──────────────────────────────────────────────

FINGER_SYNONYMS: dict[str, frozenset] = {
    'thumb':  frozenset({'thumb'}),
    'index':  frozenset({'index', 'pointer', 'indexfinger', 'forefinger'}),
    'middle': frozenset({'middle', 'middlefinger'}),
    'ring':   frozenset({'ring', 'ringfinger'}),
    'pinky':  frozenset({'pinky', 'little', 'pinkyfinger', 'littlefinger', 'pinkie'}),
}

# Numbered finger mapping when a thumb bone exists separately.
# Finger1 = index, Finger2 = middle, …
_NUM_WITH_THUMB: dict[int, str]    = {1: 'index', 2: 'middle', 3: 'ring', 4: 'pinky'}
# Numbered finger mapping when no separate thumb bone exists.
# Finger1 = thumb, Finger2 = index, …
_NUM_WITHOUT_THUMB: dict[int, str] = {1: 'thumb', 2: 'index', 3: 'middle', 4: 'ring', 5: 'pinky'}


# ── Toe identity tables ───────────────────────────────────────────────
# Maps a toe-part token (prefix or suffix of a compound toe name) to a
# canonical toe identity string.  Used by _detect_toe().
#
# Detection handles three compound forms:
#   ends-with 'toe':  bigtoe, secondtoe, ringtoe   → strip 'toe' suffix
#   starts-with 'toe': toebig, toering, toe1        → strip 'toe' prefix
#   standalone known terms: halux, hallux            → direct lookup

_TOE_PART_IDENTITY: dict[str, str] = {
    # big / first toe
    'big':    'big',
    'first':  'big',
    'gross':  'big',
    # second toe
    'second': 'second',
    'index':  'second',
    # middle / third toe
    'middle': 'middle',
    'third':  'middle',
    # fourth / ring toe
    'fourth': 'fourth',
    'ring':   'fourth',
    # little / fifth toe
    'little': 'little',
    'fifth':  'little',
    'pinky':  'little',
    'small':  'little',
}

# Full-token names that unambiguously identify a specific toe without
# needing a 'toe' prefix or suffix.
_TOE_STANDALONE: dict[str, str] = {
    'halux':   'big',
    'hallux':  'big',
}

# Numbered toe mapping — big toe is always toe 1 for toes.
_TOE_NUM: dict[int, str] = {
    1: 'big',
    2: 'second',
    3: 'middle',
    4: 'fourth',
    5: 'little',
}


# ── Toe detection helper ──────────────────────────────────────────────

def _detect_toe(token: str) -> tuple[bool, str]:
    """
    Determine whether a normalized token represents an individual toe bone.
    Returns (is_toe, toe_identity) where toe_identity is one of:
    'big', 'second', 'middle', 'fourth', 'little', or '' if not a toe.

    Detection is intentionally conservative: the token must contain 'toe'
    as a prefix or suffix, or be a known standalone toe term (halux/hallux).
    A bare 'toe' token (the generic toe bone) is NOT treated as an individual
    toe identity — it falls through to the synonym table as canonical 'toe'.
    """
    # Standalone unambiguous toe terms.
    if token in _TOE_STANDALONE:
        return True, _TOE_STANDALONE[token]

    # Compound: ends with 'toe' (bigtoe, secondtoe, ringtoe, firsttoe, …)
    if token.endswith('toe') and len(token) > 3:
        part = token[:-3]
        if part in _TOE_PART_IDENTITY:
            return True, _TOE_PART_IDENTITY[part]

    # Compound: starts with 'toe' (toebig, toering, toesecond, toe1, …)
    if token.startswith('toe') and len(token) > 3:
        part = token[3:]
        if part in _TOE_PART_IDENTITY:
            return True, _TOE_PART_IDENTITY[part]
        # Numbered: toe1, toe2, …
        if part.isdigit():
            num = int(part)
            if num in _TOE_NUM:
                return True, _TOE_NUM[num]

    return False, ''


# ── Build reverse lookups at import time ──────────────────────────────

# token → (canonical_name, low_confidence: bool)
_SYNONYM_REVERSE: dict[str, tuple[str, bool]] = {}
for _canon, _syns in SYNONYM_TABLE.items():
    for _s in _syns:
        _SYNONYM_REVERSE[_s] = (_canon, False)
for _syn, _canon in LOW_CONFIDENCE_SYNONYMS.items():
    _SYNONYM_REVERSE[_syn] = (_canon, True)

# token → finger canonical name
_FINGER_REVERSE: dict[str, str] = {}
for _canon, _syns in FINGER_SYNONYMS.items():
    for _s in _syns:
        _FINGER_REVERSE[_s] = _canon


# ── Text helpers ──────────────────────────────────────────────────────

_CAMEL_RE1 = re.compile(r'([a-z0-9])([A-Z])')
_CAMEL_RE2 = re.compile(r'([A-Z]+)([A-Z][a-z])')


def _split_camel(text: str) -> str:
    """Insert a space at camelCase transitions."""
    s = _CAMEL_RE1.sub(r'\1 \2', text)
    s = _CAMEL_RE2.sub(r'\1 \2', s)
    return s


# Separator-based side suffix patterns, checked in order.
_SIDE_SUFFIX_PATTERNS = [
    (re.compile(r'[._\- ]left$',  re.IGNORECASE), 'L'),
    (re.compile(r'[._\- ]right$', re.IGNORECASE), 'R'),
    (re.compile(r'[._\- ][lL]$'),                  'L'),
    (re.compile(r'[._\- ][rR]$'),                  'R'),
]


def _extract_side(text: str) -> tuple[str, str]:
    """
    Detect and remove a side token from a bone name.
    Returns (cleaned_text, side) where side is 'L', 'R', or ''.
    Handles separator suffixes (.L, _R, etc.), word-prefix Left/Right,
    and camelCase suffix UpperArmLeft / LeftUpperArm.
    """
    # Separator-based suffixes (most common case).
    for pat, side in _SIDE_SUFFIX_PATTERNS:
        m = pat.search(text)
        if m:
            return text[:m.start()].strip('._- '), side

    # Separator-based or bare prefixes: Left… / Right…
    lower = text.lower()
    if lower.startswith('left'):
        remainder = text[4:].lstrip('._- ')
        return remainder, 'L'
    if lower.startswith('right'):
        remainder = text[5:].lstrip('._- ')
        return remainder, 'R'

    # CamelCase suffix: UpperArmLeft / UpperArmRight
    tokens = re.split(r'[\s._\-]+', _split_camel(text).strip())
    if tokens and tokens[-1].lower() == 'left':
        cleaned = re.sub(r'Left$', '', text, flags=re.IGNORECASE).strip('._- ')
        return cleaned, 'L'
    if tokens and tokens[-1].lower() == 'right':
        cleaned = re.sub(r'Right$', '', text, flags=re.IGNORECASE).strip('._- ')
        return cleaned, 'R'

    return text, ''


_SEGMENT_RE = re.compile(r'[._\-]?(\d{1,3})$')


def _extract_segment(text: str) -> tuple[str, Optional[int], bool]:
    """
    Strip a trailing segment number.
    Returns (cleaned_text, segment_int_or_None, had_separator).

    had_separator is True when the digit was preceded by a separator
    character (. _ -), e.g. 'toe.01' → had_separator=True.
    It is False when the digit was directly attached, e.g. 'toe1' → False.
    This distinction is used to tell apart toe identity numbers (toe1 = big
    toe, no separator) from bone segment numbers (toe.01, with separator).
    """
    m = _SEGMENT_RE.search(text)
    if m:
        had_sep = len(m.group(0)) > len(m.group(1))  # separator char present
        return text[:m.start()].rstrip('._- '), int(m.group(1)), had_sep
    return text, None, False


def _strip_prefixes(name: str) -> str:
    for prefix in RIG_PREFIXES:
        if name.startswith(prefix):
            return name[len(prefix):]
        # Case-insensitive fallback.
        if name.lower().startswith(prefix.lower()):
            return name[len(prefix):]
    return name


def _strip_suffixes(name: str) -> str:
    lower = name.lower()
    for suffix in RIG_SUFFIXES:
        if lower.endswith(suffix):
            return name[:-len(suffix)]
    return name


def _tokenize(text: str) -> str:
    """
    Convert to a compact lowercase token: split camelCase, remove all
    separator characters (spaces, underscores, dashes, dots).
    """
    text = _split_camel(text)
    text = re.sub(r'[\s._\-]+', '', text)
    return text.lower()


# ── NormalizedBone ────────────────────────────────────────────────────

class NormalizedBone:
    """Holds the result of the full normalization pipeline for one bone."""

    __slots__ = (
        'original', 'side', 'segment', 'is_pole',
        'is_finger', 'finger_identity',
        'is_toe',   'toe_identity',
        'canonical', 'low_confidence',
    )

    def __init__(
        self,
        original: str,
        side: str,
        segment: Optional[int],
        is_pole: bool,
        is_finger: bool,
        finger_identity: str,
        is_toe: bool,
        toe_identity: str,
        canonical: str,
        low_confidence: bool,
    ):
        self.original        = original
        self.side            = side
        self.segment         = segment
        self.is_pole         = is_pole
        self.is_finger       = is_finger
        self.finger_identity = finger_identity
        self.is_toe          = is_toe
        self.toe_identity    = toe_identity
        self.canonical       = canonical
        self.low_confidence  = low_confidence

    def __repr__(self) -> str:
        return (
            f"NormalizedBone({self.original!r}, side={self.side!r}, "
            f"seg={self.segment}, pole={self.is_pole}, "
            f"finger={self.finger_identity!r}, toe={self.toe_identity!r}, "
            f"canonical={self.canonical!r}, low={self.low_confidence})"
        )


def normalize_bone(name: str, has_separate_thumb: bool = True) -> NormalizedBone:
    """Run the full normalization pipeline on a single bone name."""
    text = name

    # Step 1 & 2: strip rig prefixes and suffixes.
    text = _strip_prefixes(text)
    text = _strip_suffixes(text)

    # Step 3: extract side token.
    text, side = _extract_side(text)

    # Step 4: extract trailing segment number.
    text, segment, had_sep = _extract_segment(text)

    # Step 5: tokenize.
    token = _tokenize(text)

    # Step 6: detect pole / aim / target bones.
    is_pole = any(kw in token for kw in POLE_KEYWORDS)

    # Step 7: detect finger identity.
    is_finger       = False
    finger_identity = ''

    if not is_pole:
        # Direct named finger? (e.g. 'thumb', 'index', 'pinky', 'little')
        if token in _FINGER_REVERSE:
            is_finger       = True
            finger_identity = _FINGER_REVERSE[token]
        else:
            # Rigify f_ prefix: f_thumb → fthumb, f_index → findex, etc.
            candidate = None
            if token.startswith('f') and len(token) > 1:
                candidate = token[1:]
            if candidate and candidate in _FINGER_REVERSE:
                is_finger       = True
                finger_identity = _FINGER_REVERSE[candidate]
            else:
                # Compound 'finger' prefix: fingerthumb, fingerindex, etc.
                # Handles Finger_Thumb, Finger_Index, Finger_Middle, Finger_Ring,
                # Finger_Pinky / Finger_Little after tokenization.
                if token.startswith('finger') and len(token) > 6:
                    remainder = token[6:]   # e.g. 'thumb', 'index', 'pinky'
                    if remainder in _FINGER_REVERSE:
                        is_finger       = True
                        finger_identity = _FINGER_REVERSE[remainder]

                if not is_finger:
                    # Numbered: finger1 / finger2 / … or bare digit after 'finger'.
                    m = re.match(r'^(?:finger)?(\d)$', token)
                    if m:
                        num     = int(m.group(1))
                        mapping = _NUM_WITH_THUMB if has_separate_thumb else _NUM_WITHOUT_THUMB
                        if num in mapping:
                            is_finger       = True
                            finger_identity = mapping[num]

    # Step 8: detect toe identity (only when not a finger — mutually exclusive).
    is_toe       = False
    toe_identity = ''

    if not is_pole and not is_finger:
        is_toe, toe_identity = _detect_toe(token)
        # Rigify f_ prefix for individual toes: fbigtoe, findextoe, etc.
        # Try stripping the leading 'f' and re-running detection.
        if not is_toe and token.startswith('f') and len(token) > 1:
            is_toe, toe_identity = _detect_toe(token[1:])
        # Numbered toe: 'toe1', 'toe2', … with NO separator before the digit.
        # _extract_segment already consumed the digit into `segment`; the
        # remaining token is bare 'toe'.  Without a separator the digit is the
        # toe identity number, not a bone segment number.
        # e.g. DEF-toe1.L → segment=1, had_sep=False, token='toe'
        #      DEF-toe.01.L → segment=1, had_sep=True,  token='toe'  (segment, keep as-is)
        if not is_toe and token == 'toe' and segment is not None and not had_sep:
            if segment in _TOE_NUM:
                is_toe       = True
                toe_identity = _TOE_NUM[segment]
                segment      = None   # digit was identity, not bone segment

    # Step 9: synonym lookup for regular (non-finger, non-toe, non-pole) bones.
    canonical      = token
    low_confidence = False

    if not is_finger and not is_toe and not is_pole:
        if token in _SYNONYM_REVERSE:
            canonical, low_confidence = _SYNONYM_REVERSE[token]

    return NormalizedBone(
        original        = name,
        side            = side,
        segment         = segment,
        is_pole         = is_pole,
        is_finger       = is_finger,
        finger_identity = finger_identity,
        is_toe          = is_toe,
        toe_identity    = toe_identity,
        canonical       = canonical,
        low_confidence  = low_confidence,
    )


# ── Thumb detection helper ────────────────────────────────────────────

def _has_separate_thumb(bone_names: list) -> bool:
    """
    Return True if the bone list contains a bone that resolves to the
    'thumb' finger via a named token (not a numbered fallback).
    Used to determine the Finger1/2/… → finger identity offset.
    """
    for name in bone_names:
        text = _strip_suffixes(_strip_prefixes(name))
        text, _ = _extract_side(text)
        text, _, _ = _extract_segment(text)
        token   = _tokenize(text)

        # Direct named: 'thumb'
        if _FINGER_REVERSE.get(token) == 'thumb':
            return True
        # Rigify f_ prefix: fthumb
        if token.startswith('f') and len(token) > 1:
            if _FINGER_REVERSE.get(token[1:]) == 'thumb':
                return True
        # Compound finger prefix: fingerthumb (Finger_Thumb style)
        if token.startswith('finger') and len(token) > 6:
            if _FINGER_REVERSE.get(token[6:]) == 'thumb':
                return True
    return False


# ── MatchResult ───────────────────────────────────────────────────────

class MatchResult:
    """Holds the outcome of matching one source bone to a target bone."""

    __slots__ = ('source_name', 'target_name', 'status', 'reason')

    def __init__(
        self,
        source_name: str,
        target_name: str,
        status: str,
        reason: str,
    ):
        self.source_name = source_name
        self.target_name = target_name
        self.status      = status   # 'CONFIRMED', 'WARNING', or 'ERROR'
        self.reason      = reason


# ── Main matching function ────────────────────────────────────────────

def match_bones(source_names: list, target_names: list) -> list:
    """
    Match a list of source bone names to a list of target bone names.

    Returns a list of MatchResult, one per source bone name, in the
    same order as source_names.

    Matching guarantees:
      - Each target bone is assigned to at most one source bone.
      - A CONFIRMED result means a unique, high-confidence match was found.
      - A WARNING result means the match is low-confidence or ambiguous.
      - An ERROR result means no candidate was found.
    """
    src_has_thumb = _has_separate_thumb(source_names)
    tgt_has_thumb = _has_separate_thumb(target_names)

    src_bones: list[NormalizedBone] = [
        normalize_bone(n, src_has_thumb) for n in source_names
    ]
    tgt_bones: list[NormalizedBone] = [
        normalize_bone(n, tgt_has_thumb) for n in target_names
    ]

    used_targets: set[int] = set()
    results: list[MatchResult] = []

    for src in src_bones:
        # (target_index, NormalizedBone, low_confidence)
        candidates: list[tuple[int, NormalizedBone, bool]] = []

        for i, tgt in enumerate(tgt_bones):
            if i in used_targets:
                continue

            # Hard filter 1: side must match.
            if src.side != tgt.side:
                continue

            # Hard filter 2: pole/aim status must match.
            if src.is_pole != tgt.is_pole:
                continue

            # Hard filter 3: finger / toe / regular category must all match.
            if src.is_finger != tgt.is_finger:
                continue
            if src.is_toe != tgt.is_toe:
                continue

            if src.is_finger:
                # Finger bones: both finger identity and segment must match.
                if (src.finger_identity == tgt.finger_identity
                        and src.segment == tgt.segment):
                    candidates.append((i, tgt, False))

            elif src.is_toe:
                # Toe bones: both toe identity and segment must match.
                if (src.toe_identity == tgt.toe_identity
                        and src.segment == tgt.segment):
                    candidates.append((i, tgt, False))

            elif src.is_pole:
                # Pole bones: match on canonical name.
                if src.canonical == tgt.canonical:
                    candidates.append((i, tgt, False))

            else:
                # Regular bones: match on canonical name.
                if src.canonical == tgt.canonical:
                    low = src.low_confidence or tgt.low_confidence
                    candidates.append((i, tgt, low))

        # ── Resolve candidates ────────────────────────────────────────
        if len(candidates) == 1:
            idx, tgt, low_conf = candidates[0]
            used_targets.add(idx)

            if low_conf:
                status = 'WARNING'
                reason = (
                    f"Low confidence: '{src.original}' matched to "
                    f"'{tgt.original}' via ambiguous synonym "
                    f"('{src.canonical}'). Please verify this pairing."
                )
            else:
                status = 'CONFIRMED'
                reason = f"Matched '{src.original}' → '{tgt.original}'."

            results.append(MatchResult(src.original, tgt.original, status, reason))

        elif len(candidates) > 1:
            # Multiple candidates — pick first, flag as warning.
            idx, tgt, _ = candidates[0]
            used_targets.add(idx)
            all_names = ', '.join(t.original for _, t, _ in candidates)
            results.append(MatchResult(
                source_name = src.original,
                target_name = tgt.original,
                status      = 'WARNING',
                reason      = (
                    f"Multiple candidates for '{src.original}': {all_names}. "
                    f"First candidate '{tgt.original}' was selected. "
                    f"Please verify this pairing."
                ),
            ))

        else:
            results.append(MatchResult(
                source_name = src.original,
                target_name = '',
                status      = 'ERROR',
                reason      = f"No match found for '{src.original}'.",
            ))

    return results
