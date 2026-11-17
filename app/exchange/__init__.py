from flask import Blueprint

bp = Blueprint("exchange", __name__, url_prefix="/exchange")

from . import routes  # noqa: E402,F401
