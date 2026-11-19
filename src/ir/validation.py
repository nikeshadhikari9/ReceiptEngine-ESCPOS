"""
Validation of printer-independent receipts.

validate_receipt() checks the *data* the application gave us. It knows
nothing about printers: whether something fits on a particular printer
is decided later, by the layout engine and the backend.
"""

from math import isfinite

from errors import InvalidReceiptError
from ir.receipt import (
    ReceiptIR,
    TextNode,
    TextStyle,
    ColumnsNode,
    ReceiptColumn,
    SeparatorNode,
    QRNode,
    FeedNode,
    CutNode,
)

ALIGNMENTS = ("left", "center", "right")
TEXT_SIZES = ("normal", "large", "double")
SEPARATOR_PATTERNS = ("solid", "dashed", "dotted")
CUT_MODES = ("full", "partial")


def validate_receipt(receipt) -> None:
    """Raise InvalidReceiptError if the receipt is not valid."""

    if not isinstance(receipt, ReceiptIR):
        raise InvalidReceiptError(
            f"Expected a ReceiptIR, got {type(receipt).__name__}."
        )

    if not isinstance(receipt.nodes, list):
        raise InvalidReceiptError(
            f"ReceiptIR.nodes must be a list, "
            f"got {type(receipt.nodes).__name__}."
        )

    for index, node in enumerate(receipt.nodes):
        _validate_node(index, node)


# --------------------------------------------------
# HELPERS
# --------------------------------------------------

def _fail(index, node, message):
    raise InvalidReceiptError(
        f"nodes[{index}] ({type(node).__name__}): {message}"
    )


def _is_int(value) -> bool:
    # bool is a kind of int in Python (True == 1), so exclude it.
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and isfinite(value)
    )


def _check_printable_text(index, node, label, value):
    """Text must be a string without printer control characters."""

    if not isinstance(value, str):
        _fail(
            index, node,
            f"{label} must be a string, got {type(value).__name__}."
        )

    for character in value:
        code = ord(character)

        # "\n" is allowed: the layout engine turns it into a new line.
        # Other control characters (ESC, GS, NUL, tab...) would be sent
        # to the printer as raw bytes and could act as printer commands.
        if character != "\n" and (code < 0x20 or code == 0x7F):
            _fail(
                index, node,
                f"{label} contains a control character "
                f"(code {code}), which is not allowed."
            )


def _check_choice(index, node, label, value, allowed):
    if value not in allowed:
        _fail(
            index, node,
            f"{label} must be one of {list(allowed)}, got {value!r}."
        )


# --------------------------------------------------
# NODE VALIDATION
# --------------------------------------------------

def _validate_node(index, node):

    section = getattr(node, "section", None)

    if section is not None and not isinstance(section, str):
        _fail(index, node, "section must be a string or None.")

    if isinstance(node, TextNode):
        _check_printable_text(index, node, "value", node.value)

        style = node.style

        if not isinstance(style, TextStyle):
            _fail(index, node, "style must be a TextStyle.")

        _check_choice(index, node, "alignment", style.alignment, ALIGNMENTS)
        _check_choice(index, node, "size", style.size, TEXT_SIZES)

        if not isinstance(style.bold, bool):
            _fail(index, node, "bold must be True or False.")

    elif isinstance(node, ColumnsNode):
        if not isinstance(node.columns, list) or not node.columns:
            _fail(index, node, "columns must be a non-empty list.")

        for column_number, column in enumerate(node.columns):
            label = f"columns[{column_number}]"

            if not isinstance(column, ReceiptColumn):
                _fail(index, node, f"{label} must be a ReceiptColumn.")

            _check_printable_text(
                index, node, f"{label}.value", column.value
            )

            if not _is_number(column.width_percent) or column.width_percent <= 0:
                _fail(
                    index, node,
                    f"{label}.width_percent must be a number "
                    f"greater than 0, got {column.width_percent!r}."
                )

            _check_choice(
                index, node, f"{label}.alignment",
                column.alignment, ALIGNMENTS
            )

    elif isinstance(node, SeparatorNode):
        _check_choice(
            index, node, "pattern", node.pattern, SEPARATOR_PATTERNS
        )

    elif isinstance(node, QRNode):
        if not isinstance(node.value, str) or node.value == "":
            _fail(index, node, "value must be a non-empty string.")
        if not _is_int(node.size) or not (1 <= node.size <= 16):
            _fail(
                index, node,
                f"size must be a whole number between 1 and 16, "
                f"got {node.size!r}."
            )

    elif isinstance(node, FeedNode):
        if not _is_int(node.lines) or not (0 <= node.lines <= 255):
            _fail(
                index, node,
                f"lines must be a whole number between 0 and 255, "
                f"got {node.lines!r}."
            )

    elif isinstance(node, CutNode):
        _check_choice(index, node, "mode", node.mode, CUT_MODES)

    else:
        _fail(index, node, "unsupported receipt node type.")