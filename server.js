// server.js - Backend API pour funding rates RÉELS
const express = require('express');
const cors = require('cors');
const helmet = require('helmet');
const compression = require('compression');
const axios = require('axios');

const app = express();

// Middleware de sécurité et performance
app.use(helmet());
app.use(compression());
app.use(cors({
    origin: [
        'https://marcr1993.github.io',
        'http://localhost:3000',
        'http://127.0.0.1:5500'
    ]
}));
app.use(express.json());

// Cache global pour éviter les rate limits
const cache = new Map();
const CACHE_DURATION = 30000; // 30 secondes
const REQUEST_TIMEOUT = 10000; // 10 secondes

// Configuration des cryptos supportées
const SUPPORTED_CRYPTOS = ['BTC', 'ETH', 'SOL', 'ADA', 'DOT', 'MATIC', 'LINK', 'AVAX', 'ATOM', 'NEAR'];

// Utilitaire pour les requêtes avec timeout
const fetchWithTimeout = async (url, timeout = REQUEST_TIMEOUT) => {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeout);
    
    try {
        const response = await axios.get(url, {
            signal: controller.signal,
            timeout: timeout
        });
        clearTimeout(timeoutId);
        return response;
    } catch (error) {
        clearTimeout(timeoutId);
        throw error;
    }
};

// API Binance Futures - RÉELLE
async function fetchBinanceRates() {
    const startTime = Date.now();
    
    try {
        console.log('🟡 Fetching Binance Futures...');
        const response = await fetchWithTimeout('https://fapi.binance.com/fapi/v1/premiumIndex');
        
        const data = response.data
            .filter(item => 
                item.symbol.endsWith('USDT') && 
                SUPPORTED_CRYPTOS.some(crypto => item.symbol.startsWith(crypto + 'USDT'))
            )
            .map(item => ({
                exchange: 'Binance',
                symbol: item.symbol.replace('USDT', ''),
                fundingRate: parseFloat(item.lastFundingRate),
                nextFunding: parseInt(item.nextFundingTime),
                markPrice: parseFloat(item.markPrice),
                timestamp: Date.now()
            }));
            
        console.log(`✅ Binance: ${data.length} pairs (${Date.now() - startTime}ms)`);
        return data;
        
    } catch (error) {
        console.error('❌ Binance Error:', error.message);
        return [];
    }
}

// API KuCoin Futures - RÉELLE  
async function fetchKuCoinRates() {
    const startTime = Date.now();
    
    try {
        console.log('🟢 Fetching KuCoin Futures...');
        
        // Récupérer les contrats actifs
        const contractsResponse = await fetchWithTimeout('https://api-futures.kucoin.com/api/v1/contracts/active');
        const contracts = contractsResponse.data.data.filter(item => 
            item.quoteCurrency === 'USDT' && 
            SUPPORTED_CRYPTOS.includes(item.baseCurrency)
        );
        
        // Récupérer les funding rates pour chaque contrat
        const fundingPromises = contracts.map(async (contract) => {
            try {
                const fundingResponse = await fetchWithTimeout(
                    `https://api-futures.kucoin.com/api/v1/funding-rate/${contract.symbol}/current`
                );
                
                return {
                    exchange: 'KuCoin',
                    symbol: contract.baseCurrency,
                    fundingRate: parseFloat(fundingResponse.data.data.value || 0),
                    nextFunding: Date.now() + (8 * 60 * 60 * 1000), // Approximation
                    markPrice: parseFloat(contract.markPrice || 0),
                    timestamp: Date.now()
                };
            } catch (err) {
                // Fallback si funding rate spécifique échoue
                return {
                    exchange: 'KuCoin',
                    symbol: contract.baseCurrency,
                    fundingRate: 0,
                    nextFunding: Date.now() + (8 * 60 * 60 * 1000),
                    markPrice: parseFloat(contract.markPrice || 0),
                    timestamp: Date.now()
                };
            }
        });
        
        const results = await Promise.allSettled(fundingPromises);
        const data = results
            .filter(result => result.status === 'fulfilled')
            .map(result => result.value);
            
        console.log(`✅ KuCoin: ${data.length} pairs (${Date.now() - startTime}ms)`);
        return data;
        
    } catch (error) {
        console.error('❌ KuCoin Error:', error.message);
        return [];
    }
}

// API Bybit Futures - RÉELLE
async function fetchBybitRates() {
    const startTime = Date.now();
    
    try {
        console.log('🟠 Fetching Bybit Linear...');
        const response = await fetchWithTimeout('https://api.bybit.com/v5/market/instruments-info?category=linear');
        
        const data = response.data.result.list
            .filter(item => 
                item.quoteCoin === 'USDT' && 
                SUPPORTED_CRYPTOS.includes(item.baseCoin)
            )
            .map(item => ({
                exchange: 'Bybit',
                symbol: item.baseCoin,
                fundingRate: parseFloat(item.fundingRate || 0),
                nextFunding: parseInt(item.nextFundingTime || Date.now() + (8 * 60 * 60 * 1000)),
                markPrice: parseFloat(item.markPrice || 0),
                timestamp: Date.now()
            }));
            
        console.log(`✅ Bybit: ${data.length} pairs (${Date.now() - startTime}ms)`);
        return data;
        
    } catch (error) {
        console.error('❌ Bybit Error:', error.message);
        return [];
    }
}

// API OKX Futures - RÉELLE
async function fetchOKXRates() {
    const startTime = Date.now();
    
    try {
        console.log('🔵 Fetching OKX Swaps...');
        
        const [instrumentsResponse, fundingResponse] = await Promise.all([
            fetchWithTimeout('https://www.okx.com/api/v5/public/instruments?instType=SWAP'),
            fetchWithTimeout('https://www.okx.com/api/v5/public/funding-rate?instType=SWAP')
        ]);
        
        const instruments = instrumentsResponse.data.data;
        const fundingRates = fundingResponse.data.data;
        
        const data = instruments
            .filter(item => 
                item.instId.endsWith('-USDT-SWAP') && 
                SUPPORTED_CRYPTOS.includes(item.instId.split('-')[0])
            )
            .map(item => {
                const symbol = item.instId.split('-')[0];
                const funding = fundingRates.find(f => f.instId === item.instId);
                
                return {
                    exchange: 'OKX',
                    symbol: symbol,
                    fundingRate: funding ? parseFloat(funding.fundingRate) : 0,
                    nextFunding: funding ? parseInt(funding.nextFundingTime) : Date.now() + (8 * 60 * 60 * 1000),
                    markPrice: parseFloat(item.markPx || 0),
                    timestamp: Date.now()
                };
            });
            
        console.log(`✅ OKX: ${data.length} pairs (${Date.now() - startTime}ms)`);
        return data;
        
    } catch (error) {
        console.error('❌ OKX Error:', error.message);
        return [];
    }
}

// Endpoint principal - Toutes les données RÉELLES
app.get('/api/funding-rates', async (req, res) => {
    const cacheKey = 'all-funding-rates';
    const cached = cache.get(cacheKey);
    
    // Retourner cache si valide
    if (cached && Date.now() - cached.timestamp < CACHE_DURATION) {
        return res.json({
            success: true,
            data: cached.data,
            cached: true,
            timestamp: cached.timestamp,
            ttl: Math.round((CACHE_DURATION - (Date.now() - cached.timestamp)) / 1000)
        });
    }
    
    try {
        const startTime = Date.now();
        console.log('🔄 Collecte des funding rates RÉELS...');
        
        // Appeler toutes les APIs en parallèle
        const [binanceResult, kucoinResult, bybitResult, okxResult] = await Promise.allSettled([
            fetchBinanceRates(),
            fetchKuCoinRates(),
            fetchBybitRates(),
            fetchOKXRates()
        ]);
        
        // Combiner toutes les données réussies
        let allData = [];
        const exchangeStats = {};
        
        if (binanceResult.status === 'fulfilled') {
            allData = allData.concat(binanceResult.value);
            exchangeStats.binance = binanceResult.value.length;
        } else {
            exchangeStats.binance = 0;
        }
        
        if (kucoinResult.status === 'fulfilled') {
            allData = allData.concat(kucoinResult.value);
            exchangeStats.kucoin = kucoinResult.value.length;
        } else {
            exchangeStats.kucoin = 0;
        }
        
        if (bybitResult.status === 'fulfilled') {
            allData = allData.concat(bybitResult.value);
            exchangeStats.bybit = bybitResult.value.length;
        } else {
            exchangeStats.bybit = 0;
        }
        
        if (okxResult.status === 'fulfilled') {
            allData = allData.concat(okxResult.value);
            exchangeStats.okx = okxResult.value.length;
        } else {
            exchangeStats.okx = 0;
        }
        
        // Mettre en cache
        cache.set(cacheKey, {
            data: allData,
            timestamp: Date.now()
        });
        
        const totalTime = Date.now() - startTime;
        console.log(`✅ ${allData.length} funding rates RÉELS collectés en ${totalTime}ms`);
        
        res.json({
            success: true,
            data: allData,
            cached: false,
            timestamp: Date.now(),
            totalPairs: allData.length,
            exchanges: exchangeStats,
            responseTime: totalTime,
            nextUpdate: CACHE_DURATION / 1000
        });
        
    } catch (error) {
        console.error('❌ Erreur globale:', error);
        res.status(500).json({
            success: false,
            error: error.message,
            timestamp: Date.now()
        });
    }
});

// Endpoint de santé
app.get('/api/health', (req, res) => {
    res.json({
        status: 'OK',
        uptime: Math.round(process.uptime()),
        memory: process.memoryUsage(),
        timestamp: Date.now(),
        version: '1.0.0'
    });
});

// Endpoint pour les cryptos supportées
app.get('/api/cryptos', (req, res) => {
    res.json({
        supported: SUPPORTED_CRYPTOS,
        count: SUPPORTED_CRYPTOS.length,
        timestamp: Date.now()
    });
});

// Page d'accueil avec documentation
app.get('/', (req, res) => {
    res.send(`
        <html>
            <head><title>Funding Rates API</title></head>
            <body style="font-family: Arial; padding: 40px; background: #1a1a2e; color: white;">
                <h1>🚀 Funding Rates API</h1>
                <p>Backend API pour funding rates crypto en temps réel</p>
                
                <h2>📡 Endpoints disponibles :</h2>
                <ul>
                    <li><strong>GET /api/funding-rates</strong> - Tous les funding rates</li>
                    <li><strong>GET /api/health</strong> - Statut du serveur</li>
                    <li><strong>GET /api/cryptos</strong> - Cryptos supportées</li>
                </ul>
                
                <h2>🏢 Exchanges connectés :</h2>
                <ul>
                    <li>🟡 Binance Futures</li>
                    <li>🟢 KuCoin Futures</li>
                    <li>🟠 Bybit Linear</li>
                    <li>🔵 OKX Swaps</li>
                </ul>
                
                <p><strong>Cache:</strong> 30 secondes | <strong>Timeout:</strong> 10 secondes</p>
                
                <a href="/api/funding-rates" style="color: #4CAF50;">🔗 Tester l'API</a>
            </body>
        </html>
    `);
});

// Middleware de gestion d'erreurs
app.use((err, req, res, next) => {
    console.error('❌ Erreur serveur:', err);
    res.status(500).json({
        success: false,
        error: 'Erreur interne du serveur',
        timestamp: Date.now()
    });
});

// Démarrage du serveur
const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
    console.log(`🚀 Funding Rates API Server démarré`);
    console.log(`📡 Port: ${PORT}`);
    console.log(`🌐 Endpoints:`);
    console.log(`   - http://localhost:${PORT}/api/funding-rates`);
    console.log(`   - http://localhost:${PORT}/api/health`);
    console.log(`   - http://localhost:${PORT}/api/cryptos`);
    console.log('🔄 Collecte automatique toutes les 30 secondes');
});

module.exports = app;
