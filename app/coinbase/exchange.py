import ccxt.async_support as ccxt  # MUST use async_support for async functions
import asyncio

async def validate_coinbase_api(api_key: str, api_secret: str, passphrase: str = None):
    client = None
    try:
        # Configuration for Coinbase Advanced
        config = {
            'apiKey': api_key,
            'secret': api_secret
           
        }
        
        # Add passphrase ONLY if it's a Legacy Key (short secret string)
        # If using Cloud/CDP keys (long PEM secret), do not add password.
 
        client = ccxt.coinbase.requiredCredentials(config)

        # !!! CRITICAL FIX: You must use 'await' here !!!
        balance = await client.fetch_balance()
        
        print("✅ Connection Successful!")
        return True

    except ccxt.AuthenticationError as e:
        print(f"❌ Auth Error: Incorrect Key, Secret, or Passphrase. Details: {e}")
        return False
    except Exception as e:
        print(f"❌ Connection Error: {str(e)}")
        return False
    finally:
        # !!! CRITICAL FIX: You must close the client connection !!!
        if client:
            await client.close()