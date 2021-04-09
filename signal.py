
class S():
    def __init__(self, key):
        self.key = key

    def __str__(self):
        return f"{self.__class__.__name__}({self.key})"

    def __repr__(self):
        return f"{self.__class__.__name__}({self.key})"
