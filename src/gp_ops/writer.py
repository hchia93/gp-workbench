"""Emit a Guitar Pro 7/8 .gp file by rewriting the id tables of a known-good template.

Template method: only score.gpif is regenerated. BinaryStylesheet, LayoutConfiguration
and friends are copied verbatim, so the undocumented binary blobs stay valid.
"""

import os
import re
import zipfile

TUNING = [40, 45, 50, 55, 59, 64]
STEPS = {
    0: ("C", ""), 1: ("C", "#"), 2: ("D", ""), 3: ("E", "b"), 4: ("E", ""), 5: ("F", ""),
    6: ("F", "#"), 7: ("G", ""), 8: ("A", "b"), 9: ("A", ""), 10: ("B", "b"), 11: ("B", ""),
}

# Rhythm table is fixed; beats reference it by index
RHYTHMS = [
    ("Whole", 0), ("Half", 0), ("Quarter", 0), ("Eighth", 0), ("16th", 0),
    ("Half", 1), ("Quarter", 1), ("Eighth", 1),
]


class Note:
    # string is guitar-facing: 1 = high E, 6 = low E
    # hopo_origin marks the note a slur leaves, hopo_destination the one it lands on,
    # so a hammer-on is the pair set on two consecutive notes of the same string.
    def __init__(self, string, fret, muted=False, hopo_origin=False,
                 hopo_destination=False, let_ring=False, tie_origin=False,
                 tie_destination=False):
        self.string = string
        self.fret = fret
        self.muted = muted
        self.hopo_origin = hopo_origin
        self.hopo_destination = hopo_destination
        self.let_ring = let_ring
        self.tie_origin = tie_origin
        self.tie_destination = tie_destination

    def index(self):
        return 6 - self.string


class Beat:
    # brush is "Down" (low string to high) or "Up", for notes rolled rather than
    # struck together. Those rolls sit between the 32nd and the 64th and match no
    # subdivision, so they are an articulation, not a rhythm to quantise.
    def __init__(self, value, notes, dotted=False, brush=None, vibrato=None):
        self.value = value
        self.dotted = dotted
        self.notes = notes
        self.brush = brush
        self.vibrato = vibrato

    def rhythm(self):
        return RHYTHMS.index((self.value, 1 if self.dotted else 0))


def mute(strings):
    return Beat("Eighth", [Note(s, 0, muted=True) for s in strings])


def pluck(string, fret, value="Eighth", dotted=False):
    return Beat(value, [Note(string, fret)], dotted)


def chord(pairs, value="Eighth", dotted=False):
    return Beat(value, [Note(s, f) for s, f in pairs], dotted)


def _pitch(tag, midi, octave_shift):
    step, acc = STEPS[midi % 12]
    octave = midi // 12 + octave_shift
    return (f'<Property name="{tag}">\n<Pitch><Step>{step}</Step>'
            f"<Accidental>{acc}</Accidental><Octave>{octave}</Octave></Pitch></Property>")


def _note_xml(nid, note, capo):
    # Guitar Pro writes note properties in alphabetical order; keep that or it
    # silently drops the ones out of place.
    midi = TUNING[note.index()] + note.fret + capo
    parts = [_pitch("ConcertPitch", midi, 0),
             f'<Property name="Fret">\n<Fret>{note.fret}</Fret>\n</Property>']
    if note.hopo_destination:
        parts.append('<Property name="HopoDestination">\n<Enable />\n</Property>')
    if note.hopo_origin:
        parts.append('<Property name="HopoOrigin">\n<Enable />\n</Property>')
    if note.let_ring:
        parts.append('<Property name="LetRing">\n<Enable />\n</Property>')
    parts.append(f'<Property name="Midi">\n<Number>{midi}</Number>\n</Property>')
    if note.muted:
        parts.append('<Property name="Muted">\n<Enable />\n</Property>')
    parts.append(f'<Property name="String">\n<String>{note.index()}</String>\n</Property>')
    parts.append(_pitch("TransposedPitch", midi, 1))
    body = "".join(parts)
    # Tie sits ahead of the articulation, both ends flagged on their own note
    tie = ""
    if note.tie_origin or note.tie_destination:
        tie = (f'<Tie origin="{str(note.tie_origin).lower()}" '
               f'destination="{str(note.tie_destination).lower()}" />\n')
    return (f'<Note id="{nid}">\n{tie}<InstrumentArticulation>0</InstrumentArticulation>\n'
            f"<Properties>\n{body}</Properties>\n</Note>")


def _beat_xml(bid, beat, note_ids):
    return (f'<Beat id="{bid}">\n<Dynamic>MF</Dynamic>\n<Rhythm ref="{beat.rhythm()}" />\n'
            "<TransposedPitchStemOrientation>Undefined</TransposedPitchStemOrientation>\n"
            "<ConcertPitchStemOrientation>Undefined</ConcertPitchStemOrientation>\n"
            f"<Notes>{' '.join(str(i) for i in note_ids)}</Notes>\n<Properties>\n"
            + (f'<Property name="Brush">\n<Direction>{beat.brush}</Direction>\n</Property>\n'
               if beat.brush else "") +
            '<Property name="PrimaryPickupVolume">\n<Float>0.500000</Float>\n</Property>\n'
            '<Property name="PrimaryPickupTone">\n<Float>0.500000</Float>\n</Property>\n'
            + (f'<Property name="VibratoWTremBar">\n<Strength>{beat.vibrato}</Strength>\n</Property>\n'
               if beat.vibrato else "") +
            "</Properties>\n</Beat>")


def _rhythms_xml():
    out = []
    for i, (value, dots) in enumerate(RHYTHMS):
        dot = f'\n<AugmentationDot count="{dots}" />' if dots else ""
        out.append(f'<Rhythm id="{i}">\n<NoteValue>{value}</NoteValue>{dot}\n</Rhythm>')
    return "\n".join(out)


def _lyrics_xml(lines):
    """Lyric lines as (bar_offset, text).

    Guitar Pro hands one whitespace-separated token to each beat that carries a
    note, in order, so an empty token skips a beat. Offset only reaches the bar,
    everything finer is spelled with padding: leading blanks push the first
    syllable off the downbeat, inner blanks ride over held notes. Template lyrics
    survive otherwise, and the previous song's words come out in the new score.
    """
    lines = lines or [(0, "")]
    body = "\n".join(f"<Line>\n<Text><![CDATA[{text}]]></Text>\n<Offset>{offset}</Offset>\n</Line>"
                     for offset, text in lines)
    return f'<Lyrics dispatched="true">\n{body}\n</Lyrics>'


def _replace_table(xml, plural, single, body):
    pattern = r"<%s>\s*<%s id=.*?</%s>" % (plural, single, plural)
    return re.sub(pattern, f"<{plural}>\n{body}\n</{plural}>", xml, count=1, flags=re.S)


def _replace_ref_table(xml, tag, body):
    # the top-level <Bars>/<Voices>/... reference lists sit right after their id table
    return re.sub(r"<%s>[^<]*</%s>" % (tag, tag), f"<{tag}>{body}</{tag}>", xml, count=1)


def build(template_gp, song, out_gp):
    src = zipfile.ZipFile(template_gp)
    xml = src.read("Content/score.gpif").decode("utf-8")

    notes, beats, voices, bars, masterbars = [], [], [], [], []
    for bar_index, bar in enumerate(song["bars"]):
        beat_ids = []
        for beat in bar["beats"]:
            note_ids = []
            for note in beat.notes:
                note_ids.append(len(notes))
                notes.append(_note_xml(len(notes), note, song["capo"]))
            beat_ids.append(len(beats))
            beats.append(_beat_xml(len(beats), beat, note_ids))
        voices.append(f'<Voice id="{len(voices)}">\n<Beats>{" ".join(str(i) for i in beat_ids)}</Beats>\n</Voice>')
        bars.append(f'<Bar id="{bar_index}">\n<Clef>G2</Clef>\n<Voices>{bar_index} -1 -1 -1</Voices>\n</Bar>')
        repeat = bar.get("repeat", "")
        masterbars.append(f"<MasterBar>\n<Key>\n<AccidentalCount>0</AccidentalCount>\n<Mode>Major</Mode>\n"
                          f"<TransposeAs>Sharps</TransposeAs>\n</Key>\n{repeat}<Time>{song['time']}</Time>\n"
                          f"<Bars>{bar_index}</Bars>\n</MasterBar>")

    xml = _replace_table(xml, "MasterBars", "MasterBar", "\n".join(masterbars)) \
        if "<MasterBar>" in xml else xml
    xml = re.sub(r"<MasterBars>.*?</MasterBars>", "<MasterBars>\n" + "\n".join(masterbars) + "\n</MasterBars>",
                 xml, count=1, flags=re.S)
    xml = _replace_table(xml, "Bars", "Bar", "\n".join(bars))
    xml = _replace_table(xml, "Voices", "Voice", "\n".join(voices))
    xml = _replace_table(xml, "Beats", "Beat", "\n".join(beats))
    xml = _replace_table(xml, "Notes", "Note", "\n".join(notes))
    xml = _replace_table(xml, "Rhythms", "Rhythm", _rhythms_xml())

    # the reference lists that point at track-level tables
    xml = re.sub(r"(</MasterBars>\s*<Bars>)", r"\1", xml)
    for tag, body in [("Tracks", "0")]:
        xml = _replace_ref_table(xml, tag, body)

    xml = re.sub(r"<Lyrics\b.*?</Lyrics>", lambda _: _lyrics_xml(song.get("lyrics")),
                 xml, count=1, flags=re.S)

    for field, value in [("Title", song["title"]), ("Artist", song["artist"]),
                         ("Tabber", song.get("tabber", "")), ("Album", ""), ("SubTitle", "")]:
        xml = re.sub(r"<%s><!\[CDATA\[.*?\]\]></%s>" % (field, field),
                     f"<{field}><![CDATA[{value}]]></{field}>", xml, count=1, flags=re.S)

    xml = re.sub(r"<Value>\d+ 2</Value>", f"<Value>{song['tempo']} 2</Value>", xml, count=1)
    xml = re.sub(r'(<Property name="CapoFret">\s*<Fret>)\d+(</Fret>)', rf"\g<1>{song['capo']}\g<2>", xml, count=1)

    os.makedirs(os.path.dirname(out_gp), exist_ok=True)
    with zipfile.ZipFile(out_gp, "w", zipfile.ZIP_DEFLATED) as dst:
        for item in src.namelist():
            data = xml.encode("utf-8") if item == "Content/score.gpif" else src.read(item)
            dst.writestr(item, data)
    return len(notes), len(beats), len(song["bars"])
