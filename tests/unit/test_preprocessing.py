import unittest

import pandas as pd

from inmobil_iaria.preprocessing import merge_properties, transform_properties


class PreprocessingTests(unittest.TestCase):
    def test_transform_extracts_model_features(self):
        raw = pd.DataFrame(
            [
                {
                    "id": 10,
                    "Titulo": "Piso",
                    "Localizacion": "Centro",
                    "Precio": 100000,
                    "Caracteristicas_basicas": (
                        "90 m² construidos; 80 m² útiles; 3 habitaciones; "
                        "2 baños; Segunda mano/buen estado; Planta 4; exterior; "
                        "con ascensor; Terraza; Orientación sur; construido en 1998"
                    ),
                    "Caracteristicas_extra": "Piscina; Jardín; Aire acondicionado",
                }
            ]
        )

        result = transform_properties(raw).iloc[0]

        self.assertEqual(result["m2_construidos"], 90)
        self.assertEqual(result["m2_utiles"], 80)
        self.assertEqual(result["habitaciones"], 3)
        self.assertEqual(result["banos"], 2)
        self.assertEqual(result["planta_numero"], 4)
        self.assertEqual(result["ascensor"], 1)
        self.assertEqual(result["orientacion_sur"], 1)
        self.assertEqual(result["piscina"], 1)
        self.assertNotIn("Caracteristicas_basicas", result.index)

    def test_merge_keeps_the_newest_version_of_an_id(self):
        old = pd.DataFrame([{"id": 1, "Precio": 100}, {"id": 2, "Precio": 200}])
        new = pd.DataFrame([{"id": 1, "Precio": 150}])

        result = merge_properties(old, new)

        self.assertEqual(len(result), 2)
        self.assertEqual(result.loc[result["id"] == 1, "Precio"].iloc[0], 150)


if __name__ == "__main__":
    unittest.main()

