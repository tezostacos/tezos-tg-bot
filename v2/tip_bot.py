import json
import threading
import time

import schedule
from telegram import Bot
from telegram.ext import CommandHandler
import requests
import subprocess
from pytezos import pytezos
from pymongo import MongoClient
from telegram.ext import Updater
from decimal import Decimal
import traceback

with open('services.json') as conf_file:
    conf = json.load(conf_file)
    connectionString = conf['mongo']['connectionString']
    bot_token = conf['telegram_bot']['bot_token']
    constant_url = conf['constant_url']
    node_settings = conf['node_settings']
    greeting_msg = conf['greeting_msg']
    machine = conf['bot_username']
    contract_address = conf['contract']
    admin_secret = conf['admin_secret']
    node_url = conf['node_url']

print()

updater = Updater(token=bot_token)
dispatcher = updater.dispatcher

import logging

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO)


class TipBot:

    def __init__(self):
        client = MongoClient(connectionString)
        db = client.get_default_database()
        self.c_users = db['Users']
        self.c_stats = db['Stats']

        self.bot = Bot(token=bot_token)

        pz = pytezos.using(shell=node_url, key=admin_secret)
        self.ci = pz.contract(contract_address)

        self.update_stats()
        self.update_accounts()
        schedule.every(30).seconds.do(self.update_accounts)
        schedule.every(1).minute.do(self.update_stats)
        threading.Thread(target=self.pending_tasks).start()

    def pending_tasks(self):
        while True:
            try:
                schedule.run_pending()
                time.sleep(5)
            except Exception as exc:
                print(exc)
                time.sleep(5)

    def update_stats(self):
        self.update_tzstats()
        self.update_cg_data()

    def update_cg_data(self):
        try:
            response = requests.get("https://api.coingecko.com/api/v3/coins/tezos").json()

            price_usd = '{0:,.2f}'.format(response['market_data']['current_price']['usd'])
            price_btc = '{0:,.8f}'.format(response['market_data']['current_price']['btc'])
            volume = '{0:,.2f}'.format(response['market_data']['total_volume']['usd'])

            self.c_stats.update_one(
                {"_id": "coingecko"},
                {"$set": {
                    "price_usd": price_usd,
                    "price_btc": price_btc,
                    "volume": volume,
                }}, upsert=True
            )
        except Exception as exc:
            print(exc)
            traceback.print_exc()

    def update_tzstats(self):
        try:
            response = requests.get("https://api.tzstats.com/explorer/tip").json()

            total_accounts = response['total_accounts']
            accounts_30d = response['new_accounts_30d']
            active_bakers = response['roll_owners']
            delegators = response['delegators']
            total = int(response['supply']['total'])
            staking = int(response['supply']['staking'])
            unclaimed = int(response['supply']['unclaimed'])
            circulating = int(response['supply']['circulating'])
            staking_perc = "{0:.2f}".format(float(staking) / float(total) * 100)

            self.c_stats.update_one(
                {"_id": "tzstats"},
                {"$set": {
                    "total_accounts": total_accounts,
                    "accounts_30d": accounts_30d,
                    "active_bakers": active_bakers,
                    "delegators": delegators,
                    "staking": staking,
                    "staking_perc": staking_perc,
                    "unclaimed": unclaimed,
                    "circulating": circulating
                }}, upsert=True
            )
        except Exception as exc:
            print(exc)
            traceback.print_exc()

    def update_accounts(self):
        try:
            storage = self.ci.storage()
            print(storage)
            for _username in list(storage['accounts'].keys()):
                try:
                    _user = self.c_users.find_one({"username": _username})
                    if _user is not None:
                        last_balance = _user['balance']
                    else:
                        last_balance = 0

                    self.c_users.update_one(
                        {"username": _username},
                        {"$set": {
                            "username": _username,
                            "balance": str(storage['accounts'][_username])
                        }}
                    )

                    if float(last_balance) < float(str(storage['accounts'][_username])) and _user is not None:
                        self.bot.send_message(
                            chat_id=_user['_id'],
                            text="<b>Your balance has been recharged. New balance is %s XTZ</b>" % storage['accounts'][
                                _username],
                            parse_mode='HTML'
                        )
                    elif float(last_balance) > float(str(storage['accounts'][_username])) and _user is not None:
                        self.bot.send_message(
                            chat_id=_user['_id'],
                            text="<b>You successfully withdrew/tip %s XTZ. New balance is %s XTZ</b>" % (
                                "{0:.4f}".format(float(last_balance) - float(storage['accounts'][_username])),
                                storage['accounts'][_username]),
                            parse_mode='HTML'
                        )
                except Exception as exc:
                    print(exc)
                    traceback.print_exc()

        except Exception as exc:
            print(exc)
            traceback.print_exc()

    def commands(self, bot, update):
        bot.send_message(chat_id=update.message.chat_id,
                         text="Initiating commands /tip & /withdraw have a specfic format,\n use them like so:" +
                              "\n \n Parameters: \n <user> = target user to tip \n <amount> = amount of reddcoin to utilise \n <address> = reddcoin address to withdraw to \n \n Tipping format: \n /tip <user> <amount> \n \n Withdrawing format: \n /withdraw <address> <amount>")

    def help(self, bot, update):
        bot.send_message(chat_id=update.message.chat_id,
                         text="The following commands are at your disposal: /hi , /commands , /deposit , /tip , /withdraw , /price , /marketcap or /balance")

    def tacos(self, bot, update):
        tzstats_data = self.c_stats.find_one({"_id": "tzstats"})
        cg_data = self.c_stats.find_one({"_id": "coingecko"})

        text = "<b>Price:</b>: $%s (%s BTC)\n" \
               "<b>Volume:</b> $%s\n" \
               "<b>Total Accounts:</b> %s\n" \
               "<b>30d Accounts:</b> %s\n" \
               "<b>Active Bakers:</b> %s\n" \
               "<b>Delegators:</b> %s\n" \
               "<b>Staking:</b> %s XTZ (%s%%)\n" \
               "<b>Unclaimed:</b> %s XTZ\n" \
               "<b>Circulating:</b> %s XTZ\n" % (
                   cg_data['price_usd'], cg_data['price_btc'],
                   cg_data['volume'],
                   tzstats_data['total_accounts'],
                   tzstats_data['accounts_30d'],
                   tzstats_data['active_bakers'],
                   tzstats_data['delegators'],
                   tzstats_data['staking'],
                   tzstats_data['staking_perc'],
                   tzstats_data['unclaimed'],
                   tzstats_data['circulating']
               )

        bot.send_message(
            chat_id=update.message.chat_id,
            text=text,
            parse_mode='HTML'
        )

    def deposit(self, bot, update):
        user = update.message.from_user.username
        bot.send_message(
            chat_id=update.message.chat_id,
            text='<b>To Deposit XTZ to Tezos Tacos tip bot use "deposit" endpoint with string argument</b>\n'
                 '<b>Example of cmd in cli wallet:</b>\n<code>tezos-client -A teznode.letzbake.com -S -P 443 transfer 0.1 from alias to {0} --entrypoint "deposit" --arg '"{1}"' -D</code>'.format(
                contract_address, user),
            parse_mode="HTML"

        )

    def tip(self, bot, update):
        user = update.message.from_user.username
        target = update.message.text[5:]
        amount = target.split(" ")[1]
        target = target.split(" ")[0]
        if self.check_user_existence(bot, user, update):
            if target == machine:
                bot.send_message(chat_id=update.message.chat_id, text="HODL.")
            elif "@" in target:
                target = target[1:]
                storage = self.ci.storage()

                _user = self.c_users.find_one({"username": user})
                balance = float(_user['balance'])
                amount = float(amount)

                if balance < amount:
                    bot.send_message(
                        chat_id=update.message.chat_id,
                        text="@{0} you have insufficent funds.".format(user))
                elif target == user:
                    bot.send_message(
                        chat_id=update.message.chat_id,
                        text="You can't tip yourself silly.")
                else:
                    print("Sending tip from {0} to {1} with {2} amount".format(user, target, amount))
                    if self._tip(user, target, str(amount)):
                        bot.send_message(
                            chat_id=update.message.chat_id,
                            text="You're successfully sent a tip to @{0} with {1} XTZ".format(target, amount))
            else:
                bot.send_message(
                    chat_id=update.message.chat_id,
                    text="Error that user is not applicable.")

    def balance(self, bot, update):
        user = update.message.from_user.username
        if self.check_user_existence(bot, user, update):
            _user = self.c_users.find_one({"username": user})
            bot.send_message(
                chat_id=update.message.chat_id,
                text="@{0} your current balance is: {1}. Powered by <a href='https://tezostacos.com'>Tezos Tacos</a> 🌮".format(user, _user['balance']),
                disable_web_page_preview=True,
                parse_mode='HTML'
            )
        else:
            bot.send_message(
                chat_id=update.message.chat_id,
                text="@{0} your current balance is: {1}. Powered by <a href='https://tezostacos.com'>Tezos Tacos</a> 🌮".format(user, 0),
                disable_web_page_preview=True,
                parse_mode='HTML'
            )

    def price(self, bot, update):
        btc_price = requests.get(
            "https://www.binance.com/api/v3/ticker/24hr?symbol=XTZBTC").json()['lastPrice']
        usdt_price = requests.get(
            "https://www.binance.com/api/v3/ticker/24hr?symbol=XTZUSDT").json()['lastPrice']
        bot.send_message(chat_id=update.message.chat_id,
                         text="<b>XTZBTC:</b> %s ฿\n<b>XTZUSDT:</b> %s USDT\n" % (
                             btc_price, usdt_price),
                         parse_mode='HTML')

    def withdraw(self, bot, update):
        user = update.message.from_user.username
        if self.check_user_existence(bot, user, update):
            split = update.message.text.split(" ")
            print(split)
            address = split[1]
            amount = float(split[2])

            _user = self.c_users.find_one({"username": user})
            balance = float(_user['balance'])

            if balance < amount:
                bot.send_message(chat_id=update.message.chat_id,
                                 text="@{0} you have insufficent funds.".format(user))
            else:
                amount = str(amount)
                self._transfer(user, address, amount)
                bot.send_message(chat_id=update.message.chat_id,
                                 text="@{0} has successfully withdrew to address: {1} of {2} XTZ".format(
                                     user, address, amount))

    def hi(self, bot, update):
        user = update.message.from_user.username
        bot.send_message(chat_id=update.message.chat_id,
                         text="Hello @{0}, how are you doing today?".format(
                             user))

    def moon(self, bot, update):
        bot.send_message(chat_id=update.message.chat_id,
                         text="Moon mission inbound!")

    def marketcap(self, bot, update):
        try:
            mc = requests.get(
                'https://api.coingecko.com/api/v3/coins/tezos').json()
            bot.send_message(chat_id=update.message.chat_id,
                             text="The current market cap of Tezos is valued at ${0}".format(
                                 "{:,.0f}".format(float(
                                     mc['market_data']['market_cap']['usd']))))
        except Exception as exc:
            bot.send_message(chat_id=update.message.chat_id,
                             text="The service is overloaded, try call this commands little bit later!")
            print(exc)

    def start(self, bot, update):
        try:
            user = update.message.from_user.username
            self.check_user_existence(bot, user, update)
        except Exception as exc:
            print(exc)

    def check_user_existence(self, bot, user, update):
        try:
            if user is None:
                bot.send_message(chat_id=update.message.chat_id,
                                 text="Please set a telegram username in your profile settings!")
                return False
            else:
                storage = self.ci.storage()
                if user not in str(list(storage['accounts'].keys())):
                    self._add_account(user, 0)

                db_user = self.c_users.find_one({"username": user}) is not None

                if not db_user:
                    self.c_users.update_one(
                        {
                            "_id": update.message.from_user.id
                        }, {"$set": {
                            "_id": update.message.from_user.id,
                            "balance": 0,
                            "username": user,

                        }}, upsert=True
                    )
                    bot.send_message(
                        chat_id=update.message.chat_id,
                        text=greeting_msg,
                        parse_mode='HTML'
                    )
                    print("User %s added to db" % user)
                return True

        except Exception as exc:
            print(exc)

    def _add_account(self, account_name, amount):
        try:
            # Add Account
            res = self.ci.add_account(
                account_name=account_name,
                amount=Decimal(amount)
            ).operation_group.autofill().sign().inject()
            print("_add_account", res)
            return res
        except Exception as exc:
            print(exc)

    def _tip(self, _from, _to, amount):
        try:
            res = self.ci.tip(
                _from=_from,
                _to=_to,
                amount=Decimal(amount)
            ).operation_group.autofill().sign().inject()
            print("_tip", res)
            return True
        except Exception as exc:
            print(exc)
            return False

    def _transfer(self, _from, _to, amount):
        try:
            res = self.ci.transfer(
                _from=_from,
                _to=_to,
                amount=Decimal(amount)
            ).operation_group.autofill().sign().inject()
            print("_transfer", res)
            return res
        except Exception as exc:
            print(exc)

    def _remove_account(self, account_name):
        try:
            res = self.ci.remove_account(
                account_name).operation_group.autofill().sign().inject()
            print("remove account", res)
            return res
        except Exception as exc:
            print(exc)



if __name__ == '__main__':
    tip_bot_obj = TipBot()

    commands_handler = CommandHandler('commands', tip_bot_obj.commands)
    dispatcher.add_handler(commands_handler)

    moon_handler = CommandHandler('moon', tip_bot_obj.moon)
    dispatcher.add_handler(moon_handler)

    hi_handler = CommandHandler('hi', tip_bot_obj.hi)
    dispatcher.add_handler(hi_handler)

    withdraw_handler = CommandHandler('withdraw', tip_bot_obj.withdraw)
    dispatcher.add_handler(withdraw_handler)

    marketcap_handler = CommandHandler('marketcap', tip_bot_obj.marketcap)
    dispatcher.add_handler(marketcap_handler)

    deposit_handler = CommandHandler('deposit', tip_bot_obj.deposit)
    dispatcher.add_handler(deposit_handler)

    price_handler = CommandHandler('price', tip_bot_obj.price)
    dispatcher.add_handler(price_handler)

    tip_handler = CommandHandler('tip', tip_bot_obj.tip)
    dispatcher.add_handler(tip_handler)

    balance_handler = CommandHandler('balance', tip_bot_obj.balance)
    dispatcher.add_handler(balance_handler)

    help_handler = CommandHandler('help', tip_bot_obj.help)
    dispatcher.add_handler(help_handler)

    start_handler = CommandHandler('start', tip_bot_obj.start)
    dispatcher.add_handler(start_handler)

    tacos_handler = CommandHandler('tacos', tip_bot_obj.tacos)
    dispatcher.add_handler(tacos_handler)

    updater.start_polling()
