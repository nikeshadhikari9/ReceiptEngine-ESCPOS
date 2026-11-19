from printer.printer_profile import (
    PrinterProfile,
    PrinterIdentification,
    PrinterMedia,
    PrinterCapabilities,
    PrinterEncoding,
    PrinterLayout
)

from printer.transport_config import TransportConfig


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


connection = TransportConfig(
    transport_type="USB",
    device="USB001"
)


print(printer)
print(connection)

print("Printable width:", printer.media.printable_width_dots)
print("QR supported:", printer.capabilities.qr_code)
print("Connection:", connection.transport_type)
