#!/usr/bin/env python
from urllib.parse import urlparse

import pandas as pd
import requests

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


class InvalidURLException(Exception):
    pass


class SOTGScorer:
    """A class to do all the spirit scoring"""

    NETLOC = "docs.google.com"
    PATH_PREFIX = "/spreadsheets/d/"

    def __init__(self, url, columns=None):
        self.url = self.get_export_url(url)
        self.columns = columns or {}

    @classmethod
    def get_export_url(cls, url):
        """Return the export URL from a spreadsheet URL."""
        parsed = urlparse(url)
        if not parsed.netloc == cls.NETLOC:
            raise InvalidURLException("Not a google spreadsheet URL")

        if not parsed.path.startswith(cls.PATH_PREFIX):
            raise InvalidURLException("Not a google spreadsheet URL")

        if requires_login(url):
            raise InvalidURLException(
                "Spreadsheet is not accessible without login"
            )

        key = parsed.path.split("/")[3]
        return "https://{netloc}{path}{key}/export?format=csv".format(
            netloc=cls.NETLOC, path=cls.PATH_PREFIX, key=key
        )

    @property
    def data(self):
        """Return the data as a Pandas DataFrame."""
        if not hasattr(self, "_data"):
            self._data = pd.read_csv(self.url)
            COLUMNS = self._data.columns
            columns = self.columns
            self.team_column = (
                COLUMNS[int(columns.get("team"))]
                if columns.get("team")
                else TEAM_COLUMN
            )
            self.team_score_columns = (
                [
                    COLUMNS[int(column)]
                    for column in columns.get("team-score-columns")
                ]
                if columns.get("team-score-columns")
                else TEAM_SCORE_COLUMNS
            )
            self.opponent_column = (
                COLUMNS[int(columns.get("opponent"))]
                if columns.get("team")
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
                COLUMNS[int(columns.get("day"))]
                if columns.get("day")
                else DAY_COLUMN
            )
        return self._data

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
        self._fix_team_names()
        d_int = pd.np.int
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
        rankings = pd.DataFrame([score, self_score], dtype=d_int).transpose()
        rankings["Avg spirit score"] = avg_score
        rankings["Avg self spirit score"] = avg_self_score
        rankings["Avg score difference"] = avg_score - avg_self_score
        # Compute and order by ranks
        # FIXME: This is such a mess!
        rankings = rankings.sort_values("Avg spirit score", ascending=False)
        ranks = rankings["Avg spirit score"].rank(
            method="min", ascending=False
        )
        rankings["Rank"] = pd.Series(ranks, dtype=d_int)
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
            rankings.style.set_precision("4")
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
        team_scores = self.data[self.data[self.team_column] == team][
            team_columns
        ]
        merged_scores = scores.merge(
            team_scores,
            how="outer",
            left_on=[self.team_column, self.day_column],
            right_on=[self.opponent_column, self.day_column],
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
        return display_scores

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
        team_scores = self.data[self.data[self.opponent_column] == team][
            team_columns
        ]
        merged_scores = scores.merge(
            team_scores,
            how="outer",
            left_on=[self.opponent_column, self.day_column],
            right_on=[self.team_column, self.day_column],
        )
        # Replace NaN in team column with names from opponent column (self scores)
        merged_scores[self.opponent_column] = merged_scores[
            self.opponent_column
        ].mask(pd.isna, merged_scores[self.team_column])
        columns = (
            [self.opponent_column, self.day_column]
            + self.opponent_score_columns
            + [TOTAL_SCORE_COLUMN]
            + self.team_score_columns
            + [TOTAL_SELF_SCORE_COLUMN]
        )
        return merged_scores[columns]

    def _make_scores_numbers(self):
        """Convert str score columns to numbers"""
        data = self.data
        opponent_scores = data[self.opponent_score_columns]
        if not opponent_scores.dtypes.apply(
            lambda x: x.type == pd.np.float64
        ).all():
            data[self.opponent_score_columns] = opponent_scores.applymap(
                to_numbers
            )
        self_scores = data[self.team_score_columns]
        if not self_scores.dtypes.apply(
            lambda x: x.type == pd.np.float64
        ).all():
            data[self.team_score_columns] = self_scores.applymap(to_numbers)

    def _fix_team_names(self):
        data = self.data
        team = self.team_column
        opponent = self.opponent_column
        teams = set(data[data[team].notna()][team].unique())
        opponents = set(data[data[opponent].notna()][opponent].unique())
        n = len(teams - opponents)
        if n == 0:
            return
        elif n > 1:
            msg = "Fix incorrectly spelled or missing teams in {} and {}. ".format(
                self.team_column, self.opponent_column
            )
            names = ", ".join(teams ^ opponents)
            msg += "The following teams are mis-spelled or missing: {}".format(
                names
            )
            raise RuntimeError(msg)
        else:
            name = list(teams - opponents)[0]
            wrong_name = list(opponents - teams)[0]
            self._data[self.opponent_column] = self._data[
                self.opponent_column
            ].str.replace(wrong_name, name)
            print(self._data[self.opponent_column])
