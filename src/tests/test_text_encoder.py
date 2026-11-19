import unittest

from errors import TextEncodingError, BackendError, ReceiptEngineError
from compiler.text_encoder import TextEncoder, EncodedRun
from printer.printer_profile import PrinterEncoding, CodePage

PC437 = CodePage("PC437", "cp437", 0)
PC858 = CodePage("PC858", "cp858", 19)


def encoder(*pages):
    return TextEncoder(PrinterEncoding(code_pages=list(pages)))


class TestAsciiOnlyProfile(unittest.TestCase):
    """A profile with no code pages can print plain ASCII, nothing else."""

    def test_ascii_text(self):
        runs = encoder().encode("Hello 123")
        self.assertEqual(runs, [EncodedRun(None, b"Hello 123")])

    def test_empty_text_gives_no_runs(self):
        self.assertEqual(encoder().encode(""), [])

    def test_non_ascii_is_rejected_with_advice(self):
        with self.assertRaises(TextEncodingError) as context:
            encoder().encode("Caf\u00e9")

        message = str(context.exception)
        self.assertIn("U+00E9", message)
        self.assertIn("code pages", message)

    def test_no_default_page(self):
        self.assertIsNone(encoder().default_page)


class TestProfileWithCodePages(unittest.TestCase):

    def test_default_page_is_the_first_listed(self):
        self.assertEqual(encoder(PC437, PC858).default_page, PC437)

    def test_plain_text_uses_the_current_page(self):
        runs = encoder(PC437, PC858).encode("Hello", PC437)
        self.assertEqual(runs, [EncodedRun(PC437, b"Hello")])

    def test_accented_letter_is_encoded_with_the_codec(self):
        runs = encoder(PC437, PC858).encode("Caf\u00e9", PC437)
        self.assertEqual(runs, [EncodedRun(PC437, "Caf\u00e9".encode("cp437"))])

    def test_page_is_switched_only_when_needed(self):
        # The euro sign exists in PC858 but not in PC437.
        runs = encoder(PC437, PC858).encode("A\u20acB \u00e9", PC437)

        self.assertEqual(runs, [
            EncodedRun(PC437, b"A"),
            # After the switch the printer STAYS on PC858, because
            # PC858 can print the rest of the text too.
            EncodedRun(PC858, "\u20acB \u00e9".encode("cp858")),
        ])

    def test_printer_stays_on_its_current_page(self):
        runs = encoder(PC437, PC858).encode("ab", PC858)
        self.assertEqual(runs, [EncodedRun(PC858, b"ab")])

    def test_first_listed_page_is_preferred_when_none_is_current(self):
        # e-acute exists in both pages. PC437 is listed first.
        runs = encoder(PC437, PC858).encode("\u00e9", None)
        self.assertEqual(runs[0].page, PC437)

    def test_starting_without_a_current_page_still_works(self):
        runs = encoder(PC437, PC858).encode("\u20ac", None)
        self.assertEqual(runs, [EncodedRun(PC858, "\u20ac".encode("cp858"))])

    def test_character_no_page_can_print_is_rejected(self):
        # Indian rupee sign: in neither page.
        with self.assertRaises(TextEncodingError) as context:
            encoder(PC437, PC858).encode("Total \u20b9 5", PC437)

        message = str(context.exception)
        self.assertIn("U+20B9", message)
        self.assertIn("PC437", message)
        self.assertIn("PC858", message)

    def test_nepali_text_is_rejected_with_a_clear_error(self):
        with self.assertRaises(TextEncodingError) as context:
            encoder(PC437, PC858).encode("\u0928\u092e\u0938\u094d\u0924\u0947")

        self.assertIn("U+0928", str(context.exception))

    def test_encoder_can_be_reused(self):
        enc = encoder(PC437, PC858)
        first = enc.encode("\u20ac", PC437)
        second = enc.encode("\u20ac", PC437)
        self.assertEqual(first, second)


class TestErrorFamily(unittest.TestCase):

    def test_text_encoding_error_is_a_backend_error(self):
        self.assertTrue(issubclass(TextEncodingError, BackendError))
        self.assertTrue(issubclass(TextEncodingError, ReceiptEngineError))


if __name__ == "__main__":
    unittest.main()