import logging
from time import sleep

from flask import Flask
from flask import abort
from flask import json
from flask import Response
from flask.json import JSONEncoder

from httc.client import BUTTON_CODES
from httc.client import BUTTON_NAMES
from httc.client import CECClient
from httc.client import PowerStatus


class ResponseJSON(Response):
    """Extend flask.Response with support for list/dict conversion to JSON."""
    def __init__(self, content=None, *args, **kargs):
        indent = None
        separators = (',', ':')
        
        if isinstance(content, (list, dict)):
            kargs['mimetype'] = 'application/json'
            content = json.dumps(content, indent=indent, separators=separators), '\n'

        super(Response, self).__init__(content, *args, **kargs)

    @classmethod
    def force_type(cls, response, environ=None):
        """Override with support for list/dict."""
        if isinstance(response, (list, dict)):
            return cls(response)
        else:
            return super(Response, cls).force_type(response, environ)


class FlaskJSON(Flask):
    """Extension of standard Flask app with custom response class."""
    response_class = ResponseJSON


class MyJSONEncoder(JSONEncoder):
    def default(self, obj):
        if isinstance(obj, PowerStatus):
            return str(obj)
        return super(MyJSONEncoder, self).default(obj)


app = FlaskJSON(__name__)
cec = CECClient('httpc')

app.json_encoder = MyJSONEncoder


@app.route("/")
def index():
    return {
        'this': ['is', 'the', 'cec', 'http', 'client']
    }


@app.route("/ping")
def ping():
    return {'pong': True}


@app.route("/devices")
def devices():
    return cec.devices


@app.route("/scan")
def scan():
    return cec.scan()


@app.route("/buttons")
def buttons():
    return BUTTON_CODES


@app.route("/<int:device>/<button>/press", methods=['POST'])
def press(device, button):
    button = BUTTON_NAMES.get(button, button)
    return {'status': cec.button_press(button, int(device), True)}


@app.route("/<int:device>/press/<buttons>", methods=['POST'])
def press_batch(buttons, device):
    out = []
    for button in buttons.split(','):
        button = BUTTON_NAMES.get(button, button)
        sleep(0.3)
        out.append(cec.button_press(button, device, True))
    return {'status': out}


@app.route("/sequence/<sequence>", methods=['POST'])
def sequence(sequence):
    """send a sequence of the form:

    <action>(<value>...)|
    e.g.
    raw(41:44:45)|raw(41:45) # press button select on device 1 (from device 4) then release button

    """
    rules = set()
    for rule in app.url_map.iter_rules():
        if 'POST' in rule.methods:
            rules.add(rule.endpoint)

    results = []
    for step in sequence.split('|'):
        func_name, _, args = step.partition('(')
        if args:
            args = [x.strip() for x in args[:-1].split(',')]
        if func_name == "sleep":
            sleep(float(args[0]))
        elif func_name in rules:
            results.append(app.view_functions[func_name](*args))
        else:
            abort(422)
    return {'results': results}


@app.route("/raw/<command>")
def raw(command):
    cec.raw_command(command)


@app.route("/<int:device>")
def device(device):
    return cec.devices[device]


@app.route("/<int:device>/<attribute>")
def device_attribute(device, attribute):
    return {attribute: cec.devices[device][attribute]}


@app.route("/<int:device>/power")
def power(device):
    return str(int(bool(cec.power_status(device))))


@app.route("/standby", methods=['POST'])
def standby():
    return {'status': cec.standby()}


@app.route("/<int:device>/activate", methods=['POST'])
def activate(device):
    return {'status': cec.active_source(device)}


def main():
    logging.basicConfig(level=logging.DEBUG)
    app.run(host='0.0.0.0', debug=True, port=3308)


