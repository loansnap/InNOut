from pydash import _
from . import InNOut

def match(template, data, debug=None):
    return InNOut(template, data, debug)

def format(template, match_obj, debug=None, deepclean=False):
    return match_obj.format(template, debug=debug, deepclean=deepclean)

def transform(data, match_template, format_template, debug=None, deepclean=False):
    return InNOut(match_template, data, debug).format(format_template, debug=debug, deepclean=deepclean)
