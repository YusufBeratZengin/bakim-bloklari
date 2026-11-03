# bakim-bloklari

> **Yalnız yaşayan yaşlılar ve yerinde yaşlanma (aging-in-place) için mahremiyet odaklı, kamerasız Home Assistant blueprint paketi ve simülasyon motoru.**

[![CI](https://github.com/yusufberatzengin/bakim-bloklari/actions/workflows/ci.yml/badge.svg)](https://github.com/yusufberatzengin/bakim-bloklari/actions)
[![Lisans: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](pyproject.toml)
[![Kapsama: %95](https://img.shields.io/badge/coverage-95%25-brightgreen.svg)](scripts/check.sh)

[English README](README.md)

`bakim-bloklari`, yalnız yaşayan yaşlıların bağımsız ve güvenli bir yaşam sürmesini destekleyen, ortam farkındalığına dayalı hazır ev otomasyonları (blueprint) sunar. Mahremiyeti zedeleyen kameralar veya ortam dinleyen mikrofonlar kullanmadan; pasif ortam sensörlerini (PIR hareket dedektörleri, mmWave mikro-varlık radarları ve manyetik kapı kontaklarını) izleyerek sabah hareketsizliğini, uzun banyo sürelerini veya gece kapı açılmalarını tespit eder ve gerektiğinde aileye kademeli uyarı gönderir.

Paket, Home Assistant blueprint şemalarını doğrulayan ve **çevrimdışı ya da arızalı sensörlerin asla sahte acil durum alarmı üretmemesini** garanti eden 12 senaryoluk Python durum motoru simülatörünü içerir.

---

## 30 Saniyede Başlangıç

### 1. Home Assistant'a Doğrudan İçe Aktarma
Home Assistant arayüzünde **Ayarlar > Otomasyonlar ve Sahneler > Blueprint'ler > Blueprint İçe Aktar** yolunu izleyin ve dilediğiniz blueprint'in bağlantısını yapıştırın:

```text
https://github.com/yusufberatzengin/bakim-bloklari/blob/main/blueprints/automation/bakim_bloklari/morning_inactivity.yaml
```

Veya tüm paketi yerel Home Assistant yapılandırma dizininize CLI aracıyla yükleyin:

```bash
pip install bakim-bloklari
bakim-bloklari install --target ~/.homeassistant
```

### 2. CLI ile Doğrulama ve Kuru Çalıştırma (Simülasyon)
Gerçek donanıma dokunmadan blueprint'leri doğrulayabilir ve 12 senaryo testini çalıştırabilirsiniz:

```bash
# Blueprint YAML şemasını ve güvenlik kurallarını doğrula
bakim-bloklari validate

# Durum simülatöründe 12 deterministik senaryo testini çalıştır
bakim-bloklari simulate
```

### Gerçek Terminal Çıktısı

```text
$ bakim-bloklari validate
[bakim-bloklari v0.1.0] Validating 5 blueprint(s)...

[PASS] door_left_open.yaml - Elderly Care - Exterior Door Left Open & Night Wandering (Errors: 0, Warnings: 0)
[PASS] escalation_pipeline.yaml - Elderly Care - Multi-Stage Escalation Pipeline (Errors: 0, Warnings: 0)
[PASS] morning_inactivity.yaml - Elderly Care - Morning Inactivity Monitor (Errors: 0, Warnings: 0)
[PASS] ok_button.yaml - Elderly Care - 'I Am OK' & Emergency Button Handler (Errors: 0, Warnings: 0)
[PASS] prolonged_bathroom.yaml - Elderly Care - Prolonged Bathroom Occupancy Alert (Errors: 0, Warnings: 0)

============================================================
Validation SUCCESS: All 5 blueprint(s) passed schema checks.

$ bakim-bloklari simulate
[bakim-bloklari v0.1.0] Running 12 Acceptance Scenarios against: bakim_bloklari

[PASS] SCENARIO-01: Normal Morning Motion Detected -> No Alarm
[PASS] SCENARIO-02: Zero Morning Motion -> Escalation Alarm Fired
[PASS] SCENARIO-03: Resident Away (not_home) -> Alarm Suppressed
[PASS] SCENARIO-04: Vacation Mode Active -> Alarm Suppressed
[PASS] SCENARIO-05: Motion Sensor Unavailable -> Safe Fallback (No False Alarm)
[PASS] SCENARIO-06: Motion Sensor Unknown -> Safe Fallback (No False Alarm)
[PASS] SCENARIO-07: Bathroom Normal 15-Min Shower -> Cleared Normally
[PASS] SCENARIO-08: Bathroom Prolonged Occupancy (>30m) -> Emergency Alert Fired
[PASS] SCENARIO-09: Bathroom Sensor Unavailable -> Safe Fallback (No False Alarm)
[PASS] SCENARIO-10: Front Door Left Open Daytime (>5m) -> Alert Fired
[PASS] SCENARIO-11: Night Wandering Door Open (02:30 AM) -> Urgent Alert Fired
[PASS] SCENARIO-12: 'I Am OK' Button Single Press -> Alert Acknowledged & Cleared

============================================================
Simulation Summary: 12/12 scenarios passed.
All elderly care scenarios verified successfully.
```

---

## Dahil Edilen Blueprint'ler (v0.1)

| Blueprint | Açıklama | Desteklenen Donanımlar |
| --------- | -------- | ---------------------- |
| [`morning_inactivity.yaml`](blueprints/automation/bakim_bloklari/morning_inactivity.yaml) | Belirlenen sabah saat aralığında (ör. 06:30 - 10:00) evin ortak alanlarında hareket olup olmadığını inceler. Yaşlı evdeyken hareket algılanmazsa kademeli alarm başlatır. | PIR hareket dedektörleri, mmWave varlık radarları, kapı kontakları. |
| [`prolonged_bathroom.yaml`](blueprints/automation/bakim_bloklari/prolonged_bathroom.yaml) | Banyo ve ıslak hacim varlığını izleyerek kapalı kapı ardındaki düşme veya tıbbi kaza durumlarında erken uyarı verir. Varlık süresi eşiği (ör. 30 dk) aşıldığında alarm üretir. | mmWave radarlar (Aqara FP2, LD2410), PIR sensörleri, banyo kapı sensörleri. |
| [`door_left_open.yaml`](blueprints/automation/bakim_bloklari/door_left_open.yaml) | Gündüz saatlerinde dış kapı açık kaldığında (>5 dk) hatırlatır; gece saatlerinde (23:00 - 06:00) açılırsa uyurgezerlik ve gece dolaşma riskine karşı anında aileye acil bildirim atar. | Manyetik kapı kontak sensörleri (Zigbee / Z-Wave / Matter). |
| [`escalation_pipeline.yaml`](blueprints/automation/bakim_bloklari/escalation_pipeline.yaml) | Uyarı yorgunluğunu önleyen tırmanma protokolü: Önce ev içi akıllı hoparlörden sesli uyarı ("İyi misiniz?"), ardından telefona nazik bildirim, yanıt alınamazsa aileye kritik acil durum alarmı iletir. | Medya oynatıcı / akıllı hoparlör, Home Assistant Companion mobil uygulaması. |
| [`ok_button.yaml`](blueprints/automation/bakim_bloklari/ok_button.yaml) | Yatak başı kablosuz buton yönetimi. Tek basış "İyiyim" onayı vererek aktif alarmları sıfırlar; çift basış veya basılı tutma doğrudan bakıcıya acil durum çağrısı gönderir. | Zigbee / Matter kablosuz butonlar, akıllı anahtarlar. |

---

## Güvenlik ve Yanlış Alarm Önleme Mimarisi

Yaşlı bakım otomasyonlarında en büyük tehlike **uyarı yorgunluğudur**: bir sensör pil değiştirdiğinde, yeniden başladığında veya kablosuz ağdan koptuğunda aileye sahte acil durum alarmı giderse sistem güvenilirliğini kaybeder.

`bakim-bloklari`, Home Assistant Jinja şablon koşullarında sensör sağlık kontrollerini zorunlu tutar:

```yaml
# Örnek: morning_inactivity.yaml içerisindeki sensör sağlık filtresi
condition:
  - condition: template
    value_template: >-
      {% set sensors = motion_sensors_var %}
      {% set sensor_list = sensors if sensors is iterable and sensors is not string else [sensors] %}
      {% set valid_sensors = sensor_list | reject('is_state', 'unavailable') | reject('is_state', 'unknown') | list %}
      {{ valid_sensors | length > 0 }}
```

1. **Çevrimdışı Sensör İzolasyonu:** `unavailable` veya `unknown` durumundaki sensörler listelerden ayıklanır. Tüm sensörler geçici olarak ağ dışı kalmışsa acil durum alarmı kilitlenir ve sahte alarmlar engellenir.
2. **Evde Değil ve Tatil Modu Askıya Alma:** Yaşlının `person` varlığı `not_home` olduğunda veya `vacation_mode` aktif edildiğinde alarmlar otomatik duraklatılır.
3. **Kademeli Alarm Tırmanması:** Önce ev içi hoparlör ve yaşlının kendi telefonu uyarılır; yanlışlıkla tetiklenen alarmlar aileye gitmeden yaşlı tarafından kolayca iptal edilebilir.

---

## CLI Komutları

`bakim-bloklari` Python CLI aracı otomasyonlarınızı doğrulama, test etme ve dağıtma imkânı sunar:

```bash
# Tüm blueprint'leri listele ve özetlerini göster
bakim-bloklari list

# Bir blueprint'in girdilerini ve varsayılanlarını ayrıntılı incele
bakim-bloklari inspect morning_inactivity

# Blueprint YAML şemasını ve güvenlik kurallarını doğrula
bakim-bloklari validate [dosya_veya_dizin]

# 12 deterministik senaryo testini simülatörde çalıştır
bakim-bloklari simulate [-v]

# Blueprint'leri Home Assistant yapılandırma klasörüne yükle
bakim-bloklari install --target /path/to/homeassistant
```

---

## Çalışma Zamanı Bağımlılıkları ve Gerekçeleri

`bakim-bloklari` en az bağımlılık ilkesini benimser:

- `pyyaml`: Home Assistant blueprint YAML dosyalarını ve özel `!input` etiketlerini ayrıştırmak için gereklidir.
- `jinja2`: Home Assistant otomasyonlarında yer alan Jinja2 ifadelerini, durum filtrelerini (`states()`, `is_state()`) test etmek ve çalıştırmak için gereklidir.

Diğer tüm işlemler yalnızca Python standart kütüphanesini kullanır.

---

## Hedef Kitle, Sınırlar ve Yasal Uyarı

- **Hedef Kitle:** Yalnız yaşayan yaşlılar, aileler, bakıcılar ve Home Assistant kullanıcıları (`NEEDS_SOURCE`: küresel demografik pazar büyüklüğü ve yaşlı nüfus istatistikleri için resmî kaynak beklenmektedir).
- **Gizlilik Bildirimi:** Tüm otomasyon mantığı ve sensör verileri %100 yerel olarak kendi Home Assistant sunucunuzda işlenir. Hiçbir hareket veya varlık verisi yerel ağınız dışına çıkmaz.
- **Tıbbi Olmayan Cihaz Uyarısı:**

> [!IMPORTANT]
> **ACİL DURUM VEYA RESMÎ TIBBİ CİHAZ DEĞİLDİR:**  
> `bakim-bloklari`, açık kaynaklı bir ev otomasyonu ve ortam farkındalığı aracıdır. Tıbbi teşhis koymaz, yaşamsal bulgu (nabız, solunum vb.) takibi yapmaz ve 112/acil servislere doğrudan çağrı göndermez. Bir yardımcı erken uyarı sistemi olarak tasarlanmıştır; sertifikalı acil durum çağrı butonlarının, düşme dedektörlerinin veya profesyonel sağlık bakımının yerine geçemez.

---

## Geliştirme ve Test

```bash
git clone https://github.com/yusufberatzengin/bakim-bloklari.git
cd bakim-bloklari
python -m venv .venv
source .venv/bin/activate  # Windows üzerinde: .venv\Scripts\activate
pip install -e ".[dev]"

# Tüm kontrolleri çalıştır (lint + tip + testler + simülasyon)
bash scripts/check.sh
```

---

## Lisans

Bu proje [MIT Lisansı](LICENSE) ile lisanslanmıştır - Copyright (c) 2026 Yusuf Berat Zengin.
