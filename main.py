"""
🚀 Backend Flask avec APIs Directes des Exchanges
SOLUTION OPTIMISÉE pour les funding rates + arbitrage
"""
from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import threading
import time
import logging
import sys
import os
from datetime import datetime, timedelta
from collections import defaultdict
import json

# Configuration logging
logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

# Initialisation Flask
app = Flask(__name__)
CORS(app, origins=["*"])

logger.info("🚀 Starting Direct Exchange APIs Backend - OPTIMIZED SOLUTION!")

# Configuration des APIs des exchanges
EXCHANGE_CONFIGS = {
    'binance': {
        'name': 'Binance',
        'base_url': 'https://fapi.binance.com',
        'endpoints': {
            'funding_rate': '/fapi/v1/fundingRate',
            'premium_index': '/fapi/v1/premiumIndex'
        },
        'headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
    },
    'kucoin': {
        'name': 'KuCoin',
        'base_url': 'https://api-futures.kucoin.com',
        'endpoints': {
            'funding_rate': '/api/v1/funding-rate'
        },
        'headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
    },
    'bybit': {
        'name': 'Bybit',
        'base_url': 'https://api.bybit.com',
        'endpoints': {
            'funding_rate': '/v5/market/funding/history',
            'instruments': '/v5/market/instruments-info'
        },
        'headers': {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
    },
    'okx': {
        'name': 'OKX',
        'base_url': 'https://www.okx.com',
        'endpoints': {
            'funding_rate': '/api/v5/public/funding-rate',
            'instruments': '/api/v5/public/instruments'
        },
        'headers': {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'
        }
    }
}

# Symboles principaux à surveiller
TARGET_SYMBOLS = ['BTC', 'ETH', 'SOL', 'XRP', 'DOGE', 'ADA', 'AVAX', 'MATIC', 'LINK', 'DOT']

# Variables globales
funding_data_cache = []
arbitrage_opportunities = []
last_update = None
api_status = {'status': 'initializing', 'errors': 0, 'exchange_status': {}}

def get_next_funding_time():
    """Calcule le prochain horaire de funding rate"""
    now = datetime.utcnow()
    funding_hours = [0, 8, 16]  # 00:00, 08:00, 16:00 UTC
    
    for hour in funding_hours:
        next_time = now.replace(hour=hour, minute=0, second=0, microsecond=0)
        if next_time > now:
            return next_time
    
    tomorrow = now + timedelta(days=1)
    return tomorrow.replace(hour=0, minute=0, second=0, microsecond=0)

def time_until_funding():
    """Temps jusqu'au prochain funding"""
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

def fetch_binance_funding_rates():
    """Récupère les funding rates de Binance"""
    try:
        config = EXCHANGE_CONFIGS['binance']
        url = f"{config['base_url']}{config['endpoints']['funding_rate']}"
        
        logger.info("📡 Fetching Binance funding rates...")
        
        response = requests.get(url, headers=config['headers'], timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            results = []
            
            for item in data[-100:]:  # 100 derniers
                symbol = item.get('symbol', '')
                funding_rate = item.get('fundingRate')
                funding_time = item.get('fundingTime')
                
                if symbol.endswith('USDT') and funding_rate is not None:
                    clean_symbol = symbol.replace('USDT', '') + '/USDT:USDT'
                    
                    results.append({
                        'symbol': clean_symbol,
                        'base_symbol': symbol.replace('USDT', ''),
                        'exchange': 'binance',
                        'fundingRate': float(funding_rate),
                        'fundingTime': funding_time,
                        'nextFundingTime': funding_time + 28800000 if funding_time else None,  # +8h
                        'timestamp': datetime.utcnow().isoformat() + 'Z'
                    })
            
            logger.info(f"✅ Binance: {len(results)} funding rates")
            api_status['exchange_status']['binance'] = {'status': 'success', 'count': len(results)}
            return results
            
        else:
            logger.error(f"❌ Binance failed: {response.status_code}")
            api_status['exchange_status']['binance'] = {'status': 'error', 'code': response.status_code}
            return []
            
    except Exception as e:
        logger.error(f"❌ Binance error: {e}")
        api_status['exchange_status']['binance'] = {'status': 'error', 'error': str(e)[:200]}
        return []

def fetch_kucoin_funding_rates():
    """Récupère les funding rates de KuCoin"""
    try:
        config = EXCHANGE_CONFIGS['kucoin']
        results = []
        
        # KuCoin nécessite de spécifier chaque symbole
        for base_symbol in TARGET_SYMBOLS:
            try:
                symbol = f"{base_symbol}USDTM"  # Format KuCoin
                url = f"{config['base_url']}{config['endpoints']['funding_rate']}/{symbol}"
                
                logger.info(f"📡 Fetching KuCoin {symbol}...")
                
                response = requests.get(url, headers=config['headers'], timeout=20)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if 'data' in data and data['data']:
                        item = data['data']
                        funding_rate = item.get('value')
                        
                        if funding_rate is not None:
                            clean_symbol = f"{base_symbol}/USDT:USDT"
                            
                            results.append({
                                'symbol': clean_symbol,
                                'base_symbol': base_symbol,
                                'exchange': 'kucoin',
                                'fundingRate': float(funding_rate),
                                'fundingTime': None,
                                'nextFundingTime': None,
                                'timestamp': datetime.utcnow().isoformat() + 'Z'
                            })
                
                time.sleep(0.2)  # Rate limiting
                
            except Exception as e:
                logger.warning(f"⚠️ KuCoin {base_symbol} error: {e}")
                continue
        
        logger.info(f"✅ KuCoin: {len(results)} funding rates")
        api_status['exchange_status']['kucoin'] = {'status': 'success', 'count': len(results)}
        return results
        
    except Exception as e:
        logger.error(f"❌ KuCoin error: {e}")
        api_status['exchange_status']['kucoin'] = {'status': 'error', 'error': str(e)[:200]}
        return []

def fetch_bybit_funding_rates():
    """Récupère les funding rates de Bybit"""
    try:
        config = EXCHANGE_CONFIGS['bybit']
        url = f"{config['base_url']}{config['endpoints']['funding_rate']}"
        results = []
        
        # Bybit nécessite de spécifier chaque symbole
        for base_symbol in TARGET_SYMBOLS:
            try:
                symbol = f"{base_symbol}USDT"
                params = {
                    'category': 'linear',
                    'symbol': symbol,
                    'limit': 1
                }
                
                logger.info(f"📡 Fetching Bybit {symbol}...")
                
                response = requests.get(url, params=params, headers=config['headers'], timeout=20)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if 'result' in data and 'list' in data['result'] and data['result']['list']:
                        item = data['result']['list'][0]
                        funding_rate = item.get('fundingRate')
                        funding_time = item.get('fundingRateTimestamp')
                        
                        if funding_rate is not None:
                            clean_symbol = f"{base_symbol}/USDT:USDT"
                            
                            results.append({
                                'symbol': clean_symbol,
                                'base_symbol': base_symbol,
                                'exchange': 'bybit',
                                'fundingRate': float(funding_rate),
                                'fundingTime': int(funding_time) if funding_time else None,
                                'nextFundingTime': None,
                                'timestamp': datetime.utcnow().isoformat() + 'Z'
                            })
                
                time.sleep(0.2)  # Rate limiting
                
            except Exception as e:
                logger.warning(f"⚠️ Bybit {base_symbol} error: {e}")
                continue
        
        logger.info(f"✅ Bybit: {len(results)} funding rates")
        api_status['exchange_status']['bybit'] = {'status': 'success', 'count': len(results)}
        return results
        
    except Exception as e:
        logger.error(f"❌ Bybit error: {e}")
        api_status['exchange_status']['bybit'] = {'status': 'error', 'error': str(e)[:200]}
        return []

def fetch_okx_funding_rates():
    """Récupère les funding rates d'OKX"""
    try:
        config = EXCHANGE_CONFIGS['okx']
        url = f"{config['base_url']}{config['endpoints']['funding_rate']}"
        results = []
        
        # OKX nécessite de spécifier chaque instrument
        for base_symbol in TARGET_SYMBOLS:
            try:
                inst_id = f"{base_symbol}-USDT-SWAP"
                params = {'instId': inst_id}
                
                logger.info(f"📡 Fetching OKX {inst_id}...")
                
                response = requests.get(url, params=params, headers=config['headers'], timeout=20)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if 'data' in data and data['data']:
                        item = data['data'][0]
                        funding_rate = item.get('fundingRate')
                        funding_time = item.get('fundingTime')
                        next_funding_time = item.get('nextFundingTime')
                        
                        if funding_rate is not None:
                            clean_symbol = f"{base_symbol}/USDT:USDT"
                            
                            results.append({
                                'symbol': clean_symbol,
                                'base_symbol': base_symbol,
                                'exchange': 'okx',
                                'fundingRate': float(funding_rate),
                                'fundingTime': int(funding_time) if funding_time else None,
                                'nextFundingTime': int(next_funding_time) if next_funding_time else None,
                                'timestamp': datetime.utcnow().isoformat() + 'Z'
                            })
                
                time.sleep(0.2)  # Rate limiting
                
            except Exception as e:
                logger.warning(f"⚠️ OKX {base_symbol} error: {e}")
                continue
        
        logger.info(f"✅ OKX: {len(results)} funding rates")
        api_status['exchange_status']['okx'] = {'status': 'success', 'count': len(results)}
        return results
        
    except Exception as e:
        logger.error(f"❌ OKX error: {e}")
        api_status['exchange_status']['okx'] = {'status': 'error', 'error': str(e)[:200]}
        return []

def fetch_all_exchange_funding_rates():
    """Récupère les funding rates de tous les exchanges"""
    global funding_data_cache
    
    logger.info("📡 Fetching funding rates from all exchanges...")
    start_time = time.time()
    
    all_results = []
    
    # Fetch en parallèle (ou séquentiel pour éviter les rate limits)
    exchanges = [
        ('binance', fetch_binance_funding_rates),
        ('kucoin', fetch_kucoin_funding_rates),
        ('bybit', fetch_bybit_funding_rates),
        ('okx', fetch_okx_funding_rates)
    ]
    
    for exchange_name, fetch_func in exchanges:
        try:
            logger.info(f"📊 Fetching {exchange_name}...")
            results = fetch_func()
            all_results.extend(results)
            logger.info(f"✅ {exchange_name}: {len(results)} rates")
        except Exception as e:
            logger.error(f"❌ {exchange_name} failed: {e}")
            continue
    
    funding_data_cache = all_results
    
    duration = time.time() - start_time
    logger.info(f"🎉 All exchanges fetched in {duration:.1f}s - Total: {len(all_results)} rates")
    
    return all_results

def calculate_arbitrage_opportunities():
    """Calcule les opportunités d'arbitrage à partir des funding rates"""
    global arbitrage_opportunities
    
    logger.info("🔍 Calculating arbitrage opportunities...")
    
    # Grouper par symbole
    by_symbol = defaultdict(list)
    for rate in funding_data_cache:
        base_symbol = rate['base_symbol']
        by_symbol[base_symbol].append(rate)
    
    opportunities = []
    
    for base_symbol, rates in by_symbol.items():
        if len(rates) < 2:
            continue
        
        # Trouver min et max
        min_rate = min(rates, key=lambda x: x['fundingRate'])
        max_rate = max(rates, key=lambda x: x['fundingRate'])
        
        divergence = max_rate['fundingRate'] - min_rate['fundingRate']
        
        # Seuil minimal pour arbitrage (0.01%)
        if abs(divergence) > 0.0001:
            
            commission = 0.0008  # 0.08% total (0.04% par side)
            revenue_8h = abs(divergence) - commission
            revenue_annual = revenue_8h * 3 * 365 * 100  # 3 fois par jour, 365 jours
            
            # Filtrer seulement les arbitrages rentables (>5% annuel)
            if revenue_annual > 5:
                
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
                
                # Signal de timing basé sur le prochain funding
                funding_info = time_until_funding()
                
                if funding_info['total_minutes'] > 60:
                    signal = "🟢 ENTRER MAINTENANT"
                    signal_detail = f"Position optimale - {funding_info['hours_remaining']}h{funding_info['minutes_remaining']}m avant funding"
                elif funding_info['total_minutes'] > 30:
                    signal = "🟡 ENTRER BIENTÔT"
                    signal_detail = f"Préparer l'entrée - {funding_info['hours_remaining']}h{funding_info['minutes_remaining']}m avant funding"
                elif funding_info['total_minutes'] > 5:
                    signal = "🟠 ATTENTION"
                    signal_detail = f"Funding dans {funding_info['minutes_remaining']}m - Surveiller"
                else:
                    signal = "🔴 SORTIR"
                    signal_detail = "Fermer avant funding dans <5min"
                
                opportunities.append({
                    'symbol': base_symbol,
                    'strategy': strategy,
                    'longExchange': long_exchange,
                    'shortExchange': short_exchange,
                    'longRate': round(long_rate, 6),
                    'shortRate': round(short_rate, 6),
                    'divergence': round(abs(divergence), 6),
                    'divergence_pct': round(abs(divergence) * 100, 4),
                    'commission': round(commission, 6),
                    'commission_pct': round(commission * 100, 4),
                    'revenue_8h': round(revenue_8h, 6),
                    'revenue_8h_pct': round(revenue_8h * 100, 4),
                    'revenue_annual_pct': round(revenue_annual, 2),
                    'signal': signal,
                    'signal_detail': signal_detail,
                    'risk_level': 'Low' if revenue_annual > 20 else 'Medium',
                    'all_rates': rates,  # Toutes les données pour référence
                    'timestamp': datetime.utcnow().isoformat() + 'Z'
                })
    
    # Trier par revenue décroissant
    opportunities.sort(key=lambda x: x['revenue_annual_pct'], reverse=True)
    arbitrage_opportunities = opportunities[:20]  # Top 20
    
    logger.info(f"💰 Calculated {len(arbitrage_opportunities)} profitable arbitrage opportunities")

def fetch_all_data():
    """Récupère toutes les données des exchanges"""
    global last_update, api_status
    
    logger.info("📡 Starting full data fetch cycle...")
    start_time = time.time()
    
    try:
        # 1. Récupérer les funding rates
        fetch_all_exchange_funding_rates()
        
        # 2. Calculer les arbitrages
        calculate_arbitrage_opportunities()
        
        last_update = datetime.utcnow()
        
        # Compter les exchanges qui fonctionnent
        working_exchanges = sum(1 for ex_status in api_status['exchange_status'].values() 
                              if ex_status.get('status') == 'success')
        
        api_status.update({
            'status': 'success',
            'errors': 0,
            'last_update': last_update.isoformat() + 'Z',
            'working_exchanges': working_exchanges,
            'total_exchanges': len(EXCHANGE_CONFIGS)
        })
        
        duration = time.time() - start_time
        logger.info(f"🎉 Full data cycle completed in {duration:.1f}s")
        logger.info(f"📊 Summary: {len(funding_data_cache)} rates, {len(arbitrage_opportunities)} arbitrages")
        
    except Exception as e:
        logger.error(f"❌ Data fetch cycle failed: {e}")
        api_status.update({
            'status': 'error',
            'errors': api_status.get('errors', 0) + 1,
            'last_error': str(e)[:200]
        })

def background_updater():
    """Met à jour les données toutes les 2 minutes"""
    logger.info("🔄 Background updater started (2-minute intervals)")
    
    while True:
        try:
            logger.info("📊 Background update cycle...")
            fetch_all_data()
            logger.info("✅ Background update completed")
            
            # Attendre 2 minutes
            time.sleep(120)
            
        except Exception as e:
            logger.error(f"❌ Background update failed: {e}")
            time.sleep(60)  # Retry dans 1 minute

# Variables pour les signaux de trading
trading_signals = []
webhook_auth_key = "YOUR_SECRET_KEY_2025_DIRECT_EXCHANGES"  # Changez ceci !

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
        'service': 'Direct Exchange APIs - Funding Rates & Arbitrage',
        'version': '9.0-direct-exchanges',
        'description': 'Données funding rates directement depuis les APIs des exchanges',
        'data_sources': list(EXCHANGE_CONFIGS.keys()),
        'features': [
            'APIs directes Binance, KuCoin, Bybit, OKX',
            'Calculs d\'arbitrage en temps réel',
            'Signaux de timing optimisés',
            'Données fiables sans intermédiaire',
            'Support webhooks TradingView'
        ],
        'funding_schedule': '00:00, 08:00, 16:00 UTC',
        'next_funding': time_until_funding(),
        'api_status': api_status,
        'current_data': {
            'funding_rates': len(funding_data_cache),
            'arbitrage_opportunities': len(arbitrage_opportunities),
            'last_update': last_update.isoformat() + 'Z' if last_update else None
        },
        'exchanges': {name: config['base_url'] for name, config in EXCHANGE_CONFIGS.items()},
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    })

@app.route('/api/status', methods=['GET', 'OPTIONS'])
def get_status():
    return jsonify({
        'status': 'online',
        'service': 'Direct Exchange APIs Backend',
        'version': '9.0-direct-exchanges',
        'last_update': last_update.isoformat() + 'Z' if last_update else None,
        'cached_rates_count': len(funding_data_cache),
        'arbitrage_opportunities_count': len(arbitrage_opportunities),
        'api_status': api_status,
        'exchange_status': api_status.get('exchange_status', {}),
        'next_funding': time_until_funding(),
        'data_sources': 'Direct Exchange APIs',
        'target_symbols': TARGET_SYMBOLS,
        'update_interval': '2 minutes',
        'exchanges': list(EXCHANGE_CONFIGS.keys()),
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    })

@app.route('/api/funding-rates', methods=['GET', 'OPTIONS'])
def get_funding_rates():
    logger.info("📍 FUNDING RATES endpoint called")
    
    # Filtrer par exchange si spécifié
    exchange = request.args.get('exchange')
    data = funding_data_cache
    
    if exchange:
        data = [rate for rate in funding_data_cache if rate['exchange'].lower() == exchange.lower()]
    
    return jsonify({
        'status': 'success',
        'data': data,
        'count': len(data),
        'total_available': len(funding_data_cache),
        'last_update': last_update.isoformat() + 'Z' if last_update else None,
        'next_funding': time_until_funding(),
        'api_status': api_status,
        'exchange_status': api_status.get('exchange_status', {}),
        'data_sources': 'Direct Exchange APIs',
        'exchanges_available': list(EXCHANGE_CONFIGS.keys()),
        'filter_applied': f"exchange={exchange}" if exchange else None,
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    })

@app.route('/api/arbitrage', methods=['GET', 'OPTIONS'])
def get_arbitrage():
    logger.info("📍 ARBITRAGE endpoint called")
    
    # Filtrer par seuil minimum si spécifié
    min_return = request.args.get('min_return', type=float)
    data = arbitrage_opportunities
    
    if min_return:
        data = [opp for opp in arbitrage_opportunities if opp['revenue_annual_pct'] >= min_return]
    
    return jsonify({
        'status': 'success',
        'data': data,
        'count': len(data),
        'total_available': len(arbitrage_opportunities),
        'last_update': last_update.isoformat() + 'Z' if last_update else None,
        'next_funding': time_until_funding(),
        'funding_schedule': '00:00, 08:00, 16:00 UTC',
        'api_status': api_status,
        'data_sources': 'Calculated from Direct Exchange APIs',
        'min_annual_return_default': '5%',
        'filter_applied': f"min_return={min_return}%" if min_return else None,
        'calculation_details': {
            'commission_per_side': '0.04%',
            'total_commission': '0.08%',
            'funding_frequency': '3 times per day',
            'annual_calculation': 'revenue_8h * 3 * 365'
        },
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    })

@app.route('/api/funding-rate/<symbol>/current', methods=['GET', 'OPTIONS'])
def get_current_funding_rate(symbol):
    """Récupère le funding rate actuel pour un symbole spécifique depuis tous les exchanges"""
    logger.info(f"📍 CURRENT FUNDING RATE endpoint called for {symbol}")
    
    # Nettoyer le symbole
    clean_symbol = symbol.upper().replace('/USDT:USDT', '').replace('USDT', '')
    
    # Trouver les données pour ce symbole
    symbol_data = [rate for rate in funding_data_cache 
                   if rate['base_symbol'].upper() == clean_symbol]
    
    if not symbol_data:
        return jsonify({
            'status': 'not_found',
            'message': f'No funding rate data found for {symbol}',
            'available_symbols': list(set(rate['base_symbol'] for rate in funding_data_cache)),
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }), 404
    
    # Organiser par exchange
    by_exchange = {rate['exchange']: rate for rate in symbol_data}
    
    # Calculer arbitrage si possible
    arbitrage_opportunity = None
    if len(symbol_data) >= 2:
        rates = [(rate['exchange'], rate['fundingRate']) for rate in symbol_data]
        rates.sort(key=lambda x: x[1])  # Trier par taux
        
        min_ex, min_rate = rates[0]
        max_ex, max_rate = rates[-1]
        
        divergence = max_rate - min_rate
        
        if abs(divergence) > 0.0001:  # 0.01%
            commission = 0.0008
            revenue_8h = abs(divergence) - commission
            revenue_annual = revenue_8h * 3 * 365 * 100
            
            if revenue_annual > 5:
                arbitrage_opportunity = {
                    'symbol': clean_symbol,
                    'long_exchange': min_ex,
                    'short_exchange': max_ex,
                    'long_rate': min_rate,
                    'short_rate': max_rate,
                    'divergence': abs(divergence),
                    'divergence_pct': abs(divergence) * 100,
                    'revenue_annual_pct': revenue_annual,
                    'profitable': True,
                    'strategy': 'Long/Short' if divergence > 0 else 'Short/Long'
                }
    
    return jsonify({
        'status': 'success',
        'symbol_requested': symbol,
        'symbol_processed': clean_symbol,
        'exchanges': by_exchange,
        'rates_count': len(symbol_data),
        'arbitrage_opportunity': arbitrage_opportunity,
        'next_funding': time_until_funding(),
        'last_update': last_update.isoformat() + 'Z' if last_update else None,
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    })

@app.route('/api/exchanges/<exchange>/funding-rates', methods=['GET', 'OPTIONS'])
def get_exchange_funding_rates(exchange):
    """Récupère les funding rates d'un exchange spécifique"""
    logger.info(f"📍 EXCHANGE FUNDING RATES endpoint called for {exchange}")
    
    if exchange.lower() not in EXCHANGE_CONFIGS:
        return jsonify({
            'status': 'error',
            'message': f'Exchange {exchange} not supported',
            'supported_exchanges': list(EXCHANGE_CONFIGS.keys()),
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }), 400
    
    # Filtrer les données pour cet exchange
    exchange_data = [rate for rate in funding_data_cache 
                     if rate['exchange'].lower() == exchange.lower()]
    
    exchange_status = api_status.get('exchange_status', {}).get(exchange.lower(), {})
    
    return jsonify({
        'status': 'success',
        'exchange': exchange.lower(),
        'exchange_config': EXCHANGE_CONFIGS.get(exchange.lower(), {}),
        'data': exchange_data,
        'count': len(exchange_data),
        'exchange_status': exchange_status,
        'last_update': last_update.isoformat() + 'Z' if last_update else None,
        'next_funding': time_until_funding(),
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    })

@app.route('/api/test-exchanges', methods=['GET', 'OPTIONS'])
def test_exchanges():
    """Test la connectivité avec tous les exchanges"""
    logger.info("📍 TEST EXCHANGES endpoint called")
    
    test_results = {
        'test_timestamp': datetime.utcnow().isoformat() + 'Z',
        'exchanges': {}
    }
    
    # Tester chaque exchange
    for exchange_name, config in EXCHANGE_CONFIGS.items():
        logger.info(f"🧪 Testing {exchange_name}...")
        
        try:
            if exchange_name == 'binance':
                url = f"{config['base_url']}{config['endpoints']['funding_rate']}"
                params = {'limit': 1}
                
            elif exchange_name == 'kucoin':
                # Test avec BTC
                url = f"{config['base_url']}{config['endpoints']['funding_rate']}/BTCUSDTM"
                params = {}
                
            elif exchange_name == 'bybit':
                url = f"{config['base_url']}{config['endpoints']['funding_rate']}"
                params = {'category': 'linear', 'symbol': 'BTCUSDT', 'limit': 1}
                
            elif exchange_name == 'okx':
                url = f"{config['base_url']}{config['endpoints']['funding_rate']}"
                params = {'instId': 'BTC-USDT-SWAP'}
            
            response = requests.get(url, params=params, headers=config['headers'], timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                test_results['exchanges'][exchange_name] = {
                    'status': 'success',
                    'response_code': response.status_code,
                    'data_available': bool(data),
                    'response_size': len(str(data)),
                    'url_tested': url
                }
            else:
                test_results['exchanges'][exchange_name] = {
                    'status': 'error',
                    'response_code': response.status_code,
                    'error': response.text[:200],
                    'url_tested': url
                }
                
        except Exception as e:
            test_results['exchanges'][exchange_name] = {
                'status': 'exception',
                'error': str(e)[:200],
                'url_tested': url if 'url' in locals() else 'N/A'
            }
    
    # Résumé
    total_exchanges = len(EXCHANGE_CONFIGS)
    working_exchanges = sum(1 for result in test_results['exchanges'].values() 
                           if result['status'] == 'success')
    
    test_results['summary'] = {
        'total_exchanges': total_exchanges,
        'working_exchanges': working_exchanges,
        'success_rate': f"{(working_exchanges/total_exchanges)*100:.1f}%",
        'all_working': working_exchanges == total_exchanges
    }
    
    return jsonify({
        'status': 'test_completed',
        'message': 'Exchange connectivity test results',
        'results': test_results,
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    })

@app.route('/webhook/tradingview', methods=['POST'])
def tradingview_webhook():
    """Reçoit les signaux de TradingView via webhook"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No JSON data received'}), 400
        
        # Vérifier la clé d'authentification
        auth_key = data.get('auth_key', '')
        if auth_key != webhook_auth_key:
            logger.warning(f"❌ Webhook auth failed: {auth_key}")
            return jsonify({'error': 'Invalid auth key'}), 401
        
        # Extraire les données du signal
        signal_data = {
            'symbol': data.get('symbol', ''),
            'action': data.get('action', ''),  # ENTER/EXIT/BUY/SELL/CLOSE
            'exchange_long': data.get('exchange_long', ''),
            'exchange_short': data.get('exchange_short', ''),
            'quantity': data.get('quantity', 0),
            'strategy': data.get('strategy', 'arbitrage'),
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'tradingview_data': data
        }
        
        # Valider le signal
        if not signal_data['symbol'] or not signal_data['action']:
            return jsonify({'error': 'Missing required fields: symbol, action'}), 400
        
        # Stocker le signal
        trading_signals.append(signal_data)
        
        # Garder seulement les 100 derniers signaux
        if len(trading_signals) > 100:
            trading_signals.pop(0)
        
        logger.info(f"📥 TradingView signal received: {signal_data['action']} {signal_data['symbol']}")
        
        # Traiter le signal d'arbitrage
        if signal_data['strategy'] == 'arbitrage':
            result = process_arbitrage_signal(signal_data)
            return jsonify({
                'status': 'success',
                'message': 'Signal received and processed',
                'signal_id': len(trading_signals),
                'processing_result': result
            })
        
        return jsonify({
            'status': 'success',
            'message': 'Signal received',
            'signal_id': len(trading_signals)
        })
        
    except Exception as e:
        logger.error(f"❌ Webhook error: {e}")
        return jsonify({'error': str(e)}), 500

def process_arbitrage_signal(signal_data):
    """Traite un signal d'arbitrage"""
    try:
        symbol = signal_data['symbol']
        action = signal_data['action']
        
        logger.info(f"🎯 Processing arbitrage signal: {action} {symbol}")
        
        # Nettoyer le symbole
        clean_symbol = symbol.replace('/USDT:USDT', '').replace('USDT', '').upper()
        
        # Vérifier les opportunités d'arbitrage actuelles
        current_opportunity = None
        for opp in arbitrage_opportunities:
            if opp['symbol'].upper() == clean_symbol:
                current_opportunity = opp
                break
        
        if not current_opportunity:
            return {
                'status': 'warning',
                'message': f'No current arbitrage opportunity for {symbol}',
                'available_opportunities': [opp['symbol'] for opp in arbitrage_opportunities[:5]]
            }
        
        # Traiter selon l'action
        if action.upper() in ['ENTER', 'BUY']:
            result = {
                'status': 'success',
                'action': 'ENTER_ARBITRAGE',
                'symbol': symbol,
                'long_exchange': current_opportunity['longExchange'],
                'short_exchange': current_opportunity['shortExchange'],
                'expected_revenue_annual': current_opportunity['revenue_annual_pct'],
                'signal': current_opportunity['signal'],
                'message': f"Arbitrage entry signal: Long {current_opportunity['longExchange']}, Short {current_opportunity['shortExchange']}"
            }
            
        elif action.upper() in ['EXIT', 'SELL', 'CLOSE']:
            result = {
                'status': 'success',
                'action': 'EXIT_ARBITRAGE',
                'symbol': symbol,
                'message': f"Arbitrage exit signal for {symbol}"
            }
            
        else:
            result = {
                'status': 'warning',
                'message': f'Unknown action: {action}',
                'supported_actions': ['ENTER', 'EXIT', 'BUY', 'SELL', 'CLOSE']
            }
        
        logger.info(f"✅ Signal processed: {result}")
        return result
        
    except Exception as e:
        logger.error(f"❌ Signal processing error: {e}")
        return {
            'status': 'error',
            'message': str(e)
        }

@app.route('/api/webhook-info', methods=['GET', 'OPTIONS'])
def get_webhook_info():
    """Informations pour configurer TradingView"""
    return jsonify({
        'webhook_url': f'{request.url_root}webhook/tradingview',
        'method': 'POST',
        'content_type': 'application/json',
        'authentication': {
            'required': True,
            'field': 'auth_key',
            'current_key': webhook_auth_key,
            'note': 'Include auth_key in JSON payload'
        },
        'required_fields': ['symbol', 'action', 'auth_key'],
        'optional_fields': ['exchange_long', 'exchange_short', 'quantity', 'strategy'],
        'example_payload': {
            'auth_key': webhook_auth_key,
            'symbol': 'BTC/USDT:USDT',
            'action': 'ENTER',
            'exchange_long': 'binance',
            'exchange_short': 'bybit',
            'quantity': 0.1,
            'strategy': 'arbitrage'
        },
        'supported_actions': ['ENTER', 'EXIT', 'BUY', 'SELL', 'CLOSE'],
        'supported_exchanges': list(EXCHANGE_CONFIGS.keys()),
        'webhook_security': 'Use HTTPS and keep auth_key secret',
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    })

@app.route('/api/signals', methods=['GET', 'OPTIONS'])
def get_signals():
    """Récupère l'historique des signaux reçus"""
    limit = request.args.get('limit', 50, type=int)
    
    recent_signals = trading_signals[-limit:] if trading_signals else []
    
    return jsonify({
        'status': 'success',
        'signals': recent_signals,
        'count': len(recent_signals),
        'total_signals_received': len(trading_signals),
        'limit_applied': limit,
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    })

@app.route('/api/refresh', methods=['POST', 'OPTIONS'])
def force_refresh():
    """Force la mise à jour des données"""
    logger.info("📍 FORCE REFRESH endpoint called")
    
    try:
        logger.info("🔄 Force refreshing all data...")
        fetch_all_data()
        
        return jsonify({
            'status': 'success',
            'message': 'Data refreshed successfully',
            'data_summary': {
                'funding_rates': len(funding_data_cache),
                'arbitrage_opportunities': len(arbitrage_opportunities),
                'working_exchanges': api_status.get('working_exchanges', 0),
                'last_update': last_update.isoformat() + 'Z' if last_update else None
            },
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        })
        
    except Exception as e:
        logger.error(f"❌ Force refresh failed: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Refresh failed: {str(e)}',
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'healthy',
        'service': 'Direct Exchange APIs Backend',
        'data_sources': list(EXCHANGE_CONFIGS.keys()),
        'api_status': api_status,
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    }), 200

if __name__ == '__main__':
    logger.info("🌐 Starting Direct Exchange APIs Flask server...")
    
    # Test initial des APIs
    logger.info("🧪 Testing exchange APIs connectivity...")
    test_binance = fetch_binance_funding_rates()
    test_bybit = fetch_bybit_funding_rates()
    
    working_count = sum([bool(test_binance), bool(test_bybit)])
    logger.info(f"✅ Initial test: {working_count}/2 exchanges accessible")
    
    # Démarrer le background updater
    update_thread = threading.Thread(target=background_updater, daemon=True)
    update_thread.start()
    
    # Premier fetch de données
    logger.info("📊 Performing initial data fetch...")
    try:
        fetch_all_data()
        logger.info(f"✅ Initial data loaded - {len(funding_data_cache)} rates, {len(arbitrage_opportunities)} arbitrages")
    except Exception as e:
        logger.error(f"❌ Initial data fetch failed: {e}")
    
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"🌐 Direct Exchange APIs server starting on port {port}")
    logger.info("📋 Available endpoints:")
    logger.info("   GET  /                              - Service info")
    logger.info("   GET  /api/status                    - System status")
    logger.info("   GET  /api/funding-rates             - All funding rates")
    logger.info("   GET  /api/arbitrage                 - Arbitrage opportunities")
    logger.info("   GET  /api/funding-rate/<symbol>/current - Current rate for symbol")
    logger.info("   GET  /api/exchanges/<exchange>/funding-rates - Exchange specific rates")
    logger.info("   GET  /api/test-exchanges            - Test all exchanges")
    logger.info("   POST /api/refresh                   - Force data refresh")
    logger.info("   POST /webhook/tradingview           - TradingView webhook")
    logger.info("   GET  /api/webhook-info              - Webhook configuration")
    logger.info("   GET  /api/signals                   - Signal history")
    logger.info("   GET  /health                        - Health check")
    
    app.run(
        host='0.0.0.0',
        port=port,
        debug=False,
        threaded=True
    )
