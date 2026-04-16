import sqlite3
import os
from datetime import datetime, timedelta

# --- VERİTABANI YOL AYARLARI ---
# Docker içinde miyiz kontrolü (/app/data genellikle Docker volume yoludur)
if os.path.exists("/app/data"):
    DB_NAME = "/app/data/solar_log.db"
else:
    # Yerel bilgisayarda test ediliyorsa 'data' klasörü yoksa oluştur
    if not os.path.exists("data"):
        os.makedirs("data")
    DB_NAME = os.path.join("data", "solar_log.db")

def init_db():
    # Debug için yol bilgisini yazdıralım
    print(f"📂 Veritabanı Bağlanıyor: {DB_NAME}")
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # 1. Ölçümler Tablosu
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS olcumler (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slave_id INTEGER, 
            zaman TIMESTAMP,
            guc REAL,
            voltaj REAL,
            akim REAL,
            sicaklik REAL,
            hata_kodu INTEGER DEFAULT 0,
            hata_kodu_193 INTEGER DEFAULT 0
        )
    """)
    
    # Index oluştur (sorgu performansı için)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_slave_zaman 
        ON olcumler(slave_id, zaman DESC)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_zaman 
        ON olcumler(zaman DESC)
    """)

    # 2. Ayarlar Tablosu
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ayarlar (
            anahtar TEXT PRIMARY KEY,
            deger TEXT,
            aciklama TEXT,
            guncelleme_zamani TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # MIGRATION: Eski ayarlar tablosuna yeni kolonlar ekle
    try:
        ayarlar_sutunlar = [row[1] for row in cursor.execute("PRAGMA table_info(ayarlar)")]
        if 'aciklama' not in ayarlar_sutunlar:
            cursor.execute("ALTER TABLE ayarlar ADD COLUMN aciklama TEXT")
        if 'guncelleme_zamani' not in ayarlar_sutunlar:
            cursor.execute("ALTER TABLE ayarlar ADD COLUMN guncelleme_zamani TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
    except:
        pass

    # 3. Varsayılan Ayarları Ekle
    varsayilan_ayarlar = [
        ('refresh_rate', '2', 'Veri çekme sıklığı (saniye)'),
        ('guc_scale', '1.0', 'Güç çarpanı'),
        ('volt_scale', '1.0', 'Voltaj çarpanı'),
        ('akim_scale', '0.1', 'Akım çarpanı'),
        ('isi_scale', '1.0', 'Sıcaklık çarpanı'),
        ('guc_addr', '70', 'Güç register adresi'),
        ('volt_addr', '71', 'Voltaj register adresi'),
        ('akim_addr', '72', 'Akım register adresi'),
        ('isi_addr', '74', 'Sıcaklık register adresi'),
        ('target_ip', '10.35.14.10', 'Modbus IP adresi'),
        ('target_port', '502', 'Modbus Port'),
        ('slave_ids', '1,2,3', 'İnverter ID listesi'),
        ('veri_saklama_gun', '365', 'Veri saklama süresi (gün) - 0: Sınırsız')
    ]
    
    for anahtar, deger, aciklama in varsayilan_ayarlar:
        try:
            cursor.execute("""
                INSERT OR IGNORE INTO ayarlar (anahtar, deger, aciklama)
                VALUES (?, ?, ?)
            """, (anahtar, deger, aciklama))
        except:
            cursor.execute("""
                INSERT OR IGNORE INTO ayarlar (anahtar, deger)
                VALUES (?, ?)
            """, (anahtar, deger))
    
    # MIGRATION: hata_kodu_193 kolonu yoksa ekle
    try:
        mevcut_sutunlar = [row[1] for row in cursor.execute("PRAGMA table_info(olcumler)")]
        if 'hata_kodu_193' not in mevcut_sutunlar:
            cursor.execute("ALTER TABLE olcumler ADD COLUMN hata_kodu_193 INTEGER DEFAULT 0")
    except:
        pass

    # 4. Anomaliler Tablosu
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS anomaliler (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slave_id INTEGER,
            tip TEXT,
            ciddiyet TEXT DEFAULT 'warning',
            mesaj TEXT,
            zaman TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_anomali_zaman
        ON anomaliler(zaman DESC)
    """)

    # 5. Audit Log Tablosu
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kullanici TEXT DEFAULT 'admin',
            islem TEXT,
            detay TEXT,
            zaman TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()

def ayar_oku(anahtar, varsayilan=None):
    """Veritabanından ayar oku"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('SELECT deger FROM ayarlar WHERE anahtar = ?', (anahtar,))
        sonuc = cursor.fetchone()
        conn.close()
        if sonuc:
            return sonuc[0]
        return varsayilan
    except Exception as e:
        print(f"⚠️ Ayar okuma hatası ({anahtar}): {e}")
        return varsayilan

def ayar_yaz(anahtar, deger):
    """Veritabanına ayar yaz"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO ayarlar (anahtar, deger, guncelleme_zamani)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        """, (anahtar, str(deger)))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"⚠️ Ayar yazma hatası ({anahtar}): {e}")
        return False

def tum_ayarlari_oku():
    """Tüm ayarları dict olarak döndür"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('SELECT anahtar, deger FROM ayarlar')
        ayarlar = {row[0]: row[1] for row in cursor.fetchall()}
        conn.close()
        return ayarlar
    except:
        return {
            'refresh_rate': '2', 'guc_scale': '1.0', 'volt_scale': '1.0',
            'akim_scale': '0.1', 'isi_scale': '1.0', 'guc_addr': '70',
            'volt_addr': '71', 'akim_addr': '72', 'isi_addr': '74',
            'target_ip': '10.35.14.10', 'target_port': '502', 'slave_ids': '1,2,3',
            'veri_saklama_gun': '365'
        }

def veri_ekle(slave_id, data):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    simdi = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
    hk_189 = data.get('hata_kodu', 0)
    hk_193 = data.get('hata_kodu_193', 0)
    cursor.execute("""
        INSERT INTO olcumler (slave_id, zaman, guc, voltaj, akim, sicaklik, hata_kodu, hata_kodu_193)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (slave_id, simdi, data['guc'], data['voltaj'], data['akim'], data['sicaklik'], hk_189, hk_193))
    conn.commit()
    conn.close()

def son_verileri_getir(slave_id, limit=100):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT zaman, guc, voltaj, akim, sicaklik, hata_kodu, hata_kodu_193
        FROM olcumler WHERE slave_id = ?
        ORDER BY zaman DESC LIMIT ?
    """, (slave_id, limit))
    rows = cursor.fetchall()
    conn.close()
    return rows[::-1]

def tum_cihazlarin_son_durumu():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT o.slave_id, o.zaman, o.guc, o.voltaj, o.akim, o.sicaklik, o.hata_kodu, o.hata_kodu_193
        FROM olcumler o
        WHERE o.id = (
            SELECT i.id
            FROM olcumler i
            WHERE i.slave_id = o.slave_id
            ORDER BY i.zaman DESC, i.id DESC
            LIMIT 1
        )
        ORDER BY o.slave_id ASC
    """)
    rows = cursor.fetchall()
    conn.close()
    return rows

def db_temizle():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute('DELETE FROM olcumler')
        conn.commit()
        return True
    except:
        return False
    finally:
        conn.close()

# ==================== YENİ FONKSİYONLAR: GEÇMİŞ VERİ YÖNETİMİ ====================

def eski_verileri_temizle(gun_sayisi=None):
    """
    Belirtilen günden eski verileri sil
    gun_sayisi None ise ayarlardan oku
    gun_sayisi 0 ise sınırsız saklama (silme yapma)
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    try:
        if gun_sayisi is None:
            gun_sayisi = int(ayar_oku('veri_saklama_gun', '365'))
        
        # 0 = sınırsız saklama
        if gun_sayisi == 0:
            return 0
        
        tarih = datetime.now() - timedelta(days=gun_sayisi)
        tarih_str = tarih.strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('DELETE FROM olcumler WHERE zaman < ?', (tarih_str,))
        silinen = cursor.rowcount
        conn.commit()
        
        if silinen > 0:
            # VACUUM ile DB boyutunu küçült
            cursor.execute('VACUUM')
            print(f"🧹 {silinen} eski kayıt temizlendi ({gun_sayisi} günden eski)")
        
        return silinen
    except Exception as e:
        print(f"⚠️ Eski veri temizleme hatası: {e}")
        return 0
    finally:
        conn.close()

def veritabani_istatistikleri():
    """Veritabanı boyutu ve kayıt sayısı hakkında bilgi"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    try:
        # Toplam kayıt sayısı
        cursor.execute('SELECT COUNT(*) FROM olcumler')
        toplam_kayit = cursor.fetchone()[0]
        
        # İlk ve son kayıt tarihleri
        cursor.execute('SELECT MIN(zaman), MAX(zaman) FROM olcumler')
        tarih_araligi = cursor.fetchone()
        
        # Cihaz başına kayıt sayısı
        cursor.execute('''
            SELECT slave_id, COUNT(*) as kayit_sayisi, 
                   MIN(zaman) as ilk_kayit, 
                   MAX(zaman) as son_kayit
            FROM olcumler 
            GROUP BY slave_id 
            ORDER BY slave_id
        ''')
        cihaz_istatistik = cursor.fetchall()
        
        # Veritabanı dosya boyutu
        db_boyut = os.path.getsize(DB_NAME) / (1024 * 1024)  # MB cinsinden
        
        return {
            'toplam_kayit': toplam_kayit,
            'ilk_kayit': tarih_araligi[0],
            'son_kayit': tarih_araligi[1],
            'cihaz_istatistik': cihaz_istatistik,
            'db_boyut_mb': round(db_boyut, 2)
        }
    except Exception as e:
        print(f"⚠️ İstatistik hatası: {e}")
        return None
    finally:
        conn.close()

def tarih_araliginda_ortalamalar(baslangic, bitis, slave_id=None):
    """Belirtilen tarih aralığındaki ortalama değerler"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    baslangic_str = f"{baslangic} 00:00:00"
    bitis_str = f"{bitis} 23:59:59"
    
    try:
        if slave_id:
            cursor.execute('''
                SELECT 
                    AVG(guc) as ort_guc,
                    AVG(voltaj) as ort_voltaj,
                    AVG(akim) as ort_akim,
                    AVG(sicaklik) as ort_sicaklik,
                    MAX(guc) as max_guc,
                    MIN(guc) as min_guc,
                    COUNT(*) as toplam_olcum
                FROM olcumler
                WHERE zaman BETWEEN ? AND ? AND slave_id = ?
            ''', (baslangic_str, bitis_str, slave_id))
        else:
            cursor.execute('''
                SELECT 
                    AVG(guc) as ort_guc,
                    AVG(voltaj) as ort_voltaj,
                    AVG(akim) as ort_akim,
                    AVG(sicaklik) as ort_sicaklik,
                    MAX(guc) as max_guc,
                    MIN(guc) as min_guc,
                    COUNT(*) as toplam_olcum
                FROM olcumler
                WHERE zaman BETWEEN ? AND ?
            ''', (baslangic_str, bitis_str))
        
        sonuc = cursor.fetchone()
        return {
            'ort_guc': sonuc[0] or 0,
            'ort_voltaj': sonuc[1] or 0,
            'ort_akim': sonuc[2] or 0,
            'ort_sicaklik': sonuc[3] or 0,
            'max_guc': sonuc[4] or 0,
            'min_guc': sonuc[5] or 0,
            'toplam_olcum': sonuc[6] or 0
        }
    except Exception as e:
        print(f"⚠️ Ortalama hesaplama hatası: {e}")
        return None
    finally:
        conn.close()

def gunluk_uretim_hesapla(tarih, slave_id=None):
    """Belirli bir gün için toplam enerji üretimi tahmini (Wh)"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    baslangic = f"{tarih} 00:00:00"
    bitis = f"{tarih} 23:59:59"
    
    try:
        if slave_id:
            cursor.execute('''
                SELECT AVG(guc) as ort_guc, COUNT(*) as olcum_sayisi
                FROM olcumler
                WHERE zaman BETWEEN ? AND ? AND slave_id = ?
            ''', (baslangic, bitis, slave_id))
        else:
            cursor.execute('''
                SELECT AVG(guc) as ort_guc, COUNT(*) as olcum_sayisi
                FROM olcumler
                WHERE zaman BETWEEN ? AND ?
            ''', (baslangic, bitis))
        
        sonuc = cursor.fetchone()
        ort_guc = sonuc[0] or 0
        olcum_sayisi = sonuc[1] or 0
        
        # Varsayılan veri toplama aralığı (saniye)
        ayarlar = tum_ayarlari_oku()
        refresh_rate = float(ayarlar.get('refresh_rate', 2))
        
        # Toplam süre (saat)
        toplam_saat = (olcum_sayisi * refresh_rate) / 3600
        
        # Tahmini üretim (Watt-saat)
        uretim_wh = ort_guc * toplam_saat
        
        return {
            'uretim_wh': round(uretim_wh, 2),
            'uretim_kwh': round(uretim_wh / 1000, 3),
            'ort_guc': round(ort_guc, 2),
            'calisma_suresi_saat': round(toplam_saat, 2)
        }
    except Exception as e:
        print(f"⚠️ Üretim hesaplama hatası: {e}")
        return None
    finally:
        conn.close()

def hata_sayilarini_getir(baslangic, bitis, slave_id=None):
    """Belirtilen tarih aralığındaki hata kayıtlarını getir"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    baslangic_str = f"{baslangic} 00:00:00"
    bitis_str = f"{bitis} 23:59:59"
    
    try:
        if slave_id:
            cursor.execute('''
                SELECT 
                    COUNT(*) as toplam,
                    SUM(CASE WHEN hata_kodu > 0 THEN 1 ELSE 0 END) as hata_189,
                    SUM(CASE WHEN hata_kodu_193 > 0 THEN 1 ELSE 0 END) as hata_193
                FROM olcumler
                WHERE zaman BETWEEN ? AND ? AND slave_id = ?
            ''', (baslangic_str, bitis_str, slave_id))
        else:
            cursor.execute('''
                SELECT 
                    COUNT(*) as toplam,
                    SUM(CASE WHEN hata_kodu > 0 THEN 1 ELSE 0 END) as hata_189,
                    SUM(CASE WHEN hata_kodu_193 > 0 THEN 1 ELSE 0 END) as hata_193
                FROM olcumler
                WHERE zaman BETWEEN ? AND ?
            ''', (baslangic_str, bitis_str))
        
        sonuc = cursor.fetchone()
        return {
            'toplam_olcum': sonuc[0] or 0,
            'hata_189_sayisi': sonuc[1] or 0,
            'hata_193_sayisi': sonuc[2] or 0
        }
    except Exception as e:
        print(f"⚠️ Hata sayısı getirme hatası: {e}")
        return None
    finally:
        conn.close()


# ==================== ANOMALİ FONKSİYONLARI ====================

def anomali_ekle(slave_id, tip, ciddiyet, mesaj):
    """Anomali kaydı ekle.
    
    Args:
        slave_id: Cihaz ID
        tip: Anomali tipi (guc_dususu, voltaj_dusuk, sicaklik_yuksek, vb.)
        ciddiyet: "critical" veya "warning"
        mesaj: Açıklama mesajı
    """
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO anomaliler (slave_id, tip, ciddiyet, mesaj, zaman)
            VALUES (?, ?, ?, ?, ?)
        """, (slave_id, tip, ciddiyet, mesaj, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"⚠️ Anomali ekleme hatası: {e}")
        return False


def anomalileri_getir(limit=100, ciddiyet=None):
    """Anomali kayıtlarını getir.
    
    Args:
        limit: Maksimum kayıt sayısı
        ciddiyet: None=hepsi, "critical" veya "warning"
    
    Returns:
        list of tuples: (id, slave_id, tip, ciddiyet, mesaj, zaman)
    """
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        if ciddiyet:
            cursor.execute("""
                SELECT id, slave_id, tip, ciddiyet, mesaj, zaman
                FROM anomaliler
                WHERE ciddiyet = ?
                ORDER BY zaman DESC LIMIT ?
            """, (ciddiyet, limit))
        else:
            cursor.execute("""
                SELECT id, slave_id, tip, ciddiyet, mesaj, zaman
                FROM anomaliler
                ORDER BY zaman DESC LIMIT ?
            """, (limit,))
        rows = cursor.fetchall()
        conn.close()
        return rows
    except Exception as e:
        print(f"⚠️ Anomali getirme hatası: {e}")
        return []


# ==================== AUDİT LOG FONKSİYONLARI ====================

def audit_log_kaydet(kullanici, islem, detay=""):
    """Audit log kaydı ekle.
    
    Args:
        kullanici: İşlemi yapan kullanıcı
        islem: İşlem tipi (ayar_degistir, veri_sil, vb.)
        detay: Ek açıklama
    """
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO audit_log (kullanici, islem, detay, zaman)
            VALUES (?, ?, ?, ?)
        """, (kullanici, islem, detay, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"⚠️ Audit log hatası: {e}")
        return False


def audit_log_getir(limit=100):
    """Audit log kayıtlarını getir.
    
    Returns:
        list of tuples: (id, kullanici, islem, detay, zaman)
    """
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, kullanici, islem, detay, zaman
            FROM audit_log
            ORDER BY zaman DESC LIMIT ?
        """, (limit,))
        rows = cursor.fetchall()
        conn.close()
        return rows
    except Exception as e:
        print(f"⚠️ Audit log getirme hatası: {e}")
        return []
