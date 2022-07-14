#!/usr/bin/env python
import io
import re
from urllib.parse import urlparse

import numpy as np
import pandas as pd
import requests

GSHEET_NETLOC = "docs.google.com"
GSHEET_PATH_PREFIX = "/spreadsheets/d/"

TEAM_COLUMN = "Your Team"
OPPONENT_COLUMN = "Opponent Team"
OPPONENT_SCORE_COLUMNS = [
    "Rules Knowledge and Use",
    "Fouls and Body Contact",
    "Fair-Mindedness",
    "Positive Attitude and Self-Control",
    "Communication",
]
TEAM_SCORE_COLUMNS = [
    "Rules Knowledge and Use (self)",
    "Fouls and Body Contact (self)",
    "Fair-Mindedness (self)",
    "Positive Attitude and Self-Control (self)",
    "Communication (self)",
]
DAY_COLUMN = "Day"
TOTAL_SCORE_COLUMN = "Score"
TOTAL_SELF_SCORE_COLUMN = "Self Score"

ALL_COLUMNS = (
    [TEAM_COLUMN, OPPONENT_COLUMN, DAY_COLUMN]
    + OPPONENT_SCORE_COLUMNS
    + TEAM_SCORE_COLUMNS
)


def to_numbers(x):
    """Convert an element to a number."""
    if isinstance(x, str):
        try:
            return int(x.split()[0])

        except Exception:
            return 0

    return x


def requires_login(url):
    response = requests.get(url)
    return response.url.startswith("https://accounts.google.com")


def gsheet_id(url):
    parsed = urlparse(url)
    if not parsed.netloc == GSHEET_NETLOC:
        raise InvalidURLException("Not a google spreadsheet URL")

    if not parsed.path.startswith(GSHEET_PATH_PREFIX):
        raise InvalidURLException("Not a google spreadsheet URL")

    if requires_login(url):
        raise InvalidURLException("Spreadsheet is not accessible without login")

    return parsed.path.split("/")[3]


def export_url(sheet_id):
    """Return the export URL using sheet_id."""
    base = sheet_url(sheet_id)
    return f"{base}/export?format=csv"


def sheet_url(sheet_id):
    """Return the sheet URL using sheet_id."""
    return f"https://{GSHEET_NETLOC}{GSHEET_PATH_PREFIX}{sheet_id}"


def get_missing_scores(outer, inner, left_on, right_on):
    outer_left = {tuple(s) for s in outer[left_on].fillna("").values if s[0]}
    inner_left = {tuple(s) for s in inner[left_on].fillna("").values if s[0]}
    missing_left = outer_left - inner_left

    outer_right = {tuple(s) for s in outer[right_on].fillna("").values if s[0]}
    inner_right = {tuple(s) for s in inner[right_on].fillna("").values if s[0]}
    missing_right = outer_right - inner_right

    return missing_left, missing_right


class InvalidURLException(Exception):
    pass


class SOTGScorer:
    """A class to do all the spirit scoring"""

    def __init__(self, sheet_id, columns=None):
        self.url = export_url(sheet_id)
        self.sheet_url = sheet_url(sheet_id)
        self.csv, self.show_rankings = self.get_csv_and_mode()
        self.columns = columns or {}

    def get_csv_and_mode(self):
        response = requests.get(self.url)
        header = response.headers.get("Content-Disposition", "")
        match = re.search('filename="(.*)"', header)
        name = match.group(1) if match else "metadata.csv"
        return response.text, "show-rankings" in name

    @property
    def data(self):
        """Return the data as a Pandas DataFrame."""
        if not hasattr(self, "_data"):
            self._data = pd.read_csv(io.StringIO(self.csv))
            COLUMNS = self._data.columns
            columns = self.columns
            self.team_column = (
                COLUMNS[int(columns.get("team"))]
                if columns.get("team")
                else TEAM_COLUMN
            )
            self.team_score_columns = (
                [COLUMNS[int(column)] for column in columns.get("team-score-columns")]
                if columns.get("team-score-columns")
                else TEAM_SCORE_COLUMNS
            )
            self.opponent_column = (
                COLUMNS[int(columns.get("opponent"))]
                if columns.get("opponent")
                else OPPONENT_COLUMN
            )
            self.opponent_score_columns = (
                [
                    COLUMNS[int(column)]
                    for column in columns.get("opponent-score-columns")
                ]
                if columns.get("opponent-score-columns")
                else OPPONENT_SCORE_COLUMNS
            )
            self.day_column = (
                COLUMNS[int(columns.get("day"))] if columns.get("day") else DAY_COLUMN
            )
        return self._data

    @property
    def column_names(self):
        if not hasattr(self, "_data"):
            return ALL_COLUMNS
        return (
            [self.team_column, self.opponent_column, self.day_column]
            + self.opponent_score_columns
            + self.team_score_columns
        )

    @property
    def teams(self):
        """Return team names from the data."""
        if not hasattr(self, "_teams"):
            team = self.team_column
            opponent = self.opponent_column
            data = self.data
            teams = set(data[data[team].notna()][team].unique())
            opponents = set(data[data[opponent].notna()][opponent].unique())
            self._teams = sorted(teams | opponents)
        return self._teams

    @property
    def rankings(self):
        """Return spirit rankings given data, teams, and column names.

        The rankings are in the following format:
        |Team|Matches|Score|Self score|Avg spirit score|Avg self score|Difference|

        """
        data = self.data
        self._make_scores_numbers()

        # Compute aggregate scores
        total_score = data[self.opponent_score_columns].sum(axis=1)
        data[TOTAL_SCORE_COLUMN] = total_score
        total_self_score = data[self.team_score_columns].sum(axis=1)
        data[TOTAL_SELF_SCORE_COLUMN] = total_self_score
        # Get matches, total scores and averages
        team_column = self.team_column
        opponent_column = self.opponent_column
        score_matches = data.groupby(opponent_column)[opponent_column].count()
        self_score_matches = data.groupby(team_column)[team_column].count()
        score = data.groupby(self.opponent_column)[TOTAL_SCORE_COLUMN].sum()
        self_score = data.groupby(team_column)[TOTAL_SELF_SCORE_COLUMN].sum()
        avg_score = score / score_matches
        avg_self_score = self_score / self_score_matches
        # Create dataframe to use for ranking
        rankings = pd.DataFrame([score, self_score], dtype=np.int).transpose()
        rankings["Avg spirit score"] = avg_score
        rankings["Avg self spirit score"] = avg_self_score
        rankings["Avg score difference"] = avg_score - avg_self_score
        # Compute and order by ranks
        # FIXME: This is such a mess!
        rankings = rankings.sort_values("Avg spirit score", ascending=False)
        ranks = rankings["Avg spirit score"].rank(method="min", ascending=False)
        rankings["Rank"] = pd.Series(ranks, dtype=np.int)
        rankings["Team"] = rankings.index
        column_order = [
            "Rank",
            "Team",
            "Avg spirit score",
            "Avg self spirit score",
            "Score",
            "Self Score",
            "Avg score difference",
        ]
        rankings = rankings[column_order]
        # Styling
        rankings = (
            rankings.style.set_precision("2")
            .set_table_attributes(
                'border="0" class="dataframe table table-hover table-striped"'
            )
            .set_table_styles(
                [
                    dict(selector=".row_heading", props=[("display", "none")]),
                    dict(selector=".blank", props=[("display", "none")]),
                ]
            )
            .apply(self._bold_columns, axis=0)
        )
        return rankings

    @property
    def received_scores(self):
        """Return spirit scores received by each team."""
        detailed_scores = [
            (team, self._get_received_scores(team)) for team in self.teams
        ]
        return detailed_scores

    @property
    def awarded_scores(self):
        """Return spirit scores awarded by each team."""
        detailed_scores = [
            (team, self._get_awarded_scores(team)) for team in self.teams
        ]
        return detailed_scores

    @property
    def all_scores(self):
        """Return rankings, received and awarded scores."""
        return self.rankings, self.received_scores, self.awarded_scores

    @property
    def missing_columns(self):
        # NOTE: accessing self.data populates attributes required by self.column_names
        data_columns = self.data.columns
        return set(self.column_names) - set(data_columns)

    def _bold_columns(self, column):
        """Set font-weight if column needs to be bold"""
        return [
            "font-weight: 700;"
            if column.name in {"Rank", "Team", "Avg spirit score"}
            else ""
            for _ in column
        ]

    def _get_received_scores(self, team):
        """Return all the spirit scores received by the specified team

        Also, appends the self scores for that match, beside the scores
        received.

        """
        columns = (
            [self.team_column, self.day_column]
            + self.opponent_score_columns
            + [TOTAL_SCORE_COLUMN]
        )
        scores = self.data[self.data[self.opponent_column] == team][columns]
        team_columns = (
            [self.opponent_column, self.day_column]
            + self.team_score_columns
            + [TOTAL_SELF_SCORE_COLUMN]
        )
        team_scores = self.data[self.data[self.team_column] == team][team_columns]
        left_on = [self.team_column, self.day_column]
        right_on = [self.opponent_column, self.day_column]
        merged_scores_inner = scores.merge(
            team_scores, how="inner", left_on=left_on, right_on=right_on
        )
        merged_scores_outer = scores.merge(
            team_scores, how="outer", left_on=left_on, right_on=right_on
        )
        missing_our, missing_other = get_missing_scores(
            merged_scores_outer, merged_scores_inner, left_on, right_on
        )
        merged_scores = (
            merged_scores_outer if self.show_rankings else merged_scores_inner
        )
        # Replace NaN in team column with names from opponent column (self scores)
        merged_scores[self.team_column] = merged_scores[self.team_column].mask(
            pd.isna, merged_scores[self.opponent_column]
        )
        columns = (
            [self.team_column, self.day_column]
            + self.opponent_score_columns
            + [TOTAL_SCORE_COLUMN]
            + self.team_score_columns
            + [TOTAL_SELF_SCORE_COLUMN]
        )
        display_scores = merged_scores[columns].rename(
            columns={self.team_column: "Scored by"}
        )
        return display_scores, missing_our, missing_other

    def _get_awarded_scores(self, team):
        """Return all the spirit scores awarded by the specified team.


        Also, appends the self scores of the team for that match, beside the
        scores awarded

        """
        columns = (
            [self.opponent_column, self.day_column]
            + self.opponent_score_columns
            + [TOTAL_SCORE_COLUMN]
        )
        scores = self.data[self.data[self.team_column] == team][columns]
        team_columns = (
            [self.team_column, self.day_column]
            + self.team_score_columns
            + [TOTAL_SELF_SCORE_COLUMN]
        )
        team_scores = self.data[self.data[self.opponent_column] == team][team_columns]
        left_on = [self.opponent_column, self.day_column]
        right_on = [self.team_column, self.day_column]
        merged_scores_outer = scores.merge(
            team_scores, how="outer", left_on=left_on, right_on=right_on
        )
        merged_scores_inner = scores.merge(
            team_scores, how="inner", left_on=left_on, right_on=right_on
        )
        missing_other, missing_our = get_missing_scores(
            merged_scores_outer, merged_scores_inner, left_on, right_on
        )
        merged_scores = (
            merged_scores_outer if self.show_rankings else merged_scores_inner
        )
        # Replace NaN in team column with names from opponent column (self scores)
        merged_scores[self.opponent_column] = merged_scores[self.opponent_column].mask(
            pd.isna, merged_scores[self.team_column]
        )
        columns = (
            [self.opponent_column, self.day_column]
            + self.opponent_score_columns
            + [TOTAL_SCORE_COLUMN]
            + self.team_score_columns
            + [TOTAL_SELF_SCORE_COLUMN]
        )
        return merged_scores[columns], missing_our, missing_other

    def _make_scores_numbers(self):
        """Convert str score columns to numbers"""
        data = self.data
        opponent_scores = data[self.opponent_score_columns]
        if not opponent_scores.dtypes.apply(lambda x: x.type == np.float64).all():
            data[self.opponent_score_columns] = opponent_scores.applymap(to_numbers)
        self_scores = data[self.team_score_columns]
        if not self_scores.dtypes.apply(lambda x: x.type == np.float64).all():
            data[self.team_score_columns] = self_scores.applymap(to_numbers)
