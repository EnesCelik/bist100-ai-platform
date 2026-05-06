# Sprint 01 - Hybrid Core

## Sprint Hedefi

Amac, sistemin `tool + RAG` cekirdegini calisir hale getirmektir.

Sprint sonunda su akisin calismasi hedeflenir:

- sirket bazli basic market data getir
- sirket dokumani veya KAP verisi al
- parse et
- metadata cikar
- vector store'a yaz
- soru sor
- gerekiyorsa tool ve RAG sonucunu birlestir
- kaynakli cevap don

## Sprint Kapsami

1. Repo iskeleti
- `app`, `ui`, `scripts`, `data`, `docs`, `infra`

2. Temel backend
- FastAPI projesi
- `GET /health`
- config yapisi

3. Veri modeli
- `Company`
- `Document`
- `Chunk`
- `AnswerTrace`
- `MarketSnapshot`

4. Tool contract v1
- basic market data adapter
- `ticker -> market snapshot` cevabi
- sahte veriyle basla, gercek veri adapter'i sonra takilir

5. Ingest v1
- PDF veya HTML kaynagi oku
- raw dosyayi sakla
- metadata cikar

6. Chunking v1
- `chunk_size=600`
- `chunk_overlap=100`

7. Embedding + vector store
- pgvector veya lokal prototip icin basit adapter

8. Retrieval v1
- `top_k=5`
- ticker bazli filtre

9. Ask endpoint
- soru
- ilgili chunk'lar veya tool sonucu
- cevap
- citation listesi

10. Manual eval set
- en az 15 soru
- 3 sirket
- 2 farkli dokuman tipi
- 2 farkli soru tipi: tool, rag

## Ilk Sprint Gorevleri

- proje klasorlerini olustur
- `pyproject.toml` hazirla
- `.env.example` yaz
- FastAPI app baslat
- `health` route ekle
- ilk `market_data_tool` kontratini yaz
- ilk ingest script'ini yaz
- ilk retrieval fonksiyonunu yaz
- ask endpoint icin query routing tasarla
- eval sorularini topla

## Baslangic Veri Kaynaklari

Ilk sprintte kapsam dar tutulmali:

- 3 BIST100 sirketi sec
- her sirket icin 1 faaliyet raporu
- her sirket icin 3-5 KAP aciklamasi
- basic market snapshot icin ornek veri olustur

## Teknik Kararlar

- Baslangicta genis veri yerine dar ama temiz veri
- Baslangicta gercek broker entegrasyonu yok
- Baslangicta market tool mock data ile calisacak
- Signal engine sprint 1'e dahil degil
- Once tool contract ve knowledge core saglamlasacak

## Sprint Sonu Basari Kriteri

Su soru tipleri calismali:

`X sirketinin son donemde yayinladigi raporlara gore borcluluk, yatirim plani veya operasyonel riskler neler?`

`GARAN icin basic market snapshot nedir?`

Ve sistem sunlari donebilmeli:

- kisa cevap
- kullanilan kaynaklar
- tarih ve dokuman bilgisi
- gerekiyorsa tool cevabi veya tool + RAG sentezi
