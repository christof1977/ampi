import threading
from flask import Flask
from flask import request
from flask_restful import Api
from flask_restful import Resource, abort
from ampi import Ampi
from flaskext.markdown import Markdown
#from marshmallow import Schema, fields

from resources.status import Alive, Status, Source, Sources, Output, Volume, SchrankLight, Ambilight

host_name = "0.0.0.0"
port = 5000
app = Flask(__name__)
api = Api(app)
Markdown(app)

ampi = Ampi()
api.add_resource(Alive, '/', resource_class_kwargs={'ampi': ampi})
api.add_resource(Status, '/status', resource_class_kwargs={'ampi': ampi})
api.add_resource(Sources, '/source/list', resource_class_kwargs={'ampi': ampi})
api.add_resource(Source, '/source', resource_class_kwargs={'ampi': ampi})
api.add_resource(Output, '/output', resource_class_kwargs={'ampi': ampi})
api.add_resource(Volume, '/volume', resource_class_kwargs={'ampi': ampi})
api.add_resource(SchrankLight, '/light/schrank', resource_class_kwargs={'ampi': ampi})
api.add_resource(Ambilight, '/light/ambi', resource_class_kwargs={'ampi': ampi})

if __name__ == "__main__":
    threading.Thread(target=lambda: app.run(host=host_name, port=port, debug=True, use_reloader=False)).start()
    ampi.run()
