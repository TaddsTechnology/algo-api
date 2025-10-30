#!/usr/bin/env python3
"""
Formula Calculator Engine
Processes formulas from frontend and computes results using live market data
"""

import json
import math
import re
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FormulaCalculator:
    """Advanced formula calculator for financial calculations"""
    
    def __init__(self):
        self.market_data = {}
        self.variables = {}
        
        # Supported mathematical functions
        self.math_functions = {
            'abs': abs,
            'sqrt': math.sqrt,
            'pow': pow,
            'log': math.log,
            'log10': math.log10,
            'exp': math.exp,
            'sin': math.sin,
            'cos': math.cos,
            'tan': math.tan,
            'asin': math.asin,
            'acos': math.acos,
            'atan': math.atan,
            'ceil': math.ceil,
            'floor': math.floor,
            'round': round,
            'max': max,
            'min': min,
            'sum': sum,
            'avg': lambda x: sum(x) / len(x) if x else 0,
            'median': lambda x: sorted(x)[len(x)//2] if x else 0,
        }
        
        # Technical indicator functions
        self.technical_functions = {
            'rsi': self.calculate_rsi,
            'sma': self.calculate_sma,
            'ema': self.calculate_ema,
            'macd': self.calculate_macd,
            'bb_upper': self.calculate_bollinger_upper,
            'bb_lower': self.calculate_bollinger_lower,
            'stoch': self.calculate_stochastic,
            'atr': self.calculate_atr,
        }
        
        logger.info("🧮 Formula Calculator initialized")
    
    def update_market_data(self, data: Dict[str, Any]):
        """Update market data for calculations"""
        self.market_data = data
        logger.info(f"📊 Updated market data with {len(data)} instruments")
    
    def set_variables(self, variables: Dict[str, Any]):
        """Set custom variables for calculations"""
        self.variables.update(variables)
        logger.info(f"📝 Set {len(variables)} custom variables")
    
    def get_price(self, symbol: str, price_type: str = 'ltp') -> float:
        """Get price for a specific symbol"""
        try:
            if symbol in self.market_data:
                data = self.market_data[symbol]
                return float(data.get(price_type, 0))
            return 0.0
        except Exception as e:
            logger.error(f"❌ Error getting price for {symbol}: {e}")
            return 0.0
    
    def calculate_spread(self, symbol1: str, symbol2: str, operation: str = 'subtract') -> float:
        """Calculate spread between two symbols"""
        try:
            price1 = self.get_price(symbol1)
            price2 = self.get_price(symbol2)
            
            if operation == 'subtract':
                return price1 - price2
            elif operation == 'ratio':
                return price1 / price2 if price2 != 0 else 0
            elif operation == 'add':
                return price1 + price2
            elif operation == 'multiply':
                return price1 * price2
            
            return 0.0
        except Exception as e:
            logger.error(f"❌ Error calculating spread: {e}")
            return 0.0
    
    def calculate_percentage_change(self, symbol: str) -> float:
        """Calculate percentage change for a symbol"""
        try:
            if symbol in self.market_data:
                data = self.market_data[symbol]
                ltp = float(data.get('ltp', 0))
                close = float(data.get('close', 0))
                
                if close != 0:
                    return ((ltp - close) / close) * 100
            return 0.0
        except Exception as e:
            logger.error(f"❌ Error calculating percentage change: {e}")
            return 0.0
    
    def calculate_volatility(self, symbols: List[str], period: int = 20) -> float:
        """Calculate volatility for a set of symbols"""
        try:
            prices = []
            for symbol in symbols:
                if symbol in self.market_data:
                    prices.append(self.get_price(symbol))
            
            if len(prices) < 2:
                return 0.0
            
            avg_price = sum(prices) / len(prices)
            variance = sum((p - avg_price) ** 2 for p in prices) / len(prices)
            return math.sqrt(variance)
            
        except Exception as e:
            logger.error(f"❌ Error calculating volatility: {e}")
            return 0.0
    
    def calculate_rsi(self, symbol: str, period: int = 14) -> float:
        """Calculate RSI (simplified version using current data)"""
        try:
            if symbol in self.market_data:
                data = self.market_data[symbol]
                current_price = float(data.get('ltp', 0))
                open_price = float(data.get('open', 0))
                
                if open_price != 0:
                    change = current_price - open_price
                    gain = max(0, change)
                    loss = max(0, -change)
                    
                    if loss == 0:
                        return 100.0
                    
                    rs = gain / loss
                    rsi = 100 - (100 / (1 + rs))
                    return rsi
            return 50.0  # Neutral RSI
        except Exception as e:
            logger.error(f"❌ Error calculating RSI: {e}")
            return 50.0
    
    def calculate_sma(self, symbols: List[str], period: int = 20) -> float:
        """Calculate Simple Moving Average"""
        try:
            prices = []
            for symbol in symbols[:period]:
                if symbol in self.market_data:
                    prices.append(self.get_price(symbol))
            
            return sum(prices) / len(prices) if prices else 0.0
        except Exception as e:
            logger.error(f"❌ Error calculating SMA: {e}")
            return 0.0
    
    def calculate_ema(self, symbols: List[str], period: int = 20) -> float:
        """Calculate Exponential Moving Average (simplified)"""
        try:
            prices = []
            for symbol in symbols[:period]:
                if symbol in self.market_data:
                    prices.append(self.get_price(symbol))
            
            if not prices:
                return 0.0
            
            multiplier = 2 / (period + 1)
            ema = prices[0]
            
            for price in prices[1:]:
                ema = (price * multiplier) + (ema * (1 - multiplier))
            
            return ema
        except Exception as e:
            logger.error(f"❌ Error calculating EMA: {e}")
            return 0.0
    
    def calculate_macd(self, symbol: str) -> Dict[str, float]:
        """Calculate MACD (simplified)"""
        try:
            if symbol in self.market_data:
                data = self.market_data[symbol]
                current_price = float(data.get('ltp', 0))
                open_price = float(data.get('open', 0))
                
                # Simplified MACD calculation
                macd_line = current_price - open_price
                signal_line = macd_line * 0.7  # Simplified signal
                histogram = macd_line - signal_line
                
                return {
                    'macd': macd_line,
                    'signal': signal_line,
                    'histogram': histogram
                }
            
            return {'macd': 0, 'signal': 0, 'histogram': 0}
        except Exception as e:
            logger.error(f"❌ Error calculating MACD: {e}")
            return {'macd': 0, 'signal': 0, 'histogram': 0}
    
    def calculate_bollinger_upper(self, symbol: str, period: int = 20, std_dev: float = 2) -> float:
        """Calculate Bollinger Band upper limit"""
        try:
            if symbol in self.market_data:
                data = self.market_data[symbol]
                current_price = float(data.get('ltp', 0))
                high = float(data.get('high', current_price))
                low = float(data.get('low', current_price))
                
                middle = (high + low + current_price) / 3
                volatility = abs(high - low)
                
                return middle + (std_dev * volatility * 0.1)
            return 0.0
        except Exception as e:
            logger.error(f"❌ Error calculating Bollinger upper: {e}")
            return 0.0
    
    def calculate_bollinger_lower(self, symbol: str, period: int = 20, std_dev: float = 2) -> float:
        """Calculate Bollinger Band lower limit"""
        try:
            if symbol in self.market_data:
                data = self.market_data[symbol]
                current_price = float(data.get('ltp', 0))
                high = float(data.get('high', current_price))
                low = float(data.get('low', current_price))
                
                middle = (high + low + current_price) / 3
                volatility = abs(high - low)
                
                return middle - (std_dev * volatility * 0.1)
            return 0.0
        except Exception as e:
            logger.error(f"❌ Error calculating Bollinger lower: {e}")
            return 0.0
    
    def calculate_stochastic(self, symbol: str, period: int = 14) -> float:
        """Calculate Stochastic oscillator"""
        try:
            if symbol in self.market_data:
                data = self.market_data[symbol]
                current_price = float(data.get('ltp', 0))
                high = float(data.get('high', current_price))
                low = float(data.get('low', current_price))
                
                if high != low:
                    stoch = ((current_price - low) / (high - low)) * 100
                    return stoch
                return 50.0
            return 50.0
        except Exception as e:
            logger.error(f"❌ Error calculating Stochastic: {e}")
            return 50.0
    
    def calculate_atr(self, symbol: str, period: int = 14) -> float:
        """Calculate Average True Range"""
        try:
            if symbol in self.market_data:
                data = self.market_data[symbol]
                high = float(data.get('high', 0))
                low = float(data.get('low', 0))
                close = float(data.get('close', 0))
                
                true_range = max(
                    high - low,
                    abs(high - close),
                    abs(low - close)
                )
                
                return true_range
            return 0.0
        except Exception as e:
            logger.error(f"❌ Error calculating ATR: {e}")
            return 0.0
    
    def parse_and_calculate(self, formula: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Parse and calculate a formula"""
        try:
            # Set variables if provided
            if variables:
                self.set_variables(variables)
            
            # Clean and prepare formula
            formula = formula.strip()
            logger.info(f"🧮 Processing formula: {formula}")
            
            # Replace symbol references with actual values
            formula = self._replace_symbol_references(formula)
            
            # Replace function calls
            formula = self._replace_function_calls(formula)
            
            # Replace variables
            formula = self._replace_variables(formula)
            
            # Evaluate the formula safely
            result = self._safe_eval(formula)
            
            return {
                'success': True,
                'result': result,
                'formula': formula,
                'timestamp': datetime.now().isoformat(),
                'message': f"✅ Formula calculated successfully: {result}"
            }
            
        except Exception as e:
            logger.error(f"❌ Error calculating formula: {e}")
            return {
                'success': False,
                'result': 0,
                'error': str(e),
                'formula': formula,
                'timestamp': datetime.now().isoformat(),
                'message': f"❌ Formula calculation failed: {str(e)}"
            }
    
    def _replace_symbol_references(self, formula: str) -> str:
        """Replace symbol references like NIFTY.ltp with actual values"""
        # Pattern: SYMBOL.price_type
        pattern = r'([A-Z0-9_]+)\.([a-z_]+)'
        
        def replace_symbol(match):
            symbol = match.group(1)
            price_type = match.group(2)
            value = self.get_price(symbol, price_type)
            return str(value)
        
        return re.sub(pattern, replace_symbol, formula)
    
    def _replace_function_calls(self, formula: str) -> str:
        """Replace function calls with calculated values"""
        # Handle spread functions
        spread_pattern = r'spread\(([A-Z0-9_]+),\s*([A-Z0-9_]+)(?:,\s*"([^"]+)")?\)'
        
        def replace_spread(match):
            symbol1 = match.group(1)
            symbol2 = match.group(2)
            operation = match.group(3) or 'subtract'
            value = self.calculate_spread(symbol1, symbol2, operation)
            return str(value)
        
        formula = re.sub(spread_pattern, replace_spread, formula)
        
        # Handle percentage change functions
        pct_pattern = r'pct_change\(([A-Z0-9_]+)\)'
        
        def replace_pct(match):
            symbol = match.group(1)
            value = self.calculate_percentage_change(symbol)
            return str(value)
        
        formula = re.sub(pct_pattern, replace_pct, formula)
        
        # Handle technical indicator functions
        for func_name, func in self.technical_functions.items():
            tech_pattern = fr'{func_name}\(([A-Z0-9_]+)(?:,\s*(\d+))?\)'
            
            def replace_tech(match):
                symbol = match.group(1)
                period = int(match.group(2)) if match.group(2) else 14
                if func_name == 'macd':
                    result = func(symbol)
                    return str(result['macd'])
                else:
                    value = func(symbol, period) if 'period' in func.__code__.co_varnames else func(symbol)
                    return str(value)
            
            formula = re.sub(tech_pattern, replace_tech, formula)
        
        return formula
    
    def _replace_variables(self, formula: str) -> str:
        """Replace custom variables with their values"""
        for var_name, var_value in self.variables.items():
            formula = formula.replace(f'${var_name}', str(var_value))
        
        return formula
    
    def _safe_eval(self, expression: str) -> float:
        """Safely evaluate mathematical expression"""
        # Allow only safe mathematical operations
        allowed_chars = set('0123456789+-*/.() ')
        if not all(c in allowed_chars or c.isalpha() for c in expression):
            raise ValueError("Invalid characters in formula")
        
        # Create safe namespace for evaluation
        safe_dict = {
            '__builtins__': {},
            **self.math_functions
        }
        
        try:
            result = eval(expression, safe_dict)
            return float(result)
        except Exception as e:
            raise ValueError(f"Invalid formula: {str(e)}")
    
    def get_supported_functions(self) -> Dict[str, List[str]]:
        """Get list of supported functions"""
        return {
            'mathematical': list(self.math_functions.keys()),
            'technical': list(self.technical_functions.keys()),
            'special': ['spread', 'pct_change', 'volatility']
        }
    
    def validate_formula(self, formula: str) -> Dict[str, Any]:
        """Validate a formula without executing it"""
        try:
            # Basic syntax validation
            if not formula or not formula.strip():
                return {'valid': False, 'error': 'Empty formula'}
            
            # Check for balanced parentheses
            if formula.count('(') != formula.count(')'):
                return {'valid': False, 'error': 'Unbalanced parentheses'}
            
            # Check for valid characters
            allowed_pattern = r'^[A-Za-z0-9_+\-*/().,$\s"]+$'
            if not re.match(allowed_pattern, formula):
                return {'valid': False, 'error': 'Invalid characters in formula'}
            
            return {'valid': True, 'message': 'Formula syntax is valid'}
            
        except Exception as e:
            return {'valid': False, 'error': str(e)}

# Global calculator instance
calculator = FormulaCalculator()

def process_formula(formula: str, market_data: Dict[str, Any], variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Process a formula with given market data"""
    calculator.update_market_data(market_data)
    return calculator.parse_and_calculate(formula, variables)