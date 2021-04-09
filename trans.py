from . import MatchTrans, FormatTrans

class Trans():
    def __init__(self, template, forward=None, reverse=None, format=None, match=None, strict=False, debug=False):
        '''
        forward and format are the same function. Only one can be defined at a time.
        reverse and match are the same function. Only one can be defined at a time.
        '''
        if not reverse and not forward and not format and not match:
            raise Exception("(forward/format) or/and (reverse/match) transformation function must be present")

        self.match = None
        self.format = None
        self.template = template
        if reverse:
            self.match = MatchTrans(template, reverse, strict, debug)
        elif match:
            self.match = MatchTrans(template, match, strict, debug)
        if forward:
            self.format = FormatTrans(template, forward, strict, debug)
        elif format:
            self.format = FormatTrans(template, format, strict, debug)


    def transform(self, *args, dir='v', **kwargs):
        if dir == 'format' and self.format:
            return self.format.transform(*args, **kwargs)
        elif dir == 'match' and self.match:
            return self.match.transform(*args, **kwargs)
