# 💰 Funding Rates Backend API

Backend robuste pour monitorer les funding rates des cryptomonnaies sur plusieurs exchanges et détecter les opportunités d'arbitrage.

## 🚀 Features

- ✅ Collecte automatique des funding rates
- ✅ Calcul d'opportunités d'arbitrage en temps réel
- ✅ API REST avec CORS complet
- ✅ Cache intelligent pour performances
- ✅ Gestion d'erreurs robuste
- ✅ Thread-safe et production-ready

## 📊 Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | API status et informations |
| `/api/funding-rates` | GET | Tous les funding rates |
| `/api/arbitrage` | GET | Top 10 opportunités d'arbitrage |
| `/api/status` | GET | Status détaillé du service |
| `/health` | GET | Health check pour monitoring |

## 🏛️ Exchanges Supportés

- **Binance** - Leader mondial
- **Bybit** - Derivatives populaire  
- **OKX** - Exchange majeur
- **Gate.io** - Large sélection d'altcoins

## 🔧 Configuration

- **Cache:** 5 minutes
- **Rate Limiting:** 2s entre requêtes
- **Timeout:** 15s par exchange
- **Max Symbols:** 50 par exchange

## 📈 Example Response

```json
{
  "status": "success",
  "data": [
    {
      "symbol": "BTC/USDT:USDT",
      "exchange": "binance",
      "fundingRate": 0.0001,
      "timestamp": "2025-01-01T12:00:00"
    }
  ],
  "count": 150,
  "last_update": "2025-01-01T12:00:00"
}
```

## 🚀 Deployment

Déployé sur Render avec auto-scaling et monitoring 24/7.

- **Platform:** Render
- **Runtime:** Python 3.11
- **Server:** Gunicorn
- **Monitoring:** Health checks automatiques

## 📝 Logs

Le service génère des logs détaillés pour monitoring:
- ✅ Succès des requêtes par exchange
- ⚠️ Rate limits et retry automatiques  
- ❌ Erreurs avec stack traces
- 📊 Métriques de performance

---

**Status:** 🟢 Production Ready
