from importlib.metadata import version

__version__ = version("rockminer")
del version

__all__ = ["__version__"]
