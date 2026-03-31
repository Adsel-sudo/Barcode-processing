import unittest

from pdf_barcode_text_block_validator import (
    extract_candidate_filename,
    is_valid_filename_token,
)


class FilenameExtractionTests(unittest.TestCase):
    def test_case_1_comma_then_take_last_valid_token(self):
        text = "CuteBone Dog Swim Trunk...door Fun, Dinos DST10XL"
        self.assertEqual(extract_candidate_filename(text), "DST10XL")

    def test_case_2_comma_then_skip_phrase(self):
        text = "CuteBone One Piece Dog B...ol, Beach & Play LTDB11S"
        self.assertEqual(extract_candidate_filename(text), "LTDB11S")

    def test_case_3_comma_without_space_after_comma(self):
        text = "babygoal Baby Girl ...onths,YZX04-12-18M-B"
        self.assertEqual(extract_candidate_filename(text), "YZX04-12-18M-B")

    def test_no_comma_take_last_valid_token(self):
        text = "Product Desc for Sample SKU AB12CD34"
        self.assertEqual(extract_candidate_filename(text), "AB12CD34")

    def test_invalid_tokens_filtered(self):
        self.assertFalse(is_valid_filename_token("New"))
        self.assertFalse(is_valid_filename_token("新品"))
        self.assertFalse(is_valid_filename_token("Made in China"))
        self.assertFalse(is_valid_filename_token("X01234"))
        self.assertFalse(is_valid_filename_token("A&B1"))
        self.assertFalse(is_valid_filename_token("___"))


if __name__ == "__main__":
    unittest.main()
