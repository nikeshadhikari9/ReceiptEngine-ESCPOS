from dataclasses import dataclass, field
from typing import List, Literal, Union, Optional


# --------------------------------------------------
# 1. TEXT STYLE
# --------------------------------------------------

@dataclass
class RenderStyle:
    alignment: Literal["left", "center", "right"] = "left"
    bold: bool = False
    size: Literal["normal", "large", "double"] = "normal"


# --------------------------------------------------
# 2. BASE RENDER OPERATION
# --------------------------------------------------

@dataclass
class RenderOperation:
    pass


# --------------------------------------------------
# 3. TEXT OPERATION
# --------------------------------------------------

@dataclass
class TextOperation(RenderOperation):
    text: str
    style: RenderStyle = field(default_factory=RenderStyle)


# --------------------------------------------------
# 4. COLUMN LINE
# --------------------------------------------------

@dataclass
class RenderColumn:
    text: str
    width: int
    alignment: Literal["left", "center", "right"] = "left"


@dataclass
class RenderLine:
    columns: List[RenderColumn] = field(default_factory=list)


# --------------------------------------------------
# 5. COLUMNS OPERATION
# --------------------------------------------------

@dataclass
class ColumnsOperation(RenderOperation):
    lines: List[RenderLine] = field(default_factory=list)


# --------------------------------------------------
# 6. SEPARATOR OPERATION
# --------------------------------------------------

@dataclass
class SeparatorOperation(RenderOperation):
    character: str = "-"
    repeat: int = 48


# --------------------------------------------------
# 7. QR OPERATION
# --------------------------------------------------

@dataclass
class QROperation(RenderOperation):
    data: str
    method: Optional[Literal["native", "raster"]] = None
    size: int = 6
    alignment: Literal["left", "center", "right"] = "center"

# --------------------------------------------------
# 8. FEED OPERATION
# --------------------------------------------------

@dataclass
class FeedOperation(RenderOperation):
    lines: int = 1


# --------------------------------------------------
# 9. CUT OPERATION
# --------------------------------------------------

@dataclass
class CutOperation(RenderOperation):
    mode: Literal["full", "partial"] = "full"


# --------------------------------------------------
# 10. RENDER PLAN
# --------------------------------------------------

RenderOperationType = Union[
    TextOperation,
    ColumnsOperation,
    SeparatorOperation,
    QROperation,
    FeedOperation,
    CutOperation
]


@dataclass
class RenderPlan:
    printer_id: str
    operations: List[RenderOperationType] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
