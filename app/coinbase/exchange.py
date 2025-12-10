import ccxt.async_support as ccxt


def clean_private_key(pem: str) -> str:
    return pem.replace("\\n", "\n").strip()


async def validate_coinbase_api(api_key: str, api_secret: str, passphrase: str) -> bool:
    private_key = clean_private_key(api_secret)
    print("Validating Coinbase API credentials...", api_key, private_key)

    try:
        exchange = ccxt.coinbase({
            "apiKey": api_key,
            "secret": private_key,
            "enableRateLimit": True,
        })
        exchange.has["fetchCurrencies"] = False
        # If authentication fails, this call will raise an exception
        accounts = await exchange.v3PrivateGetBrokerageAccounts()
        print("Accounts:", accounts)
        if "accounts" not in accounts:
            return False  # Auth FAILED 

        return True   # Auth SUCCESS

    except Exception:
        return False  # Auth FAILED

    finally:
        await exchange.close()
