# 12 Haftalik BIST100 AI Engineer Gecis Plani

## Hedef

12 hafta sonunda elinde su 4 parca olsun:

- BIST100 Knowledge Assistant
- BIST100 Market Tools Layer
- BIST100 Research Agent
- Signal Engine + Paper Trading MVP
- LLMOps Dashboard

## Hafta 1

- Python, pandas, requests, SQLite tekrar
- veri cekme, temizleme, tablo mantigi
- finans verisi icin temel kolon okuma

Teslim:
- 3 Python script
- ham veri ve temiz veri ciktilari

## Hafta 2

- FastAPI, Pydantic, REST endpoint
- Docker temel
- config ve env yonetimi

Teslim:
- `/health`
- `/companies`
- `/documents`

## Hafta 3

- LLM temel kavramlari
- prompt design
- token, context, chunking mantigi
- tool calling mantigi

Teslim:
- prompt notebook veya markdown notlari
- ilk chunking denemeleri
- tool vs RAG karar tablosu

## Hafta 4

- hybrid agent mimarisi
- tool routing, retrieval, reranking, citation mantigi
- guardrail ve cost dusuncesi

Teslim:
- mimari diyagram
- karar dokumani

## Hafta 5

- KAP ve rapor ingest pipeline
- market data tool contract
- PDF ve HTML parse
- metadata normalizasyonu

Teslim:
- dokuman ingest akisi
- market tool mock akisi
- `documents`, `chunks`, `companies` kayitlari

## Hafta 6

- embeddings
- pgvector indeksleme
- retrieval API
- ilk market data endpoint'i

Teslim:
- `/ingest`
- `/ask`
- `/market-data`
- citation'li cevap v1

## Hafta 7

- reranking
- filtreli retrieval
- sirket ve tarih bazli sorgu
- basic query routing

Teslim:
- gelistirilmis cevap kalitesi
- manual eval set

## Hafta 8

- research agent
- coklu sirket karsilastirma
- markdown rapor uretimi
- tool + RAG sentezi

Teslim:
- `/research/compare`
- markdown rapor

## Hafta 9

- signal engine tasarimi
- temel skor modeli
- teknik/fundamental sinyal birlestirme

Teslim:
- `signal_enabled` modulu
- explainable signal output

## Hafta 10

- paper trading
- watchlist
- strateji simulasyonu

Teslim:
- sinyal kayitlari
- sanal pozisyon izleme

## Hafta 11

- LLMOps dashboard
- prompt versioning
- latency/cost tracking
- feedback toplama

Teslim:
- dashboard ekranlari
- temel metrik paneli

## Hafta 12

- deployment
- README, architecture write-up
- demo video ve case study

Teslim:
- canli demo veya local demo paketi
- portfoy sunumu

## Stratejik Not

Bu planin amaci seni `fintech AI product / AI engineer` profiline yaklastirmak.

Ana deger:

- domain bilgisi
- veri + backend + LLM + tool entegrasyonu
- gozlemlenebilir AI sistem kurma becerisi
