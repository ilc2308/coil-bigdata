"""
test_components.py
Pruebas unitarias para glosa_parser y rule_engine.
"""

import os
import unittest
from src.utils.glosa_parser import parse_glosa, hash_sha256
from src.utils.rule_engine import CoverageRuleEngine

class TestComponents(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        servicios_path = os.path.join(base_dir, "dataset", "COIL_catalogo_servicios_cubiertos.csv")
        perfiles_path = os.path.join(base_dir, "dataset", "COIL_catalogo_perfiles_cobertura.csv")
        cls.engine = CoverageRuleEngine(servicios_path, perfiles_path)

    def test_glosa_parsing_valid(self):
        glosa = "Paciente: Carlos Slim; DNO: DNO-99999999; SeguroSocial: SS-111-22-3333; Edad: 45; PerfilCobertura: PRIORITARIO; ServicioSolicitado: Consulta de medicina general; Medicacion: acetaminofén|ibuprofeno"
        valid, data, err = parse_glosa(glosa)
        self.assertTrue(valid)
        self.assertIsNone(err)
        self.assertEqual(data["paciente"], "Carlos Slim")
        self.assertEqual(data["dno"], "DNO-99999999")
        self.assertEqual(data["edad"], 45)
        self.assertEqual(data["perfil_cobertura"], "PRIORITARIO")
        self.assertEqual(data["servicio_solicitado"], "Consulta de medicina general")
        self.assertEqual(len(data["medicaciones"]), 2)
        # Verificar hash SHA-256
        self.assertEqual(data["dno_hash"], hash_sha256("DNO-99999999"))

    def test_glosa_parsing_invalid(self):
        glosa_invalida = "Paciente: Solo Nombre; DNO: Incompleto"
        valid, data, err = parse_glosa(glosa_invalida)
        self.assertFalse(valid)
        self.assertIsNotNone(err)

    def test_coverage_prioritario_100(self):
        eval_res = self.engine.evaluate_order(
            servicio_solicitado="Consulta de medicina general",
            perfil_cobertura="PRIORITARIO",
            valor_procedimiento=50000,
            medicaciones=["acetaminofén"]
        )
        self.assertEqual(eval_res["decision"], "CUBRE")
        self.assertEqual(eval_res["porcentaje_cobertura"], 100)
        self.assertEqual(eval_res["valor_reconocido"], 50000)
        self.assertEqual(eval_res["codigo_servicio"], "COV-001")

    def test_coverage_estandar_50(self):
        eval_res = self.engine.evaluate_order(
            servicio_solicitado="Consulta de medicina general",
            perfil_cobertura="ESTANDAR",
            valor_procedimiento=50000,
            medicaciones=["ibuprofeno"]
        )
        self.assertEqual(eval_res["decision"], "CUBRE")
        self.assertEqual(eval_res["porcentaje_cobertura"], 50)
        self.assertEqual(eval_res["valor_reconocido"], 25000)

    def test_coverage_copago_25(self):
        eval_res = self.engine.evaluate_order(
            servicio_solicitado="Consulta de medicina general",
            perfil_cobertura="COPAGO",
            valor_procedimiento=50000,
            medicaciones=["ibuprofeno"]
        )
        self.assertEqual(eval_res["decision"], "CUBRE")
        self.assertEqual(eval_res["porcentaje_cobertura"], 25)
        self.assertEqual(eval_res["valor_reconocido"], 12500)

    def test_coverage_non_covered_0(self):
        eval_res = self.engine.evaluate_order(
            servicio_solicitado="Cirugía estética no autorizada",
            perfil_cobertura="PRIORITARIO",
            valor_procedimiento=1000000,
            medicaciones=[]
        )
        self.assertEqual(eval_res["decision"], "NO CUBRE")
        self.assertEqual(eval_res["porcentaje_cobertura"], 0)
        self.assertEqual(eval_res["valor_reconocido"], 0)
        self.assertEqual(eval_res["codigo_servicio"], "NON-COVERED")

if __name__ == "__main__":
    unittest.main()
