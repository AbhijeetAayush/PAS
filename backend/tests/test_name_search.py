import unittest

from services.name_search import spellings, voter_search


class SpellingTest(unittest.TestCase):
    def assert_has(self, typed: str, hindi: str) -> None:
        forms = spellings(typed)
        self.assertIn(hindi, forms, msg=f"{typed} -> {forms}")

    def test_prefix_and_full_names(self) -> None:
        self.assert_has("ABHI", "अभि")
        self.assert_has("abhi", "अभि")
        self.assert_has("abhijeet", "अभिजीत")
        self.assert_has("abhijit", "अभिजित")
        self.assert_has("abhishek", "अभिषेक")
        self.assert_has("singh", "सिंह")
        self.assert_has("ram", "राम")
        self.assert_has("prasad", "प्रसाद")
        self.assert_has("kumar", "कुमार")
        self.assert_has("kumari", "कुमारी")
        self.assert_has("yadav", "यादव")
        self.assert_has("devi", "देवी")
        self.assert_has("mohan", "मोहन")
        self.assert_has("shyam", "श्याम")
        self.assert_has("anil", "अनिल")
        self.assert_has("shankar", "शंकर")
        self.assert_has("lakshman", "लक्ष्मण")
        self.assert_has("laxman", "लक्ष्मण")
        self.assert_has("sharma", "शर्मा")
        self.assert_has("paswan", "पासवान")

    def test_hindi_typing_is_not_transliterated(self) -> None:
        clause, params = voter_search("अभि")
        self.assertIn("lower(name) like @q", clause)
        self.assertEqual(params[0]["parameterValue"]["value"], "%अभि%")
        self.assertEqual(len(params), 2)
        self.assertIn("name like @h0", clause)

    def test_english_search_adds_hindi_likes(self) -> None:
        clause, params = voter_search("abhi")
        values = [item["parameterValue"]["value"] for item in params]
        self.assertIn("%abhi%", values)
        self.assertIn("%अभि%", values)
        self.assertIn("name like @h0", clause)
        self.assertIn("epic", clause)

    def test_two_words_must_both_match(self) -> None:
        clause, _params = voter_search("ram singh")
        self.assertIn(" and ", clause)
        self.assertIn("%राम%", [item["parameterValue"]["value"] for item in voter_search("ram singh")[1]])
        self.assertIn("%सिंह%", [item["parameterValue"]["value"] for item in voter_search("ram singh")[1]])
