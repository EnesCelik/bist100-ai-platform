# BIST100 AI Platform

Bu proje, AI Engineer gecis planini finans domain'i ile birlestiren portfoy odakli bir urun tasarimidir.

## Urun Vizyonda Ne Var?

- KAP, faaliyet raporu ve yatirimci sunumu ingest etme
- canli market data tool entegrasyonu
- Sirket bazli kaynak gosterimli soru-cevap
- Sirket karsilastirma ve donemsel degisim analizi
- Opsiyonel signal engine ile `bullish / neutral / bearish` veya `buy / hold / sell` uretimi
- Paper trading modu
- Prompt, maliyet, latency ve feedback takibi

## Cekirdek Ilke

Bu sistem artik `hybrid agent platform` olarak tasarlanir.

Tek bir cozum yok:

- canli ve yapisal veri icin `tool/API`
- dokuman ve gecmis metin zekasi icin `RAG`
- karar akisi icin `agent orchestration`

Bu ayrim sayesinde:

- anlik veri vector DB'ye zorla yazilmaz
- dokuman arama ile canli veri sorgusu birbirine karismaz
- agent, soruya gore dogru veri yolunu secer
- portfoy acisindan daha gercekci bir urun ortaya cikar

## Moduller

1. `knowledge`
- KAP aciklamalari, raporlar ve tablolar
- citation'li RAG cevaplari
- kaynak odakli dokuman zekasi

2. `research`
- sirket karsilastirma
- olay etkisi analizi
- Markdown/PDF rapor uretimi

3. `market_tools`
- fiyat, hacim, basic quote verisi
- broker veya third-party API baglantisi
- agent tarafinda cagirilacak tool katmani

4. `signal`
- teknik ve temel skor birlestirme
- aciklama ureten sinyal motoru
- `signal_enabled` ile acilir

5. `paper_trading`
- gercek emir yok
- strateji simulasyonu ve performans izleme
- `paper_trade_enabled` ile acilir

6. `llmops`
- prompt versiyonlama
- token, latency, cost takibi
- feedback loop ve model routing

## Baslangic Stack

- Python 3.11
- FastAPI
- PostgreSQL + pgvector
- Redis
- OpenAI
- Streamlit
- Docker Compose
- Langfuse veya Helicone

## Veri Edinim Stratejisi

- `RAG` icin: KAP, faaliyet raporlari, yatirimci sunumlari
- `tool/API` icin: canli fiyat, hacim, quote, indikatot verisi
- `signal` icin ilk asama: Garanti eTrader `Pay Duzey 1+`
- ileri seviye order-flow icin: `Pay Duzey 2`, `Pay Islem Tarafi Esanli`, `Takas Analiz`

Ilk hedef, her veriyi ayni sepete koymak degil; once:

- dokumanlar icin RAG
- canli market data icin tool
- bunlari birlestiren basit agent akisi

kurmaktir.

## Karar Kalitesi Notu

Bu projede nihai hedef sadece soru cevaplayan bir sistem kurmak degil, hisse icin `neden artar`, `neden duser`, `hangi kosullarda alinabilir`, `hangi kosullarda risk artar` gibi sorulara daha dogru yonlenebilen bir karar destek yapisi kurmaktir.

Su anki durum:

- mimari dogru yone girdi
- `tool + RAG + analysis` katmanlari olustu
- fakat sistem henuz `decision-grade intelligence` seviyesinde degil

Bu seviyeye yaklasmak icin zorunlu gereksinimler:

1. `Gercek market data`
- fiyat
- hacim
- mum/zaman serisi
- mumkunse kademe, order flow, uye/takas proxy

2. `Gercek fundamental data`
- gelir
- borcluluk
- marj
- buyume
- carpanlar

3. `Gercek event data`
- KAP parse
- bilanço
- temettu
- sermaye islemleri
- yonetim degisimi
- ihale, ceza, regülasyon etkileri

Ek olarak gerekli katman:

- `macro_event_service`
- savas
- yaptirim
- petrol/emtia soku
- faiz/merkez bankasi etkisi
- ticaret kisiti
- arz zinciri bozulmasi

Bu katman dunya olaylarinin BIST hisselerine dolayli etkisini tasimak icin gereklidir.

4. `Scoring engine`
- trend score
- momentum score
- valuation score
- earnings/fundamental score
- event impact score
- risk score

5. `Recommendation policy`
- model dogrudan kafasina gore `buy/sell` dememeli
- once `bullish / neutral / bearish`
- sonra policy ile `buy / hold / reduce`

Mevcut ilk policy kurali:

- `signal` agirligi: `1.0`
- `fundamental` agirligi: `1.3`
- `event` agirligi: `1.6`
- `macro_event` agirligi: `1.8`
- weighted net score `> 2.2` ise `bullish`
- weighted net score `< -2.2` ise `bearish`
- aradaki bantta `neutral`

Ilk action mapping:

- `bullish -> buy`
- `neutral -> hold`
- `bearish -> reduce`

6. `Validation`
- backtest
- yanlis pozitif / yanlis negatif olcumu
- hangi sinyalin ise yaradigini gosteren kalite takibi

Kritik ilke:

- `Su anki sistem = analysis framework`
- `Hedef sistem = decision-grade intelligence`

Sonraki gelistirme sirasinda bu not temel referans olarak korunacak.

## Gercek Veri Gecis Sirasi

Mock'tan gercek sisteme geciste oncelik sirasi su olacak:

1. `Event data once`
- ilk gercek entegrasyon `KAP parse` olacak
- cunku hem RAG hem analysis hem de event service ayni anda guclenir
- ilk buyuk kazanc: citation kalitesi ve gercek olay etkisi

2. `Market data ikinci`
- fiyat
- hacim
- mum/zaman serisi
- temel quote verisi

Bu katman signal service ve hybrid query kalitesini yukseltecek.

3. `Fundamental data ucuncu`
- bilanço kalemleri
- marj
- borcluluk
- buyume
- carpanlar

Bu katman recommendation policy'nin daha saglam calismasi icin gerekli.

4. `Signal engine dorduncu`
- gercek veriden trend, momentum, volatility, volume breakout hesaplari
- mock signal service bu asamada gercek hesaba donusecek

5. `Validation besinci`
- backtest
- precision/recall benzeri kalite olcumleri
- sinyal ve policy kalibrasyonu

## Neden Bu Sira?

- `KAP/event` katmani hem RAG hem analysis tarafina en hizli degeri verir
- `market data` olmadan signal tarafi gucsuz kalir
- `fundamental data` olmadan uzun vadeli karar kalitesi eksik kalir
- `validation` olmadan recommendation katmani guvenilir sayilmaz

Kisa karar:

- `once event`
- `sonra market data`
- `sonra fundamental`
- `sonra signal hesaplama`
- `en sonda validation ve policy kalibrasyonu`

## Macro Event Service Notu

`macro_event_service` ayri bir katman olarak ele alinacak.

Bu servis ne yapacak:

1. dunya olaylarini toplayacak
- savas
- yaptirim
- bogaz kapanmasi
- petrol/emtia soku
- faiz ve ticaret kararlari

2. olaylari siniflandiracak
- `geopolitics`
- `energy`
- `rates`
- `trade`
- `sanctions`
- `supply_chain`

3. etki mapping'i uretecek
- sektor etkisi
- emtia etkisi
- BIST ticker etkisi

4. analysis katmanina evidence saglayacak

Veri kaynagi mantigi:

- guvenilir haber akisleri
- resmi kurum/aciklama kaynaklari
- emtia ve makro veri API'leri
- gerekirse manuel event seed

BIST impact mapping mantigi:

- `sector mapping`
- `macro rule mapping`
- `ticker-specific override`

Analysis entegrasyonu:

- `signal_service`
- `fundamental_service`
- `event_service`
- `macro_event_service`

Bu dort katman `analysis_query` icinde ortak evidence uretir.
Su an ilk implementasyon `mock_macro_event_service` ile calisir; yani dunya olayi mantigi zincire baglandi ama veri kaynagi henuz gercek haber/makro API degildir.
Bir sonraki asamada bu katman gercek haber akisina, emtia verisine ve resmi aciklama kaynaklarina baglanacaktir.

## Dokumanlar

- [12 haftalik plan](./docs/PLAN_12_WEEKS.md)
- [mimari tasarim](./docs/ARCHITECTURE.md)
- [ilk sprint backlog'u](./docs/SPRINT_01.md)

## Macro Event JSON Akisi

Makro olay katmani artik sabit Python sozlugunden degil, `data/macro_events/index.json` dosyasindan okunur.

Bu akisin amaci:
- dunya olaylarini kod degistirmeden ekleyebilmek
- `analysis_query` icinde makro event evidence uretmek
- recommendation policy'ye bu evidence'i agirlikli sekilde yansitmak

Yeni endpoint'ler:
- `GET /api/v1/macro-events/{ticker}`
- `POST /api/v1/ingest/macro-events`

Bu katman su an hala MVP seviyesindedir:
- veri kaynagi JSON tabanli
- gercek haber/makro API entegrasyonu yok
- ama event akisi artik API uzerinden beslenebilir hale geldi

## JSON'dan DB'ye Gecis Esigi

Ilk faz icin JSON yeterli.
Asagidaki esiklerden biri geldiginde PostgreSQL tarafina gecmek mantikli olur:

- `50+ macro event kaydi` birikmeye baslarsa
- ayni anda birden fazla kaynak veya kullanici veri ekliyorsa
- tarih, kategori, bolge veya ticker bazli filtreleme artarsa
- event history uzerinde sorgu, karsilastirma ve dashboard ihtiyaci buyurse
- ayni veri hem analysis hem reporting hem dashboard katmaninda tekrar kullanilacaksa

Pratik karar:
- su an JSON ile devam edelim
- ilk ciddi esik `50+ kayit` veya `coklu yazma/filtreleme` ihtiyacidir

## Veritabani Karari

Bu proje icin ana veritabani karari `PostgreSQL` olarak belirlendi.

Neden `PostgreSQL`:
- yapisal ve iliskisel veri ihtiyaci var
- tarih, kategori, ticker, bolge bazli filtreleme gerekli
- analysis, recommendation ve event history sorgulari buyuyecek
- dashboard, raporlama ve policy kalibrasyonu icin SQL sorgulari daha uygun
- audit edilebilirlik ve veri disiplinini korumak daha kolay

Bu projede veritabaninin rol dagilimi su olacak:
- `PostgreSQL`: ana uygulama verisi
- `pgvector`: RAG embedding ve dokuman chunk arama katmani
- `Redis`: cache, gecici state ve hizlandirma katmani

`NoSQL-first` yaklasimi bu proje icin ana omurga olarak secilmedi.
Cunku event history, filtreleme, iliskisel analiz ve raporlama ihtiyaclari SQL tarafina daha dogal oturuyor.

Pratik karar:
- MVP fazinda JSON ile devam
- ilk kalici DB gecisinde `PostgreSQL`
- RAG buyudugunde `pgvector`
- performans ihtiyaci arttiginda `Redis`

## Macro Rule Mapping

Makro olay katmani artik sadece JSON kaydindaki hazir etkilere bakmaz.
Asagidaki iki ek katman da calisir:

- `sector mapping`
- `ticker-specific override`

Calisma mantigi:
- JSON kaydi temel olayi tasir
- `event_category` alani okunur
- ilgili hissenin sektoru bulunur
- sektor bazli genel etkiler eklenir
- gerekiyorsa ticker'a ozel override etkileri eklenir
- tum etkiler birlestirilip tekrar eden maddeler temizlenir

Bu yapi neden gerekli:
- ayni makro olay farkli sektorlerde farkli sonuclar dogurur
- tek tek her ticker icin tum etkiyi elle yazmak zorunda kalmayiz
- yeni olay eklemek daha hizli olur
- ileride JSON'dan PostgreSQL'e gecis daha duzenli olur

## Region Ve Multi-Ticker Macro Events

Makro olay katmaninda artik iki ek yetenek var:

1. `region mapping`
- ayni event category farkli bolgelerde farkli siddette etki yaratabilir
- ornegin `middle_east` havacilikta operasyonel riskleri daha sert artirirken savunmada talep algisini guclendirebilir

2. `multi-ticker ingest`
- tek bir dunya olayi birden fazla hisseyi etkileyebilir
- bu nedenle ayni kaydi tek tek tekrar girmek yerine toplu yazma destegi eklendi

Yeni endpoint:
- `POST /api/v1/ingest/macro-events/bulk`

Kullanim mantigi:
- olay bir kez tanimlanir
- etkilenen ticker listesi verilir
- sistem her ticker icin ayri kayit olusturur
- sonra `sector + region + ticker override` kurallari birlikte calisir

## Bulk Macro Event Duzeltmesi

`bulk` ingest akisinda ortak event etkileri ile sektor/ticker etkileri ayrildi.

Yeni kural:
- `base_positive_impacts` ve `base_negative_impacts` sadece tum ticker'lara ortak yazilabilecek, ticker-agnostic etkileri tasir
- sektor ve ticker'a ozel etkiler payload ile verilmez
- bu etkiler sadece `rule mapping` katmani tarafindan uretilir

Bu ayrim neden gerekli:
- ayni pozitif etkinin yanlis hisselere tasinmasini onler
- `Defense` icin mantikli bir etki `Airlines` veya `Banking` icine yanlislikla dusmez
- bulk event semantigi temiz kalir

## Macro Analysis Milestone

Bu asamada `macro analysis` MVP milestone'u tamamlandi.

Tamamlanan yetenekler:
- `macro_event_service` analysis zincirine baglandi
- `sector mapping` eklendi
- `region mapping` eklendi
- `ticker-specific override` eklendi
- `bulk macro event ingest` eklendi
- `recommendation policy` macro event etkisini agirlikli skora katacak sekilde guncellendi
- `analysis answer` kisa ozet tarafinda daha spesifik macro/event highlight sececek sekilde iyilestirildi

Bu milestone ile sistem artik ayni dunya olayini farkli hisselerde farkli okuyabilen, bunu evidence ve recommendation katmanina yansitabilen bir yapıya ulasmistir.

Bu asamanin sonraki dogal adimlari:
- gercek news ingest
- historical macro event listing
- policy kalibrasyonu

## Institutional Flow Katmani

Kurumsal ve fon akisi, bu projede `ana karar motoru` degil `confirmation layer` olarak ele alinir.

Bu katman neyi takip eder:
- fon ve kurumsal ilginin artip azalmadigi yonler
- tema bazli kurumsal kayma
- likidite ve agirlik degisimi sinyalleri
- riskten kacinma donemlerinde pozisyon cozulme ihtimali

Sistemdeki rolu:
- `analysis_evidence` icine `institutional_flow` kategorisi olarak girer
- recommendation policy'ye agirlikli ama sinirli etki eder
- tek basina `buy/sell` karari uretmez
- mevcut sinyal, fundamental ve makro okumayi dogrulayan veya zayiflatan katman olarak kullanilir

Mevcut policy agirligi:
- `institutional_flow`: `1.2`

Karar esigi temkinli tutulur:
- tam sinir skorlarinda sistem `neutral` kalmayi tercih eder

Neden `macro_event` kadar yuksek degil:
- fon verisi tek basina neden-sonuc iliskisini tam aciklamaz
- gecikmeli veya donemsel hareketler yaniltici olabilir
- bu nedenle ana belirleyici degil, destekleyici sinyal olarak konumlanir

## Kisa Gozden Gecirme Notu

Su an en guclu taraflar:
- `analysis_query` katmanli calisiyor
- `macro_event` zinciri sektor, bolge ve ticker override ile ayrisiyor
- recommendation policy artik daha tutarli bir akisa sahip

Guncellenebilecek yerler:
- `confidence` artik dinamik heuristikle hesaplanir; ancak henuz backtest veya calibration ile dogrulanmis degildir
- `route detection` hala keyword tabanli; daha iyi query intent routing eklenebilir
- `local retriever` her istekte diski yeniden okuyor; cache veya preload ile hiz artirilabilir
- `historical event listing` ve filtreleme henuz yok

Bu notlar sonraki kalite iyilestirme backlog'u olarak korunur.

## Historical Macro Event Listing

Makro olaylar icin artik gecmis listeleme endpoint'i de mevcut:
- `GET /api/v1/macro-events/history/{ticker}`

Desteklenen query parametreleri:
- `limit`: varsayilan `10`, maksimum `50`
- `category`: opsiyonel kategori filtresi

Bu endpoint neden gerekli:
- tek bir son olaya bakmak yerine event gecmisini gorebiliriz
- policy kalibrasyonu icin gecmis olaylar izlenebilir
- dashboard ve future news ingest icin uygun ara katman saglar

## Legacy Macro Event Cleanup

Eski `bulk` akistan kalan hatali ortak pozitif etkileri temizlemek icin su endpoint eklendi:
- `POST /api/v1/macro-events/cleanup/legacy`

Bu endpoint su an hedefli bir normalizasyon yapar:
- eski hatali `defense` pozitiflerini ticker-agnostic ortak etkiye cevirir
- history ve analysis katmaninda legacy veri kirliligini azaltir

## News Ingest Katmani

Ham haber katmani eklendi.
Bu katman dogrudan recommendation uretmez; once haberi sisteme kaydeder.

Yeni endpoint'ler:
- `POST /api/v1/ingest/news`
- `GET /api/v1/news/history/{ticker}`

Desteklenen query parametreleri:
- `limit`
- `tag`

Bu katmanin amaci:
- ham haberi yorumlanmis `macro_event` katmanindan ayirmak
- gercek news API entegrasyonu oncesi temiz bir ingest katmani kurmak
- sonraki adimda `news -> macro_event` donusumu icin temel olusturmak

## News Dedupe Ve Cleanup

Haber ingest katmani artik duplicate kayitlara karsi korumali calisir.

Davranis:
- ayni `ticker + headline + published_at + source_url` kombinasyonu tekrar gelirse kayit eklenmez
- response `status` alani `skipped` doner

Ek endpoint:
- `POST /api/v1/news/cleanup/duplicates`

Bu endpoint mevcut JSON store icindeki tekrarlari temizler.

## News To Macro Donusumu

Ham haberden yorumlanmis makro olay katmanina gecis icin ilk donusum endpoint'i eklendi:
- `POST /api/v1/news/convert-to-macro`

Ilk versiyon davranisi:
- haber kaydini `ticker + headline + published_at` ile bulur
- `tags`, `headline` ve `summary` uzerinden `event_category` ve `region` turetir
- temel pozitif/negatif etkileri rule-based olarak uretir
- sonucu `macro_event` store icine yazar

Bu katman henuz MVP seviyesindedir:
- rule-based calisir
- LLM veya gercek haber siniflandirma modeli kullanmaz
- ama `news -> macro_event` ayrimini netlestirir ve sonraki gelistirmeler icin temel olusturur

## PostgreSQL Foundation

Veritabani temeli artik kod tarafinda da kuruldu.

Eklenen ana parcalar:
- SQLAlchemy baglantisi ve session yapisi
- baslangic tablolari: `news_items`, `macro_event_records`, `analysis_runs`
- `docker-compose.yml` ile lokal PostgreSQL servisi
- `GET /api/v1/db/health`
- `POST /api/v1/db/init`

Bu asamada not:
- JSON store'lar hala calismaya devam eder
- yani bu adim tam migration degil, DB foundation asamasidir
- sonraki adimda news ve macro event store'lari kontrollu sekilde PostgreSQL'e tasinabilir

Ilk lokal calistirma akisi:
1. `docker compose up -d postgres`
2. `POST /api/v1/db/init`
3. `GET /api/v1/db/health`


## Scan Snapshot Notes

- `POST /api/v1/scan/market/snapshot` endpointi ile o anki tarama sonucu DB'ye kaydedilir.
- `GET /api/v1/scan/history` endpointi ile snapshot gecmisi izlenebilir.
- Snapshot kayitlari dashboard icin gunluk/oturum bazli piyasa fotografi saglar.
- `market_data_provider` ayari ile `matriks` secildiginde current price ve gun ici hacim artik Garanti/Matriks canli snapshot endpointinden okunur; OHLCV tarafi ise su an icin Yahoo uzerinden devam eder.

## Matriks Integration

- `MARKET_DATA_PROVIDER` artik `mock`, `yahoo_delayed` veya `matriks` olabilir.
- `matriks` secildiginde snapshot provider once `MATRIKS_MARKET_DATA_TOKEN` alanini dener; token yoksa veya JWT suresi dolduysa `MATRIKS_USERNAME` ve `MATRIKS_PASSWORD` ile `Integration.aspx` uzerinden otomatik login yapmayi dener.
- Auth formati Garanti WebTrader bundle'indan dogrulandi: REST cagrilar `Authorization: jwt <token>` header'i ile gider; login POST'u ise `MsgType=A`, `SourceID=40`, `ExchangeID=4` ve form-urlencoded alanlarla `Integration.aspx` endpointine yapilir.
- Canli snapshot akisi `https://api.matriksdata.com/dumrul/v1/snapshot-market-real` endpointinden `last`, `bid`, `ask`, `quantity` ve `dayClose` bilgilerini ceker.
- Provider sonucu mevcut market snapshot cache'ine yazar; istek basarisiz olursa son cache'e geri doner.
- Otomatik login akisi `MATRIKS_CUSTOMER_NO`, `MATRIKS_ACCOUNT_ID`, `MATRIKS_SESSION_KEY`, `MATRIKS_LOGIN_ACTION` ve `MATRIKS_LOGIN_OTP` alanlariyla genisletilebilir; varsayilan akista `CustomerNo=0` ve `AccountID=0` ile plain login denenir.
- Garanti mobil onay gerekiyorsa backend `POST /api/v1/market-data/auth/garanti/sso/start` ile SSO login URL'si uretir, kullanici browser'da onaylar, sonra `POST /api/v1/market-data/auth/garanti/sso/complete` ile `client_state` finalize edilerek yeni `MarketDataToken` alınır.
- Garanti web oturumu zaten aciksa ve `Integration.aspx` response'u elinizdeyse, `POST /api/v1/market-data/auth/garanti/browser-bootstrap` ile `MarketDataToken` dogrudan runtime'a yuklenebilir.
- OHLCV provider'i Matriks `tick/bar.gz` response formatini okuyacak sekilde hazirlandi. Gunluk timeframe (`1G`) icin gerçek period degeri Network'ten dogrulandi ve varsayilan olarak `1day` aktif edildi.
- `tick/bar.gz` endpointi `timestamp` parametresi istedigi icin backend bu parametreyi otomatik ekler.
- Intraday tarafta frontend isteginden gelen `5min` periodu dogrulandi; backend `1H` icin 12 adet `5min`, `4H` icin 48 adet `5min` bar'i aggregate ederek Matriks OHLCV uretir.
- Haftalik timeframe (`1W`) icin gerçek request henuz netlesmediyse sistem otomatik olarak Yahoo OHLCV fallback kullanir.

## Matriks Integration Checklist

Bu bolum, gercek Matriks baglantisina gecmeden once netlestirilmesi gereken bilgileri tutar. Su an cevaplar bilinmiyor; bilgi geldikce bu checklist uzerinden ilerleyecegiz.

1. `Erisim tipi`
- REST API mi?
- WebSocket mi?
- terminal ustunden DLL / COM / .NET bridge mi?
- Python tarafinda dogrudan kullanilabilir bir katman var mi?

2. `Kimlik dogrulama`
- kullanici adi / sifre mi?
- token mi?
- terminal ID gerekiyor mu?
- ek cihaz veya IP yetkisi gerekiyor mu?

3. `Veri kapsami`
- anlik fiyat
- degisim yuzdesi
- hacim
- en iyi alis / satis
- OHLC veya mum verisi
- derinlik
- takas / kurum / fon akis katmanlari

4. `Sembol formati`
- `THYAO`
- `THYAO.E`
- `THYAO.IS`
- baska bir kodlama kullaniliyor mu?

5. `Rate limit ve kullanim sinirlari`
- saniyede kac istek?
- ayni anda kac baglanti?
- terminal acik olmadan calisiyor mu?

6. `Ornek request/response`
- en az bir gercek `THYAO` quote cevabi gerekli
- mapping katmani bu ornege gore netlestirilecek

7. `Hata davranisi`
- yetki yoksa ne donuyor?
- sembol yoksa ne donuyor?
- timeout veya session expiry nasil gorunuyor?

8. `Lisans ve ticari kosul`
- sadece terminal lisansi yeterli mi?
- API erisimi ayri mi ucretleniyor?
- canli veri icin ek moduller gerekiyor mu?

Ilk PoC basari kriteri:
- `GET /api/v1/market-data/THYAO` cagrisi gercek Matriks verisiyle su alanlari dondurebilmeli:
  - `ticker`
  - `last_price`
  - `change_percent`
  - `volume`
  - `best_bid`
  - `best_ask`

## Analysis Run Logging

- `dashboard.py` ile ilk Streamlit dashboard eklendi.
- Ana ekran chat merkezli degil, `market scan` merkezli calisir.
- Bullish/bearish aday listeleri, filtrelenebilir `market scan` tablosu, scan snapshot history, ticker detail, macro timeline, analysis history ve ask panel ayni ekranda toplanir.
- Tablo uzerinden secilen ticker, detail panelini gunceller; bu yapi dashboard'i BIST100 geneli tarama ekranina yaklastirir.

- `GET /api/v1/scan/market` endpointi eklendi.
- Mevcut hisse evreni icin analysis motoru toplu calistirilir ve her ticker icin `stance`, `action`, `confidence`, `weighted_score`, hacim ve kisa neden uretilir.
- `stance` ve `limit` ile temel filtreleme yapilir; ilk dashboard bu endpoint ustune kurulacak.

- `POST /api/v1/ask` cevabi uretildikten sonra `analysis_runs` tablosuna log dusulur.
- Kaydedilen alanlar: `ticker`, `question`, `route_type`, `stance`, `action`, `confidence`, `used_sources`, `recommendation_summary`.
- Bu log katmani kalite takibi, policy kalibrasyonu ve ileride dashboard icin hazir veri saglar.

- `GET /api/v1/analysis-runs` endpointi eklendi.
- Desteklenen filtreler: `ticker`, `route_type`, `stance`, `action`, `min_confidence`, `date_from`, `date_to`, `limit`.
- `analysis_runs` tablosuna `created_at` zaman damgasi eklendi; tarih araligi filtreleri bu alan uzerinden calisir.
- Boylece analysis gecmisi Swagger uzerinden de izlenebilir hale geldi.

## News Storage Status

- `macro_event` servisi de PostgreSQL oncelikli calisir; DB ulasilamazsa gecici JSON fallback devam eder.
- Mevcut JSON macro event kayitlarini veritabanina tasimak icin `POST /api/v1/macro-events/migrate/from-json` endpointi eklendi.
- `news -> macro` donusumu artik macro kaydini da once PostgreSQL'e yazar.

- `news` servisi artik PostgreSQL oncelikli calisir; DB ulasilamazsa gecici olarak JSON fallback kullanir.
- Mevcut JSON haberlerini veritabanina tasimak icin `POST /api/v1/news/migrate/from-json` endpointi eklendi.
- `news -> macro` donusumu artik haber kaydini once PostgreSQL'de arar; boylece ham haber katmani DB tabanli hale gelmeye baslar.



## Arastirma Notlari

- `Matriks canli veri cekme uygulamasi` not edildi; ileride Garanti disi canli veri/entegrasyon secenekleri incelenecek.
- `ux_algo smart money concepts` not edildi; TradingView source kodu ileride signal/algoritma katmani icin referans olarak incelenecek.

## Chart Analysis Roadmap

Grafik yorumlama tarafinda secilen sira su olacak:

1. `Chart feature engine once`
- trend
- EMA
- RSI
- hacim
- kirilim
- destek / direnc
- volatility
- market structure

2. `LLM yorum katmani sonra`
- feature engine tarafinda uretilen yapisal ciktilar once kodla hesaplanacak
- LLM bu feature setini kullanarak insan okunur yorum, senaryo ve risk anlatimi uretecek

3. `Chart screenshot yorumlama en son`
- ekran goruntusu analizi ana karar motori olmayacak
- sadece yardimci baglam katmani olarak dusunulecek

Kisa ilke:
- `hesaplama = deterministic engine`
- `yorumlama = LLM`
- `nihai recommendation = policy + explanation`

Ilk implementasyon notu:
- `app/services/chart_feature_service.py` ile ilk chart feature engine eklendi.
- `GET /api/v1/chart-features/{ticker}` endpointi trend, EMA, RSI, hacim orani, kirilim durumu, destek/direnc, volatility ve market structure ozeti dondurur.
- `signal_service` artik sabit metin yerine chart feature engine uzerinden turetilir.
- Bu asamada input veri kaynagi seed/mock profile tabanlidir; gercek OHLCV geldiginde ayni kontrat korunarak sadece input katmani degistirilecek.
