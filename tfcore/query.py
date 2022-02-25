import json
import logging

from os import getenv
from typing import Dict, List
from datetime import datetime, timedelta
from terrasnek.api import TFC
from .run import TFRun, parse_tf_runs

logger = logging.getLogger(__name__)

ORG = 'org'
WORKSPACE = 'workspace'

TERRAFORM_SECTION = 'terraform'
TERRAFORM_URL = 'url'
TERRAFORM_SERVICE_ACCOUNT_WORKSPACE_MAP = 'service_workspace_map'
TERRAFORM_WORKSPACE_TOKEN_FILE = 'workspace_token_file'
ENV_TERRAFORM_WORKSPACE_TOKEN_FILE = "TERRAFORM_READ_TOKENS"

class TFQuery:
    """
    Query for terraform runs generating changes
    """

    # TODO: add checking of map format
    def __init__(self, tf_url: str, sa_org_workspace_map: Dict[str, Dict[str, str]], org_token_map: Dict[str, str]):
        """
        :param tf_url: Terraform instance URL
        :param sa_org_workspace_map: Map of GCP Service Account to TF organization/workspace
        :param org_token_map: Map of TF organization to TF team token
        """
        self.tf_url = tf_url
        self.sa_org_workspace_map = sa_org_workspace_map
        self.org_token_map = org_token_map

    def __get_api(self, gcp_sa: str) -> TFC:
        """
        Connect to TF API object for GCP Service account
        :param gcp_sa: GCP Service Account which performed change
        :raises TFQueryError
        :return: Terraform API object
        """
        if gcp_sa not in self.sa_org_workspace_map:
            raise TFQueryError(f"Unknown GCP ServiceAccount {gcp_sa}")
        tf_org = self.sa_org_workspace_map[gcp_sa][ORG]
        tf_token = self.org_token_map[tf_org]
        tf_api = TFC(tf_token, url=self.tf_url)
        tf_api.set_org(tf_org)
        return tf_api

    def get_runs(self, gcp_sa: str,
                 run_limit: int = 10,
                 change_time: datetime = None,
                 time_window: int = 30) -> List[TFRun]:
        """
        Get TF runs for given GCP Service account at given point in time
        :param gcp_sa: GCP Service Account which performed change
        :param run_limit: Number of TF run limits to get
        :param change_time: point in time from which to look for change
        :param time_window: size of time window to look for change (in minutes)
        :return:
        """
        logger.info(f"Getting TF {run_limit} last runs for workspace connected {gcp_sa}")
        tf_api = self.__get_api(gcp_sa)
        tf_workspace_names = self.sa_org_workspace_map[gcp_sa][WORKSPACE]
        tf_runs = []
        for workspace in tf_workspace_names:
            try:
                logger.info(f"Getting workspace_id for workspace name {workspace}")
                workspace_response = tf_api.workspaces.show(workspace_name=workspace)
                tf_workspace_id = workspace_response["data"]["id"]
            except Exception as e:
                raise TFQueryError(f"Issue getting workspace ID for workspace {workspace}") from e
            try:
                logger.info(f"Getting {run_limit} TF runs for workspace ID {tf_workspace_id}")
                runs_response = tf_api.runs.list(tf_workspace_id, page_size=run_limit, include=["created-by"])
                tf_runs += parse_tf_runs(runs_response, tf_api.get_org(), workspace)
            except Exception as e:
                raise TFQueryError(f"Issue getting terraform runs") from e
        if not change_time:
            change_time = datetime.utcnow()
        start_time = (change_time - timedelta(minutes=time_window))
        tf_runs = [tf_run for tf_run in tf_runs if tf_run.apply_time >= start_time]
        return tf_runs


def configure_tfquery(config: Dict) -> TFQuery:
    """
    Generates TFQuery based from configuraiton file
    :param config: configuration
    :return: TFQuery object with parsed config
    """
    #TODO Add handling of raised exception
    if config is None:
        logger.info("No terraform configuration found. Skipping TF querying for additional info")
        return None
    if not isinstance(config, dict):
        raise TFQueryConfigurationError(f"Incorrect configuration type. Should be dict is {type(config)}")
    if TERRAFORM_URL not in config:
        raise TFQueryConfigurationError(f"Missing required key: {TERRAFORM_URL}")
    if TERRAFORM_SERVICE_ACCOUNT_WORKSPACE_MAP not in config:
        raise TFQueryConfigurationError(f"Missing required key: {TERRAFORM_SERVICE_ACCOUNT_WORKSPACE_MAP}")

    # Verify url
    url = config[TERRAFORM_URL]
    if not isinstance(url, str):
        raise TFQueryConfigurationError(f"Incorrect value for {TERRAFORM_URL}. Should be str is {type(url)}")

    # Verify service account workspace mapping structure
    sa_workspace_map = config[TERRAFORM_SERVICE_ACCOUNT_WORKSPACE_MAP]
    if not isinstance(sa_workspace_map, dict):
        raise TFQueryConfigurationError(f"Incorrect configuration type in {TERRAFORM_SERVICE_ACCOUNT_WORKSPACE_MAP}. "
                                        f"Should be dict is {type(sa_workspace_map)}")
    for key, value in sa_workspace_map.items():
        if not isinstance(key, str):
            raise TFQueryConfigurationError(f"Incorrect entry type for {key}. Should be str is {type(key)}")
        if not isinstance(value, dict):
            raise TFQueryConfigurationError(f"Incorrect entry type for {value}. Should be dict in {type(key)}")
        if ORG not in value or WORKSPACE not in value:
            raise TFQueryConfigurationError(f"Missing one of required keys: {ORG}, {WORKSPACE} "
                                            f"in {key}")
        if not isinstance(value[ORG], str):
            raise TFQueryConfigurationError(f"Incorrect value type for {key} {ORG}. "
                                            f"Should be str is {type(value[ORG])}")
        if not isinstance(value[WORKSPACE], list):
            raise TFQueryConfigurationError(f"Incorrect value type for {key} {WORKSPACE}. "
                                            f"Should be list is {type(value[WORKSPACE])}")

    # Verify token file
    token_file = config.get(TERRAFORM_WORKSPACE_TOKEN_FILE, getenv(ENV_TERRAFORM_WORKSPACE_TOKEN_FILE))
    if token_file is None:
        raise TFQueryConfigurationError(f"No token file specified in configuration file and no "
                                        f"env var set with file location")
    if not isinstance(token_file, str):
        raise TFQueryConfigurationError(f"Incorrect value for {TERRAFORM_WORKSPACE_TOKEN_FILE}. "
                                        f"Should be str, is {type(token_file)}")
    try:
        with open(token_file) as fh:
            token_map = json.load(fh)
    except Exception as e:
        raise TFQueryConfigurationError(f"Issue opening token file {TERRAFORM_WORKSPACE_TOKEN_FILE}") from e

    if not isinstance(token_map, dict):
        raise TFQueryConfigurationError(f"Incorrect token file configuration {TERRAFORM_WORKSPACE_TOKEN_FILE} "
                                        f"Should be dict is {type(token_map)}")
    for key, value in token_map.items():
        if not isinstance(key, str):
            raise TFQueryConfigurationError(f"Incorrect configuration in token file. Workspace names should be string")
        if not isinstance(value, str):
            raise TFQueryConfigurationError(f"Incorrect configuration in token file. Tokens should be string")

    return TFQuery(tf_url=url, sa_org_workspace_map=sa_workspace_map, org_token_map=token_map)


class TFQueryError(Exception):
    pass


class TFQueryConfigurationError(TFQueryError):
    pass
