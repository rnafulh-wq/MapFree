class Event:
    def __init__(self, type_, message=None, progress=None):
        self.type = type_
        self.message = message
        self.progress = progress
