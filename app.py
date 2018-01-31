#!/usr/bin/env python

from flask import Flask, render_template, request

from scorer import SpiritScorer

app = Flask(__name__)


def parse_column_args():
    columns = {
        'team': request.args.get('team'),
        'opponent': request.args.get('opponent'),
        'team-score-columns': request.args.getlist('team-score-columns'),
        'opponent-score-columns': request.args.getlist('opponent-score-columns'),
    }
    return columns


@app.route('/', methods=['GET'])
def index():
    url = request.args.get('url')
    columns = parse_column_args()
    if url is None:
        rankings = None
        all_columns = []

    elif not all(columns.values()):
        scorer = SpiritScorer(url)
        all_columns = list(scorer.data.columns)
        try:
            rankings = scorer.compute_rankings()

        except KeyError as e:
            # FIXME: Show message ....
            rankings = None

    else:
        scorer = SpiritScorer(url, columns=columns)
        rankings = scorer.compute_rankings()
        all_columns = list(scorer.data.columns)

    return render_template('index.html.jinja',
                           columns=columns,
                           all_columns=all_columns,
                           url=url,
                           rankings=rankings)


if __name__ == '__main__':
    app.run(debug=True)
