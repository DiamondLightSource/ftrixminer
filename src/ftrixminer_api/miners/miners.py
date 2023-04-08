# Use standard logging in this module.
import logging

# Exceptions.
from ftrixminer_api.exceptions import NotFound

# Types.
from ftrixminer_api.miners.constants import Types

# Class managing list of things.
from ftrixminer_api.things import Things

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------------------
__default_ftrixminer_miner = None


def ftrixminer_miners_set_default(ftrixminer_miner):
    global __default_ftrixminer_miner
    __default_ftrixminer_miner = ftrixminer_miner


def ftrixminer_miners_get_default():
    global __default_ftrixminer_miner
    if __default_ftrixminer_miner is None:
        raise RuntimeError("ftrixminer_miners_get_default instance is None")
    return __default_ftrixminer_miner


# -----------------------------------------------------------------------------------------


class Miners(Things):
    """
    List of available ftrixminer_miners.
    """

    # ----------------------------------------------------------------------------------------
    def __init__(self, name=None):
        Things.__init__(self, name)

    # ----------------------------------------------------------------------------------------
    def build_object(self, specification):
        """"""

        ftrixminer_miner_class = self.lookup_class(specification["type"])

        try:
            ftrixminer_miner_object = ftrixminer_miner_class(specification)
        except Exception as exception:
            raise RuntimeError(
                "unable to build ftrixminer miner object for type %s"
                % (ftrixminer_miner_class)
            ) from exception

        return ftrixminer_miner_object

    # ----------------------------------------------------------------------------------------
    def lookup_class(self, class_type):
        """"""

        if class_type == Types.AIOHTTP:
            from ftrixminer_api.miners.aiohttp import Aiohttp

            return Aiohttp

        if class_type == Types.DIRECT:
            from ftrixminer_lib.miners.direct_poll import DirectPoll

            return DirectPoll

        raise NotFound(f"unable to get ftrixminer miner class for type {class_type}")
