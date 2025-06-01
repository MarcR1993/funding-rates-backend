# main.py - API Funding Rates optimisée pour Render
import asyncio
import json
import os
from datetime import datetime
from typing import Dict, List, Optional

import ccxt.async_support as ccxt
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import numpy as np

# Configuration
app = FastAPI(
    title="Funding Rates Arbitrage API",
    description="API professionnelle pour l'arbitrage de funding rates crypto",
    version="1.0.0"
)

# CORS pour permettre les appels depuis GitHub Pages
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://marcr1993.github.io",
        "https://*.github.io",
        "http://localhost:3000",
        "http://127.0.0.1:5500",
        "*"  # Pour les tests
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class FundingRateArbitrage:
    def __init__(self):
        # Exchanges supportés avec priorité
        self.exchanges = ["binance", "bybit", "okx", "gate"]  # Réduit pour Render
        self.supported_cryptos = ['BTC', 'ETH', 'SOL', 'ADA', 'DOT', 'MATIC', 'LINK']
        
        # Table des commissions (du code Python original)
        self.commissions = {
            "binance": {
                "spot": {"taker": 0.1, "maker": 0.1},
                "futures": {"taker": 0.04, "maker": 0.02},
            },
            "bybit": {
                "spot": {"rate": 0.1},
                "futures": {"taker": 0.06, "maker": 0.01},
            },
            "okx": {
                "spot": {"taker": 0.1, "maker": 0.08},
                "futures": {"taker": 0.05, "maker": 0.02},
            },
            "gate": {
                "spot": {"taker": 0.2, "maker": 0.2},
                "futures": {"taker": 0.05, "maker": 0.015},
            }
        }

    async def fetch_exchange_funding_rates(self, exchange_name: str) -> Dict:
        """Récupérer les funding rates d'un exchange spécifique"""
        try:
            print(f"🔄 Fetching {exchange_name}...")
            
            exchange_class = getattr(ccxt, exchange_name)
            exchange = exchange_class({
                'enableRateLimit': True,
                'timeout': 10000,  # 10 secondes timeout
                'sandbox': False,
            })
            
            funding_rates = {}
            
            if exchange_name == "binance":
                # Optimisation pour Binance - endpoint direct
                try:
                    premium_index = await exchange.fetch_funding_rates()
                    for symbol, data in premium_index.items():
                        if (symbol.endswith('USDT') and 
                            any(symbol.startswith(f"{crypto}/") for crypto in self.supported_cryptos)):
                            
                            clean_symbol = symbol.replace('/USDT:USDT', '')
                            funding_rates[clean_symbol] = {
                                'fundingRate': data.get('fundingRate', 0),
                                'nextFunding': data.get('timestamp', datetime.now().timestamp() * 1000),
                                'markPrice': data.get('markPrice', 0),
                            }
                except Exception as e:
                    print(f"Binance premium index failed: {e}")
            
            else:
                # Pour autres exchanges - méthode standard
                try:
                    markets = await exchange.load_markets()
                    
                    # Filtrer les symboles pertinents
                    target_symbols = [
                        symbol for symbol, market in markets.items()
                        if (market.get('linear') and 
                            symbol.endswith('USDT') and
                            any(symbol.startswith(f"{crypto}/") for crypto in self.supported_cryptos))
                    ]
                    
                    # Limiter pour éviter les timeouts
                    target_symbols = target_symbols[:10]
                    
                    for symbol in target_symbols:
                        try:
                            funding_data = await exchange.fetch_funding_rate(symbol)
                            clean_symbol = symbol.replace('/USDT:USDT', '')
                            
                            funding_rates[clean_symbol] = {
                                'fundingRate': funding_data.get('fundingRate', 0),
                                'nextFunding': funding_data.get('timestamp', datetime.now().timestamp() * 1000),
                                'markPrice': funding_data.get('markPrice', 0),
                            }
                        except Exception as e:
                            continue
                            
                except Exception as e:
                    print(f"Error loading markets for {exchange_name}: {e}")
            
            await exchange.close()
            print(f"✅ {exchange_name}: {len(funding_rates)} pairs fetched")
            return funding_rates
            
        except Exception as e:
            print(f"❌ {exchange_name} failed: {e}")
            return {}

    async def fetch_all_funding_rates(self) -> Dict:
        """Récupérer toutes les données en parallèle avec timeout"""
        try:
            # Timeout global pour Render (30s max)
            tasks = [
                asyncio.wait_for(
                    self.fetch_exchange_funding_rates(exchange), 
                    timeout=8.0  # 8s par exchange
                ) 
                for exchange in self.exchanges
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            all_data = {}
            for i, result in enumerate(results):
                exchange_name = self.exchanges[i]
                if isinstance(result, dict) and result:
                    all_data[exchange_name] = result
                else:
                    print(f"No data from {exchange_name}")
                    all_data[exchange_name] = {}
            
            return all_data
            
        except Exception as e:
            print(f"Error in fetch_all_funding_rates: {e}")
            return {}

    def calculate_arbitrage_opportunities(self, exchange_data: Dict) -> List[Dict]:
        """Calculer les opportunités d'arbitrage"""
        opportunities = []
        
        # Récupérer tous les symboles uniques
        all_symbols = set()
        for exchange_rates in exchange_data.values():
            all_symbols.update(exchange_rates.keys())
        
        for symbol in all_symbols:
            rates_by_exchange = {}
            
            # Collecter les rates pour ce symbole
            for exchange, rates in exchange_data.items():
                if symbol in rates and rates[symbol]['fundingRate'] is not None:
                    rates_by_exchange[exchange] = rates[symbol]['fundingRate']
            
            # Besoin d'au moins 2 exchanges
            if len(rates_by_exchange) < 2:
                continue
            
            # Trouver max et min
            max_exchange = max(rates_by_exchange, key=rates_by_exchange.get)
            min_exchange = min(rates_by_exchange, key=rates_by_exchange.get)
            max_rate = rates_by_exchange[max_exchange]
            min_rate = rates_by_exchange[min_exchange]
            
            # Calculer métriques
            divergence_abs = abs(max_rate - min_rate)
            divergence_pct = divergence_abs * 100
            
            # Commissions
            max_comm = self.get_commission(max_exchange, "futures", taker=True)
            min_comm = self.get_commission(min_exchange, "futures", taker=True)
            total_commission = 2 * (max_comm + min_comm)
            
            # Revenue net
            revenue_net = divergence_pct - total_commission
            
            # APR (3 fundings par jour, 365 jours)
            apr_gross = divergence_pct * 365 * 3
            apr_net = revenue_net * 365 * 3
            
            # Seulement les opportunités rentables
            if revenue_net > 0:
                opportunities.append({
                    'symbol': symbol,
                    'longExchange': min_exchange,
                    'shortExchange': max_exchange,
                    'longRate': min_rate,
                    'shortRate': max_rate,
                    'divergence': divergence_pct,
                    'totalCommission': total_commission,
                    'revenueNet': revenue_net,
                    'aprGross': apr_gross,
                    'aprNet': apr_net,
                    'profitability': (revenue_net / divergence_pct * 100) if divergence_pct > 0 else 0,
                    'timestamp': datetime.now().isoformat()
                })
        
        # Trier par APR net décroissant
        opportunities.sort(key=lambda x: x['aprNet'], reverse=True)
        return opportunities

    def get_commission(self, exchange: str, trade: str, taker: bool = True) -> float:
        """Récupérer commission selon exchange et type"""
        if exchange not in self.commissions:
            return 0.1
        
        exchange_fees = self.commissions[exchange]
        if trade not in exchange_fees:
            return 0.1
        
        trade_fees = exchange_fees[trade]
        
        if 'rate' in trade_fees:
            return trade_fees['rate']
        
        return trade_fees.get('taker' if taker else 'maker', 0.1)

# Instance globale
arbitrage = FundingRateArbitrage()

@app.get("/")
async def root():
    return {
        "message": "🚀 Funding Rates Arbitrage API",
        "version": "1.0.0",
        "status": "LIVE",
        "endpoints": {
            "funding_rates": "/api/funding-rates",
            "arbitrage": "/api/arbitrage", 
            "health": "/api/health"
        },
        "exchanges": arbitrage.exchanges,
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/health")
async def health_check():
    return {
        "status": "OK",
        "environment": "production",
        "timestamp": datetime.now().isoformat(),
        "exchanges": arbitrage.exchanges,
        "supported_cryptos": arbitrage.supported_cryptos,
        "uptime": "running"
    }

@app.get("/api/funding-rates")
async def get_funding_rates():
    """Endpoint principal - Tous les funding rates"""
    try:
        print("🔄 Fetching funding rates from all exchanges...")
        start_time = datetime.now()
        
        # Récupérer données de tous les exchanges
        exchange_data = await arbitrage.fetch_all_funding_rates()
        
        # Formater pour le frontend
        formatted_data = []
        exchange_stats = {}
        
        for exchange, symbols_data in exchange_data.items():
            exchange_stats[exchange] = len(symbols_data)
            
            for symbol, data in symbols_data.items():
                formatted_data.append({
                    'exchange': exchange.capitalize(),
                    'symbol': symbol,
                    'fundingRate': data['fundingRate'],
                    'nextFunding': data['nextFunding'],
                    'markPrice': data['markPrice'],
                    'timestamp': datetime.now().isoformat()
                })
        
        end_time = datetime.now()
        response_time = (end_time - start_time).total_seconds()
        
        print(f"✅ Collection completed: {len(formatted_data)} pairs in {response_time:.2f}s")
        
        return {
            "success": True,
            "data": formatted_data,
            "totalPairs": len(formatted_data),
            "exchanges": exchange_stats,
            "responseTime": response_time,
            "timestamp": datetime.now().isoformat(),
            "cached": False
        }
        
    except Exception as e:
        print(f"❌ Error in get_funding_rates: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching funding rates: {str(e)}")

@app.get("/api/arbitrage")
async def get_arbitrage_opportunities():
    """Endpoint arbitrage - Top opportunités"""
    try:
        print("🔄 Calculating arbitrage opportunities...")
        
        # Récupérer les données
        exchange_data = await arbitrage.fetch_all_funding_rates()
        
        # Calculer les opportunités
        opportunities = arbitrage.calculate_arbitrage_opportunities(exchange_data)
        
        return {
            "success": True,
            "opportunities": opportunities[:15],  # Top 15
            "totalOpportunities": len(opportunities),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        print(f"❌ Error calculating arbitrage: {e}")
        raise HTTPException(status_code=500, detail=f"Error calculating arbitrage: {str(e)}")

# Point d'entrée pour Render
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
