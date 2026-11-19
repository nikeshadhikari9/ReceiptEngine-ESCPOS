"""
ESC/POS backend: turns a resolved RenderPlan into ESC/POS bytes.

ESCPosBackend itself holds no per-receipt data. Every call to render()
creates a new _RenderJob, which owns the output buffer for that one
receipt. Because jobs never share anything, several receipts can be
rendered at the same time by the same backend object.
"""

from typing import List

from errors import BackendError

from compiler.text_encoder import TextEncoder

from compiler.render_plan import (
    TextOperation,
    ColumnsOperation,
    SeparatorOperation,
    QROperation,
    FeedOperation,
    CutOperation,
)


class ESCPosError(BackendError):
    """Raised when an ESC/POS operation cannot be encoded."""
    pass


# The QR methods this backend can really generate. The CapabilityResolver
# reads this (through ESCPosBackend.supported_qr_methods) so it never
# chooses a method the backend cannot produce. Add "raster" here only
# when raster QR generation is actually implemented.
SUPPORTED_QR_METHODS = frozenset({"native"})


class ESCPosBackend:
    """
    Public entry point. Stateless: safe to share between threads.
    """

    # Read by the CapabilityResolver (see SUPPORTED_QR_METHODS above).
    supported_qr_methods = SUPPORTED_QR_METHODS

    def render(self, render_plan, printer_profile) -> bytes:
        """
        Convert a resolved RenderPlan into ESC/POS bytes.
        Does not communicate with a physical printer.
        """

        return _RenderJob(printer_profile).run(render_plan)


class _RenderJob:
    """
    Builds the bytes for ONE receipt. Created fresh by every render()
    call and thrown away afterwards, so it can keep its own state
    (the output buffer) without affecting any other receipt.
    """

    ESC = 0x1B
    GS = 0x1D
    LF = 0x0A

    def __init__(self, printer_profile):

        self.output = bytearray()

        # Decides which code page each piece of text needs.
        self.encoder = TextEncoder(printer_profile.encoding)

        # The code page the printer is currently on (None = unknown or
        # none selected).
        self.current_page = None

    def run(self, render_plan) -> bytes:

        # Initialize printer (this also resets its code page)
        self._initialize()

        # Select the profile's first code page, if it lists any
        default_page = self.encoder.default_page

        if default_page is not None:
            self._select_code_page(default_page)

        # Process operations in order
        for operation in render_plan.operations:

            if isinstance(operation, TextOperation):
                self._text(operation)

            elif isinstance(operation, ColumnsOperation):
                self._columns(operation)

            elif isinstance(operation, SeparatorOperation):
                self._separator(operation)

            elif isinstance(operation, QROperation):
                self._qr(operation)

            elif isinstance(operation, FeedOperation):
                self._feed(operation)

            elif isinstance(operation, CutOperation):
                self._cut(operation)

            else:
                raise ESCPosError(
                    f"Unsupported operation: "
                    f"{type(operation).__name__}"
                )

        return bytes(self.output)

    # -----------------------------------------
    # LOW-LEVEL COMMAND WRITER
    # -----------------------------------------

    def _write(self, data: bytes):
        self.output.extend(data)

    def _command(self, *values: int):
        self.output.extend(values)

    def _write_text(self, text: str):
        """
        Encode text with the printer's code pages and write it,
        switching code page whenever the text needs it.
        """

        for run in self.encoder.encode(text, self.current_page):

            if run.page is not None and run.page != self.current_page:
                self._select_code_page(run.page)

            self._write(run.data)

    def _select_code_page(self, page):

        # ESC t n
        self._command(self.ESC, 0x74, page.page_id)

        self.current_page = page

    # -----------------------------------------
    # INITIALIZATION
    # -----------------------------------------

    def _initialize(self):
        # ESC @
        self._command(self.ESC, 0x40)

    # -----------------------------------------
    # TEXT STYLE
    # -----------------------------------------

    def _alignment(self, alignment: str):

        alignment_values = {
            "left": 0,
            "center": 1,
            "right": 2,
        }

        if alignment not in alignment_values:
            raise ESCPosError(
                f"Unsupported alignment: {alignment}"
            )

        # ESC a n
        self._command(
            self.ESC,
            0x61,
            alignment_values[alignment]
        )

    def _bold(self, enabled: bool):

        # ESC E n
        self._command(
            self.ESC,
            0x45,
            1 if enabled else 0
        )

    def _text_size(self, size: str):

        size_values = {
            "normal": 0x00,
            "large": 0x11,
            "double": 0x11,
        }

        if size not in size_values:
            raise ESCPosError(
                f"Unsupported text size: {size}"
            )

        # GS ! n
        self._command(
            self.GS,
            0x21,
            size_values[size]
        )

    def _reset_text_style(self):
        self._bold(False)
        self._text_size("normal")
        self._alignment("left")

    # -----------------------------------------
    # TEXT OPERATION
    # -----------------------------------------

    def _text(self, operation: TextOperation):

        style = operation.style

        self._alignment(style.alignment)
        self._bold(style.bold)
        self._text_size(style.size)

        self._write_text(operation.text)

        self._command(self.LF)

        self._reset_text_style()

    # -----------------------------------------
    # COLUMN OPERATION
    # -----------------------------------------

    def _columns(self, operation: ColumnsOperation):

        # Column rows are always printed in the default style and alignment.
        self._reset_text_style()

        for line in operation.lines:

            parts = []

            for column in line.columns:

                if column.width <= 0:
                    raise ESCPosError(
                        "Column width must be greater than zero"
                    )

                text = column.text

                if len(text) > column.width:
                    raise ESCPosError(
                        f"Column text exceeds allocated width: {text}"
                    )

                if column.alignment == "left":
                    formatted = text.ljust(column.width)

                elif column.alignment == "right":
                    formatted = text.rjust(column.width)

                elif column.alignment == "center":
                    formatted = text.center(column.width)

                else:
                    raise ESCPosError(
                        f"Unsupported column alignment: "
                        f"{column.alignment}"
                    )

                parts.append(formatted)

            # Combine columns into one physical line
            combined_text = "".join(parts)

            self._alignment("left")

            self._write_text(combined_text)

            self._command(self.LF)

    # -----------------------------------------
    # SEPARATOR OPERATION
    # -----------------------------------------

    def _separator(self, operation: SeparatorOperation):

        if operation.repeat < 0:
            raise ESCPosError(
                "Separator repeat cannot be negative"
            )

        if len(operation.character) != 1:
            raise ESCPosError(
                "Separator must contain exactly one character"
            )

        text = operation.character * operation.repeat

        self._alignment("left")

        self._write_text(text)

        self._command(self.LF)

    # -----------------------------------------
    # QR CODE OPERATION
    # -----------------------------------------

    def _qr(self, operation: QROperation):

        if operation.method is None:
            raise ESCPosError(
                "QR operation has no method. The plan must be resolved "
                "by the CapabilityResolver before it reaches the backend."
            )

        if operation.method not in SUPPORTED_QR_METHODS:
            raise ESCPosError(
                f"QR method '{operation.method}' is not supported by "
                f"the ESC/POS backend. Supported methods: "
                f"{sorted(SUPPORTED_QR_METHODS)}."
            )

        if not operation.data:
            raise ESCPosError(
                "QR data cannot be empty"
            )

        if not 1 <= operation.size <= 16:
            raise ESCPosError(
                "QR module size must be between 1 and 16"
            )

        self._alignment(operation.alignment)

        # QR data is read by a scanner, not printed with the printer's
        # character tables, so it is always UTF-8.
        try:
            data = operation.data.encode("utf-8")
        except UnicodeEncodeError as error:
            raise ESCPosError(
                f"QR data cannot be encoded as UTF-8: {error}"
            ) from error

        if len(data) + 3 > 65535:
            raise ESCPosError(
                "QR data is too large for this command"
            )

        # Select QR model 2
        # GS ( k 04 00 31 41 32 00
        self._command(
            self.GS, 0x28, 0x6B,
            0x04, 0x00,
            0x31, 0x41, 0x32, 0x00
        )

        # Set QR module size
        # GS ( k 03 00 31 43 n
        self._command(
            self.GS, 0x28, 0x6B,
            0x03, 0x00,
            0x31, 0x43, operation.size
        )

        # Set error correction level M
        # GS ( k 03 00 31 45 31
        self._command(
            self.GS, 0x28, 0x6B,
            0x03, 0x00,
            0x31, 0x45, 0x31
        )

        # Store QR data
        payload_length = len(data) + 3

        p_l = payload_length & 0xFF
        p_h = (payload_length >> 8) & 0xFF

        # GS ( k pL pH 31 50 30 data
        self._command(
            self.GS, 0x28, 0x6B,
            p_l, p_h,
            0x31, 0x50, 0x30
        )

        self._write(data)

        # Print QR code
        # GS ( k 03 00 31 51 30
        self._command(
            self.GS, 0x28, 0x6B,
            0x03, 0x00,
            0x31, 0x51, 0x30
        )

        self._command(self.LF)

        self._alignment("left")

    # -----------------------------------------
    # FEED OPERATION
    # -----------------------------------------

    def _feed(self, operation: FeedOperation):

        if not 0 <= operation.lines <= 255:
            raise ESCPosError(
                "Feed lines must be between 0 and 255"
            )

        # ESC d n
        self._command(
            self.ESC,
            0x64,
            operation.lines
        )

    # -----------------------------------------
    # CUT OPERATION
    # -----------------------------------------

    def _cut(self, operation: CutOperation):

        cut_modes = {
            "full": 0,
            "partial": 1,
        }

        if operation.mode not in cut_modes:
            raise ESCPosError(
                f"Unsupported cut mode: {operation.mode}"
            )

        # GS V m
        self._command(
            self.GS,
            0x56,
            cut_modes[operation.mode]
        )