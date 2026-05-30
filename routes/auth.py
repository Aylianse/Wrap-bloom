from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app

auth_bp = Blueprint("auth", __name__)


def login_required(f):
    """Decorator that redirects unauthenticated users to the login page."""
    from functools import wraps

    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)

    return decorated


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("logged_in"):
        return redirect(url_for("main.dashboard"))

    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        valid_user = current_app.config["AUTH_USERNAME"]
        valid_pass = current_app.config["AUTH_PASSWORD"]

        if username == valid_user and password == valid_pass:
            session["logged_in"] = True
            session["username"] = username
            return redirect(url_for("main.dashboard"))
        else:
            error = "Invalid username or password."

    return render_template("login.html", error=error)


@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
