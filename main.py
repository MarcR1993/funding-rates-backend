"""
🚀 Backend Flask pour Funding Rates - VERSION 3 EXCHANGES
Optimisé pour: Binance, KuCoin, Bybit
Plus rapide et plus stable
"""
from flask import Flask, jsonify, request
from flask_cors import CORS
import ccxt
import asyncio
import threading
import time
import logging
import sys
import os
from datetime import datetime, timedelta
from collections import defaultdict
import traceback

# Configuration logging
logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

# Initialisation Flask
app = Flask(__name__)
CORS(app, origins=["*"])

logger.info("🚀 Starting 3-Exchange Funding Rates API (Binance, KuCoin, Bybit)...")

# Configuration exchanges - SEULEMENT 3 EXCHANGES FIABLES
EXCHANGES_CONFIG = {
    'binance': ccxt.binance({
        'enableRateLimit': True, 
        'sandbox': False,
        'timeout': 20000,
        'rateLimit': 1200
    }),
    'kucoin': ccxt.kucoin({
        'enableRateLimit': True, 
        'sandbox': False,
        'timeout': 20000,
        'rateLimit': 1000
    }),
    'bybit': ccxt.bybit({
        'enableRateLimit': True, 
        'sandbox': False,
        'timeout': 20000,
        'rateLimit': 1000
    })
}

# Symboles ciblés - Plus large sélection
TARGET_SYMBOLS = [
    'BTC/USDT:USDT', 'ETH/USDT:USDT', 'SOL/USDT:USDT', 'XRP/USDT:USDT', 
    'DOGE/USDT:USDT', 'ADA/USDT:USDT', 'AVAX/USDT:USDT', 'MATIC/USDT:USDT',
    'LINK/USDT:USDT', 'DOT/USDT:USDT', 'UNI/USDT:USDT', 'ATOM/USDT:USDT',
    'FIL/USDT:USDT', 'LTC/USDT:USDT', 'BCH/USDT:USDT', 'ETC/USDT:USDT',
    'NEAR/USDT:USDT', 'FTM/USDT:USDT', 'SAND/USDT:USDT', 'MANA/USDT:USDT',
    'ICP/USDT:USDT', 'AAVE/USDT:USDT', 'CRV/USDT:USDT', 'SUSHI/USDT:USDT',
    'COMP/USDT:USDT', 'YFI/USDT:USDT', 'SNX/USDT:USDT', 'MKR/USDT:USDT'
]

# Variables globales
funding_data_cache = []
arbitrage_opportunities = []
last_update = None
exchange_status = {}

def get_next_funding_time():
    """Calcule le prochain horaire de funding rate (toutes les 8h)"""
    now = datetime.utcnow()
    funding_hours = [0, 8, 16]  # 00:00, 08:00, 16:00 UTC
    
    for hour in funding_hours:
        next_time = now.replace(hour=hour, minute=0, second=0, microsecond=0)
        if next_time > now:
            return next_time
    
    # Si on a dépassé 16:00, le prochain est demain à 00:00
    tomorrow = now + timedelta(days=1)
    return tomorrow.replace(hour=0, minute=0, second=0, microsecond=0)

def time_until_funding():
    """Temps restant jusqu'au prochain funding"""
    next_funding = get_next_funding_time()
    now = datetime.utcnow()
    delta = next_funding - now
    
    hours = delta.total_seconds() // 3600
    minutes = (delta.total_seconds() % 3600) // 60
    
    return {
        'next_funding_utc': next_funding.isoformat() + 'Z',
        'hours_remaining': int(hours),
        'minutes_remaining': int(minutes),
        'total_minutes': int(delta.total_seconds() // 60)
    }

async def fetch_funding_rate_safe(exchange_name, exchange, symbol):
    """Récupère le funding rate avec gestion d'erreurs robuste"""
    try:
        # Vérifier si l'exchange supporte fetch_funding_rate
        if not hasattr(exchange, 'fetch_funding_rate'):
            logger.warning(f"⚠️ {exchange_name} doesn't support fetch_funding_rate")
            return None
        
        # Timeout personnalisé pour chaque exchange
        funding = await asyncio.wait_for(
            exchange.fetch_funding_rate(symbol), 
            timeout=15
        )
        
        rate = funding.get('fundingRate')
        
        if rate is not None and isinstance(rate, (int, float)):
            logger.info(f"✅ {exchange_name}: {symbol} = {rate:.6f}")
            return {
                'symbol': symbol,
                'exchange': exchange_name,
                'fundingRate': float(rate),
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            }
        else:
            logger.warning(f"⚠️ {exchange_name} {symbol}: Invalid rate data")
            return None
        
    except asyncio.TimeoutError:
        logger.warning(f"⏰ {exchange_name} {symbol}: Timeout")
        return None
    except Exception as e:
        error_msg = str(e)[:100]
        logger.warning(f"⚠️ {exchange_name} {symbol}: {error_msg}")
        return None

async def fetch_exchange_data(exchange_name, exchange):
    """Récupère toutes les données d'un exchange"""
    logger.info(f"📊 Fetching from {exchange_name}...")
    
    exchange_rates = []
    errors = 0
    
    try:
        # Charger les markets avec timeout
        markets = await asyncio.wait_for(exchange.load_markets(), timeout=20)
        available_symbols = [s for s in TARGET_SYMBOLS if s in markets]
        
        logger.info(f"📋 {exchange_name}: {len(available_symbols)} symbols available")
        
        # Limiter à 20 symboles pour éviter les rate limits
        limited_symbols = available_symbols[:20]
        
        # Fetch avec semaphore pour limiter la concurrence
        semaphore = asyncio.Semaphore(3)  # Max 3 requêtes simultanées
        
        async def fetch_with_semaphore(symbol):
            async with semaphore:
                return await fetch_funding_rate_safe(exchange_name, exchange, symbol)
        
        # Lancer toutes les requêtes
        tasks = [fetch_with_semaphore(symbol) for symbol in limited_symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Traiter les résultats
        for result in results:
            if isinstance(result, dict) and result is not None:
                exchange_rates.append(result)
            elif isinstance(result, Exception):
                errors += 1
            else:
                errors += 1
        
        success_count = len(exchange_rates)
        logger.info(f"✅ {exchange_name}: {success_count} rates fetched, {errors} errors")
        
        return exchange_rates, {
            'status': 'success',
            'count': success_count,
            'errors': errors,
            'last_update': datetime.utcnow().isoformat() + 'Z'
        }
        
    except Exception as e:
        logger.error(f"❌ {exchange_name} failed completely: {e}")
        return [], {
            'status': 'error',
            'count': 0,
            'errors': 1,
            'error_message': str(e)[:200],
            'last_update': datetime.utcnow().isoformat() + 'Z'
        }

async def fetch_all_funding_rates():
    """Récupère tous les funding rates de tous les exchanges"""
    global funding_data_cache, last_update, exchange_status
    
    logger.info("📡 Fetching funding rates from 3 exchanges...")
    start_time = time.time()
    
    all_rates = []
    exchange_status = {}
    
    # Fetch chaque exchange en parallèle
    tasks = []
    for exchange_name, exchange in EXCHANGES_CONFIG.items():
        task = fetch_exchange_data(exchange_name, exchange)
        tasks.append((exchange_name, task))
    
    # Attendre tous les résultats avec timeout global
    try:
        results = await asyncio.wait_for(
            asyncio.gather(*[task for _, task in tasks], return_exceptions=True),
            timeout=60  # 1 minute max pour tout
        )
        
        # Traiter les résultats
        for (exchange_name, _), result in zip(tasks, results):
            if isinstance(result, tuple):
                rates, status = result
                all_rates.extend(rates)
                exchange_status[exchange_name] = status
            else:
                logger.error(f"❌ {exchange_name}: {result}")
                exchange_status[exchange_name] = {
                    'status': 'error',
                    'count': 0,
                    'errors': 1,
                    'error_message': str(result)[:200]
                }
        
    except asyncio.TimeoutError:
        logger.error("❌ Global timeout reached (60s)")
        for exchange_name in EXCHANGES_CONFIG.keys():
            if exchange_name not in exchange_status:
                exchange_status[exchange_name] = {
                    'status': 'timeout',
                    'count': 0,
                    'errors': 1
                }
    
    funding_data_cache = all_rates
    last_update = datetime.utcnow()
    
    duration = time.time() - start_time
    logger.info(f"🎉 Fetched {len(all_rates)} total rates in {duration:.1f}s")
    
    # Calculer les arbitrages
    calculate_arbitrage_opportunities()

def calculate_arbitrage_opportunities():
    """Calcule les opportunités d'arbitrage entre les 3 exchanges"""
    global arbitrage_opportunities
    
    logger.info("🔍 Calculating arbitrage opportunities...")
    
    # Grouper par symbole
    by_symbol = defaultdict(list)
    for rate in funding_data_cache:
        symbol = rate['symbol']
        by_symbol[symbol].append(rate)
    
    opportunities = []
    
    for symbol, rates in by_symbol.items():
        if len(rates) < 2:
            continue
        
        # Trouver min et max
        min_rate = min(rates, key=lambda x: x['fundingRate'])
        max_rate = max(rates, key=lambda x: x['fundingRate'])
        
        divergence = max_rate['fundingRate'] - min_rate['fundingRate']
        
        # Seuil minimal pour considérer comme arbitrage (0.005% = 0.00005)
        if abs(divergence) > 0.00005:
            
            # Calcul des revenus estimés
            commission_long = 0.0004   # 0.04% Binance/Bybit maker
            commission_short = 0.0004  # 0.04% commission moyenne
            total_commission = commission_long + commission_short
            
            # Revenue net sur 8h (1 période de funding)
            revenue_8h = abs(divergence) - total_commission
            
            # Revenue annualisé (3 fois par jour * 365 jours)
            revenue_annual = revenue_8h * 3 * 365 * 100  # En pourcentage
            
            # Only show profitable opportunities
            if revenue_annual > 1:  # Au moins 1% annuel
                
                # Déterminer la stratégie optimale
                if divergence > 0:
                    strategy = "Long/Short"
                    long_exchange = min_rate['exchange']
                    short_exchange = max_rate['exchange']
                    long_rate = min_rate['fundingRate']
                    short_rate = max_rate['fundingRate']
                else:
                    strategy = "Short/Long"
                    long_exchange = max_rate['exchange']
                    short_exchange = min_rate['exchange']
                    long_rate = max_rate['fundingRate']
                    short_rate = min_rate['fundingRate']
                
                # Timing optimal
                funding_info = time_until_funding()
                
                # Signal d'entrée/sortie
                if funding_info['total_minutes'] > 30:
                    signal = "🟢 ENTRER MAINTENANT"
                    signal_detail = f"Ouvrir position {funding_info['hours_remaining']}h{funding_info['minutes_remaining']}m avant funding"
                elif funding_info['total_minutes'] > 5:
                    signal = "🟡 ENTRER BIENTÔT"
                    signal_detail = f"Position à ouvrir dans {funding_info['minutes_remaining']}m"
                else:
                    signal = "🔴 SORTIR"
                    signal_detail = "Fermer position avant funding dans <5min"
                
                opportunity = {
                    'symbol': symbol.split('/')[0],
                    'strategy': strategy,
                    'longExchange': long_exchange,
                    'shortExchange': short_exchange,
                    'longRate': round(long_rate, 6),
                    'shortRate': round(short_rate, 6),
                    'divergence': round(abs(divergence), 6),
                    'divergence_pct': round(abs(divergence) * 100, 4),
                    'commission': round(total_commission, 6),
                    'revenue_8h': round(revenue_8h, 6),
                    'revenue_8h_pct': round(revenue_8h * 100, 4),
                    'revenue_annual_pct': round(revenue_annual, 2),
                    'signal': signal,
                    'signal_detail': signal_detail,
                    'next_funding_utc': funding_info['next_funding_utc'],
                    'minutes_to_funding': funding_info['total_minutes'],
                    'timestamp': datetime.utcnow().isoformat() + 'Z'
                }
                
                opportunities.append(opportunity)
    
    # Trier par revenue décroissant
    opportunities.sort(key=lambda x: x['revenue_annual_pct'], reverse=True)
    arbitrage_opportunities = opportunities[:15]  # Top 15
    
    logger.info(f"💰 Found {len(arbitrage_opportunities)} profitable arbitrage opportunities")

def background_updater():
    """Met à jour les données toutes les 3 minutes"""
    logger.info("🔄 Background updater started (3-minute intervals)")
    
    while True:
        try:
            logger.info("📊 Starting background data update...")
            
            # Créer un nouveau event loop pour ce thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Fetch des données
            loop.run_until_complete(fetch_all_funding_rates())
            loop.close()
            
            logger.info(f"✅ Background update completed - {len(funding_data_cache)} rates cached")
            
            # Attendre 3 minutes avant la prochaine mise à jour
            time.sleep(180)
            
        except Exception as e:
            logger.error(f"❌ Background update failed: {e}")
            logger.error(traceback.format_exc())
            time.sleep(60)  # Retry dans 1 minute en cas d'erreur

# Routes Flask
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', '*')
    response.headers.add('Access-Control-Allow-Methods', '*')
    return response

@app.route('/', methods=['GET', 'OPTIONS'])
def home():
    return jsonify({
        'status': 'online',
        'service': 'Funding Rates API - 3 EXCHANGES',
        'version': '4.0-optimized',
        'exchanges': ['Binance', 'KuCoin', 'Bybit'],
        'features': [
            'Optimized for 3 major exchanges',
            'Faster data collection (3min updates)',
            'Robust error handling',
            'Profitable arbitrage detection'
        ],
        'funding_schedule': '00:00, 08:00, 16:00 UTC',
        'next_funding': time_until_funding(),
        'endpoints': {
            '/api/funding-rates': 'GET - All funding rates',
            '/api/arbitrage': 'GET - Profitable arbitrage opportunities',
            '/api/status': 'GET - Service status',
            '/health': 'GET - Health check'
        },
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    })

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    }), 200

@app.route('/api/status', methods=['GET', 'OPTIONS'])
def get_status():
    return jsonify({
        'status': 'online',
        'service': 'Funding Rates API',
        'version': '4.0-optimized',
        'last_update': last_update.isoformat() + 'Z' if last_update else None,
        'cached_rates_count': len(funding_data_cache),
        'arbitrage_opportunities_count': len(arbitrage_opportunities),
        'exchange_status': exchange_status,
        'next_funding': time_until_funding(),
        'supported_exchanges': ['binance', 'kucoin', 'bybit'],
        'update_interval': '3 minutes',
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    })

@app.route('/api/funding-rates', methods=['GET', 'OPTIONS'])
def get_funding_rates():
    logger.info("📍 FUNDING RATES endpoint called")
    
    return jsonify({
        'status': 'success',
        'data': funding_data_cache,
        'count': len(funding_data_cache),
        'last_update': last_update.isoformat() + 'Z' if last_update else None,
        'next_funding': time_until_funding(),
        'exchange_status': exchange_status,
        'message': f'Live data from {len(EXCHANGES_CONFIG)} exchanges',
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    })

@app.route('/api/arbitrage', methods=['GET', 'OPTIONS'])
def get_arbitrage():
    logger.info("📍 ARBITRAGE endpoint called")
    
    return jsonify({
        'status': 'success',
        'data': arbitrage_opportunities,
        'count': len(arbitrage_opportunities),
        'last_update': last_update.isoformat() + 'Z' if last_update else None,
        'next_funding': time_until_funding(),
        'funding_schedule': '00:00, 08:00, 16:00 UTC',
        'exchanges': ['Binance', 'KuCoin', 'Bybit'],
        'message': 'Profitable arbitrage opportunities between 3 exchanges',
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    })

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'status': 'error',
        'message': f'Endpoint not found: {request.path}',
        'available_endpoints': ['/', '/health', '/api/status', '/api/funding-rates', '/api/arbitrage'],
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    }), 404

if __name__ == '__main__':
    logger.info("🌐 Starting optimized Flask server...")
    
    # Initialiser les exchanges
    for name, exchange in EXCHANGES_CONFIG.items():
        try:
            logger.info(f"✅ {name} initialized")
            exchange_status[name] = {'status': 'initialized'}
        except Exception as e:
            logger.error(f"❌ {name} failed to initialize: {e}")
            exchange_status[name] = {'status': 'error', 'error': str(e)}
    
    # Démarrer le background updater
    update_thread = threading.Thread(target=background_updater, daemon=True)
    update_thread.start()
    
    # Premier fetch synchrone
    logger.info("📊 Performing initial data fetch...")
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(fetch_all_funding_rates())
        loop.close()
        logger.info(f"✅ Initial fetch completed - {len(funding_data_cache)} rates loaded")
    except Exception as e:
        logger.error(f"❌ Initial fetch failed: {e}")
    
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"🌐 Server starting on port {port}")
    
    app.run(
        host='0.0.0.0',
        port=port,
        debug=False,
        threaded=True
    )
