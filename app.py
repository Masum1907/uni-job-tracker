import os
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session
from apscheduler.schedulers.background import BackgroundScheduler
import atexit

import db
import scraper
from config import SCAN_INTERVAL_MINUTES, ADMIN_PASSWORD
from seed_universities import SEED_UNIVERSITIES

app = Flask(__name__)
# On Render: set a SECRET_KEY environment variable to a long random
# string. Falling back to a fixed value is fine for local testing only.
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-change-in-production")

db.init_db()
db.seed_universities(SEED_UNIVERSITIES)


def admin_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not session.get("is_admin"):
            flash("Please log in to do that.")
            return redirect(url_for("admin_login", next=request.path))
        return view_func(*args, **kwargs)
    return wrapped


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        password = request.form.get("password", "")
        if password == ADMIN_PASSWORD:
            session["is_admin"] = True
            flash("Logged in.")
            next_url = request.args.get("next") or url_for("universities")
            return redirect(next_url)
        flash("Wrong password.")
    return render_template("admin_login.html")


@app.route("/admin/logout", methods=["POST"])
def admin_logout():
    session.pop("is_admin", None)
    flash("Logged out.")
    return redirect(url_for("dashboard"))


@app.route("/")
def dashboard():
    only_unread = request.args.get("unread") == "1"
    postings = db.list_postings(only_unread=only_unread)
    return render_template(
        "dashboard.html",
        postings=postings,
        only_unread=only_unread,
        unread_count=db.unread_count(),
    )


@app.route("/mark-read/<int:posting_id>", methods=["POST"])
def mark_read(posting_id):
    db.mark_read(posting_id)
    return redirect(request.referrer or url_for("dashboard"))


@app.route("/mark-all-read", methods=["POST"])
def mark_all_read():
    db.mark_all_read()
    return redirect(url_for("dashboard"))


@app.route("/check-now", methods=["POST"])
def check_now():
    new_count = scraper.run_all_checks()
    flash(f"Check complete -- {new_count} new posting(s) found.")
    return redirect(url_for("dashboard"))


@app.route("/universities")
def universities():
    return render_template("universities.html", universities=db.list_universities())


@app.route("/universities/add", methods=["POST"])
@admin_required
def add_university():
    name = request.form.get("name", "").strip()
    url_ = request.form.get("url", "").strip()
    type_ = request.form.get("type", "").strip()
    if name and url_:
        ok = db.add_university(name, url_, type_)
        flash("Added." if ok else "That URL is already in the list.")
    else:
        flash("Name and URL are both required.")
    return redirect(url_for("universities"))


@app.route("/universities/bulk-add", methods=["POST"])
@admin_required
def bulk_add_universities():
    raw = request.form.get("bulk_text", "")
    added, skipped = 0, 0
    for line in raw.splitlines():
        line = line.strip()
        if not line or "," not in line:
            continue
        name, url_ = line.split(",", 1)
        if db.add_university(name.strip(), url_.strip()):
            added += 1
        else:
            skipped += 1
    flash(f"Added {added} universities ({skipped} skipped as duplicates/invalid).")
    return redirect(url_for("universities"))


@app.route("/universities/delete/<int:uni_id>", methods=["POST"])
@admin_required
def delete_university(uni_id):
    db.delete_university(uni_id)
    flash("Removed.")
    return redirect(url_for("universities"))


def scheduled_job():
    with app.app_context():
        scraper.run_all_checks()


if SCAN_INTERVAL_MINUTES > 0:
    scheduler = BackgroundScheduler()
    scheduler.add_job(scheduled_job, "interval", minutes=SCAN_INTERVAL_MINUTES)
    scheduler.start()
    atexit.register(lambda: scheduler.shutdown())


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
