import logging
import re
from datetime import datetime
from typing import Dict, List, Any

from cloudimized.core.jiranotifier import JiraNotifier, JiraNotifierError, configure_jiranotifier
from cloudimized.core.slacknotifier import SlackNotifier, SlackNotifierError, configure_slack_notifier
from cloudimized.gcpcore.gcpchangelog import getChangeLogs
from cloudimized.gcpcore.gcpquery import GcpQuery
from cloudimized.gitcore.gitchange import GitChange
from cloudimized.gitcore.repo import GitRepo
from cloudimized.tfcore.query import TFQuery, TFQueryError, configure_tfquery

logger = logging.getLogger(__name__)

CHANGE_TF_RUN_STATE = ['applied', 'errored']
CHANGE_PROCESSOR = "change_processor"
SCAN_INTERVAL = "scan_interval"
SERVICE_ACCOUNT_REGEX = "service_account_regex"
TICKET_REGEX = "ticket_regex"
TICKET_SYS_URL = "ticket_sys_url"
TERRAFORM_SECTION = "terraform"
SLACK_SECTION = "slack"
JIRA_SECTION = "jira"


class ChangeProcessor:
    """
    Handles processing detected Git changes
    """

    def __init__(self, repo: GitRepo,
                 gcp_type_queries_map: Dict[str, GcpQuery],
                 scan_interval: int,
                 service_account_regex: str,
                 tf_query: TFQuery = None,
                 ticket_regex: str = None,
                 ticket_sys_url: str = None,
                 slack_notifier: SlackNotifier = None,
                 jira_notifier: JiraNotifier = None):
        """
        :param repo: GitRepo holding configuration
        :param gcp_type_queries_map: resource name to GcpQuery mapping
        :param scan_interval: interval between each scan in minutes
        :param service_account_regex: regex used to identify Service Account changer name
        :param tf_query: Terraform connector
        :param ticket_regex: Regex to find ticket information in Terraform Run message
        :param ticket_sys_url: URL to ticketing system
        :param slack_notifier: optional posting to Slack
        """
        self.repo = repo
        self.gcp_type_queries_map = gcp_type_queries_map
        self.scan_interval = scan_interval
        self.tf_query = tf_query
        self.service_account_regex = service_account_regex
        self.ticket_regex = ticket_regex
        self.ticket_sys_url = ticket_sys_url
        self.slack_notifier = slack_notifier
        self.jira_notifier = jira_notifier

    def process_change(self, git_change: GitChange, change_time: datetime = None):
        """
        Retrieves GCP logs
        :param git_change: change detected by Git
        :param change_time: time of scan start/finish
        """
        # TODO: implement better time selection
        message = f"{git_change.resource_type.title()} updated in {git_change.project}"
        manual_change = False
        skip_process_ticket = False
        try:
            self.repo.repo.git.add(git_change.get_filename())
        except Exception as e:
            raise ChangeProcessorError(f"Issue adding file '{git_change.get_filename()}' in Git") from e
        try:
            if not self.repo.repo.index.diff("HEAD"):
                logger.info(f"Skipping non-change '{git_change.get_filename()}'")
                return
        except Exception as e:
            logger.warning(f"Issue checking branch repo HEAD. Empty repo without commit?\n{e}\n{e.__cause__}")
        if not change_time:
            change_time = datetime.utcnow()
        try:
            logging.info(f"Retrieving GCP change logs for '{git_change.get_filename()}'")
            gcp_change_logs = getChangeLogs(project=git_change.project,
                                            gcp_query=self.gcp_type_queries_map[git_change.resource_type],
                                            change_time=change_time,
                                            time_window=self.scan_interval)
        except Exception as e:
            logger.warning(f"Issue getting GCP logs for change '{git_change.get_filename()}'\n{e}\n{e.__cause__}")
            gcp_change_logs = []
        if len(gcp_change_logs) == 1:
            logger.info(f"Found Gcp change log for resource '{git_change.resource_type}' for "
                        f"project '{git_change.project}'")
        elif len(gcp_change_logs) > 1:
            # Log multiple Gcp Log entries for analyzing and improvment in future
            logger.info(f"Multiple Gcp change logs found for resource '{git_change.resource_type}' for "
                        f"project '{git_change.project}'. Log count {len(gcp_change_logs)}\n{gcp_change_logs}")
        changers = []
        for gcp_change_log in gcp_change_logs:
            if not gcp_change_log.changer:
                logger.info(f"Missing changer in GCP log for change {git_change.get_filename()}\n{gcp_change_log}")
                continue
            try:
                changer_login = gcp_change_log.changer.split("@")[0]
            except Exception as e:
                logger.warning(f"Issue retrieving changer login from {gcp_change_log.changer}")
                if gcp_change_log.changer not in changers:
                    changers.append(gcp_change_log.changer)
                    message += f"\n Change done by unknown user '{gcp_change_log.changer}'"
                continue

            if changer_login in changers:
                # Skip lookup for same changer
                logger.info(f"Skipping lookup for changer '{changer_login}'")
                continue
            else:
                changers.append(changer_login)
            if not re.match(rf"{self.service_account_regex}", gcp_change_log.changer):
                # Manual change
                git_change.manual = True
                logger.info(f"Manual change performed by '{changer_login}' detected")
                message += f"\n MANUAL change done by {changer_login}"
            else:
                message += f"\n Terraform change done by {changer_login}"
                # Process only if tf_query is set
                if self.tf_query:
                    logger.info(f"Retrieving Terraform Runs for service account '{changer_login}'")
                    try:
                        tf_runs = self.tf_query.get_runs(gcp_sa=changer_login)
                    except TFQueryError as e:
                        logger.warning(f"Issue getting terraform runs for GCP log {gcp_change_log}\n{e}\n{e.__cause__}")
                        continue
                    if not (self.ticket_regex and self.ticket_sys_url):
                        logger.info(f"Skipping ticket processing - ticket regex and/or ticketing URL not set")
                        skip_process_ticket = True
                    for tf_run in tf_runs:
                        if tf_run.status not in CHANGE_TF_RUN_STATE:
                            logger.info(f"Skipping processing non-change Terraform Run '{tf_run}")
                            continue
                        logger.info(f"Processing Terraform run: {tf_run}")
                        run_url = (f"{self.tf_query.tf_url}/app/{tf_run.org}/workspaces/{tf_run.workspace}/runs/"
                                   f"{tf_run.run_id}")
                        message += f"\n Related TF run {run_url}"
                        if not skip_process_ticket:
                            ticket_match = re.search(rf"{self.ticket_regex}", tf_run.message)
                            if ticket_match:
                                try:
                                    ticket = ticket_match.group(1)
                                except Exception as e:
                                    logger.warning(f"Issue retrieving ticket number from "
                                                   f"run '{tf_run}'\n{e}\n{e.__cause__}")
                                    continue
                                # TODO Parametrize string replacement
                                message += f"\n Related ticket {self.ticket_sys_url}/{ticket.replace('_', '-')}"
        # Add least one changer has been identified
        if changers:
            git_change.message = message
            git_change.changers = changers
        else:
            message += f"\n Unable to identify changer"
            git_change.message = message
        logger.info(f"Committing change '{git_change.get_filename()}'")
        self.repo.repo.git.commit(m=message)

        git_change.commit = self.repo.repo.heads.master.commit
        git_change.diff = self.repo.repo.git.diff("HEAD~1..HEAD")
        if self.slack_notifier:
            try:
                logger.info(f"Posting to Slack channel ID: {self.slack_notifier.channelID}")
                self.slack_notifier.post(git_change)
            except SlackNotifierError as e:
                logger.warning(f"Issue sending message to Slack\n{e}\n{e.__cause__}")
        if self.jira_notifier:
            try:
                self.jira_notifier.post(git_change)
            except JiraNotifierError as e:
                logger.warning(f"Issue creating ticket in Jira\n{e}\n{e.__cause__}")

    def process(self, git_changes: List[GitChange], change_time: datetime = None):
        """
        Process repo for changes
        :param git_changes: list of changes detected by Git
        :param change_time: time of scan start/finish
        """
        for git_change in git_changes:
            self.process_change(git_change, change_time)
        try:
            commits_ahead = self.repo.repo.iter_commits('origin/master..master')
            commit_count = sum(1 for c in commits_ahead)
        except Exception as e:
            logger.warning(f"Issue checking commit number diff in remote. "
                           f"Empty repo without commit?\n{e}\n{e.__cause__}")
            try:
                commit_count = self.repo.repo.git.rev_list("--count", "HEAD")
            except Exception as sub_e:
                logger.warning(f"Unexpected error when counting commit number\n{e}\n{e.__cause__}")
                commit_count = 1
        if commit_count:
            logger.info(f"Pushing {commit_count} commit(s) to remote")
            try:
                self.repo.repo.remotes.origin.push()
            except Exception as e:
                raise ChangeProcessorError("Issue pushing changes to remote") from e


def configure_change_processor(config: Dict[str, Any],
                               gcp_type_queries_map: Dict[str, GcpQuery],
                               repo: GitRepo,
                               slack_token: str,
                               jira_user: str,
                               jira_token: str) -> ChangeProcessor:
    """
    Builds Change from configuraiton file
    :param config: dictionary containing configuraiton
    :param gcp_type_queries_map: resource_name to GcpQuery map
    :param repo: repo where config is stored
    :param slack_token: Slack's Bot API token
    :param jira_user: Jira username for ticket creation
    :param jira_token: Jira token/pass for ticket creation
    :return: ChangeProcessor with valid configuration
    """
    if not isinstance(config, dict):
        raise ChangeProcessorError(f"Incorrect type of config element {CHANGE_PROCESSOR}. "
                                   f"Should be dict, is {type(config)}")
    if SCAN_INTERVAL not in config:
        raise ChangeProcessorError(f"Missing required parameter '{SCAN_INTERVAL}' in '{CHANGE_PROCESSOR}' section.")
    if SERVICE_ACCOUNT_REGEX not in config:
        raise ChangeProcessorError(f"Missing required parameter '{SERVICE_ACCOUNT_REGEX}'"
                                   f" in '{CHANGE_PROCESSOR}' section.")
    scan_interval = config.get(SCAN_INTERVAL)
    service_account_regex = config.get(SERVICE_ACCOUNT_REGEX)
    ticket_regex = config.get(TICKET_REGEX, None)
    ticket_sys_url = config.get(TICKET_SYS_URL, None)
    tf_query_config = config.get(TERRAFORM_SECTION, None)
    tf_query = configure_tfquery(tf_query_config)
    try:
        slack_notifier = configure_slack_notifier(config.get(SLACK_SECTION, None), slack_token)
    except SlackNotifierError as e:
        raise ChangeProcessorError(f"Issue with SlackNotifier\n{e}\n{e.__cause__}") from e
    try:
        jira_notifier = configure_jiranotifier(config.get(JIRA_SECTION, None), username=jira_user, password=jira_token)
    except JiraNotifierError as e:
        raise ChangeProcessorError(f"Issue with JiraNotifier\n{e}\n{e.__cause__}") from e
    if not isinstance(scan_interval, int):
        raise ChangeProcessorError(f"Incorrect type of config element {SCAN_INTERVAL}. "
                                   f"Should be int, is {type(scan_interval)}")
    if not isinstance(service_account_regex, str):
        raise ChangeProcessorError(f"Incorrect type of config element {SERVICE_ACCOUNT_REGEX}. "
                                   f"Should be str, is {type(service_account_regex)}")
    if not isinstance(ticket_regex, str):
        raise ChangeProcessorError(f"Incorrect type of config element {TICKET_REGEX}. "
                                   f"Should be str, is {type(ticket_regex)}")
    if not isinstance(ticket_sys_url, str):
        raise ChangeProcessorError(f"Incorrect type of config element {TICKET_SYS_URL}. "
                                   f"Should be str, is {type(ticket_sys_url)}")
    if not isinstance(gcp_type_queries_map, dict):
        raise ChangeProcessorError(f"Incorrect type of config element gcp_type_queries_map. "
                                   f"Should be dict, is {type(gcp_type_queries_map)}")
    if not isinstance(repo, GitRepo):
        raise ChangeProcessorError(f"Incorrect type of repo parameter. "
                                   f"Should be GitRepo, is {type(repo)}")
    if tf_query is not None:
        if not isinstance(tf_query, TFQuery):
            raise ChangeProcessorError(f"Incorrect type of tf_query parameter. "
                                       f"Should be TFQuery, is {type(tf_query)}")
    return ChangeProcessor(repo=repo,
                           gcp_type_queries_map=gcp_type_queries_map,
                           scan_interval=scan_interval,
                           service_account_regex=service_account_regex,
                           tf_query=tf_query,
                           ticket_regex=ticket_regex,
                           ticket_sys_url=ticket_sys_url,
                           slack_notifier=slack_notifier,
                           jira_notifier=jira_notifier)


class ChangeProcessorError(Exception):
    pass
