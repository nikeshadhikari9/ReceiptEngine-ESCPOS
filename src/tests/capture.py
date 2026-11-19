"""Unit tests for the capture area of the receipt engine."""

from pathlib import Path

from printer.printer_profile import load_printer_profile
from printer.receipt_printer import ReceiptPrinter

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


PROFILE = (
    Path(__file__).resolve().parents[1]
    / "printer"
    / "epson_tm_t20iv.json"
)


class RecordingTransport:
    def __init__(self):
        """Internal helper implementing init."""
        self.sent = b""

    def send(self, data):
        """Function providing send behavior for the receipt engine."""
        self.sent += data
        return len(data)


profile = load_printer_profile(PROFILE)
transport = RecordingTransport()

receipt = ReceiptIR(nodes=[
    # Header
    TextNode(
        value="JALDIMAI FOODS",
        style=TextStyle(
            alignment="center",
            bold=True,
            size="double",
        ),
    ),

    TextNode(
        value="Food Delivery Service",
        style=TextStyle(
            alignment="center",
            bold=False,
            size="normal",
        ),
    ),

    SeparatorNode(pattern="dotted"),

    # Order details
    TextNode(
        value="Order #1052",
        style=TextStyle(
            alignment="left",
            bold=True,
            size="normal",
        ),
    ),

    TextNode(
        value="19 Nov 2026",
        style=TextStyle(
            alignment="left",
            size="normal",
        ),
    ),

    SeparatorNode(pattern="dashed"),

    # Items
    ColumnsNode(columns=[
        ReceiptColumn("Chicken Momo", 70),
        ReceiptColumn("Rs. 350", 30, "right"),
    ]),

    SeparatorNode(pattern="solid"),

    TextNode(
        value="TOTAL: Rs. 350",
        style=TextStyle(
            alignment="right",
            bold=True,
            size="large",
        ),
    ),

    FeedNode(lines=1),

    QRNode(
        value="https://example.com/order/1052",
        size=6,
    ),

    FeedNode(lines=3),

    CutNode(mode="full"),
])

ReceiptPrinter(profile, transport).print_receipt(receipt)

# Save ESC/POS binary
with open("receipt.bin", "wb") as file:
    file.write(transport.sent)

print(f"{len(transport.sent)} bytes → receipt.bin")

