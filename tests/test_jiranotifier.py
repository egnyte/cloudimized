import unittest

import mock
from jira import JIRA

from cloudimized.core.jiranotifier import configure_jiranotifier, JiraNotifier, JiraNotifierError, logger
from cloudimized.gitcore.gitchange import GitChange


class JiraNotifierTestCase(unittest.TestCase):
    def setUp(self) -> None:
        kwargs = {"test_field": [{"name": "test_value"}]}
        self.jiranotifier = JiraNotifier(jira_url="test_url",
                                         projectkey="test_key",
                                         username="test_user",
                                         password="test_pass",
                                         issuetype="test_type",
                                         filter_set=None,
                                         **kwargs)
        self.gitchange = GitChange(provider="azure",
                                   resource_type="test_resource",
                                   project="test_project")
        self.gitchange.diff = "TEST_CHANGE_DIFF"
        self.gitchange.changers = ["test_changer"]

    def test_configure_incorrect_config_type(self):
        with self.assertRaises(JiraNotifierError) as cm:
            configure_jiranotifier(config="incorrect_config_type",
                                   username="test_user",
                                   password="test_password")
        self.assertEqual(f"Incorrect Jira Notifier configuration. Should be dict, is <class 'str'>", str(cm.exception))

    def test_configure_missing_required_key(self):
        with self.assertRaises(JiraNotifierError) as cm:
            configure_jiranotifier(config={"missing_required_key": ""},
                                   username="test_user",
                                   password="test_password")
        self.assertEqual(f"Missing one of required config keys: ['url', 'projectKey']", str(cm.exception))

    def test_configure_missing_credentials(self):
        with self.assertRaises(JiraNotifierError) as cm:
            configure_jiranotifier(config={"url": "", "projectKey": ""},
                                   username="test_user",
                                   password="")
        self.assertEqual(f"Jira password/token not set in env var: 'JIRA_PSW'",
                         str(cm.exception))

    def test_configure_missing_token(self):
        with self.assertRaises(JiraNotifierError) as cm:
            configure_jiranotifier(config={"url": "", "projectKey": "", "isToken": True},
                                   username="",
                                   password="")
        self.assertEqual(f"Jira password/token not set in env var: 'JIRA_PSW'",
                         str(cm.exception))

    def test_configure_incorrect_fields_type(self):
        with self.assertRaises(JiraNotifierError) as cm:
            configure_jiranotifier(config={"url": "", "projectKey": "",
                                           "fields": "incorrect_type"},
                                   username="test_user",
                                   password="test_password")
        self.assertEqual((f"Incorrect Jira Notifier Fields configuration. "
                          f"Should be dict, is <class 'str'>"), str(cm.exception))

    def test_configure_incorrect_filterset_type(self):
        with self.assertRaises(JiraNotifierError) as cm:
            configure_jiranotifier(config={"url": "", "projectKey": "",
                                           "filterSet": "incorrect_type"},
                                   username="test_user",
                                   password="test_password")
        self.assertEqual((f"Incorrect Jira Notifier FilterSet configuration. "
                          f"Should be dict, is <class 'str'>"), str(cm.exception))

    def test_configure_incorrect_projectidfilter_type(self):
        with self.assertRaises(JiraNotifierError) as cm:
            configure_jiranotifier(config={"url": "", "projectKey": "",
                                           "filterSet": {"missing_key": None}},
                                   username="test_user",
                                   password="test_password")
        self.assertEqual(f"Missing required param projectId", str(cm.exception))

    def test_configure_incorrect_projectidfilter_value(self):
        with self.assertRaises(JiraNotifierError) as cm:
            configure_jiranotifier(config={"url": "", "projectKey": "",
                                           "filterSet": {"projectId": []}},
                                   username="test_user",
                                   password="test_password")
        self.assertEqual((f"Incorrect Jira Notifier projectId configuration value. "
                          f"Should be str, is <class 'list'>"), str(cm.exception))

    @mock.patch("cloudimized.core.jiranotifier.JiraNotifier", spec=JiraNotifier)
    def test_configure_correct_result(self, mock_jiranotifier):
        result = configure_jiranotifier(config={"url": "test_url",
                                                "projectKey": "TEST",
                                                "fields": {
                                                    "extra": "testField"
                                                }},
                                        username="test_user",
                                        password="test_password")
        self.assertIsInstance(result, JiraNotifier)
        mock_jiranotifier.assert_called_with(jira_url="test_url",
                                             username="test_user",
                                             password="test_password",
                                             issuetype="Task",
                                             projectkey="TEST",
                                             filter_set=None,
                                             extra="testField")

    @mock.patch("cloudimized.core.jiranotifier.JiraNotifier", spec=JiraNotifier)
    def test_configure_correct_result_with_token_auth(self, mock_jiranotifier):
        result = configure_jiranotifier(config={"url": "test_url",
                                                "projectKey": "TEST",
                                                "isToken": True,
                                                "fields": {
                                                    "extra": "testField"
                                                }},
                                        username="",
                                        password="test_password")
        self.assertIsInstance(result, JiraNotifier)
        mock_jiranotifier.assert_called_with(jira_url="test_url",
                                             username="",
                                             password="test_password",
                                             issuetype="Task",
                                             projectkey="TEST",
                                             filter_set=None,
                                             extra="testField")

    @mock.patch("cloudimized.core.jiranotifier.JIRA", spec=JIRA)
    def test_post_non_manual_change(self, mock_jira):
        self.gitchange.manual = False
        result = self.jiranotifier.post(self.gitchange)
        self.assertIsNone(result)
        mock_jira.assert_not_called()

    @mock.patch("cloudimized.core.jiranotifier.JIRA", spec=JIRA)
    def test_post_non_matching_filter(self, mock_jira):
        self.gitchange.manual = True
        filter_set = {"projectId": "NO_MATCH"}
        self.jiranotifier.filter_set = filter_set
        result = self.jiranotifier.post(self.gitchange)
        self.assertIsNone(result)
        mock_jira.assert_not_called()

    @mock.patch("cloudimized.core.jiranotifier.JIRA", spec=JIRA)
    def test_post_authentication_issue(self, mock_jira):
        self.gitchange.manual = True
        mock_jira.side_effect = Exception("Auth Issue")
        with self.assertRaises(JiraNotifierError) as cm:
            self.jiranotifier.post(self.gitchange)
        self.assertEqual(f"Issue creating ticket\nAuth Issue", f"{str(cm.exception)}\n{str(cm.exception.__cause__)}")

    @mock.patch("cloudimized.core.jiranotifier.JIRA", spec=JIRA)
    def test_post_creating_issue_issue(self, mock_jira):
        self.gitchange.manual = True
        mock_jira_object = mock.MagicMock()
        mock_jira_object.create_issue.side_effect = Exception("Ticket create issue")
        mock_jira.return_value = mock_jira_object
        with self.assertRaises(JiraNotifierError) as cm:
            self.jiranotifier.post(self.gitchange)
        self.assertEqual(f"Issue creating ticket\nTicket create issue",
                         f"{str(cm.exception)}\n{str(cm.exception.__cause__)}")
        mock_jira_object.create_issue.assert_called_with(project={"key": "test_key"},
                                                         summary=(f"GCP manual change detected - project: "
                                                                  f"test_project, resource: test_resource"),
                                                         description=(f"Manual changes performed by test_changer\n\n"
                                                                      f"{{code:java}}\nTEST_CHANGE_DIFF\n{{code}}\n"),
                                                         issuetype={"name": "test_type"},
                                                         test_field=[{"name": "test_value"}])

    @mock.patch("cloudimized.core.jiranotifier.JIRA", spec=JIRA)
    def test_post_update_assignee_issue(self, mock_jira):
        self.gitchange.manual = True
        mock_issue_object = mock.MagicMock()
        mock_issue_object.update.side_effect = Exception("Update Issue")
        type(mock_issue_object).key = mock.PropertyMock(return_value="TEST_KEY")
        mock_jira_object = mock.MagicMock()
        mock_jira_object.create_issue.return_value = mock_issue_object
        mock_jira.return_value = mock_jira_object
        with self.assertLogs(logger, level="WARNING") as cm:
            self.jiranotifier.post(self.gitchange)
        self.assertEqual(f"WARNING:cloudimized.core.jiranotifier:Unable to assign ticket TEST_KEY to "
                         f"changer: test_changer\nUpdate Issue",
                         cm.output[0])
        mock_jira_object.create_issue.assert_called_with(project={"key": "test_key"},
                                                         summary=(f"GCP manual change detected - project: "
                                                                  f"test_project, resource: test_resource"),
                                                         description=(f"Manual changes performed by test_changer\n\n"
                                                                      f"{{code:java}}\nTEST_CHANGE_DIFF\n{{code}}\n"),
                                                         issuetype={"name": "test_type"},
                                                         test_field=[{"name": "test_value"}])
        mock_issue_object.update.assert_called_with(assignee={"name": "test_changer"})

    @mock.patch("cloudimized.core.jiranotifier.JIRA", spec=JIRA)
    def test_post_update_success(self, mock_jira):
        self.gitchange.manual = True
        filter_set = {"projectId": ".est_pro.*"}
        self.jiranotifier.filter_set = filter_set
        mock_issue_object = mock.MagicMock()
        type(mock_issue_object).key = mock.PropertyMock(return_value="TEST_KEY")
        mock_issue_object.__str__.return_value = "test_issue_str"
        mock_jira_object = mock.MagicMock()
        mock_jira_object.create_issue.return_value = mock_issue_object
        mock_jira.return_value = mock_jira_object
        with self.assertLogs(logger, level="INFO") as cm:
            self.jiranotifier.post(self.gitchange)
        self.assertEqual(f"INFO:cloudimized.core.jiranotifier:Assigning issue TEST_KEY to user test_changer",
                         cm.output[-1])
        mock_jira_object.create_issue.assert_called_with(project={"key": "test_key"},
                                                         summary=(f"GCP manual change detected - project: "
                                                                  f"test_project, resource: test_resource"),
                                                         description=(f"Manual changes performed by test_changer\n\n"
                                                                      f"{{code:java}}\nTEST_CHANGE_DIFF\n{{code}}\n"),
                                                         issuetype={"name": "test_type"},
                                                         test_field=[{"name": "test_value"}])
        mock_issue_object.update.assert_called_with(assignee={"name": "test_changer"})


if __name__ == '__main__':
    unittest.main()
