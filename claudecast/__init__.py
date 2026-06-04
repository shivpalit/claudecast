from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("claudecast")
except PackageNotFoundError:
    __version__ = "unknown"
