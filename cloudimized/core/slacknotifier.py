import logging
from slack_sdk import WebClient
from typing import Dict, Any

from cloudimized.gitcore.gitchange import GitChange

logger = logging.getLogger(__name__)

MANUAL_CHANGE_HEADER = ":warning: *MANUAL CHANGE* :warning:"
SLACK_TOKEN = "SLACK_TOKEN"
CHANNEL_ID = "channelID"
REPO_COMMIT_URL = "repoCommitURL"


class SlackNotifier:
    """
    Sends change notificiations to Slack
    """

    def __init__(self, token: str, channelID: str, repo_commit_url: str):
        """
        :param token: bot user OAuth Token
        :param channelID: channel ID
        :param repo_commit_url: URL base for Git Repository commits
        """
        self.channelID = channelID
        self.token = token
        self.repo_commit_url = repo_commit_url

    def post(self, change: GitChange):
        """
        Posts message to Slack
        :param change: change to post into Slack
        """
        client = WebClient(token=self.token)
        comment = ""
        if change.manual:
            comment = f"{MANUAL_CHANGE_HEADER}\n"
        comment += f"{change.message}\n"

        if change.commit:
            comment += f"Commit: {self.repo_commit_url}/{change.commit}\n"
        else:
            comment += f"Unknown commit ID: {self.repo_commit_url}s/master\n"

        try:
            response = client.files_upload(
                channels=self.channelID,
                title=change.get_filename(),
                content=change.diff,
                initial_comment=comment
            )
        except Exception as e:
            raise SlackNotifierError("Issue posting to Slack channel") from e


def configure_slack_notifier(config: Dict[str, Any],
                             token: str) -> SlackNotifier:
    """
    Builds Slack Notifier from configuraiton file with sanity check
    :param config: Slack Notifier configuration section from config file
    :param token: Slack App Bot token passed outside of configuration file
    """
    if config is None:
        return None
    channelID = config.get(CHANNEL_ID, None)
    repo_commit_url = config.get(REPO_COMMIT_URL, None)
    if not isinstance(channelID, str):
        raise SlackNotifierError(f"Incorrect type of config element {CHANNEL_ID}. "
                                 f"Should be str, is {type(CHANNEL_ID)}")
    if not isinstance(repo_commit_url, str):
        raise SlackNotifierError(f"Incorrect type of config element {REPO_COMMIT_URL}. "
                                 f"Should be str, is {type(REPO_COMMIT_URL)}")
    if not isinstance(token, str):
        raise SlackNotifierError(f"Missing Slack App Bot token. Set env var {SLACK_TOKEN}"
                                 f" with correct value")
    return SlackNotifier(token=token,
                         channelID=channelID,
                         repo_commit_url=repo_commit_url)


class SlackNotifierError(Exception):
    pass
