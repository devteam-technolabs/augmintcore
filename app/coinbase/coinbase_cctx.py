# import asyncio

# import ccxt.async_support as ccxt_async


# def clean_private_key(pem: str) -> str:
#     return pem.replace("\\n", "\n").replace("\r", "").strip()


# async def get_working_coinbase_exchange(
#     api_key: str,
#     api_secret: str,
#     passphrase: str | None = None,
# ):

#     try:
#         private_key = clean_private_key(api_secret)

#         exchange = ccxt_async.coinbaseadvanced(
#             {
#                 "apiKey": api_key.strip(),
#                 "secret": private_key,
#                 "enableRateLimit": True,
#                 # Optional: Disable fetchBalance warning if any
#                 "options": {
#                     "adjustForTimeDifference": True,
#                     "createMarketBuyOrderRequiresPrice": True,  # Set default
#                 },
#             }
#         )

#         # Retry mechanism to handle Nonce/Auth collisions & Time Skew
#         for i in range(3):
#             try:
#                 # Use fetch_accounts instead of fetch_balance to avoid transaction_summary 401
#                 accounts = await exchange.fetch_accounts()

#                 # Transform to CCXT balance structure manually
#                 balance = {"free": {}, "total": {}, "used": {}, "info": accounts}
#                 for account in accounts:
#                     currency_code = account["code"]
#                     # 'free' might be available, usually fetch_accounts returns 'free' or 'total'
#                     # Let's inspect typical CCXT fetch_accounts result:
#                     # {'id': '...', 'code': 'BTC', 'info': {...}, 'free': 0.1, 'total': 0.1, ...}
#                     # Usually it parses 'free' and 'total' if available.
#                     # Looking at user log: {'id': '...', 'info': {'available_balance': {'value': '...'}}}

#                     # We can use the 'info' -> 'available_balance' -> 'value'
#                     try:
#                         free = float(account["info"]["available_balance"]["value"])
#                         total = free  # Assuming hold is negligible or not parsed here
#                         if (
#                             "hold" in account["info"]
#                             and "value" in account["info"]["hold"]
#                         ):
#                             total += float(account["info"]["hold"]["value"])

#                         balance[currency_code] = {
#                             "free": free,
#                             "used": total - free,
#                             "total": total,
#                         }
#                         balance["free"][currency_code] = free
#                         balance["total"][currency_code] = total
#                         balance["used"][currency_code] = total - free
#                     except (KeyError, ValueError, TypeError):
#                         pass

#                 exchange._cached_validation_balance = balance
#                 return exchange

#             except (ccxt_async.AuthenticationError, ccxt_async.ExchangeError) as e:
#                 print(f"⚠️ attempt {i+1} failed ({e})")
#                 if i < 2:  # Try 3 times (0, 1, 2)
#                     print(f"⏰ Syncing time difference...")
#                     try:
#                         await exchange.load_time_difference()
#                     except Exception:
#                         pass  # Ignore if time sync fails, retry anyway
#                     await asyncio.sleep(1.0)
#                     continue
#                 # If v3 fails, we might try v2 ONLY if passphrase exists
#                 raise e

#     except Exception as e:
#         print(f"⚠️ coinbaseadvanced failed: {e}")
#         try:
#             await exchange.close()
#         except Exception:
#             pass

#     # Only try v2 (coinbaseexchange) if passphrase is provided
#     if passphrase:
#         try:
#             exchange = ccxt_async.coinbaseexchange(
#                 {
#                     "apiKey": api_key.strip(),
#                     "secret": api_secret.strip(),
#                     "password": passphrase.strip(),
#                     "enableRateLimit": True,
#                 }
#             )
#             exchange.set_sandbox_mode(True)
#             balance = await exchange.fetch_balance()
#             exchange._cached_validation_balance = balance
#             return exchange

#         except Exception as e:
#             print(f"❌ coinbaseexchange failed: {e}")
#             try:
#                 await exchange.close()
#             except Exception:
#                 pass

#     return None


import asyncio
import traceback
import ccxt.async_support as ccxt_async


def clean_private_key(pem: str) -> str:
    print("🧹 Cleaning private key...")
    cleaned = pem.replace("\\n", "\n").replace("\r", "").strip()
    print("🧹 Private key cleaned")
    return cleaned


async def get_working_coinbase_exchange(
    api_key: str,
    api_secret: str,
    passphrase: str | None = None,
):

    print("\n==============================")
    print("🚀 Starting Coinbase Exchange Initialization")
    print("API KEY:", api_key[:8], "...")
    print("Passphrase exists:", bool(passphrase))
    print("==============================")

    exchange = None

    try:
        print("🔑 Cleaning API secret...")
        private_key = clean_private_key(api_secret)

        print("🌐 Creating coinbaseadvanced exchange instance")

        exchange = ccxt_async.coinbaseadvanced(
            {
                "apiKey": api_key.strip(),
                "secret": private_key,
                "enableRateLimit": True,
                "options": {
                    "adjustForTimeDifference": True,
                    "createMarketBuyOrderRequiresPrice": True,
                },
            }
        )

        print("✅ Exchange instance created")

        # Retry mechanism
        for i in range(3):

            try:
                print(f"\n🔄 Attempt {i+1} to fetch accounts")

                print("📡 Sending request → fetch_accounts()")
                accounts = await exchange.fetch_accounts()

                print("✅ Accounts received")
                print("📦 Number of accounts:", len(accounts))

                # Transform accounts into balance structure
                balance = {"free": {}, "total": {}, "used": {}, "info": accounts}

                for account in accounts:

                    print("🔍 Processing account:", account.get("code"))

                    currency_code = account["code"]

                    try:
                        free = float(account["info"]["available_balance"]["value"])
                        total = free

                        if (
                            "hold" in account["info"]
                            and "value" in account["info"]["hold"]
                        ):
                            total += float(account["info"]["hold"]["value"])

                        balance[currency_code] = {
                            "free": free,
                            "used": total - free,
                            "total": total,
                        }

                        balance["free"][currency_code] = free
                        balance["total"][currency_code] = total
                        balance["used"][currency_code] = total - free

                        print(
                            f"💰 {currency_code} → free={free}, total={total}"
                        )

                    except Exception as e:
                        print(
                            f"⚠️ Failed parsing account {currency_code}: {e}"
                        )

                print("✅ Balance structure created")

                exchange._cached_validation_balance = balance

                print("🎉 Coinbase exchange authenticated successfully")

                return exchange

            except (ccxt_async.AuthenticationError, ccxt_async.ExchangeError) as e:

                print(f"\n⚠️ Attempt {i+1} failed")
                print("ERROR:", repr(e))

                if i < 2:
                    print("⏰ Syncing time difference...")

                    try:
                        await exchange.load_time_difference()
                        print("✅ Time synced")
                    except Exception as time_error:
                        print("⚠️ Time sync failed:", time_error)

                    print("⏳ Waiting 1 second before retry")
                    await asyncio.sleep(1.0)
                    continue

                print("❌ All attempts failed")
                raise e

    except Exception as e:

        print("\n🔥 coinbaseadvanced initialization FAILED")
        print("ERROR:", repr(e))
        traceback.print_exc()

        if exchange:
            print("🔌 Closing failed exchange instance")
            try:
                await exchange.close()
            except Exception:
                pass

    # =========================
    # FALLBACK → Coinbase Pro
    # =========================

    if passphrase:

        print("\n🔁 Attempting fallback → coinbaseexchange")

        try:

            exchange = ccxt_async.coinbaseexchange(
                {
                    "apiKey": api_key.strip(),
                    "secret": api_secret.strip(),
                    "password": passphrase.strip(),
                    "enableRateLimit": True,
                }
            )

            print("🌐 Coinbase Exchange instance created")

            exchange.set_sandbox_mode(True)
            print("🧪 Sandbox mode enabled")

            print("📡 Fetching balance (fallback)")
            balance = await exchange.fetch_balance()

            print("✅ Balance fetched via fallback")

            exchange._cached_validation_balance = balance

            return exchange

        except Exception as e:

            print("\n❌ coinbaseexchange fallback FAILED")
            print("ERROR:", repr(e))
            traceback.print_exc()

            if exchange:
                try:
                    await exchange.close()
                except Exception:
                    pass

    print("\n🚫 All authentication attempts failed")

    return None