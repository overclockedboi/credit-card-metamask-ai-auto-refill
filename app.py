from dotenv import load_dotenv
from fastapi import FastAPI, staticfiles, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.exceptions import HTTPException
from pydantic import BaseModel, validator
import json
import os
import random
import logging
from decimal import Decimal
from mistralai import Mistral
from web3 import Web3

# Load environment variables from .env file
load_dotenv()


# Logger setup
logging.basicConfig(level=logging.INFO)

app = FastAPI()

# Serve static files
app.mount("/static", staticfiles.StaticFiles(directory="static"), name="static")

# Constants
CARD_MIN_THRESHOLD = 100  # $100 minimum threshold
CARD_TARGET_BALANCE = 200  # $200 target balance
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
INFURA_URL = os.getenv("INFURA_URL")
PRICE_FEED_ADDRESS = os.getenv("PRICE_FEED_ADDRESS")
MINIMUM_PROFITABLE_USD = 50  # Minimum USD amount for profitable transaction
GAS_LIMIT = 21000  # Standard ETH transfer gas limit
PROFIT_MARGIN = 1.05  # 5% profit margin requirement

# Initialize Mistral AI and Web3
mistral_client = Mistral(api_key=MISTRAL_API_KEY)
w3 = Web3(Web3.HTTPProvider(INFURA_URL))

# Global state for demo
CURRENT_CARD_BALANCE = 200.00
CURRENT_ETH_BALANCE = 0.2  # Initial ETH balance (approximately $400 at $2000/ETH)

class TransactionRequest(BaseModel):
    amount: Decimal
    currency: str = 'USD'
    wallet_address: str = None

    @validator('amount')
    def amount_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError('Amount must be positive')
        return v

    @validator('currency')
    def currency_must_be_valid(cls, v):
        if v not in ['ETH', 'USD']:
            raise ValueError('Currency must be ETH or USD')
        return v

class TradingSuggestion(BaseModel):
    action: str
    amount: Decimal
    reason: str

class TransactionResult(BaseModel):
    status: str
    amount: float
    tx_hash: str
    new_balance: float
    new_metamask_balance_usd: float
    new_eth_balance: float

async def get_eth_price():
    try:
        # Using Chainlink ETH/USD price feed contract
        abi = [{"inputs":[],"name":"latestRoundData","outputs":[{"internalType":"uint80","name":"roundId","type":"uint80"},{"internalType":"int256","name":"answer","type":"int256"},{"internalType":"uint256","name":"startedAt","type":"uint256"},{"internalType":"uint256","name":"updatedAt","type":"uint256"},{"internalType":"uint80","name":"answeredInRound","type":"uint80"}],"stateMutability":"view","type":"function"}]        
        contract = w3.eth.contract(address=price_feed_address, abi=abi)
        latest_data = contract.functions.latestRoundData().call()
        return float(latest_data[1] / 1e8)  # Price feed returns price with 8 decimals
    except Exception as e:
        logging.error(f"Error getting ETH price: {e}")
        return 2000  # Fallback price

async def get_gas_price():
    try:
        gas_price_wei = w3.eth.gas_price
        gas_price_gwei = w3.from_wei(gas_price_wei, 'gwei')
        return float(gas_price_gwei)
    except Exception as e:
        logging.error(f"Error getting gas price: {e}")
        return 50  # Default to 50 gwei if error

async def calculate_transaction_cost(eth_price):
    try:
        gas_price_gwei = await get_gas_price()
        # Convert all numbers to float to ensure consistent type operations
        gas_price_eth = float(w3.from_wei(w3.to_wei(float(gas_price_gwei), 'gwei'), 'ether'))
        gas_limit = float(GAS_LIMIT)
        eth_price = float(eth_price)
        
        transaction_fee_eth = gas_price_eth * gas_limit
        transaction_fee_usd = transaction_fee_eth * eth_price
        return float(transaction_fee_usd)
    except Exception as e:
        logging.error(f"Error calculating transaction cost: {e}")
        return 5.0  # Default $5 if error

async def calculate_minimum_profitable_amount(eth_price):
    try:
        tx_cost_usd = await calculate_transaction_cost(eth_price)
        # Minimum amount should cover transaction cost plus profit margin
        min_amount = max(MINIMUM_PROFITABLE_USD, tx_cost_usd * PROFIT_MARGIN)
        return round(min_amount, 2)
    except Exception as e:
        logging.error(f"Error calculating minimum profitable amount: {e}")
        return MINIMUM_PROFITABLE_USD

async def get_ai_trading_suggestion(balance_eth, eth_price):
    try:
        # Convert values to float for calculations
        balance_eth = float(balance_eth)
        eth_price = float(eth_price)
        total_value = balance_eth * eth_price
        
        # Prepare context for AI
        prompt = f"""As a crypto trading expert, analyze the following portfolio and market conditions:

Portfolio Status:
- Current ETH Balance: {balance_eth:.4f} ETH
- Current ETH Price: ${eth_price:.2f}
- Total Portfolio Value: ${total_value:.2f}

Based on current market conditions, provide a trading recommendation in this exact format:
ACTION: [BUY/SELL/HOLD]
AMOUNT: [number] ETH
REASON: [your analysis]"""

        # Send request to Mistral API
        response = mistral_client.chat.complete(
            model="mistral-small",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
            response_format={
          "type": "json_object",
      }, 
        )
        print(f"AI Suggestion: {response}")  # Debugging output
        # Get the suggestion text from the response
        suggestion_text = response.choices[0].message.content

        
        
        # Parse the structured response
        lines = suggestion_text.strip().split('\n')
        action = "hold"
        amount = 0.0
        reason = "Unable to parse AI suggestion"
        
        try:
            # Extract action, amount, and reason from the structured response
            for line in lines:
                if line.startswith('ACTION:'):
                    action = line.replace('ACTION:', '').strip().lower()
                elif line.startswith('AMOUNT:'):
                    amount_str = line.replace('AMOUNT:', '').strip().lower()
                    if 'eth' in amount_str:
                        amount_str = amount_str.replace('eth', '').strip()
                    amount = float(amount_str)
                elif line.startswith('REASON:'):
                    reason = line.replace('REASON:', '').strip()
            
            # Validate and adjust the suggestion
            if action == 'buy':
                # Limit buy amount to either 0.5 ETH or 50% of current balance
                amount = min(0.5, balance_eth * 0.5)
            elif action == 'sell':
                # Limit sell amount to 50% of current balance
                amount = min(amount, balance_eth * 0.5)
            else:
                action = 'hold'
                amount = 0.0
            
            # Ensure amount is always positive and rounded
            amount = round(abs(float(amount)), 4)
            
        except Exception as e:
            logging.error(f"Error parsing AI suggestion: {e}")
            action = "hold"
            amount = 0.0
            reason = f"Error parsing AI suggestion: {str(e)}"

        return {
            "action": action,
            "amount": amount,
            "reason": reason
        }
    except Exception as e:
        logging.error(f"Error getting AI trading suggestion: {e}")
        return {
            "action": "hold",
            "amount": 0.0,
            "reason": f"Unable to get AI suggestion: {str(e)}"
        }

@app.get("/", response_class=HTMLResponse)
def read_root():
    with open("static/index.html", "r") as f:
        return f.read()

@app.get("/status")
async def status(request: Request, wallet_address: str = None):
    try:
        global CURRENT_ETH_BALANCE
        card_balance = get_card_balance()
        eth_price = await get_eth_price()
        gas_price = await get_gas_price()
        min_profitable_amount = await calculate_minimum_profitable_amount(eth_price)
        
        eth_balance = CURRENT_ETH_BALANCE  # Use global ETH balance instead of random
        metamask_balance_usd = eth_balance * eth_price
        trading_suggestion = await get_ai_trading_suggestion(eth_balance, eth_price)
        
        decision = check_card_balance(card_balance)
        
        return JSONResponse(content={
            "card_balance": card_balance,
            "eth_balance": eth_balance,
            "eth_price": eth_price,
            "gas_price_gwei": gas_price,
            "min_profitable_amount": min_profitable_amount,
            "metamask_balance_usd": metamask_balance_usd,
            "trading_suggestion": trading_suggestion,
            "decision": decision
        }, status_code=200)
    except Exception as e:
        logging.error(f"Error getting status: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@app.post("/use-card")
async def use_card(request: TransactionRequest):
    try:
        global CURRENT_CARD_BALANCE, CURRENT_ETH_BALANCE
        amount_usd = float(request.amount)
        eth_price = float(await get_eth_price())
        min_profitable_amount = await calculate_minimum_profitable_amount(eth_price)
        
        # Check if withdrawal amount is profitable
        if amount_usd < min_profitable_amount:
            raise HTTPException(
                status_code=400, 
                detail=f"Amount too low for profitable transaction. Minimum amount: ${min_profitable_amount:.2f}"
            )
        
        if CURRENT_CARD_BALANCE < amount_usd:
            raise HTTPException(status_code=400, detail="Insufficient card balance")
        
        # Simulate card usage and update balance
        tx_hash = simulate_card_transaction(amount_usd)
        CURRENT_CARD_BALANCE = float(CURRENT_CARD_BALANCE) - amount_usd
        
        # Check if we need to top up after the transaction
        if CURRENT_CARD_BALANCE < CARD_MIN_THRESHOLD:
            # Calculate optimal top-up amount based on ETH price and gas fees
            min_topup = max(
                CARD_TARGET_BALANCE - CURRENT_CARD_BALANCE,
                float(await calculate_minimum_profitable_amount(eth_price)) * 2  # 2x minimum profitable amount
            )
            
            await auto_topup(min_topup)
            CURRENT_CARD_BALANCE = float(CURRENT_CARD_BALANCE) + min_topup
            
            # Calculate and update MetaMask balance after top-up
            topup_eth_amount = min_topup / eth_price
            CURRENT_ETH_BALANCE = float(CURRENT_ETH_BALANCE) - topup_eth_amount
        
        metamask_balance_usd = float(CURRENT_ETH_BALANCE) * eth_price
        
        return JSONResponse(content={
            "status": "Card Transaction Successful",
            "amount": float(amount_usd),
            "tx_hash": tx_hash,
            "new_balance": float(CURRENT_CARD_BALANCE),
            "new_metamask_balance_usd": float(metamask_balance_usd),
            "new_eth_balance": float(CURRENT_ETH_BALANCE),
            "min_profitable_amount": float(min_profitable_amount)
        }, status_code=200)
    except Exception as e:
        logging.error(f"Error processing card transaction: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def auto_sell_eth_for_card(target_usd_amount):
    try:
        eth_price = await get_eth_price()
        gas_cost = await calculate_transaction_cost(eth_price)
        
        # Add profit margin to ensure profitable trade
        required_amount = target_usd_amount * PROFIT_MARGIN + gas_cost
        eth_amount = required_amount / eth_price
        
        # Check if we have enough ETH
        if eth_amount > CURRENT_ETH_BALANCE:
            raise ValueError(f"Insufficient ETH balance. Need {eth_amount:.4f} ETH but have {CURRENT_ETH_BALANCE:.4f} ETH")
            
        # Get AI trading suggestion before selling
        suggestion = await get_ai_trading_suggestion(CURRENT_ETH_BALANCE, eth_price)
        
        # Only proceed if AI doesn't strongly recommend holding or buying
        if suggestion["action"] == "hold" and float(suggestion["amount"]) > eth_amount:
            raise ValueError(f"AI suggests holding: {suggestion['reason']}")
            
        # Simulate selling ETH
        tx_hash = simulate_eth_sale(eth_amount)
        
        return {
            "status": "success",
            "eth_sold": eth_amount,
            "usd_received": target_usd_amount,
            "tx_hash": tx_hash,
            "ai_suggestion": suggestion
        }
    except Exception as e:
        logging.error(f"Error in auto sell ETH: {e}")
        raise

def simulate_eth_sale(eth_amount):
    try:
        global CURRENT_ETH_BALANCE
        CURRENT_ETH_BALANCE -= float(eth_amount)
        fake_tx_hash = "0x" + os.urandom(32).hex()
        logging.info(f"Simulated ETH sale: {eth_amount:.4f} ETH, tx: {fake_tx_hash}")
        return fake_tx_hash
    except Exception as e:
        logging.error(f"Error simulating ETH sale: {e}")
        raise

async def auto_topup(amount_usd):
    try:
        # First try to sell ETH for the required amount
        sale_result = await auto_sell_eth_for_card(amount_usd)
        
        # If successful, simulate adding funds to card
        if sale_result["status"] == "success":
            global CURRENT_CARD_BALANCE
            CURRENT_CARD_BALANCE += float(amount_usd)
            
            return {
                "status": "success",
                "amount_added": amount_usd,
                "eth_sold": sale_result["eth_sold"],
                "tx_hash": sale_result["tx_hash"],
                "ai_suggestion": sale_result["ai_suggestion"]
            }
    except Exception as e:
        logging.error(f"Error in auto top-up: {e}")
        raise

def get_card_balance():
    global CURRENT_CARD_BALANCE
    return CURRENT_CARD_BALANCE

def simulate_card_transaction(amount_usd):
    try:
        fake_tx_hash = "0x" + os.urandom(32).hex()
        logging.info(f"Simulated card transaction: ${amount_usd}, tx: {fake_tx_hash}")
        return fake_tx_hash
    except Exception as e:
        logging.error(f"Error simulating card transaction: {e}")
        return None

def check_card_balance(balance):
    try:
        if balance < CARD_MIN_THRESHOLD:
            topup_amount = CARD_TARGET_BALANCE - balance
            return {
                "action": "top-up",
                "amount": round(topup_amount, 2),
                "reason": f"Balance ${balance} below minimum threshold ${CARD_MIN_THRESHOLD}"
            }
        return {
            "action": "skip",
            "amount": 0,
            "reason": f"Balance ${balance} above minimum threshold ${CARD_MIN_THRESHOLD}"
        }
    except Exception as e:
        logging.error(f"Error checking card balance: {e}")
        return None
