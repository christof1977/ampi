from flask_restful import Resource, request
from flask import jsonify
import json
import markdown
import markdown.extensions.fenced_code
from flask import render_template, make_response

class Alive(Resource):
    def __init__(self, **kwargs):
        self.ampi = kwargs['ampi']

    def get(self):
        return json.loads(self.ampi.get_alive())

class Status(Resource):
    def __init__(self, **kwargs):
        self.ampi = kwargs['ampi']

    def get(self):
        return json.loads(self.ampi.status())

class Sources(Resource):
    def __init__(self, **kwargs):
        self.ampi = kwargs['ampi']

    def get(self):
        return json.loads(self.ampi.get_sources())

class Source(Resource):
    def __init__(self, **kwargs):
        self.ampi = kwargs['ampi']

    def get(self):
        return json.loads(self.ampi.get_source())

    def put(self):
        source = request.args.get("set")
        return json.loads(self.ampi.set_source(source))

class Output(Resource):
    def __init__(self, **kwargs):
        self.ampi = kwargs['ampi']

    def get(self):
        return json.loads(self.ampi.get_output())

    def put(self):
        output = request.args.get("set")
        return json.loads(self.ampi.set_output(output))

class Volume(Resource):
    def __init__(self, **kwargs):
        self.ampi = kwargs['ampi']

    def get(self):
        return json.loads(self.ampi.get_volume())

    def put(self):
        vol = request.args.get("vol")
        return json.loads(self.ampi.set_volume(vol))

class SchrankLight(Resource):
    def __init__(self, **kwargs):
        self.ampi = kwargs['ampi']

    def get(self):
        return json.loads(self.ampi.get_schrank_light())

    def put(self):
        return json.loads(self.ampi.set_schrank_light())

class Ambilight(Resource):
    def __init__(self, **kwargs):
        self.ampi = kwargs['ampi']

    def get(self):
        return json.loads(self.ampi.get_al())

    def put(self):
        return(json.loads(self.ampi.set_al(request.args)))

