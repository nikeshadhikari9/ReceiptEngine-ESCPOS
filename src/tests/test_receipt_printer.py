
import unittest
from unittest.mock import MagicMock

from printer.receipt_printer import ReceiptPrinter
from printer.receipt_printer import PrintResult

from printer.printer_profile import (
    PrinterProfile,
    PrinterIdentification,
    PrinterMedia,
    PrinterCapabilities,
    PrinterEncoding,
    PrinterLayout,
)
from errors import PrinterMismatchError

from compiler.render_plan import RenderPlan


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

        supported_transports=["USB", "serial", "network"],

        layout=PrinterLayout(
            left_margin_dots=0,
            right_margin_dots=0,
        ),
    )


class TestReceiptPrinter(unittest.TestCase):

    def setUp(self):
        self.profile = create_printer_profile()

        self.receipt = MagicMock()

        self.render_plan = RenderPlan(
            printer_id="printer_001",
            operations=[],
            warnings=[],
        )

        self.resolved_plan = RenderPlan(
            printer_id="printer_001",
            operations=[],
            warnings=["Test warning"],
        )

        self.layout_engine = MagicMock()
        self.capability_resolver = MagicMock()
        self.backend = MagicMock()
        self.transport = MagicMock()

        self.layout_engine.layout.return_value = self.render_plan

        self.capability_resolver.resolve.return_value = (
            self.resolved_plan
        )

        self.backend.render.return_value = b"ESC/POS DATA"

        self.transport.send.return_value = len(b"ESC/POS DATA")

        self.printer = ReceiptPrinter(
            printer_profile=self.profile,
            transport=self.transport,
            layout_engine=self.layout_engine,
            capability_resolver=self.capability_resolver,
            backend=self.backend,
        )

    def test_print_receipt(self):

        result = self.printer.print_receipt(self.receipt)

        self.layout_engine.layout.assert_called_once_with(
            self.receipt,
            self.profile,
        )

        self.capability_resolver.resolve.assert_called_once_with(
            self.render_plan,
            self.profile,
        )

        self.backend.render.assert_called_once_with(
            self.resolved_plan,
            self.profile,
        )

        self.transport.send.assert_called_once_with(
            b"ESC/POS DATA"
        )

        self.assertIsInstance(result, PrintResult)

        self.assertEqual(result.printer_id, "printer_001")
        self.assertEqual(result.bytes_sent, 12)
        self.assertEqual(result.warnings, ["Test warning"])

    def test_rejects_wrong_printer_id(self):

        self.render_plan.printer_id = "another_printer"

        with self.assertRaises(PrinterMismatchError):
            self.printer.print_receipt(self.receipt)

        self.capability_resolver.resolve.assert_not_called()
        self.backend.render.assert_not_called()
        self.transport.send.assert_not_called()

    def test_transport_error_propagates(self):

        self.transport.send.side_effect = OSError(
            "Connection failed"
        )

        with self.assertRaises(OSError):
            self.printer.print_receipt(self.receipt)

    def test_backend_error_prevents_sending(self):

        from compiler.escpos_backend import ESCPosError

        self.backend.render.side_effect = ESCPosError(
            "Encoding failed"
        )

        with self.assertRaises(ESCPosError):
            self.printer.print_receipt(self.receipt)

        self.transport.send.assert_not_called()


if __name__ == "__main__":
    unittest.main()
