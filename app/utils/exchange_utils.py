from app.constants.exchange_constants import EXCHANGE_CONSTANTS


def get_exchange_by_str(exchange_str: str):
    for exchange in EXCHANGE_CONSTANTS:
        if exchange["exchange_str"] == exchange_str:
            return exchange
    return None


def get_exchange_by_name(exchange_name: str):
    for exchange in EXCHANGE_CONSTANTS:
        if exchange["exchange_name"] == exchange_name:
            return exchange
    return None
