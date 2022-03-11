import unittest
import mock
import logging

from datetime import datetime
from cloudimized.tfcore.run import TFRun, TFRunError, parse_tf_runs, filter_non_change_runs

class TFRunTestCase(unittest.TestCase):
    def setUp(self) -> None:
        logging.disable(logging.WARNING)

    def tearDown(self) -> None:
        logging.disable(logging.NOTSET)

    def test_parse_no_data(self):
        with self.assertRaises(TFRunError):
            parse_tf_runs({}, "test_org", "test_workspace")

    def test_parse_missing_status(self):
        # Assume
        result = parse_tf_runs(tf_run_missing_status, "test_org", "test_workspace")
        self.assertEqual(result, [])

    def test_parse_non_relevat_status(self):
        result = parse_tf_runs(tf_run_status_planning, "test_org", "test_workspace")
        self.assertEqual(result, [])

    @mock.patch("cloudimized.tfcore.run.TFRun")
    def test_parse_relevant_runs(self, mock_tfrun):
        result = parse_tf_runs(tf_run_status_relevant, "test_org", "test_workspace")
        # Assert that those two TFRun objects were created and returned in list
        calls = [
            mock.call("test_msg_1",
                      "test_id_1",
                      "applied",
                      datetime.strptime("2001-01-01T00:00:01", "%Y-%m-%dT%H:%M:%S"),
                      "test_org",
                      "test_workspace"),
            mock.call("test_msg_3",
                      "test_id_3",
                      "errored",
                      datetime.strptime("2001-01-01T00:00:03", "%Y-%m-%dT%H:%M:%S"),
                      "test_org",
                      "test_workspace")
        ]
        mock_tfrun.assert_has_calls(calls)
        self.assertEqual(len(result), len(calls))

    def test_filter_non_change_runs(self):
        change_time = datetime.strptime("2001-01-01T00:02:00", "%Y-%m-%dT%H:%M:%S")
        result = filter_non_change_runs(tf_runs=tf_runs_test, change_time=change_time)
        self.assertEqual(len(result), 2)
        self.assertIs(result[0], tf_runs_test[0])
        self.assertIs(result[1], tf_runs_test[2])


if __name__ == '__main__':
    unittest.main()

tf_run_missing_status = {
    "data": [{}]
}

tf_run_status_planning = {
    "data": [{
        "attributes": {
            "status": "planing"
        }
    }]
}

tf_run_status_relevant = {
    "data": [
        {
            "attributes": {
                "status": "applied",
                "message": "test_msg_1",
                "status-timestamps": {
                    "applying-at": "2001-01-01T00:00:01+00:00"
                }
            },
            "id": "test_id_1"
        },
        {
            "attributes": {
                "status": "pending",
                "message": "test_msg_2",
                "status-timestamps": {}
            },
            "id": "test_id_2"
        },
        {
            "attributes": {
                "status": "errored",
                "message": "test_msg_3",
                "status-timestamps": {
                    "errored-at": "2001-01-01T00:00:03+00:00"
                }
            },
            "id": "test_id_3"
        },
    ]
}

tf_runs_test = [
    TFRun("test-message1",
          "test-id1",
          "applied",
          datetime.strptime("2001-01-01T00:00:01", "%Y-%m-%dT%H:%M:%S"),
          "test_org",
          "test_workspace"),
    TFRun("test-message2",
          "test-id2",
          "pending",
          datetime.strptime("2001-01-01T00:00:02", "%Y-%m-%dT%H:%M:%S"),
          "test_org",
          "test_workspace"),
    TFRun("test-message3",
          "test-id3",
          "errored",
          datetime.strptime("2001-01-01T00:00:03", "%Y-%m-%dT%H:%M:%S"),
          "test_org",
          "test_workspace"),
    TFRun("test-message4",
          "test-id4",
          "applied",
          datetime.strptime("2000-12-30T00:00:01", "%Y-%m-%dT%H:%M:%S"),
          "test_org",
          "test_workspace"),
]
