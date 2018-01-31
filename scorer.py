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
SELF_SCORE_COLUMNS = [
    'Rules Knowledge & Use.1',
    'Fouls and Body Contact.1',
    'Fair Mindedness.1',
    'Positive Attitude and Self-Control.1',
    'Communication.1',
]
TOTAL_SCORE_COLUMN = 'Score'
TOTAL_SELF_SCORE_COLUMN = 'Self Score'


class SpiritScorer:
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
            self.opponent_column = (
                COLUMNS[int(columns.get('opponent'))] if columns.get('team') else OPPONENT_COLUMN
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

    def compute_rankings(self):
        """Return spirit rankings given data, teams, and column names.

        The rankings are in the following format:
        |Team|Matches|Score|Self score|Avg spirit score|Avg self score|Difference|

        """
        data = self.data
        # Compute aggregate scores
        total_score = data[OPPONENT_SCORE_COLUMNS].sum(axis=1)
        data[TOTAL_SCORE_COLUMN] = total_score
        total_self_score = data[SELF_SCORE_COLUMNS].sum(axis=1)
        data[TOTAL_SELF_SCORE_COLUMN] = total_self_score

        # Get matches and total scores
        team_column = self.team_column
        matches = data.groupby(team_column)[team_column].count().rename('Matches')
        score = data.groupby(OPPONENT_COLUMN)[TOTAL_SCORE_COLUMN].sum()
        self_score = data.groupby(team_column)[TOTAL_SELF_SCORE_COLUMN].sum()

        # Compute averages
        rankings = pd.DataFrame([matches, score, self_score]).transpose()
        avg_score = score/matches
        avg_self_score = self_score/matches
        rankings['Avg spirit score'] = avg_score
        rankings['Avg self spirit score'] = avg_self_score
        rankings['Difference'] = avg_score - avg_self_score

        return rankings.sort_values('Avg spirit score', ascending=False)
