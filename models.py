"""
Solar Monitor - Veri Modelleri & Hata Kod Haritaları
=====================================================
Modbus register hata kodlarının açıklamalarını ve
veri yapılarını tanımlar.

Kullanım:
    from models import FAULT_MAP_189, FAULT_MAP_193
    aciklama = FAULT_MAP_189.get(bit_no, "Bilinmeyen")
"""

from dataclasses import dataclass, field
from datetime import datetime


# ══════════════════════════════════════════════════════════════
# REGISTER 189 — 32-bit Hata Kodu Haritası (Bit bazlı)
# ══════════════════════════════════════════════════════════════
FAULT_MAP_189: dict[int, str] = {
    0:  "DC Overcurrent Fault [1-1]",
    1:  "DC Overcurrent Fault [1-2]",
    2:  "DC Overcurrent Fault [2-1]",
    3:  "DC Overcurrent Fault [2-2]",
    4:  "DC Overcurrent Fault [3-1]",
    5:  "DC Overcurrent Fault [3-2]",
    6:  "DC Overcurrent Fault [4-1]",
    7:  "DC Overcurrent Fault [4-2]",
    8:  "DC Overcurrent Fault [5-1]",
    9:  "DC Overcurrent Fault [5-2]",
    10: "DC Overcurrent Fault [6-1]",
    11: "DC Overcurrent Fault [6-2]",
    12: "DC Overcurrent Fault [7-1]",
    13: "DC Overcurrent Fault [7-2]",
    14: "DC Overcurrent Fault [8-1]",
    15: "DC Overcurrent Fault [8-2]",
    16: "DC Overcurrent Fault [9-1]",
    17: "DC Overcurrent Fault [9-2]",
    18: "DC Overcurrent Fault [10-1]",
    19: "DC Overcurrent Fault [10-2]",
    20: "DC Overcurrent Fault [11-1]",
    21: "DC Overcurrent Fault [11-2]",
    22: "DC Overcurrent Fault [12-1]",
    23: "DC Overcurrent Fault [12-2]",
}

# ══════════════════════════════════════════════════════════════
# REGISTER 193 — 16-bit Hata Kodu Haritası (Bit bazlı)
# ══════════════════════════════════════════════════════════════
FAULT_MAP_193: dict[int, str] = {
    0:  "PV Overvoltage [1]",
    1:  "PV Overvoltage [2]",
    2:  "PV Overvoltage [3]",
    3:  "PV Overvoltage [4]",
    4:  "PV Overvoltage [5]",
    5:  "PV Overvoltage [6]",
    6:  "PV Overvoltage [7]",
    7:  "PV Overvoltage [8]",
    8:  "PV Overvoltage [9]",
    9:  "PV Overvoltage [10]",
    10: "PV Overvoltage [11]",
    11: "PV Overvoltage [12]",
    12: "Grid Overvoltage",
    13: "Grid Undervoltage",
    14: "Grid Overfrequency",
    15: "Grid Underfrequency",
}


# ══════════════════════════════════════════════════════════════
# VERİ YAPILARI
# ══════════════════════════════════════════════════════════════

@dataclass
class OlcumVerisi:
    """Tek bir ölçüm kaydını temsil eder."""
    slave_id: int = 0
    guc: float = 0.0
    voltaj: float = 0.0
    akim: float = 0.0
    sicaklik: float = 0.0
    hata_kodu: int = 0
    hata_kodu_193: int = 0
    zaman: str = ""

    def to_dict(self) -> dict:
        return {
            "slave_id": self.slave_id,
            "guc": self.guc,
            "voltaj": self.voltaj,
            "akim": self.akim,
            "sicaklik": self.sicaklik,
            "hata_kodu": self.hata_kodu,
            "hata_kodu_193": self.hata_kodu_193,
            "zaman": self.zaman or datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }


@dataclass
class CihazDurumu:
    """Bir cihazın anlık durumunu temsil eder."""
    slave_id: int = 0
    son_zaman: str = ""
    guc: float = 0.0
    voltaj: float = 0.0
    akim: float = 0.0
    sicaklik: float = 0.0
    hata_kodu: int = 0
    hata_kodu_193: int = 0
    aktif: bool = False

    @property
    def has_error(self) -> bool:
        return self.hata_kodu != 0 or self.hata_kodu_193 != 0

    @property
    def durum_text(self) -> str:
        if self.has_error:
            return "ARIZA"
        elif self.guc > 0:
            return "AKTİF"
        return "BEKLEMEDE"


@dataclass
class AnomalyRecord:
    """Bir anomali kaydını temsil eder."""
    id: int = 0
    slave_id: int = 0
    tip: str = ""
    ciddiyet: str = "warning"
    mesaj: str = ""
    zaman: str = ""
