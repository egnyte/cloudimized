import argparse
import logging
import os
import sys

import yaml

from gcpcore.gcpservicequery import configure_services, GcpServiceQueryConfigError
from gcpcore.gcpservicequery import SERVICE_NAME, SERVICE_SECTION, VERSION, QUERIES
from gcpcore.gcpquery import configure_queries, GcpQueryArgumentError, GcpQueryError
from gcpcore.gcpquery import RESOURCE, GCP_API_CALL, RESULT_ITEMS_FIELD, ITEM_EXCLUDE_FILTER, GCP_LOG_RESOURCE_TYPE
from gitcore.repo import configure_repo, GitRepoError, GitRepoConfigError, GIT_USER, GIT_PASSWORD, GIT_SECTION
from tfcore.query import configure_tfquery, TFQueryConfigurationError, TERRAFORM_SECTION
from core.result import set_query_results_from_configuration, QueryResultError
from core.changeprocessor import configure_change_processor, ChangeProcessorError, CHANGE_PROCESSOR
from core.slacknotifier import SLACK_TOKEN

logger = logging.getLogger(__name__)

CONFIG_FILE = "config.yaml"

# Configuration file - key names
GCP_QUERIES = "queries"
DISCOVER_PROJECTS_KEY = "discover_projects"
EXCLUDED_PROJECTS_KEY = "excluded_projects"
PROJECTS_LIST_KEY = "project_list"
SCAN_INTERVAL = "scan_interval"

# DISCOVERY PROJECTS QUERY CONFIG
PROJECTS_DISCOVERY_SERVICE_NAME = "cloudresourcemanager"
PROJECTS_DISCOVERY_RESOURCE_NAME = "projects"
PROJECTS_DISCOVERY_SERVICE_CONFIG = [
    {
        SERVICE_NAME: PROJECTS_DISCOVERY_SERVICE_NAME,
        VERSION: "v1",
        QUERIES: [{
            RESOURCE: PROJECTS_DISCOVERY_RESOURCE_NAME,
            GCP_API_CALL: "projects.list",
            GCP_LOG_RESOURCE_TYPE: "N/A",
            RESULT_ITEMS_FIELD: "projects",
            ITEM_EXCLUDE_FILTER: [{
                "projectId": 'sys-[0-9]+'
            }]
        }]
    }
]


class GcpOxidizer:
    """
    GcpOxidizer main class
    """

    def __init__(self):
        (
            self.config_file,
            self.loglevel
        ) = self.parse_args()
        self.gcp_services = None
        self.gcp_type_queries_map = {}
        self.git_repo = None
        self.tf_query = None
        self.do_project_discovery = None
        self.excluded_projects = None
        self.projects = None
        self.run_results = None
        self.change_processor = None
        self.parse_config_file()

    def parse_args(self):
        parser = argparse.ArgumentParser("Runs GCP oxidizer")
        parser.add_argument("-c", "--config", default=CONFIG_FILE, help="Configuration file")
        parser.add_argument("-l", "--loglevel", default="INFO", help="Set logging level",
                            choices=["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"])
        args = parser.parse_args()
        return (
            args.config,
            args.loglevel
        )

    def parse_config_file(self) -> None:
        """
        Read in and parse configuration file
        """
        if not self.config_file:
            raise GcpOxidizerConfigException("No config file provided")
        try:
            with open(self.config_file) as fh:
                config = yaml.safe_load(fh)
        except yaml.YAMLError as e:
            raise GcpOxidizerConfigException(f"Error in yaml file format: '{self.config_file}'") from e
        except Exception as e:
            raise GcpOxidizerConfigException(f"Issue opening config file {self.config_file}") from e
        # Check if config file is not empty
        if not config:
            raise GcpOxidizerConfigException(f"Configuration file is empty: {self.config_file}")
        gcp_service_queries = config.get(SERVICE_SECTION, None)
        try:
            self.gcp_services = configure_services(gcp_service_queries)
        except GcpServiceQueryConfigError as e:
            raise GcpOxidizerConfigException(f"Error in configuration file in section: '{SERVICE_SECTION}'") from e
        try:
            for service in gcp_service_queries:
                serviceName = service[SERVICE_NAME]
                queries = configure_queries(service[GCP_QUERIES])
                self.gcp_services[serviceName].queries = queries
                self.gcp_type_queries_map.update(queries)
        except GcpQueryArgumentError as e:
            raise GcpOxidizerConfigException(f"Incorrect GCP query configuration in section: '{serviceName}'") from e
        try:
            self.run_results = set_query_results_from_configuration(self.gcp_services)
        except QueryResultError as e:
            raise GcpOxidizerConfigException(f"Error in service/query configuration") from e
        try:
            self.git_repo = configure_repo(user=os.getenv(GIT_USER),
                                           password=os.getenv(GIT_PASSWORD),
                                           config=config.get(GIT_SECTION))
        except GitRepoConfigError as e:
            raise GcpOxidizerConfigException(f"Error in Git configuration") from e
        # try:
        #     self.tf_query = configure_tfquery(config.get(TERRAFORM_SECTION))
        # except TFQueryConfigurationError as e:
        #     raise GcpOxidizerConfigException(f"Error in Terraform configuration") from e
        change_processor_config = config.get(CHANGE_PROCESSOR, None)
        if configure_change_processor is None:
            raise GcpOxidizerConfigException(f"Missing required section {CHANGE_PROCESSOR}")
        try:
            self.change_processor = configure_change_processor(config=change_processor_config,
                                                               gcp_type_queries_map=self.gcp_type_queries_map,
                                                               repo=self.git_repo,
                                                               slack_token=os.getenv(SLACK_TOKEN))
        except ChangeProcessorError as e:
            raise GcpOxidizerConfigException(f"Issue with ChangeProcessor config") from e
        #TODO Add type checking for below options
        #TODO Add config check when discovery list is disabled and project list is not provided
        self.do_project_discovery = config.get(DISCOVER_PROJECTS_KEY, "False")
        self.excluded_projects = config.get(EXCLUDED_PROJECTS_KEY, [])
        self.projects = config.get(PROJECTS_LIST_KEY, None) #TODO Add logic to detect if list is not set
        #TODO Move logging setup at the beggining
        self.set_logging(self.loglevel)

    def set_logging(self, loglevel: str):
        """
        Configures logging
        :param loglevel: logging level for script
        """
        logging.basicConfig(format='%(asctime)s : %(levelname)s : %(message)s', level=loglevel)

    def discover_projects(self) -> None:
        """
        Performs discovery of all GCP projects
        :raises Exception #TODO add exception handling in build() and execute()
        """
        logger.info(f"Performing GCP projects discovery")
        project_service = configure_services(PROJECTS_DISCOVERY_SERVICE_CONFIG)
        project_service[PROJECTS_DISCOVERY_SERVICE_NAME].queries = \
                configure_queries(PROJECTS_DISCOVERY_SERVICE_CONFIG[0][GCP_QUERIES])
        project_service[PROJECTS_DISCOVERY_SERVICE_NAME].build()
        result = project_service[PROJECTS_DISCOVERY_SERVICE_NAME].queries[PROJECTS_DISCOVERY_RESOURCE_NAME] \
            .execute(project_id=None)
        # Create list of project_id from query
        all_projects = [project["projectId"] for project in result]
        # Filter out exclude projects
        self.projects = [projectId for projectId in all_projects if projectId not in self.excluded_projects]
        logger.info(f"Discovered {len(result)} projects")

    def run_queries(self) -> None:
        """
        Execute all configured queries and gather results
        """
        for serviceName, service in self.gcp_services.items():
            try:
                logger.info(f"Connecting to Google API for service '{serviceName}'")
                service.build()
            except Exception as e:
                logger.warning(f"Issue connecting to API for service '{serviceName}'. "
                               "Skipping all its queries")
                continue
            for resource_name, query in service.queries.items():
                logger.info(f"Querying configuration for resource '{resource_name}'")
                for project_id in self.projects:
                    try:
                        result = query.execute(project_id)
                        if result is None:
                            logger.info(f"No '{resource_name}' resources found for project '{project_id}'")
                            continue
                        self.run_results.add_result(resource_name, project_id, result)
                    except GcpQueryError as e:
                        logger.warning(f"Issue when performing query for resource '{resource_name} "
                                       f"for project '{project_id}\n{e}\n{e.__cause__}")
                        #TODO: Add handling of failed queries i.e. error stats at the end

    @staticmethod
    def run():
        try:
            # Setup and parse configuraiton
            gcpoxidizer = GcpOxidizer()
        except GcpOxidizerConfigException as e:
            logger.critical(f"Error in GcpOxidizer configuration\n{e}\n{e.__cause__}")
            sys.exit(1)
        try:
            gcpoxidizer.git_repo.setup()
        except GitRepoError as e:
            logger.critical(f"Error setting up Git Repo: '{gcpoxidizer.git_repo.repo_url}'\n{e}\n{e.__cause__}")
        if gcpoxidizer.do_project_discovery:
            try:
                gcpoxidizer.discover_projects()
            except Exception as e:
                logger.critical(f"Issue during projects discovery\n{e}\n{e.__cause__}")
                sys.exit(1)
        # Clean repo
        try:
            gcpoxidizer.git_repo.clean_repo()
            pass
        except GitRepoError as e:
            logger.critical(f"Issue during Git repo preparation\n{e}\n{e.__cause__}")
            sys.exit(1)
        # Run all queries
        gcpoxidizer.run_queries()
        # Dump results to files
        try:
            gcpoxidizer.run_results.dump_results(directory=gcpoxidizer.git_repo.directory)
        except QueryResultError as e:
            logger.critical(f"Issue during dumping results to local files\n{e}\n{e.__cause__}")
        try:
            logger.info(f"Checking Git configuration files for changes")
            git_changes = gcpoxidizer.git_repo.get_changes()
        except GitRepoError as e:
            logger.critical(f"Issue verifying changes in Git Repo\n{e}\n{e.__cause__}")
        if not git_changes:
            logger.info(f"No Git configuration file changes detected")
            return
        else:
            try:
                logger.info(f"Processing {len(git_changes)} Git change(s)")
                gcpoxidizer.change_processor.process(git_changes=git_changes)
            except ChangeProcessorError as e:
                logger.critical(f"Issue processing Git changes\n{e}\n{e.__cause__}")
        logger.info("Run completed")


class GcpOxidizerException(Exception):
    pass


class GcpOxidizerConfigException(GcpOxidizerException):
    pass
