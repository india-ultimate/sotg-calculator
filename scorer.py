#!/usr/bin/env python

from urllib.parse import urlparse

import pandas as pd


TEAM_COLUMN = 'Your Team'
OPPONENT_COLUMN = 'Opponent Team'
OPPONENT_SCORE_COLUMNS = [
    'Rules Knowledge & Use',
    'Fouls and Body Contact',
    'Fair Mindedness',
    'Positive Attitude and Self-Control',
    'Communication',
]
TEAM_SCORE_COLUMNS = [
    'Rules Knowledge & Use.1',
    'Fouls and Body Contact.1',
    'Fair Mindedness.1',
    'Positive Attitude and Self-Control.1',
    'Communication.1',
]
TOTAL_SCORE_COLUMN = 'Score'
TOTAL_SELF_SCORE_COLUMN = 'Self Score'


def to_numbers(x):
    """Convert an element to a number."""
    if isinstance(x, str):
        try:
            return int(x.split()[0])
        except Exception:
            return 0
    return x


class SOTGScorer:
    """A class to do all the spirit scoring"""

    NETLOC = 'docs.google.com'
    PATH_PREFIX = '/spreadsheets/d/'

    def __init__(self, url, columns=None):
        self.url = self.get_export_url(url)
        self.columns = columns or {}

    @classmethod
    def get_export_url(cls, url):
        """Return the export URL from a spreadsheet URL."""
        parsed = urlparse(url)
        if not parsed.netloc == cls.NETLOC:
            raise ValueError('Not a google spreadsheets URL')
        if not parsed.path.startswith(cls.PATH_PREFIX):
            raise ValueError('Not a google spreadsheets URL')
        key = parsed.path.split('/')[3]
        return 'https://{netloc}{path}{key}/export?format=csv'.format(
            netloc=cls.NETLOC,
            path=cls.PATH_PREFIX,
            key=key
        )

    @property
    def data(self):
        """Return the data as a Pandas DataFrame."""
        if not hasattr(self, '_data'):
            self._data = pd.read_csv(self.url)
            COLUMNS = self._data.columns
            columns = self.columns
            self.team_column = (
                COLUMNS[int(columns.get('team'))] if columns.get('team') else TEAM_COLUMN
            )
            self.team_score_columns = (
                [COLUMNS[int(column)] for column in columns.get('team-score-columns')]
                if columns.get('team-score-columns')
                else TEAM_SCORE_COLUMNS
            )
            self.opponent_column = (
                COLUMNS[int(columns.get('opponent'))] if columns.get('team') else OPPONENT_COLUMN
            )
            self.opponent_score_columns = (
                [COLUMNS[int(column)] for column in columns.get('opponent-score-columns')]
                if columns.get('opponent-score-columns')
                else OPPONENT_SCORE_COLUMNS
            )
        return self._data

    @property
    def teams(self):
        """Return team names from the data."""
        if not hasattr(self, '_teams'):
            column = self.team_column
            data = self.data
            self._teams = list(data[data[column].notna()][column].unique())
        return self._teams

    def _make_scores_numbers(self):
        """Convert str score columns to numbers"""

        data = self.data

        opponent_scores = data[self.opponent_score_columns]
        if not opponent_scores.dtypes.apply(lambda x: x.type == pd.np.float64).all():
            data[self.opponent_score_columns] = opponent_scores.applymap(to_numbers)

        self_scores = data[self.team_score_columns]
        if not self_scores.dtypes.apply(lambda x: x.type == pd.np.float64).all():
            data[self.team_score_columns] = self_scores.applymap(to_numbers)

    def compute_rankings(self):
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

        # Get matches and total scores
        team_column = self.team_column
        matches = data.groupby(team_column)[team_column].count().rename('Matches')
        score = data.groupby(self.opponent_column)[TOTAL_SCORE_COLUMN].sum()
        self_score = data.groupby(team_column)[TOTAL_SELF_SCORE_COLUMN].sum()

        # Compute averages
        rankings = pd.DataFrame([matches, score, self_score]).transpose()
        avg_score = score/matches
        avg_self_score = self_score/matches
        rankings['Avg spirit score'] = avg_score
        rankings['Avg self spirit score'] = avg_self_score
        rankings['Difference'] = avg_score - avg_self_score

        # Compute and append rankings
        # FIXME: This is such a mess!
        rankings = rankings.sort_values('Avg spirit score', ascending=False)
        ranks = rankings['Avg spirit score'].rank(method='min', ascending=False)
        rankings['Rank'] = pd.Series(ranks, dtype=pd.np.int)
        rankings['Team'] = rankings.index
        rankings = rankings.set_index('Rank', drop=True)
        rankings.index.name = None
        column_order = [
            'Team', 'Matches', 'Score', 'Self Score',
            'Avg spirit score', 'Avg self spirit score', 'Difference'
        ]
        rankings = rankings[column_order]
        rankings.columns.name = 'Rank'

        return rankings
