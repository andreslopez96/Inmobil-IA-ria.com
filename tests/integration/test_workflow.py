import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import joblib
import numpy as np

from inmobil_iaria.config import AppConfig, ProjectPaths
from inmobil_iaria.domain.properties import RawProperty
from inmobil_iaria.sources.fixture import FixtureSource
from inmobil_iaria.storage import read_csv
from inmobil_iaria.workflow import collect_new_properties, run_core


class _FixedModel:
    def __init__(self, value):
        self.value = value

    def predict(self, features):
        return np.full(len(features), self.value)


class WorkflowIntegrationTests(unittest.TestCase):
    def test_collection_preserves_a_single_column_id_registry(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            paths = ProjectPaths(root)
            paths.raw_data.mkdir(parents=True)
            paths.ids.write_text("id\n452404\n94779582\n", encoding="utf-8")
            source = FixtureSource(
                [
                    RawProperty(
                        id=123,
                        Titulo="Piso",
                        Localizacion="Centro",
                        Precio=100000,
                        Caracteristicas_basicas="80 m² construidos",
                    )
                ]
            )

            new_ids = collect_new_properties(paths, source)
            stored_ids = set(read_csv(paths.ids)["id"].astype(int))

        self.assertEqual(new_ids, [123])
        self.assertEqual(stored_ids, {123, 452404, 94779582})

    def test_complete_workflow_uses_fixtures_without_network_or_latex(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            paths = ProjectPaths(root)
            (root / "config").mkdir()
            (root / "data" / "private").mkdir(parents=True)
            (root / "assets" / "reports").mkdir(parents=True)

            registry = {"models": []}
            for name, legacy, output in (
                ("random_forest", "random_forest_venta.pkl", "Predicción_RF"),
                ("bagging", "bagging_venta.pkl", "Predicción_Bagging"),
                ("gradient_boosting", "gb_venta.pkl", "Predicción_GB"),
            ):
                model_dir = root / "models" / name
                model_dir.mkdir(parents=True)
                joblib.dump(_FixedModel(130000), model_dir / "model.pkl")
                (model_dir / "metadata.json").write_text(
                    json.dumps(
                        {
                            "feature_columns": ["m2_construidos"],
                            "metrics": {"mse": 1.0},
                        }
                    ),
                    encoding="utf-8",
                )
                registry["models"].append(
                    {
                        "name": name,
                        "directory": name,
                        "legacy_model": legacy,
                        "legacy_columns": "unused.pkl",
                        "output": output,
                        "active": True,
                    }
                )
            (root / "config" / "model_registry.yaml").write_text(
                json.dumps(registry), encoding="utf-8"
            )
            (root / "config" / "matching_rules.yaml").write_text(
                json.dumps(
                    {
                        "thresholds": {
                            "default": {"areas": [], "bands": [], "default_ratio": 0}
                        },
                        "selected_values": ["1", "true", "yes", "si", "x"],
                    }
                ),
                encoding="utf-8",
            )
            (root / "data" / "private" / "clients.csv").write_text(
                "id;nombre;email;precio_min;precio_max;m2_min;habitaciones_min;baños_min;barrios_interes\n"
                "demo;Demo;demo@example.invalid;50000;150000;50;2;1;Centro\n",
                encoding="utf-8",
            )
            (root / "assets" / "reports" / "template.tex").write_text(
                "ID={{ID}} PRECIO={{PRECIO}}", encoding="utf-8"
            )

            config = AppConfig.from_env(root)
            source = FixtureSource(
                [
                    RawProperty(
                        id=123,
                        Titulo="Piso",
                        Localizacion="Centro",
                        Precio=100000,
                        Caracteristicas_basicas=(
                            "80 m² construidos; 70 m² útiles; 2 habitaciones; "
                            "1 baño; Segunda mano/buen estado; exterior"
                        ),
                    )
                ]
            )

            result = run_core(
                config,
                source=source,
                auto_approve=True,
                compile_pdf=False,
                send=False,
                prepare_assets=False,
            )

            self.assertEqual(result.status, "reports_generated")
            self.assertEqual(result.new_properties, 1)
            self.assertEqual(result.opportunities, 1)
            self.assertEqual(result.reports, 1)
            self.assertEqual(read_csv(paths.review).iloc[0]["Titulo"], "Piso")
            self.assertTrue((root / "artifacts" / "reports" / "123" / "source.tex").exists())


if __name__ == "__main__":
    unittest.main()
