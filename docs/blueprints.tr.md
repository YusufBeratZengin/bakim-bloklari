# Blueprint alanları — Türkçe başvuru

Home Assistant blueprint arayüz metinleri (giriş adları ve açıklamaları) tek bir dilde
tanımlanır; HA'nın blueprint şeması alan bazında yerelleştirme desteklemez. Bu nedenle her
blueprint'in `description` alanına Türkçe bir özet eklendi ve alanların Türkçe karşılıkları
bu belgede tutuluyor. Arayüzde İngilizce etiket, altında Türkçe özet göreceksiniz.

## morning_inactivity.yaml — Sabah hareketsizlik denetimi

| Alan | Türkçe | Not |
| --- | --- | --- |
| `motion_sensors` | Hareket / varlık sensörleri | Birden fazla seçilebilir. PIR, mmWave radar veya kapı kontağı. |
| `check_time` | Sabah kontrol saati | Varsayılan 10:00. |
| `morning_start_time` | Sabah penceresi başlangıcı | Varsayılan 06:30. Bu saatten sonraki herhangi bir hareket "aktivite" sayılır. |
| `person_entity` | Yaşlı kişi varlığı | `not_home` ise uyarı verilmez. |
| `vacation_mode` | Tatil / uzakta modu | `on` ise uyarı verilmez. |
| `ok_button` | "İyiyim" onay düğmesi | `on` ise sabah kontrolü atlanır. |
| `notify_action` | Uyarı eylemi | Örn. `notify.mobile_app_bakici`. |

Davranış: kontrol saatinde sensörlerden biri `on` ise **veya** son durum değişikliği bugünkü
`morning_start_time`'dan sonra olduysa uyarı çıkmaz. Tüm sensörler `unavailable`/`unknown`
ise güvenli tarafta kalınır ve uyarı verilmez.

## prolonged_bathroom.yaml — Uzun banyo denetimi

| Alan | Türkçe | Not |
| --- | --- | --- |
| `bathroom_sensor` | Banyo varlık sensörü | Süre bu sensörün `on` kaldığı süreye göre ölçülür. |
| `door_sensor` | Banyo kapı kontağı (isteğe bağlı) | Çevrimdışıysa alarm üretilmez. |
| `max_duration_minutes` | En uzun güvenli süre (dk) | Varsayılan 30. |
| `person_entity` | Yaşlı kişi varlığı | Evde değilse uyarı verilmez. |
| `vacation_mode` | Tatil modu | `on` ise uyarı verilmez. |
| `notify_action` | Uyarı eylemi | — |

## door_left_open.yaml — Kapı açık kalma / gece gezintisi

| Alan | Türkçe | Not |
| --- | --- | --- |
| `door_sensor` | Dış kapı kontağı | `device_class: door` önerilir. |
| `day_open_timeout_minutes` | Gündüz açık kalma süresi (dk) | Varsayılan 5. |
| `night_wandering_alert` | Gece gezintisi uyarısı | Kapatılırsa gece açılışları yalnızca süre kuralıyla değerlendirilir. |
| `night_start_time` | Gece başlangıcı | Varsayılan 23:00. |
| `night_end_time` | Gece bitişi | Varsayılan 06:00. Gece aralığı gece yarısını aşabilir. |
| `notify_action` | Uyarı eylemi | — |

## escalation_pipeline.yaml — Kademeli acil durum hattı

| Alan | Türkçe | Not |
| --- | --- | --- |
| `trigger_boolean` | Tetikleyici varlık | `input_boolean` veya `alert`. `on` olduğunda hat başlar. |
| `ack_entity` | Onay düğmesi/anahtarı (isteğe bağlı) | Boş bırakılırsa iki zaman penceresi kullanılır. |
| `wait_resident_minutes` | Yaşlı yanıt penceresi (dk) | Her aşamada bu kadar beklenir. |
| `speaker_action` | 1. aşama: ev içi hoparlör | "İyi misiniz?" sesi veya zil. |
| `resident_notify_action` | 2. aşama: yaşlının telefonu | Yalnızca ilk pencere onaysız geçerse çalışır. |
| `caregiver_notify_action` | 3. aşama: bakıcı kritik alarmı | İki pencere de onaysız geçerse çalışır. |

Sıra: hoparlör → onay bekle → (onay yoksa) telefon bildirimi → onay bekle → (onay yoksa)
bakıcı alarmı. Herhangi bir aşamadaki onay sonraki aşamaları durdurur.

## ok_button.yaml — "İyiyim" / acil durum düğmesi

| Alan | Türkçe | Not |
| --- | --- | --- |
| `button_entity` | Akıllı düğme varlığı | `event`, `sensor` veya `binary_sensor`. |
| `single_press_action` | Tek basış eylemi | Uyarıları temizler / kontrolü onaylar. |
| `emergency_press_action` | Acil eylem | Çift/uzun basışta çalışır. |
| `emergency_event_types` | Acil olay değerleri | Virgülle ayrılır: `double_press, long_press, hold, emergency`. |

## Örnek otomasyon eşleşmeleri

- Sabah blueprint'inin `ok_button` girdisine `input_boolean.morning_ok` verin; ok_button
  blueprint'inde tek basış eylemini `input_boolean.turn_on` + `input_boolean.morning_ok`
  olarak ayarlayın.
- Kademeli hattı `input_boolean.care_alert` ile tetikleyin; banyo ve sabah blueprint'lerinin
  `notify_action` alanından `input_boolean.turn_on` ile aynı bayrağı açabilirsiniz.

> Bu paket acil servis çağrısı yapmaz ve tıbbi tanı koymaz. Hayati risk taşıyan durumlarda
> sertifikalı bir acil durum cihazı/servisi kullanın.
