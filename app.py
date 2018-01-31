#!/usr/bin/env python

from flask import Flask, render_template, request

from scorer import SpiritScorer

app = Flask(__name__)


@app.route('/', methods=['GET'])
def index():
    url = request.args.get('url')
    if url is not None:
        scorer = SpiritScorer(url)
        rankings = scorer.compute_rankings()

    else:
        rankings = None

    return render_template('index.html.jinja', rankings=rankings)


if __name__ == '__main__':
    app.run(debug=True)
