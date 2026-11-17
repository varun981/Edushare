from flask import Blueprint

bp = Blueprint("donation", __name__, url_prefix="/donate")

from . import routes  # noqa: E402,F401
