
from math import ceil, floor
from typing import List

from errors import LayoutError
from ir.validation import validate_receipt

from ir.receipt import (
    ReceiptIR,
    TextNode,
    ColumnsNode,
    SeparatorNode,
    QRNode,
    FeedNode,
    CutNode,
)

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


class LayoutEngine:

    def layout(
        self,
        receipt: ReceiptIR,
        printer_profile
    ) -> RenderPlan:

        # 0. Reject invalid receipt data before doing any work
        validate_receipt(receipt)

        # 1. Calculate available printable character width
        usable_width = self._calculate_usable_width(printer_profile)

        # 2. Create an empty RenderPlan
        render_plan = RenderPlan(
            printer_id=printer_profile.printer_id
        )

        # 3. Process each Receipt IR node in order
        for node in receipt.nodes:

            if isinstance(node, TextNode):
                operations = self._layout_text(
                    node,
                    usable_width
                )

                render_plan.operations.extend(operations)

            elif isinstance(node, ColumnsNode):
                operation = self._layout_columns(
                    node,
                    usable_width
                )

                render_plan.operations.append(operation)

            elif isinstance(node, SeparatorNode):
                operation = self._layout_separator(
                    node,
                    usable_width
                )

                render_plan.operations.append(operation)

            elif isinstance(node, QRNode):
                operation = self._layout_qr(node)

                render_plan.operations.append(operation)

            elif isinstance(node, FeedNode):
                operation = self._layout_feed(node)

                render_plan.operations.append(operation)

            elif isinstance(node, CutNode):
                operation = self._layout_cut(node)

                render_plan.operations.append(operation)

            else:
                raise LayoutError(
                    f"Unsupported receipt node: "
                    f"{type(node).__name__}"
                )

        return render_plan


    # --------------------------------------------------
    # WIDTH CALCULATION
    # --------------------------------------------------

    def _calculate_usable_width(self, printer_profile) -> int:

        media = printer_profile.media
        layout = printer_profile.layout

        total_columns = media.character_columns
        printable_dots = media.printable_width_dots

        left_margin = layout.left_margin_dots
        right_margin = layout.right_margin_dots

        if total_columns <= 0:
            raise LayoutError(
                "Printer character_columns must be greater than 0"
            )

        if printable_dots <= 0:
            raise LayoutError(
                "Printer printable_width_dots must be greater than 0"
            )

        if left_margin < 0 or right_margin < 0:
            raise LayoutError(
                "Printer margins cannot be negative"
            )

        if left_margin + right_margin >= printable_dots:
            raise LayoutError(
                "Printer margins consume the entire printable width"
            )

        # Approximate dots occupied by one character column
        dots_per_column = printable_dots / total_columns

        # Convert physical margins to character columns
        left_columns = ceil(
            left_margin / dots_per_column
        )

        right_columns = ceil(
            right_margin / dots_per_column
        )

        usable_columns = (
            total_columns
            - left_columns
            - right_columns
        )

        if usable_columns <= 0:
            raise LayoutError(
                "No usable character columns remain"
            )

        return usable_columns


    # --------------------------------------------------
    # TEXT LAYOUT
    # --------------------------------------------------

    def _layout_text(
        self,
        node: TextNode,
        width: int
    ) -> List[TextOperation]:

        text = node.value

        style = node.style

        # Width multiplier for larger text
        size_multiplier = {
            "normal": 1,
            "large": 2,
            "double": 2,
        }

        multiplier = size_multiplier.get(
            style.size,
            1
        )

        effective_width = width // multiplier

        if effective_width <= 0:
            raise LayoutError(
                "Text style is too large for printer width"
            )

        # Wrap text
        wrapped_lines = self._wrap_text(
            text,
            effective_width
        )

        # Convert each wrapped line into TextOperation
        operations = []

        for line in wrapped_lines:

            render_style = RenderStyle(
                alignment=style.alignment,
                bold=style.bold,
                size=style.size
            )

            operations.append(
                TextOperation(
                    text=line,
                    style=render_style
                )
            )

        return operations


    # --------------------------------------------------
    # COLUMN LAYOUT
    # --------------------------------------------------

    def _layout_columns(
        self,
        node: ColumnsNode,
        width: int
    ) -> ColumnsOperation:

        columns = node.columns

        if not columns:
            raise LayoutError(
                "ColumnsNode contains no columns"
            )

        # 1. Calculate each column's allocated width
        column_widths = self._calculate_column_widths(
            columns,
            width
        )

        # 2. Wrap each column's text
        wrapped_columns = []

        for column, allocated_width in zip(
            columns,
            column_widths
        ):

            wrapped_text = self._wrap_text(
                column.value,
                allocated_width
            )

            wrapped_columns.append(
                wrapped_text
            )

        # 3. Find the number of physical lines required
        line_count = max(
            len(column_lines)
            for column_lines in wrapped_columns
        )

        # 4. Build physical RenderLines
        render_lines = []

        for line_index in range(line_count):

            render_columns = []

            for column_index, column in enumerate(columns):

                allocated_width = column_widths[
                    column_index
                ]

                column_lines = wrapped_columns[
                    column_index
                ]

                # If this column has no text on this line,
                # use an empty string.
                if line_index < len(column_lines):

                    text = column_lines[line_index]

                else:

                    text = ""

                render_columns.append(
                    RenderColumn(
                        text=text,
                        width=allocated_width,
                        alignment=column.alignment
                    )
                )

            render_lines.append(
                RenderLine(
                    columns=render_columns
                )
            )

        # 5. Return the completed operation
        return ColumnsOperation(
            lines=render_lines
        )


    # --------------------------------------------------
    # COLUMN WIDTH ALLOCATION
    # --------------------------------------------------

    def _calculate_column_widths(
        self,
        columns,
        total_width: int
    ) -> List[int]:

        percentages = [
            column.width_percent
            for column in columns
        ]

        if any(
            percentage <= 0
            for percentage in percentages
        ):
            raise LayoutError(
                "Column widths must be greater than zero"
            )

        percentage_total = sum(percentages)

        if percentage_total <= 0:
            raise LayoutError(
                "Invalid total column width"
            )

        # Normalize percentages if they don't total 100
        normalized_percentages = [
            percentage / percentage_total
            for percentage in percentages
        ]

        # Calculate exact fractional widths
        exact_widths = [
            percentage * total_width
            for percentage in normalized_percentages
        ]

        # Initially assign floor values
        allocated_widths = [
            floor(value)
            for value in exact_widths
        ]

        # Calculate remaining columns
        remaining_width = (
            total_width
            - sum(allocated_widths)
        )

        
        # Each floor() loses less than one column, so the total loss is
        # smaller than the number of columns. If this ever fails, the
        # rounding strategy above has changed and needs another look.
        assert 0 <= remaining_width < len(allocated_widths)
        
        # Distribute remaining columns to the columns
        # with the largest fractional remainders
        remainders = [
            exact_width - allocated_width
            for exact_width, allocated_width
            in zip(
                exact_widths,
                allocated_widths
            )
        ]

        indexes = sorted(
            range(len(remainders)),
            key=lambda index: remainders[index],
            reverse=True
        )

        for index in indexes[:remaining_width]:

            allocated_widths[index] += 1

        # Prevent columns from receiving zero width
        if any(
            allocated_width <= 0
            for allocated_width in allocated_widths
        ):
            raise LayoutError(
                "A column received zero character width. "
                "Increase printer width or reduce column count."
            )

        return allocated_widths


    # --------------------------------------------------
    # SEPARATOR LAYOUT
    # --------------------------------------------------

    def _layout_separator(
        self,
        node: SeparatorNode,
        width: int
    ) -> SeparatorOperation:

        pattern_characters = {
            "solid": "-",
            "dashed": "=",
            "dotted": ".",
        }

        character = pattern_characters.get(
            node.pattern
        )

        if character is None:
            raise LayoutError(
                f"Unsupported separator pattern: "
                f"{node.pattern}"
            )

        return SeparatorOperation(
            character=character,
            repeat=width
        )


    # --------------------------------------------------
    # QR LAYOUT
    # --------------------------------------------------

    def _layout_qr(
        self,
        node: QRNode
    ) -> QROperation:

        if not node.value:
            raise LayoutError(
                "QR code data cannot be empty"
            )

        if node.size <= 0:
            raise LayoutError(
                "QR code size must be greater than zero"
            )

        return QROperation(
            data=node.value,

            # Layout does not decide how the printer implements QR.
            # CapabilityResolver chooses the method later.
            method=None,

            size=node.size,

            alignment="center"
        )


    # --------------------------------------------------
    # FEED LAYOUT
    # --------------------------------------------------

    def _layout_feed(
        self,
        node: FeedNode
    ) -> FeedOperation:

        if node.lines < 0:
            raise LayoutError(
                "Feed lines cannot be negative"
            )

        return FeedOperation(
            lines=node.lines
        )


    # --------------------------------------------------
    # CUT LAYOUT
    # --------------------------------------------------

    def _layout_cut(
        self,
        node: CutNode
    ) -> CutOperation:

        return CutOperation(
            mode=node.mode
        )


    # --------------------------------------------------
    # TEXT WRAPPING
    # --------------------------------------------------

    def _wrap_text(
        self,
        text: str,
        width: int
    ) -> List[str]:

        if width <= 0:
            raise LayoutError(
                "Text wrapping width must be greater than zero"
            )

        if text == "":
            return [""]

        result = []

        # Handle explicit newline characters
        paragraphs = text.split("\n")

        for paragraph in paragraphs:

            # Preserve blank lines
            if paragraph == "":
                result.append("")
                continue

            words = paragraph.split()

            current_line = ""

            for word in words:

                # Handle words longer than the width
                if len(word) > width:

                    # Flush current line first
                    if current_line:

                        result.append(current_line)
                        current_line = ""

                    # Split the long word into chunks
                    chunks = [
                        word[index:index + width]
                        for index in range(
                            0,
                            len(word),
                            width
                        )
                    ]

                    # Keep final chunk for possible
                    # combination with the next word
                    result.extend(chunks[:-1])

                    current_line = chunks[-1]

                    continue

                # Try to add the word to current line
                if current_line:

                    candidate = (
                        current_line
                        + " "
                        + word
                    )

                else:

                    candidate = word

                # If candidate fits, continue line
                if len(candidate) <= width:

                    current_line = candidate

                else:

                    # Otherwise finish previous line
                    result.append(current_line)

                    current_line = word

            # Add final line of paragraph
            if current_line:

                result.append(current_line)

        return result
