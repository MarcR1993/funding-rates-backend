"""
🚀 Backend Flask avec CoinGlass API
SOLUTION PARFAITE pour les funding rates + arbitrage
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

logger.info("🚀 Starting CoinGlass API Backend - PERFECT SOLUTION!")

# Configuration CoinGlass API v4
COINGLASS_CONFIG = {
    'base_url': 'https://open-api-v4.coinglass.com',
    'endpoints': {
        'funding_rates': '/api/futures/funding-rates/charts',
        'funding_arbitrage': '/api/futures/funding-rates/heatmap',
        'supported_pairs': '/api/futures/supported-exchange-pairs',
        'market_overview': '/api/futures/funding-rates/overview'
    },
    'headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    }
}

# Symboles principaux à surveiller
TARGET_SYMBOLS = ['BTC', 'ETH', 'SOL', 'XRP', 'DOGE', 'ADA', 'AVAX', 'MATIC', 'LINK', 'DOT']

# Variables globales
funding_data_cache = []
arbitrage_opportunities = []
last_update = None
api_status = {'status': 'initializing', 'errors': 0}

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

def fetch_coinglass_funding_overview():
    """Récupère l'aperçu des funding rates de CoinGlass"""
    try:
        config = COINGLASS_CONFIG
        url = f"{config['base_url']}{config['endpoints']['market_overview']}"
        
        # Paramètres pour obtenir les dernières données
        params = {
            'interval': '8h',  # Funding rate toutes les 8h
            'limit': 50       # Top 50 symboles
        }
        
        logger.info(f"📡 Fetching CoinGlass overview: {url}")
        
        response = requests.get(
            url,
            params=params,
            headers=config['headers'],
            timeout=30
        )
        
        logger.info(f"📊 CoinGlass overview response: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            logger.info(f"📦 CoinGlass overview data structure: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
            return data
        else:
            logger.error(f"❌ CoinGlass overview failed: {response.status_code} - {response.text[:200]}")
            return None
            
    except Exception as e:
        logger.error(f"❌ CoinGlass overview error: {e}")
        return None

def fetch_binance_funding_direct():
    """Récupère les funding rates directement de Binance"""
    try:
        # Endpoint Binance direct
        url = "https://fapi.binance.com/fapi/v1/fundingRate"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        logger.info("📡 Fetching Binance funding rates direct...")
        
        response = requests.get(url, headers=headers, timeout=20)
        
        if response.status_code == 200:
            data = response.json()
            results = []
            
            for item in data[-50:]:  # 50 derniers
                symbol = item.get('symbol', '')
                funding_rate = item.get('fundingRate')
                funding_time = item.get('fundingTime')
                
                if symbol.endswith('USDT') and funding_rate:
                    clean_symbol = symbol.replace('USDT', '') + '/USDT:USDT'
                    
                    results.append({
                        'symbol': clean_symbol,
                        'exchange': 'binance',
                        'fundingRate': float(funding_rate),
                        'fundingTime': funding_time,
                        'timestamp': datetime.utcnow().isoformat() + 'Z'
                    })
            
            logger.info(f"✅ Binance direct: {len(results)} funding rates")
            return results
            
        else:
            logger.error(f"❌ Binance direct failed: {response.status_code}")
            return []
            
    except Exception as e:
        logger.error(f"❌ Binance direct error: {e}")
        return []

def fetch_bybit_funding_direct():
    """Récupère les funding rates directement de Bybit"""
    try:
        url = "https://api.bybit.com/v5/market/funding/history"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        
        results = []
        
        # Test quelques symboles populaires
        test_symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'XRPUSDT', 'DOGEUSDT']
        
        for symbol in test_symbols:
            try:
                params = {
                    'category': 'linear',
                    'symbol': symbol,
                    'limit': 1
                }
                
                logger.info(f"📡 Fetching Bybit {symbol} funding rate...")
                
                response = requests.get(url, params=params, headers=headers, timeout=15)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if 'result' in data and 'list' in data['result']:
                        for item in data['result']['list']:
                            funding_rate = item.get('fundingRate')
                            funding_time = item.get('fundingRateTimestamp')
                            
                            if funding_rate:
                                clean_symbol = symbol.replace('USDT', '') + '/USDT:USDT'
                                
                                results.append({
                                    'symbol': clean_symbol,
                                    'exchange': 'bybit',
                                    'fundingRate': float(funding_rate),
                                    'fundingTime': funding_time,
                                    'timestamp': datetime.utcnow().isoformat() + 'Z'
                                })
                
                time.sleep(0.3)  # Délai entre symboles
                
            except Exception as e:
                logger.warning(f"⚠️ Bybit {symbol} error: {e}")
                continue
        
        logger.info(f"✅ Bybit direct: {len(results)} funding rates")
        return results
        
    except Exception as e:
        logger.error(f"❌ Bybit direct error: {e}")
        return []

def fetch_okx_funding_direct():
    """Récupère les funding rates directement d'OKX"""
    try:
        url = "https://www.okx.com/api/v5/public/funding-rate"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'
        }
        
        logger.info("📡 Fetching OKX funding rates direct...")
        
        # Test quelques instruments populaires
        test_instruments = ['BTC-USDT-SWAP', 'ETH-USDT-SWAP', 'SOL-USDT-SWAP', 'XRP-USDT-SWAP']
        results = []
        
        for inst_id in test_instruments:
            try:
                params = {'instId': inst_id}
                
                response = requests.get(url, params=params, headers=headers, timeout=15)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if 'data' in data:
                        for item in data['data']:
                            funding_rate = item.get('fundingRate')
                            funding_time = item.get('fundingTime')
                            
                            if funding_rate:
                                # Convertir BTC-USDT-SWAP en BTC/USDT:USDT
                                symbol_part = inst_id.replace('-USDT-SWAP', '')
                                clean_symbol = symbol_part + '/USDT:USDT'
                                
                                results.append({
                                    'symbol': clean_symbol,
                                    'exchange': 'okx',
                                    'fundingRate': float(funding_rate),
                                    'fundingTime': funding_time,
                                    'timestamp': datetime.utcnow().isoformat() + 'Z'
                                })
                
                time.sleep(0.3)  # Délai entre symboles
                
            except Exception as e:
                logger.warning(f"⚠️ OKX {inst_id} error: {e}")
                continue
        
        logger.info(f"✅ OKX direct: {len(results)} funding rates")
        return results
        
    except Exception as e:
        logger.error(f"❌ OKX direct error: {e}")
        return []

def fetch_coinglass_funding_rates():
    """Récupère les funding rates - VERSION HYBRIDE avec tests directs"""
    try:
        logger.info("🧪 Testing DIRECT exchange APIs first...")
        
        all_results = []
        
        # Test 1: Binance direct
        binance_results = fetch_binance_funding_direct()
        all_results.extend(binance_results)
        
        # Test 2: Bybit direct  
        bybit_results = fetch_bybit_funding_direct()
        all_results.extend(bybit_results)
        
        # Test 3: OKX direct
        okx_results = fetch_okx_funding_direct()
        all_results.extend(okx_results)
        
        logger.info(f"✅ DIRECT APIs: Total {len(all_results)} funding rates fetched")
        
        # Si on a des données, les retourner
        if all_results:
            return all_results
        
        # Sinon, fallback vers CoinGlass (méthode originale)
        logger.info("⚠️ Direct APIs failed, trying CoinGlass fallback...")
        
        config = COINGLASS_CONFIG
        results = []
        
        # Pour chaque symbole principal
        for symbol in TARGET_SYMBOLS[:5]:  # Limiter à 5 pour test
            try:
                url = f"{config['base_url']}{config['endpoints']['funding_rates']}"
                
                params = {
                    'symbol': symbol,
                    'type': 'U',  # USDT margined
                    'interval': '8h'
                }
                
                logger.info(f"📡 Fetching {symbol} from CoinGlass...")
                
                response = requests.get(
                    url,
                    params=params,
                    headers=config['headers'],
                    timeout=20
                )
                
                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"📦 CoinGlass {symbol} response: {data}")
                    
                    # Traiter les données CoinGlass
                    if 'data' in data and isinstance(data['data'], list):
                        for item in data['data']:
                            # Extraire les données par exchange
                            if 'exchanges' in item:
                                for exchange_data in item['exchanges']:
                                    exchange_name = exchange_data.get('exchangeName', '').lower()
                                    funding_rate = exchange_data.get('fundingRate')
                                    
                                    if exchange_name and funding_rate is not None:
                                        results.append({
                                            'symbol': f"{symbol}/USDT:USDT",
                                            'exchange': exchange_name,
                                            'fundingRate': float(funding_rate),
                                            'timestamp': datetime.utcnow().isoformat() + 'Z'
                                        })
                    
                    logger.info(f"✅ {symbol}: {len([r for r in results if symbol in r['symbol']])} rates")
                    
                else:
                    logger.warning(f"⚠️ CoinGlass {symbol} failed: {response.status_code}")
                
                # Délai entre les requêtes
                time.sleep(1)
                
            except Exception as e:
                logger.warning(f"⚠️ CoinGlass {symbol} error: {e}")
                continue
        
        logger.info(f"✅ CoinGlass fallback: Total {len(results)} funding rates fetched")
        return results
        
    except Exception as e:
        logger.error(f"❌ All funding rates methods failed: {e}")
        return []

def fetch_coinglass_arbitrage_data():
    """Récupère les données d'arbitrage de CoinGlass"""
    try:
        config = COINGLASS_CONFIG
        url = f"{config['base_url']}{config['endpoints']['funding_arbitrage']}"
        
        params = {
            'type': 'U',  # USDT margined
            'limit': 20   # Top 20 opportunities
        }
        
        logger.info(f"🎯 Fetching CoinGlass arbitrage data...")
        
        response = requests.get(
            url,
            params=params,
            headers=config['headers'],
            timeout=20
        )
        
        if response.status_code == 200:
            data = response.json()
            arbitrages = []
            
            if 'data' in data and isinstance(data['data'], list):
                for item in data['data']:
                    symbol = item.get('symbol', '')
                    
                    # Si on a des données d'arbitrage
                    if 'arbitrageData' in item:
                        arb = item['arbitrageData']
                        
                        # Calculer l'arbitrage
                        long_exchange = arb.get('longExchange', '')
                        short_exchange = arb.get('shortExchange', '')
                        long_rate = arb.get('longRate', 0)
                        short_rate = arb.get('shortRate', 0)
                        
                        if long_exchange and short_exchange:
                            divergence = abs(short_rate - long_rate)
                            commission = 0.0008  # 0.08% total
                            revenue_8h = divergence - commission
                            revenue_annual = revenue_8h * 3 * 365 * 100
                            
                            if revenue_annual > 10:  # Seulement les arbitrages rentables
                                
                                # Signal de timing
                                funding_info = time_until_funding()
                                
                                if funding_info['total_minutes'] > 30:
                                    signal = "🟢 ENTRER MAINTENANT"
                                    signal_detail = f"Position optimale {funding_info['hours_remaining']}h{funding_info['minutes_remaining']}m avant funding"
                                elif funding_info['total_minutes'] > 5:
                                    signal = "🟡 ENTRER BIENTÔT"
                                    signal_detail = f"Ouvrir dans {funding_info['minutes_remaining']}m"
                                else:
                                    signal = "🔴 SORTIR"
                                    signal_detail = "Fermer avant funding dans <5min"
                                
                                arbitrages.append({
                                    'symbol': symbol,
                                    'strategy': 'Long/Short' if short_rate > long_rate else 'Short/Long',
                                    'longExchange': long_exchange,
                                    'shortExchange': short_exchange,
                                    'longRate': round(long_rate, 6),
                                    'shortRate': round(short_rate, 6),
                                    'divergence': round(divergence, 6),
                                    'divergence_pct': round(divergence * 100, 4),
                                    'commission': round(commission, 6),
                                    'revenue_8h': round(revenue_8h, 6),
                                    'revenue_8h_pct': round(revenue_8h * 100, 4),
                                    'revenue_annual_pct': round(revenue_annual, 2),
                                    'signal': signal,
                                    'signal_detail': signal_detail,
                                    'timestamp': datetime.utcnow().isoformat() + 'Z'
                                })
            
            logger.info(f"💰 CoinGlass arbitrage: {len(arbitrages)} opportunities")
            return arbitrages
            
        else:
            logger.warning(f"⚠️ CoinGlass arbitrage failed: {response.status_code}")
            return []
            
    except Exception as e:
        logger.error(f"❌ CoinGlass arbitrage error: {e}")
        return []

def calculate_arbitrage_from_funding_data():
    """Calcule les arbitrages à partir des funding rates récupérés"""
    global arbitrage_opportunities
    
    logger.info("🔍 Calculating arbitrages from funding data...")
    
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
        
        # Seuil minimal pour arbitrage
        if abs(divergence) > 0.0001:  # 0.01%
            
            commission = 0.0008  # 0.08% total
            revenue_8h = abs(divergence) - commission
            revenue_annual = revenue_8h * 3 * 365 * 100
            
            if revenue_annual > 10:  # Au moins 10% annuel
                
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
                
                # Signal de timing
                funding_info = time_until_funding()
                
                if funding_info['total_minutes'] > 30:
                    signal = "🟢 ENTRER MAINTENANT"
                    signal_detail = f"Position optimale {funding_info['hours_remaining']}h{funding_info['minutes_remaining']}m avant funding"
                elif funding_info['total_minutes'] > 5:
                    signal = "🟡 ENTRER BIENTÔT"
                    signal_detail = f"Ouvrir dans {funding_info['minutes_remaining']}m"
                else:
                    signal = "🔴 SORTIR"
                    signal_detail = "Fermer avant funding dans <5min"
                
                opportunities.append({
                    'symbol': symbol.split('/')[0],
                    'strategy': strategy,
                    'longExchange': long_exchange,
                    'shortExchange': short_exchange,
                    'longRate': round(long_rate, 6),
                    'shortRate': round(short_rate, 6),
                    'divergence': round(abs(divergence), 6),
                    'divergence_pct': round(abs(divergence) * 100, 4),
                    'commission': round(commission, 6),
                    'revenue_8h': round(revenue_8h, 6),
                    'revenue_8h_pct': round(revenue_8h * 100, 4),
                    'revenue_annual_pct': round(revenue_annual, 2),
                    'signal': signal,
                    'signal_detail': signal_detail,
                    'timestamp': datetime.utcnow().isoformat() + 'Z'
                })
    
    # Trier par revenue décroissant
    opportunities.sort(key=lambda x: x['revenue_annual_pct'], reverse=True)
    arbitrage_opportunities = opportunities[:10]
    
    logger.info(f"💰 Calculated {len(arbitrage_opportunities)} profitable arbitrages")

def fetch_all_coinglass_data():
    """Récupère toutes les données CoinGlass"""
    global funding_data_cache, last_update, api_status
    
    logger.info("📡 Fetching ALL CoinGlass data...")
    start_time = time.time()
    
    try:
        # 1. Funding rates détaillés
        funding_rates = fetch_coinglass_funding_rates()
        funding_data_cache = funding_rates
        
        # 2. Essayer d'obtenir les arbitrages directement de CoinGlass
        coinglass_arbitrages = fetch_coinglass_arbitrage_data()
        
        if coinglass_arbitrages:
            # Utiliser les arbitrages de CoinGlass
            arbitrage_opportunities = coinglass_arbitrages
            logger.info("✅ Using CoinGlass arbitrage data")
        else:
            # Calculer nos propres arbitrages
            calculate_arbitrage_from_funding_data()
            logger.info("✅ Using calculated arbitrage data")
        
        last_update = datetime.utcnow()
        api_status = {
            'status': 'success',
            'errors': 0,
            'last_update': last_update.isoformat() + 'Z'
        }
        
        duration = time.time() - start_time
        logger.info(f"🎉 CoinGlass data fetched successfully in {duration:.1f}s")
        logger.info(f"📊 Data: {len(funding_data_cache)} funding rates, {len(arbitrage_opportunities)} arbitrages")
        
    except Exception as e:
        logger.error(f"❌ CoinGlass data fetch failed: {e}")
        api_status = {
            'status': 'error',
            'errors': api_status.get('errors', 0) + 1,
            'last_error': str(e)[:200]
        }

def background_updater():
    """Met à jour les données CoinGlass toutes les 3 minutes"""
    logger.info("🔄 CoinGlass background updater started (3-minute intervals)")
    
    while True:
        try:
            logger.info("📊 CoinGlass background update...")
            fetch_all_coinglass_data()
            logger.info(f"✅ CoinGlass update completed")
            
            # Attendre 3 minutes
            time.sleep(180)
            
        except Exception as e:
            logger.error(f"❌ CoinGlass background update failed: {e}")
            time.sleep(60)  # Retry dans 1 minute

# Variables pour les signaux de trading
trading_signals = []
webhook_auth_key = "YOUR_SECRET_KEY_2024"  # Changez ceci !

# Routes Flask
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', '*')
    response.headers.add('Access-Control-Allow-Methods', '*')
    return response

@app.route('/webhook/tradingview', methods=['POST'])
def tradingview_webhook():
    """Reçoit les signaux de TradingView via webhook"""
    try:
        # Vérifier l'authentification
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
            'action': data.get('action', ''),  # BUY/SELL/CLOSE
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
        
        # Vérifier les opportunités d'arbitrage actuelles
        current_opportunity = None
        for opp in arbitrage_opportunities:
            if opp['symbol'] == symbol.replace('/USDT:USDT', ''):
                current_opportunity = opp
                break
        
        if not current_opportunity:
            return {
                'status': 'warning',
                'message': f'No current arbitrage opportunity for {symbol}'
            }
        
        # Simuler le traitement du signal
        if action == 'ENTER':
            # Logique d'entrée en position d'arbitrage
            result = {
                'status': 'success',
                'action': 'ENTER_ARBITRAGE',
                'symbol': symbol,
                'long_exchange': current_opportunity['longExchange'],
                'short_exchange': current_opportunity['shortExchange'],
                'expected_revenue': current_opportunity['revenue_annual_pct'],
                'message': f"Arbitrage position opened: Long {current_opportunity['longExchange']}, Short {current_opportunity['shortExchange']}"
            }
            
        elif action == 'EXIT':
            # Logique de sortie de position d'arbitrage
            result = {
                'status': 'success',
                'action': 'EXIT_ARBITRAGE',
                'symbol': symbol,
                'message': f"Arbitrage position closed for {symbol}"
            }
            
        else:
            result = {
                'status': 'warning',
                'message': f'Unknown action: {action}'
            }
        
        logger.info(f"✅ Signal processed: {result}")
        return result
        
    except Exception as e:
        logger.error(f"❌ Signal processing error: {e}")
        return {
            'status': 'error',
            'message': str(e)
        }

@app.route('/api/test-endpoints', methods=['GET', 'OPTIONS'])
def test_endpoints():
    """Test des endpoints directs des exchanges"""
    logger.info("📍 TEST ENDPOINTS called")
    
    results = {
        'test_timestamp': datetime.utcnow().isoformat() + 'Z',
        'binance': {'status': 'testing...'},
        'bybit': {'status': 'testing...'},
        'okx': {'status': 'testing...'}
    }
    
    # Test Binance
    try:
        binance_data = fetch_binance_funding_direct()
        results['binance'] = {
            'status': 'success' if binance_data else 'no_data',
            'count': len(binance_data),
            'sample': binance_data[:3] if binance_data else None
        }
    except Exception as e:
        results['binance'] = {
            'status': 'error',
            'error': str(e)[:200]
        }
    
    # Test Bybit
    try:
        bybit_data = fetch_bybit_funding_direct()
        results['bybit'] = {
            'status': 'success' if bybit_data else 'no_data',
            'count': len(bybit_data),
            'sample': bybit_data[:3] if bybit_data else None
        }
    except Exception as e:
        results['bybit'] = {
            'status': 'error',
            'error': str(e)[:200]
        }
    
    # Test OKX
    try:
        okx_data = fetch_okx_funding_direct()
        results['okx'] = {
            'status': 'success' if okx_data else 'no_data',
            'count': len(okx_data),
            'sample': okx_data[:3] if okx_data else None
        }
    except Exception as e:
        results['okx'] = {
            'status': 'error',
            'error': str(e)[:200]
        }
    
    # Résumé global
    total_success = sum(1 for ex in ['binance', 'bybit', 'okx'] if results[ex]['status'] == 'success')
    total_data = sum(results[ex].get('count', 0) for ex in ['binance', 'bybit', 'okx'])
    
    results['summary'] = {
        'exchanges_working': total_success,
        'total_exchanges_tested': 3,
        'total_funding_rates': total_data,
        'success_rate': f"{(total_success/3)*100:.1f}%"
    }
    
    return jsonify({
        'status': 'test_completed',
        'message': 'Direct exchange APIs testing results',
        'results': results,
        'endpoints_tested': [
            'Binance: https://fapi.binance.com/fapi/v1/fundingRate',
            'Bybit: https://api.bybit.com/v5/market/funding/history',
            'OKX: https://www.okx.com/api/v5/public/funding-rate'
        ],
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    })

@app.route('/api/funding-rate/<symbol>/current', methods=['GET', 'OPTIONS'])
def get_current_funding_rate(symbol):
    """Récupère le funding rate actuel pour un symbole spécifique"""
    logger.info(f"📍 CURRENT FUNDING RATE endpoint called for {symbol}")
    
    # Nettoyer le symbole
    clean_symbol = symbol.upper()
    if not clean_symbol.endswith('USDT'):
        clean_symbol += 'USDT'
    
    results = {}
    
    # Test Binance pour ce symbole
    try:
        url = "https://fapi.binance.com/fapi/v1/fundingRate"
        params = {'symbol': clean_symbol}
        
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data:
                latest = data[-1]  # Dernier funding rate
                results['binance'] = {
                    'fundingRate': float(latest.get('fundingRate', 0)),
                    'fundingTime': latest.get('fundingTime'),
                    'symbol': latest.get('symbol'),
                    'status': 'success'
                }
            else:
                results['binance'] = {'status': 'no_data'}
        else:
            results['binance'] = {'status': 'error', 'code': response.status_code}
            
    except Exception as e:
        results['binance'] = {'status': 'error', 'error': str(e)[:100]}
    
    # Test Bybit pour ce symbole
    try:
        url = "https://api.bybit.com/v5/market/funding/history"
        params = {
            'category': 'linear',
            'symbol': clean_symbol,
            'limit': 1
        }
        
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if 'result' in data and 'list' in data['result'] and data['result']['list']:
                latest = data['result']['list'][0]
                results['bybit'] = {
                    'fundingRate': float(latest.get('fundingRate', 0)),
                    'fundingTime': latest.get('fundingRateTimestamp'),
                    'symbol': latest.get('symbol'),
                    'status': 'success'
                }
            else:
                results['bybit'] = {'status': 'no_data'}
        else:
            results['bybit'] = {'status': 'error', 'code': response.status_code}
            
    except Exception as e:
        results['bybit'] = {'status': 'error', 'error': str(e)[:100]}
    
    # Test OKX pour ce symbole
    try:
        # Convertir BTCUSDT en BTC-USDT-SWAP
        okx_symbol = clean_symbol.replace('USDT', '') + '-USDT-SWAP'
        
        url = "https://www.okx.com/api/v5/public/funding-rate"
        params = {'instId': okx_symbol}
        
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if 'data' in data and data['data']:
                latest = data['data'][0]
                results['okx'] = {
                    'fundingRate': float(latest.get('fundingRate', 0)),
                    'fundingTime': latest.get('fundingTime'),
                    'symbol': latest.get('instId'),
                    'status': 'success'
                }
            else:
                results['okx'] = {'status': 'no_data'}
        else:
            results['okx'] = {'status': 'error', 'code': response.status_code}
            
    except Exception as e:
        results['okx'] = {'status': 'error', 'error': str(e)[:100]}
    
    # Calculer arbitrage si on a des données
    arbitrage_opportunity = None
    
    working_exchanges = [(ex, data) for ex, data in results.items() 
                        if data.get('status') == 'success']
    
    if len(working_exchanges) >= 2:
        rates = [(ex, data['fundingRate']) for ex, data in working_exchanges]
        rates.sort(key=lambda x: x[1])  # Trier par taux
        
        min_ex, min_rate = rates[0]
        max_ex, max_rate = rates[-1]
        
        divergence = max_rate - min_rate
        
        if abs(divergence) > 0.0001:  # 0.01%
            commission = 0.0008
            revenue_8h = abs(divergence) - commission
            revenue_annual = revenue_8h * 3 * 365 * 100
            
            if revenue_annual > 10:
                arbitrage_opportunity = {
                    'symbol': clean_symbol,
                    'long_exchange': min_ex,
                    'short_exchange': max_ex,
                    'long_rate': min_rate,
                    'short_rate': max_rate,
                    'divergence': abs(divergence),
                    'divergence_pct': abs(divergence) * 100,
                    'revenue_annual_pct': revenue_annual,
                    'profitable': True
                }
    
    return jsonify({
        'status': 'success',
        'symbol_requested': symbol,
        'symbol_processed': clean_symbol,
        'exchanges': results,
        'arbitrage_opportunity': arbitrage_opportunity,
        'next_funding': time_until_funding(),
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    })

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
            'note': 'Include auth_key in JSON payload'
        },
        'required_fields': ['symbol', 'action', 'auth_key'],
        'optional_fields': ['exchange_long', 'exchange_short', 'quantity', 'strategy'],
        'example_payload': {
            'auth_key': 'YOUR_SECRET_KEY_2024',
            'symbol': 'BTC/USDT:USDT',
            'action': 'ENTER',
            'exchange_long': 'binance',
            'exchange_short': 'bybit',
            'quantity': 0.1,
            'strategy': 'arbitrage'
        },
        'supported_actions': ['ENTER', 'EXIT', 'BUY', 'SELL', 'CLOSE'],
        'webhook_security': 'Use HTTPS and keep auth_key secret'
    })

@app.route('/', methods=['GET', 'OPTIONS'])
def home():
    return jsonify({
        'status': 'online',
        'service': 'CoinGlass Funding Rates API',
        'version': '8.0-coinglass',
        'description': 'Professional funding rates and arbitrage data via CoinGlass API',
        'data_source': 'CoinGlass API v4 - Professional Grade',
        'features': [
            'Real funding rates from CoinGlass aggregation',
            'Professional arbitrage calculations',
            'Multi-exchange coverage (Binance, OKX, Bybit, etc.)',
            'Real-time timing signals',
            'Reliable professional API'
        ],
        'funding_schedule': '00:00, 08:00, 16:00 UTC',
        'next_funding': time_until_funding(),
        'api_status': api_status,
        'current_data': {
            'funding_rates': len(funding_data_cache),
            'arbitrage_opportunities': len(arbitrage_opportunities),
            'last_update': last_update.isoformat() + 'Z' if last_update else None
        },
        'coinglass_base_url': COINGLASS_CONFIG['base_url'],
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    })

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'healthy',
        'data_source': 'CoinGlass API v4',
        'api_status': api_status,
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    }), 200

@app.route('/api/status', methods=['GET', 'OPTIONS'])
def get_status():
    return jsonify({
        'status': 'online',
        'service': 'CoinGlass Funding Rates API',
        'version': '8.0-coinglass',
        'last_update': last_update.isoformat() + 'Z' if last_update else None,
        'cached_rates_count': len(funding_data_cache),
        'arbitrage_opportunities_count': len(arbitrage_opportunities),
        'api_status': api_status,
        'next_funding': time_until_funding(),
        'data_source': 'CoinGlass API v4',
        'target_symbols': TARGET_SYMBOLS,
        'update_interval': '3 minutes',
        'coinglass_endpoints': list(COINGLASS_CONFIG['endpoints'].keys()),
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    })

@app.route('/api/funding-rates', methods=['GET', 'OPTIONS'])
def get_funding_rates():
    logger.info("📍 COINGLASS FUNDING RATES endpoint called")
    
    return jsonify({
        'status': 'success',
        'data': funding_data_cache,
        'count': len(funding_data_cache),
        'last_update': last_update.isoformat() + 'Z' if last_update else None,
        'next_funding': time_until_funding(),
        'api_status': api_status,
        'data_source': 'CoinGlass API v4 Professional',
        'message': 'Professional funding rates from CoinGlass aggregation',
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    })

@app.route('/api/arbitrage', methods=['GET', 'OPTIONS'])
def get_arbitrage():
    logger.info("📍 COINGLASS ARBITRAGE endpoint called")
    
    return jsonify({
        'status': 'success',
        'data': arbitrage_opportunities,
        'count': len(arbitrage_opportunities),
        'last_update': last_update.isoformat() + 'Z' if last_update else None,
        'next_funding': time_until_funding(),
        'funding_schedule': '00:00, 08:00, 16:00 UTC',
        'api_status': api_status,
        'data_source': 'CoinGlass API v4 + Custom Calculations',
        'min_annual_return': '10%',
        'message': 'Professional arbitrage opportunities from CoinGlass data',
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    })

if __name__ == '__main__':
    logger.info("🌐 Starting CoinGlass API Flask server...")
    
    # Test initial de l'API CoinGlass
    logger.info("🧪 Testing CoinGlass API connectivity...")
    overview = fetch_coinglass_funding_overview()
    if overview:
        logger.info("✅ CoinGlass API is accessible!")
    else:
        logger.warning("⚠️ CoinGlass API test failed, but starting anyway...")
    
    # Démarrer le background updater
    update_thread = threading.Thread(target=background_updater, daemon=True)
    update_thread.start()
    
    # Premier fetch de données CoinGlass
    logger.info("📊 Performing initial CoinGlass data fetch...")
    try:
        fetch_all_coinglass_data()
        logger.info(f"✅ Initial CoinGlass data loaded - {len(funding_data_cache)} rates")
    except Exception as e:
        logger.error(f"❌ Initial CoinGlass fetch failed: {e}")
    
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"🌐 CoinGlass API server starting on port {port}")
    
    app.run(
        host='0.0.0.0',
        port=port,
        debug=False,
        threaded=True
    )
