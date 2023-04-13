import asyncio

# Use standard logging in this module.
import logging
from collections import OrderedDict

import pytds
from dls_utilpack.explain import explain
from prettytable import PrettyTable

# Base class for cli subcommands.
from ftrixminer_cli.subcommands.base import ArgKeywords, Base

logger = logging.getLogger()


# Messages about starting and stopping services.
logging.getLogger("pytds").setLevel("WARNING")


# --------------------------------------------------------------
class Explore1(Base):
    """
    Start single service and keep running until ^C or remotely requested shutdown.
    """

    # this translates the directory names in RockMaker to names for the pipeline
    translate = {
        "SWISSci_2drop": "2drop",
        "SWISSci_3Drop": "3drop",
        "SWISSci_3drop": "3drop",
        "Mitegen_insitu1": "mitegen",
        "MiTInSitu": "mitegen",
    }

    def __init__(self, args, mainiac):
        super().__init__(args)

    # ----------------------------------------------------------------------------------------
    def run(self):
        """ """

        # Run in asyncio event loop.
        asyncio.run(self.__run_coro())

    # ----------------------------------------------------------
    async def __run_coro(self):
        """"""

        # Load the configuration.
        multiconf = self.get_multiconf(vars(self._args))
        configuration = await multiconf.load()

        mssql = configuration["ftrixminer_mssql"]

        # connect to the RockMaker database
        self.__connection = pytds.connect(
            mssql["server"],
            mssql["database"],
            mssql["username"],
            mssql["password"],
        )

        # Plate's treenode is "ExperimentPlate".
        # Parent of ExperimentPlate is "Experiment", aka visit
        # Parent of Experiment is "Project", aka plate type.
        # Parent of Project is "ProjectsFolder", we only care about "XChem"
        # Get all xchem barcodes and the associated experiment name.
        records = self.query(
            "SELECT"
            " Plate.ID AS id,"
            " plate_type_node.Name AS plate_type,"
            " Plate.Barcode AS barcode,"
            " experiment_node.Name AS visit"
            " FROM Plate"
            " JOIN Experiment ON experiment.ID = plate.experimentID"
            " JOIN TreeNode AS experiment_node ON experiment_node.ID = Experiment.TreeNodeID"
            " JOIN TreeNode AS plate_type_node ON plate_type_node.ID = experiment_node.ParentID"
            " JOIN TreeNode AS projects_folder_node ON projects_folder_node.ID = plate_type_node.ParentID"
            " WHERE projects_folder_node.Name = 'xchem'"
            " AND plate_type_node.Name IN ('SWISSci_3drop')"
        )

        fields = ["id", "plate_type", "barcode", "visit"]
        table = PrettyTable(fields)
        for record in records:
            values = []
            for field in fields:
                values.append(record[field])
            table.add_row(values)
        logger.info(f"\n{table.get_string()}")

        # logger.debug(
        #     "%s=%s %s=%s %s=%s %s=%s"
        #     % (
        #         row[6],
        #         row[7],
        #         row[4],
        #         row[5],
        #         row[2],
        #         row[3],
        #         row[0],
        #         row[1],
        #     )
        # )

        # Plate's treenode is "ExperimentPlate".
        # Parent of ExperimentPlate is "Experiment".
        # Parent of Experiment is "Project", aka plate type.
        # Parent of Project is "ProjectsFolder", we only care about "XChem"
        # Get all xchem barcodes and the associated experiment name.
        # c.execute(
        #     "SELECT DISTINCT "
        #     "TN1.Type, "
        #     "TN1.Name, "
        #     "TN2.Type, "
        #     "TN2.Name, "
        #     "TN3.Type, "
        #     "TN3.Name, "
        #     "TN4.Type, "
        #     "TN4.Name "
        #     "From Plate "
        #     "INNER JOIN TreeNode TN1 ON Plate.TreeNodeID = TN1.ID "
        #     "INNER JOIN TreeNode TN2 ON TN1.ParentID = TN2.ID "
        #     "INNER JOIN TreeNode TN3 ON TN2.ParentID = TN3.ID "
        #     "INNER JOIN TreeNode TN4 ON TN3.ParentID = TN4.ID "
        #     "WHERE TN4.Name IN ('Xchem', 'XChem') "
        #     "AND TN3.NAME IN ('SWISSci_3drop')"
        # )

        # for row in c.fetchall():
        #     project = row[5]
        #     experiment = row[3]
        #     logger.debug(f"plate type {project}, visit {experiment}")

    # ----------------------------------------------------------------------------------------
    def query(self, sql, subs=None, why=None):

        if subs is None:
            subs = []

        try:
            cursor = self.__connection.cursor()
            cursor.execute(sql, subs)
            rows = cursor.fetchall()
            cols = []
            for col in cursor.description:
                cols.append(col[0])

            if why is None:
                logger.debug("%d records from: %s" % (len(rows), sql))
            else:
                logger.debug("%d records from %s: %s" % (len(rows), why, sql))
            records = []
            for row in rows:
                record = OrderedDict()
                for index, col in enumerate(cols):
                    record[col] = row[index]
                records.append(record)
            return records
        except Exception as exception:
            if why is None:
                raise RuntimeError(explain(exception, f"executing {sql}"))
            else:
                raise RuntimeError(explain(exception, f"executing {why}: {sql}"))
        finally:
            if cursor is not None:
                cursor.close()

    # ----------------------------------------------------------
    def add_arguments(parser):

        parser.add_argument(
            "--configuration",
            "-c",
            help="Configuration file.",
            type=str,
            metavar="yaml filename",
            default=None,
            dest=ArgKeywords.CONFIGURATION,
        )

        return parser
