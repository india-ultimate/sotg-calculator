#!/usr/bin/env python
import os
from os.path import abspath, dirname, join
from urllib.parse import urlparse, urlunparse

from cryptography.fernet import Fernet
from flask import flash, Flask, redirect, render_template, request, url_for
import mistune

from scorer import SOTGScorer, InvalidURLException, gsheet_id, ALL_COLUMNS

HERE = dirname(abspath(__file__))
README = join(HERE, "README.md")
DEBUG = "DEBUG" in os.environ
FERNET_KEY = os.getenv(
    "FERNET_KEY", "fJmpQZpowvAPFiYu4fPT0-dKRbd2h_Mvy7XXsuf9FdE="
).encode()
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "Super secret key")


def get_usage():
    """Return rendered HTML of the Usage section from README.md."""
    usage = ""
    for line in open(README):
        if not usage and not line.startswith("## Usage"):
            continue

        elif usage and line.startswith("## ") and not line.startswith("## Usage"):
            break

        else:
            usage += line
    html = mistune.markdown(usage, escape=False)
    usage, more_usage = html.split("<!-- More -->")
    with open(join(HERE, "templates", "read-more-button.html.jinja")) as f:
        button_code = f.read().strip()
    usage = usage.replace("<!-- see-more-link -->", button_code)
    return usage, more_usage


@app.before_request
def redirect_heroku():
    """Redirect herokuapp requests to indiaultimate.org."""
    urlparts = urlparse(request.url)
    if urlparts.netloc == "sotg-calculator.herokuapp.com":
        urlparts_list = list(urlparts)
        urlparts_list[1] = "sotg.indiaultimate.org"
        return redirect(urlunparse(urlparts_list), code=301)


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/demo")
def demo():
    return render_template("demo.html")


def _parse_args():
    url = request.args.get("url")
    sheet_id = request.args.get("sheet_id")
    columns = {
        "team": request.args.get("team"),
        "opponent": request.args.get("opponent"),
        "day": request.args.get("day"),
        "team-score-columns": request.args.getlist("team-score-columns"),
        "opponent-score-columns": request.args.getlist("opponent-score-columns"),
    }
    page = request.args.get("page")
    return url, sheet_id, columns, page


def f_encrypt(text):
    f = Fernet(FERNET_KEY)
    return f.encrypt(text.encode()).decode()


def f_decrypt(token):
    f = Fernet(FERNET_KEY)
    return f.decrypt(token.encode()).decode()


@app.route("/", methods=["GET"])
def index():
    usage, more_usage = get_usage()
    return render_template("index.html.jinja", usage=usage, more_usage=more_usage)


@app.route("/score", methods=["GET"])
def score():
    url, sheet_id, columns, page = _parse_args()
    if not url and not sheet_id:
        return redirect(url_for("index"))

    if not sheet_id:
        try:
            sheet_id = f_encrypt(gsheet_id(url))
        except InvalidURLException as e:
            flash(str(e))
        return redirect(url_for("score", sheet_id=sheet_id, page=page, **columns))

    _sheet_id = f_decrypt(sheet_id)
    scorer = SOTGScorer(_sheet_id, columns=columns)
    if scorer.missing_columns:
        flash(
            f"Some columns are missing: {scorer.missing_columns}."
            f"Please select the columns to use for the calculations, "
            f"or rename columns to match {ALL_COLUMNS}"
        )
        all_columns = list(scorer.data.columns)
        return redirect(
            url_for("columns", sheet_id=sheet_id, all_columns=all_columns, **columns)
        )

    try:
        rankings, received_scores, awarded_scores = scorer.all_scores
    except Exception as e:
        flash(str(e))
        return redirect(url_for("index"))

    return render_template(
        "score.html.jinja",
        url=scorer.sheet_url,
        show_rankings=scorer.show_rankings,
        rankings=rankings,
        received_scores=received_scores,
        awarded_scores=awarded_scores,
    )


@app.route("/columns", methods=["GET"])
def columns():
    _, sheet_id, columns, _ = _parse_args()
    all_columns = request.args.getlist("all_columns")
    # FIXME: Could pass missing columns to make number of selections smaller
    return render_template(
        "columns.html.jinja",
        all_columns=all_columns,
        columns=columns,
        sheet_id=sheet_id,
    )


def format_scores(scores):
    return scores.to_html(
        index=False,
        classes=["table", "table-striped"],
        na_rep="-",
        border=0,
        float_format="%d",
        justify="left",
    )


app.jinja_env.filters["format_scores"] = format_scores
if __name__ == "__main__":
    app.jinja_env.cache = None
    app.run(debug=DEBUG)
