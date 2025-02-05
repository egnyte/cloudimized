import logging
import unittest
import mock
import datetime as dt

import time_machine

from cloudimized.core.changeprocessor import ChangeProcessor, ChangeProcessorError, configure_change_processor
from cloudimized.gitcore.repo import GitRepo
from cloudimized.gitcore.gitchange import GitChange
from cloudimized.gcpcore.gcpquery import GcpQuery
from cloudimized.gcpcore.gcpchangelog import GcpChangeLog
from cloudimized.tfcore.query import TFQuery, TFQueryError
from cloudimized.tfcore.run import TFRun


class ChangeProcessorTestCase(unittest.TestCase):
    @time_machine.travel(dt.datetime(1985, 10, 26, 1, 24))
    def setUp(self) -> None:
        logging.disable(logging.CRITICAL)
        self.processor = ChangeProcessor(repo=mock.MagicMock(spec=GitRepo),
                                         gcp_type_queries_map=test_gcp_type_queries_map,
                                         scan_interval=30,
                                         service_account_regex=test_service_account_regex,
                                         tf_query=mock.MagicMock(spec=TFQuery),
                                         ticket_regex=test_ticket_regex,
                                         ticket_sys_url="https://test.ticketing.system/browse")
        self.processor.repo.repo = mock.MagicMock()

        test_tfrun1 = TFRun(message="test_message1 changed in TEST_1234 ticket",
                            run_id="test0123456789",
                            status="applied",
                            apply_time=dt.datetime.utcnow(),
                            org="test_org",
                            workspace="test_workspace")

        test_tfrun2 = TFRun(message="test_message2",
                            run_id="test1234567890",
                            status="planned",
                            apply_time=dt.datetime.utcnow(),
                            org="test_org",
                            workspace="test_workspace")
        self.test_tfruns = [test_tfrun1, test_tfrun2]

        self.config = {
            "scan_interval": 30,
            "service_account_regex": "^test-terraform_.*",
            "ticket_regex": "^.*?(TEST[-_][0-9]+).*",
            "ticket_sys_url": "https://test_terraform.com"
        }
        self.type_query_map = {
            "test_resource" : mock.MagicMock(spec=GcpQuery)
        }

    def tearDown(self) -> None:
        logging.disable(logging.NOTSET)

    def test_process_add_error(self):
        self.processor.repo.repo.git.add.side_effect = Exception("test_error")
        with self.assertRaises(ChangeProcessorError) as cm:
            self.processor.process([test_git_change1], None)
        self.assertEqual("Issue adding file 'azure/test_resource1/test_project1.yaml' in Git", str(cm.exception))
        self.processor.repo.repo.remotes.origin.push.assert_not_called()

    def test_process_add_error_gcp(self):
        self.processor.repo.repo.git.add.side_effect = Exception("test_error")
        with self.assertRaises(ChangeProcessorError) as cm:
            self.processor.process([test_git_change2], None)
        self.assertEqual("Issue adding file 'gcp/test_resource1/test_project1.yaml' in Git", str(cm.exception))
        self.processor.repo.repo.remotes.origin.push.assert_not_called()


    @time_machine.travel(dt.datetime(1985, 10, 26, 1, 24))
    @mock.patch("cloudimized.core.changeprocessor.getChangeLogs")
    def test_process_non_change(self, mock_getchangelogs):
        self.processor.repo.repo.index.diff.return_value = False
        self.processor.repo.repo.iter_commits.return_value = []
        self.processor.process([test_git_change1], None)
        mock_getchangelogs.assert_not_called()
        self.processor.repo.repo.remotes.origin.push.assert_not_called()

    @time_machine.travel(dt.datetime(1985, 10, 26, 1, 24))
    @mock.patch("cloudimized.core.changeprocessor.getChangeLogs")
    def test_process_empty_repo_case_gcp(self, mock_getchangelogs):
        self.processor.repo.repo.index.diff.side_effect = Exception("test issue")
        self.processor.repo.repo.iter_commits.side_effect = Exception("test issue #2")
        self.processor.repo.repo.git.rev_list.return_value = 1

        self.processor.process([test_git_change2], None)
        expected_message = "Test_Resource1 updated in GCP: test_project1\n Unable to identify changer"
        self.assertEqual(expected_message,
                         test_git_change2.message)
        mock_getchangelogs.assert_called_once()
        self.processor.repo.repo.git.commit.assert_called_with(m=expected_message)
        self.processor.repo.repo.remotes.origin.push.assert_called_once()

    @time_machine.travel(dt.datetime(1985, 10, 26, 1, 24))
    @mock.patch("cloudimized.core.changeprocessor.getChangeLogs")
    def test_process_empty_repo_case_azure(self, mock_getchangelogs):
        self.processor.repo.repo.index.diff.side_effect = Exception("test issue")
        self.processor.repo.repo.iter_commits.side_effect = Exception("test issue #2")
        self.processor.repo.repo.git.rev_list.return_value = 1

        self.processor.process([test_git_change1], None)
        expected_message = "Test_Resource1 updated in AZURE: test_project1"
        self.assertEqual(expected_message,
                         test_git_change1.message)
        assert not mock_getchangelogs.called
        self.processor.repo.repo.git.commit.assert_called_with(m=expected_message)
        self.processor.repo.repo.remotes.origin.push.assert_called_once()

    @time_machine.travel(dt.datetime(1985, 10, 26, 1, 24))
    @mock.patch("cloudimized.core.changeprocessor.getChangeLogs")
    def test_process_empty_repo_case_with_commit_count_error_gcp(self, mock_getchangelogs):
        self.processor.repo.repo.index.diff.side_effect = Exception("test issue")
        self.processor.repo.repo.iter_commits.side_effect = Exception("test issue #2")
        self.processor.repo.repo.git.rev_list.side_effect = Exception("test issue #3")

        self.processor.process([test_git_change2], None)
        expected_message = "Test_Resource1 updated in GCP: test_project1\n Unable to identify changer"
        self.assertEqual(expected_message,
                         test_git_change2.message)
        mock_getchangelogs.assert_called_once()
        self.processor.repo.repo.git.commit.assert_called_with(m=expected_message)
        self.processor.repo.repo.remotes.origin.push.assert_called_once()

    @time_machine.travel(dt.datetime(1985, 10, 26, 1, 24))
    @mock.patch("cloudimized.core.changeprocessor.getChangeLogs")
    def test_process_empty_repo_case_with_commit_count_error_azure(self, mock_getchangelogs):
        self.processor.repo.repo.index.diff.side_effect = Exception("test issue")
        self.processor.repo.repo.iter_commits.side_effect = Exception("test issue #2")
        self.processor.repo.repo.git.rev_list.side_effect = Exception("test issue #3")

        self.processor.process([test_git_change1], None)
        expected_message = "Test_Resource1 updated in AZURE: test_project1"
        self.assertEqual(expected_message,
                         test_git_change1.message)
        assert not mock_getchangelogs.called
        self.processor.repo.repo.git.commit.assert_called_with(m=expected_message)
        self.processor.repo.repo.remotes.origin.push.assert_called_once()

    @time_machine.travel(dt.datetime(1985, 10, 26, 1, 24))
    @mock.patch("cloudimized.core.changeprocessor.getChangeLogs")
    def test_process_getchangelogs_error_gcp(self, mock_getchangelogs):
        mock_getchangelogs.side_effect = Exception("test error")
        self.processor.repo.repo.iter_commits.return_value = ["test_commit_hash"]

        self.processor.process([test_git_change2], None)
        expected_message = "Test_Resource1 updated in GCP: test_project1\n Unable to identify changer"
        self.assertEqual(expected_message,
                         test_git_change2.message)
        mock_getchangelogs.assert_called_once()
        self.processor.repo.repo.git.commit.assert_called_with(m=expected_message)
        self.processor.repo.repo.remotes.origin.push.assert_called_once()

    @time_machine.travel(dt.datetime(1985, 10, 26, 1, 24))
    @mock.patch("cloudimized.core.changeprocessor.getChangeLogs")
    def test_process_getchangelogs_error_azure(self, mock_getchangelogs):
        mock_getchangelogs.side_effect = Exception("test error")
        self.processor.repo.repo.iter_commits.return_value = ["test_commit_hash"]

        self.processor.process([test_git_change1], None)
        expected_message = "Test_Resource1 updated in AZURE: test_project1"
        self.assertEqual(expected_message,
                         test_git_change1.message)
        assert not mock_getchangelogs.called
        self.processor.repo.repo.git.commit.assert_called_with(m=expected_message)
        self.processor.repo.repo.remotes.origin.push.assert_called_once()

    @time_machine.travel(dt.datetime(1985, 10, 26, 1, 24))
    @mock.patch("cloudimized.core.changeprocessor.getChangeLogs")
    def test_process_no_gcp_logs_found(self, mock_getchangelogs):
        self.processor.repo.repo.iter_commits.return_value = ["test_commit_hash"]
        mock_getchangelogs.return_value = []
        self.processor.process([test_git_change2], None)
        self.assertEqual("Test_Resource1 updated in GCP: test_project1\n Unable to identify changer",
                         test_git_change2.message)
        mock_getchangelogs.assert_called_once()
        self.processor.repo.repo.remotes.origin.push.assert_called_once()

    @time_machine.travel(dt.datetime(1985, 10, 26, 1, 24))
    @mock.patch("cloudimized.core.changeprocessor.getChangeLogs")
    def test_process_missing_changer_in_gcp_log(self, mock_getchangelogs):
        self.processor.repo.repo.iter_commits.return_value = ["test_commit_hash"]
        gcp_change_log_mock1 = mock.MagicMock(spec=GcpChangeLog)
        type(gcp_change_log_mock1).changer = mock.PropertyMock(return_value=None)
        mock_getchangelogs.return_value = [gcp_change_log_mock1]

        self.processor.process([test_git_change2], None)
        expected_message = "Test_Resource1 updated in GCP: test_project1\n Unable to identify changer"
        self.assertEqual(expected_message,
                         test_git_change2.message)
        mock_getchangelogs.assert_called_once()
        self.processor.repo.repo.git.commit.assert_called_with(m=expected_message)
        self.processor.repo.repo.remotes.origin.push.assert_called_once()

    @time_machine.travel(dt.datetime(1985, 10, 26, 1, 24))
    @mock.patch("cloudimized.core.changeprocessor.getChangeLogs")
    def test_process_parsing_login_error(self, mock_getchangelogs):
        self.processor.repo.repo.iter_commits.return_value = ["test_commit_hash"]
        gcp_change_log_mock1 = mock.MagicMock(spec=GcpChangeLog)
        type(gcp_change_log_mock1).changer = mock.PropertyMock(return_value=1)
        mock_getchangelogs.return_value = [gcp_change_log_mock1]

        self.processor.process([test_git_change2], None)
        expected_message = "Test_Resource1 updated in GCP: test_project1\n Change done by unknown user '1'"
        self.assertEqual(expected_message,
                         test_git_change2.message)
        mock_getchangelogs.assert_called_once()
        self.processor.repo.repo.git.commit.assert_called_with(m=expected_message)
        self.processor.repo.repo.remotes.origin.push.assert_called_once()

    @time_machine.travel(dt.datetime(1985, 10, 26, 1, 24))
    @mock.patch("cloudimized.core.changeprocessor.getChangeLogs")
    def test_process_parsing_manual_change(self, mock_getchangelogs):
        self.processor.repo.repo.iter_commits.return_value = ["test_commit_hash"]
        gcp_change_log_mock1 = mock.MagicMock(spec=GcpChangeLog)
        type(gcp_change_log_mock1).changer = mock.PropertyMock(return_value=test_manual_changer)
        mock_getchangelogs.return_value = [gcp_change_log_mock1]

        self.processor.process([test_git_change2], None)
        expected_message = "Test_Resource1 updated in GCP: test_project1\n MANUAL change done by test_user"
        self.assertEqual(expected_message,
                         test_git_change2.message)
        mock_getchangelogs.assert_called_once()
        self.processor.repo.repo.git.commit.assert_called_with(m=expected_message)
        self.processor.repo.repo.remotes.origin.push.assert_called_once()

    @time_machine.travel(dt.datetime(1985, 10, 26, 1, 24))
    @mock.patch("cloudimized.core.changeprocessor.getChangeLogs")
    def test_process_parsing_gcp_logs_with_same_changer(self, mock_getchangelogs):
        self.processor.repo.repo.iter_commits.return_value = ["test_commit_changer"]
        gcp_change_log_mock1 = mock.MagicMock(spec=GcpChangeLog)
        type(gcp_change_log_mock1).changer = mock.PropertyMock(return_value=test_manual_changer)
        gcp_change_log_mock2 = mock.MagicMock(spec=GcpChangeLog)
        type(gcp_change_log_mock2).changer = mock.PropertyMock(return_value=test_manual_changer)
        mock_getchangelogs.return_value = [gcp_change_log_mock1, gcp_change_log_mock2]

        self.processor.process([test_git_change2], None)
        expected_message = "Test_Resource1 updated in GCP: test_project1\n MANUAL change done by test_user"
        self.assertEqual(expected_message,
                         test_git_change2.message)
        mock_getchangelogs.assert_called_once()
        self.processor.repo.repo.git.commit.assert_called_once_with(m=expected_message)
        self.processor.repo.repo.remotes.origin.push.assert_called_once()

    @time_machine.travel(dt.datetime(1985, 10, 26, 1, 24))
    @mock.patch("cloudimized.core.changeprocessor.getChangeLogs")
    def test_process_get_runs_error_gcp(self, mock_getchangelogs):
        self.processor.repo.repo.iter_commits.return_value = ["test_commit_hash"]
        gcp_change_log_mock1 = mock.MagicMock(spec=GcpChangeLog)
        type(gcp_change_log_mock1).changer = mock.PropertyMock(return_value=test_terraform_service_account)
        mock_getchangelogs.return_value = [gcp_change_log_mock1]
        self.processor.tf_query.get_runs.side_effect = TFQueryError("test error")

        self.processor.process([test_git_change2], None)
        expected_message = "Test_Resource1 updated in GCP: test_project1\n Terraform change done by test-terraform_workspace"
        self.assertEqual(expected_message,
                         test_git_change2.message)
        mock_getchangelogs.assert_called_once()
        self.processor.tf_query.get_runs.assert_called_once_with(gcp_sa="test-terraform_workspace")
        self.processor.repo.repo.git.commit.assert_called_with(m=expected_message)
        self.processor.repo.repo.remotes.origin.push.assert_called_once()

    @time_machine.travel(dt.datetime(1985, 10, 26, 1, 24))
    @mock.patch("cloudimized.core.changeprocessor.getChangeLogs")
    def test_process_get_runs_error_azure(self, mock_getchangelogs):
        self.processor.repo.repo.iter_commits.return_value = ["test_commit_hash"]
        gcp_change_log_mock1 = mock.MagicMock(spec=GcpChangeLog)
        type(gcp_change_log_mock1).changer = mock.PropertyMock(return_value=test_terraform_service_account)
        mock_getchangelogs.return_value = [gcp_change_log_mock1]
        self.processor.tf_query.get_runs.side_effect = TFQueryError("test error")

        self.processor.process([test_git_change1], None)
        expected_message = "Test_Resource1 updated in AZURE: test_project1"
        self.assertEqual(expected_message,
                         test_git_change1.message)
        assert not mock_getchangelogs.called
        assert not self.processor.tf_query.get_runs.called
        self.processor.repo.repo.git.commit.assert_called_with(m=expected_message)
        self.processor.repo.repo.remotes.origin.push.assert_called_once()

    @time_machine.travel(dt.datetime(1985, 10, 26, 1, 24))
    @mock.patch("cloudimized.core.changeprocessor.getChangeLogs")
    def test_process_skip_ticket_processing(self, mock_getchangelogs):
        self.processor.repo.repo.iter_commits.return_value = ["test_commit_hash"]
        self.processor.ticket_regex = None
        gcp_change_log_mock1 = mock.MagicMock(spec=GcpChangeLog)
        type(gcp_change_log_mock1).changer = mock.PropertyMock(return_value=test_terraform_service_account)
        mock_getchangelogs.return_value = [gcp_change_log_mock1]
        self.processor.tf_query.get_runs.return_value = self.test_tfruns
        type(self.processor.tf_query).tf_url = mock.PropertyMock(return_value="https://test_terraform.com")

        self.processor.process([test_git_change2], None)
        expected_message = "Test_Resource1 updated in GCP: test_project1\n" \
                           " Terraform change done by test-terraform_workspace\n" \
                           " Related TF run " \
                           "https://test_terraform.com/app/test_org/workspaces/test_workspace/runs/test0123456789"
        self.assertEqual(expected_message,
                         test_git_change2.message)
        mock_getchangelogs.assert_called_once()
        self.processor.tf_query.get_runs.assert_called_once_with(gcp_sa="test-terraform_workspace")
        self.processor.repo.repo.git.commit.assert_called_with(m=expected_message)
        self.processor.repo.repo.remotes.origin.push.assert_called_once()

    @time_machine.travel(dt.datetime(1985, 10, 26, 1, 24))
    @mock.patch("cloudimized.core.changeprocessor.re")
    @mock.patch("cloudimized.core.changeprocessor.getChangeLogs")
    def test_process_with_ticket_processing_error(self, mock_getchangelogs, mock_re):
        self.processor.repo.repo.iter_commits.return_value = ["test_commit_hash"]
        gcp_change_log_mock1 = mock.MagicMock(spec=GcpChangeLog)
        type(gcp_change_log_mock1).changer = mock.PropertyMock(return_value=test_terraform_service_account)
        mock_getchangelogs.return_value = [gcp_change_log_mock1]
        self.processor.tf_query.get_runs.return_value = self.test_tfruns
        type(self.processor.tf_query).tf_url = mock.PropertyMock(return_value="https://test_terraform.com")
        mock_re.search.return_value = "invalid value"

        self.processor.process([test_git_change2], None)
        expected_message = "Test_Resource1 updated in GCP: test_project1\n" \
                           " Terraform change done by test-terraform_workspace\n" \
                           " Related TF run " \
                           "https://test_terraform.com/app/test_org/workspaces/test_workspace/runs/test0123456789"
        self.assertEqual(expected_message,
                         test_git_change2.message)
        mock_getchangelogs.assert_called_once()
        self.processor.tf_query.get_runs.assert_called_once_with(gcp_sa="test-terraform_workspace")
        self.processor.repo.repo.git.commit.assert_called_with(m=expected_message)
        self.processor.repo.repo.remotes.origin.push.assert_called_once()

    @time_machine.travel(dt.datetime(1985, 10, 26, 1, 24))
    @mock.patch("cloudimized.core.changeprocessor.getChangeLogs")
    def test_process_with_ticket_processing(self, mock_getchangelogs):
        self.processor.repo.repo.iter_commits.return_value = ["test_commit_hash"]
        gcp_change_log_mock1 = mock.MagicMock(spec=GcpChangeLog)
        type(gcp_change_log_mock1).changer = mock.PropertyMock(return_value=test_terraform_service_account)
        mock_getchangelogs.return_value = [gcp_change_log_mock1]
        self.processor.tf_query.get_runs.return_value = self.test_tfruns
        type(self.processor.tf_query).tf_url = mock.PropertyMock(return_value="https://test_terraform.com")

        self.processor.process([test_git_change2], None)
        expected_message = "Test_Resource1 updated in GCP: test_project1\n" \
                           " Terraform change done by test-terraform_workspace\n" \
                           " Related TF run " \
                           "https://test_terraform.com/app/test_org/workspaces/test_workspace/runs/test0123456789\n" \
                           " Related ticket https://test.ticketing.system/browse/TEST-1234"
        self.assertEqual(expected_message,
                         test_git_change2.message)
        mock_getchangelogs.assert_called_once()
        self.processor.tf_query.get_runs.assert_called_once_with(gcp_sa="test-terraform_workspace")
        self.processor.repo.repo.git.commit.assert_called_with(m=expected_message)
        self.processor.repo.repo.remotes.origin.push.assert_called_once()

    def test_configure_config_type_error(self):
        with self.assertRaises(ChangeProcessorError) as cm:
            configure_change_processor(config="invalid type",
                                       gcp_type_queries_map=self.type_query_map,
                                       repo=mock.MagicMock(spec=GitRepo),
                                       slack_token="test_token",
                                       jira_user="test_jira_user",
                                       jira_token="test_jira_psw")
        self.assertEqual("Incorrect type of config element change_processor. Should be dict, is <class 'str'>",
                         str(cm.exception))

    def test_configure_scan_missing(self):
        del self.config["scan_interval"]
        with self.assertRaises(ChangeProcessorError) as cm:
            configure_change_processor(config=self.config,
                                       gcp_type_queries_map=self.type_query_map,
                                       repo=mock.MagicMock(spec=GitRepo),
                                       slack_token="test_token",
                                       jira_user="test_jira_user",
                                       jira_token="test_jira_psw")
        self.assertEqual("Missing required parameter 'scan_interval' in 'change_processor' section.",
                         str(cm.exception))

    def test_configure_service_account_regex_missing(self):
        del self.config["service_account_regex"]
        with self.assertRaises(ChangeProcessorError) as cm:
            configure_change_processor(config=self.config,
                                       gcp_type_queries_map=self.type_query_map,
                                       repo=mock.MagicMock(spec=GitRepo),
                                       slack_token="test_token",
                                       jira_user="test_jira_user",
                                       jira_token="test_jira_psw")
        self.assertEqual("Missing required parameter 'service_account_regex' in 'change_processor' section.",
                         str(cm.exception))

    def test_configure_scan_interval_type_error(self):
        self.config["scan_interval"] = "invalid_type"
        with self.assertRaises(ChangeProcessorError) as cm:
            configure_change_processor(config=self.config,
                                       gcp_type_queries_map=self.type_query_map,
                                       repo=mock.MagicMock(spec=GitRepo),
                                       slack_token="test_token",
                                       jira_user="test_jira_user",
                                       jira_token="test_jira_psw")
        self.assertEqual("Incorrect type of config element scan_interval. Should be int, is <class 'str'>",
                         str(cm.exception))

    def test_configure_service_account_regex_type_error(self):
        self.config["service_account_regex"] = 1
        with self.assertRaises(ChangeProcessorError) as cm:
            configure_change_processor(config=self.config,
                                       gcp_type_queries_map=self.type_query_map,
                                       repo=mock.MagicMock(spec=GitRepo),
                                       slack_token="test_token",
                                       jira_user="test_jira_user",
                                       jira_token="test_jira_psw")
        self.assertEqual("Incorrect type of config element service_account_regex. Should be str, is <class 'int'>",
                         str(cm.exception))

    def test_configure_ticket_regex_type_error(self):
        self.config["ticket_regex"] = 1
        with self.assertRaises(ChangeProcessorError) as cm:
            configure_change_processor(config=self.config,
                                       gcp_type_queries_map=self.type_query_map,
                                       repo=mock.MagicMock(spec=GitRepo),
                                       slack_token="test_token",
                                       jira_user="test_jira_user",
                                       jira_token="test_jira_psw")
        self.assertEqual("Incorrect type of config element ticket_regex. Should be str, is <class 'int'>",
                         str(cm.exception))

    def test_configure_ticket_sys_url_type_error(self):
        self.config["ticket_regex"] = 1
        with self.assertRaises(ChangeProcessorError) as cm:
            configure_change_processor(config=self.config,
                                       gcp_type_queries_map=self.type_query_map,
                                       repo=mock.MagicMock(spec=GitRepo),
                                       slack_token="test_token",
                                       jira_user="test_jira_user",
                                       jira_token="test_jira_psw")
        self.assertEqual("Incorrect type of config element ticket_regex. Should be str, is <class 'int'>",
                         str(cm.exception))

    def test_configure_type_query_map_type_error(self):
        with self.assertRaises(ChangeProcessorError) as cm:
            configure_change_processor(config=self.config,
                                       gcp_type_queries_map="incorrect type",
                                       repo=mock.MagicMock(spec=GitRepo),
                                       slack_token="test_token",
                                       jira_user="test_jira_user",
                                       jira_token="test_jira_psw")
        self.assertEqual("Incorrect type of config element gcp_type_queries_map. Should be dict, is <class 'str'>",
                         str(cm.exception))

    def test_configure_repo_type_error(self):
        with self.assertRaises(ChangeProcessorError) as cm:
            configure_change_processor(config=self.config,
                                       gcp_type_queries_map=self.type_query_map,
                                       repo="incorrect_type",
                                       slack_token="test_token",
                                       jira_user="test_jira_user",
                                       jira_token="test_jira_psw")
        self.assertEqual("Incorrect type of repo parameter. Should be GitRepo, is <class 'str'>",
                         str(cm.exception))

    @mock.patch("cloudimized.core.changeprocessor.configure_tfquery")
    def test_configure_tfquery_type_error(self, mock_tfquery):
        mock_tfquery.return_value = "incorrect_type"
        with self.assertRaises(ChangeProcessorError) as cm:
            configure_change_processor(config=self.config,
                                       gcp_type_queries_map=self.type_query_map,
                                       repo=mock.MagicMock(spec=GitRepo),
                                       slack_token="test_token",
                                       jira_user="test_jira_user",
                                       jira_token="test_jira_psw")
        self.assertEqual("Incorrect type of tf_query parameter. Should be TFQuery, is <class 'str'>",
                         str(cm.exception))

    def test_configure_tfquery_not_set(self):
        configure_change_processor(config=self.config,
                                   gcp_type_queries_map=self.type_query_map,
                                   repo=mock.MagicMock(spec=GitRepo),
                                   slack_token="test_token",
                                   jira_user="test_jira_user",
                                   jira_token="test_jira_psw")

    #TODO Add tests for jiranotifier

    def test_configure_success(self):
        result = configure_change_processor(config=self.config,
                                            gcp_type_queries_map=self.type_query_map,
                                            repo=mock.MagicMock(spec=GitRepo),
                                            slack_token="test_token",
                                            jira_user="test_jira_user",
                                            jira_token="test_jira_psw")


if __name__ == '__main__':
    unittest.main()

test_gcpquery1 = mock.MagicMock(spec=GcpQuery)
test_gcpquery2 = mock.MagicMock(spec=GcpQuery)

test_gcp_type_queries_map = {
    "test_resource1": test_gcpquery1,
    "test_resource2": test_gcpquery2
}

test_service_account_regex = '^test-terraform_.*'
test_ticket_regex = '^.*?(TEST[-_][0-9]+).*'

test_git_change1 = GitChange(provider="azure", resource_type="test_resource1", project="test_project1")
test_git_change2 = GitChange(provider="gcp", resource_type="test_resource1", project="test_project1")
test_git_change_unknownProvider = GitChange(provider="unknown", resource_type="test_resource1", project="test_project1")

test_manual_changer = "test_user@example.com"
test_terraform_service_account = "test-terraform_workspace@example.com"
