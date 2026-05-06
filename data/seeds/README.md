# Universe Seeds

Bu klasor gercek universe import dosyalari icin kullanilir.

## Onemli Ayrim

- `POST /api/v1/companies/migrate/from-mock`
  - Sadece demo/mock dataset'i DB'ye tasir.
  - Gercek current BIST100 constituent listesini cekmez.

- `POST /api/v1/companies/universe/load-seed?seed_name=...`
  - Seed dosyasini okuyup hedef universe'u onunla senkronize eder.
  - Gercek BIST100 import yolu budur.

## Seed Formati

```json
{
  "universe_code": "bist100",
  "universe_name": "BIST 100",
  "source": "manual_bist100_seed_2026q2",
  "items": [
    {
      "ticker": "AKBNK",
      "name": "Akbank",
      "sector": "Banking",
      "signal_enabled": false,
      "is_active": true
    }
  ]
}
```

## Tipik Akis

1. `data/seeds/bist100_seed.current.json` dosyasini guncelle
2. `POST /api/v1/companies/universe/load-seed?seed_name=bist100_seed.current`
3. `GET /api/v1/companies?universe_code=bist100` ile sonucu kontrol et
