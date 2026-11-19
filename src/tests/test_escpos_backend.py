
import unittest

from compiler.escpos_backend import ESCPosBackend, ESCPosError

from compiler.render_plan import (
    RenderPlan,
    TextOperation,
    RenderStyle,
    ColumnsOperation,
    RenderLine,
    RenderColumn,
    SeparatorOperation,
    QROperation,
    FeedOperation,
    CutOperation,
)

from printer.printer_profile import (
    PrinterProfile,
    PrinterIdentification,
    PrinterMedia,
    PrinterCapabilities,
    PrinterEncoding,
    PrinterLayout,
)
from errors import TextEncodingError


def create_printer_profile():
    return PrinterProfile(
        printer_id="printer_001",

        identification=PrinterIdentification(
            manufacturer="EPSON",
            model="TM-T20IV",
        ),

        media=PrinterMedia(
            paper_width_mm=80,
            printable_width_dots=576,
            character_columns=48,
        ),

        capabilities=PrinterCapabilities(
            qr_code=True,
            barcode=True,
            raster=True,
            cutting=True,
        ),

        encoding=PrinterEncoding(),

        supported_transports=["USB", "serial"],

        layout=PrinterLayout(
            left_margin_dots=0,
            right_margin_dots=0,
        ),
    )


class TestESCPosBackend(unittest.TestCase):

    def setUp(self):
        self.backend = ESCPosBackend()
        self.printer = create_printer_profile()

    def render(self, operations):
        plan = RenderPlan(
            printer_id="printer_001",
            operations=operations,
        )

        return self.backend.render(plan, self.printer)

    def test_initialize_command(self):
        result = self.render([])

        self.assertTrue(
            result.startswith(bytes([0x1B, 0x40]))
        )

    def test_text_output(self):
        result = self.render([
            TextOperation(
                text="HELLO",
                style=RenderStyle(),
            )
        ])

        self.assertIn(b"HELLO", result)
        self.assertIn(bytes([0x0A]), result)

    def test_alignment_command(self):
        result = self.render([
            TextOperation(
                text="CENTER",
                style=RenderStyle(
                    alignment="center"
                ),
            )
        ])

        # ESC a 1 = center alignment
        self.assertIn(
            bytes([0x1B, 0x61, 0x01]),
            result,
        )

    def test_bold_commands(self):
        result = self.render([
            TextOperation(
                text="BOLD",
                style=RenderStyle(
                    bold=True
                ),
            )
        ])

        # ESC E 1 = bold enabled
        self.assertIn(
            bytes([0x1B, 0x45, 0x01]),
            result,
        )

        # ESC E 0 = bold disabled
        self.assertIn(
            bytes([0x1B, 0x45, 0x00]),
            result,
        )

    def test_separator(self):
        result = self.render([
            SeparatorOperation(
                character="-",
                repeat=10,
            )
        ])

        self.assertIn(b"----------", result)

    def test_columns(self):
        result = self.render([
            ColumnsOperation(
                lines=[
                    RenderLine(
                        columns=[
                            RenderColumn(
                                text="MOMO",
                                width=10,
                                alignment="left",
                            ),
                            RenderColumn(
                                text="250",
                                width=5,
                                alignment="right",
                            ),
                        ]
                    )
                ]
            )
        ])

        self.assertIn(b"MOMO        250", result)

    def test_column_width_overflow(self):
        with self.assertRaises(ESCPosError):
            self.render([
                ColumnsOperation(
                    lines=[
                        RenderLine(
                            columns=[
                                RenderColumn(
                                    text="TOO LONG",
                                    width=3,
                                )
                            ]
                        )
                    ]
                )
            ])

    def test_feed_command(self):
        result = self.render([
            FeedOperation(lines=3)
        ])

        # ESC d 3
        self.assertIn(
            bytes([0x1B, 0x64, 0x03]),
            result,
        )

    def test_full_cut_command(self):
        result = self.render([
            CutOperation(mode="full")
        ])

        # GS V 0
        self.assertIn(
            bytes([0x1D, 0x56, 0x00]),
            result,
        )

    def test_partial_cut_command(self):
        result = self.render([
            CutOperation(mode="partial")
        ])

        # GS V 1
        self.assertIn(
            bytes([0x1D, 0x56, 0x01]),
            result,
        )

    def test_native_qr_command(self):
        result = self.render([
            QROperation(
                data="https://example.com",
                method="native",
                size=6,
            )
        ])

        # GS ( k command prefix
        self.assertIn(
            bytes([0x1D, 0x28, 0x6B]),
            result,
        )

        # QR data storage command: cn=49, fn=80, m=48
        self.assertIn(
            bytes([0x31, 0x50, 0x30]),
            result,
        )

        self.assertIn(
            b"https://example.com",
            result,
        )

    def test_qr_without_resolved_method(self):
        with self.assertRaises(ESCPosError):
            self.render([
                QROperation(
                    data="https://example.com",
                    method=None,
                )
            ])

    def test_raster_qr_not_implemented(self):
        with self.assertRaises(ESCPosError):
            self.render([
                QROperation(
                    data="https://example.com",
                    method="raster",
                )
            ])

    def test_empty_qr_data(self):
        with self.assertRaises(ESCPosError):
            self.render([
                QROperation(
                    data="",
                    method="native",
                )
            ])

    def test_invalid_qr_size(self):
        with self.assertRaises(ESCPosError):
            self.render([
                QROperation(
                    data="https://example.com",
                    method="native",
                    size=20,
                )
            ])

    def test_ascii_encoding_rejects_nepali(self):
        with self.assertRaises(TextEncodingError):
            self.render([
                TextOperation(
                    text="नमस्ते",
                )
            ])

    def test_multiple_render_calls(self):
        first = self.render([
            TextOperation(text="FIRST")
        ])

        second = self.render([
            TextOperation(text="SECOND")
        ])

        self.assertIn(b"FIRST", first)
        self.assertNotIn(b"FIRST", second)
        self.assertIn(b"SECOND", second)


if __name__ == "__main__":
    unittest.main()
