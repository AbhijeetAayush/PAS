import unittest

from domain.models import AppError
from services.age import AGE_SQL, ROLL_YEAR, age_bands, age_labels, age_where, current_age


class CurrentAgeTest(unittest.TestCase):
    def test_2021_age_moves_forward_with_the_year(self) -> None:
        self.assertEqual(ROLL_YEAR, 2021)
        self.assertEqual(current_age(29, 2026), 34)
        self.assertEqual(current_age(29, 2027), 35)
        self.assertEqual(current_age(18, 2026), 23)

    def test_sql_uses_the_date_in_india(self) -> None:
        self.assertIn("current_date('Asia/Kolkata')", AGE_SQL)
        self.assertIn("2021", AGE_SQL)
        self.assertIn("safe_cast(v.age as int64)", AGE_SQL)

    def test_bands_start_at_18_then_step_by_five(self) -> None:
        labels = age_labels()
        self.assertEqual(labels[:4], ["18-25", "25-30", "30-35", "35-40"])
        self.assertEqual(labels[-1], "95+")
        self.assertEqual([band[0] for band in age_bands()], labels)

    def test_filter_is_inclusive_and_the_open_band_has_no_top(self) -> None:
        clause, params = age_where("25-30")
        self.assertIn("between @age_low and @age_high", clause)
        self.assertEqual([item["parameterValue"]["value"] for item in params], ["25", "30"])
        older, older_params = age_where("95+")
        self.assertIn(">= @age_low", older)
        self.assertEqual(older_params[0]["parameterValue"]["value"], "95")
        with self.assertRaises(AppError):
            age_where("10-15")
