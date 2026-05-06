# BIST100 AI Platform Mimarisi

## Urun Konumlandirma

Bu sistem bir `investment research assistant`, `market tool platform` ve `signal platform` olarak tasarlanir.

Uc ayri veri/karar katmani vardir:

1. `knowledge layer`
- dogrulanabilir kaynaklar
- KAP, rapor, tablo, sunum
- citation'li cevap

2. `tool layer`
- canli fiyat ve hacim verisi
- quote, indicator ve market snapshot
- MCP veya API ile agent'a tanitilan araclar

3. `signal layer`
- model yorumlari
- rule-based veya hybrid score
- feature flag ile acilan riskli alan

Bu ayrim kritik cunku:

- source-backed dokuman cevabi ile canli veri ayni sey degildir
- canli veri vector DB'ye yazilmak zorunda degildir
- signal uretimi, veri cekmenin kendisinden ayrilmalidir

## Neden Hybrid Architecture?

Bu projede tek basina RAG yeterli degildir.

- `canli fiyat`, `hacim`, `quote`, `indikator` gibi veriler icin tool/API daha dogrudur
- `KAP`, `faaliyet raporu`, `yatirimci sunumu` gibi uzun metinler icin RAG daha dogrudur
- `agent orchestration` ise kullanici sorusuna gore hangi yolun secilecegine karar verir

Hedef mimari:

- `Tool-first for live structured data`
- `RAG-first for document intelligence`
- `Agent for orchestration and synthesis`

## Yuksek Seviye Akis

1. Veri toplama
- KAP
- faaliyet raporlari
- yatirimci sunumlari
- fiyat ve hacim verisi
- market quote ve indicator verisi

2. Veri isleme
- dokumanlar icin:
- parse
- normalize
- metadata cikar
- chunk olustur

- canli veri icin:
- API/tool response normalize et
- cache veya relational store'a yaz

3. Depolama
- PostgreSQL: sirket, dokuman, olay, signal metadata
- pgvector: embedding ve retrieval
- Redis: cache, queue, kisa sureli state
- object storage: PDF ve ham dokuman

4. AI katmani
- agent router
- tool calling
- embedding modeli
- retrieval
- reranking
- answer generation
- research orchestration

5. Signal katmani
- technical indicators
- fundamental score
- event score
- confidence hesaplama

6. Sunum katmani
- FastAPI
- Streamlit UI
- dashboard

## Query Routing Mantigi

Agent, gelen soruyu once siniflandirir:

1. `tool_query`
- "GARAN son fiyat nedir?"
- "THYAO hacim artisi var mi?"

Bu tip sorularda once market data tool cagrilir.

2. `rag_query`
- "ASELS son faaliyet raporunda hangi riskler var?"
- "KAP aciklamalarina gore son donemde neler oldu?"

Bu tip sorularda once retrieval calisir.

3. `hybrid_query`
- "Son KAP aciklamalari ile fiyat hareketi birlikte ne soyluyor?"
- "Bu hisse icin haber + fiyat + rapor sentezi nedir?"

Bu tip sorularda hem tool hem RAG kullanilir, sonra agent cevaplari birlestirir.

## Market Data Tiers

Signal katmani icin veri ihtiyacini asamali ele alacagiz.

1. `Tier 0 - Source-backed knowledge`
- KAP
- faaliyet raporlari
- yatirimci sunumlari
- finansal tablo ve dipnotlar

Bu katman RAG ve research agent icin yeterlidir.

2. `Tier 1 - Basic live market data`
- son fiyat
- gunluk degisim
- hacim
- en iyi alis/satis

Bu seviye, basit momentum ve olay etkisi takibi icin yeterlidir.

3. `Tier 2 - Enhanced live market data`
- en iyi kademedeki miktarlar
- gerceklesen islem miktarlari
- daha sik guncellenen akis

Baslangic signal engine icin hedef seviye budur.
Ilk satin alim onerisi: `Garanti eTrader Pay Duzey 1+`

4. `Tier 3 - Order flow and member flow`
- derinlik
- islem tarafi uye bazli akis
- takas dagilim degisimi

Bu seviye, `buy/sell pressure`, `kurum akisi proxy` ve `position accumulation` gibi sinyaller icin gereklidir.
Baslangicta zorunlu degildir.

## Tool Layer Tasarimi

Canli ve yapisal veri icin ayri bir tool katmani olacak:

1. `market_data_tool`
- son fiyat
- gunluk degisim
- hacim
- en iyi alis/satis

2. `indicator_tool`
- RSI
- MACD
- moving average
- volatility snapshot

3. `member_flow_tool`
- islem tarafi proxy
- takas dagilim ozetleri

4. `document_lookup_tool`
- belirli ticker ve tarih icin ilgili dokumanlari getir
- bu tool arka tarafta RAG pipeline'ini tetikleyebilir

Bu araclar FastAPI endpoint, MCP tool veya servis adapter'i olarak modellenebilir.

## Signal Sources

Signal engine tek bir kaynaga bakmayacak. Hibrit skor mantigi kullanilacak:

1. `price_action_signal`
- fiyat degisimi
- momentum
- hacim artisi

2. `order_flow_signal`
- en iyi kademe baskisi
- alis/satis miktar dengesizligi
- derinlik yogunlugu

3. `member_flow_proxy`
- uye bazli islem akis degisimi
- takas dagilim degisimi

Bu katman dogrudan "buyuk yatirimci kim" sorusunu cevaplamaz.
Onun yerine buyuk para veya kurum akisina dair dolayli sinyal uretir.

4. `fundamental_signal`
- gelir
- borcluluk
- marj
- donemsel finansal degisim

5. `event_signal`
- KAP aciklamasi
- yonetim degisimi
- yatirim duyurusu
- ceza, ihale, ortaklik, sermaye islemleri

6. `llm_explanation_signal`
- yukaridaki sinyallerin nedenini aciklar
- ozet yorum uretir
- tek basina skor olusturmaz

## Onerilen Klasor Yapisi

```text
bist100-ai-platform/
├─ app/
│  ├─ api/
│  │  ├─ main.py
│  │  └─ routes/
│  │     ├─ health.py
│  │     ├─ ingest.py
│  │     ├─ ask.py
│  │     ├─ research.py
│  │     └─ signals.py
│  ├─ core/
│  │  ├─ config.py
│  │  ├─ flags.py
│  │  └─ logging.py
│  ├─ data_sources/
│  │  ├─ kap/
│  │  ├─ reports/
│  │  └─ market_data/
│  ├─ agent/
│  │  ├─ router.py
│  │  ├─ orchestrator.py
│  │  └─ planner.py
│  ├─ tools/
│  │  ├─ market_data_tool.py
│  │  ├─ indicator_tool.py
│  │  ├─ member_flow_tool.py
│  │  └─ document_lookup_tool.py
│  ├─ rag/
│  │  ├─ loaders/
│  │  ├─ chunking/
│  │  ├─ embeddings/
│  │  ├─ retrievers/
│  │  ├─ rerank/
│  │  └─ pipeline.py
│  ├─ research/
│  │  ├─ compare.py
│  │  ├─ summarize.py
│  │  └─ report_writer.py
│  ├─ signals/
│  │  ├─ engine.py
│  │  ├─ indicators.py
│  │  ├─ scorer.py
│  │  └─ policy.py
│  ├─ trading/
│  │  ├─ paper_broker.py
│  │  ├─ portfolio.py
│  │  └─ simulator.py
│  ├─ llmops/
│  │  ├─ traces.py
│  │  ├─ feedback.py
│  │  └─ routing.py
│  └─ models/
│     ├─ schemas.py
│     └─ entities.py
├─ ui/
│  └─ streamlit_app.py
├─ scripts/
│  ├─ backfill_kap.py
│  ├─ ingest_reports.py
│  └─ run_manual_eval.py
├─ data/
│  ├─ raw/
│  ├─ processed/
│  └─ eval/
├─ docs/
├─ infra/
│  ├─ docker-compose.yml
│  └─ Dockerfile
├─ pyproject.toml
└─ README.md
```

## Feature Flags

```text
signal_enabled=false
paper_trade_enabled=false
broker_execution_enabled=false
research_agent_enabled=true
market_tools_enabled=true
```

## Ilk Versiyon API'leri

- `GET /health`
- `POST /ingest/documents`
- `POST /ask`
- `POST /research/compare`
- `POST /signals/evaluate`
- `GET /companies/{ticker}`
- `GET /market-data/{ticker}`
- `GET /indicators/{ticker}`

## Signal Uretim Prensibi

Ilk versiyon icin saf LLM ile al/sat uretmek yerine hibrit tasarim daha sagliklidir:

- technical indicators
- fundamental metrics
- KAP ve olay etkisi
- order flow ve takas proxy
- LLM sadece yorumlama ve aciklama katmaninda kullanilir

Bu sayede hem kontrol artar hem de neden-sonuc iliskisi daha net izlenir.

## Vector DB'yi Nasil Besleyecegiz?

Vector DB sadece dokumanlar icin kullanilacak.

Yazilacak veri:

- KAP aciklamalari
- faaliyet raporlari
- yatirimci sunumlari
- gerekirse finansal tablo dipnotlari

Yazilmayacak veri:

- anlik fiyat
- hacim tick verisi
- indicator snapshot
- order book bilgisi

Ingest akisi:

1. dokumani al
2. parse et
3. metadata cikar
4. chunk olustur
5. embedding uret
6. pgvector'a upsert et

Canli market data ise tool veya relational store tarafinda kalacak.

## Satin Alma Yolu

1. Asama 1
- `knowledge layer` + temel tool contract
- ucretsiz ve halka acik kaynaklar

2. Asama 2
- `Garanti eTrader Pay Duzey 1+`
- market data tool + temel signal engine

3. Asama 3
- gerekiyorsa `Pay Duzey 2`, `Pay Islem Tarafi Esanli`, `Takas Analiz`
- order-flow ve member-flow guclendirmesi
