"""Planner boundary: limited offline grammar, optional provider factory."""
from __future__ import annotations

import importlib
import os
import re
from typing import Protocol

from .model import Selection


class Planner(Protocol):
    def plan(self, instruction: str, selection: Selection | None = None) -> list[dict]: ...


def sequence(group: str, filters: list[dict]) -> list[dict]:
    hourly = group == 'pickup_hour'
    return [{'op':'select_table','table':'trips'}, *filters,
            {'op':'group_by','field':group}, {'op':'aggregate','function':'count'},
            {'op':'sort_rows','field':'pickup_hour' if hourly else 'trips','descending':not hourly},
            {'op':'add_chart_type','type':'line' if hourly else 'bar'},
            {'op':'add_encoding','x':group,'y':'trips'},
            {'op':'add_params','type':'interval','encoding':'x'}, {'op':'add_data'}]


def selection_filters(selection: Selection) -> list[dict]:
    return [{'op':'filter_rows','field':'pickup_hour','values':selection.hours},
            {'op':'filter_rows','field':'pickup_borough','values':selection.boroughs}]


class RuleBasedPlanner:
    """Recognize only the documented January trip-count requests."""
    def plan(self, instruction: str, selection: Selection | None = None) -> list[dict]:
        text = instruction.lower()
        unsupported = ['predict','tip','mean','average','median','february','march','april','may','june','july','august','september','october','november','december','fewest','ascending']
        years = re.findall(r'\b\d{4}\b', text)
        if 'trip' not in text or any(re.search(r'\b'+word+r'\b', text) for word in unsupported) or any(y != '2024' for y in years):
            raise ValueError('Offline planner supports January 2024 trip counts only')
        if selection is not None:
            if 'rank' not in text or 'zone' not in text:
                raise ValueError('Follow-up requires ranking pickup zones by trip count')
            return sequence('pickup_zone_id',selection_filters(selection))
        boroughs=[b for b in ['Manhattan','Queens','Brooklyn','Bronx','Staten Island'] if b.lower() in text]
        if len(boroughs) != 1 or not ('hourly' in text or 'hour' in text):
            raise ValueError('Request hourly trip counts for one pickup borough')
        return sequence('pickup_hour',[{'op':'filter_rows','field':'pickup_borough','values':boroughs}])


def planner_from_env() -> Planner:
    hook=os.environ.get('FIGUREFLOW_PLANNER')
    if not hook:
        return RuleBasedPlanner()
    try:
        module,factory=hook.split(':')
        planner=getattr(importlib.import_module(module),factory)()
    except (ValueError,ImportError,AttributeError) as error:
        raise ValueError('FIGUREFLOW_PLANNER must identify an importable module:factory') from error
    if not callable(getattr(planner,'plan',None)):
        raise ValueError('Planner factory must return an object with plan()')
    return planner
