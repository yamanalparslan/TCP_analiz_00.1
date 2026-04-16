import os
import unittest

import veritabani


class TestSonDurumSorgusu(unittest.TestCase):
    def setUp(self):
        self.original_db = veritabani.DB_NAME
        veritabani.DB_NAME = "test_summary.db"
        veritabani.init_db()

    def tearDown(self):
        veritabani.DB_NAME = self.original_db
        if os.path.exists("test_summary.db"):
            os.remove("test_summary.db")

    def test_tum_cihazlarin_son_durumu_latest_row_values(self):
        veritabani.veri_ekle(1, {"guc": 100, "voltaj": 220, "akim": 5, "sicaklik": 20, "hata_kodu": 0, "hata_kodu_193": 0})
        veritabani.veri_ekle(2, {"guc": 200, "voltaj": 221, "akim": 6, "sicaklik": 21, "hata_kodu": 0, "hata_kodu_193": 0})
        veritabani.veri_ekle(1, {"guc": 300, "voltaj": 222, "akim": 7, "sicaklik": 22, "hata_kodu": 11, "hata_kodu_193": 12})

        rows = veritabani.tum_cihazlarin_son_durumu()

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0], (1, rows[0][1], 300.0, 222.0, 7.0, 22.0, 11, 12))
        self.assertEqual(rows[1], (2, rows[1][1], 200.0, 221.0, 6.0, 21.0, 0, 0))


if __name__ == "__main__":
    unittest.main()
