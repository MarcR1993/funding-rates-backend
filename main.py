"""
Backend Flask Ultra-Robuste pour Funding Rates Monitor
Version production avec gestion d'erreurs maximale
"""
from flask import Flask, jsonify, request
from flask_cors import CORS
import logging
import traceback
from datetime import datetime, timedelta
import threading
import time
import os
import json
import sys
from typing import Dict, List, Optional, Tuple
import signal

# Imports avec gestion d'erreur
try:
    import pandas as pd
    import numpy as np
    import ccxt
    from ccxt import ExchangeError, NetworkError, RequestTimeout
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Installing required packages...")
    os.system("pip install ccxt pandas numpy")
    import pandas as pd
    import numpy as np
    import ccxt
    from ccxt import ExchangeError, NetworkError, RequestTimeout

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('app.log', mode='a') if os.access('.', os.W_OK) else logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Initialisation Flask
app = Flask(__name__)

# Configuration CORS ultra-permissive
CORS(app, 
     origins=["*"],
     allow_headers=["*"],
     methods=["*"],
     supports_credentials=True
)

# Configuration globale
class Config:
    CACHE_DURATION = 300  # 5 minutes
    MAX_RETRIES = 3
    REQUEST_TIMEOUT = 15
    RATE_LIMIT_DELAY = 2  # secondes entre les requêtes
    MAX_SYMBOLS_PER_EXCHANGE = 50  # Limiter pour éviter les rate limits
    SUPPORTED_EXCHANGES = ["binance", "bybit", "okx", "gate"]  # Exchanges les plus fiables

# Variables globales thread-safe
class DataStore:
    def __init__(self):
        self.funding_data = []
        self.arbitrage_data = []
        self.last_update = None
        self.errors = []
        self.lock = threading.RLock()
        self.is_updating = False

data_store = DataStore()

# Classe robuste pour funding rates
class RobustFundingRateCollector:
    def __init__(self):
        self.exchanges = {}
        self.commission_rates = {
            "binance": {"futures": 0.04, "spot": 0.1},
            "bybit": {"futures": 0.06, "spot": 0.1},
            "okx": {"futures": 0.05, "spot": 0.1},
            "gate": {"futures": 0.05, "spot": 0.2},
        }
        self.initialize_exchanges()

    def initialize_exchanges(self):
        """Initialiser les exchanges avec configuration robuste"""
        for exchange_name in Config.SUPPORTED_EXCHANGES:
            try:
                exchange_class = getattr(ccxt, exchange_name)
                self.exchanges[exchange_name] = exchange_class({
                    'timeout': Config.REQUEST_TIMEOUT * 1000,
                    'enableRateLimit': True,
                    'rateLimit': 2000,  # 2 secondes entre les requêtes
                    'sandbox': False,
                    'verbose': False,
                    'headers': {
                        'User-Agent': 'funding-rates-monitor/1.0'
                    }
                })
                logger.info(f"✅ {exchange_name} initialized")
            except Exception as e:
                logger.error(f"❌ Failed to initialize {exchange_name}: {e}")

    def fetch_funding_rates(self, exchange_name: str) -> Dict[str, float]:
        """Récupérer les funding rates d'un exchange de manière robuste"""
        if exchange_name not in self.exchanges:
            logger.error(f"❌ Exchange {exchange_name} not available")
            return {}

        exchange = self.exchanges[exchange_name]
        rates = {}
        
        try:
            logger.info(f"📡 Fetching markets from {exchange_name}...")
            
            # Récupérer les marchés avec retry
            markets = None
            for attempt in range(Config.MAX_RETRIES):
                try:
                    markets = exchange.load_markets()
                    break
                except (NetworkError, RequestTimeout) as e:
                    if attempt == Config.MAX_RETRIES - 1:
                        raise e
                    logger.warning(f"⚠️ {exchange_name} attempt {attempt + 1} failed: {e}")
                    time.sleep(Config.RATE_LIMIT_DELAY * (attempt + 1))

            if not markets:
                logger.error(f"❌ No markets loaded for {exchange_name}")
                return {}

            # Filtrer les contrats perpétuels populaires
            perpetual_symbols = []
            for symbol, market in markets.items():
                if (market.get('type') == 'swap' and 
                    market.get('linear', False) and 
                    'USDT' in symbol and
                    market.get('active', False)):
                    perpetual_symbols.append(symbol)

            # Limiter le nombre de symboles pour éviter rate limits
            perpetual_symbols = perpetual_symbols[:Config.MAX_SYMBOLS_PER_EXCHANGE]
            logger.info(f"📊 Found {len(perpetual_symbols)} perpetual contracts on {exchange_name}")

            # Récupérer les funding rates avec gestion d'erreur par symbole
            success_count = 0
            for symbol in perpetual_symbols:
                try:
                    funding_info = exchange.fetch_funding_rate(symbol)
                    if funding_info and 'fundingRate' in funding_info:
                        rates[symbol] = funding_info['fundingRate']
                        success_count += 1
                    
                    # Rate limiting agressif
                    time.sleep(Config.RATE_LIMIT_DELAY)
                    
                except Exception as e:
                    logger.debug(f"⚠️ {exchange_name} - {symbol}: {e}")
                    continue

            logger.info(f"✅ {exchange_name}: {success_count}/{len(perpetual_symbols)} rates fetched")
            return rates

        except Exception as e:
            logger.error(f"❌ {exchange_name} critical error: {e}")
            return {}

    def collect_all_rates(self) -> Tuple[List[Dict], List[str]]:
        """Collecter tous les funding rates"""
        all_data = []
        errors = []
        
        for exchange_name in Config.SUPPORTED_EXCHANGES:
            try:
                logger.info(f"🔄 Processing {exchange_name}...")
                rates = self.fetch_funding_rates(exchange_name)
                
                for symbol, rate in rates.items():
                    all_data.append({
                        'symbol': symbol,
                        'exchange': exchange_name,
                        'fundingRate': rate,
                        'timestamp': datetime.now().isoformat()
                    })
                
                if rates:
                    logger.info(f"✅ {exchange_name}: {len(rates)} rates collected")
                else:
                    error_msg = f"❌ {exchange_name}: No rates collected"
                    logger.warning(error_msg)
                    errors.append(error_msg)
                    
            except Exception as e:
                error_msg = f"❌ {exchange_name}: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)
                continue

        return all_data, errors

    def calculate_arbitrage(self, funding_data: List[Dict]) -> List[Dict]:
        """Calculer les opportunités d'arbitrage"""
        try:
            if not funding_data:
                return []

            # Grouper par symbole
            symbol_groups = {}
            for item in funding_data:
                symbol = item['symbol']
                if symbol not in symbol_groups:
                    symbol_groups[symbol] = {}
                symbol_groups[symbol][item['exchange']] = item['fundingRate']

            opportunities = []
            for symbol, exchanges in symbol_groups.items():
                if len(exchanges) < 2:
                    continue

                rates = list(exchanges.values())
                exchanges_list = list(exchanges.keys())
                
                min_rate = min(rates)
                max_rate = max(rates)
                min_exchange = exchanges_list[rates.index(min_rate)]
                max_exchange = exchanges_list[rates.index(max_rate)]
                
                divergence = (max_rate - min_rate) * 100
                
                # Calculer commissions approximatives
                commission = (self.commission_rates.get(min_exchange, {}).get('futures', 0.05) + 
                            self.commission_rates.get(max_exchange, {}).get('futures', 0.05))
                
                revenue = divergence - commission
                
                if abs(divergence) > 0.01:  # Seuil minimum de 0.01%
                    opportunities.append({
                        'symbol': symbol.replace('/USDT:USDT', ''),
                        'longExchange': min_exchange,
                        'shortExchange': max_exchange,
                        'longRate': min_rate,
                        'shortRate': max_rate,
                        'divergence': divergence,
                        'commission': commission,
                        'revenue': revenue,
                        'timestamp': datetime.now().isoformat()
                    })

            # Trier par revenue absolu décroissant
            opportunities.sort(key=lambda x: abs(x['revenue']), reverse=True)
            return opportunities[:10]  # Top 10

        except Exception as e:
            logger.error(f"💥 Arbitrage calculation error: {e}")
            return []

# Instance du collector
collector = RobustFundingRateCollector()

# Fonction de mise à jour thread-safe
def update_data():
    """Mettre à jour les données de manière thread-safe"""
    with data_store.lock:
        if data_store.is_updating:
            logger.info("⏳ Update already in progress, skipping...")
            return
        
        data_store.is_updating = True

    try:
        logger.info("🔄 Starting data update...")
        start_time = time.time()
        
        # Collecter les données
        funding_data, errors = collector.collect_all_rates()
        
        # Calculer les arbitrages
        arbitrage_data = collector.calculate_arbitrage(funding_data)
        
        # Mettre à jour le store de manière atomique
        with data_store.lock:
            data_store.funding_data = funding_data
            data_store.arbitrage_data = arbitrage_data
            data_store.errors = errors
            data_store.last_update = datetime.now()
        
        elapsed = time.time() - start_time
        logger.info(f"✅ Data update completed in {elapsed:.2f}s")
        logger.info(f"📊 {len(funding_data)} rates, {len(arbitrage_data)} arbitrages")
        
    except Exception as e:
        logger.error(f"💥 Update failed: {e}")
        logger.error(traceback.format_exc())
    finally:
        with data_store.lock:
            data_store.is_updating = False

# Thread de mise à jour en arrière-plan
def background_updater():
    """Thread de mise à jour en arrière-plan avec gestion d'erreur"""
    logger.info("🔄 Background updater started")
    
    while True:
        try:
            # Vérifier si mise à jour nécessaire
            should_update = False
            with data_store.lock:
                if (data_store.last_update is None or 
                    datetime.now() - data_store.last_update > timedelta(seconds=Config.CACHE_DURATION)):
                    should_update = True
            
            if should_update:
                update_data()
            
            time.sleep(60)  # Vérifier toutes les minutes
            
        except Exception as e:
            logger.error(f"💥 Background updater error: {e}")
            time.sleep(300)  # Attendre 5 minutes en cas d'erreur

# Headers CORS pour toutes les réponses
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', '*')
    response.headers.add('Access-Control-Allow-Methods', '*')
    response.headers.add('Access-Control-Allow-Credentials', 'true')
    return response

# Routes API
@app.route('/', methods=['GET', 'OPTIONS'])
def home():
    """Page d'accueil"""
    with data_store.lock:
        return jsonify({
            'status': 'online',
            'service': 'Funding Rates API',
            'version': '2.0',
            'last_update': data_store.last_update.isoformat() if data_store.last_update else None,
            'cached_rates': len(data_store.funding_data),
            'cached_arbitrages': len(data_store.arbitrage_data),
            'supported_exchanges': Config.SUPPORTED_EXCHANGES,
            'endpoints': {
                '/api/funding-rates': 'GET - All funding rates',
                '/api/arbitrage': 'GET - Arbitrage opportunities',
                '/api/status': 'GET - Service status'
            }
        })

@app.route('/api/funding-rates', methods=['GET', 'OPTIONS'])
def get_funding_rates():
    """Récupérer les funding rates"""
    try:
        # Force update si pas de données ou cache expiré
        with data_store.lock:
            needs_update = (not data_store.funding_data or 
                          data_store.last_update is None or
                          datetime.now() - data_store.last_update > timedelta(seconds=Config.CACHE_DURATION))
        
        if needs_update and not data_store.is_updating:
            logger.info("🔄 Cache expired, forcing update...")
            update_thread = threading.Thread(target=update_data, daemon=True)
            update_thread.start()
            
            # Attendre un peu pour avoir des données fraîches
            time.sleep(2)
        
        with data_store.lock:
            return jsonify({
                'status': 'success',
                'data': data_store.funding_data,
                'count': len(data_store.funding_data),
                'last_update': data_store.last_update.isoformat() if data_store.last_update else None,
                'errors': data_store.errors if data_store.errors else None
            })
            
    except Exception as e:
        logger.error(f"💥 API Error: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e),
            'data': []
        }), 500

@app.route('/api/arbitrage', methods=['GET', 'OPTIONS'])
def get_arbitrage():
    """Récupérer les opportunités d'arbitrage"""
    try:
        with data_store.lock:
            return jsonify({
                'status': 'success',
                'data': data_store.arbitrage_data,
                'count': len(data_store.arbitrage_data),
                'last_update': data_store.last_update.isoformat() if data_store.last_update else None
            })
    except Exception as e:
        logger.error(f"💥 Arbitrage API Error: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e),
            'data': []
        }), 500

@app.route('/api/status', methods=['GET', 'OPTIONS'])
def get_status():
    """Status détaillé de l'API"""
    with data_store.lock:
        return jsonify({
            'status': 'online',
            'last_update': data_store.last_update.isoformat() if data_store.last_update else None,
            'is_updating': data_store.is_updating,
            'cached_rates': len(data_store.funding_data),
            'cached_arbitrages': len(data_store.arbitrage_data),
            'errors': data_store.errors,
            'supported_exchanges': Config.SUPPORTED_EXCHANGES,
            'config': {
                'cache_duration': Config.CACHE_DURATION,
                'max_symbols_per_exchange': Config.MAX_SYMBOLS_PER_EXCHANGE,
                'request_timeout': Config.REQUEST_TIMEOUT
            }
        })

@app.route('/health', methods=['GET'])
def health():
    """Health check pour Render"""
    return jsonify({'status': 'healthy'}), 200

# Gestionnaires d'erreurs
@app.errorhandler(404)
def not_found(error):
    return jsonify({'status': 'error', 'message': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'status': 'error', 'message': 'Internal server error'}), 500

# Gestionnaire de signaux pour arrêt propre
def signal_handler(signum, frame):
    logger.info(f"🛑 Received signal {signum}, shutting down gracefully...")
    sys.exit(0)

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

if __name__ == '__main__':
    logger.info("🚀 Starting Robust Funding Rates API...")
    
    # Démarrer le thread de mise à jour
    updater_thread = threading.Thread(target=background_updater, daemon=True)
    updater_thread.start()
    
    # Mise à jour initiale
    logger.info("📊 Performing initial data fetch...")
    update_data()
    
    # Démarrer le serveur
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"🌐 Server starting on port {port}")
    
    app.run(
        host='0.0.0.0', 
        port=port, 
        debug=False,
        threaded=True,
        use_reloader=False
    )
