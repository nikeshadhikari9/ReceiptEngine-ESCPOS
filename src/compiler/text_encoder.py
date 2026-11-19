"""
Generic text encoder.

Turns text into bytes using the code pages listed in a printer profile.
It knows nothing about ESC/POS or any other printer language: it only
decides WHICH code page each part of the text needs. The backend decides
how to tell the printer to switch pages.

Rules:
  * The printer stays on its current page for as long as that page can
    print the next character (so ordinary text causes no page switches).
  * When it cannot, the first page in the profile's list that can print
    the character is used.
  * If no page can print the character, TextEncodingError is raised.
  * If the profile lists no code pages, only ASCII text is allowed.
"""

from dataclasses import dataclass
from typing import List, Optional

from errors import TextEncodingError
from printer.printer_profile import CodePage, PrinterEncoding


@dataclass(frozen=True)
class EncodedRun:
    """A piece of text, already encoded, that belongs to one code page."""

    # None means "no page selection": the profile has no code pages
    # and the data is plain ASCII.
    page: Optional[CodePage]
    data: bytes


class TextEncoder:

    def __init__(self, encoding: PrinterEncoding):
        self.pages: List[CodePage] = list(encoding.code_pages)

    @property
    def default_page(self) -> Optional[CodePage]:
        """The page to select at the start of a receipt, if any."""
        return self.pages[0] if self.pages else None

    def encode(
        self,
        text: str,
        current_page: Optional[CodePage] = None
    ) -> List[EncodedRun]:
        """
        Encode text. current_page is the page the printer is on right now.
        Returns one run per stretch of text that uses the same page.
        """

        if not self.pages:
            return self._encode_ascii_only(text)

        # The caller may only have told us which page the printer is on.
        # If that page is not one of the pages this profile declares,
        # treat it as "no page selected" and let preference order decide.
        if current_page is not None and current_page not in self.pages:
            current_page = None
        runs = []
        page = current_page
        pending = bytearray()

        for character in text:

            data = (
                self._encode_character(page, character)
                if page is not None
                else None
            )

            if data is None:
                new_page, data = self._find_page(character)

                if pending:
                    runs.append(EncodedRun(page, bytes(pending)))
                    pending = bytearray()

                page = new_page

            pending.extend(data)

        if pending:
            runs.append(EncodedRun(page, bytes(pending)))

        return runs

    # -----------------------------------------

    @staticmethod
    def _encode_character(page: CodePage, character: str):
        try:
            return character.encode(page.codec)
        except UnicodeEncodeError:
            return None

    def _find_page(self, character: str):
        for page in self.pages:
            data = self._encode_character(page, character)

            if data is not None:
                return page, data

        raise TextEncodingError(
            f"Cannot print {character!r} (U+{ord(character):04X}): "
            f"none of the printer's code pages can represent it. "
            f"Pages tried: {[page.name for page in self.pages]}."
        )

    @staticmethod
    def _encode_ascii_only(text: str) -> List[EncodedRun]:
        try:
            data = text.encode("ascii")
        except UnicodeEncodeError as error:
            character = text[error.start]

            raise TextEncodingError(
                f"Cannot print {character!r} (U+{ord(character):04X}): "
                f"the printer profile lists no code pages, so only "
                f"ASCII text can be printed. Add code pages to the "
                f"profile's encoding section."
            ) from error

        return [EncodedRun(None, data)] if data else []