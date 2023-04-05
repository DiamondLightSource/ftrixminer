import asyncio

# Use standard logging in this module.
import logging
from collections import OrderedDict

import pytds
from dls_utilpack.describe import describe
from dls_utilpack.explain import explain

# Xchembku client context.
from xchembku_api.datafaces.context import Context as XchembkuDatafacesContext

# Base class for cli subcommands.
from rockminer_cli.subcommands.base import ArgKeywords, Base

# Rockminer context creator.
from rockminer_lib.miners.context import Context

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

        mssql = configuration["rockminer_mssql"]

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
            " Plate.Barcode AS barcode,"
            " experiment_node.Name AS visit"
            " FROM Plate"
            " JOIN Experiment ON experiment.ID = plate.experimentID"
            " JOIN TreeNode AS experiment_node ON experiment_node.ID = Experiment.TreeNodeID"
            " JOIN TreeNode AS plate_type_node ON plate_type_node.ID = experiment_node.ParentID"
            " JOIN TreeNode AS projects_folder_node ON projects_folder_node.ID = plate_type_node.ParentID"
            " WHERE projects_folder_node.Name = 'xchem'"
            " AND plate_type_node.NAME IN ('SWISSci_3drop')"
        )

        for record in records:
            logger.debug(
                f"plate {record['id']} barcode {record['barcode']}, visit {record['visit']}"
            )
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

        return

        # Plate's treenode is "ExperimentPlate".
        # Parent of ExperimentPlate is "Experiment".
        # Parent of Experiment is "Project", aka plate type.
        # Parent of Project is "ProjectsFolder", we only care about "XChem"
        # Get all xchem barcodes and the associated experiment name.
        c.execute(
            "SELECT DISTINCT "
            "TN1.Type, "
            "TN1.Name, "
            "TN2.Type, "
            "TN2.Name, "
            "TN3.Type, "
            "TN3.Name, "
            "TN4.Type, "
            "TN4.Name "
            "From Plate "
            "INNER JOIN TreeNode TN1 ON Plate.TreeNodeID = TN1.ID "
            "INNER JOIN TreeNode TN2 ON TN1.ParentID = TN2.ID "
            "INNER JOIN TreeNode TN3 ON TN2.ParentID = TN3.ID "
            "INNER JOIN TreeNode TN4 ON TN3.ParentID = TN4.ID "
            "WHERE TN4.Name IN ('Xchem', 'XChem') "
            "AND TN3.NAME IN ('SWISSci_3drop')"
        )

        for row in c.fetchall():
            project = row[5]
            experiment = row[3]
            logger.debug(f"plate type {project}, visit {experiment}")
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

        return

        plate_types = []
        for row in c.fetchall():
            plate_types.append(str(row[4]))
        # get all plate types
        plate_types = list(set(plate_types))
        # lists to hold barcode
        logger.info(describe("plate_types", plate_types))

        # lists to hold barcodes and plate types
        barcodes = []
        plates = []

        for plate in plate_types:

            # For each plate type, find all of the relevant barcodes
            c.execute(
                "SELECT Barcode FROM Plate "
                "INNER JOIN ExperimentPlate ep ON ep.PlateID = Plate.ID "
                "INNER JOIN ImagingTask it ON it.ExperimentPlateID = ep.ID "
                "INNER JOIN TreeNode as TN1 ON Plate.TreeNodeID = TN1.ID "
                "INNER JOIN TreeNode as TN2 ON TN1.ParentID = TN2.ID "
                "INNER JOIN TreeNode as TN3 ON TN2.ParentID = TN3.ID "
                "INNER JOIN TreeNode as TN4 ON TN3.ParentID = TN4.ID "
                "where TN4.Name='Xchem' AND TN3.Name like %s "
                "and it.DateImaged >= Convert(datetime, DATEADD(DD, -15, GETDATE()))",
                (str("%" + plate + "%"),),
            )

            rows = c.fetchall()

            # logger.info(f"plate {plate} has {len(rows)} rows")
            for row in rows:
                # translate the name from RockMaker (UI) strange folders to 2drop or 3drop (in transfer parameter)
                if plate in self.translate.keys():
                    plates.append(self.translate[plate])
                    barcodes.append(str(row[0]))

        logger.info(describe("plates", plates))
        logger.info(describe("barcodes", barcodes))

        for barcode in barcodes:
            c.execute(
                "SELECT DISTINCT "
                "w.PlateID, ib.ID, w.WellNumber, cpv.CaptureProfileID,  "
                "w.RowLetter, w.ColumnNumber, wd.DropNumber, "
                "crp.Value, it.DateImaged "
                "from Well w INNER JOIN Plate p ON w.PlateID = p.ID "
                "INNER JOIN WellDrop wd ON wd.WellID = w.id "
                "INNER JOIN ExperimentPlate ep ON ep.PlateID = p.ID "
                "INNER JOIN ImagingTask it ON it.ExperimentPlateID = ep.ID "
                "INNER JOIN ImageBatch ib ON ib.ImagingTaskID = it.ID "
                "INNER JOIN CaptureResult cr ON cr.ImageBatchID = ib.ID "
                "INNER JOIN CaptureProfileVersion cpv ON cpv.ID = cr.CaptureProfileVersionID "
                "INNER JOIN CaptureResultProperty crp on CaptureResultID = cr.ID "
                "WHERE p.Barcode=%s AND crp.Value like %s",
                (str(barcode), "%RI1000%"),
            )

            # add all info to results dict
            for row in c.fetchall():
                results = {}
                results["PlateID"] = str(row[0])
                results["BatchID"] = str(row[1])
                results["WellNum"] = str(row[2])
                results["ProfileID"] = str(row[3])
                results["WellRowLetter"] = str(row[4])
                results["WellColNum"] = str(row[5])
                results["DropNum"] = str(row[6])
                results["ImagerName"] = str(row[7])
                results["DateImaged"] = str(row[8].date())
                logger.info(describe("results", results))
                break

            break

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
