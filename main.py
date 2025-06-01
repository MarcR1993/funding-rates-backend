"""
Backend Flask pour Funding Rates - Version CORRIGÉE
"""
from flask import Flask, jsonify, request
from flask_cors import CORS
import logging
import sys
import os
from datetime import datetime

# Configuration logging
logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

# Initialisation Flask
app = Flask(__name__)
CORS(app, origins=["*"])

logger.info("🚀 Starting Funding Rates API - FIXED VERSION")

# Variables globales simples pour commencer
funding_data_cache = []
last_update = None

# Données de test pour commencer
def get_test_data():
    return [
        {'symbol': 'BTC/USDT:USDT', 'exchange': 'binance', 'fundingRate': 0.0001, 'timestamp': datetime.now().isoformat()},
        {'symbol': 'BTC/USDT:USDT', 'exchange': 'bybit', 'fundingRate': 0.0002, 'timestamp': datetime.now().isoformat()},
        {'symbol': 'BTC/USDT:USDT', 'exchange': 'okx', 'fundingRate': 0.0003, 'timestamp': datetime.now().isoformat()},
        {'symbol': 'BTC/USDT:USDT', 'exchange': 'gate', 'fundingRate': 0.0004, 'timestamp': datetime.now().isoformat()},
        {'symbol': 'ETH/USDT:USDT', 'exchange': 'binance', 'fundingRate': 0.0005, 'timestamp': datetime.now().isoformat()},
        {'symbol': 'ETH/USDT:USDT', 'exchange': 'bybit', 'fundingRate': 0.0006, 'timestamp': datetime.now().isoformat()},
        {'symbol': 'ETH/USDT:USDT', 'exchange': 'okx', 'fundingRate': 0.0007, 'timestamp': datetime.now().isoformat()},
        {'symbol': 'ETH/USDT:USDT', 'exchange': 'gate', 'fundingRate': 0.0008, 'timestamp': datetime.now().isoformat()},
        {'symbol': 'SOL/USDT:USDT', 'exchange': 'binance', 'fundingRate': -0.0001, 'timestamp': datetime.now().isoformat()},
        {'symbol': 'SOL/USDT:USDT', 'exchange': 'bybit', 'fundingRate': -0.0002, 'timestamp': datetime.now().isoformat()},
    ]

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', '*')
    response.headers.add('Access-Control-Allow-Methods', '*')
    return response

@app.route('/', methods=['GET', 'OPTIONS'])
def home():
    logger.info("📍 HOME endpoint called")
    return jsonify({
        'status': 'online',
        'service': 'Funding Rates API',
        'version': '2.0-fixed',
        'message': 'Backend is working correctly!',
        'endpoints': {
            '/api/funding-rates': 'GET - All funding rates',
            '/api/arbitrage': 'GET - Arbitrage opportunities', 
            '/api/status': 'GET - Service status',
            '/health': 'GET - Health check'
        },
        'timestamp': datetime.now().isoformat()
    })

@app.route('/health', methods=['GET'])
def health():
    logger.info("📍 HEALTH endpoint called")
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat()
    }), 200

@app.route('/api/status', methods=['GET', 'OPTIONS'])
def get_status():
    logger.info("📍 STATUS endpoint called")
    return jsonify({
        'status': 'online',
        'service': 'Funding Rates API',
        'version': '2.0-fixed',
        'uptime': 'running',
        'last_update': last_update.isoformat() if last_update else None,
        'cached_data_count': len(funding_data_cache),
        'supported_exchanges': ['binance', 'bybit', 'okx', 'gate'],
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/funding-rates', methods=['GET', 'OPTIONS'])
def get_funding_rates():
    logger.info("📍 FUNDING RATES endpoint called")
    
    global funding_data_cache, last_update
    
    try:
        # Pour l'instant, utiliser des données de test
        funding_data_cache = get_test_data()
        last_update = datetime.now()
        
        logger.info(f"✅ Returning {len(funding_data_cache)} funding rates")
        
        return jsonify({
            'status': 'success',
            'data': funding_data_cache,
            'count': len(funding_data_cache),
            'last_update': last_update.isoformat(),
            'message': 'Test data - working correctly!',
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"❌ Error in funding rates endpoint: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e),
            'data': [],
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/arbitrage', methods=['GET', 'OPTIONS'])
def get_arbitrage():
    logger.info("📍 ARBITRAGE endpoint called")
    
    # Calculer quelques arbitrages simples
    arbitrage_data = [
        {
            'symbol': 'BTC',
            'longExchange': 'binance',
            'shortExchange': 'gate',
            'longRate': 0.0001,
            'shortRate': 0.0004,
            'divergence': 0.03,
            'commission': 0.01,
            'revenue': 0.02,
            'timestamp': datetime.now().isoformat()
        },
        {
            'symbol': 'ETH',
            'longExchange': 'binance', 
            'shortExchange': 'gate',
            'longRate': 0.0005,
            'shortRate': 0.0008,
            'divergence': 0.03,
            'commission': 0.01,
            'revenue': 0.02,
            'timestamp': datetime.now().isoformat()
        }
    ]
    
    return jsonify({
        'status': 'success',
        'data': arbitrage_data,
        'count': len(arbitrage_data),
        'message': 'Test arbitrage data',
        'timestamp': datetime.now().isoformat()
    })

@app.errorhandler(404)
def not_found(error):
    logger.error(f"📍 404 ERROR: {request.url}")
    return jsonify({
        'status': 'error',
        'message': f'Endpoint not found: {request.path}',
        'available_endpoints': ['/', '/health', '/api/status', '/api/funding-rates', '/api/arbitrage'],
        'timestamp': datetime.now().isoformat()
    }), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"📍 500 ERROR: {error}")
    return jsonify({
        'status': 'error',
        'message': 'Internal server error',
        'timestamp': datetime.now().isoformat()
    }), 500

if __name__ == '__main__':
    logger.info("🌐 Starting Flask server...")
    
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"🌐 Port: {port}")
    
    # Initialiser les données de test
    funding_data_cache = get_test_data()
    last_update = datetime.now()
    logger.info(f"📊 Initialized with {len(funding_data_cache)} test records")
    
    app.run(
        host='0.0.0.0',
        port=port,
        debug=False,
        threaded=True
    )
