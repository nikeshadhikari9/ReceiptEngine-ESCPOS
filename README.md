# ReceiptEngine-ESCPOS

ReceiptEngine-ESCPOS is a printer-independent Python library for building, validating, laying out, compiling, and sending receipts to ESC/POS thermal printers. Applications construct a structured receipt with the classes in `src/ir/`; the engine then converts that receipt into printer commands and submits the resulting bytes through a transport.

The project separates receipt content from printer mechanics. A receipt does not contain ESC/POS bytes, and the layout system does not send data to a printer. This separation makes receipts reusable across printers and makes it easier to test layout, encoding, capabilities, and transport behavior independently.

## Architecture

The print pipeline is:

```text
Printer Profile (JSON or Python objects)
                    +
ReceiptIR             -> ReceiptPrinter
                              |
                              v
                     LayoutEngine
                              |
                              v
                       RenderPlan
                              |
                              v
                   CapabilityResolver
                              |
                              v
                      ESCPosBackend
                              |
                              v
                       ESC/POS bytes
                              |
                              v
                         Transport
```

The main stages are:

1. **Receipt validation** verifies printer-independent content, node types, styles, widths, text characters, QR data, feed lines, and cut modes.
2. **Printer-profile validation** verifies printer dimensions, capabilities, text encodings, margins, and supported transports.
3. **Layout** converts each receipt node into a printer-aware intermediate `RenderPlan`.
4. **Capability resolution** chooses available implementations for hardware-dependent operations such as native or raster QR codes.
5. **ESC/POS encoding** converts the resolved render plan into binary printer commands.
6. **Transport** sends the bytes to a network printer or supplies the data to another transport implementation.

## Project Structure

```text
ReceiptEngine-ESCPOS/
|-- main.py                         # Empty top-level entry point
|-- src/
|   |-- ir/
|   |   |-- receipt.py              # Receipt IR data classes
|   |   `-- validation.py           # Receipt IR validation
|   |-- compiler/
|   |   |-- layout_engine.py        # Receipt-to-render-plan layout
|   |   |-- render_plan.py          # Printer-aware intermediate operations
|   |   |-- capability_resolver.py  # Hardware capability selection
|   |   |-- text_encoder.py         # Code-page text encoding
|   |   `-- escpos_backend.py       # ESC/POS command generation
|   |-- printer/
|   |   |-- printer_profile.py      # Profile models and JSON loading
|   |   |-- transport_config.py     # Transport configuration
|   |   |-- transport.py            # Network transport implementation
|   |   |-- receipt_printer.py      # Pipeline orchestrator
|   |   `-- epson_tm_t20iv.json     # Example Epson TM-T20IV profile
|   |-- demo/                       # Standalone usage demonstrations
|   `-- tests/                      # Unit tests and test utilities
`-- documentation/
    `-- Flow_diagram.png             # Project flow illustration
```

## Receipt Intermediate Representation

The classes in `src/ir/receipt.py` describe what should be printed without specifying ESC/POS commands.

### `ReceiptIR`

The root object contains a receipt `version`, optional `metadata`, and an ordered list of receipt nodes.

```python
ReceiptIR(
    version=1,
    metadata={"order_id": "1052"},
    nodes=[...]
)
```

### Receipt Nodes

- **`TextNode`** prints text with alignment, bold, and text-size settings.
- **`ReceiptColumn`** represents one column value and percentage-based width.
- **`ColumnsNode`** prints a row containing multiple columns and supports wrapping and horizontal alignment.
- **`SeparatorNode`** prints solid, dashed, or dotted horizontal separators.
- **`QRNode`** describes a QR code value and module size.
- **`FeedNode`** advances paper by a number of lines.
- **`CutNode`** requests a full or partial paper cut.

### `TextStyle`

`TextStyle` controls a text node:

- `alignment`: `left`, `center`, or `right`
- `bold`: `True` or `False`
- `size`: `normal`, `large`, or `double`

The `section` field is available on every receipt node as an optional application-defined label. The engine validates its type but does not use it while printing.

## Receipt Validation

`src/ir/validation.py` exposes `validate_receipt()`. It raises `InvalidReceiptError` for invalid receipt structures or values.

Validation checks include:

- `ReceiptIR` and its `nodes` list must have the correct types.
- Text must be a string and must not contain raw control characters.
- Alignment, text size, separator pattern, and cut mode must use supported values.
- Column lists must be non-empty, and column percentages must be positive numbers.
- QR values must be non-empty and QR sizes must be between 1 and 16.
- Feed values must be integers between 0 and 255.
- Sections must be strings or `None`.

This validation is printer-independent. Printer-specific fitting happens later in the layout engine.

## Printer Profiles

`src/printer/printer_profile.py` provides the classes that describe a physical printer:

- `PrinterIdentification`: manufacturer and model
- `PrinterMedia`: paper width, printable dots, and character columns
- `PrinterCapabilities`: native QR, barcode, raster, and cutting support
- `PrinterEncoding`: code pages and optional raster fallback
- `PrinterLayout`: left and right margins
- `PrinterProfile`: complete profile containing all of the sections above

Profiles can be created in Python or loaded from JSON with `load_printer_profile()`. They are deeply validated during construction and loading.

```python
from printer.printer_profile import load_printer_profile

profile = load_printer_profile("src/printer/epson_tm_t20iv.json")
```

The example file defines an Epson TM-T20IV profile with 80 mm paper, 512 printable dots, 42 character columns, native QR support, raster support, and cutting support.

### Code Pages

Each `CodePage` has a human-readable name, Python codec name, and ESC/POS page ID. Profile code pages are checked to ensure they are valid, unique, and single-byte character encodings.

If no code pages are configured, `TextEncoder` accepts only ASCII. If code pages are configured, text remains on the current page while characters fit and switches to a compatible profile page when necessary.

## Layout Engine

`LayoutEngine.layout()` validates the receipt and converts it into a `RenderPlan`.

### Width Calculation

The layout engine combines:

- Printer character columns
- Printable dot width
- Left and right margins

It calculates the usable character width by converting dot margins into character columns and subtracting them from the printer's width.

### Text Layout

Text is wrapped at word boundaries. A newline creates a separate paragraph or line. Long words are split into width-sized chunks. `large` and `double` text styles reduce the effective text width because they occupy more physical columns.

### Column Layout

Column percentages are normalized when they do not add up to exactly 100. The engine calculates exact widths, applies integer flooring, and distributes leftover character columns to the columns with the largest fractional remainders. Columns with zero allocated width are rejected.

Each column is wrapped independently. The engine determines the highest wrapped line count and emits aligned text for each physical line.

### Other Layout Operations

- Separators expand to the full usable printable width.
- QR codes are centered and remain implementation-neutral until capability resolution.
- Feed operations preserve the requested line count.
- Cut operations preserve full or partial cut mode.

## Render Plan

The classes in `src/compiler/render_plan.py` form the printer-aware intermediate representation:

- `TextOperation`
- `ColumnsOperation`
- `SeparatorOperation`
- `QROperation`
- `FeedOperation`
- `CutOperation`
- `RenderPlan`

A render plan belongs to a `printer_id`, contains an ordered operations list, and may include warnings. It sits between layout and printer command generation so those phases can be tested separately.

## Capability Resolution

`CapabilityResolver` validates hardware-dependent operations against both the printer profile and the backend's supported capabilities.

For QR codes, native implementation is preferred first, followed by raster fallback. The resolver uses:

- `printer_profile.capabilities.qr_code` for native QR support
- `printer_profile.capabilities.raster` for raster support
- `ESCPosBackend.supported_qr_methods` for backend support

A QR operation is left as `native` or `raster` only after both sides agree. Raster fallback adds a warning to the render plan. If no implementation is available, it raises `CapabilityError`.

Cut operations require `printer_profile.capabilities.cutting`. Unsupported cutting raises `CapabilityError` before ESC/POS bytes are generated.

## Text Encoding

`TextEncoder` receives the printer encoding configuration and converts text into `EncodedRun` objects.

An `EncodedRun` contains:

- A `CodePage`, or `None` for ASCII-only profiles
- The encoded `bytes` for that character range

The encoder:

1. Keeps the printer on its current code page when possible.
2. Searches profile code pages in configured order for an unsupported character.
3. Produces separate runs whenever the required code page changes.
4. Raises `TextEncodingError` when no code page can represent the character.

QR data is handled separately and is always encoded as UTF-8 because it is machine-readable payload, not regular printable text.

## ESC/POS Backend

`ESCPosBackend` converts a resolved render plan into ESC/POS bytes. It is stateless: every `render()` call creates a fresh `_RenderJob`, so simultaneous receipts do not share buffer or code-page state.

The backend emits commands for:

- Printer initialization
- Code-page selection
- Alignment, bold, and text size
- Column formatting and line feeds
- Separators
- Native QR model 2 commands
- Paper feeding
- Full or partial cutting

The backend currently advertises only native QR support. Raster QR generation is not implemented.

Unresolved QR operations, unsupported operations, invalid command values, and backend encoding errors raise `ESCPosError`, which inherits from `BackendError`.

## Transport and Printing

`ReceiptPrinter` is the public orchestration class. `print_receipt()` performs the complete pipeline:

1. Layout the receipt.
2. Confirm the render plan printer ID matches the profile.
3. Resolve capabilities.
4. Render ESC/POS bytes.
5. Send bytes through the transport.
6. Return a `PrintResult`.

`PrintResult` reports the printer ID, number of bytes submitted, and capability warnings. A successful result means data was accepted by the transport, not that the physical printer necessarily finished printing it.

`NetworkTransport` sends bytes using a TCP socket. It validates host, port, timeout, and transport type; opens a connection; calls `sendall()`; and converts socket failures into `TransportError`.

`TransportConfig` currently describes USB, serial, and network settings. The active transport implementation is network-based. USB and serial profiles can be declared, but sending them requires an appropriate transport implementation.

## Error Handling

`src/errors.py` provides a receipt-engine error hierarchy:

- `ReceiptEngineError`: base class
- `InvalidReceiptError`
- `InvalidProfileError`
- `LayoutError`
- `CapabilityError`
- `BackendError`
- `TextEncodingError`
- `TransportError`
- `PrinterMismatchError`

Callers can catch `ReceiptEngineError` for all engine failures or catch a specific subclass for targeted handling.

## Basic Usage

```python
from ir.receipt import (
    ReceiptIR,
    TextNode,
    TextStyle,
    ColumnsNode,
    ReceiptColumn,
    CutNode,
)
from printer.printer_profile import load_printer_profile
from printer.receipt_printer import ReceiptPrinter
from printer.transport import NetworkTransport
from printer.transport_config import TransportConfig

profile = load_printer_profile("src/printer/epson_tm_t20iv.json")
transport = NetworkTransport(
    TransportConfig(
        transport_type="network",
        host="192.0.2.10",
        port=9100,
        timeout=5,
    )
)

receipt = ReceiptIR(
    nodes=[
        TextNode(
            value="JALDIMAI FOODS",
            style=TextStyle(alignment="center", bold=True, size="large"),
        ),
        ColumnsNode(
            columns=[
                ReceiptColumn("Chicken Momo", 70),
                ReceiptColumn("Rs. 350", 30, "right"),
            ]
        ),
        CutNode(mode="full"),
    ]
)

result = ReceiptPrinter(profile, transport).print_receipt(receipt)

print(result.printer_id)
print(result.bytes_sent)
print(result.warnings)
```

## Testing

The unit tests cover receipt validation, printer-profile validation, text encoding, layout wrapping and columns, capability resolution, ESC/POS commands, backend state isolation, transport behavior, and the complete orchestrator.

Run the suite from the repository root:

```powershell
$env:PYTHONPATH="src"
.\venv\Scripts\python.exe -m unittest discover -s src/tests -t src -v
```

From the project root, the suite can also be started with:

```powershell
python -m unittest discover -s src/tests -t src -v
```

## Demonstrations

The `src/demo/` directory contains small standalone examples:

- `demo_layout_engine.py` demonstrates text, columns, QR, feed, and cut layout.
- `demo_render_plan.py` constructs and inspects a render plan directly.
- `demo_printer_profile.py` constructs profile objects and transport configuration.

`src/tests/capture.py` builds a complete sample receipt and writes generated ESC/POS bytes to `receipt.bin` using a recording transport.
