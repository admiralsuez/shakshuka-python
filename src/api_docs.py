from flask import Blueprint
from flask_restx import Api, Resource, fields


blueprint = Blueprint("api", __name__, url_prefix="/api")
api = Api(blueprint, doc="/", title="Shakshuka API", version="1.0")

info_model = api.model(
    "Info",
    {
        "name": fields.String,
        "version": fields.String,
        "testing": fields.Boolean,
        "port": fields.Integer,
    },
)


@api.route("/v1/info")
class InfoResource(Resource):
    @api.marshal_with(info_model)
    def get(self):
        from datetime import datetime
        import os

        testing = os.environ.get("SHAKSHUKA_TESTING", "0") == "1"
        port = int(os.environ.get("SHAKSHUKA_PORT", "8989"))
        return {
            "name": "shakshuka",
            "version": "1.0.0",
            "testing": testing,
            "port": port,
        }


