import logging
from typing import Dict, Any
from jira import JIRA

from gitcore.gitchange import GitChange

logger = logging.getLogger(__name__)

DEFAULT_ISSUE_TYPE = "Task"
URL = "url"
PROJECTKEY = "projectKey"
ISSUETYPE = "issueType"
FIELDS = "fields"

class JiraNotifier:
    """
    Creates ticket in Jira for configuration change
    """

    def __init__(self,
                 jira_url: str,
                 projectkey: str,
                 username: str,
                 password: str,
                 issuetype: str,
                 **kwargs):
        """
        :param jira_url: Jira instance URL address
        :param username: Jira's service account user
        :param password: Jira's service account password
        :param kwargs: additional Jira issue fields
        """
        self.jira_url = jira_url
        self.username = username
        self.password = password
        self.projectkey = projectkey
        self.issuetype = issuetype
        self.kwargs = kwargs


    def post(self, change: GitChange):
        """
        Creates Jira issue for Git Change
        """
        logging.info(f"Connecting to Jira '{self.jira_url}' as '{self.username}'")
        try:
            jira = JIRA(options={'server': self.jira_url}, basic_auth=(self.username, self.password))
            summary = f"GCP manual change detected - project: {change.project}, resource: {change.resource_type}"
            # In case multiple changers were identified
            if len(change.changers) == 0:
                changer = "Unknown changer"
            elif len(change.changers) == 1:
                changer = change.changers[0]
            else:
                changer = change.changers
            description = (f"Manual changes performed by {changer}\n\n"
                           f"{{code:java}}\n{change.diff}\n{{code}}\n")
            issue = jira.create_issue(project={"key": self.projectkey},
                                      summary=summary,
                                      description=description,
                                      issuetype={"name": self.issuetype},
                                      **self.kwargs)
        except Exception as e:
            raise JiraNotifierError("Issue creating ticket") from e
        # Assign ticket to changer
        for changer in change.changers:
            try:
                issue.update(assignee={'name': changer})
                logger.info(f"Issue {issue.key} assigned to user {changer}")
                break
            except Exception as e:
                logger.warning(f"Unable to assign ticket {issue.key} to changer: {changer}\n{e}")


class JiraNotifierError(Exception):
    pass


def configure_jiranotifier(config: Dict[str, Any], username: str, password: str):
    """
    Configures JiraNotifier from config file
    :param config: configuration dictionary
    :param username: Jira username
    :param password: Jira password
    """
    if not isinstance(config, dict):
        raise JiraNotifierError(f"Incorrect Jira Notifier configuration. Should be dict, is {type(config)}")
    required_keys = [URL, PROJECTKEY]
    if not all(key in config for key in required_keys):
        raise JiraNotifierError(f"Missing one of required config keys: {required_keys}")
    if not all(key for key in [username, password]):
        raise JiraNotifierError(f"Missing Jira Username/Password credentials")
    extra_fields = config.get(FIELDS, {})
    if not isinstance(extra_fields, dict):
        raise JiraNotifierError(f"Incorrect Jira Notifier Fields configuration. "
                                f"Should be dict, is {type(extra_fields)}")
    return JiraNotifier(jira_url=config.get(URL),
                        username=username,
                        password=password,
                        issuetype=config.get(ISSUETYPE, DEFAULT_ISSUE_TYPE),
                        projectkey=config.get(PROJECTKEY),
                        **extra_fields)
