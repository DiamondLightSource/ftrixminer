import asyncio
import logging
import time

# Things xchembku provides.
from xchembku_api.datafaces.context import Context as XchembkuDatafaceClientContext
from xchembku_api.datafaces.datafaces import xchembku_datafaces_get_default
from xchembku_api.models.crystal_plate_filter_model import CrystalPlateFilterModel

# Crystal plate objects factory.
from xchembku_lib.crystal_plate_objects.crystal_plate_objects import CrystalPlateObjects

# Client context creator.
from ftrixminer_api.miners.context import Context as MinerClientContext

# Server context creator.
from ftrixminer_lib.miners.context import Context as MinerServerContext

# Base class for the tester.
from tests.base import Base

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------------------------
class TestMinerDirectPoll:
    """
    Test miner interface by direct call.
    """

    def test(self, constants, logging_setup, output_directory):

        # Configuration file to use.
        configuration_file = "tests/configurations/direct_poll.yaml"

        MinerTester().main(constants, configuration_file, output_directory)


# ----------------------------------------------------------------------------------------
class TestMinerService:
    """
    Test miner interface through network interface.
    """

    def test(self, constants, logging_setup, output_directory):

        # Configuration file to use.
        configuration_file = "tests/configurations/service.yaml"

        MinerTester().main(constants, configuration_file, output_directory)


# ----------------------------------------------------------------------------------------
class MinerTester(Base):
    """
    Test scraper miner's ability to automatically discover files and push them to xchembku.
    """

    # ----------------------------------------------------------------------------------------
    async def _main_coroutine(self, constants, output_directory):
        """ """

        # Get the multiconf from the testing configuration yaml.
        multiconf = self.get_multiconf()

        # Load the multiconf into a dict.
        multiconf_dict = await multiconf.load()

        # Reference the dict entry for the xchembku dataface.
        xchembku_dataface_specification = multiconf_dict[
            "xchembku_dataface_specification"
        ]

        # Make the xchembku client context, expected to be direct (no server).
        xchembku_client_context = XchembkuDatafaceClientContext(
            xchembku_dataface_specification
        )

        miner_specification = multiconf_dict["ftrixminer_miner_specification"]
        # Make the server context.
        miner_server_context = MinerServerContext(miner_specification)

        # Make the client context.
        miner_client_context = MinerClientContext(miner_specification)

        plate_count = 2

        # Start the client context for the direct access to the xchembku.
        async with xchembku_client_context:
            # Start the miner client context.
            async with miner_client_context:
                # And the miner server context which starts the coro.
                async with miner_server_context:
                    await self.__run_part1(plate_count, constants, output_directory)

                logger.debug(
                    "------------ restarting miner server --------------------"
                )

                # Start the server again.
                # This covers the case where miner starts by finding existing entries in the database and doesn't double-collect those on disk.
                async with miner_server_context:
                    await self.__run_part2(plate_count, constants, output_directory)

    # ----------------------------------------------------------------------------------------

    async def __run_part1(self, plate_count, constants, output_directory):
        """ """
        # Reference the xchembku object which the context has set up as the default.
        xchembku = xchembku_datafaces_get_default()

        # Filter get all crystal plates.
        filter = CrystalPlateFilterModel()

        # Wait for all the plates to appear.
        time0 = time.time()
        timeout = 5.0
        while True:

            # Get all images.
            models = await xchembku.fetch_crystal_plates(filter)

            # Stop looping when we got the images we expect.
            if len(models) >= plate_count:
                break

            if time.time() - time0 > timeout:
                raise RuntimeError(
                    f"only {len(models)} images out of {plate_count}"
                    f" registered within {timeout} seconds"
                )
            await asyncio.sleep(1.0)

        assert len(models) == plate_count, "plates after mining"

        # Make sure that the model which came out of the database can be instantiated.
        specification = {"type": models[0].thing_type}
        o = CrystalPlateObjects().build_object(specification)
        assert o.get_well_count() == 288

    # ----------------------------------------------------------------------------------------

    async def __run_part2(self, plate_count, constants, output_directory):
        """ """
        # Reference the xchembku object which the context has set up as the default.
        xchembku = xchembku_datafaces_get_default()

        await asyncio.sleep(2.0)
        # Get all images after servers start up and run briefly.
        filter = CrystalPlateFilterModel()
        records = await xchembku.fetch_crystal_plates(filter)

        assert len(records) == plate_count, "plates after restarting miner"
