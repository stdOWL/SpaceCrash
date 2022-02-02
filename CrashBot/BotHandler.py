import threading
import time

from pymongo import MongoClient
import random
from utils import generate_random_username, generate_random_password, generate_password_hash, getCurrentTime
import mysql.connector
from Bot import Bot


class BotHandler(threading.Thread):
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.isRunning = True
        self.accounts = []
        self.activeBots = []

        self.mongoClient = MongoClient(
            f"mongodb://{config['mongodb']['user']}:{config['mongodb']['password']}@{config['mongodb']['host']}:27017/{config['mongodb']['database']}?authSource=admin")
        self.mongoDb = self.mongoClient[config['mongodb']['database']]
        self.mysqlClient = mysql.connector.connect(
            host="173.249.0.254",
            user="root",
            password="N54RMTD8qcJkHzX9",
            database="aced"
        )
        self.lastBotControlTime = 0

    def setRunning(self, _isRunning):
        self.isRunning = _isRunning

    def loadAccounts(self):
        self.mongoDb.CrashBotAccounts.update_many({}, {"$set": {"isOnline": False}})
        self.accounts = self.mongoDb.CrashBotAccounts.find({})

    def getCursor(self):
        try:
            self.mysqlClient.ping(reconnect=True, attempts=3, delay=5)
        except mysql.connector.Error as err:
            raise err
        return self.mysqlClient.cursor(dictionary=True)

    def getWallets(self, userid):
        cursor = self.getCursor()
        cursor.execute("SELECT * FROM vw_userWalletsDetailed WHERE userid = %s", (userid,))
        wallets = cursor.fetchall()
        cursor.close()
        return wallets

    def insertAccountDatabase(self, email, username, password, passwordHashed):
        print(f"Creating new account username={username},email={email}")
        cursor = self.getCursor()
        cursor.execute(
            "INSERT INTO Users(email,username,password,verifyParam,role, isBot) VALUES (%s, %s, %s, 'AUTO-CREATED','BOT', 1)",
            (email, username, passwordHashed))
        self.mysqlClient.commit()
        userid = cursor.lastrowid

        cursor.execute("UPDATE Users SET verified = 1 WHERE id = %s", (userid,))
        self.mysqlClient.commit()
        cursor.execute("UPDATE UserWallets SET balance = 10000000 WHERE userid = %s", (userid,))
        self.mysqlClient.commit()
        cursor.close()

        self.mongoDb.CrashBotAccounts.insert_one({
            "userid": userid,
            "username": username,
            "password": password,
            "passwordHashed": passwordHashed,
            "email": email,
            "isOnline": False,
        })

        return self.mongoDb.CrashBotAccounts.find_one({
            "username": username
        })

    def createNewBotAccount(self):
        username = generate_random_username()
        email = f"{generate_random_username()}@gmail.com"
        password = generate_random_password()
        passwordHash = generate_password_hash(password)
        account = self.insertAccountDatabase(email, username, password, passwordHash)
        wallets = self.getWallets(account['userid'])
        return account, wallets

    def getAvailableBot(self):
        if random.randint(0, 10000) < self.config['bots']['createAccountPercentage']:
            return self.createNewBotAccount()
        availableBots = []
        for account in self.accounts:
            if not account['isOnline']:  # make other controls
                availableBots.append(account)
        if len(availableBots) > 0:
            account = random.choice(availableBots)
            return account, self.getWallets(account['userid'])

        # current accounts not available so create new one.
        return self.createNewBotAccount()

    def reviveNewBot(self):
        try:
            account, wallets = self.getAvailableBot()
            account['isOnline'] = True
            botThread = Bot(self.config, account, wallets)
            botThread.start()
            self.activeBots.append(botThread)
            print("bot online:", account)
        except Exception as e:
            print("reviveNewBot error", e)

    def controlDeadBots(self):
        for bot in self.activeBots.copy():
            if bot.isFinished:
                if bot.error:
                    print("bot dead with error ", bot.account, bot.error)
                else:
                    print("bot dead without error ", bot.account)
                self.activeBots.remove(bot)
    def killAll(self):
        for bot in self.activeBots:
            bot.setRunning(False)
        for bot in self.activeBots:
            bot.join()
        self.activeBots = []

    def controlBotsCounts(self):
        activeCount = len(self.activeBots)
        minOnlineBot = self.config['bots']['minOnlineBot']
        maxOnlineBot = self.config['bots']['maxOnlineBot']
        newActiveCount = random.randint(minOnlineBot, maxOnlineBot)
        if newActiveCount == 0:
            self.killAll()
            time.sleep(60 * random.randint(3, 15))

        if newActiveCount > activeCount:
            for botId in range(newActiveCount - activeCount):
                self.reviveNewBot()

    def run(self) -> None:
        self.loadAccounts()
        while self.isRunning:
            if getCurrentTime() - self.lastBotControlTime > self.config['bots']['checkBotsTime'] * 60 * 1e3:
                self.controlDeadBots()
                self.controlBotsCounts()
                self.lastBotControlTime = getCurrentTime()
            time.sleep(1)
