import argparse
import logging
import os
import threading

import sys
import yaml

from concurrent.futures import ThreadPoolExecutor, as_completed

from azure.identity import DefaultAzureCredential

from cloudimized.core.changeprocessor import configure_change_processor, ChangeProcessorError, CHANGE_PROCESSOR
from cloudimized.core.result import set_query_results_from_configuration, QueryResultError, GCP_KEY, AZURE_KEY
from cloudimized.core.slacknotifier import SLACK_TOKEN
from cloudimized.azurecore.azurecredential import get_azure_credential
from cloudimized.azurecore.azurequery import AZURE_QUERIES_SECTION, configure_azure_queries, AzureQuery, \
    AzureQueryArgumentError, AzureQueryError
from cloudimized.azurecore.resourcegroupsquery import RESOURCE_GROUPS_RESOURCE_NAME
from cloudimized.azurecore.subscriptionsquery import SUBSCRIPTIONS_RESOURCE_NAME
from cloudimized.gcpcore.gcpquery import RESOURCE, GCP_API_CALL, RESULT_ITEMS_FIELD, ITEM_EXCLUDE_FILTER, \
    GCP_LOG_RESOURCE_TYPE
from cloudimized.gcpcore.gcpquery import configure_queries, GcpQueryArgumentError, GcpQueryError
from cloudimized.gcpcore.gcpservicequery import SERVICE_NAME, SERVICE_SECTION, VERSION, QUERIES
from cloudimized.gcpcore.gcpservicequery import configure_services, GcpServiceQuery, GcpServiceQueryConfigError
from cloudimized.gitcore.repo import configure_repo, GitRepoError, GitRepoConfigError, GIT_USER, GIT_PASSWORD, \
    GIT_SECTION
from cloudimized.core.jiranotifier import JIRA_USR, JIRA_PSW

logger = logging.getLogger(__name__)

CONFIG_FILE = "config.yaml"
SINGLE_RUN_CONFIGS_DIR = "singlerunconfigs"

# Configuration file - key names
GCP_QUERIES = "queries"
## GCP
DISCOVER_PROJECTS_KEY = "discover_projects"
EXCLUDED_PROJECTS_KEY = "excluded_projects"
PROJECTS_LIST_KEY = "project_list"
## Azure
DISCOVER_SUBSCRIPTIONS_KEY = "discover_subscriptions"
EXCLUDED_SUBSCRIPTIONS_KEY = "excluded_subscriptions"
SUBSCRIPTIONS_LIST_KEY = "subscriptions_list"
## Other
SCAN_INTERVAL = "scan_interval"
THREAD_COUNT = "thread_count"

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


class Cloudimizer:
    """
    Cloudimizer main class
    """

    def __init__(self):
        (
            self.config_file,
            self.loglevel,
            self.arg_singlerun,
            self.arg_output,
            self.arg_list,
            self.arg_describe,
            self.arg_name,
            self.arg_provider
        ) = self.parse_args()
        self.gcp_services = None
        self.azure_queries = None
        self.gcp_type_queries_map = {}
        self.git_repo = None
        self.tf_query = None
        # GCP
        self.do_project_discovery = None
        self.excluded_projects = None
        self.projects = None
        # Azure
        self.do_subscription_discovery = None
        self.excluded_subscriptions = None
        self.subscriptions = None
        ##
        self.run_results = None
        self.change_processor = None
        self.thread_count = None
        if not self.arg_singlerun:
            self.parse_config_file()
        else:
            if self.arg_list:
                self.list_singlerun_configs()
                sys.exit(0)
            if self.arg_describe:
                self.describe_singlerun_configs(self.arg_name)
                sys.exit(0)
            self.set_single_run(resource_name=self.arg_name, provider_name=self.arg_provider)
            self.set_logging(self.loglevel)

    def parse_args(self):
        parser = argparse.ArgumentParser("Runs Cloudimizer",
                                         formatter_class=argparse.ArgumentDefaultsHelpFormatter)
        parser.add_argument("-c", "--config", default=CONFIG_FILE, help="Configuration file")
        parser.add_argument("-l", "--loglevel", default="INFO", help="Set logging level",
                            choices=["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"])
        singlerun_group = parser.add_argument_group('Single Run Mode')
        singlerun_group.add_argument("-s", "--singlerun", action="store_true", help="Scan & dump files mode")
        singlerun_group.add_argument("--list", action="store_true", help="List single run configs")
        singlerun_group.add_argument("-d", "--describe", action="store_true", help="Print single run config")
        singlerun_group.add_argument("-n", "--name", type=str, help="Name of single run config")
        singlerun_group.add_argument("-p", "--provider", choices=["gcp", "azure"],
                                     help="Cloud provider selection")
        singlerun_group.add_argument("-o", "--output", default="yaml", choices=["yaml", "csv"],
                                     help="Output file format")
        args = parser.parse_args()


        # Name has to be set if running singlerun (except listing)
        if (args.singlerun == True and args.list == False and args.name is None):
            parser.error("--name is required in singlerun mode")
        # Provided is required in singlerun mode
        if (args.singlerun == True and args.list == False and args.provider is None):
            parser.error("--provider is required in singlerun mode")
        return (
            args.config,
            args.loglevel,
            args.singlerun,
            args.output,
            args.list,
            args.describe,
            args.name,
            args.provider
        )

    def list_singlerun_configs(self):
        try:
            script_dir = os.path.dirname(__file__)
            configs_dir = os.path.abspath(f"{script_dir}/../{SINGLE_RUN_CONFIGS_DIR}")
            all_files = [f.split(".")[0] for f in os.listdir(configs_dir)
                         if os.path.isfile(os.path.join(configs_dir, f))]
            print(f"Available single run configs:\n{all_files}")
        except Exception as e:
            print(f"Issue discovering singe run configs\n{str(e)}")

    def describe_singlerun_configs(self, config_name: str):
        try:
            script_dir = os.path.dirname(__file__)
            configs_dir = f"{script_dir}/../{SINGLE_RUN_CONFIGS_DIR}"
            filename = os.path.abspath(f"{configs_dir}/{config_name}.yaml")
            print(f"Config file: {filename}\n")
            with open(filename, 'r') as fh:
                print(fh.read())
        except Exception as e:
            print(f"Issue discovering singe run configs\n{str(e)}")

    def parse_config_file(self) -> None:
        """
        Read in and parse configuration file
        """
        if not self.config_file:
            raise CloudimizerConfigException("No config file provided")
        try:
            with open(self.config_file) as fh:
                config = yaml.safe_load(fh)
        except yaml.YAMLError as e:
            raise CloudimizerConfigException(f"Error in yaml file format: '{self.config_file}'") from e
        except Exception as e:
            raise CloudimizerConfigException(f"Issue opening config file {self.config_file}") from e
        # Check if config file is not empty
        if not config:
            raise CloudimizerConfigException(f"Configuration file is empty: {self.config_file}")
        # GCP queries
        gcp_service_queries = config.get(SERVICE_SECTION, None)
        if gcp_service_queries:
            try:
                self.gcp_services = configure_services(gcp_service_queries)
            except GcpServiceQueryConfigError as e:
                raise CloudimizerConfigException(f"Error in configuration file in section: '{SERVICE_SECTION}'") from e
            try:
                for service in gcp_service_queries:
                    serviceName = service[SERVICE_NAME]
                    queries = configure_queries(service[GCP_QUERIES])
                    self.gcp_services[serviceName].queries = queries
                    self.gcp_type_queries_map.update(queries)
            except GcpQueryArgumentError as e:
                raise CloudimizerConfigException(f"Incorrect GCP query configuration in section: '{serviceName}'") from e
        # Azure queries
        azure_queries = config.get(AZURE_QUERIES_SECTION, None)
        if azure_queries:
            try:
                self.azure_queries = configure_azure_queries(azure_queries)
            except AzureQueryArgumentError as e:
                raise CloudimizerConfigException(f"Error in configuration file in section: '{AZURE_QUERIES_SECTION}") \
                    from e
        try:
            self.run_results = set_query_results_from_configuration(self.gcp_services, self.azure_queries)
        except QueryResultError as e:
            raise CloudimizerConfigException(f"Error in service/query configuration") from e
        try:
            self.git_repo = configure_repo(user=os.getenv(GIT_USER),
                                           password=os.getenv(GIT_PASSWORD),
                                           config=config.get(GIT_SECTION))
        except GitRepoConfigError as e:
            raise CloudimizerConfigException(f"Error in Git configuration") from e
        # try:
        #     self.tf_query = configure_tfquery(config.get(TERRAFORM_SECTION))
        # except TFQueryConfigurationError as e:
        #     raise GcpOxidizerConfigException(f"Error in Terraform configuration") from e
        change_processor_config = config.get(CHANGE_PROCESSOR, None)
        if configure_change_processor is None:
            raise CloudimizerConfigException(f"Missing required section {CHANGE_PROCESSOR}")
        try:
            self.change_processor = configure_change_processor(config=change_processor_config,
                                                               gcp_type_queries_map=self.gcp_type_queries_map,
                                                               repo=self.git_repo,
                                                               slack_token=os.getenv(SLACK_TOKEN),
                                                               jira_user=os.getenv(JIRA_USR),
                                                               jira_token=os.getenv(JIRA_PSW))
        except ChangeProcessorError as e:
            raise CloudimizerConfigException(f"Issue with ChangeProcessor config") from e
        # TODO Add type checking for below options
        # TODO Add config check when discovery list is disabled and project list is not provided
        # GCP
        self.do_project_discovery = config.get(DISCOVER_PROJECTS_KEY, "False")
        self.excluded_projects = config.get(EXCLUDED_PROJECTS_KEY, [])
        self.projects = config.get(PROJECTS_LIST_KEY, None)  # TODO Add logic to detect if list is not set
        # Azure
        self.do_subscription_discovery = config.get(DISCOVER_SUBSCRIPTIONS_KEY, "False")
        self.excluded_subscriptions = config.get(EXCLUDED_SUBSCRIPTIONS_KEY, [])
        self.subscriptions = config.get(SUBSCRIPTIONS_LIST_KEY, None) # TODO Add logic to detect if list is not set
        ##
        self.thread_count = config.get(THREAD_COUNT, 3)
        # TODO Move logging setup at the beggining
        self.set_logging(self.loglevel)

    def set_single_run(self, resource_name: str, provider_name: str):
        """
        Prepare configuration for single run mode
        :param resource_name: GCP resource name to scan
        """
        try:
            script_dir = os.path.dirname(__file__)
            filename = f"{script_dir}/../{SINGLE_RUN_CONFIGS_DIR}/{provider_name}/{resource_name}.yaml"
            with open(filename) as fh:
                service = yaml.safe_load(fh)
        except yaml.YAMLError as e:
            raise CloudimizerConfigException(f"Error opening yaml file: '{filename}'") from e
        if provider_name == "gcp":
            try:
                self.gcp_services = configure_services([service])
            except GcpServiceQueryConfigError as e:
                raise CloudimizerConfigException(f"Error in service config in file: '{filename}'") from e
            try:
                serviceName = service[SERVICE_NAME]
                queries = configure_queries(service[GCP_QUERIES])
                self.gcp_services[serviceName].queries = queries
                self.gcp_type_queries_map.update(queries)
            except GcpQueryArgumentError as e:
                raise CloudimizerConfigException(f"Error in query config in file: '{filename}'") from e
        elif provider_name == "azure":
            try:
                self.azure_queries = configure_azure_queries([service])
            except AzureQueryArgumentError as e:
                raise CloudimizerConfigException(f"Error in service config in file: '{filename}'") from e
        else:
            raise CloudimizerConfigException(f"Unknown provider: {provider_name}")
        try:
            self.run_results = set_query_results_from_configuration(self.gcp_services, self.azure_queries)
        except QueryResultError as e:
            raise CloudimizerConfigException(f"Error in service/query configuration") from e
        self.excluded_projects = []


    def set_logging(self, loglevel: str):
        """
        Configures logging
        :param loglevel: logging level for script
        """
        logging.basicConfig(format='%(asctime)s : %(levelname)s : %(message)s', level=loglevel)

    #For GCP projects discovery
    def discover_projects(self) -> None:
        """
        Performs discovery of all GCP projects
        :raises Exception #TODO add exception handling in build() and execute()
        """
        logger.info(f"Performing GCP projects discovery")
        project_service = configure_services(PROJECTS_DISCOVERY_SERVICE_CONFIG)
        project_service[PROJECTS_DISCOVERY_SERVICE_NAME].queries = \
            configure_queries(PROJECTS_DISCOVERY_SERVICE_CONFIG[0][GCP_QUERIES])
        service = project_service[PROJECTS_DISCOVERY_SERVICE_NAME].build()
        result = project_service[PROJECTS_DISCOVERY_SERVICE_NAME].queries[PROJECTS_DISCOVERY_RESOURCE_NAME] \
            .execute(service=service, project_id=None)
        # Create list of project_id from query
        all_projects = [project["projectId"] for project in result]
        # Filter out exclude projects
        self.projects = [projectId for projectId in all_projects if projectId not in self.excluded_projects]
        logger.info(f"Discovered {len(result)} projects")

    #For Azure subscriptions discovery
    def discover_azure(self) -> None:
        """
        Performs discovery of all available subscriptions IDs
        """
        self.subscriptions = {}
        logger.info(f"Performing Azure subscriptions discovery")
        credentials = get_azure_credential()
        query = AzureQuery.create(resource_name=SUBSCRIPTIONS_RESOURCE_NAME)
        raw_result = query.execute(credentials=credentials,
                                   subscription_id=None,
                                   resource_groups=None)
        subscription_ids = [subscription['subscription_id'] for subscription in raw_result]
        logger.info(f"Discovered {len(subscription_ids)} Azure subscriptions. Discovering resource groups")
        query = AzureQuery.create(resource_name=RESOURCE_GROUPS_RESOURCE_NAME)
        for sub_id in subscription_ids:
            raw_result = query.execute(credentials=credentials,
                                       subscription_id=sub_id,
                                       resource_groups=None)
            resource_groups = [resource_group['name'] for resource_group in raw_result]
            #Add only non-empty subscriptions
            logger.info(f"Discovered {len(resource_groups)} ResourceGroups in Subscription {sub_id}")
            if resource_groups:
                self.subscriptions[sub_id] = resource_groups


    def run_queries(self) -> None:
        """
        Execute all configured queries and gather results
        """
        # Create per-thread local storage
        local = threading.local()
        for serviceName, service in self.gcp_services.items():
            with ThreadPoolExecutor(max_workers=self.thread_count, initializer=initializer_worker,
                                    initargs=(local, service)) as executor:
                for resource_name, query in service.queries.items():
                    logger.info(f"Querying configuration for resource '{resource_name}'")
                    futures = []
                    for project_id in self.projects:
                        future = executor.submit(query_task, query.execute, project_id, local)
                        future.project_id = project_id
                        futures.append(future)
                    for future in as_completed(futures):
                        try:
                            result = future.result()
                            if len(result) == 0:
                                logger.info(f"No '{resource_name}' resources found for project '{future.project_id}'")
                                continue
                            self.run_results.add_result(resource_name=resource_name,
                                                        provider=GCP_KEY,
                                                        target_id=future.project_id,
                                                        result=result)
                        except GcpQueryError as e:
                            logger.warning(f"Issue when performing query for resource '{resource_name} "
                                           f"for project '{future.project_id}\n{e}\n{e.__cause__}")
                            #TODO: Add handling of failed queries i.e. error stats at the end

    def run_azure_queries(self) -> None:
        """
        Execute all configured Azure queries and gather results
        """
        local = threading.local()
        with ThreadPoolExecutor(max_workers=self.thread_count, initializer=initializer_azure_worker,
                                initargs=(local,)) as executor:
            for resource_name, query in self.azure_queries.items():
                logger.info(f"Querying configuration for resource '{resource_name}'")
                futures = []
                for subscription_id, resource_groups in self.subscriptions.items():
                    future = executor.submit(query_azure_task, query.execute, subscription_id, resource_groups, local)
                    future.subscription_id = subscription_id
                    futures.append(future)
                for future in as_completed(futures):
                    try:
                        result = future.result()
                        if len(result) == 0:
                            logger.info(f"No '{resource_name}' resources found for subscription '{future.subscription_id}'")
                            continue
                        self.run_results.add_result(resource_name=resource_name,
                                                    provider=AZURE_KEY,
                                                    target_id=future.subscription_id,
                                                    result=result)
                    except AzureQueryError as e:
                        logger.warning(f"Issue when performing query for resource '{resource_name} "
                                       f"for subscription '{future.subscription_id}\n{e}\n{e.__cause__}")
                        # TODO: Add handling of failed queries i.e. error stats at the end

    def singlerun_mode(self):
        if self.arg_provider == "gcp":
            # Discover all projects
            try:
                self.discover_projects()
            except Exception as e:
                logger.critical(f"Issue during projects discovery\n{e}\n{e.__cause__}")
                sys.exit(1)
            self.run_queries()
        elif self.arg_provider == "azure":
            #Discover all subscriptions
            try:
                self.discover_azure()
            except Exception as e:
                logger.critical(f"Issue during subscriptions discovery\n{e}\n{e.__cause__}")
                sys.exit(1)
            self.run_azure_queries()
        # Dump results to files
        try:
            if self.arg_output == "csv":
                self.run_results.dump_results_csv(directory=".")
            elif self.arg_output == "yaml":
                self.run_results.dump_results(directory=".")
        except QueryResultError as e:
            logger.critical(f"Issue during dumping results to local files\n{e}\n{e.__cause__}")

    def main_mode(self):
        try:
            self.git_repo.setup()
        except GitRepoError as e:
            logger.critical(f"Error setting up Git Repo: '{self.git_repo.repo_url}'\n{e}\n{e.__cause__}")
        # GCP
        if self.do_project_discovery:
            try:
                self.discover_projects()
            except Exception as e:
                logger.critical(f"Issue during GCP projects discovery\n{e}\n{e.__cause__}")
                sys.exit(1)
        # Azure
        if self.do_subscription_discovery:
            try:
                self.discover_azure()
            except Exception as e:
                logger.critical(f"Issue during Azure subscriptions discovery\n{e}\n{e.__cause__}")
                sys.exit(1)
        # Clean repo
        try:
            self.git_repo.clean_repo()
            pass
        except GitRepoError as e:
            logger.critical(f"Issue during Git repo preparation\n{e}\n{e.__cause__}")
            sys.exit(1)
        # Run all queries
        ## GCP
        if self.gcp_services:
            logger.info(f"Running all GCP queries")
            self.run_queries()
        ## Azure
        if self.azure_queries:
            logger.info(f"Running all Azure queries")
            self.run_azure_queries()
        # Dump results to files
        try:
            self.run_results.dump_results(directory=self.git_repo.directory)
        except QueryResultError as e:
            logger.critical(f"Issue during dumping results to local files\n{e}\n{e.__cause__}")
        try:
            logger.info(f"Checking Git configuration files for changes")
            git_changes = self.git_repo.get_changes()
        except GitRepoError as e:
            logger.critical(f"Issue verifying changes in Git Repo\n{e}\n{e.__cause__}")
        if not git_changes:
            logger.info(f"No Git configuration file changes detected")
            return
        else:
            try:
                logger.info(f"Processing {len(git_changes)} Git change(s)")
                self.change_processor.process(git_changes=git_changes)
            except ChangeProcessorError as e:
                logger.critical(f"Issue processing Git changes\n{e}\n{e.__cause__}")
        logger.info("Run completed")


def initializer_worker(local, service: GcpServiceQuery):
    """
    Initializer function for Query execute threads
    :param local: theading.local() instance
    :param service: GCP service instance
    """
    logger.info(f"Creating GCP service object {service.serviceName} for thread {threading.get_ident()}")
    try:
        local.service = service.build()
    except Exception as e:
        logger.warning(f"Issue building service {service.serviceName}\n{e}\n{e.__cause__}")

def initializer_azure_worker(local):
    """
    Initializer function for Query execute threads
    :param local: theading.local() instance
    """
    logger.info(f"Creating Azure credentials object for thread {threading.get_ident()}")
    try:
        local.credential = get_azure_credential()
    except Exception as e:
        logger.warning(f"Issue getting Azure credentials\n{e}\n{e.__cause__}")


def query_task(query_function, project_id, local):
    """
    Wrapper for query function for multithreading
    :param query_function: query execute function
    :param project_id: GCP project ID to scan
    :param local: thread local variable
    """
    return query_function(local.service, project_id)


def query_azure_task(query_function, subscription_id, resource_groups, local):
    """
    Wrapper for query function for multithreading
    :param query_function: query execute function
    :param subscription_id: Azure subscription ID to scan
    :param resource_groups: list of Azure Resource Groups in given subscription
    :param local: thread local variable
    """
    return query_function(local.credential, subscription_id, resource_groups)


def execute():
    try:
        # Setup and parse configuraiton
        cloudimizer = Cloudimizer()
    except CloudimizerConfigException as e:
        logger.critical(f"Error in Cloudimizer configuration\n{e}\n{e.__cause__}")
        sys.exit(1)
    if not cloudimizer.arg_singlerun:
        logger.info("Running in main mode")
        cloudimizer.main_mode()
    else:
        logger.info("Running in single run mode")
        cloudimizer.singlerun_mode()


class CloudimizerException(Exception):
    pass


class CloudimizerConfigException(CloudimizerException):
    pass
