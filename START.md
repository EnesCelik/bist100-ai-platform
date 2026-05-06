# Ilk Calistirma

## 1. Proje klasorune gir

```bash
cd /Users/ahmetenescelik/Desktop/AiEngineer/bist100-ai-platform
```

## 2. Sanal ortam olustur

```bash
uv venv
source .venv/bin/activate
```

## 3. Paketleri kur

```bash
uv pip install -e .
```

## 4. Ortam dosyasini hazirla

```bash
cp .env.example .env
```

## 5. API uygulamasini calistir

```bash
uvicorn app.api.main:app --reload
```

## 6. API kontrol et

Tarayicida su adresi acilmali:

```text
http://127.0.0.1:8000/api/v1/health
```

Beklenen cevap:

```json
{"status":"ok"}
```

## 7. Dashboard'u calistir

Yeni bir terminalde:

```bash
cd /Users/ahmetenescelik/Desktop/AiEngineer/bist100-ai-platform
source .venv/bin/activate
streamlit run dashboard.py
```

Beklenen adres:

```text
http://localhost:8501
```
