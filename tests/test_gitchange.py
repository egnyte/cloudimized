import unittest

import mock

from cloudimized.gitcore.gitchange import GitChange

class MyTestCase(unittest.TestCase):
    def testGetFilename(self):
        expected_result = "azure/firewall/project1.yaml"
        gitchange = GitChange("azure", "firewall", "project1")
        result = gitchange.get_filename()
        self.assertEqual(result, expected_result)

    def testGetCommitMsg(self):
        #No changers
        gitchange = GitChange("gcp", "testresource", "testproject")
        expected_result = "Testresource updated in GCP: testproject by UNKNOWN"
        self.assertEqual(gitchange.get_commit_message(), expected_result)

        # Multiple unique changers
        gitchange = GitChange("gcp", "testresource", "testproject")
        mock_gitchangelog1 = mock.MagicMock()
        type(mock_gitchangelog1).changer = mock.PropertyMock(return_value="testuser")
        mock_gitchangelog2 = mock.MagicMock()
        type(mock_gitchangelog2).changer = mock.PropertyMock(return_value="anothertestuser")
        gitchange.gcp_change_log += [mock_gitchangelog1, mock_gitchangelog2]
        expected_result = "Testresource updated in GCP: testproject by ['testuser', 'anothertestuser']"
        self.assertEqual(gitchange.get_commit_message(), expected_result)

        # Multiple non-unique changer
        gitchange = GitChange("gcp", "testresource", "testproject")
        mock_gitchangelog1 = mock.MagicMock()
        type(mock_gitchangelog1).changer = mock.PropertyMock(return_value="testuser")
        mock_gitchangelog2 = mock.MagicMock()
        type(mock_gitchangelog2).changer = mock.PropertyMock(return_value="anothertestuser")
        mock_gitchangelog3 = mock.MagicMock()
        type(mock_gitchangelog3).changer = mock.PropertyMock(return_value="testuser")
        gitchange.gcp_change_log += [mock_gitchangelog1, mock_gitchangelog2, mock_gitchangelog3]
        expected_result = "Testresource updated in GCP: testproject by ['testuser', 'anothertestuser']"
        self.assertEqual(gitchange.get_commit_message(), expected_result)



if __name__ == '__main__':
    unittest.main()

modified_files = [
    "firewall/project1.yaml",
    "vpn/project2.yaml"
]

modified_files_empty = []
