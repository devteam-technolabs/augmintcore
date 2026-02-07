import ccxt.async_support as ccxt_async
import asyncio

def clean_private_key(pem: str) -> str:
    return pem.replace("\\n", "\n").strip()

async def get_working_coinbase_exchange(
    api_key: str,
    api_secret: str,
    passphrase: str | None = None,
):
    
    try:
        private_key = clean_private_key(api_secret)
        print("private_key:", private_key)
        exchange = ccxt_async.coinbaseadvanced({
            "apiKey": api_key,
            "secret": private_key,
            "enableRateLimit": True

        })
        exchange.options['adjustForTimeDifference'] = True 
        
        # Retry mechanism to handle Nonce/Auth collisions
        for i in range(2):
            try:
                balance = await exchange.fetch_balance()
                exchange._cached_validation_balance = balance
                return exchange
            except (ccxt_async.AuthenticationError, ccxt_async.ExchangeError) as e:
                print(f"⚠️ attempt {i+1} failed ({e})")
                if i == 0:
                    await asyncio.sleep(1.0)
                    continue
                raise e # Re-raise on final attempt


    except Exception as e:
        print(f"⚠️ coinbaseadvanced failed: {e}")
        try:
            await exchange.close()
        except Exception:
            pass

    try:
        exchange = ccxt_async.coinbaseexchange({
            "apiKey": api_key,
            "secret": api_secret,
            "password": passphrase,
            "enableRateLimit": True,
        })
        exchange.set_sandbox_mode(True)
        balance = await exchange.fetch_balance()
        exchange._cached_validation_balance = balance
        return exchange

    except Exception as e:
        print(f"❌ coinbaseexchange failed: {e}")
        try:
            await exchange.close()
        except Exception:
            pass

    return False
