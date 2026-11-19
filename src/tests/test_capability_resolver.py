import unittest
from unittest.mock import MagicMock

from errors import CapabilityError
from ir.receipt import ReceiptIR, QRNode, TextNode
from compiler.capability_resolver import CapabilityResolver
from compiler.escpos_backend import ESCPosBackend
from compiler.layout_engine import LayoutEngine
from compiler.render_plan import (
    RenderPlan,
    QROperation,
    CutOperation,
    FeedOperation,
)
from printer.printer_profile import (
    PrinterProfile,
    PrinterIdentification,
    PrinterMedia,
    PrinterCapabilities,
    PrinterEncoding,
    PrinterLayout,
)
from printer.receipt_printer import ReceiptPrinter


def make_profile(qr_code=True, raster=True, cutting=True, barcode=False):
    return PrinterProfile(
        printer_id="printer_001",
        identification=PrinterIdentification("EPSON", "TM-T20IV"),
        media=PrinterMedia(80, 576, 48),
        capabilities=PrinterCapabilities(
            qr_code=qr_code, barcode=barcode, raster=raster, cutting=cutting
        ),
        encoding=PrinterEncoding(),
        supported_transports=["network"],
        layout=PrinterLayout(0, 0),
    )


def plan_with(*operations):
    return RenderPlan(printer_id="printer_001", operations=list(operations))


def qr_plan():
    return plan_with(QROperation(data="https://example.com"))


class TestQrResolution(unittest.TestCase):

    def test_native_is_preferred_when_everything_supports_it(self):
        resolved = CapabilityResolver().resolve(
            qr_plan(), make_profile(qr_code=True, raster=True)
        )
        self.assertEqual(resolved.operations[0].method, "native")

    def test_raster_is_used_when_printer_lacks_native(self):
        resolved = CapabilityResolver().resolve(
            qr_plan(), make_profile(qr_code=False, raster=True)
        )
        self.assertEqual(resolved.operations[0].method, "raster")
        self.assertEqual(len(resolved.warnings), 1)
        self.assertIn("raster", resolved.warnings[0])

    def test_neither_method_on_printer_is_an_error(self):
        with self.assertRaises(CapabilityError) as context:
            CapabilityResolver().resolve(
                qr_plan(), make_profile(qr_code=False, raster=False)
            )
        self.assertIn("neither", str(context.exception))

    def test_unknown_method_name_is_rejected(self):
        with self.assertRaises(CapabilityError):
            CapabilityResolver(supported_qr_methods=["natve"])


class TestBackendAwareResolution(unittest.TestCase):
    """The resolver must not pick what the backend cannot generate."""

    def test_native_backend_with_native_printer(self):
        resolver = CapabilityResolver(supported_qr_methods={"native"})
        resolved = resolver.resolve(
            qr_plan(), make_profile(qr_code=True, raster=True)
        )
        self.assertEqual(resolved.operations[0].method, "native")

    def test_native_only_backend_will_not_get_raster(self):
        resolver = CapabilityResolver(supported_qr_methods={"native"})

        with self.assertRaises(CapabilityError) as context:
            resolver.resolve(
                qr_plan(), make_profile(qr_code=False, raster=True)
            )

        message = str(context.exception)
        self.assertIn("backend", message)
        self.assertIn("native", message)

    def test_raster_capable_backend_gets_raster(self):
        resolver = CapabilityResolver(
            supported_qr_methods={"native", "raster"}
        )
        resolved = resolver.resolve(
            qr_plan(), make_profile(qr_code=False, raster=True)
        )
        self.assertEqual(resolved.operations[0].method, "raster")

    def test_real_backend_declares_native_only(self):
        self.assertEqual(
            ESCPosBackend().supported_qr_methods, frozenset({"native"})
        )


class TestOtherOperations(unittest.TestCase):

    def test_cut_without_cutter_is_an_error(self):
        with self.assertRaises(CapabilityError):
            CapabilityResolver().resolve(
                plan_with(CutOperation(mode="full")),
                make_profile(cutting=False),
            )

    def test_cut_with_cutter_passes_through(self):
        cut = CutOperation(mode="partial")
        resolved = CapabilityResolver().resolve(
            plan_with(cut), make_profile(cutting=True)
        )
        self.assertEqual(resolved.operations, [cut])

    def test_other_operations_pass_through_unchanged(self):
        feed = FeedOperation(lines=2)
        resolved = CapabilityResolver().resolve(
            plan_with(feed), make_profile()
        )
        self.assertEqual(resolved.operations, [feed])

    def test_original_plan_is_not_modified(self):
        original = qr_plan()
        CapabilityResolver().resolve(original, make_profile())
        self.assertIsNone(original.operations[0].method)


class TestLayoutDoesNotChooseQrMethod(unittest.TestCase):

    def test_layout_leaves_qr_method_undecided(self):
        plan = LayoutEngine().layout(
            ReceiptIR(nodes=[QRNode(value="https://example.com")]),
            make_profile(),
        )
        self.assertIsNone(plan.operations[0].method)


class TestOrchestratorWiring(unittest.TestCase):
    """ReceiptPrinter must give its default resolver the backend's list."""

    def printer_for(self, profile):
        transport = MagicMock()
        transport.send.side_effect = lambda data: len(data)
        return ReceiptPrinter(profile, transport), transport

    def test_native_qr_is_printed(self):
        printer, transport = self.printer_for(make_profile())

        printer.print_receipt(
            ReceiptIR(nodes=[QRNode(value="https://example.com")])
        )

        sent = transport.send.call_args[0][0]
        self.assertIn(bytes([0x1D, 0x28, 0x6B]), sent)
        self.assertIn(b"https://example.com", sent)

    def test_raster_only_printer_fails_before_any_bytes_are_sent(self):
        printer, transport = self.printer_for(
            make_profile(qr_code=False, raster=True)
        )

        with self.assertRaises(CapabilityError):
            printer.print_receipt(
                ReceiptIR(nodes=[QRNode(value="https://example.com")])
            )

        transport.send.assert_not_called()

    def test_receipt_without_qr_still_prints_on_such_a_printer(self):
        printer, transport = self.printer_for(
            make_profile(qr_code=False, raster=True)
        )

        printer.print_receipt(ReceiptIR(nodes=[TextNode(value="Hello")]))

        transport.send.assert_called_once()


if __name__ == "__main__":
    unittest.main()