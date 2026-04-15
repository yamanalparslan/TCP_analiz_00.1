# ⚡ Solar Monitor v2.0

Modbus TCP üzerinden solar inverter'ları izleyen, verileri kaydeden ve görselleştiren **endüstriyel seviye** izleme sistemi.

## ✨ Özellikler

| Kategori | Özellik |
|----------|---------|
| 📊 **Dashboard** | Gerçek zamanlı güç/voltaj/akım/sıcaklık izleme, gauge göstergeleri |
| 🔌 **Veri Toplama** | Senkron + Asenkron Modbus TCP collector (10+ cihaz paralel okuma) |
| 🔮 **Tahmin** | Lineer regresyon ile enerji üretim tahmini + %95 güven bandı |
| ⚖️ **Karşılaştırma** | Cihaz performans kıyaslama, radar grafiği, puan sistemi |
| 🤖 **Anomali Tespiti** | Statik + istatistiksel (dinamik) eşikler, filo sapma analizi |
| 📄 **PDF Rapor** | Profesyonel A4 rapor oluşturma (günlük / haftalık) |
| 📥 **Export** | Excel, CSV veri dışa aktarma |
| 🔌 **REST API** | FastAPI ile 10+ endpoint, Swagger UI |
| 📈 **Prometheus** | Grafana uyumlu metrik exporter |
| 🔒 **Güvenlik** | PBKDF2 hash, brute-force koruma, RBAC yetki sistemi |
| 📝 **Audit Log** | Tüm kullanıcı işlemlerinin izlenmesi |
| 💾 **Yedekleme** | Otomatik SQLite backup + downsampling |
| 🐳 **Docker** | Multi-service Docker Compose orchestration |

## 🚀 Hızlı Başlangıç

### Yerel Çalıştırma

```bash
# 1. Bağımlılıkları kur
pip install -r requirements.txt

# 2. .env dosyasını oluştur
cp .env.example .env
# .env dosyasını düzenle (IP, port, şifre vb.)

# 3. Collector'ı başlat (veri toplama)
python collector.py

# 4. Arayüzü başlat (ayrı terminal)
streamlit run panel.py

# 5. REST API (opsiyonel, ayrı terminal)
python api.py

# 6. Prometheus Exporter (opsiyonel, ayrı terminal)
python prometheus_exporter.py
```

### Docker ile Çalıştırma

```bash
# Tüm servisleri başlat
docker compose up -d

# Production
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

## 🌐 Servis Portları

| Port | Servis | Açıklama |
|------|--------|----------|
| `8501` | Streamlit Panel | Ana dashboard |
| `8502` | Healthcheck | Sistem sağlık durumu |
| `8503` | REST API | FastAPI + Swagger (`/api/docs`) |
| `9100` | Prometheus | Metrik exporter (`/metrics`) |

## 📁 Proje Yapısı

```
├── panel.py                 # Streamlit ana arayüz + gauge göstergeleri
├── collector.py             # Senkron Modbus veri toplayıcı
├── collector_async.py       # Asenkron collector (asyncio)
├── api.py                   # FastAPI REST API
├── prometheus_exporter.py   # Prometheus metrik exporter
├── healthcheck.py           # HTTP sağlık endpoint
├── veritabani.py            # DB katmanı (SQLite, WAL, downsampling, yedek)
├── anomaly.py               # Anomali tespiti (statik + dinamik DynamicThreshold)
├── auth.py                  # Kimlik doğrulama + RBAC
├── config.py                # Merkezi konfigürasyon (.env)
├── models.py                # Veri modelleri (dataclass)
├── notifications.py         # Telegram + Webhook bildirimler
├── utils.py                 # Yardımcı fonksiyonlar
├── styles.py                # Dark tema CSS
├── pages/
│   ├── 1_📊_Günlük_Rapor.py   # Günlük üretim raporu
│   ├── 2_⚠️_alarms.py        # Alarm izleme
│   ├── 3_📥_Export.py         # Veri dışa aktarma
│   ├── 4_🔍_Anomaliler.py    # Anomali kayıtları
│   ├── 5_📝_Audit_Log.py     # Kullanıcı işlem logları
│   ├── 6_📄_PDF_Rapor.py     # PDF rapor oluşturucu
│   ├── 7_🔮_Tahmin.py        # Üretim tahmini
│   ├── 8_⚖️_Karsilastir.py   # Cihaz karşılaştırma
│   └── 9_🖥️_Sistem.py       # Sistem durumu
├── .env.example             # Ortam değişken şablonu
├── Dockerfile               # Multi-stage Docker build
├── docker-compose.yml       # 5 servislı Docker Compose
├── security_tests.py        # 29 test
└── .github/workflows/ci.yml # GitHub Actions CI
```

## 🔒 Güvenlik & RBAC

| Rol | Etiket | Yetkiler |
|-----|--------|----------|
| `admin` | 👑 Yönetici | Tüm işlemler |
| `operator` | 🔧 Operatör | Dashboard, raporlar, ayar değişikliği |
| `viewer` | 👁️ İzleyici | Sadece görüntüleme |

```env
# .env'de yapılandırma
USER_ROLES=admin:admin,sahada1:operator,musteri:viewer
```

- **Varsayılan giriş:** `admin` / `solar2026`
- **Şifreleme:** PBKDF2-SHA256 (100K iterasyon)
- **Brute-force:** 5 deneme sonrası 60 sn kilitleme

## 📢 Bildirimler

### Telegram Bot Kurulumu

1. [@BotFather](https://t.me/BotFather) ile yeni bot oluştur
2. Bot token'ı al
3. Chat ID'yi bul
4. `.env` dosyasını güncelle:
   ```env
   TELEGRAM_ENABLED=true
   TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
   TELEGRAM_CHAT_ID=-100123456789
   ```

## 🧪 Testler

```bash
python -m unittest security_tests -v
# Ran 29 tests — OK
```

## 📊 CI/CD

GitHub Actions ile otomatik:
- ✅ Python 3.9 / 3.11 / 3.12 testleri
- ✅ Ruff lint kontrolü
- ✅ Docker build doğrulaması

## 📝 Lisans

MIT
