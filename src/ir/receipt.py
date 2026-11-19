
from dataclasses import dataclass, field
from typing import Optional, List, Literal, Union


# --------------------------------------------------
# 1. TEXT STYLE
# --------------------------------------------------

@dataclass
class TextStyle:
    alignment: Literal["left", "center", "right"] = "left"
    bold: bool = False
    size: Literal["normal", "large", "double"] = "normal"


# --------------------------------------------------
# 2. BASE RECEIPT NODE
# --------------------------------------------------

@dataclass
class ReceiptNode:
    # Free-form label the caller can attach to a node for its own
    # bookkeeping. The engine validates the type but never reads it.
    section: Optional[str] = None


# --------------------------------------------------
# 3. TEXT NODE
# --------------------------------------------------

@dataclass
class TextNode(ReceiptNode):
    value: str = ""
    style: TextStyle = field(default_factory=TextStyle)


# --------------------------------------------------
# 4. COLUMN NODE
# --------------------------------------------------

@dataclass
class ReceiptColumn:
    value: str
    # percentage of the line; values don't have to add up to 100
    width_percent: float
    alignment: Literal["left", "center", "right"] = "left"


@dataclass
class ColumnsNode(ReceiptNode):
    columns: List[ReceiptColumn] = field(default_factory=list)


# --------------------------------------------------
# 5. SEPARATOR NODE
# --------------------------------------------------

@dataclass
class SeparatorNode(ReceiptNode):
    pattern: Literal["solid", "dashed", "dotted"] = "solid"


# --------------------------------------------------
# 6. QR CODE NODE
# --------------------------------------------------

@dataclass
class QRNode(ReceiptNode):
    value: str = ""
    size: int = 6


# --------------------------------------------------
# 7. FEED NODE
# --------------------------------------------------

@dataclass
class FeedNode(ReceiptNode):
    lines: int = 1


# --------------------------------------------------
# 8. CUT NODE
# --------------------------------------------------

@dataclass
class CutNode(ReceiptNode):
    mode: Literal["full", "partial"] = "full"


# --------------------------------------------------
# 9. RECEIPT IR
# --------------------------------------------------

ReceiptNodeType = Union[
    TextNode,
    ColumnsNode,
    SeparatorNode,
    QRNode,
    FeedNode,
    CutNode
]


@dataclass
class ReceiptIR:
    version: int = 1
    metadata: dict = field(default_factory=dict)
    nodes: List[ReceiptNodeType] = field(default_factory=list)
