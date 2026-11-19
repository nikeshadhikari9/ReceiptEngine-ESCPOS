from dataclasses import replace
from typing import Iterable, Optional

from errors import CapabilityError

from compiler.render_plan import (
    RenderPlan,
    QROperation,
    CutOperation,
)

# Every QR method the engine knows about, best choice first.
QR_METHOD_PREFERENCE = ("native", "raster")


class CapabilityResolver:
    """
    Decides how each hardware-dependent operation will be carried out.

    Two things must both be true before a method can be chosen:

      1. the PRINTER supports it (from the printer profile), and
      2. the BACKEND can actually generate it.

    supported_qr_methods is how the resolver learns about (2). The
    ReceiptPrinter passes in the backend's own list. If it is None,
    the resolver only looks at the printer.
    """

    def __init__(
        self,
        supported_qr_methods: Optional[Iterable[str]] = None
    ):
        if supported_qr_methods is None:
            self.supported_qr_methods = None
            return

        methods = frozenset(supported_qr_methods)
        unknown = methods - set(QR_METHOD_PREFERENCE)

        if unknown:
            raise CapabilityError(
                f"Unknown QR method(s): {sorted(unknown)}. "
                f"Known methods: {list(QR_METHOD_PREFERENCE)}."
            )

        self.supported_qr_methods = methods

    def resolve(
        self,
        render_plan: RenderPlan,
        printer_profile
    ) -> RenderPlan:

        resolved_operations = []

        warnings = list(render_plan.warnings)

        capabilities = printer_profile.capabilities

        for operation in render_plan.operations:

            # ----------------------------------
            # QR CODE RESOLUTION
            # ----------------------------------

            if isinstance(operation, QROperation):

                resolved_qr = self._resolve_qr(
                    operation,
                    capabilities
                )

                resolved_operations.append(resolved_qr)

                raster_warning =  "QR code will be printed using raster fallback."

                if resolved_qr.method == "raster" and raster_warning not in warnings:
                    warnings.append(raster_warning)

            # ----------------------------------
            # CUT RESOLUTION
            # ----------------------------------

            elif isinstance(operation, CutOperation):

                if not capabilities.cutting:
                    raise CapabilityError(
                        "Receipt requires paper cutting, "
                        "but the printer does not support cutting."
                    )

                resolved_operations.append(operation)

            # ----------------------------------
            # OTHER OPERATIONS
            # ----------------------------------

            else:
                resolved_operations.append(operation)

        return RenderPlan(
            printer_id=render_plan.printer_id,
            operations=resolved_operations,
            warnings=warnings
        )


    # ----------------------------------
    # QR RESOLUTION
    # ----------------------------------

    def _resolve_qr(
        self,
        operation: QROperation,
        capabilities
    ) -> QROperation:

        printer_can = {
            "native": capabilities.qr_code,
            "raster": capabilities.raster,
        }

        # Try the best method first. A method is usable only if the
        # printer supports it AND the backend can generate it.
        for method in QR_METHOD_PREFERENCE:

            if not printer_can[method]:
                continue

            if (
                self.supported_qr_methods is not None
                and method not in self.supported_qr_methods
            ):
                continue

            return replace(operation, method=method)

        # Nothing usable. Explain which side is the problem.
        printer_methods = [
            method for method in QR_METHOD_PREFERENCE
            if printer_can[method]
        ]

        if not printer_methods:
            raise CapabilityError(
                "QR printing is not supported. "
                "The printer supports neither native QR "
                "commands nor raster printing."
            )

        raise CapabilityError(
            "QR printing is not possible. "
            f"The printer supports {printer_methods}, but the backend "
            f"can only generate {sorted(self.supported_qr_methods)}."
        )