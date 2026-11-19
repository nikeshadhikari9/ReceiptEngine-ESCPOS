"""
Shared error types for the receipt engine.

Every error the engine raises on purpose inherits from ReceiptEngineError,
so an application can catch everything with one line:

    try:
        printer.print_receipt(receipt)
    except ReceiptEngineError as error:
        ...

or catch one specific kind (for example, only InvalidReceiptError).

Errors that belong to one specific printer language (such as ESCPosError)
live next to that backend instead of here, so this file stays free of
ESC/POS knowledge.
"""


class ReceiptEngineError(Exception):
    """Base class for all receipt engine errors."""


class InvalidReceiptError(ReceiptEngineError):
    """The receipt data given by the application is not valid."""


class InvalidProfileError(ReceiptEngineError):
    """A printer profile is not valid."""


class LayoutError(ReceiptEngineError):
    """Receipt content cannot be laid out on this printer."""


class CapabilityError(ReceiptEngineError):
    """A required printer capability is unavailable."""


class BackendError(ReceiptEngineError):
    """A backend could not turn the render plan into printer commands."""


class TextEncodingError(BackendError):
    """Text contains a character the printer cannot print."""


class TransportError(ReceiptEngineError):
    """Communication with the printer failed."""

class PrinterMismatchError(ReceiptEngineError):
    """The render plan targets a different printer than the configured one."""