from importlib.metadata import version

__version__ = version("ftrixminer")
del version

__all__ = ["__version__"]
