import unittest

from ir.receipt import ReceiptIR, ReceiptColumn, ColumnsNode
from printer.printer_profile import (
    PrinterProfile,
    PrinterIdentification,
    PrinterMedia,
    PrinterCapabilities,
    PrinterEncoding,
    PrinterLayout,
)
from compiler.layout_engine import LayoutEngine, LayoutError
from errors import InvalidReceiptError
from compiler.capability_resolver import CapabilityResolver
from compiler.escpos_backend import ESCPosBackend


def make_profile(character_columns=48, printable_dots=576):
    """Build a printer profile. Defaults describe an 80 mm printer."""
    return PrinterProfile(
        printer_id="printer_001",
        identification=PrinterIdentification(
            manufacturer="EPSON", model="TM-T20IV"
        ),
        media=PrinterMedia(
            paper_width_mm=80,
            printable_width_dots=printable_dots,
            character_columns=character_columns,
        ),
        capabilities=PrinterCapabilities(
            qr_code=True, barcode=True, raster=True, cutting=True
        ),
        encoding=PrinterEncoding(),
        supported_transports=["network"],
        layout=PrinterLayout(left_margin_dots=0, right_margin_dots=0),
    )


def make_receipt(*columns):
    """Build a receipt containing one row of columns."""
    return ReceiptIR(nodes=[ColumnsNode(columns=list(columns))])


def widths_of_first_line(plan):
    """Return the character width of each column on the first printed line."""
    first_line = plan.operations[0].lines[0]
    return [column.width for column in first_line.columns]


class TestColumnWidths(unittest.TestCase):

    def setUp(self):
        self.engine = LayoutEngine()

    def test_70_30_split_on_80mm_printer(self):
        receipt = make_receipt(
            ReceiptColumn("Chicken Momo", width_percent=70),
            ReceiptColumn("Rs. 350", width_percent=30, alignment="right"),
        )
        plan = self.engine.layout(receipt, make_profile(48, 576))

        # 48 * 0.70 = 33.6 and 48 * 0.30 = 14.4. The leftover character
        # goes to the column with the larger fraction, so 34 + 14.
        self.assertEqual(widths_of_first_line(plan), [34, 14])

    def test_same_receipt_on_58mm_printer_gives_different_layout(self):
        receipt = make_receipt(
            ReceiptColumn("Chicken Momo", width_percent=70),
            ReceiptColumn("Rs. 350", width_percent=30, alignment="right"),
        )
        plan = self.engine.layout(receipt, make_profile(32, 384))

        self.assertEqual(widths_of_first_line(plan), [22, 10])

    def test_widths_always_add_up_to_the_line_width(self):
        splits = [(70, 30), (50, 50), (33, 33, 34), (10, 20, 30, 40)]

        for percents in splits:
            with self.subTest(percents=percents):
                columns = [
                    ReceiptColumn("x", width_percent=p) for p in percents
                ]
                plan = self.engine.layout(
                    make_receipt(*columns), make_profile(48, 576)
                )
                self.assertEqual(sum(widths_of_first_line(plan)), 48)

    def test_percentages_not_adding_to_100_are_scaled(self):
        receipt = make_receipt(
            ReceiptColumn("a", width_percent=1),
            ReceiptColumn("b", width_percent=1),
        )
        plan = self.engine.layout(receipt, make_profile(48, 576))

        self.assertEqual(widths_of_first_line(plan), [24, 24])

    def test_widths_are_whole_numbers(self):
        receipt = make_receipt(
            ReceiptColumn("a", width_percent=70),
            ReceiptColumn("b", width_percent=30),
        )
        plan = self.engine.layout(receipt, make_profile())

        for width in widths_of_first_line(plan):
            self.assertIsInstance(width, int)


class TestColumnWrapping(unittest.TestCase):

    def test_long_text_wraps_onto_extra_lines(self):
        receipt = make_receipt(
            ReceiptColumn("Chicken Momo Special Combo", width_percent=20),
            ReceiptColumn("Rs. 350", width_percent=80, alignment="right"),
        )
        plan = LayoutEngine().layout(receipt, make_profile(48, 576))
        lines = plan.operations[0].lines

        # The narrow first column cannot fit the name on one line.
        self.assertGreater(len(lines), 1)

        # The price is short, so on the extra lines its cell is empty.
        self.assertEqual(lines[0].columns[1].text, "Rs. 350")
        self.assertEqual(lines[1].columns[1].text, "")

    def test_no_text_is_wider_than_its_column(self):
        receipt = make_receipt(
            ReceiptColumn("Extraordinarily-long-word-here", width_percent=20),
            ReceiptColumn("ok", width_percent=80),
        )
        plan = LayoutEngine().layout(receipt, make_profile(48, 576))

        for line in plan.operations[0].lines:
            for column in line.columns:
                self.assertLessEqual(len(column.text), column.width)


class TestColumnErrors(unittest.TestCase):

    def test_no_columns_is_rejected(self):
        with self.assertRaises(InvalidReceiptError):
            LayoutEngine().layout(make_receipt(), make_profile())

    def test_zero_percent_is_rejected(self):
        receipt = make_receipt(
            ReceiptColumn("a", width_percent=0),
            ReceiptColumn("b", width_percent=100),
        )
        with self.assertRaises(InvalidReceiptError):
            LayoutEngine().layout(receipt, make_profile())

    def test_negative_percent_is_rejected(self):
        receipt = make_receipt(
            ReceiptColumn("a", width_percent=-10),
            ReceiptColumn("b", width_percent=110),
        )
        with self.assertRaises(InvalidReceiptError):
            LayoutEngine().layout(receipt, make_profile())

    def test_too_many_columns_for_a_tiny_printer_is_rejected(self):
        receipt = make_receipt(
            ReceiptColumn("a", width_percent=1),
            ReceiptColumn("b", width_percent=1),
            ReceiptColumn("c", width_percent=1),
        )
        # Only 2 character cells exist, so 3 columns cannot all fit.
        with self.assertRaises(LayoutError):
            LayoutEngine().layout(receipt, make_profile(2, 16))


class TestColumnsThroughWholePipeline(unittest.TestCase):
    """Receipt -> layout -> capability check -> ESC/POS bytes."""

    def compile(self, receipt, profile):
        plan = LayoutEngine().layout(receipt, profile)
        resolved = CapabilityResolver().resolve(plan, profile)
        return ESCPosBackend().render(resolved, profile)

    def test_row_is_padded_to_exactly_the_line_width(self):
        receipt = make_receipt(
            ReceiptColumn("Chicken Momo - Special", width_percent=70),
            ReceiptColumn("Rs. 350", width_percent=30, alignment="right"),
        )
        output = self.compile(receipt, make_profile(48, 576))

        expected_row = (
            "Chicken Momo - Special".ljust(34) + "Rs. 350".rjust(14)
        ).encode("ascii")

        self.assertEqual(len(expected_row), 48)
        self.assertIn(expected_row, output)

    def test_same_receipt_prints_narrower_on_58mm(self):
        receipt = make_receipt(
            ReceiptColumn("Coke", width_percent=70),
            ReceiptColumn("Rs. 60", width_percent=30, alignment="right"),
        )
        output = self.compile(receipt, make_profile(32, 384))

        expected_row = (
            "Coke".ljust(22) + "Rs. 60".rjust(10)
        ).encode("ascii")

        self.assertEqual(len(expected_row), 32)
        self.assertIn(expected_row, output)


if __name__ == "__main__":
    unittest.main()