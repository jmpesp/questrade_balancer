#!/usr/bin/env python

import sys
import requests
import json


# usage:
#
# ./balance.py <optional amount to spend>
#
# If you don't supply an amount to spend, this script will attempt to spend
# your entire "buying power".


class QuestradeBalancer(object):
    def __init__(self):
        with open("token") as fp:
            self.refresh_token = fp.read().strip()

        self.session = requests.session()

        # each time you run balance.py, it will get a new token and save it
        url = "".join([
            "https://login.questrade.com/oauth2/",
            "token?grant_type=refresh_token",
            "&refresh_token={}".format(self.refresh_token),
            ])

        resp = self.session.get(url)
        resp.raise_for_status()

        #print(requests.utils.dict_from_cookiejar(self.session.cookies))

        self.login_creds = resp.json()

        with open("token", "w") as fp:
            fp.write(self.login_creds["refresh_token"].strip())

        # {
        #     'access_token': '',
        #     'expires_in': 1800,
        #     'token_type': 'Bearer',
        #     'api_server': 'https://api07.iq.questrade.com/',
        #     'refresh_token': ''
        # }

        self.headers = {
            "Authorization": "{} {}".format(self.login_creds["token_type"],
                                            self.login_creds["access_token"]),
            "Host": self.login_creds["api_server"],
            #"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Gecko/20100101 Firefox/60.0",
            #"Accept": "application/json",
            #"Accept-Encoding": "gzip, deflate, br",
            #"Accept-Language": "en-US,en;q=0.5",
        }

        if self.login_creds["api_server"][-1] == '/':
            self.login_creds["api_server"] = \
                self.login_creds["api_server"][:-1]

    def get(self, url, params={}):
        resp = self.session.get(self.login_creds["api_server"] + url,
                                headers=self.headers,
                                params=params)
        resp.raise_for_status()
        return resp.json()

    def post(self, url, params):
        resp = self.session.post(self.login_creds["api_server"] + url,
                                 headers=self.headers,
                                 params=params)
        resp.raise_for_status()
        return resp.json()

    def buy(self, account_id, symbol, quantity):
        # Questrade doesn't allow buying via this API anymore!
        params = {
            'symbolId': symbol,
            'quantity': quantity,
            'orderType': 'Market',
            'action': 'Buy',
            'timeInForce': 'Day',
        }
        #print json.dumps(params, indent=2)
        return self.post("/v1/accounts/{}/orders".format(account_id),
                         params)

    def get_symbol_price(self, symbol):
        params = {
            "prefix": symbol,
        }
        resp = self.get("/v1/symbols/search", params)

        assert len(resp["symbols"]) == 1

        symbolId = resp["symbols"][0]["symbolId"]

        resp = self.get("/v1/markets/quotes/{}".format(symbolId))

        assert len(resp["quotes"]) == 1

        return resp["quotes"][0]["bidPrice"]

    def balance(self):
        """Get portfolio, and buy / sell to maintain the allocations."""

        # find account
        accounts = self.get("/v1/accounts")["accounts"]

        # {
        #   "userId": <number>,
        #   "accounts": [
        #     {
        #       "status": "Active",
        #       "isBilling": true,
        #       "number": "<number>",
        #       "isPrimary": true,
        #       "type": "TFSA",
        #       "clientAccountType": "Individual"
        #     }
        #   ]
        # }

        with open("portfolio.json") as fp:
            portfolio = json.load(fp)

        # validate portfolio.json
        total_percent = 0
        for symbol in portfolio["symbols"]:
            percent = portfolio["symbols"][symbol]["percent"]
            total_percent += percent

        if total_percent > 1.0:
            print("Cannot have total portfolio percent over 1!")
            exit(1)

        # the total percent can be less than 1 (100%), the rest will be kept
        # as cash.

        if len(accounts) != 1:
            raise RuntimeError("more than 1 account seen!")

        account = accounts[0]

        # get positions
        positions = self.get(
            "/v1/accounts/{}/positions".format(account["number"])
        )["positions"]

        # {
        #   "positions": [
        #     {
        #       "symbol": "THI.TO",
        #       "symbolId": 38738,
        #       "openQuantity": 100,
        #       "currentMarketValue": 6017,
        #       "currentPrice": 60.17,
        #       "averageEntryPrice": 60.23,
        #       "closedPnl": 0,
        #       "openPnl": -6,
        #       "totalCost": false,
        #       "isRealTime": "Individual",
        #       "isUnderReorg": false
        #     }
        #   ]
        # }

        # get balances
        balances = self.get(
            "/v1/accounts/{}/balances".format(account["number"])
        )

        # note one account is assumed here.
        buying_power = [x["buyingPower"]
                        for x in balances["perCurrencyBalances"]
                        if x["currency"] == "CAD"][0]

        print("Total buying power:", buying_power)

        if len(sys.argv) > 1:
            buying_power = int(sys.argv[1])
            print("buying power set to", buying_power)

        total_position_value = 0
        total_profit_and_losses = 0
        for position in positions:
            if position["currentMarketValue"]:
                total_position_value += position["currentMarketValue"]
            if position["openPnl"]:
                total_profit_and_losses += position["openPnl"]

        print("Total position value:", total_position_value)
        print("Total profits / losses:", total_profit_and_losses)

        print("")

        total_spent = 0
        total_sold = 0

        # iterate over held positions, and buy or sell to bring back to portfolio
        # percentages.
        for position in positions:
            if position["currentMarketValue"]:
                if position["symbol"] not in list(portfolio["symbols"].keys()):
                    print(position["symbol"], "held but not in portfolio.json!")
                    continue

                target_percent = portfolio["symbols"][position["symbol"]]["percent"]

                print(position["symbol"], "at", position["currentPrice"])

                target_value = (total_position_value+buying_power)*target_percent
                actual_value = position["currentMarketValue"]

                print("value: target {} actual {}".format(target_value,
                                                          actual_value))

                print("value difference: {}".format(actual_value - target_value))

                if target_value > actual_value:
                    buy_order = (target_value-actual_value)/position["currentPrice"]
                    buy_order = int(buy_order)
                    if buy_order != 0:
                        print("could buy", buy_order)
                        #try:
                        #    self.buy(account["number"],
                        #             position["symbolId"],
                        #             buy_order)
                        #except Exception as e:
                        #    print("could not buy! {}".format(e))

                        total_spent += position["currentPrice"] * buy_order

                if target_value < actual_value:
                    sell_order = (actual_value-target_value)/position["currentPrice"]
                    sell_order = int(sell_order)
                    if sell_order != 0:
                        print("could sell", sell_order)
                        total_sold += sell_order * position["currentPrice"]

                print("")

        # now, for positions not held yet
        for symbol in list(portfolio["symbols"].keys()):
            if symbol not in [x["symbol"] for x in positions]:
                print("{} is new!".format(symbol))

                price = self.get_symbol_price(symbol)
                print("price is {}".format(price))

                target_percent = portfolio["symbols"][symbol]["percent"]

                target_value = (total_position_value+buying_power)*target_percent

                buy_order = int(target_value/price)

                print("could buy {}".format(buy_order))

        print("total spent: {}".format(total_spent))
        print("total sold: {}".format(total_sold))
        print("total diff: {}".format(total_sold - total_spent))


if __name__ == "__main__":
    qb = QuestradeBalancer()
    qb.balance()

