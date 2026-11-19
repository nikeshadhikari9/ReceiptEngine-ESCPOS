from ir.receipt import (
    ReceiptIR,
    TextNode,
    TextStyle,
    ReceiptColumn,
    ColumnsNode,
    SeparatorNode,
    QRNode,
    FeedNode,
    CutNode,
)

from printer.printer_profile import (
    PrinterProfile,
    PrinterIdentification,
    PrinterMedia,
    PrinterCapabilities,
    PrinterEncoding,
    PrinterLayout,
)

from compiler.layout_engine import LayoutEngine


# -----------------------------------------
# PRINTER
# -----------------------------------------

printer = PrinterProfile(
    printer_id="printer_001",

    identification=PrinterIdentification(
        manufacturer="EPSON",
        model="TM-T20IV"
    ),

    media=PrinterMedia(
        paper_width_mm=80,
        printable_width_dots=576,
        character_columns=48
    ),

    capabilities=PrinterCapabilities(
        qr_code=True,
        barcode=True,
        raster=True,
        cutting=True
    ),

    encoding=PrinterEncoding(),

    supported_transports=["USB", "serial"],

    layout=PrinterLayout(
        left_margin_dots=0,
        right_margin_dots=0
    )
)


# -----------------------------------------
# RECEIPT
# -----------------------------------------

receipt = ReceiptIR(
    nodes=[
        TextNode(
            value="JALDIMAI FOODS",
            style=TextStyle(
                alignment="center",
                bold=True,
                size="normal"
            )
        ),

        TextNode(
            value="Order #1052",
            style=TextStyle(
                alignment="left"
            )
        ),

        SeparatorNode(
            pattern="solid"
        ),

        ColumnsNode(
            columns=[
                ReceiptColumn(
                    value="Chicken Momo - Special",
                    width_percent=70,
                    alignment="left"
                ),

                ReceiptColumn(
                    value="Rs. 350",
                    width_percent=30,
                    alignment="right"
                )
            ]
        ),

        ColumnsNode(
            columns=[
                ReceiptColumn(
                    value="Coke",
                    width_percent=70,
                    alignment="left"
                ),

                ReceiptColumn(
                    value="Rs. 60",
                    width_percent=30,
                    alignment="right"
                )
            ]
        ),

        SeparatorNode(
            pattern="dashed"
        ),

        TextNode(
            value="Total: Rs. 410",
            style=TextStyle(
                alignment="right",
                bold=True
            )
        ),

        QRNode(
            value="https://example.com/order/1052",
            size=6
        ),

        FeedNode(
            lines=3
        ),

        CutNode(
            mode="full"
        )
    ]
)


# -----------------------------------------
# RUN LAYOUT ENGINE
# -----------------------------------------

engine = LayoutEngine()

render_plan = engine.layout(
    receipt,
    printer
)


# -----------------------------------------
# DISPLAY OUTPUT
# -----------------------------------------

print("Printer:", render_plan.printer_id)

print("\nOperations:")

for operation in render_plan.operations:

    print("\n", type(operation).__name__)

    if hasattr(operation, "text"):
        print("Text:", operation.text)

    elif hasattr(operation, "columns"):
        for line in operation.lines:
            print([
                (column.text, column.width, column.alignment)
                for column in line.columns
            ])

    elif hasattr(operation, "repeat"):
        print("Repeat:", operation.repeat)

    elif hasattr(operation, "data"):
        print("QR Data:", operation.data)

    elif hasattr(operation, "lines"):
        print("Feed:", operation.lines)

    elif hasattr(operation, "mode"):
        print("Mode:", operation.mode)