"""
A thin python wrapper around the FoodData Central API.
Requires an API key from https://fdc.nal.usda.gov/api-key-signup.html (free).
"""

import json
import requests
from urllib.parse import urljoin
from dataclasses import dataclass
from functools import cached_property, cache


def parse_json(data):
    """
    Extract relevant information from the json response.
    This discards everything but name, ID, calories and macronutrients.

    :param data: json response
    :return: list of dicts with name, ID, calories and macronutrients
    """
    output = {}
    output["food_id"] = data["fdcId"]
    output["name"] = data["description"].lower()
    nutrition = {
        x["nutrient"]["name"].lower(): x["amount"] for x in data["foodNutrients"]
    }
    output["calories"] = int(nutrition["energy"])
    output["macronutrients"] = {
        "fat": nutrition["total lipid (fat)"],
        "carbs": nutrition["carbohydrate, by difference"],
        "protein": nutrition["protein"],
    }
    output["serving"] = {
        "value": data["servingSize"],
        "unit": data["servingSizeUnit"].lower(),
    }
    output["nutrition_per_serving"] = {
        "calories": data["labelNutrients"]["calories"]["value"],
        "fat": data["labelNutrients"]["fat"]["value"],
        "carbs": data["labelNutrients"]["carbohydrates"]["value"],
        "protein": data["labelNutrients"]["protein"]["value"],
    }
    return output


@dataclass
class FoodEntry:
    """
    A food entry with name, ID, calories, macronutrients, serving size and nutrition per
    serving.
    """
    food_id: int
    name: str
    calories: int
    macronutrients: dict
    serving: int
    nutrition_per_serving: dict

    def __str__(self):
        pass

    @staticmethod
    def from_json(json):
        return FoodEntry(**parse_json(json))


class FCAPI(object):
    """
    The main class for the FCAPI client. This class implements all the methods of the
    API. The mapping from API endpoints to methods is as follows:
        /food/{fdcId} -> food_by_id
        /foods -> foods_by_id
        /foods/list -> abridged_food_list (not implemented)
        /foods/search -> food_by_query
        /json-spec -> json_spec
        /yaml-spec -> yaml_spec
    """

    base_url = "https://api.nal.usda.gov/fdc/v1/"

    def __init__(self, api_key):
        """
        Initializes the FCAPI client.

        :param api_key: The API key. You will need to get one yourself.
        """
        self.api_key = api_key

    @cache
    def food_by_id(self, food_id, **kwargs):
        """
        Implements the /food/{fdcId} endpoint.
        Searches for a food item by the corresponding ID.
        This function only handles a single ID. If you have multiple, use foods_by_id.

        :param food_id: The food id.
        :param kwargs: The optional arguments to pass to the API.
        :return: A FoodEntry object.
        """
        if not isinstance(food_id, int):
            raise TypeError("food_id must be an integer. for a list use foods_by_id")
        # check if is already in local database
        url = urljoin(self.base_url, "food/" + str(food_id))
        params = {"api_key": self.api_key}
        params.update(kwargs)
        response = requests.get(url, params=params)
        check_response(response)
        return FoodEntry.from_json(json.loads(response.text))

    @cache
    def foods_by_id(self, food_ids, **kwargs):
        """
        Searches for multiple food items by the corresponding IDs.
        This function is appropriate if you already know the IDs.
        Note that it just omits any IDs that are not found.

        :param food_ids: The food ids.
        :param kwargs: The optional arguments to pass to the API.
        :return: A list of FoodEntry objects.
        """
        if not isinstance(food_ids, list):
            raise TypeError("food_ids must be a list. for a single id use food_by_id")
        if len(food_ids) > 20:
            raise ValueError("food_ids must be a list of length <= 20")
        url = urljoin(self.base_url, "foods")
        params = {
            "api_key": self.api_key,
            "fdcIds": ",".join([str(x) for x in food_ids]),
        }
        params.update(kwargs)
        response = requests.get(url, params=params)
        check_response(response)
        return [FoodEntry.from_json(x) for x in json.loads(response.text)["foods"]]

    @cache
    def search_food_by_query(self, query, brand=None, **kwargs):
        """
        Searches for a food item. This can result in a lot of results, the more specific
        the query, the better.

        :param query: The thing you want to search for.
        :param brand: The brand you want to search for.
        :param kwargs: The optional arguments to pass to the API.
        :return: A list of food items.
        """
        url = urljoin(self.base_url, "foods/search")
        params = {"api_key": self.api_key}
        params.update(kwargs)
        response = requests.get(url, params=params)
        check_response(response)
        return [FoodEntry.from_json(x) for x in json.loads(response.text)["foods"]]

    @cached_property
    def json_spec(self):
        """
        Returns the JSON specification for the API.
        """
        url = urljoin(self.base_url, "json-spec")
        params = {"api_key": self.api_key}
        response = requests.get(url, params=params)
        check_response(response)
        return json.loads(response.text)

    @cached_property
    def yaml_spec(self):
        """
        Returns the YAML specification for the API.
        Note that python doesn't have a built-in YAML parser, so I just return the raw
        text.
        """
        url = urljoin(self.base_url, "yaml-spec")
        params = {"api_key": self.api_key}
        response = requests.get(url, params=params)
        check_response(response)
        return response.text


def check_response(response):
    """
    Check validity of response.
    200 is valid
    400 means invalid parameters
    404 means not found
    """
    if response.status_code == 200:
        return True
    elif response.status_code == 400:
        raise ValueError("Apparently this request used an invalid parameter.")
    elif response.status_code == 404:
        raise ValueError("The status code indicates that the food item was not found.")
    else:
        raise RuntimeError("The status code indicates an unknown error.")
