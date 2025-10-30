---
title: Enhanced Algo Trading API
emoji: 📈
colorFrom: green
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
short_description: High-performance algorithmic trading API with specialized futures endpoints and formula calculations
---

# 🚀 Enhanced Algo Trading Market Data API

A high-performance FastAPI application providing real-time futures market data with specialized endpoints for algorithmic trading.

## 🎯 Features

- **Ultra-fast Data Fetching**: 0.5-2s refresh rates
- **Specialized Endpoints**: Current, Near, Far futures categories
- **Formula Calculator**: Real-time calculations with technical indicators
- **Production Ready**: Docker deployment with health monitoring

## 📊 API Endpoints

- `GET /api/current-futures` - Current month futures (0-35 days)
- `GET /api/near-futures` - Near month futures (36-70 days)
- `GET /api/far-futures` - Far month futures (71-105 days)
- `GET /api/all-futures` - All futures combined
- `POST /api/calculate` - Formula calculations
- `GET /docs` - Interactive API documentation

## 🔧 Environment Variables Required

Set these in your Space settings:
- `KITE_API_KEY`: Your Kite Connect API key
- `KITE_ACCESS_TOKEN`: Your current access token
