import unittest
import mock

import cloudimized.gitcore.repo as repo
from cloudimized.gitcore.repo import GitRepo, GitRepoError, configure_repo
from cloudimized.gitcore.gitchange import GitChange

class GitRepoCase(unittest.TestCase):
    def setUp(self) -> None:
        self.gitrepo = GitRepo("user", "password", "https://example.com/test/repo.git", "localRepo")

    @mock.patch("cloudimized.gitcore.repo.git")
    @mock.patch("cloudimized.gitcore.repo.exists")
    def test_setup_local_exists(self, mock_exists, mock_git):
        mock_exists.return_value = True
        # Fetching remote
        self.gitrepo.setup()
        mock_git.Repo().remotes.origin.fetch.assert_called_once()
        mock_git.reset_mock()
        # Issue fetching remote
        with self.assertRaises(repo.GitRepoError):
            mock_git.Repo().remotes.origin.fetch.side_effect = Exception()
            self.gitrepo.setup()

    @mock.patch("cloudimized.gitcore.repo.git")
    @mock.patch("cloudimized.gitcore.repo.exists")
    def test_setup_ssh_cloning(self, mock_exists, mock_git):
        mock_exists.return_value = False
        self.gitrepo.repo_url = "git@git.example.com:test/repo.git"
        self.gitrepo.setup()
        mock_git.Repo.clone_from.assert_called_with("git@git.example.com:test/repo.git", "localRepo")

    @mock.patch("cloudimized.gitcore.repo.git")
    @mock.patch("cloudimized.gitcore.repo.exists")
    def test_setup_https_cloning(self, mock_exists, mock_git):
        mock_exists.return_value = False
        # Test correct url with creds
        self.gitrepo.setup()
        mock_git.Repo.clone_from.assert_called_with("https://user:password@example.com/test/repo.git",
                                                    "localRepo")
        mock_git.reset_mock()

        # Test missing password
        with self.assertRaises(repo.GitRepoError):
            self.gitrepo.user = None
            self.gitrepo.setup()
        mock_git.reset_mock()

        # Test incorrect URL
        with self.assertRaises(repo.GitRepoError):
            self.gitrepo.user = "user"
            self.gitrepo.repo_url = "incorrect_url"
            self.gitrepo.setup()

    def test_get_changes_repo_not_setup(self):
        with self.assertRaises(repo.GitRepoError) as cm:
            self.gitrepo.get_changes()
        self.assertEqual("Git Repo not set up", str(cm.exception))

    def test_get_changes_success(self):
        git_mock = mock.MagicMock()
        type(git_mock).untracked_files = mock.PropertyMock(return_value=["test_resource1/test_untracked_file1.yaml",
                                                                         "test_resource2/test_untracked_file2.yaml"])
        index_mock = mock.MagicMock()
        item_0 = mock.MagicMock()
        type(item_0).a_path = mock.PropertyMock(return_value="test_resource1/test_change_file3.yaml")
        item_1 = mock.MagicMock()
        type(item_1).a_path = mock.PropertyMock(return_value="test_resource3/test_change_file4.yaml")
        index_mock.diff.return_value = [item_0, item_1]
        type(git_mock).index = mock.PropertyMock(return_value=index_mock)
        self.gitrepo.repo = git_mock
        result = self.gitrepo.get_changes()
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 4)
        for change in result:
            self.assertIsInstance(change, GitChange)
        self.assertEqual(result[0].resource_type, "test_resource1")
        self.assertEqual(result[0].project, "test_untracked_file1")
        self.assertEqual(result[1].resource_type, "test_resource2")
        self.assertEqual(result[1].project, "test_untracked_file2")
        self.assertEqual(result[2].resource_type, "test_resource1")
        self.assertEqual(result[2].project, "test_change_file3")
        self.assertEqual(result[3].resource_type, "test_resource3")
        self.assertEqual(result[3].project, "test_change_file4")

    def test_commit_change_exception(self):
        repo_mock = mock.MagicMock()
        repo_mock.git.add.side_effect = Exception()
        self.gitrepo.repo = repo_mock
        with self.assertRaises(GitRepoError) as cm:
            self.gitrepo.commit_change(GitChange(provider="azure", resource_type="test_resource", project="test_project"), "test_message")
        self.assertEqual("Issue commiting change for project 'test_project' type 'test_resource'", str(cm.exception))

    def test_commit_change_success(self):
        repo_mock = mock.MagicMock()
        self.gitrepo.repo = repo_mock
        self.gitrepo.commit_change(GitChange(provider="gcp", resource_type="test_resource", project="test_project"), "test_message")
        repo_mock.git.add.assert_called_with("gcp/test_resource/test_project.yaml")
        repo_mock.git.commit.assert_called_with("test_message")

    def test_push_changes_issue(self):
        repo_mock = mock.MagicMock()
        repo_mock.remotes.origin.push.side_effect = Exception()
        self.gitrepo.repo = repo_mock
        with self.assertRaises(GitRepoError) as cm:
            self.gitrepo.push_changes()
        self.assertEqual("Issue pushing local changes to remote", str(cm.exception))

    def test_push_changes_success(self):
        repo_mock = mock.MagicMock()
        self.gitrepo.repo = repo_mock
        self.gitrepo.push_changes()
        repo_mock.remotes.origin.push.assert_called_once()

    @mock.patch("cloudimized.gitcore.repo.GitRepo", spec=GitRepo)
    def test_configure_repo(self, mock_gitrepo):
        # Missing username
        with self.assertRaises(repo.GitRepoConfigError):
            configure_repo(user=None, password=None, config={})
        # Missing password
        with self.assertRaises(repo.GitRepoConfigError):
            configure_repo(user="test_user", password=None, config={})
        # Incorrect config format
        with self.assertRaises(repo.GitRepoConfigError):
            configure_repo(user="test_user", password="secret", config=[])
        # Missing required key in dictionary
        with self.assertRaises(repo.GitRepoConfigError):
            configure_repo(user="test_user", password="secret", config={})
        # Missing required key in dictionary
        with self.assertRaises(repo.GitRepoConfigError):
            configure_repo(user="test_user", password="secret", config=no_local_dir_config)

        result = configure_repo(user="test_user", password="secret", config=local_dir_config)
        self.assertIsInstance(result, GitRepo)
        mock_gitrepo.assert_called_with("test_user", "secret", "test_url", "/local/dir")

    @mock.patch("cloudimized.gitcore.repo.rmtree")
    @mock.patch("cloudimized.gitcore.repo.listdir")
    def test_clean_repo_not_setup(self, mock_listdir, mock_rmtree):
        with self.assertRaises(GitRepoError) as cm:
            self.gitrepo.clean_repo()
        self.assertEqual("Repo 'https://example.com/test/repo.git' needs to be setup first",
                         str(cm.exception))

    @mock.patch("cloudimized.gitcore.repo.rmtree")
    @mock.patch("cloudimized.gitcore.repo.listdir")
    def test_clean_repo_listing_issue(self, mock_listdir, mock_rmtree):
        self.gitrepo.repo = mock.MagicMock()
        mock_listdir.side_effect = Exception("issue")
        with self.assertRaises(GitRepoError) as cm:
            self.gitrepo.clean_repo()
        self.assertEqual("Issue retrieving directories in directory 'localRepo'",
                         str(cm.exception))

    @mock.patch("cloudimized.gitcore.repo.isdir")
    @mock.patch("cloudimized.gitcore.repo.rmtree")
    @mock.patch("cloudimized.gitcore.repo.listdir")
    def test_clean_repo_remove_issue(self, mock_listdir, mock_rmtree, mock_isdir):
        self.gitrepo.repo = mock.MagicMock()
        mock_listdir.return_value = ["test_directory1", "test_directory2"]
        mock_isdir.side_effect = [True, True]
        mock_rmtree.side_effect = Exception("issue")
        with self.assertRaises(GitRepoError) as cm:
            self.gitrepo.clean_repo()
        self.assertEqual("Issue removing directories in 'localRepo'",
                         str(cm.exception))

    @mock.patch("cloudimized.gitcore.repo.isdir")
    @mock.patch("cloudimized.gitcore.repo.rmtree")
    @mock.patch("cloudimized.gitcore.repo.listdir")
    def test_clean_repo_only_git_folder(self, mock_listdir, mock_rmtree, mock_isdir):
        self.gitrepo.repo = mock.MagicMock()
        mock_listdir.return_value = [".git"]
        mock_isdir.side_effect = [True]
        self.gitrepo.clean_repo()
        mock_rmtree.assert_not_called()

    @mock.patch("cloudimized.gitcore.repo.isdir")
    @mock.patch("cloudimized.gitcore.repo.rmtree")
    @mock.patch("cloudimized.gitcore.repo.listdir")
    def test_clean_repo_success(self, mock_listdir, mock_rmtree, mock_isdir):
        self.gitrepo.repo = mock.MagicMock()
        mock_listdir.return_value = [".git", "test_directory1", "test_directory2", "README.md"]
        mock_isdir.side_effect = [True, True, True, False]
        self.gitrepo.clean_repo()
        calls = [
            mock.call("localRepo/test_directory1"),
            mock.call("localRepo/test_directory2")
        ]
        mock_rmtree.assert_has_calls(calls)

if __name__ == '__main__':
    unittest.main()


missing_url_config = {
}

no_local_dir_config = {
    repo.GIT_REPO_URL: "test_url"
}

local_dir_config = {
    repo.GIT_REPO_URL: "test_url",
    repo.GIT_LOCAL_DIR: "/local/dir"
}
