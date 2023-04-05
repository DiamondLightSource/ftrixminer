import asyncio

# Use standard logging in this module.
import logging

import pytds
from dls_utilpack.describe import describe

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
        conn = pytds.connect(
            mssql["server"],
            mssql["database"],
            mssql["username"],
            mssql["password"],
        )
        c = conn.cursor()

        # find the directory names corresponding to plate types for all entries in the XChem folder
        # XChem
        # |- Plate Type (e.g. SwissSci3D)
        #    |- Barcode
        #       |- Data
        c.execute(
            "SELECT TN3.Name as 'Name' From Plate "
            "INNER JOIN TreeNode TN1 ON Plate.TreeNodeID = TN1.ID "
            "INNER JOIN TreeNode TN2 ON TN1.ParentID = TN2.ID "
            "INNER JOIN TreeNode TN3 ON TN2.ParentID = TN3.ID "
            "INNER JOIN TreeNode TN4 ON TN3.ParentID = TN4.ID "
            "where TN4.Name='Xchem'"
        )

        plate_types = []
        for row in c.fetchall():
            plate_types.append(str(row[0]))
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
