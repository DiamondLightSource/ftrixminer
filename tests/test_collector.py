import asyncio
import logging
import os
import time

# Things xchembku provides.
from xchembku_api.datafaces.context import Context as XchembkuDatafaceClientContext
from xchembku_api.datafaces.datafaces import xchembku_datafaces_get_default

# Client context creator.
from rockminer_api.miners.context import Context as MinerClientContext

# Server context creator.
from rockminer_lib.miners.context import Context as MinerServerContext

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

        miner_specification = multiconf_dict["rockminer_miner_specification"]
        # Make the server context.
        miner_server_context = MinerServerContext(miner_specification)

        # Make the client context.
        miner_client_context = MinerClientContext(miner_specification)

        image_count = 2

        # Start the client context for the direct access to the xchembku.
        async with xchembku_client_context:
            # Start the miner client context.
            async with miner_client_context:
                # And the miner server context which starts the coro.
                async with miner_server_context:
                    await self.__run_part1(image_count, constants, output_directory)

                logger.debug(
                    "------------ restarting miner server --------------------"
                )

                # Start the server again.
                # This covers the case where miner starts by finding existing entries in the database and doesn't double-collect those on disk.
                async with miner_server_context:
                    await self.__run_part2(image_count, constants, output_directory)

    # ----------------------------------------------------------------------------------------

    async def __run_part1(self, image_count, constants, output_directory):
        """ """
        # Reference the xchembku object which the context has set up as the default.
        xchembku = xchembku_datafaces_get_default()

        # Make the scrapable directory.
        images_directory = f"{output_directory}/images"
        os.makedirs(images_directory)

        # Get list of images before we create any of the scrape-able files.
        records = await xchembku.fetch_crystal_wells_filenames()

        assert len(records) == 0, "images before any scraping"

        # Create a few scrape-able files.
        for i in range(10, 10 + image_count):
            filename = f"{images_directory}/%06d.jpg" % (i)
            with open(filename, "w") as stream:
                stream.write("")

        # Wait for all the images to appear.
        time0 = time.time()
        timeout = 5.0
        while True:

            # Get all images.
            records = await xchembku.fetch_crystal_wells_filenames()

            # Stop looping when we got the images we expect.
            if len(records) >= image_count:
                break

            if time.time() - time0 > timeout:
                raise RuntimeError(
                    f"only {len(records)} images out of {image_count}"
                    f" registered within {timeout} seconds"
                )
            await asyncio.sleep(1.0)

        # Wait a couple more seconds to make sure there are no extra images appearing.
        await asyncio.sleep(2.0)
        # Get all images.
        records = await xchembku.fetch_crystal_wells_filenames()

        assert len(records) == image_count, "images after scraping"

    # ----------------------------------------------------------------------------------------

    async def __run_part2(self, image_count, constants, output_directory):
        """ """
        # Reference the xchembku object which the context has set up as the default.
        xchembku = xchembku_datafaces_get_default()

        await asyncio.sleep(2.0)
        # Get all images after servers start up and run briefly.
        records = await xchembku.fetch_crystal_wells_filenames()

        assert len(records) == image_count, "images after restarting scraper"
