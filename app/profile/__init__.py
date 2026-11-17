from flask import Blueprint

bp = Blueprint("profile", __name__, url_prefix="/profile")

from . import routes  # noqa: E402,F401
