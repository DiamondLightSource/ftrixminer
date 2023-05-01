import asyncio
import logging
from typing import List

import pytds
from dls_utilpack.callsign import callsign
from dls_utilpack.explain import explain2
from dls_utilpack.require import require

# Crystal plate constants.
from xchembku_api.crystal_plate_objects.constants import TREENODE_NAMES_TO_THING_TYPES

# Dataface client context.
from xchembku_api.datafaces.context import Context as XchembkuDatafaceClientContext
from xchembku_api.models.crystal_plate_filter_model import CrystalPlateFilterModel

# Crystal well pydantic model.
from xchembku_api.models.crystal_plate_model import CrystalPlateModel

# Base class for miner instances.
from ftrixminer_lib.miners.base import Base as MinerBase

logger = logging.getLogger(__name__)

thing_type = "ftrixminer_lib.miners.direct_poll"


# ------------------------------------------------------------------------------------------
class DirectPoll(MinerBase):
    """
    Object representing plate miner.
    The behavior is to start a coro task to waken every few seconds and scan for new plates.
    Files are pushed to xchembku.
    """

    # ----------------------------------------------------------------------------------------
    def __init__(self, specification, predefined_uuid=None):
        MinerBase.__init__(
            self, thing_type, specification, predefined_uuid=predefined_uuid
        )

        s = f"{callsign(self)} specification", self.specification()

        type_specific_tbd = require(s, self.specification(), "type_specific_tbd")
        self.__mssql = require(s, type_specific_tbd, "mssql")
        xchembku_dataface_specification = require(
            s, type_specific_tbd, "xchembku_dataface_specification"
        )

        # Create a dataface context objectwhere we push new plates discovered.
        self.__xchembku_client_context = XchembkuDatafaceClientContext(
            xchembku_dataface_specification
        )

        # Activate the context later.
        self.__xchembku = None

        # This flag will stop the ticking async task.
        self.__keep_ticking = True
        self.__tick_future = None

        self.__latest_formulatrix__plate__id = 0

    # ----------------------------------------------------------------------------------------
    async def activate(self) -> None:
        """
        Activate the object.

        This implementation gets the list of filenames already known to the xchembku.

        Then it starts the coro task to awaken every few seconds to scrape the directories.
        """

        # Activate the context.
        await self.__xchembku_client_context.aenter()

        # Get a reference to the xchembku interface provided by the context.
        self.__xchembku = self.__xchembku_client_context.get_interface()

        # Get latest plate we already have in the database.
        # This allows us to query mssql for just plates that are newer.
        crystal_plate_models = await self.__xchembku.fetch_crystal_plates(
            CrystalPlateFilterModel(limit=1, direction=-1),
            why="latest plate we already have in the database",
        )
        if len(crystal_plate_models) > 0:
            self.__latest_formulatrix__plate__id = crystal_plate_models[
                0
            ].formulatrix__plate__id

        # Poll periodically.
        self.__tick_future = asyncio.get_event_loop().create_task(self.tick())

    # ----------------------------------------------------------------------------------------
    async def deactivate(self) -> None:
        """
        Deactivate the object.

        Causes the coro task to stop.

        This implementation then releases resources relating to the xchembku connection.
        """

        if self.__tick_future is not None:
            # Set flag to stop the periodic ticking.
            self.__keep_ticking = False
            # Wait for the ticking to stop.
            await self.__tick_future

        # Forget we have an xchembku client reference.
        self.__xchembku = None

        if self.__xchembku_client_context is not None:
            await self.__xchembku_client_context.aexit()
            self.__xchembku_client_context = None

    # ----------------------------------------------------------------------------------------
    async def tick(self) -> None:
        """
        A coro task which does periodic checking for new files in the directories.

        Stops when flag has been set by other tasks.

        # TODO: Use an event to awaken ticker early to handle stop requests sooner.
        """

        while self.__keep_ticking:
            try:
                await self.discover()
            except Exception as exception:
                logger.error(explain2(exception, "scraping"), exc_info=exception)

            # TODO: Make periodic tick period to be configurable.
            await asyncio.sleep(1.0)

    # ----------------------------------------------------------------------------------------
    async def discover(self) -> None:
        """
        Scrape discover new plates in the Formulatrix database.
        """

        # Query mssql or dummy.
        rows = await self.query()

        logger.debug(f"[FTRIXMINER POLL] discovered {len(rows)} new plate rows")

        # Loop over the rows we got back from the query.
        for row in rows:
            formulatrix__plate__id = int(row[0])
            thing_type = TREENODE_NAMES_TO_THING_TYPES.get(row[3])
            if thing_type is None:
                raise RuntimeError(f"programming error: plate type {row[3]} unexpected")
            crystal_plate_model = CrystalPlateModel(
                barcode=str(row[1]),
                visit=str(row[2]),
                thing_type=thing_type,
                formulatrix__plate__id=formulatrix__plate__id,
            )

            # Add plate to our database.
            # I don't worry about performance hit of adding plates one by one with upsert
            # since new plates don't get added very often.
            await self.__xchembku.upsert_crystal_plates([crystal_plate_model])

            self.__latest_formulatrix__plate__id = formulatrix__plate__id

    # ----------------------------------------------------------------------------------------
    async def query(self) -> List[List]:
        """
        Read dummy data from configuration.
        """

        server = self.__mssql["server"]

        if server == "dummy":
            return await self.query_dummy()
        else:
            return await self.query_mssql()

    # ----------------------------------------------------------------------------------------
    async def query_mssql(self) -> List[List]:
        """
        Scrape discover new plates in the Formulatrix database.
        """

        # Connect to the RockMaker database at every tick.
        # TODO: Handle failure to connect to RockMaker database.
        connection = pytds.connect(
            self.__mssql["server"],
            self.__mssql["database"],
            self.__mssql["username"],
            self.__mssql["password"],
        )

        # Select only plate types we care about.
        treenode_names = [
            f"'{str(name)}'" for name in list(TREENODE_NAMES_TO_THING_TYPES.keys())
        ]

        # Plate's treenode is "ExperimentPlate".
        # Parent of ExperimentPlate is "Experiment", aka visit
        # Parent of Experiment is "Project", aka plate type.
        # Parent of Project is "ProjectsFolder", we only care about "XChem"
        # Get all xchem barcodes and the associated experiment name.
        sql = (
            "SELECT"
            " Plate.ID AS id,"
            " Plate.Barcode AS barcode,"
            " experiment_node.Name AS visit,"
            " plate_type_node.Name AS plate_type"
            " FROM Plate"
            " JOIN Experiment ON experiment.ID = plate.experimentID"
            " JOIN TreeNode AS experiment_node ON experiment_node.ID = Experiment.TreeNodeID"
            " JOIN TreeNode AS plate_type_node ON plate_type_node.ID = experiment_node.ParentID"
            " JOIN TreeNode AS projects_folder_node ON projects_folder_node.ID = plate_type_node.ParentID"
            f" WHERE Plate.ID > {self.__latest_formulatrix__plate__id}"
            " AND projects_folder_node.Name = 'xchem'"
            f" AND plate_type_node.Name IN ({',' .join(treenode_names)})"
        )

        cursor = connection.cursor()
        cursor.execute(sql)
        rows = cursor.fetchall()

        return rows

    # ----------------------------------------------------------------------------------------
    async def query_dummy(self) -> List[List]:
        """
        Read dummy data from configuration.
        """

        database = self.__mssql["database"]
        records = self.__mssql[database]

        # Keep only records that haven't been queried before.
        new_records = []
        for record in records:
            if record[0] > self.__latest_formulatrix__plate__id:
                new_records.append(record)

        return new_records

    # ----------------------------------------------------------------------------------------
    async def close_client_session(self):
        """"""

        pass
