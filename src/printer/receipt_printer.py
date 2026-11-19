
from dataclasses import dataclass
from typing import List

from printer.printer_profile import PrinterProfile
from compiler.layout_engine import LayoutEngine
from compiler.capability_resolver import CapabilityResolver
from compiler.escpos_backend import ESCPosBackend


@dataclass
class PrintResult:
    printer_id: str
    bytes_sent: int
    warnings: List[str]


class ReceiptPrinter:

    def __init__(
        self,
        printer_profile: PrinterProfile,
        transport,
        layout_engine=None,
        capability_resolver=None,
        backend=None,
    ):
        self.printer_profile = printer_profile
        self.transport = transport

        self.layout_engine = (
            layout_engine or LayoutEngine()
        )

        self.backend = backend or ESCPosBackend()

        # The default resolver is told what the backend can generate,
        # so it never picks a method the backend cannot produce.
        self.capability_resolver = (
            capability_resolver
            or CapabilityResolver(
                supported_qr_methods=self.backend.supported_qr_methods
            )
        )
    def print_receipt(self, receipt) -> PrintResult:
        """
        Compile a receipt and submit its bytes to the printer.

        This method does not guarantee that the printer physically
        printed the receipt. It reports successful byte submission.
        """

        # 1. Convert ReceiptIR into a layout plan.
        render_plan = self.layout_engine.layout(
            receipt,
            self.printer_profile,
        )

        # Ensure the plan targets the configured printer.
        if render_plan.printer_id != self.printer_profile.printer_id:
            raise ValueError(
                "Render plan printer ID does not match "
                "the configured printer profile."
            )

        # 2. Resolve hardware-dependent operations.
        resolved_plan = self.capability_resolver.resolve(
            render_plan,
            self.printer_profile,
        )

        # 3. Convert the resolved plan into ESC/POS bytes.
        printer_data = self.backend.render(
            resolved_plan,
            self.printer_profile,
        )

        # 4. Submit the bytes through the transport.
        bytes_sent = self.transport.send(printer_data)

        # 5. Return the submission result.
        return PrintResult(
            printer_id=self.printer_profile.printer_id,
            bytes_sent=bytes_sent,
            warnings=list(resolved_plan.warnings),
        )
