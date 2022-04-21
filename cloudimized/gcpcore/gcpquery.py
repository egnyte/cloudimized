import logging
import re
from typing import Callable, Any, Dict, List, Union
from copy import deepcopy
from itertools import filterfalse
from functools import reduce
from operator import methodcaller, itemgetter

from googleapiclient.discovery import Resource

logger = logging.getLogger(__name__)

RESOURCE = "resource"
GCP_API_CALL = "gcp_api_call"
GCP_LOG_RESOURCE_TYPE = "gcp_log_resource_type"
RESULT_ITEMS_FIELD = "items"
DEFAULT_RESULT_ITEMS_FILED = "items"
ITEM_EXCLUDE_FILTER = "item_exclude_filter"
NUM_RETRIES = "num_retries"

DEFAULT_NUM_RETRIES = 3

AGGREGATED_LIST = "aggregatedList"
SORT_KEY = "name"

class GcpQuery:
    """A class for sending list query to GCP"""

    def __init__(self, resource_name: str,
                 api_call: str,
                 gcp_log_resource_type: str,
                 result_items_field: str,
                 field_exclude_filter: List = None,
                 field_include_filter: List = None,
                 item_exclude_filter: List[Dict[str, str]] = None,
                 num_retries: int = 3,
                 **kwargs):
        """
        :param resource_name: user-friendly name to describe queried resource
        :param api_call: GCP function call to run on service
        :param gcp_log_resource_type: resource type in GCP Log Explorer associated with resource_name
        :param result_item_field: key name for items queried in GCP response
        :param field_exclude_filter: fields to be excluded from each item
        :param field_include_filter: fields to keep for each item
        :param item_exclude_filter: regex rules to use for filtering whole items
        :param num_retries: number of retry attempts for API calls
        :param kwargs: kwargs to pass into gcp function
        """
        if field_include_filter and field_exclude_filter:
            raise GcpQueryArgumentError(f"Issue for resource_name {resource_name} field_include_filter and "
                                        f"field_exclude_filter are mutually exclusive")
        self.resource_name = resource_name
        self.api_call = api_call
        self.gcp_log_resource_type = gcp_log_resource_type
        self.result_items_field = result_items_field
        self.result_exclude_filter = field_exclude_filter
        self.result_include_filter = field_include_filter
        self.result_item_filter = item_exclude_filter
        self.num_retries = num_retries
        self.kwargs = kwargs

    def execute(self, service: Resource, project_id: str) -> List[Dict]:
        """
        Sends GCP query that lists resources in project. keyword_arguments should contain project_id entry
        where string <PROJECT_ID> will be substituted with project_id
        :param service: GCP Resource object used to send query
        :param project_id: GCP project ID to query
        :return: List of resources that were queried
        """
        if service is None:
            raise GcpQueryError(f"Service not set for '{self.resource_name}'")
        logger.info(f"Running query for '{self.resource_name}' in project '{project_id}'")
        # Replace <PROJECT_ID> in kwargs with actual project_id
        query_kwargs = deepcopy(self.kwargs)
        # Perform only if project_id is set
        ## Don't replace for queries that don't use project_id
        if project_id:
            for k, v in self.kwargs.items():
                if isinstance(v, str):
                    query_kwargs[k] = v.replace("<PROJECT_ID>", project_id)
                    logger.debug(f"Replacing <PROJECT_ID> string in param_name: {k}, param_value: {v} "
                                 f"with string {project_id}")
        try:
            # Build function call for resource
            # i.e. run service.projects().list()
            ## Run query without last call i.e. service.projects()
            logger.debug(f"Query GCP Resource object: {service}\n"
                         f"Query API call: {self.api_call}")
            api_last_call_method = self.api_call.split(".")[-1]
            query_base = reduce(lambda x, y: methodcaller(y)(x), self.api_call.split(".")[:-1], service)
            logger.debug(f"Query base for API call: {query_base}\nAPI call kwargs: {query_kwargs}")
            # Run last call on service with arguments if present i.e. (service.projects()).list()
            request = methodcaller(api_last_call_method, **query_kwargs)(query_base)
            logger.debug(f"API call request object: {request}")
            response = request.execute(num_retries=self.num_retries)
            logger.debug(f"API call response object: {response}")
        except Exception as e:
            raise GcpQueryError(f"Issue executing call '{self.api_call}' with args '{self.kwargs}'") from e
        result = response.get(self.result_items_field, None)
        # Separate handling for aggregatedList call
        if api_last_call_method == AGGREGATED_LIST:
            result = self._parse_aggregated_list(result)
        if not result:
            return result
        # Sort result list to get predictable results
        # Results from kubernetes cluster list call return non-consistent list order
        # Perform sorting based on "name" key if present
        try:
            result.sort(key=itemgetter(SORT_KEY))
        except Exception as e:
            logger.warning(f"Skipping result sorting for API call '{self.api_call}' for project '{project_id}'. "
                           f"Missing default sort key in result '{SORT_KEY}'")
            logger.debug(f"Reason: {e}")
        if self.result_item_filter:
            for filter_condition_set in self.result_item_filter:
                result[:] = [i for i in result if self.__filter_item(i, filter_condition_set)]
        if self.result_exclude_filter:
            return self.__filter_field_exclude(self.result_exclude_filter, result)
        elif self.result_include_filter:
            return self._filter_result_include(result)
        else:
            return result

    def __filter_field_exclude(self, fields: List[Union[str, Dict]], result: List[Dict]) -> List[Dict]:
        filtered_result = result[:]
        for field in fields:
            if isinstance(field, str):
                for item in filtered_result:
                    item.pop(field, None)
            elif isinstance(field, dict):
                for item in filtered_result:
                    for nested_key, nested_fields in field.items():
                        nested_result = item.get(nested_key, {})
                        if isinstance(nested_result, dict):
                            self.__filter_field_exclude(fields=nested_fields, result=[nested_result])
                        if isinstance(nested_result, list):
                            self.__filter_field_exclude(fields=nested_fields, result=nested_result)
        return filtered_result

    def _filter_result_include(self, result: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter out all fields except ones specified from each item in results"""
        filtered_result = []
        for item in result:
            filtered_item = {key: item[key] for key in item if key in self.result_include_filter}
            filtered_result.append(filtered_item)
        return filtered_result

    def __filter_item(self, item: Dict[str, Any], filter_condition_set) -> bool:
        for filter_field, filter_condition in filter_condition_set.items():
            if isinstance(filter_condition, str):
                field_value = item.get(filter_field, "")
                if isinstance(field_value, list):
                    field_value[:] = [i for i in field_value if not re.match(rf"{filter_condition}", i)]
                    break
                elif isinstance(field_value, str):
                    if not re.match(rf"{filter_condition}", field_value):
                        break
            elif isinstance(filter_condition, dict):
                nested_result = item.get(filter_field, None)
                if nested_result is None:
                    break
                if isinstance(nested_result, dict):
                    return self.__filter_item(nested_result, filter_condition)
                elif isinstance(nested_result, list):
                    nested_result[:] = [i for i in nested_result if self.__filter_item(i, filter_condition)]
                    break
        else:
            # If all condition match filter item out
            return False
        # If there was a break don't filter item out
        return True

    def _parse_aggregated_list(self, api_call_result: Dict[str, Dict]) -> List[Dict]:
        """
        Parses response from aggregatedList API call into format common to other calls
        :param api_call_result: aggregatedList call response
        :return: parsed result in common format
        """
        result = []
        if not isinstance(api_call_result, dict):
            raise GcpQueryError(f"Incorrect result type for aggregatedList parsing. Is {type(api_call_result)}, "
                                f"should be dict")
        try:
            logger.debug(f"Retrieving resource name from API call definition: {self.api_call}")
            api_result_resource_name = self.api_call.split(".")[-2]
            logger.debug(f"Using resource name: {api_result_resource_name} for retrieving "
                         f"results from aggregatedList call")
        except Exception as e:
            raise GcpQueryError(f"Issue retrieving resource name from aggregatedList API call {self.api_call}") from e
        try:
            for region, region_response in api_call_result.items():
                if api_result_resource_name in region_response:
                    logger.debug(f"Found resource '{api_result_resource_name}' in region '{region}'")
                    result.extend(region_response[api_result_resource_name])
        except Exception as e:
            raise GcpQueryError(f"Issue processing api_call_result") from e
        # Return None to make it compatible with normal queries
        if not result:
            return None
        else:
            return result


def configure_queries(queries: List[Dict[str, Any]]) -> Dict[str, GcpQuery]:
    """
    Configures GCP queries objects from configuration
    :param queries: per service query configuration
    :returns resource name to GCPQuery object mapping
    """
    if not isinstance(queries, list):
        raise GcpQueryArgumentError(f"Incorrect GCP queries configuration. Should be list, is {type(queries)}")
    #TODO better configuraiton file verification
    result = {}
    for query in queries:
        if RESOURCE not in query or GCP_API_CALL not in query:
            raise GcpQueryArgumentError(f"Missing required key in query: '{query}'")
        if GCP_LOG_RESOURCE_TYPE not in query:
            raise GcpQueryArgumentError(f"Missing required key: '{GCP_LOG_RESOURCE_TYPE}' "
                                        f"in query configuration '{query}'")
        if ITEM_EXCLUDE_FILTER in query:
            item_exclude_filter = query[ITEM_EXCLUDE_FILTER]
            if not isinstance(item_exclude_filter, list):
                raise GcpQueryArgumentError(f"Incorrect GCP query configuration. Item exclude filter should be list, "
                                            f"is {type(item_exclude_filter)}")
        num_retries = query.get(NUM_RETRIES, DEFAULT_NUM_RETRIES)
        try:
            # Create kwargs from only keyword arguments
            ## Skip gcp query kwargs and pass everything else to api call
            kwargs = dict(filterfalse(lambda x: x[0] not in set([
                "field_exclude_filter", "field_include_filter", "item_exclude_filter", "result_items_field"]),
                                      query.items()))
            if "gcp_function_args" in query:
                kwargs = {**kwargs, **query["gcp_function_args"]}
            results_items_field = query.get(RESULT_ITEMS_FIELD, DEFAULT_RESULT_ITEMS_FILED)
            result[query[RESOURCE]] = GcpQuery(resource_name=query[RESOURCE],
                                               api_call=query[GCP_API_CALL],
                                               gcp_log_resource_type=query[GCP_LOG_RESOURCE_TYPE],
                                               result_items_field=results_items_field,
                                               num_retries=num_retries,
                                               **kwargs)
        except Exception as e:
            raise GcpQueryArgumentError(f"Issue parsing query config {query}") from e
    return result


class GcpQueryError(Exception):
    pass


class GcpQueryArgumentError(GcpQueryError):
    pass
