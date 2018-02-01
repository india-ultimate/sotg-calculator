#!/usr/bin/env python

from os.path import abspath, dirname, join
from flask import Flask, render_template, request
import mistune

from scorer import SOTGScorer

HERE = dirname(abspath(__file__))
README = join(HERE, 'README.md')
app = Flask(__name__)


def get_usage():
    """Return rendered HTML of the Usage section from README.md."""
    usage = ''
    for line in open(README):
        if not usage and not line.startswith('## Usage'):
            continue
        elif usage and line.startswith('## ') and not line.startswith('## Usage'):
            break
        else:
            usage += line
    return mistune.markdown(usage)


@app.route('/', methods=['GET'])
def index():
    url = request.args.get('url')
    columns = {
        'team': request.args.get('team'),
        'opponent': request.args.get('opponent'),
        'day': request.args.get('day'),
        'team-score-columns': request.args.getlist('team-score-columns'),
        'opponent-score-columns': request.args.getlist('opponent-score-columns'),
    }

    rankings = None
    detailed_scores = []
    all_columns = []

    if url is None:
        pass

    elif not all(columns.values()):
        scorer = SOTGScorer(url)
        all_columns = list(scorer.data.columns)
        try:
            rankings = scorer.compute_rankings()
            detailed_scores = scorer.compute_detailed_scores()

        except KeyError as e:
            # FIXME: Show message ....
            print(e)

    else:
        scorer = SOTGScorer(url, columns=columns)
        rankings = scorer.compute_rankings()
        detailed_scores = scorer.compute_detailed_scores()
        all_columns = list(scorer.data.columns)

    return render_template('index.html.jinja',
                           usage=get_usage(),
                           columns=columns,
                           all_columns=all_columns,
                           url=url,
                           rankings=rankings,
                           detailed_scores=detailed_scores)


if __name__ == '__main__':
    app.run(debug=True)
