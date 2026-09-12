import tempfile
import unittest
from pathlib import Path

import pandas as pd

from inmobil_iaria.notifications import reports_by_client


class NotificationTests(unittest.TestCase):
    def test_groups_each_selected_report_for_its_interested_clients(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "101" / "report.pdf"
            second = root / "102" / "report.pdf"
            first.parent.mkdir()
            second.parent.mkdir()
            first.write_bytes(b"pdf")
            second.write_bytes(b"pdf")
            selected = pd.DataFrame(
                [
                    {"id": 101, "Clientes_Interesados": "['cliente-a']"},
                    {
                        "id": 102,
                        "Clientes_Interesados": "['cliente-a', 'cliente-b']",
                    },
                ]
            )

            grouped = reports_by_client(selected, [first, second])

        self.assertEqual(grouped["cliente-a"], [first, second])
        self.assertEqual(grouped["cliente-b"], [second])


if __name__ == "__main__":
    unittest.main()
