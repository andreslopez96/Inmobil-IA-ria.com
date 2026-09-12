import os
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

from inmobil_iaria.prediction import ModelSpec, predict_properties


class _FixedModel:
    def __init__(self, value):
        self.value = value

    def predict(self, features):
        return np.full(len(features), self.value)


class PredictionTests(unittest.TestCase):
    @patch("inmobil_iaria.prediction.joblib.load")
    def test_models_share_alignment_and_produce_one_clean_schema(self, load):
        load.side_effect = [
            _FixedModel(120),
            ["feature"],
            _FixedModel(120),
            ["feature"],
            _FixedModel(120),
            ["feature"],
        ]
        existing_path = Path(os.devnull)
        specs = tuple(
            ModelSpec(existing_path, existing_path, output, 1.0)
            for output in ("Predicción_RF", "Predicción_Bagging", "Predicción_GB")
        )
        properties = pd.DataFrame(
            [
                {
                    "id": 1,
                    "Localizacion": "Centro",
                    "Precio": 100,
                    "m2_construidos": 80,
                    "m2_utiles": 70,
                    "feature": 3,
                }
            ]
        )

        result = predict_properties(properties, specs)

        self.assertEqual(result.iloc[0]["Diferencia_Ponderada"], 20)
        self.assertEqual(len(result.columns), len(set(result.columns)))
        price_index = result.columns.get_loc("Precio")
        self.assertEqual(
            result.columns[price_index : price_index + 5].tolist(),
            [
                "Precio",
                "Diferencia_Ponderada",
                "Predicción_RF",
                "Predicción_Bagging",
                "Predicción_GB",
            ],
        )


if __name__ == "__main__":
    unittest.main()
