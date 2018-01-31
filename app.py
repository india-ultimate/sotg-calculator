#!/usr/bin/env python

from urllib.parse import urlparse

import pandas as pd


GOOGLE = 'docs.google.com'
SPREADSHEET_PATH = '/spreadsheets/d/'
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

def get_export_url(url):
    """Return the export URL from a spreadsheet URL."""
    parsed = urlparse(url)
    if not parsed.netloc == GOOGLE:
        raise ValueError('Not a google spreadsheets URL')
    if not parsed.path.startswith(SPREADSHEET_PATH):
        raise ValueError('Not a google spreadsheets URL')
    key = parsed.path.split('/')[3]
    return 'https://{netloc}{path}{key}/export?format=csv'.format(netloc=GOOGLE,
                                                                  path=SPREADSHEET_PATH,
                                                                  key=key)


def get_teams(data, column=TEAM_COLUMN):
    """Return team names given a df."""
    return list(data[data[column].notna()][column].unique())


def get_rankings(data, teams):
    """Return spirit rankings given data, teams, and column names.

    The rankings are in the following format:
    |Team|Matches|Score|Self score|Avg spirit score|Avg self score|Difference|

    """
    # Compute aggregate scores
    total_score = data[OPPONENT_SCORE_COLUMNS].sum(axis=1)
    data[TOTAL_SCORE_COLUMN] = total_score
    total_self_score = data[SELF_SCORE_COLUMNS].sum(axis=1)
    data[TOTAL_SELF_SCORE_COLUMN] = total_self_score

    # Get matches and total scores
    matches = data.groupby(TEAM_COLUMN)[TEAM_COLUMN].count().rename('Matches')
    score = data.groupby(OPPONENT_COLUMN)[TOTAL_SCORE_COLUMN].sum()
    self_score = data.groupby(TEAM_COLUMN)[TOTAL_SELF_SCORE_COLUMN].sum()

    # Compute averages
    rankings = pd.DataFrame([matches, score, self_score]).transpose()
    avg_score = score/matches
    avg_self_score = self_score/matches
    rankings['Avg spirit score'] = avg_score
    rankings['Avg self spirit score'] = avg_self_score
    rankings['Difference'] = avg_score - avg_self_score
    return rankings.sort_values('Avg spirit score', ascending=False)


def get_detailed_scoresheets(data, teams):
    pass


def main(url):
    """Return the spirit scores given URL to a spreadsheet with responses."""
    export_url = get_export_url(url)
    data = pd.read_csv(export_url)
    TEAMS = get_teams(data)
    rankings = get_rankings(data, TEAMS)
    get_detailed_scoresheets(data, TEAMS)
    return rankings


if __name__ == '__main__':
    import sys
    url = sys.argv[1]
    rankings = main(url)
