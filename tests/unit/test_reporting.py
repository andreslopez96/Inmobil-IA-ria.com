import unittest

import pandas as pd

from inmobil_iaria.config import ProjectPaths
from inmobil_iaria.reporting import render_tex


class ReportingTests(unittest.TestCase):
    def test_template_paths_are_portable(self):
        template = (
            r"ID={{ID}} TITLE={{{TITULO}}} "
            r"\includegraphics{/legacy/reports/Positivo_fondo_blanco.png}"
        )
        info = pd.Series(
            {
                "id": 10,
                "Titulo": "Piso exterior & reformado",
                "Localizacion": "Centro",
                "Precio": 100000,
                "Diferencia_Ponderada": 10000,
                "m2_construidos": 90,
                "m2_utiles": 80,
                "habitaciones": 3,
                "banos": 2,
                "estado_vivienda": "Buen estado",
                "ascensor": 1,
                "Calefacción": "individual",
                "ano_construccion": 2000,
            }
        )

        result = render_tex(template, info, ProjectPaths())

        self.assertIn("ID=10", result)
        self.assertIn(r"Piso exterior \& reformado", result)
        self.assertIn("../../../assets/reports/brand.png", result)
        self.assertNotIn("/legacy", result)


if __name__ == "__main__":
    unittest.main()
