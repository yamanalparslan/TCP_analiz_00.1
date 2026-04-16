import logging
import time

from pymodbus.client import ModbusTcpClient

import utils
import veritabani


def load_config():
    """Veritabanindan ayarlari yukle."""
    ayarlar = veritabani.tum_ayarlari_oku()

    slave_ids_raw = ayarlar.get("slave_ids", "1,2,3")
    slave_ids, parse_errors = utils.parse_id_list(slave_ids_raw)

    if parse_errors:
        logging.warning("ID parsing hatalari: %s", ", ".join(parse_errors))

    return {
        "target_ip": ayarlar.get("target_ip", "10.35.14.10"),
        "target_port": int(ayarlar.get("target_port", 502)),
        "refresh_rate": float(ayarlar.get("refresh_rate", 2)),
        "slave_ids": slave_ids,
        "guc_addr": int(ayarlar.get("guc_addr", 70)),
        "volt_addr": int(ayarlar.get("volt_addr", 71)),
        "akim_addr": int(ayarlar.get("akim_addr", 72)),
        "isi_addr": int(ayarlar.get("isi_addr", 74)),
        "guc_scale": float(ayarlar.get("guc_scale", 1.0)),
        "volt_scale": float(ayarlar.get("volt_scale", 1.0)),
        "akim_scale": float(ayarlar.get("akim_scale", 0.1)),
        "isi_scale": float(ayarlar.get("isi_scale", 1.0)),
        "veri_saklama_gun": int(ayarlar.get("veri_saklama_gun", 365)),
        "alarm_registers": [
            {"addr": 189, "key": "hata_kodu", "count": 2},
            {"addr": 193, "key": "hata_kodu_193", "count": 1},
        ],
    }


def read_single_register(client, address, slave_id):
    rr = client.read_holding_registers(address=address, count=1, slave=slave_id)
    if rr.isError():
        return None
    return rr.registers[0]


def read_device(client, slave_id, config):
    try:
        if not client.connected:
            client.connect()
            time.sleep(0.1)

        raw_guc = read_single_register(client, config["guc_addr"], slave_id)
        if raw_guc is None:
            logging.error("Modbus guc okunamadi (ID=%s)", slave_id)
            try:
                client.close()
            except Exception:
                pass
            return None

        time.sleep(0.05)
        raw_volt = read_single_register(client, config["volt_addr"], slave_id)
        time.sleep(0.05)
        raw_akim = read_single_register(client, config["akim_addr"], slave_id)
        time.sleep(0.05)
        raw_isi = read_single_register(client, config["isi_addr"], slave_id)

        veriler = {
            "guc": raw_guc * config["guc_scale"],
            "voltaj": 0 if raw_volt is None else utils.to_signed16(raw_volt) * config["volt_scale"],
            "akim": 0 if raw_akim is None else utils.to_signed16(raw_akim) * config["akim_scale"],
            "sicaklik": 0 if raw_isi is None else utils.decode_temperature_register(raw_isi, config["isi_scale"]),
        }

        for reg in config["alarm_registers"]:
            try:
                time.sleep(0.05)
                r_hata = client.read_holding_registers(
                    address=reg["addr"],
                    count=reg.get("count", 2),
                    slave=slave_id,
                )
                if not r_hata.isError():
                    if reg.get("count", 2) == 2:
                        veriler[reg["key"]] = (r_hata.registers[0] << 16) | r_hata.registers[1]
                    else:
                        veriler[reg["key"]] = r_hata.registers[0]
                else:
                    veriler[reg["key"]] = 0
            except Exception:
                veriler[reg["key"]] = 0

        return veriler

    except Exception as exc:
        logging.error("ID %s hata: %s", slave_id, exc)
        client.close()
        return None


def otomatik_veri_temizle(config):
    """
    Ayarlara gore eski verileri otomatik temizle.
    0 = sinirsiz saklama (temizleme yapma)
    """
    saklama_gun = config.get("veri_saklama_gun", 365)

    if saklama_gun == 0:
        return 0

    try:
        silinen = veritabani.eski_verileri_temizle(saklama_gun)
        if silinen > 0:
            print(f"\nOtomatik Temizlik: {silinen} kayit silindi ({saklama_gun} gunden eski)")
        return silinen
    except Exception as exc:
        print(f"\nOtomatik temizlik hatasi: {exc}")
        return 0


def start_collector():
    veritabani.init_db()
    print("=" * 60)
    print("COLLECTOR BASLATILDI (Dinamik Ayar Modu)")
    print("=" * 60)

    config = load_config()
    client = ModbusTcpClient(config["target_ip"], port=config["target_port"], timeout=2.0)

    print(f"IP: {config['target_ip']}:{config['target_port']}")
    print(f"Refresh: {config['refresh_rate']}s")
    print(f"Slave IDs: {config['slave_ids']}")
    print(
        "Carpanlar: "
        f"Guc={config['guc_scale']}, "
        f"V={config['volt_scale']}, "
        f"A={config['akim_scale']}, "
        f"C={config['isi_scale']}"
    )

    if config["veri_saklama_gun"] == 0:
        print("Veri Saklama: Sinirsiz")
    else:
        print(f"Veri Saklama: {config['veri_saklama_gun']} Gun")

    print("=" * 60)

    ayar_kontrol_sayaci = 0
    temizlik_sayaci = 0
    temizlik_periyodu = 1800

    otomatik_veri_temizle(config)

    while True:
        start_time = time.time()

        ayar_kontrol_sayaci += 1
        if ayar_kontrol_sayaci >= 10:
            yeni_config = load_config()
            if (
                yeni_config["target_ip"] != config["target_ip"]
                or yeni_config["target_port"] != config["target_port"]
            ):
                print("\nIP/Port degisti, baglanti yenileniyor...")
                client.close()
                client = ModbusTcpClient(
                    yeni_config["target_ip"],
                    port=yeni_config["target_port"],
                    timeout=2.0,
                )
            config = yeni_config
            ayar_kontrol_sayaci = 0
            print(f"\nAyarlar guncellendi (Refresh: {config['refresh_rate']}s)")

        temizlik_sayaci += 1
        if temizlik_sayaci >= temizlik_periyodu:
            otomatik_veri_temizle(config)
            temizlik_sayaci = 0

        for dev_id in config["slave_ids"]:
            print(f"ID {dev_id}...", end=" ")
            time.sleep(0.5)
            data = read_device(client, dev_id, config)
            if data:
                veritabani.veri_ekle(dev_id, data)
                h189 = data.get("hata_kodu", 0)
                h193 = data.get("hata_kodu_193", 0)
                if h189 == 0 and h193 == 0:
                    durum = "TEMIZ"
                else:
                    durum = f"HATA (189:{h189}, 193:{h193})"
                print(f"[OK] {durum}")
            else:
                print("[YOK]")

        elapsed = time.time() - start_time
        time.sleep(max(0, config["refresh_rate"] - elapsed))


if __name__ == "__main__":
    logging.basicConfig(level=logging.ERROR)
    start_collector()
