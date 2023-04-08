# Use standard logging in this module.
import logging

# Exceptions.
from rockminer_api.exceptions import NotFound

# Types.
from rockminer_api.miners.constants import Types

# Class managing list of things.
from rockminer_api.things import Things

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------------------
__default_rockminer_miner = None


def rockminer_miners_set_default(rockminer_miner):
    global __default_rockminer_miner
    __default_rockminer_miner = rockminer_miner


def rockminer_miners_get_default():
    global __default_rockminer_miner
    if __default_rockminer_miner is None:
        raise RuntimeError("rockminer_miners_get_default instance is None")
    return __default_rockminer_miner


# -----------------------------------------------------------------------------------------


class Miners(Things):
    """
    List of available rockminer_miners.
    """

    # ----------------------------------------------------------------------------------------
    def __init__(self, name=None):
        Things.__init__(self, name)

    # ----------------------------------------------------------------------------------------
    def build_object(self, specification):
        """"""

        rockminer_miner_class = self.lookup_class(specification["type"])

        try:
            rockminer_miner_object = rockminer_miner_class(specification)
        except Exception as exception:
            raise RuntimeError(
                "unable to build rockminer miner object for type %s"
                % (rockminer_miner_class)
            ) from exception

        return rockminer_miner_object

    # ----------------------------------------------------------------------------------------
    def lookup_class(self, class_type):
        """"""

        if class_type == Types.AIOHTTP:
            from rockminer_api.miners.aiohttp import Aiohttp

            return Aiohttp

        if class_type == Types.DIRECT:
            from rockminer_lib.miners.direct_poll import DirectPoll

            return DirectPoll

        raise NotFound(f"unable to get rockminer miner class for type {class_type}")
