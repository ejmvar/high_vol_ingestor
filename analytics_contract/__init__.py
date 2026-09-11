"""Replaceable analytical query ports and compatibility fixtures."""

from .fixture import EXPECTED_SUMMARY, FIXTURE_ROWS, Summary
from .ports import AnalyticsAdapter

__all__ = ["AnalyticsAdapter", "EXPECTED_SUMMARY", "FIXTURE_ROWS", "Summary"]
