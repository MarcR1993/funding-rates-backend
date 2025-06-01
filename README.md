# 🚀 Funding Rates API - Backend

API professionnelle pour l'arbitrage de funding rates crypto en temps réel.

## 🏢 Exchanges supportés

- **Binance** - Futures USDT
- **Bybit** - Linear Perpetual  
- **OKX** - USDT Swaps
- **Gate.io** - Futures USDT

## 🪙 Cryptos surveillées

BTC, ETH, SOL, ADA, DOT, MATIC, LINK

## 📡 Endpoints

### GET `/api/funding-rates`
Récupère tous les funding rates en temps réel.

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "exchange": "Binance",
      "symbol": "BTC",
      "fundingRate": 0.0001,
      "nextFunding": 1703952000000,
      "markPrice": 43250.5,
      "timestamp": "2024-01-01T12:00:00"
    }
  ],
  "totalPairs": 28,
  "exchanges": {
    "binance": 7,
    "bybit": 7,
    "okx": 7,
    "gate": 7
  },
  "responseTime": 2.34
}
```

### GET `/api/arbitrage`
Calcule les meilleures opportunités d'arbitrage.

**Response:**
```json
{
  "success": true,
  "opportunities": [
    {
      "symbol": "BTC",
      "longExchange": "gate", 
      "shortExchange": "binance",
      "longRate": 0.0001,
      "shortRate": 0.0008,
      "divergence": 0.07,
      "totalCommission": 0.18,
      "revenueNet": -0.11,
      "aprGross": 76.65,
      "aprNet": -120.45,
      "profitability": -157.14
    }
  ],
  "totalOpportunities": 5
}
```

### GET `/api/health`
Statut de l'API.

## 🚀 Déploiement

### Render
1. Connect GitHub repo
2. Build Command: `pip install -r requirements.txt`
3. Start Command: `python main.py`

### Local
```bash
pip install -r requirements.txt
python main.py
```

## 🔗 Frontend

Compatible avec : https://marcr1993.github.io/funding-rates-bot/

## ⚙️ Configuration

Les commissions sont configurées selon les tarifs officiels de chaque exchange (maker/taker).

## 📊 Performance

- **Response time** : < 3 secondes
- **Timeout** : 30 secondes max
- **Cache** : Pas de cache (données live)
- **Rate limiting** : Géré par CCXT

## 🛠️ Tech Stack

- **FastAPI** - Framework web
- **CCXT** - APIs crypto
- **Pandas** - Analyse des données  
- **Asyncio** - Programmation asynchrone
