"""
Printer profile: what a physical printer is and what it can do.

A profile is checked when it is created. If any value is wrong, creating
the profile raises InvalidProfileError, so a broken profile can never
reach the layout engine, the resolver or the backend.

Profiles can be built in code, or loaded from a JSON file:

    profile = load_printer_profile("printer/espon_tm_t20iv.json")
"""

import codecs
import json
from dataclasses import dataclass, field, fields
from math import isfinite
from typing import Optional, List

from errors import InvalidProfileError


# --------------------------------------------------
# CHECKING HELPERS
# --------------------------------------------------

def _fail(path, message):
    raise InvalidProfileError(f"{path}: {message}")


def _check_text(path, value):
    if not isinstance(value, str) or not value.strip():
        _fail(path, f"must be a non-empty string, got {value!r}.")


def _check_whole_number(path, value, minimum):
    # bool is a kind of int in Python (True == 1), so exclude it.
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or value < minimum
    ):
        _fail(
            path,
            f"must be a whole number of at least {minimum}, "
            f"got {value!r}."
        )


def _check_positive_number(path, value):
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not isfinite(value)
        or value <= 0
    ):
        _fail(path, f"must be a number greater than 0, got {value!r}.")


def _check_bool(path, value):
    if not isinstance(value, bool):
        _fail(path, f"must be true or false, got {value!r}.")


def _check_codec(path, value):
    _check_text(path, value)

    try:
        codecs.lookup(value)
    except LookupError:
        _fail(path, f"{value!r} is not a known text encoding.")


# --------------------------------------------------
# PROFILE PARTS
# --------------------------------------------------

@dataclass
class PrinterIdentification:
    manufacturer: str
    model: str

    def __post_init__(self):
        _check_text("identification.manufacturer", self.manufacturer)
        _check_text("identification.model", self.model)


@dataclass
class PrinterMedia:
    paper_width_mm: float
    printable_width_dots: int
    character_columns: int

    def __post_init__(self):
        _check_positive_number("media.paper_width_mm", self.paper_width_mm)
        _check_whole_number(
            "media.printable_width_dots", self.printable_width_dots, 1
        )
        _check_whole_number(
            "media.character_columns", self.character_columns, 1
        )

        if self.printable_width_dots < self.character_columns:
            _fail(
                "media",
                "printable_width_dots must be at least character_columns "
                "(each character column needs one or more dots)."
            )


@dataclass
class PrinterCapabilities:
    qr_code: bool = False
    barcode: bool = False
    raster: bool = False
    cutting: bool = False

    def __post_init__(self):
        _check_bool("capabilities.qr_code", self.qr_code)
        _check_bool("capabilities.barcode", self.barcode)
        _check_bool("capabilities.raster", self.raster)
        _check_bool("capabilities.cutting", self.cutting)


def _check_single_byte_codec(path, value):
    """The codec must be a single-byte, ASCII-compatible code page."""

    _check_codec(path, value)

    try:
        ascii_compatible = all(
            bytes([code]).decode(value) == chr(code)
            for code in range(0x20, 0x7F)
        )
    except UnicodeDecodeError:
        ascii_compatible = False

    upper_half_bytes = 0

    for code in range(0x80, 0x100):
        try:
            if len(bytes([code]).decode(value)) == 1:
                upper_half_bytes += 1
        except UnicodeDecodeError:
            pass

    if not ascii_compatible or upper_half_bytes < 64:
        _fail(
            path,
            f"{value!r} is not a single-byte code page "
            f"(for example cp437, cp850, cp1252)."
        )


@dataclass
class CodePage:
    """
    One character table that a printer can switch to.

    name:    a label for humans and error messages, for example "PC437".
    codec:   the matching Python text encoding, for example "cp437".
    page_id: the number the printer protocol uses to select this table
             (for ESC/POS printers this is the n in the ESC t n command;
             look it up in the printer's manual).
    """

    name: str
    codec: str
    page_id: int

    def __post_init__(self):
        _check_text("code_page.name", self.name)
        _check_single_byte_codec("code_page.codec", self.codec)
        _check_whole_number("code_page.page_id", self.page_id, 0)

        if self.page_id > 255:
            _fail(
                "code_page.page_id",
                f"must be between 0 and 255, got {self.page_id!r}."
            )


@dataclass
class PrinterEncoding:
    """
    Which character tables this printer can use.

    code_pages is ordered by preference: the first one is selected at
    the start of every receipt. If the list is empty, only plain ASCII
    text can be printed and no code page command is ever sent.
    """

    code_pages: List[CodePage] = field(default_factory=list)
    unicode_raster_fallback: bool = False

    def __post_init__(self):
        if not isinstance(self.code_pages, list):
            _fail(
                "encoding.code_pages",
                f"must be a list, got {type(self.code_pages).__name__}."
            )

        for index, page in enumerate(self.code_pages):
            if not isinstance(page, CodePage):
                _fail(
                    f"encoding.code_pages[{index}]",
                    f"must be a CodePage, got {type(page).__name__}."
                )

        names = [page.name for page in self.code_pages]
        ids = [page.page_id for page in self.code_pages]

        if len(set(names)) != len(names):
            _fail("encoding.code_pages", f"duplicate names in {names}.")

        if len(set(ids)) != len(ids):
            _fail("encoding.code_pages", f"duplicate page_ids in {ids}.")

        _check_bool(
            "encoding.unicode_raster_fallback",
            self.unicode_raster_fallback
        )


@dataclass
class PrinterLayout:
    left_margin_dots: int = 0
    right_margin_dots: int = 0

    def __post_init__(self):
        _check_whole_number("layout.left_margin_dots", self.left_margin_dots, 0)
        _check_whole_number(
            "layout.right_margin_dots", self.right_margin_dots, 0
        )


# --------------------------------------------------
# COMPLETE PROFILE
# --------------------------------------------------

_PROFILE_KEYS = (
    "printer_id",
    "identification",
    "media",
    "capabilities",
    "encoding",
    "supported_transports",
    "layout",
)


@dataclass
class PrinterProfile:
    printer_id: str
    identification: PrinterIdentification
    media: PrinterMedia
    capabilities: PrinterCapabilities
    encoding: PrinterEncoding
    supported_transports: List[str]
    layout: PrinterLayout

    def __post_init__(self):
        _check_text("printer_id", self.printer_id)

        # Each part must be the real object, not (for example) a plain
        # dictionary that was read from JSON and never converted.
        for name, expected in (
            ("identification", PrinterIdentification),
            ("media", PrinterMedia),
            ("capabilities", PrinterCapabilities),
            ("encoding", PrinterEncoding),
            ("layout", PrinterLayout),
        ):
            value = getattr(self, name)

            if not isinstance(value, expected):
                _fail(
                    name,
                    f"must be a {expected.__name__}, "
                    f"got {type(value).__name__}."
                )

        if not isinstance(self.supported_transports, list):
            _fail(
                "supported_transports",
                f"must be a list, "
                f"got {type(self.supported_transports).__name__}."
            )

        for index, transport in enumerate(self.supported_transports):
            _check_text(f"supported_transports[{index}]", transport)

        # A check that needs two parts at once.
        margins = (
            self.layout.left_margin_dots + self.layout.right_margin_dots
        )

        if margins >= self.media.printable_width_dots:
            _fail(
                "layout",
                f"margins ({margins} dots) leave no printable width "
                f"(printable_width_dots is "
                f"{self.media.printable_width_dots})."
            )

    @classmethod
    def from_dict(cls, data) -> "PrinterProfile":
        """Build a validated profile from plain dictionary data."""

        if not isinstance(data, dict):
            _fail(
                "profile",
                f"must be an object/dictionary, got {type(data).__name__}."
            )

        missing = [key for key in _PROFILE_KEYS if key not in data]
        unknown = [key for key in data if key not in _PROFILE_KEYS]

        if missing:
            _fail("profile", f"missing required keys: {missing}.")

        if unknown:
            _fail("profile", f"unknown keys: {unknown}.")

        encoding = data["encoding"]

        # code_pages arrives from JSON as a list of dictionaries.
        # Turn each one into a CodePage object.
        if isinstance(encoding, dict) and isinstance(
            encoding.get("code_pages"), list
        ):
            encoding = dict(encoding)
            encoding["code_pages"] = [
                _build(CodePage, f"encoding.code_pages[{index}]", item)
                for index, item in enumerate(encoding["code_pages"])
            ]

        return cls(
            printer_id=data["printer_id"],
            identification=_build(
                PrinterIdentification, "identification",
                data["identification"]
            ),
            media=_build(PrinterMedia, "media", data["media"]),
            capabilities=_build(
                PrinterCapabilities, "capabilities", data["capabilities"]
            ),
            encoding=_build(PrinterEncoding, "encoding", encoding),
            supported_transports=data["supported_transports"],
            layout=_build(PrinterLayout, "layout", data["layout"]),
        )


def _build(part_class, name, section):
    """Create one profile part from a dictionary, with clear errors."""

    if not isinstance(section, dict):
        _fail(
            name,
            f"must be an object/dictionary, got {type(section).__name__}."
        )

    allowed = [field.name for field in fields(part_class)]
    unknown = [key for key in section if key not in allowed]

    if unknown:
        _fail(name, f"unknown keys: {unknown}. Allowed keys: {allowed}.")

    try:
        return part_class(**section)
    except TypeError as error:
        # Raised by Python when a required key is missing.
        _fail(name, str(error))


def load_printer_profile(path) -> PrinterProfile:
    """Read a printer profile from a JSON file and validate it."""

    try:
        # utf-8-sig also accepts files saved with a BOM (Windows Notepad).
        with open(path, encoding="utf-8-sig") as file:
            data = json.load(file)

    except OSError as error:
        raise InvalidProfileError(
            f"Cannot read printer profile file {str(path)!r}: {error}"
        ) from error

    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise InvalidProfileError(
            f"Printer profile file {str(path)!r} is not valid JSON: {error}"
        ) from error

    return PrinterProfile.from_dict(data)