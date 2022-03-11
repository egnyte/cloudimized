import logging

import git
from typing import List, Dict
from os.path import exists, isdir, join
from os import listdir
from shutil import rmtree
from cloudimized.gitcore.gitchange import GitChange
from os.path import basename, dirname

logger = logging.getLogger(__name__)

#TODO Add command line option to set those
# Env name for passing user/pass
GIT_USER = "GIT_USR"
GIT_PASSWORD = "GIT_PSW"

# Config keys
GIT_SECTION = "git"
GIT_REPO_URL = "remote_url"
GIT_LOCAL_DIR = "local_directory"

class GitRepo:
    """Git repo in which changes are tracked"""

    def __init__(self, user: str, password: str, repo_url: str, directory: str):
        """
        :param user: git username
        :param password: git password or token
        :param repo_url: Git remote repo URL
        :param directory: Git local repo directory
        """
        self.user = user
        self.password = password
        self.repo_url = repo_url
        self.directory = directory
        self.repo = None

    #TODO: Add initial mapping of repo - resource/project - to better compare previous state to current
    # This is useful when a resource existed previously and in current run doesn't exist i.e. project was deleted
    def setup(self) -> None:
        """
        Setup local and remote repo
        """
        if exists(self.directory):
            logger.info(f"Veryfing Git repo at: '{self.directory}'...")
            try:
                self.repo = git.Repo(self.directory)
            except Exception as e:
                raise GitRepoError(f"Directory '{self.directory}' is not a git repo")
            try:
                logger.info(f"Syncing local repo with remote")
                # Remove any local changes, checkout to master and sync with remote
                self.repo.git.reset("--hard")
                self.repo.git.checkout("master")
                self.repo.remotes.origin.fetch()
                self.repo.git.reset("--hard", "origin/master")
            except Exception as e:
                raise GitRepoError(f"Issue syncing remote") from e
        else:
            if self.repo_url.startswith("https://"):
                if self.user is None or self.password is None:
                    raise GitRepoError("Missing credentials for Git HTTPS method")
                # Cloning via HTTPS
                method = "HTTPS"
                # Add user/pass to URL
                repo_url_cred = f"https://{self.user}:{self.password}@{self.repo_url.split('://')[1]}"
            elif self.repo_url.startswith("git@"):
                # Cloning via SSH
                method = "SSH"
                repo_url_cred = self.repo_url
            else:
                raise GitRepoError(f"Incorrect Git URL: '{self.repo_url}'")
            try:
                logger.info(f"Local Git repo not found. Cloning {self.repo_url} into {self.directory} via {method}")
                self.repo = git.Repo.clone_from(repo_url_cred, self.directory)
            except Exception as e:
                raise GitRepoError(f"Issue cloning Git repo {self.repo_url}: {type(e)}\n{e}")

    def get_changes(self) -> List[GitChange]:
        """
        Returns all changes for current repo state
        :returns all detected changes
        """
        if not self.repo:
            raise GitRepoError(f"Git Repo not set up")
        file_changes = self.repo.untracked_files + [item.a_path for item in self.repo.index.diff(None)]
        result = []
        for filename in file_changes:
            resource_type = dirname(filename)
            project = basename(filename).split(".")[0]
            result.append(GitChange(resource_type, project))
        return result

    def commit_change(self, change: GitChange, message: str) -> None:
        """
        Commit change with provided message
        :param change: single resource/project change
        :param message: commit message
        :return:
        """
        try:
            self.repo.git.add(change.get_filename())
            self.repo.git.commit(message)
        except Exception as e:
            raise GitRepoError(f"Issue commiting change for project '{change.project}' "
                               f"type '{change.resource_type}'") from e

    def push_changes(self) -> None:
        """
        Pushes local changes to remote
        """
        try:
            self.repo.remotes.origin.push()
        except Exception as e:
            raise GitRepoError(f"Issue pushing local changes to remote") from e

    def clean_repo(self) -> None:
        """
        Removes all files in repository for preparations for new config scanning
        :raises GitRepoError
        """
        if not self.repo:
            raise GitRepoError(f"Repo '{self.repo_url}' needs to be setup first")
        try:
            # Get all directories in self.directory (to skip files in the list i.e. README.md)
            directories = [name for name in listdir(self.directory) if isdir(join(self.directory, name))]
        except Exception as e:
            raise GitRepoError(f"Issue retrieving directories in directory '{self.directory}'") from e
        try:
            for directory in directories:
                if directory == ".git": #skip git folder
                    continue
                else:
                    logger.info(f"Removing directory '{self.directory}/{directory}")
                    rmtree(f"{self.directory}/{directory}")
        except Exception as e:
            raise GitRepoError(f"Issue removing directories in '{self.directory}'") from e


def configure_repo(user: str, password: str, config: Dict[str, str]) -> GitRepo:
    """
    Parses configuration file with Git Repo configuration
    :param config: repo configuration
    :param user: git username for remote repo
    :param password: git's password/token for remote repo
    :return: Git Repo with parsed configuration
    """
    if not config:
        raise GitRepoConfigError(f"Missing required git section: '{GIT_SECTION}'")
    if not user:
        raise GitRepoConfigError(f"Git username not set in env var: '{GIT_USER}'")
    if not password:
        raise GitRepoConfigError(f"Git password/token not set in env var: '{GIT_PASSWORD}'")
    if not isinstance(config, dict):
        raise GitRepoConfigError(f"Incorrect type in git configuration section: '{GIT_SECTION}'. "
                                 f"Should be dict, is {type(config)}")
    if GIT_REPO_URL not in config:
        raise GitRepoConfigError(f"Missing required key in Git configuration: '{GIT_REPO_URL}'")
    if GIT_LOCAL_DIR not in config:
        raise GitRepoConfigError(f"Missing required key in Git configuration: '{GIT_LOCAL_DIR}'")
    return GitRepo(user=user, password=password, repo_url=config[GIT_REPO_URL], directory=config[GIT_LOCAL_DIR])


class GitRepoError(Exception):
    pass


class GitRepoConfigError(GitRepoError):
    pass
