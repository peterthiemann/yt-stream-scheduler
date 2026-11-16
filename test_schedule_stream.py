from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from datetime import date, datetime
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

loader = SourceFileLoader("schedule_stream", str(Path(__file__).with_name("schedule-stream")))
tool = module_from_spec(spec_from_loader(loader.name, loader))
loader.exec_module(tool)

MONDAY = datetime(2026, 11, 16, 9, tzinfo=tool.UTC)
TUESDAY = "2026-11-17T09:15:00Z"
WEDNESDAY = "2026-11-18T12:00:00Z"
CHANNEL = "UCStreamingChannel"
STREAM = "reusable-stream"
TEMPLATE = "template123"
TITLE = "Lecture 7: Type Inference"
CONFIG = {
    "expected_channel_id": CHANNEL,
    "template_id": TEMPLATE,
    "privacy_policy_version": tool.PRIVACY_POLICY_VERSION,
    "client": {"client_id": "client", "client_secret": "client-secret"},
    "refresh_token": "refresh-token",
}


def broadcast(video_id, start, *, title=TITLE, privacy="unlisted", stream=None):
    result = {
        "id": video_id,
        "snippet": {"channelId": CHANNEL, "scheduledStartTime": start, "title": title},
        "status": {"privacyStatus": privacy},
        "contentDetails": {},
    }
    if stream:
        result["contentDetails"]["boundStreamId"] = stream
    return result


class MockGoogle:
    def __init__(self):
        self.channel_id = CHANNEL
        self.next_video = 1
        self.items = []
        self.reads = []
        self.writes = []
        self.bind_error = None
        self.insert_error = None
        self.commit_on_insert_error = False
        self.template = broadcast(TEMPLATE, "2026-03-18T12:00:00Z", stream=STREAM)
        self.template["snippet"].update({
            "description": "Lecture series",
            "categoryId": "27",
            "scheduledEndTime": "2026-03-18T13:00:00Z",
        })
        self.template["status"]["selfDeclaredMadeForKids"] = False
        self.template["contentDetails"].update({"enableDvr": False, "enableAutoStart": True})
        self.stream = {
            "id": STREAM,
            "snippet": {"channelId": CHANNEL},
            "contentDetails": {"isReusable": True},
        }

    def request(self, request, operation, *, oauth=False):
        if oauth:
            params = parse_qs(request.data.decode("ascii"))
            assert params["grant_type"] == ["refresh_token"]
            assert params["refresh_token"] == [CONFIG["refresh_token"]]
            return {"access_token": "private-access-token"}

        url = urlsplit(request.full_url)
        query = {key: values[0] for key, values in parse_qs(url.query).items()}
        resource = url.path.removeprefix("/youtube/v3/")
        if request.method == "GET":
            self.reads.append((resource, query))
            if resource == "channels":
                assert query["mine"] == "true"
                return {"items": [{"id": self.channel_id, "snippet": {"title": "Lecture channel"}}]}
            if resource == "liveStreams":
                assert query["id"] == self.stream["id"]
                assert "cdn" not in query["part"]
                return {"items": [deepcopy(self.stream)]}
            if "id" in query:
                matches = [item for item in self.items if item["id"] == query["id"]]
                if not matches and self.template and query["id"] == self.template["id"]:
                    matches = [self.template]
                return {"items": deepcopy(matches)}

            assert query["broadcastStatus"] == "upcoming"
            # Return a single broadcast per page, including unbound and Studio-created events.
            start = int(query.get("pageToken", "0"))
            page = {"items": deepcopy(self.items[start:start + 1])}
            if start + 1 < len(self.items):
                page["nextPageToken"] = str(start + 1)
            return page

        self.writes.append((resource, query, request.data))
        if resource == "liveBroadcasts":
            body = json.loads(request.data)
            video_id = f"video{self.next_video:06d}"
            self.next_video += 1
            item = {**deepcopy(body), "id": video_id}
            item["snippet"]["channelId"] = CHANNEL
            if self.insert_error is None or self.commit_on_insert_error:
                self.items.append(item)
            if self.insert_error:
                raise self.insert_error
            return deepcopy(item)

        assert resource == "liveBroadcasts/bind"
        if self.bind_error:
            raise self.bind_error
        for item in self.items:
            if item["id"] == query["id"]:
                item.setdefault("contentDetails", {})["boundStreamId"] = query["streamId"]
                return deepcopy(item)
        raise AssertionError("Attempted to bind an unknown broadcast")


class ScheduleTests(unittest.TestCase):
    def setUp(self):
        self.google = MockGoogle()
        self.workspace = self.enterContext(tempfile.TemporaryDirectory())
        self.config_dir = Path(self.workspace) / "config"
        self.config_dir.mkdir()
        self.enterContext(patch.object(tool, "CONFIG_DIR", self.config_dir))
        tool.save_config(CONFIG)
        self.enterContext(patch.object(tool, "request_json", self.google.request))

    def run_cli(self, *args, now=MONDAY):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err), patch.object(tool, "datetime", wraps=datetime) as clock:
            clock.now.return_value = now
            status = tool.main(list(args))
        return status, out.getvalue(), err.getvalue()

    def test_two_monday_runs_and_both_slots_occupied(self):
        for video_id, expected in (("video000001", TUESDAY), ("video000002", WEDNESDAY),
                                   ("video000003", "2026-11-24T09:15:00Z")):
            status, out, err = self.run_cli(TITLE, "-v")
            self.assertEqual(status, 0, err)
            self.assertEqual(out, f"https://www.youtube.com/watch?v={video_id}\n")
            self.assertEqual(self.google.items[-1]["snippet"]["scheduledStartTime"], expected)
            self.assertEqual(self.google.items[-1]["status"]["privacyStatus"], "unlisted")
            self.assertEqual(tool.bound_stream(self.google.items[-1]), STREAM)
        self.assertIn("Skipped occupied slot 2026-11-17 10:15 CET", err)
        self.assertIn("Skipped occupied slot 2026-11-18 13:00 CET", err)
        self.assertIn("Authorized channel: Lecture channel", err)
        self.assertIn("Created broadcast video000003", err)
        self.assertIn("Bound the template's stream", err)
        self.assertNotIn("private-access-token", err + out)

    def test_studio_broadcasts_use_pagination_and_match_by_instant(self):
        self.google.items = [
            broadcast("studio00001", "2026-11-18T13:00:00+01:00", title="Studio 1", privacy="private"),
            broadcast("studio00002", "2026-11-17T09:15:00.000Z", title="Studio 2", privacy="public"),
        ]
        status, out, err = self.run_cli("--dry-run", "-v", TITLE)
        self.assertEqual((status, out, self.google.writes), (0, "", []))
        self.assertIn("2026-11-24 10:15 CET", err)
        self.assertIn("Would create an unlisted broadcast", err)
        self.assertTrue(any(query.get("pageToken") == "1" for _, query in self.google.reads))

    def test_spring_and_autumn_daylight_saving(self):
        cases = (
            ("2026-03-24", "2026-03-24T09:15:00Z"),
            ("2026-03-31", "2026-03-31T08:15:00Z"),
            ("2026-04-01", "2026-04-01T11:00:00Z"),
            ("2026-10-21", "2026-10-21T11:00:00Z"),
            ("2026-10-28", "2026-10-28T12:00:00Z"),
        )
        now = datetime(2026, 3, 23, tzinfo=tool.UTC)
        for day, utc in cases:
            with self.subTest(day=day):
                status, out, err = self.run_cli("--date", day, TITLE, now=now)
                self.assertEqual(status, 0, err)
                item = self.google.items[-1]
                self.assertEqual(item["snippet"]["scheduledStartTime"], utc)
                self.assertEqual(
                    tool.instant(item["snippet"]["scheduledEndTime"]) - tool.instant(utc),
                    tool.timedelta(hours=1),
                )

    def test_current_or_past_slots_do_not_qualify(self):
        now = tool.instant(TUESDAY)
        status, out, err = self.run_cli(TITLE, "--date", "2026-11-17", now=now)
        self.assertEqual((status, out, self.google.writes), (1, "", []))
        self.assertIn("future Tuesday", err)
        status, _, err = self.run_cli(TITLE, "--dry-run", now=now)
        self.assertEqual(status, 0)
        self.assertIn("2026-11-18 13:00", err)

    def test_rejects_mismatched_channel_before_listing_or_writing(self):
        self.google.channel_id = "UCOtherChannel"
        status, out, err = self.run_cli(TITLE)
        self.assertEqual((status, out, self.google.writes), (1, "", []))
        self.assertEqual([name for name, _ in self.google.reads], ["channels"])
        self.assertIn("Channel mismatch", err)
        self.assertIn(CHANNEL, err)
        self.assertIn("UCOtherChannel", err)

    def test_binding_failure_is_recoverable_by_date_and_title(self):
        self.google.bind_error = tool.ApiError("YouTube returned HTTP 503.", 503)
        status, out, err = self.run_cli(TITLE)
        self.assertEqual((status, out), (1, ""))
        self.assertIn("video000001", err)
        self.assertIn("--date 2026-11-17 and the same title", err)

        self.google.bind_error = None
        status, out, err = self.run_cli(TITLE, "--date", "2026-11-17", "-v")
        self.assertEqual(status, 0, err)
        self.assertEqual(out, "https://www.youtube.com/watch?v=video000001\n")
        self.assertIn("Reused broadcast", err)
        self.assertEqual([name for name, _, _ in self.google.writes],
                         ["liveBroadcasts", "liveBroadcasts/bind", "liveBroadcasts/bind"])
        self.run_cli(TITLE, "--date", "2026-11-17")
        self.assertEqual(len(self.google.writes), 3)

    def test_specific_date_conflicts_leave_broadcasts_untouched(self):
        for existing in (
            [broadcast("studio00001", TUESDAY, privacy="private")],
            [broadcast("studio00001", TUESDAY, stream="other-stream")],
            [broadcast("studio00001", TUESDAY, title="Other")],
            [broadcast("studio00001", TUESDAY), broadcast("studio00002", TUESDAY)],
        ):
            with self.subTest(existing=existing):
                self.google.items = existing
                status, out, err = self.run_cli(TITLE, "--date", "2026-11-17")
                self.assertEqual((status, out, self.google.writes), (1, "", []))
                self.assertIn("Conflict", err)

    def test_ambiguous_insert_recovers_same_slot_before_any_new_insert(self):
        self.google.insert_error = tool.ApiError("Connection lost.")
        self.google.commit_on_insert_error = True
        status, out, err = self.run_cli(TITLE, "-v")
        self.assertEqual(status, 0, err)
        self.assertIn("Recovered broadcast", err)
        self.assertIn("video000001", out)
        self.assertEqual([name for name, _ in self.google.reads],
                         ["channels", "liveBroadcasts", "liveStreams", "liveBroadcasts", "liveBroadcasts"])
        self.assertEqual([name for name, _, _ in self.google.writes],
                         ["liveBroadcasts", "liveBroadcasts/bind"])

    def test_ambiguous_insert_and_empty_slot_ask_for_explicit_retry(self):
        self.google.insert_error = tool.ApiError("YouTube returned HTTP 503.", 503)
        status, out, err = self.run_cli(TITLE)
        self.assertEqual((status, out), (1, ""))
        self.assertIn("--date 2026-11-17", err)
        self.assertEqual(len(self.google.writes), 1)

    def test_setup_restarts_sign_in_and_retries_missing_template_binding(self):
        credentials_path = Path(self.workspace) / "desktop.json"
        credentials_path.write_text(json.dumps({"installed": CONFIG["client"]}))
        watch = f"https://www.youtube.com/watch?v={TEMPLATE}&t=3"
        self.google.items = [
            broadcast("unbound0001", TUESDAY),
            broadcast(TEMPLATE, TUESDAY, stream=STREAM),
        ]
        self.google.items[1]["contentDetails"].update({
            "monitorStream": {"enableMonitorStream": False, "embedHtml": "read-only markup"},
            "closedCaptionsType": "closedCaptionsEmbedded",
            "enableClosedCaptions": False,
            "latencyPreference": "normal",
        })
        self.google.items[1]["snippet"]["description"] = "Template description"
        tokens = {"access_token": "private-access-token", "refresh_token": CONFIG["refresh_token"]}

        sign_in = patch.object(tool, "sign_in", return_value=tokens)
        with sign_in as auth, patch("builtins.input", side_effect=[
            "yes", "", "y", CHANNEL, "https://youtu.be/unbound0001", watch,
        ]):
            status, out, err = self.run_cli("setup", "--credentials", str(credentials_path))
        self.assertEqual((status, out), (0, ""), err)
        self.assertEqual(auth.call_count, 2)
        self.assertIn("no bound stream", err)
        self.assertIn(CHANNEL, err)
        self.assertNotIn(tokens["refresh_token"], err)
        saved_path = self.config_dir / "config.json"
        self.assertEqual(saved_path.stat().st_mode & 0o777, 0o600)
        saved = json.loads(saved_path.read_text())
        self.assertEqual(saved, CONFIG)
        _, settings = tool.YouTube("private-access-token").template(TEMPLATE, CHANNEL)
        self.assertEqual(settings["snippet"], {"description": "Template description"})
        self.assertEqual(settings["contentDetails"], {
            "monitorStream": {"enableMonitorStream": False},
            "closedCaptionsType": "closedCaptionsEmbedded",
            "latencyPreference": "normal",
        })

    def test_declining_privacy_policy_stops_setup_before_oauth(self):
        original = (self.config_dir / "config.json").read_bytes()
        with patch.object(tool, "sign_in") as auth, patch("builtins.input", return_value=""):
            status, out, err = self.run_cli("setup", "--credentials", "unused.json")
        self.assertEqual((status, out), (1, ""))
        self.assertIn(tool.PRIVACY_POLICY_URL, err)
        self.assertIn("Accept the Privacy Policy", err)
        auth.assert_not_called()
        self.assertEqual((self.config_dir / "config.json").read_bytes(), original)

    def test_legacy_metadata_is_removed_before_oauth_or_policy_acceptance(self):
        legacy = {
            "client": CONFIG["client"], "refresh_token": CONFIG["refresh_token"],
            "channel_id": CHANNEL, "stream_id": STREAM, "settings": {"snippet": {"description": "Old"}},
        }
        for args in ((TITLE, "--dry-run"), ("setup", "--credentials", "unused.json")):
            with self.subTest(args=args):
                tool.save_config(legacy)
                with patch.object(tool, "oauth_token") as refresh, patch.object(tool, "sign_in") as sign_in, \
                        patch("builtins.input", return_value="n"):
                    status, out, err = self.run_cli(*args)
                self.assertEqual((status, out), (1, ""))
                self.assertIn("Privacy Policy", err)
                refresh.assert_not_called()
                sign_in.assert_not_called()
                self.assertEqual(json.loads((self.config_dir / "config.json").read_text()), {
                    "client": CONFIG["client"], "refresh_token": CONFIG["refresh_token"],
                })

    def test_old_policy_acceptance_requires_setup_before_oauth(self):
        tool.save_config({**CONFIG, "privacy_policy_version": 0})
        with patch.object(tool, "oauth_token") as refresh:
            status, out, err = self.run_cli(TITLE)
        self.assertEqual((status, out), (1, ""))
        self.assertIn("accept the current Privacy Policy", err)
        refresh.assert_not_called()

    def test_reads_current_template_and_stream_after_more_than_30_days(self):
        status, _, err = self.run_cli(TITLE)
        self.assertEqual(status, 0, err)
        self.assertEqual(self.google.items[-1]["snippet"]["description"], "Lecture series")
        current_stream = "replacement-stream"
        self.google.template["snippet"]["description"] = "Updated description"
        self.google.template["contentDetails"]["boundStreamId"] = current_stream
        self.google.stream["id"] = current_stream

        status, _, err = self.run_cli(TITLE, now=datetime(2026, 12, 21, tzinfo=tool.UTC))
        self.assertEqual(status, 0, err)
        self.assertEqual(self.google.items[-1]["snippet"]["description"], "Updated description")
        self.assertEqual(tool.bound_stream(self.google.items[-1]), current_stream)
        self.assertEqual(json.loads((self.config_dir / "config.json").read_text()), CONFIG)

    def test_missing_template_blocks_scheduling(self):
        self.google.template = None
        status, out, err = self.run_cli(TITLE)
        self.assertEqual((status, out, self.google.writes), (1, "", []))
        self.assertIn("Run setup to choose a usable template broadcast", err)

    def test_non_reusable_template_stream_is_rejected(self):
        self.google.items = [broadcast(TEMPLATE, TUESDAY, stream=STREAM)]
        self.google.stream["contentDetails"]["isReusable"] = False
        with self.assertRaisesRegex(tool.TemplateError, "not marked reusable"):
            tool.YouTube("private-access-token").template(TEMPLATE, CHANNEL)


if __name__ == "__main__":
    unittest.main()
