import enum


class CallStatusType(str, enum.Enum):
    success = "success"
    failure = "failure"


class ResponseType(str, enum.Enum):
    accept = "accept"
    reject = "reject"
