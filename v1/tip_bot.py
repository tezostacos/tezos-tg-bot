import json

import requests
import subprocess
from telegram.ext.dispatcher import run_async
from telegram.ext import Updater



with open('services.json') as conf_file:
    conf = json.load(conf_file)
    bot_token = conf['telegram_bot']['bot_token']
    constant_url = conf['constant_url']
    node_settings = conf['node_settings']
    greeting_msg = conf['greeting_msg']
    machine = conf['bot_username']


updater = Updater(token=bot_token)
dispatcher = updater.dispatcher

core = "/usr/bin/tezos-client"


import logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)


def commands(bot, update):
    user = update.message.from_user.username
    bot.send_message(chat_id=update.message.chat_id, text="Initiating commands /tip & /withdraw have a specfic format,\n use them like so:" + "\n \n Parameters: \n <user> = target user to tip \n <amount> = amount of reddcoin to utilise \n <address> = reddcoin address to withdraw to \n \n Tipping format: \n /tip <user> <amount> \n \n Withdrawing format: \n /withdraw <address> <amount>")


def help(bot, update):
    bot.send_message(chat_id=update.message.chat_id, text="The following commands are at your disposal: /hi , /commands , /deposit , /tip , /withdraw , /price , /marketcap or /balance")


def tacos(bot, update):
    mc = requests.get('https://api.coingecko.com/api/v3/coins/tezos').json()
    btc_price = requests.get("https://www.binance.com/api/v3/ticker/24hr?symbol=XTZBTC").json()['lastPrice']
    usdt_price = requests.get("https://www.binance.com/api/v3/ticker/24hr?symbol=XTZUSDT").json()['lastPrice']
    text = "<b>XTZBTC:</b> %s ฿\n<b>XTZUSDT:</b> %s USDT\n" % (btc_price, usdt_price)
    text += "The current market cap of Tezos is valued at ${0}\n".format("{:,.0f}".format(float(mc['market_data']['market_cap']['usd'])))

    bot.send_message(
        chat_id=update.message.chat_id,
        text=text,
        parse_mode='HTML'
    )


def deposit(bot, update):
    user = update.message.from_user.username
    if check_user_existence(bot, user, update):
        result = subprocess.run([core, *node_settings, "show", "address", user],stdout=subprocess.PIPE)
        print(result)
        clean = (result.stdout.strip()).decode("utf-8").split('\n')[0].replace("Hash:", "")
        bot.send_message(chat_id=update.message.chat_id, text="@{0} your depositing address is: {1}".format(user, clean))


def tip(bot, update):
    user = update.message.from_user.username
    target = update.message.text[5:]
    amount =  target.split(" ")[1]
    target =  target.split(" ")[0]
    if check_user_existence(bot, user, update):
        if target == machine:
            bot.send_message(chat_id=update.message.chat_id, text="HODL.")
        elif "@" in target:
            target = target[1:]
            alias_list = get_alias_lists()
            if target not in str(alias_list):
                register_user(target)
            user = update.message.from_user.username
            result = subprocess.run([core, *node_settings, "get", "balance", "for", user], stdout=subprocess.PIPE)
            print(result)
            balance = float((result.stdout.strip()).decode("utf-8").split(" ")[0])
            amount = float(amount)
            print("Sending tip from %s to %s with %s amount" % (user, target, amount))
            if balance < amount:
                bot.send_message(chat_id=update.message.chat_id, text="@{0} you have insufficent funds.".format(user))
            elif target == user:
                bot.send_message(chat_id=update.message.chat_id, text="You can't tip yourself silly.")
            else:
                balance = str(balance)
                amount = str(amount)
                gas_settings = get_gas_settings()
                tx = subprocess.Popen([core, *node_settings, "transfer", amount, "from", user, "to", target, *gas_settings], stdout=subprocess.PIPE)
               # print(tx, " ******\n", tx.stdout.strip())
                bot.send_message(chat_id=update.message.chat_id, text="@{0} tipped @{1} of {2} ꜩ".format(user, target, amount))
        else:
            bot.send_message(chat_id=update.message.chat_id, text="Error that user is not applicable.")


def balance(bot, update):
    user = update.message.from_user.username
    if check_user_existence(bot, user, update):
        result = subprocess.run([core, *node_settings, "get", "balance", "for", user], stdout=subprocess.PIPE)
        print(result)
        balance = (result.stdout.strip()).decode("utf-8")
        bot.send_message(chat_id=update.message.chat_id, text="@{0} your current balance is: {1}".format(user, balance))


def price(bot, update):
    btc_price = requests.get("https://www.binance.com/api/v3/ticker/24hr?symbol=XTZBTC").json()['lastPrice']
    usdt_price = requests.get("https://www.binance.com/api/v3/ticker/24hr?symbol=XTZUSDT").json()['lastPrice']
    bot.send_message(
        chat_id=update.message.chat_id,
        text="<b>XTZBTC:</b> %s ฿\n<b>XTZUSDT:</b> %s USDT\n" % (btc_price, usdt_price),
        parse_mode='HTML'
    )


def withdraw(bot, update):
    user = update.message.from_user.username
    if check_user_existence(bot, user, update):
        split = update.message.text.split(" ")
        print(split)
        address = split[1]
        amount = float(split[2])
        result = subprocess.run([core, *node_settings, "get", "balance", "for", user], stdout=subprocess.PIPE)
        balance = float(result.stdout.strip().decode("utf-8").split(" ")[0])
        if balance < amount:
            bot.send_message(chat_id=update.message.chat_id, text="@{0} you have insufficent funds.".format(user))
        else:
            amount = str(amount)
            gas_settings = get_gas_settings()
            tx = subprocess.Popen([core, *node_settings, "transfer", amount, "from", user, "to", address, *gas_settings], stdout=subprocess.PIPE)
           # print(tx, "\n", tx.stdout.strip())
            bot.send_message(chat_id=update.message.chat_id, text="@{0} has successfully withdrew to address: {1} of {2} RDD" .format(user,address,amount))


def hi(bot, update):
    user = update.message.from_user.username
    bot.send_message(chat_id=update.message.chat_id, text="Hello @{0}, how are you doing today?".format(user))


def moon(bot, update):
    bot.send_message(chat_id=update.message.chat_id, text="Moon mission inbound!")


def marketcap(bot, update):
    try:
        mc = requests.get('https://api.coingecko.com/api/v3/coins/tezos').json()
        bot.send_message(chat_id=update.message.chat_id, text="The current market cap of Tezos is valued at ${0}".format("{:,.0f}".format(float(mc['market_data']['market_cap']['usd']))))
    except Exception as exc:
        bot.send_message(chat_id=update.message.chat_id, text="The service is overloaded, try call this commands little bit later!")
        print(exc)


def start(bot, update):
    try:
        user = update.message.from_user.username
        if check_user_existence(bot, user, update):
            bot.send_message(
                chat_id=update.message.chat_id,
                text=greeting_msg,
                parse_mode='HTML'
            )
    except Exception as exc:
        print(exc)

def get_alias_lists():
    result = subprocess.run([core, *node_settings, "list", "known", "contracts"], stdout=subprocess.PIPE)
    print(result)
    result = result.stdout.strip().decode("utf-8")
    print(result)
    return result


def get_gas_settings():
    gas_settings = ["--gas-limit", "20375", "--storage-limit", "70"]
    try:
        response = requests.get(constant_url).json()
        gas_settings = ["--gas-limit", response['hard_gas_limit_per_operation'], "--storage-limit", response['hard_storage_limit_per_operation']]
        return gas_settings
    except Exception as exc:
        print(exc)
        return gas_settings


def check_user_existence(bot, user, update):
    try:
        if user is None:
            bot.send_message(chat_id=update.message.chat_id, text="Please set a telegram username in your profile settings!")
            return False
        else:
            alias_list = get_alias_lists()
            if user not in str(alias_list):
                register_user(user)
            return True

    except Exception as exc:
        print(exc)


def register_user(user):
    result = subprocess.run([core, "-A", "xxx", "gen", "keys", user], stdout=subprocess.PIPE)
    print(result)
    result = result.stdout.strip().decode("utf-8")
    print(result)


from telegram.ext import CommandHandler

commands_handler = CommandHandler('commands', commands)
dispatcher.add_handler(commands_handler)

moon_handler = CommandHandler('moon', moon)
dispatcher.add_handler(moon_handler)

hi_handler = CommandHandler('hi', hi)
dispatcher.add_handler(hi_handler)

withdraw_handler = CommandHandler('withdraw', withdraw)
dispatcher.add_handler(withdraw_handler)

marketcap_handler = CommandHandler('marketcap', marketcap)
dispatcher.add_handler(marketcap_handler)

deposit_handler = CommandHandler('deposit', deposit)
dispatcher.add_handler(deposit_handler)

price_handler = CommandHandler('price', price)
dispatcher.add_handler(price_handler)

tip_handler = CommandHandler('tip', tip)
dispatcher.add_handler(tip_handler)

balance_handler = CommandHandler('balance', balance)
dispatcher.add_handler(balance_handler)

help_handler = CommandHandler('help', help)
dispatcher.add_handler(help_handler)

start_handler = CommandHandler('start', start)
dispatcher.add_handler(start_handler)

tacos_handler = CommandHandler('tacos', tacos)
dispatcher.add_handler(tacos_handler)


updater.start_polling()


