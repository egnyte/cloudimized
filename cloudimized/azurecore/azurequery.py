import logging
import os
import re
import importlib.util
import sys
from typing import Any, Dict, List, Union
from abc import ABC, abstractmethod
from itertools import filterfalse
from operator import itemgetter
from azure.identity import DefaultAzureCredential

logger = logging.getLogger(__name__)

AZURE_QUERIES_SECTION = "azure_queries"
RESOURCE = "resource"
ITEM_EXCLUDE_FILTER = "item_exclude_filter"
NUM_RETRIES = "num_retries"
SORT_FIELDS = "sortFields"

DEFAULT_NUM_RETRIES = 3

AGGREGATED_LIST = "aggregatedList"
DEFAULT_SORT_FIELDS = ["name"]

class AzureQuery(ABC):
    """A class for sending queries to Azure"""

    #Registry of implementation classes
    _registry = {}

    def __init__(self, resource_name: str,
                 field_exclude_filter: List = None,
                 field_include_filter: List = None,
                 item_exclude_filter: List[Dict[str, str]] = None,
                 num_retries: int = 3,
                 sort_fields: List = DEFAULT_SORT_FIELDS,
                 **kwargs):
        """
        :param resource_name: user-friendly name to describe queried
        :param field_exclude_filter: fields to be excluded from each item
        :param field_include_filter: fields to keep for each item
        :param item_exclude_filter: regex rules to use for filtering whole items
        :param num_retries: number of retry attempts for API calls
        :param sort_fields: results sorting fields
        :param kwargs: kwargs to pass into azure function
        """
        if field_include_filter and field_exclude_filter:
            raise AzureQueryArgumentError(f"Issue for resource_name {resource_name} field_include_filter and "
                                        f"field_exclude_filter are mutually exclusive")
        self.resource_name = resource_name
        self.result_exclude_filter = field_exclude_filter
        self.result_include_filter = field_include_filter
        self.result_item_filter = item_exclude_filter
        self.num_retries = num_retries
        self.sort_fields = sort_fields
        self.kwargs = kwargs

    @classmethod
    def register_class(cls, resource_name):
        def decorator(subclass):
            cls._registry[resource_name] = subclass
            return subclass
        return decorator

    @classmethod
    def create(cls, resource_name, *args, **kwargs):
        if resource_name not in cls._registry:
            raise ValueError(f"Class '{resource_name}' is not registered")
        return cls._registry[resource_name](resource_name, *args, **kwargs)

    def execute(self,
                credentials: DefaultAzureCredential,
                subscription_id: str,
                resource_groups: List[str]) -> List[Dict]:
        """
        Sends Azure query that lists virtualProjects in subscription in project.
        :param credentials: Azure credential object
        :param subscription_id: Azure subscription ID to query
        :param resource_groups: list of Rescource Group names
        :return: List of resources that were queried
        """
        logger.info(f"Running query for '{self.resource_name}' in subscription '{subscription_id}'")
        try:
            raw_result = self.__send_query(credentials, subscription_id, resource_groups)
        except Exception as e:
            raise AzureQueryError(f"Issue executing call '{self.resource_name}'") from e
        try:
            #Most responses from Azure will implement as_dict() to serialize those objects
            result = [item.as_dict() for item in raw_result]
        except Exception as e:
            raise AzureQueryError(f"Issue serializing response from call '{self.resource_name} ") from e
        # Sort result list to get predictable results
        # Perform sorting based on "name" key if present
        self.__sort_result(result, subscription_id)
        if self.result_item_filter:
            for filter_condition_set in self.result_item_filter:
                result[:] = [i for i in result if self.__filter_item(i, filter_condition_set)]
        if self.result_exclude_filter:
            return self.__filter_field_exclude(self.result_exclude_filter, result)
        elif self.result_include_filter:
            return self._filter_field_include(self.result_include_filter, result)
        else:
            return result


    @abstractmethod
    def __send_query(self, subscription_id: str):
        pass


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

    def _filter_field_include(self, fields: List[Union[str, Dict]], result: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filter out all fields except ones specified from each item in results
        """
        def filter_dict(entry, filters):
            filtered_entry = {}
            for key, value in entry.items():
                if isinstance(value, dict):
                    if key in filters:
                        if not filters[key]:  # Include the entire nested dictionary
                            filtered_entry[key] = filter_dict(value, {})
                        else:
                            filtered_entry[key] = filter_dict(value, filters[key])
                elif key in filters or not filters:  # Include the field if it's in filters or filters are empty
                    filtered_entry[key] = value
            return filtered_entry

        filtered_data = []
        for entry in result:
            filtered_entry = filter_dict(entry, fields)
            filtered_data.append(filtered_entry)

        return filtered_data

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

    def __sort_result(self, result: List[Dict], subscription_id: str) -> None:
        """
        Performs sorting of given result list
        :param result: results to be sorted
        :param subscription_id: Subscription ID for logging purposes
        """
        for sort_field in self.sort_fields:
            try:
                if isinstance(sort_field, str):
                    result.sort(key=itemgetter(sort_field))
                elif isinstance(sort_field, dict):
                    for inner_key, inner_field in sort_field.items():
                        for outer_result_item in result:
                            try:
                                inner_result = outer_result_item[inner_key]
                                inner_result.sort(key=itemgetter(inner_field))
                            except Exception as e:
                                logger.warning(f"Unable to sort inner list for {sort_field} fields for project "
                                               f"{subscription_id}")
            except Exception as e:
                logger.warning(
                    f"Issue sorting results for call:'{self.resource_name}' for subscription:'{subscription_id}' "
                    f"for sorting field {sort_field}")
                logger.debug(f"Reason: {e}")


def configure_azure_queries(queries: List[Dict[str, Any]]) -> Dict[str, AzureQuery]:
    """
    Configures Azure queries objects from configuration
    :param queries: per service query configuration
    :returns resource name to AzureQuery object mapping
    """
    if not isinstance(queries, list):
        raise AzureQueryArgumentError(f"Incorrect Azure queries configuration. Should be list, is {type(queries)}")
    #TODO better configuraiton file verification
    result = {}
    for query in queries:
        if RESOURCE not in query:
            raise AzureQueryArgumentError(f"Missing required key in query: '{query}'")
        #TODO Add Azure logging parsing
        if ITEM_EXCLUDE_FILTER in query:
            item_exclude_filter = query[ITEM_EXCLUDE_FILTER]
            if not isinstance(item_exclude_filter, list):
                raise AzureQueryArgumentError(f"Incorrect Azure query configuration. Item exclude filter should be list, "
                                            f"is {type(item_exclude_filter)}")
        num_retries = query.get(NUM_RETRIES, DEFAULT_NUM_RETRIES)
        sort_fields = query.get(SORT_FIELDS, DEFAULT_SORT_FIELDS)
        # Create kwargs from only keyword arguments
        ## Skip gcp query kwargs and pass everything else to api call
        kwargs = dict(filterfalse(lambda x: x[0] not in set([
            "field_exclude_filter", "field_include_filter", "item_exclude_filter", "result_items_field"]),
                                  query.items()))
        try:
            result[query[RESOURCE]] = AzureQuery.create(resource_name=query[RESOURCE],
                                               num_retries=num_retries,
                                               sort_fields=sort_fields,
                                                **kwargs)
        except Exception as e:
            raise AzureQueryArgumentError(f"Issue parsing query config {query}") from e
    return result

#Needed to load all implementation of AzureQuery Base Class
try:
    impl_classes_dir = os.path.dirname(__file__)
    for filename in os.listdir(impl_classes_dir):
        if filename.endswith(".py") and filename not in ("azurequery.py", "__init__.py"):
            module_name = __name__.split(".")[-1]
            spec = importlib.util.spec_from_file_location(module_name, f"{impl_classes_dir}/{filename}")
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
except Exception as e:
    logger.error(f"Unable to load AzureQuery classes from {impl_classes_dir}")
    raise e


class AzureQueryError(Exception):
    pass


class AzureQueryArgumentError(AzureQueryError):
    pass
