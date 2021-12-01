import logging

import requests
from cachetools.func import lru_cache

from .service import devops_basic_auth
from ..config import INCIDENT_DEVOPS_ENDPOINT

log = logging.getLogger(__name__)


@lru_cache(maxsize=32)
def get_products():
    try:
        products_url = f"{INCIDENT_DEVOPS_ENDPOINT}/incidents/products"
        response = requests.get(url=products_url, auth=devops_basic_auth())

        if not response.ok:
            log.error(f"Error getting products from bold API: {response.text}")

        return response.json()
    except Exception:
        log.error(f"Error getting products from bold API")
    return {}


@lru_cache(maxsize=32)
def get_teams():
    try:
        teams_url = f"{INCIDENT_DEVOPS_ENDPOINT}/incidents/teams"
        response = requests.get(url=teams_url, auth=devops_basic_auth())

        if not response.ok:
            log.error(f"Error getting teams from bold API: {response.text}")
            return []

        teams = response.json()["teams"]
        return sorted(teams, key=str.casefold)
    except Exception:
        log.error(f"Error getting teams from bold API")
    return []


@lru_cache(maxsize=32)
def get_area_info():
    try:
        info_url = f"{INCIDENT_DEVOPS_ENDPOINT}/incidents/area.info"
        response = requests.get(url=info_url, auth=devops_basic_auth())

        if not response.ok:
            log.error(f"Error getting IT info from bold API: {response.text}")
            return {}

        return response.json()
    except Exception:
        log.error(f"Error getting IT info from bold API")
    return {}


def describe_products(team: str, product: str):
    products = get_products().get(team, {}).get(product, {})
    return (
        products.get("owner", ""),
        products.get("area", ""),
        products.get("process", ""),
        products.get("business_line", "")
    )


def get_products_by_team(team: str):
    products = get_products().get(team, [])
    return products.keys()
