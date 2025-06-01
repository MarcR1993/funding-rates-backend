# 🔧 EXEMPLE COMPLET - TON BACKEND AVEC CORS
from flask import Flask, jsonify, request
from flask_cors import CORS  # 👈 IMPORT AJOUTÉ
import requests
from datetime import datetime
import json

app = Flask(__name__)
CORS(app)  # 👈 LIGNE AJOUTÉE - RÉSOUT LE PROBLÈME CORS

# 📡 Tes fonctions existantes (ne change rien ici)
def get_binance_funding_rates():
    """Récupère les funding rates de Binance"""
    try:
        url = "https://fapi.binance.com/fapi/v1/premiumIndex"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return [
                {
                    "exchange": "Binance",
                    "symbol": item["symbol"].replace("USDT", ""),
                    "fundingRate": float(item["lastFundingRate"]),
                    "markPrice": float(item["markPrice"]),
                    "timestamp": datetime.now().isoformat()
                }
                for item in data if item["symbol"].endswith("USDT")
            ][:50]  # Limiter à 50 pour la performance
    except Exception as e:
        print(f"Erreur Binance: {e}")
        return []

def get_bybit_funding_rates():
    """Récupère les funding rates de Bybit"""
    try:
        url = "https://api.bybit.com/v5/market/tickers?category=linear"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("retCode") == 0:
                return [
                    {
                        "exchange": "Bybit", 
                        "symbol": item["symbol"].replace("USDT", ""),
                        "fundingRate": float(item.get("fundingRate", 0)),
                        "markPrice": float(item.get("markPrice", 0)),
                        "timestamp": datetime.now().isoformat()
                    }
                    for item in data["result"]["list"] 
                    if item["symbol"].endswith("USDT") and item.get("fundingRate")
                ][:50]
    except Exception as e:
        print(f"Erreur Bybit: {e}")
        return []

def get_all_funding_rates():
    """Récupère toutes les funding rates"""
    all_rates = []
    
    # Binance
    binance_rates = get_binance_funding_rates()
    all_rates.extend(binance_rates)
    
    # Bybit  
    bybit_rates = get_bybit_funding_rates()
    all_rates.extend(bybit_rates)
    
    return all_rates

# 🌍 ROUTES AVEC CORS AUTOMATIQUE
@app.route('/')
def home():
    """Page d'accueil de l'API"""
    return jsonify({
        "message": "🚀 Funding Rates Arbitrage API",
        "version": "1.0.0",
        "status": "LIVE",
        "cors_enabled": True,  # 👈 NOUVEAU : Confirme que CORS est actif
        "endpoints": {
            "funding_rates": "/api/funding-rates",
            "arbitrage": "/api/arbitrage", 
            "health": "/api/health"
        },
        "exchanges": ["binance", "bybit", "okx", "gate"],
        "timestamp": datetime.now().isoformat()
    })

@app.route('/api/health')
def health():
    """Health check"""
    return jsonify({
        "status": "OK",
        "cors_enabled": True,  # 👈 NOUVEAU
        "timestamp": datetime.now().isoformat(),
        "message": "Backend fonctionnel avec CORS activé"
    })

@app.route('/api/funding-rates')
def get_funding_rates():
    """Récupère les funding rates en temps réel"""
    try:
        print("📡 Récupération des funding rates...")
        funding_data = get_all_funding_rates()
        
        return jsonify({
            "success": True,
            "cors_enabled": True,  # 👈 NOUVEAU
            "data": funding_data,
            "count": len(funding_data),
            "exchanges": list(set([item["exchange"] for item in funding_data])),
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        print(f"❌ Erreur funding rates: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

@app.route('/api/arbitrage')
def get_arbitrage_opportunities():
    """Calcule les opportunités d'arbitrage"""
    try:
        funding_data = get_all_funding_rates()
        
        # Grouper par symbol
        symbols = {}
        for item in funding_data:
            symbol = item["symbol"]
            if symbol not in symbols:
                symbols[symbol] = []
            symbols[symbol].append(item)
        
        # Calculer les arbitrages
        arbitrage_opportunities = []
        for symbol, rates in symbols.items():
            if len(rates) >= 2:
                rates_sorted = sorted(rates, key=lambda x: x["fundingRate"])
                lowest = rates_sorted[0]
                highest = rates_sorted[-1]
                
                divergence = highest["fundingRate"] - lowest["fundingRate"]
                if abs(divergence) > 0.0001:  # 0.01% minimum
                    arbitrage_opportunities.append({
                        "symbol": symbol,
                        "long_exchange": lowest["exchange"],
                        "short_exchange": highest["exchange"],
                        "long_rate": lowest["fundingRate"],
                        "short_rate": highest["fundingRate"],
                        "divergence": divergence,
                        "potential_profit": abs(divergence) * 100,
                        "timestamp": datetime.now().isoformat()
                    })
        
        return jsonify({
            "success": True,
            "cors_enabled": True,  # 👈 NOUVEAU
            "data": arbitrage_opportunities,
            "count": len(arbitrage_opportunities),
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

# 🚀 LANCEMENT DE L'APP
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)

# 📝 NOTES :
# 1. flask-cors==4.0.0 doit être dans requirements.txt
# 2. CORS(app) active CORS pour toutes les routes automatiquement
# 3. Tes fonctions existantes ne changent pas
# 4. Render redéploie automatiquement après commit/push
