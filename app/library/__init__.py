from flask import Blueprint

bp = Blueprint("library", __name__, url_prefix="/library")

from . import routes  # noqa: E402,F401
