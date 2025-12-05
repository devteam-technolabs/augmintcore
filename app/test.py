import asyncio
import ccxt.async_support as ccxt  # <--- NOTE: async_support

async def test_connection():
    # REPLACE THESE WITH YOUR REAL CREDENTIALS
    API_KEY = "db11a850-ce66-4149-8492-cf7dc147756d"
    API_SECRET = "reZCOPSGEXwrgjUTFMSxS0veRoDx38mxA/zUeixLOLA+ibnkBbNvoPeVke19PSYKpDhaB7Tv0BlvHod0J2yjpg=="  
 

    try:
        print("1. Initializing Client...")
        # CORRECT SYNTAX: Pass the dictionary directly to the constructor
        exchange = ccxt.coinbase({
            'apiKey': API_KEY,
            'secret': API_SECRET,
            # 'password': 'your_passphrase', # ONLY if using old Legacy keys (see below)
        })

        print("2. Fetching balance...")
        balance = await exchange.fetch_balance()
        
        print("✅ SUCCESS! Balance fetched.")
        print(balance)

    except ccxt.AuthenticationError as e:
        print(f"❌ AUTH ERROR: {e}")
    except Exception as e:
        print(f"❌ ERROR: {e}")
    finally:
        if 'exchange' in locals():
            await exchange.close()
            print("3. Connection closed.")

if __name__ == "__main__":
    asyncio.run(test_connection())