import unittest

from services.booths import epics_in_text, ranges_overlap, serial_span, single_booth_by_ward, wards_with_pdfs


class BoothMapTest(unittest.TestCase):
    def test_one_booth_in_a_ward_is_that_wards_number(self) -> None:
        booths = [
            {"ward_no": 1, "booth_no": "145", "pdf_url": ""},
            {"ward_no": 3, "booth_no": "03/01", "pdf_url": "https://sec.example/a.pdf"},
            {"ward_no": 3, "booth_no": "03/02", "pdf_url": "https://sec.example/b.pdf"},
        ]
        self.assertEqual(single_booth_by_ward(booths), {1: "145"})

    def test_split_wards_keep_their_roll_pdfs(self) -> None:
        booths = [
            {"ward_no": 1, "booth_no": "01/01", "pdf_url": "https://sec.example/one.pdf"},
            {"ward_no": 3, "booth_no": "03/01", "pdf_url": "https://sec.example/a.pdf"},
            {"ward_no": 3, "booth_no": "03/02", "pdf_url": "https://sec.example/b.pdf"},
        ]
        groups = wards_with_pdfs(booths)
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["ward_no"], 3)
        self.assertEqual([item["booth_no"] for item in groups[0]["booths"]], ["03/01", "03/02"])

    def test_epics_survive_broken_hindi_text(self) -> None:
        text = "लनरपरचक कप नपम :मटहममद रमलज रजप \nIKB2964732\nIKB2964732\nnot an epic"
        self.assertEqual(epics_in_text(text), {"IKB2964732"})

    def test_serial_span_is_the_contiguous_voter_numbers(self) -> None:
        text = "\n".join(["0", "1", "2", "3", "house 14"])
        self.assertEqual(serial_span(text), (1, 3))
        self.assertIsNone(serial_span("1\n2\n9"))

    def test_overlapping_serial_ranges_are_rejected(self) -> None:
        self.assertTrue(ranges_overlap([(1, 522), (500, 900)]))
        self.assertFalse(ranges_overlap([(1, 522), (523, 1044)]))
