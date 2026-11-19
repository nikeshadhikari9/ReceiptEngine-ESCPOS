import json
import os
import tempfile
import unittest

from errors import InvalidProfileError, ReceiptEngineError
from printer.printer_profile import (
    PrinterProfile,
    PrinterIdentification,
    PrinterMedia,
    PrinterCapabilities,
    PrinterEncoding,
    CodePage,
    PrinterLayout,
    load_printer_profile,
)

# The JSON file that ships with the project.
PROFILE_JSON = os.path.join(
    os.path.dirname(__file__), "..", "printer", "espon_tm_t20iv.json"
)


def valid_data():
    """A correct profile as plain dictionary data (like the JSON file)."""
    return {
        "printer_id": "printer_001",
        "identification": {"manufacturer": "EPSON", "model": "TM-T20IV"},
        "media": {
            "paper_width_mm": 80,
            "printable_width_dots": 576,
            "character_columns": 48,
        },
        "capabilities": {
            "qr_code": True,
            "barcode": True,
            "raster": True,
            "cutting": True,
        },
        "encoding": {
            "code_pages": [],
            "unicode_raster_fallback": False,
        },
        "supported_transports": ["network"],
        "layout": {"left_margin_dots": 0, "right_margin_dots": 0},
    }


def build_profile(**changes):
    """Build a profile in code, replacing any part with a different one."""
    parts = dict(
        printer_id="printer_001",
        identification=PrinterIdentification("EPSON", "TM-T20IV"),
        media=PrinterMedia(80, 576, 48),
        capabilities=PrinterCapabilities(True, True, True, True),
        encoding=PrinterEncoding(),
        supported_transports=["network"],
        layout=PrinterLayout(0, 0),
    )
    parts.update(changes)
    return PrinterProfile(**parts)


class TestValidProfiles(unittest.TestCase):

    def test_valid_profile_is_accepted(self):
        profile = build_profile()
        self.assertEqual(profile.media.character_columns, 48)

    def test_defaults_are_valid(self):
        PrinterCapabilities()
        PrinterEncoding()
        PrinterLayout()

    def test_58mm_profile_is_accepted(self):
        build_profile(media=PrinterMedia(58, 384, 32))

    def test_code_pages_are_accepted(self):
        encoding = PrinterEncoding(code_pages=[
            CodePage("PC437", "cp437", 0),
            CodePage("PC858", "cp858", 19),
            CodePage("WPC1252", "cp1252", 16),
        ])
        self.assertEqual(len(encoding.code_pages), 3)

    def test_code_pages_from_dictionary_become_objects(self):
        data = valid_data()
        data["encoding"]["code_pages"] = [
            {"name": "PC437", "codec": "cp437", "page_id": 0},
            {"name": "PC858", "codec": "cp858", "page_id": 19},
        ]

        profile = PrinterProfile.from_dict(data)

        self.assertEqual(
            profile.encoding.code_pages,
            [CodePage("PC437", "cp437", 0), CodePage("PC858", "cp858", 19)],
        )

    def test_from_dict_matches_a_profile_built_in_code(self):
        self.assertEqual(
            PrinterProfile.from_dict(valid_data()),
            build_profile(),
        )

    def test_real_json_file_loads(self):
        profile = load_printer_profile(PROFILE_JSON)

        self.assertIsInstance(profile.media, PrinterMedia)
        self.assertEqual(profile.identification.model, "TM-T20IV")
        self.assertEqual(profile.media.character_columns, 48)
        self.assertTrue(profile.capabilities.qr_code)
        self.assertTrue(profile.encoding.code_pages)
        self.assertIsInstance(profile.encoding.code_pages[0], CodePage)


class TestInvalidProfiles(unittest.TestCase):

    def assert_invalid(self, make_profile, expected_text=None):
        with self.assertRaises(InvalidProfileError) as context:
            make_profile()

        if expected_text is not None:
            self.assertIn(expected_text, str(context.exception))

    def test_printer_id(self):
        for bad in ("", "   ", None, 5):
            with self.subTest(bad=bad):
                self.assert_invalid(
                    lambda: build_profile(printer_id=bad), "printer_id"
                )

    def test_identification(self):
        self.assert_invalid(
            lambda: PrinterIdentification("", "TM-T20IV"), "manufacturer"
        )
        self.assert_invalid(
            lambda: PrinterIdentification("EPSON", None), "model"
        )

    def test_media_numbers(self):
        cases = [
            (lambda: PrinterMedia(0, 576, 48), "paper_width_mm"),
            (lambda: PrinterMedia(-80, 576, 48), "paper_width_mm"),
            (lambda: PrinterMedia(float("nan"), 576, 48), "paper_width_mm"),
            (lambda: PrinterMedia(80, 0, 48), "printable_width_dots"),
            (lambda: PrinterMedia(80, -1, 48), "printable_width_dots"),
            (lambda: PrinterMedia(80, 576.5, 48), "printable_width_dots"),
            (lambda: PrinterMedia(80, 576, 0), "character_columns"),
            (lambda: PrinterMedia(80, 576, True), "character_columns"),
            (lambda: PrinterMedia(80, 576, "48"), "character_columns"),
        ]

        for make, text in cases:
            with self.subTest(text=text):
                self.assert_invalid(make, text)

    def test_fewer_dots_than_columns(self):
        self.assert_invalid(lambda: PrinterMedia(80, 10, 48), "at least")

    def test_capabilities_must_be_true_or_false(self):
        self.assert_invalid(
            lambda: PrinterCapabilities(qr_code="yes"), "qr_code"
        )
        self.assert_invalid(
            lambda: PrinterCapabilities(cutting=1), "cutting"
        )

    def test_code_page_problems(self):
        cases = [
            (lambda: CodePage("", "cp437", 0), "name"),
            (lambda: CodePage("X", "not-a-codec", 0), "not a known text"),
            (lambda: CodePage("X", "utf-8", 0), "single-byte"),
            (lambda: CodePage("X", "ascii", 0), "single-byte"),
            (lambda: CodePage("X", "cp437", -1), "page_id"),
            (lambda: CodePage("X", "cp437", 256), "page_id"),
            (lambda: CodePage("X", "cp437", 1.5), "page_id"),
            (lambda: CodePage("X", "cp437", True), "page_id"),
        ]

        for make, text in cases:
            with self.subTest(text=text):
                self.assert_invalid(make, text)

    def test_encoding_code_pages_must_be_a_list_of_code_pages(self):
        self.assert_invalid(
            lambda: PrinterEncoding(code_pages="cp437"), "code_pages"
        )
        self.assert_invalid(
            lambda: PrinterEncoding(code_pages=[{"name": "x"}]),
            "code_pages[0]",
        )

    def test_duplicate_code_pages_are_rejected(self):
        self.assert_invalid(
            lambda: PrinterEncoding(code_pages=[
                CodePage("PC437", "cp437", 0),
                CodePage("PC437", "cp850", 2),
            ]),
            "duplicate names",
        )
        self.assert_invalid(
            lambda: PrinterEncoding(code_pages=[
                CodePage("A", "cp437", 0),
                CodePage("B", "cp850", 0),
            ]),
            "duplicate page_ids",
        )

    def test_unicode_raster_fallback_must_be_bool(self):
        self.assert_invalid(
            lambda: PrinterEncoding(unicode_raster_fallback="no"),
            "unicode_raster_fallback",
        )

    def test_negative_or_fractional_margins(self):
        self.assert_invalid(
            lambda: PrinterLayout(left_margin_dots=-1), "left_margin_dots"
        )
        self.assert_invalid(
            lambda: PrinterLayout(right_margin_dots=2.5), "right_margin_dots"
        )

    def test_margins_that_use_up_the_whole_width(self):
        self.assert_invalid(
            lambda: build_profile(layout=PrinterLayout(300, 276)),
            "margins",
        )

    def test_parts_must_be_real_objects_not_dictionaries(self):
        # This is the mistake that used to be silently accepted.
        self.assert_invalid(
            lambda: build_profile(media={"paper_width_mm": 80}), "media"
        )
        self.assert_invalid(
            lambda: build_profile(identification="EPSON"), "identification"
        )

    def test_supported_transports(self):
        self.assert_invalid(
            lambda: build_profile(supported_transports="network"),
            "supported_transports",
        )
        self.assert_invalid(
            lambda: build_profile(supported_transports=["network", 5]),
            "supported_transports[1]",
        )

    def test_errors_belong_to_the_engine_error_family(self):
        with self.assertRaises(ReceiptEngineError):
            PrinterMedia(0, 576, 48)


class TestFromDict(unittest.TestCase):

    def assert_invalid(self, data, expected_text):
        with self.assertRaises(InvalidProfileError) as context:
            PrinterProfile.from_dict(data)

        self.assertIn(expected_text, str(context.exception))

    def test_not_a_dictionary(self):
        self.assert_invalid([], "dictionary")
        self.assert_invalid(None, "dictionary")

    def test_missing_top_level_key(self):
        data = valid_data()
        del data["media"]
        self.assert_invalid(data, "missing required keys")

    def test_unknown_top_level_key_is_a_typo_guard(self):
        data = valid_data()
        data["capabilties"] = {}
        self.assert_invalid(data, "unknown keys")

    def test_unknown_key_inside_a_part(self):
        data = valid_data()
        data["media"]["colour"] = "white"
        self.assert_invalid(data, "colour")

    def test_missing_key_inside_a_part(self):
        data = valid_data()
        del data["media"]["character_columns"]
        self.assert_invalid(data, "media")

    def test_part_has_the_wrong_json_type(self):
        data = valid_data()
        data["media"] = [80, 576, 48]
        self.assert_invalid(data, "media")

    def test_values_are_still_validated(self):
        data = valid_data()
        data["media"]["character_columns"] = 0
        self.assert_invalid(data, "character_columns")

    def test_old_encoding_keys_are_rejected_with_a_helpful_message(self):
        data = valid_data()
        data["encoding"]["input"] = "UTF-8"
        data["encoding"]["printer_codepage"] = None
        self.assert_invalid(data, "unknown keys")

    def test_bad_code_page_inside_dictionary_names_its_position(self):
        data = valid_data()
        data["encoding"]["code_pages"] = [
            {"name": "PC437", "codec": "cp437", "page_id": 0},
            {"name": "BAD", "codec": "cp437", "page_id": 999},
        ]
        self.assert_invalid(data, "page_id")


class TestLoadFromFile(unittest.TestCase):

    def write(self, directory, text, name="profile.json"):
        path = os.path.join(directory, name)

        with open(path, "w", encoding="utf-8") as file:
            file.write(text)

        return path

    def test_missing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "nope.json")

            with self.assertRaises(InvalidProfileError):
                load_printer_profile(path)

    def test_file_that_is_not_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write(directory, "{ this is not json")

            with self.assertRaises(InvalidProfileError) as context:
                load_printer_profile(path)

            self.assertIn("not valid JSON", str(context.exception))

    def test_json_with_the_wrong_shape(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write(directory, "[1, 2, 3]")

            with self.assertRaises(InvalidProfileError):
                load_printer_profile(path)

    def test_file_saved_with_a_bom_still_loads(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "profile.json")

            with open(path, "w", encoding="utf-8-sig") as file:
                json.dump(valid_data(), file)

            self.assertEqual(
                load_printer_profile(path).printer_id, "printer_001"
            )


if __name__ == "__main__":
    unittest.main()