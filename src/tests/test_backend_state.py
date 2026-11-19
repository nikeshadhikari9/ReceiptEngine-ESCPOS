import threading
import unittest

from compiler.escpos_backend import ESCPosBackend, ESCPosError
from compiler.render_plan import (
    RenderPlan,
    TextOperation,
    QROperation,
)
from printer.printer_profile import (
    PrinterProfile,
    PrinterIdentification,
    PrinterMedia,
    PrinterCapabilities,
    PrinterEncoding,
    PrinterLayout,
)


def make_profile():
    return PrinterProfile(
        printer_id="printer_001",
        identification=PrinterIdentification("EPSON", "TM-T20IV"),
        media=PrinterMedia(80, 576, 48),
        capabilities=PrinterCapabilities(qr_code=True, cutting=True),
        encoding=PrinterEncoding(),
        supported_transports=["network"],
        layout=PrinterLayout(0, 0),
    )


def text_plan(*texts):
    return RenderPlan(
        printer_id="printer_001",
        operations=[TextOperation(text=text) for text in texts],
    )


class TestBackendHoldsNoState(unittest.TestCase):

    def setUp(self):
        self.backend = ESCPosBackend()
        self.profile = make_profile()

    def test_backend_keeps_nothing_between_renders(self):
        self.backend.render(text_plan("hello"), self.profile)

        self.assertNotIn("output", vars(self.backend))
        self.assertNotIn("encoding", vars(self.backend))

    def test_render_inside_another_render_does_not_corrupt_either(self):
        """
        While the backend is in the middle of printing receipt A, we make
        it render receipt B on the same backend object. With shared state
        this wiped A's buffer. Now A must come out exactly as if B had
        never happened.
        """
        backend = self.backend
        profile = self.profile
        other_plan = text_plan("OTHER RECEIPT")
        triggered = []

        class Sneaky(str):
            def encode(self, *args, **kwargs):
                if not triggered:
                    triggered.append(True)
                    backend.render(other_plan, profile)
                return super().encode(*args, **kwargs)

        expected = backend.render(text_plan("FIRST", "SECOND"), profile)
        actual = backend.render(text_plan("FIRST", Sneaky("SECOND")), profile)

        self.assertTrue(triggered)
        self.assertEqual(actual, expected)

    def test_many_threads_can_share_one_backend(self):
        backend = self.backend
        profile = self.profile
        failures = []

        def worker(number):
            plan = text_plan(f"RECEIPT {number}", "x" * 40)
            expected = backend.render(plan, profile)

            for _ in range(300):
                if backend.render(plan, profile) != expected:
                    failures.append(number)
                    return

        threads = [
            threading.Thread(target=worker, args=(n,)) for n in range(8)
        ]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        self.assertEqual(failures, [])


class TestBackendQrChecks(unittest.TestCase):

    def render_qr(self, method):
        plan = RenderPlan(
            printer_id="printer_001",
            operations=[QROperation(data="https://example.com",
                                    method=method)],
        )
        return ESCPosBackend().render(plan, make_profile())

    def test_unresolved_qr_message_points_at_the_resolver(self):
        with self.assertRaises(ESCPosError) as context:
            self.render_qr(None)

        self.assertIn("CapabilityResolver", str(context.exception))

    def test_unsupported_method_message_lists_supported_ones(self):
        with self.assertRaises(ESCPosError) as context:
            self.render_qr("raster")

        message = str(context.exception)
        self.assertIn("raster", message)
        self.assertIn("native", message)

    def test_native_method_still_works(self):
        self.assertIn(bytes([0x31, 0x50, 0x30]), self.render_qr("native"))


if __name__ == "__main__":
    unittest.main()