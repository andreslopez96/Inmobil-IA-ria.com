import tempfile
import unittest
from pathlib import Path

from inmobil_iaria.storage import read_csv_flexible


class FlexibleCsvTests(unittest.TestCase):
    def test_reads_a_single_id_column_without_inventing_a_separator(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ids.csv"
            path.write_text("id\n452404\n94779582\n", encoding="utf-8")

            frame = read_csv_flexible(path)

        self.assertEqual(list(frame.columns), ["id"])
        self.assertEqual(frame["id"].tolist(), [452404, 94779582])


if __name__ == "__main__":
    unittest.main()
