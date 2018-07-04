#!/usr/bin/env python
import os
from os.path import abspath, dirname, join

from flask import flash, Flask, render_template, request
from flask_sslify import SSLify
import mistune

from scorer import SOTGScorer, InvalidURLException

HERE = dirname(abspath(__file__))
README = join(HERE, 'README.md')
DEBUG = 'DEBUG' in os.environ
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'Super secret key')
if 'DYNO' in os.environ:
    # only trigger SSLify if the app is running on Heroku
    sslify = SSLify(app)


def get_usage():
    """Return rendered HTML of the Usage section from README.md."""
    usage = ''
    for line in open(README):
        if not usage and not line.startswith('## Usage'):
            continue

        elif usage and line.startswith('## ') and not line.startswith(
            '## Usage'
        ):
            break

        else:
            usage += line
    html = mistune.markdown(usage, escape=False)
    usage, more_usage = html.split('<!-- More -->')
    with open(join(HERE, 'templates', 'read-more-button.html.jinja')) as f:
        button_code = f.read().strip()
    usage = usage.replace('<!-- see-more-link -->', button_code)
    return usage, more_usage


@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/demo')
def demo():
    return render_template('demo.html')


@app.route('/', methods=['GET'])
def index():
    url = request.args.get('url')
    columns = {
        'team': request.args.get('team'),
        'opponent': request.args.get('opponent'),
        'day': request.args.get('day'),
        'team-score-columns': request.args.getlist('team-score-columns'),
        'opponent-score-columns': request.args.getlist(
            'opponent-score-columns'
        ),
    }
    rankings = None
    received_scores = awarded_scores = all_columns = []
    errors = []
    prompt_column_select = False
    if not url:
        pass
    elif not all(columns.values()):
        try:
            scorer = SOTGScorer(url)
        except InvalidURLException as e:
            errors.append('Invalid URL - {}'.format(e))
        else:
            all_columns = list(scorer.data.columns)
            try:
                rankings, received_scores, awarded_scores = scorer.all_scores
            except KeyError as e:
                prompt_column_select = True
                errors.append(
                    'Some columns are named differently. '
                    'Please select the columns to use for the calculations'
                )
            except Exception as e:
                print(repr(e))
                prompt_column_select = True
                errors.append(
                    'Unknown Error: Try selecting the columns to use for the calculations'
                )
    else:
        scorer = SOTGScorer(url, columns=columns)
        rankings, received_scores, awarded_scores = scorer.all_scores
        all_columns = list(scorer.data.columns)
    for e in errors:
        flash(e, 'error')
    usage, more_usage = get_usage()
    return render_template(
        'index.html.jinja',
        errors=errors,
        usage=usage,
        more_usage=more_usage,
        columns=columns,
        all_columns=all_columns,
        url=url,
        prompt_column_select=prompt_column_select,
        rankings=rankings,
        received_scores=received_scores,
        awarded_scores=awarded_scores,
    )


def format_scores(scores):
    return scores.to_html(
        index=False,
        classes=['table', 'table-striped'],
        na_rep='-',
        border=0,
        float_format='%d',
        justify='left',
    )


app.jinja_env.filters['format_scores'] = format_scores
if __name__ == '__main__':
    app.jinja_env.cache = None
    app.run(debug=DEBUG)
