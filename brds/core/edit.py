"""Find and replace utilities."""

from collections import namedtuple
from typing import Callable, Iterable, Union

from pandas import DataFrame, Index, Series

ExactMatch = namedtuple("ExactMatch", "column value")
Replacement = namedtuple("Replacement", "column value")
FindCallBack = Callable[[DataFrame], Series]
MatcherT = Iterable[Union[ExactMatch, FindCallBack]]


def find(df: DataFrame, matchers: MatcherT) -> DataFrame:
    """Find all rows where the columns exacly match the values."""
    for matcher in matchers:
        if isinstance(matcher, ExactMatch):
            column, value = matcher
            df = df[df[column] == value]
        elif callable(matcher):
            df = df[matcher(df)]
        else:
            raise RuntimeError(f"Unable to process matcher '{matcher}'")
    return df


def finder(exact_match: MatcherT) -> Callable[[DataFrame], DataFrame]:
    """Make a funciton that will find all rows from a dataframe where the columns exactly match the given values."""

    def _find(df: DataFrame) -> DataFrame:
        return find(df, exact_match)

    return _find


def replace(df: DataFrame, index: Index, replacements: Iterable[Replacement]) -> DataFrame:
    """Replace the specified columns with specified values at the given index."""
    for column, value in replacements:
        df.loc[index, [column]] = value
    return df


def replacer(
    replacements: Iterable[Replacement],
) -> Callable[[DataFrame, Index], DataFrame]:
    """Make a funtion to replace the specified columns with specified values at the given index."""

    def _replace(df: DataFrame, index: Index) -> DataFrame:
        return replace(df, index, replacements)

    return _replace


def find_and_replace(
    df: DataFrame,
    exact_match: MatcherT,
    replacements: Iterable[Replacement],
) -> DataFrame:
    """Find exact matches and replace the values in those rows with replacements."""
    return replace(df, find(df, exact_match).index, replacements)


def find_and_replacer(
    exact_match: MatcherT,
    replacements: Iterable[Replacement],
) -> Callable[[DataFrame], DataFrame]:
    """Make a function to find exact matches and replace the values in those rows with replacements."""

    def _find_and_replace(df: DataFrame):
        return find_and_replace(df, exact_match, replacements)

    return _find_and_replace
