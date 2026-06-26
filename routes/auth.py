import logging
from collections import defaultdict
import time

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user

from extensions import db, limiter
from models import User
from forms import RegistrationForm, LoginForm

logger = logging.getLogger(__name__)

auth = Blueprint("auth", __name__)

# Keep track of timestamps of login attempts per IP address
login_attempts = defaultdict(list)

def check_login_rate_limit(ip_address):
    """Allow up to 5 login attempts per minute per IP address."""
    now = time.time()
    # Keep only attempts in the last 60 seconds
    attempts = [t for t in login_attempts[ip_address] if now - t < 60]
    login_attempts[ip_address] = attempts
    return len(attempts) >= 5

def record_login_attempt(ip_address):
    login_attempts[ip_address].append(time.time())


@auth.route("/register", methods=["GET", "POST"])
@limiter.limit("10 per hour")
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    form = RegistrationForm()
    if form.validate_on_submit():
        existing = User.query.filter(
            (User.email == form.email.data) | (User.username == form.username.data)
        ).first()
        if existing:
            flash("That username or email is already registered.", "danger")
            return render_template("register.html", form=form)

        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()

        flash("Welcome to LeafLore! Please log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("register.html", form=form)


@auth.route("/login", methods=["GET", "POST"])
@limiter.limit("20 per minute")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    ip = request.remote_addr
    if check_login_rate_limit(ip):
        flash("Too many login attempts. Please wait 60 seconds.", "danger")
        return render_template("login.html", form=LoginForm()), 429

    form = LoginForm()
    if form.validate_on_submit():
        record_login_attempt(ip)
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.check_password(form.password.data):
            # Clear attempts on successful login
            login_attempts.pop(ip, None)
            login_user(user, remember=form.remember.data)
            logger.info("User %s logged in from %s", user.id, request.remote_addr)
            next_page = request.args.get("next")
            return redirect(next_page or url_for("dashboard.index"))
        logger.warning("Failed login attempt for email=%s from %s", form.email.data, request.remote_addr)
        flash("Invalid email or password.", "danger")

    return render_template("login.html", form=form)


@auth.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))
