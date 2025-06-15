"""
Enhanced Open Interest Calculator for NIFTY Options
Since Yahoo Finance doesn't provide actual OI data, this module generates
realistic theoretical OI patterns based on market behavior and volatility.
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import random
from loguru import logger

class OpenInterestCalculator:
    """Calculate theoretical Open Interest patterns for NIFTY options"""
    
    def __init__(self):
        self.logger = logger
        # Set random seed for consistent patterns
        random.seed(42)
        np.random.seed(42)
    
    def calculate_theoretical_oi(self, 
                                spot_price: float, 
                                strikes: List[float], 
                                volatility: float = 0.20,
                                days_to_expiry: int = 7) -> Dict[float, Dict[str, float]]:
        """
        Calculate theoretical Open Interest for given strikes
        
        Args:
            spot_price: Current NIFTY spot price
            strikes: List of strike prices
            volatility: Implied volatility
            days_to_expiry: Days to expiry
            
        Returns:
            Dictionary with strike as key and {'call_oi': x, 'put_oi': y} as value
        """
        self.logger.info(f"Calculating theoretical OI for {len(strikes)} strikes around spot {spot_price}")
        
        oi_data = {}
        
        # Base OI levels (in lakhs)
        base_call_oi = 50.0
        base_put_oi = 50.0
        
        # ATM strike
        atm_strike = min(strikes, key=lambda x: abs(x - spot_price))
        
        for strike in strikes:
            # Distance from ATM (normalized)
            distance_from_atm = abs(strike - atm_strike) / spot_price
            
            # Moneyness factor
            if strike < spot_price:
                # ITM calls, OTM puts
                call_moneyness = (spot_price - strike) / spot_price
                put_moneyness = 0.1  # Lower OI for OTM puts far from spot
            elif strike > spot_price:
                # OTM calls, ITM puts  
                call_moneyness = 0.1  # Lower OI for OTM calls far from spot
                put_moneyness = (strike - spot_price) / spot_price
            else:
                # ATM
                call_moneyness = 0.5
                put_moneyness = 0.5
            
            # Calculate Call OI
            # Higher OI at ATM and resistance levels
            if abs(strike - spot_price) <= 100:  # ATM range
                call_multiplier = 1.5 + (0.5 * np.exp(-distance_from_atm * 10))
            elif strike > spot_price:  # Resistance levels (calls sold)
                if (strike - spot_price) % 500 == 0:  # Major resistance levels
                    call_multiplier = 2.0
                elif (strike - spot_price) % 100 == 0:  # Minor resistance levels
                    call_multiplier = 1.3
                else:
                    call_multiplier = 0.8 - distance_from_atm
            else:
                call_multiplier = 0.6 - distance_from_atm * 0.5
            
            # Calculate Put OI
            # Higher OI at support levels and protective puts
            if abs(strike - spot_price) <= 100:  # ATM range
                put_multiplier = 1.5 + (0.5 * np.exp(-distance_from_atm * 10))
            elif strike < spot_price:  # Support levels (puts bought)
                if (spot_price - strike) % 500 == 0:  # Major support levels
                    put_multiplier = 2.2
                elif (spot_price - strike) % 100 == 0:  # Minor support levels
                    put_multiplier = 1.4
                else:
                    put_multiplier = 0.9 - distance_from_atm * 0.3
            else:
                put_multiplier = 0.5 - distance_from_atm * 0.4
            
            # Apply volatility impact (higher vol = higher OI)
            vol_factor = 1 + (volatility - 0.15) * 2
            
            # Apply time decay factor (closer to expiry = higher activity)
            time_factor = 1 + (30 - days_to_expiry) / 30 * 0.5
            
            # Calculate final OI values
            call_oi = max(5.0, base_call_oi * call_multiplier * vol_factor * time_factor)
            put_oi = max(5.0, base_put_oi * put_multiplier * vol_factor * time_factor)
            
            # Add some random variation to make it realistic
            call_oi *= (0.8 + 0.4 * random.random())
            put_oi *= (0.8 + 0.4 * random.random())
            
            # Round to realistic values
            call_oi = round(call_oi, 2)
            put_oi = round(put_oi, 2)
            
            oi_data[strike] = {
                'call_oi': call_oi,
                'put_oi': put_oi,
                'total_oi': call_oi + put_oi,
                'pcr': put_oi / call_oi if call_oi > 0 else 0
            }
        
        self.logger.success(f"Generated theoretical OI data for {len(oi_data)} strikes")
        return oi_data
    
    def calculate_max_pain(self, oi_data: Dict[float, Dict[str, float]]) -> float:
        """Calculate Max Pain strike price"""
        max_pain_data = []
        
        for test_strike in oi_data.keys():
            total_pain = 0
            
            for strike, data in oi_data.items():
                # Call pain: if spot > strike, calls are ITM
                if test_strike > strike:
                    call_pain = (test_strike - strike) * data['call_oi']
                else:
                    call_pain = 0
                
                # Put pain: if spot < strike, puts are ITM  
                if test_strike < strike:
                    put_pain = (strike - test_strike) * data['put_oi']
                else:
                    put_pain = 0
                
                total_pain += call_pain + put_pain
            
            max_pain_data.append({
                'strike': test_strike,
                'total_pain': total_pain
            })
        
        # Find strike with minimum total pain
        max_pain_strike = min(max_pain_data, key=lambda x: x['total_pain'])['strike']
        self.logger.info(f"Max Pain calculated at strike: {max_pain_strike}")
        
        return max_pain_strike
    
    def identify_support_resistance(self, 
                                   oi_data: Dict[float, Dict[str, float]], 
                                   spot_price: float) -> Tuple[List[Dict], List[Dict]]:
        """Identify support and resistance levels based on OI"""
        
        # Support levels: High Put OI below current price
        support_candidates = []
        resistance_candidates = []
        
        for strike, data in oi_data.items():
            if strike < spot_price:
                # Potential support
                support_candidates.append({
                    'strike': strike,
                    'put_oi': data['put_oi'],
                    'distance': spot_price - strike
                })
            elif strike > spot_price:
                # Potential resistance
                resistance_candidates.append({
                    'strike': strike,
                    'call_oi': data['call_oi'],
                    'distance': strike - spot_price
                })
        
        # Sort by OI and select top 3
        support_levels = sorted(support_candidates, key=lambda x: x['put_oi'], reverse=True)[:3]
        resistance_levels = sorted(resistance_candidates, key=lambda x: x['call_oi'], reverse=True)[:3]
        
        self.logger.info(f"Identified {len(support_levels)} support and {len(resistance_levels)} resistance levels")
        
        return support_levels, resistance_levels
    
    def generate_oi_chart_data(self, oi_data: Dict[float, Dict[str, float]]) -> Dict:
        """Generate data for OI chart visualization"""
        
        strikes = sorted(oi_data.keys())
        call_oi_values = [oi_data[strike]['call_oi'] for strike in strikes]
        put_oi_values = [oi_data[strike]['put_oi'] for strike in strikes]
        
        chart_data = {
            'labels': [str(int(strike)) for strike in strikes],
            'call_oi': call_oi_values,
            'put_oi': put_oi_values,
            'total_call_oi': sum(call_oi_values),
            'total_put_oi': sum(put_oi_values),
            'total_pcr': sum(put_oi_values) / sum(call_oi_values) if sum(call_oi_values) > 0 else 0
        }
        
        self.logger.success("Generated OI chart data successfully")
        return chart_data

class MarketDataEnhancer:
    """Enhance Yahoo Finance data with realistic market patterns"""
    
    def __init__(self):
        self.oi_calculator = OpenInterestCalculator()
        self.logger = logger
    
    def enhance_options_data(self, 
                           options_data: List[Dict], 
                           spot_price: float,
                           volatility: float = 0.20) -> List[Dict]:
        """Enhance options data with OI and market metrics"""
        
        self.logger.info("Enhancing options data with realistic market patterns")
        
        # Extract strikes
        strikes = sorted(list(set([opt['strike'] for opt in options_data])))
        
        # Calculate theoretical OI
        days_to_expiry = options_data[0].get('days_to_expiry', 7) if options_data else 7
        oi_data = self.oi_calculator.calculate_theoretical_oi(
            spot_price, strikes, volatility, days_to_expiry
        )
        
        # Enhance each option with OI data
        enhanced_data = []
        for option in options_data:
            strike = option['strike']
            option_type = option['option_type'].lower()
            
            # Add OI data
            if strike in oi_data:
                if option_type == 'call':
                    option['open_interest'] = oi_data[strike]['call_oi']
                    option['total_oi'] = oi_data[strike]['total_oi']
                else:
                    option['open_interest'] = oi_data[strike]['put_oi']
                    option['total_oi'] = oi_data[strike]['total_oi']
                
                # Add change in OI (random for demo)
                option['change_in_oi'] = round(option['open_interest'] * (random.random() * 0.4 - 0.2), 2)
                
                # Add volume (typically 10-50% of OI)
                option['volume'] = round(option['open_interest'] * (0.1 + 0.4 * random.random()), 2)
                
                # Add bid-ask spread
                option['bid_price'] = max(0.05, option['theoretical_price'] * 0.98)
                option['ask_price'] = option['theoretical_price'] * 1.02
                
                # Add LTP (Last Traded Price) - close to theoretical
                option['ltp'] = option['theoretical_price'] * (0.95 + 0.1 * random.random())
                option['change'] = option['ltp'] - option['theoretical_price']
                option['change_percent'] = (option['change'] / option['theoretical_price']) * 100 if option['theoretical_price'] > 0 else 0
            
            enhanced_data.append(option)
        
        self.logger.success(f"Enhanced {len(enhanced_data)} options with market data")
        return enhanced_data
    
    def calculate_comprehensive_analytics(self, 
                                        enhanced_data: List[Dict], 
                                        spot_price: float) -> Dict:
        """Calculate comprehensive market analytics"""
        
        self.logger.info("Calculating comprehensive market analytics")
        
        # Separate calls and puts
        calls = [opt for opt in enhanced_data if opt['option_type'].lower() == 'call']
        puts = [opt for opt in enhanced_data if opt['option_type'].lower() == 'put']
        
        # Get unique strikes for OI analysis
        strikes = sorted(list(set([opt['strike'] for opt in enhanced_data])))
        oi_data = {}
        
        # Build OI data structure
        for strike in strikes:
            call_data = next((opt for opt in calls if opt['strike'] == strike), None)
            put_data = next((opt for opt in puts if opt['strike'] == strike), None)
            
            oi_data[strike] = {
                'call_oi': call_data['open_interest'] if call_data else 0,
                'put_oi': put_data['open_interest'] if put_data else 0
            }
        
        # Calculate analytics
        total_call_oi = sum([data['call_oi'] for data in oi_data.values()])
        total_put_oi = sum([data['put_oi'] for data in oi_data.values()])
        
        # Max Pain
        max_pain = self.oi_calculator.calculate_max_pain(oi_data)
        
        # Support & Resistance
        support_levels, resistance_levels = self.oi_calculator.identify_support_resistance(oi_data, spot_price)
        
        # ATM Strike
        atm_strike = min(strikes, key=lambda x: abs(x - spot_price))
        
        # OI Chart Data
        chart_data = self.oi_calculator.generate_oi_chart_data(oi_data)
        
        analytics = {
            'spot_price': spot_price,
            'atm_strike': atm_strike,
            'max_pain_strike': max_pain,
            'total_call_oi': round(total_call_oi, 2),
            'total_put_oi': round(total_put_oi, 2),
            'total_pcr': round(total_put_oi / total_call_oi, 4) if total_call_oi > 0 else 0,
            'support_levels': support_levels,
            'resistance_levels': resistance_levels,
            'oi_chart_data': chart_data,
            'strike_range': {
                'min': min(strikes),
                'max': max(strikes),
                'count': len(strikes)
            }
        }
        
        self.logger.success("Comprehensive analytics calculated successfully")
        return analytics
