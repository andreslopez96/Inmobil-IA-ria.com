import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from inmobil_iaria.matching import match_clients, read_review, selected_properties


class MatchingTests(unittest.TestCase):
    def test_matches_only_new_properties_that_fit_the_client(self):
        properties = pd.DataFrame(
            [
                {
                    "id": 1,
                    "Precio": 100000,
                    "Localizacion": "Centro",
                    "Diferencia_Ponderada": 30000,
                    "Predicción_RF": 105000,
                    "Predicción_Bagging": 105000,
                    "Predicción_GB": 105000,
                    "m2_utiles": 70,
                    "planta_numero": 2,
                    "habitaciones": 2,
                    "banos": 1,
                    "Exterior": 1,
                    "estado_vivienda": "Segunda mano/Buen estado",
                    "terraza": 1,
                },
                {
                    "id": 2,
                    "Precio": 100000,
                    "Localizacion": "Centro",
                    "Diferencia_Ponderada": 30000,
                    "Predicción_RF": 105000,
                    "Predicción_Bagging": 105000,
                    "Predicción_GB": 105000,
                    "m2_utiles": 40,
                    "planta_numero": 1,
                    "habitaciones": 1,
                    "banos": 1,
                    "Exterior": 0,
                    "estado_vivienda": "Segunda mano/Buen estado",
                    "terraza": 0,
                },
            ]
        )
        clients = pd.DataFrame(
            [
                {
                    "id": "c1",
                    "precio_min": 90000,
                    "precio_max": 150000,
                    "m2_min": 60,
                    "m2_max": 100,
                    "planta_min": 1,
                    "planta_max": 5,
                    "habitaciones_min": 2,
                    "baños_min": 1,
                    "exterior": "sí",
                    "barrios_interes": "Centro",
                    "estados_vivienda": "Segunda mano/Buen estado",
                    "extras": "terraza",
                }
            ]
        )

        result = match_clients(properties, clients, [1, 2])

        self.assertEqual(result["id"].tolist(), [1])
        self.assertEqual(result.iloc[0]["Clientes_Interesados"], ["c1"])

    def test_preserves_original_threshold_and_price_boundaries(self):
        properties = pd.DataFrame(
            [
                {
                    "id": 1,
                    "Precio": 100000,
                    "Localizacion": "Centro",
                    "Diferencia_Ponderada": 25000,
                    "Predicción_RF": 125000,
                    "Predicción_Bagging": 125000,
                    "Predicción_GB": 125000,
                    "m2_utiles": 70,
                },
                {
                    "id": 2,
                    "Precio": 100000,
                    "Localizacion": "Centro",
                    "Diferencia_Ponderada": 25001,
                    "Predicción_RF": 125001,
                    "Predicción_Bagging": 125001,
                    "Predicción_GB": 125001,
                    "m2_utiles": 70,
                },
                {
                    "id": 3,
                    "Precio": 80000,
                    "Localizacion": "Centro",
                    "Diferencia_Ponderada": 999999,
                    "Predicción_RF": 999999,
                    "Predicción_Bagging": 999999,
                    "Predicción_GB": 999999,
                    "m2_utiles": 70,
                },
            ]
        )
        clients = pd.DataFrame([{"id": "c1"}])

        result = match_clients(properties, clients, [1, 2, 3])

        self.assertEqual(result["id"].tolist(), [2])

    def test_selected_accepts_spanish_boolean(self):
        review = pd.DataFrame(
            [{"id": 1, "Seleccionado": "Sí"}, {"id": 2, "Seleccionado": "No"}]
        )
        self.assertEqual(selected_properties(review)["id"].tolist(), [1])

    def test_matches_new_build_wording_used_by_the_clients_csv(self):
        properties = pd.DataFrame(
            [
                {
                    "id": 1,
                    "Precio": 100000,
                    "Localizacion": "Centro",
                    "Diferencia_Ponderada": 30000,
                    "Predicción_RF": 130000,
                    "Predicción_Bagging": 130000,
                    "Predicción_GB": 130000,
                    "m2_utiles": 70,
                    "estado_vivienda": "Obra nueva",
                }
            ]
        )
        clients = pd.DataFrame(
            [{"id": "c1", "estados_vivienda": "Promoción de obra nueva"}]
        )

        result = match_clients(properties, clients, [1])

        self.assertEqual(result["id"].tolist(), [1])

    def test_review_accepts_numbers_delimiter_changes(self):
        with TemporaryDirectory() as directory:
            comma_file = Path(directory) / "comma.csv"
            semicolon_file = Path(directory) / "semicolon.csv"
            comma_file.write_text("id,Seleccionado\n1,Sí\n", encoding="utf-8")
            semicolon_file.write_text("id;Seleccionado\n1;Sí\n", encoding="utf-8")

            self.assertEqual(read_review(comma_file).columns.tolist(), ["id", "Seleccionado"])
            self.assertEqual(
                read_review(semicolon_file).columns.tolist(), ["id", "Seleccionado"]
            )


if __name__ == "__main__":
    unittest.main()
