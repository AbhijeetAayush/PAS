import unittest

from adapters.page_reader import _as_page, _vertex_url
from adapters.qstash import QStash, flow_control, lane_for
from adapters.sec_client import parse_district_html, parse_nagar_page
from domain.cards import clean_page, clean_voter
from domain.models import Body
from services.ingest import IngestService


class CardsTest(unittest.TestCase):
    def test_keeps_hindi_and_english_columns_shape(self) -> None:
        card = clean_voter(
            {
                "serial": "1",
                "epic": "ikb0926568",
                "name": "सलीम कुमार",
                "relation": "पिता का नाम",
                "relation_name": "गिरधारी सिंह",
                "house_no": "48",
                "age": "29",
                "gender": "पुरुष",
                "assembly_ref": "157/124/317",
            }
        )
        self.assertIsNotNone(card)
        assert card is not None
        self.assertEqual(card.name, "सलीम कुमार")
        self.assertEqual(card.relation, "पिता")
        self.assertEqual(card.gender, "पुरुष")
        self.assertEqual(card.epic, "IKB0926568")

    def test_drops_duplicate_serials(self) -> None:
        page = clean_page(
            {
                "page_kind": "voters",
                "voters": [
                    {"serial": 1, "name": "राम"},
                    {"serial": 1, "name": "श्याम"},
                ],
            }
        )
        self.assertEqual(len(page["voters"]), 1)
        self.assertEqual(page["voters"][0].name, "राम")


class SourceParseTest(unittest.TestCase):
    def test_district_options(self) -> None:
        page = """
        <select id="ddlDistrict">
          <option value="">-- Select District --</option>
          <option value="22">&#x92D;&#x93E;&#x917;&#x932;&#x92A;&#x941;&#x930;</option>
        </select>
        <select id="ddlBlock"></select>
        """
        districts = parse_district_html(page)
        self.assertEqual(districts[0].id, "22")
        self.assertEqual(districts[0].name, "भागलपुर")

    def test_nagar_rows(self) -> None:
        page = """
        <table><tbody>
          <tr>
            <td>1</td>
            <td>Akbarnagar</td>
            <td><a href="https://cdn.s3waas.gov.in/a/2022080197.pdf">F_Ward_01__WI</a></td>
          </tr>
          <tr>
            <td>12</td>
            <td>Naugachhia</td>
            <td><a href="https://cdn.s3waas.gov.in/a/2022080137.pdf">F_Ward_01__WI</a></td>
          </tr>
        </tbody></table>
        """
        links = parse_nagar_page(page, "https://bhagalpur.nic.in/roll/", "Akbarnagar")
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0].ward_no, 1)
        self.assertTrue(links[0].source_url.endswith("2022080197.pdf"))


class EndpointTest(unittest.TestCase):
    def test_gemini_35_uses_the_global_host(self) -> None:
        url = _vertex_url("gemini-3.5-flash", "pas-br", "global")
        self.assertTrue(url.startswith("https://aiplatform.googleapis.com/v1/projects/pas-br/locations/global/"))
        self.assertIn("models/gemini-3.5-flash:generateContent", url)

    def test_page_object_wrapped_in_a_list_is_accepted(self) -> None:
        page = _as_page([{"page_kind": "voters", "ward_no": 1, "voters": [{"serial": 1, "name": "राम"}]}])
        self.assertEqual(page["page_kind"], "voters")
        self.assertEqual(page["voters"][0]["name"], "राम")

    def test_qstash_defaults_to_the_us_region(self) -> None:
        queue = QStash("token", "current", "next")
        self.assertEqual(queue.base_url, "https://qstash-us-east-1.upstash.io")

    def test_page_reads_are_capped_and_enqueue_is_separate(self) -> None:
        self.assertEqual(lane_for("/internal/qstash/page"), "read")
        self.assertEqual(lane_for("/internal/qstash/file"), "prepare")
        self.assertEqual(flow_control("read"), ("voter-roll", "parallelism=3, rate=10, period=1m"))
        self.assertEqual(flow_control("prepare"), ("voter-roll-prepare", "parallelism=4"))


class RetryTest(unittest.TestCase):
    def test_vertex_rate_limit_is_retried(self) -> None:
        from services.pipeline import _retryable

        self.assertTrue(_retryable("Vertex read failed: 429 Resource exhausted"))
        self.assertFalse(_retryable("Vertex returned an unexpected page shape"))


class IngestOnceTest(unittest.TestCase):
    def test_completed_body_is_not_queued_again(self) -> None:
        catalog = _Catalog()
        jobs = _Jobs(done="job-1")
        queue = _Queue()
        service = IngestService(catalog, jobs, queue, "https://worker.example")
        result = service.start("user", "22", "15", "nagar_panchayat", "akbarnagar")
        self.assertEqual(result.status, "already_downloaded")
        self.assertEqual(result.job_id, "job-1")
        self.assertEqual(queue.messages, [])
        self.assertEqual(jobs.created, [])

    def test_new_body_publishes_one_discover_message(self) -> None:
        catalog = _Catalog()
        jobs = _Jobs(done=None)
        queue = _Queue()
        service = IngestService(catalog, jobs, queue, "https://worker.example/")
        result = service.start("user", "22", "15", "nagar_panchayat", "akbarnagar")
        self.assertEqual(result.status, "queued")
        self.assertEqual(len(queue.messages), 1)
        url, payload, lane = queue.messages[0]
        self.assertEqual(lane, "prepare")
        self.assertEqual(url, "https://worker.example/internal/qstash/discover")
        self.assertEqual(payload["callback_base"], "https://worker.example")
        self.assertEqual(jobs.created[0]["body_name"], "नगर पंचायत, अकबरनगर")


class _Catalog:
    def get_body(self, district_id: str, prakhand_id: str, body_type: str, body_id: str) -> Body:
        return Body(
            publication="2022-final-phase-2",
            district_id=district_id,
            district_name="भागलपुर",
            prakhand_id=prakhand_id,
            prakhand_name="सुलतानगंज",
            body_type=body_type,
            body_id=body_id,
            body_name="नगर पंचायत, अकबरनगर",
            match_name="Akbarnagar",
        )


class _Jobs:
    def __init__(self, done: str | None) -> None:
        self.done = done
        self.created: list[dict] = []

    def downloaded_job(self, body_key: str) -> str | None:
        return self.done

    def open_job(self, body_key: str) -> str | None:
        return None

    def create_job(self, job: dict) -> None:
        self.created.append(job)


class _Queue:
    def __init__(self) -> None:
        self.messages: list[tuple[str, dict]] = []

    def publish(self, url: str, payload: dict, lane: str = "prepare") -> None:
        self.messages.append((url, payload, lane))


if __name__ == "__main__":
    unittest.main()
