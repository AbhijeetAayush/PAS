import unittest

from domain.models import AppError
from services.voter_marks import CASTES, PARTIES, VOTER_KEY_SQL, clean_mark, extra_where, order_clause

_KEY = "a" * 64

_EXPECTED = {
    "Yadav": "BC-II",
    "Dusadh / Paswan": "SC",
    "Chamar / Ravidas / Mochi": "SC",
    "Kushwaha / Koeri": "BC-II",
    "Sheikh": "GEN",
    "Brahmin": "GEN",
    "Momin / Ansari": "EBC",
    "Rajput": "GEN",
    "Musahar": "SC",
    "Kurmi": "BC-II",
    "Bhumihar": "GEN",
    "Teli": "BC-II",
    "Mallah": "EBC",
    "Bania / Vaishya": "BC-II",
    "Kanu": "EBC",
    "Dhanuk": "EBC",
    "Noniya": "EBC",
    "Surjapuri Muslim": "BC-II",
    "Pan / Sawasi / Panr": "SC",
    "Chandravanshi / Kahar": "EBC",
    "Nai": "EBC",
    "Barhai": "EBC",
    "Dhuniya (Muslim)": "EBC",
    "Prajapati / Kumhar": "EBC",
    "Raine / Kunjra": "EBC",
    "Pasi": "SC",
    "Bind": "EBC",
    "Kulhaiya": "BC-II",
    "Pathan / Khan": "GEN",
    "Dhobi / Rajak": "SC",
    "Kayastha": "GEN",
    "Kamar / Lohar / Karmakar": "EBC",
    "Haluai": "EBC",
    "Kewat": "EBC",
    "Gangota": "EBC",
    "Beldar": "EBC",
    "Goswami / Sanyasi / Gosain": "BC-II",
}


class CasteCategoryTest(unittest.TestCase):
    def test_every_caste_has_the_given_category(self) -> None:
        self.assertEqual(dict(CASTES), _EXPECTED)

    def test_caste_fills_category_and_a_plain_job_drops_farming(self) -> None:
        mark = clean_mark(
            {
                "voter_key": _KEY,
                "religion": "Hindu",
                "caste": "Yadav",
                "category": "SC",
                "occupation": "Teacher",
                "farmer_kinds": ["Crops"],
                "farmer_other": "maize",
            }
        )
        self.assertEqual(mark["category"], "BC-II")
        self.assertEqual(mark["farmer_kinds"], "")
        self.assertEqual(mark["farmer_other"], "")

    def test_farmer_keeps_several_kinds_and_the_other_note(self) -> None:
        mark = clean_mark(
            {
                "voter_key": _KEY,
                "occupation": "Farmer",
                "farmer_kinds": ["Poultry", "Other", "Crops"],
                "farmer_other": "  beekeeping ",
            }
        )
        self.assertEqual(mark["farmer_kinds"], "|Crops|Poultry|Other|")
        self.assertEqual(mark["farmer_other"], "beekeeping")
        self.assertEqual(mark["category"], "")

    def test_ideology_fills_the_party_leader(self) -> None:
        mark = clean_mark(
            {
                "voter_key": _KEY,
                "ideology": "Bharatiya Janata Party (BJP)",
                "leader": "Someone else",
            }
        )
        self.assertEqual(mark["leader"], "Narendra Modi")
        self.assertEqual(dict(PARTIES)["Jan Suraaj Party (JSP)"], "Prashant Kishor")
        self.assertEqual(dict(PARTIES)["Indian Inclusive Party (IIP)"], "Indrajeet Prasad Gupta")
        self.assertEqual(len(PARTIES), 15)
        self.assertEqual(order_clause("leader", "asc"), "m.leader asc nulls last, v.serial")
        cleared = clean_mark({"voter_key": _KEY, "ideology": ""})
        self.assertEqual(cleared["leader"], "")
        with self.assertRaises(AppError):
            clean_mark({"voter_key": _KEY, "ideology": "Not a party"})

    def test_shop_other_is_kept_only_when_other_is_chosen(self) -> None:
        mark = clean_mark(
            {
                "voter_key": _KEY,
                "occupation": "Shopkeeper",
                "shop_kinds": ["Kirana"],
                "shop_other": "toys",
            }
        )
        self.assertEqual(mark["shop_kinds"], "|Kirana|")
        self.assertEqual(mark["shop_other"], "")

    def test_unknown_caste_is_rejected(self) -> None:
        with self.assertRaises(AppError):
            clean_mark({"voter_key": _KEY, "caste": "Not a caste"})


class VoterQueryTest(unittest.TestCase):
    def test_filters_use_parameters(self) -> None:
        sql, params = extra_where({"religion": "Muslim", "farmer": "Crops", "name": "abhi"})
        self.assertIn("m.religion = @religion", sql)
        self.assertIn("m.farmer_kinds", sql)
        self.assertIn("v.name like @c0h0", sql)
        values = [item["parameterValue"]["value"] for item in params]
        self.assertIn("Muslim", values)
        self.assertIn("%|Crops|%", values)
        self.assertIn("%अभि%", values)

    def test_sort_is_limited_to_known_columns(self) -> None:
        self.assertEqual(order_clause("caste", "desc"), "m.caste desc nulls last, v.serial")
        self.assertEqual(order_clause("farmer_other", "asc"), "m.farmer_other asc nulls last, v.serial")
        self.assertEqual(order_clause("", "desc"), "v.ward_no, v.part_no, v.serial")
        with self.assertRaises(AppError):
            order_clause("name; drop table voters", "asc")

    def test_voter_key_uses_the_same_parts_as_the_roll_insert(self) -> None:
        self.assertIn("v.publication", VOTER_KEY_SQL)
        self.assertIn("v.source_url", VOTER_KEY_SQL)
        self.assertIn("v.page_no", VOTER_KEY_SQL)
        self.assertIn("v.serial", VOTER_KEY_SQL)
        self.assertEqual(VOTER_KEY_SQL.count("'|'"), 3)
