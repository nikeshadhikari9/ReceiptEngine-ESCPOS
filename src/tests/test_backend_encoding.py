import unittest

from errors import TextEncodingError
from compiler.escpos_backend import ESCPosBackend
from compiler.render_plan import (
    RenderPlan,
    TextOperation,
    ColumnsOperation,
    RenderLine,
    RenderColumn,
    QROperation,
)
from printer.printer_profile import (
    PrinterProfile,
    PrinterIdentification,
    PrinterMedia,
    PrinterCapabilities,
    PrinterEncoding,
    CodePage,
    PrinterLayout,
)

ESC_T = b"\x1bt"          # ESC t : select code page
ESC_AT = b"\x1b@"         # ESC @ : initialize printer


def make_profile(*pages):
    return PrinterProfile(
        printer_id="printer_001",
        identification=PrinterIdentification("ANY", "ANY"),
        media=PrinterMedia(80, 576, 48),
        capabilities=PrinterCapabilities(qr_code=True, cutting=True),
        encoding=PrinterEncoding(code_pages=list(pages)),
        supported_transports=["network"],
        layout=PrinterLayout(0, 0),
    )


def render(profile, *operations):
    plan = RenderPlan(printer_id="printer_001", operations=list(operations))
    return ESCPosBackend().render(plan, profile)


# Page numbers here are deliberately NOT Epson's: the backend must use
# whatever numbers the profile says.
PAGE_A = CodePage("PAGE_A", "cp437", 7)
PAGE_B = CodePage("PAGE_B", "cp858", 42)


class TestAsciiOnlyProfile(unittest.TestCase):

    def test_no_code_page_command_is_sent(self):
        output = render(make_profile(), TextOperation(text="Hello"))

        self.assertNotIn(ESC_T, output)
        self.assertIn(b"Hello", output)

    def test_non_ascii_text_is_rejected(self):
        with self.assertRaises(TextEncodingError):
            render(make_profile(), TextOperation(text="Caf\u00e9"))


class TestProfileWithCodePages(unittest.TestCase):

    def test_first_page_is_selected_right_after_initialize(self):
        output = render(
            make_profile(PAGE_A, PAGE_B), TextOperation(text="Hi")
        )

        self.assertTrue(output.startswith(ESC_AT + ESC_T + bytes([7])))

    def test_page_numbers_come_from_the_profile(self):
        output = render(
            make_profile(PAGE_A, PAGE_B), TextOperation(text="\u20ac")
        )

        self.assertIn(ESC_T + bytes([42]), output)

    def test_page_switch_happens_before_the_character(self):
        euro = "\u20ac".encode("cp858")

        output = render(
            make_profile(PAGE_A, PAGE_B), TextOperation(text="\u20ac")
        )

        switch = output.index(ESC_T + bytes([42]))
        self.assertLess(switch, output.index(euro, switch))

    def test_text_that_fits_the_first_page_causes_no_switch(self):
        output = render(
            make_profile(PAGE_A, PAGE_B),
            TextOperation(text="Caf\u00e9"),
        )

        self.assertEqual(output.count(ESC_T), 1)
        self.assertIn("Caf\u00e9".encode("cp437"), output)

    def test_selected_page_is_remembered_between_operations(self):
        output = render(
            make_profile(PAGE_A, PAGE_B),
            TextOperation(text="\u20ac1"),
            TextOperation(text="\u20ac2"),
        )

        # Once for PAGE_A at the start, once (only) for PAGE_B.
        self.assertEqual(output.count(ESC_T + bytes([42])), 1)
        self.assertEqual(output.count(ESC_T), 2)

    def test_columns_use_the_same_encoding(self):
        line = RenderLine(columns=[
            RenderColumn("Caf\u00e9", 10, "left"),
            RenderColumn("\u20ac5", 6, "right"),
        ])

        output = render(
            make_profile(PAGE_A, PAGE_B),
            ColumnsOperation(lines=[line]),
        )

        self.assertIn(ESC_T + bytes([42]), output)
        self.assertIn("\u20ac5".encode("cp858"), output)

    def test_unprintable_character_raises_text_encoding_error(self):
        with self.assertRaises(TextEncodingError):
            render(
                make_profile(PAGE_A, PAGE_B),
                TextOperation(text="\u0928\u092e\u0938"),
            )

    def test_each_render_starts_from_a_fresh_page_selection(self):
        profile = make_profile(PAGE_A, PAGE_B)
        backend = ESCPosBackend()

        plan = RenderPlan(
            printer_id="printer_001",
            operations=[TextOperation(text="\u20ac")],
        )

        first = backend.render(plan, profile)
        second = backend.render(plan, profile)

        self.assertEqual(first, second)


class TestQrDataIsUtf8(unittest.TestCase):

    def test_qr_payload_ignores_printer_code_pages(self):
        output = render(
            make_profile(PAGE_A, PAGE_B),
            QROperation(data="Caf\u00e9 \u20b9", method="native"),
        )

        self.assertIn("Caf\u00e9 \u20b9".encode("utf-8"), output)
        # Only the single selection of PAGE_A at the start.
        self.assertEqual(output.count(ESC_T), 1)

    def test_qr_works_even_without_code_pages(self):
        output = render(
            make_profile(),
            QROperation(data="\u0928\u092e\u0938", method="native"),
        )

        self.assertIn("\u0928\u092e\u0938".encode("utf-8"), output)


if __name__ == "__main__":
    unittest.main()