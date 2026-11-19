import unittest

from errors import (
    ReceiptEngineError,
    InvalidReceiptError,
    InvalidProfileError,
    LayoutError,
    CapabilityError,
    BackendError,
    TransportError,
)
from compiler.escpos_backend import ESCPosError
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
from ir.validation import validate_receipt


def receipt_with(node):
    return ReceiptIR(nodes=[node])


class TestValidReceipts(unittest.TestCase):

    def test_complete_receipt_is_accepted(self):
        receipt = ReceiptIR(nodes=[
            TextNode(value="JALDIMAI FOODS",
                     style=TextStyle(alignment="center", bold=True,
                                     size="large")),
            SeparatorNode(pattern="dashed"),
            ColumnsNode(columns=[
                ReceiptColumn("Momo", 70),
                ReceiptColumn("Rs. 250", 30, "right"),
            ]),
            QRNode(value="https://example.com", size=6),
            FeedNode(lines=3),
            CutNode(mode="partial"),
        ])

        validate_receipt(receipt)  # must not raise

    def test_empty_receipt_is_accepted(self):
        validate_receipt(ReceiptIR())

    def test_newline_is_allowed_in_text(self):
        validate_receipt(receipt_with(TextNode(value="line1\nline2")))

    def test_float_percent_is_accepted(self):
        validate_receipt(receipt_with(ColumnsNode(columns=[
            ReceiptColumn("a", 33.3),
            ReceiptColumn("b", 66.7),
        ])))


class TestInvalidReceipts(unittest.TestCase):

    def assert_invalid(self, receipt):
        with self.assertRaises(InvalidReceiptError):
            validate_receipt(receipt)

    def test_not_a_receipt(self):
        self.assert_invalid("hello")
        self.assert_invalid(None)

    def test_nodes_not_a_list(self):
        self.assert_invalid(ReceiptIR(nodes="oops"))

    def test_unknown_node_type(self):
        self.assert_invalid(ReceiptIR(nodes=["not a node"]))

    def test_text_value_must_be_a_string(self):
        self.assert_invalid(receipt_with(TextNode(value=123)))
        self.assert_invalid(receipt_with(TextNode(value=None)))

    def test_bad_alignment(self):
        self.assert_invalid(receipt_with(
            TextNode(value="x", style=TextStyle(alignment="middle"))))

    def test_bad_size(self):
        self.assert_invalid(receipt_with(
            TextNode(value="x", style=TextStyle(size="huge"))))

    def test_bold_must_be_bool(self):
        self.assert_invalid(receipt_with(
            TextNode(value="x", style=TextStyle(bold="yes"))))

    def test_style_must_be_a_textstyle(self):
        self.assert_invalid(receipt_with(
            TextNode(value="x", style="bold")))

    def test_column_problems(self):
        self.assert_invalid(receipt_with(ColumnsNode(columns=[])))
        self.assert_invalid(receipt_with(ColumnsNode(columns=["a"])))
        self.assert_invalid(receipt_with(ColumnsNode(columns=[
            ReceiptColumn("a", 0)])))
        self.assert_invalid(receipt_with(ColumnsNode(columns=[
            ReceiptColumn("a", -5)])))
        self.assert_invalid(receipt_with(ColumnsNode(columns=[
            ReceiptColumn("a", float("nan"))])))
        self.assert_invalid(receipt_with(ColumnsNode(columns=[
            ReceiptColumn("a", "50")])))
        self.assert_invalid(receipt_with(ColumnsNode(columns=[
            ReceiptColumn(5, 50)])))
        self.assert_invalid(receipt_with(ColumnsNode(columns=[
            ReceiptColumn("a", 50, "middle")])))

    def test_bad_separator_pattern(self):
        self.assert_invalid(receipt_with(SeparatorNode(pattern="wavy")))

    def test_qr_problems(self):
        self.assert_invalid(receipt_with(QRNode(value="", size=6)))
        self.assert_invalid(receipt_with(QRNode(value="x", size=0)))
        self.assert_invalid(receipt_with(QRNode(value="x", size=2.5)))
        self.assert_invalid(receipt_with(QRNode(value=42, size=6)))

    def test_feed_problems(self):
        self.assert_invalid(receipt_with(FeedNode(lines=-1)))
        self.assert_invalid(receipt_with(FeedNode(lines=1.5)))
        self.assert_invalid(receipt_with(FeedNode(lines=True)))

    def test_bad_cut_mode(self):
        self.assert_invalid(receipt_with(CutNode(mode="half")))

    def test_error_message_names_the_bad_node(self):
        receipt = ReceiptIR(nodes=[
            TextNode(value="fine"),
            TextNode(value=123),
        ])

        with self.assertRaises(InvalidReceiptError) as context:
            validate_receipt(receipt)

        message = str(context.exception)
        self.assertIn("nodes[1]", message)
        self.assertIn("TextNode", message)


class TestControlCharacters(unittest.TestCase):
    """Customer-supplied text must not be able to send printer commands."""

    def test_escape_character_is_rejected_in_text(self):
        # ESC p is the "open cash drawer" command.
        with self.assertRaises(InvalidReceiptError):
            validate_receipt(receipt_with(TextNode(value="Bob\x1bp\x00")))

    def test_gs_character_is_rejected(self):
        with self.assertRaises(InvalidReceiptError):
            validate_receipt(receipt_with(TextNode(value="\x1dV\x00")))

    def test_tab_and_carriage_return_are_rejected(self):
        for bad in ("a\tb", "a\rb", "a\x00b", "a\x7fb"):
            with self.subTest(bad=bad):
                with self.assertRaises(InvalidReceiptError):
                    validate_receipt(receipt_with(TextNode(value=bad)))

    def test_control_character_rejected_in_column_text(self):
        with self.assertRaises(InvalidReceiptError):
            validate_receipt(receipt_with(ColumnsNode(columns=[
                ReceiptColumn("ok", 50),
                ReceiptColumn("bad\x1b@", 50),
            ])))


class TestErrorFamily(unittest.TestCase):

    def test_every_engine_error_shares_one_base(self):
        for error_class in (
            InvalidReceiptError,
            InvalidProfileError,
            LayoutError,
            CapabilityError,
            BackendError,
            TransportError,
            ESCPosError,
        ):
            with self.subTest(error=error_class.__name__):
                self.assertTrue(
                    issubclass(error_class, ReceiptEngineError)
                )

    def test_escpos_error_is_a_backend_error(self):
        self.assertTrue(issubclass(ESCPosError, BackendError))


if __name__ == "__main__":
    unittest.main()