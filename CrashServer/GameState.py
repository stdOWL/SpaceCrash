import enum
import json
from datetime import datetime
import math
from pymongo import MongoClient
import redis
from Enums import State
import mysql.connector
import pika

CrashSpeed = 0.00006
TakingBetTime = 20


def getCurrentTime():
    return int(datetime.now().timestamp() * 1e3)


class GameState:
    def __init__(self, gameStateHandler, config, sessionId=None):
        self.state = State.NotStarted
        self.gameStateHandler = gameStateHandler
        self.rabbitmqClient = pika.BlockingConnection(pika.ConnectionParameters(host=config['rabbitmq']['host'],virtual_host=config['rabbitmq']['vhost'],credentials=pika.credentials.PlainCredentials(username=config['rabbitmq']['user'],password=config['rabbitmq']['password']), heartbeat=5))

        self.rabbitmq_ch = self.rabbitmqClient.channel()
        self.rabbitmq_hbeat = 0

        self.GameHistory = []
        self.createTime = self.bettingEndTime = self.runningStartTime = self.runningOverTime = 0
        self.preGame = None
        self.mongoClient = MongoClient(
            f"mongodb://{config['mongodb']['user']}:{config['mongodb']['password']}@{config['mongodb']['host']}:27017/{config['mongodb']['database']}?authSource=admin")
        self.mongoDb = self.mongoClient[config['mongodb']['database']]
        self.redisClient = redis.Redis(host=config['redis']['host'], port=config['redis']['port'], db=config['redis']['db'],
                                       password=config['redis']['password'],
                                       decode_responses=True)


        self.bets = []
        self.mysqlClient = mysql.connector.connect(
            host="173.249.0.254",
            user="root",
            password="N54RMTD8qcJkHzX9",
            database="aced"
        )

        self.exchangeValues = []
        self.loadExchangeValues()

        if sessionId is None:
            self.sessionId = self.getLastSessionId()
        else:
            self.sessionId = sessionId

    def keepConnectionsAlive(self):
        if getCurrentTime() - self.rabbitmq_hbeat > 3000:
            self.rabbitmqClient.sleep(0.001)
            self.rabbitmq_hbeat = getCurrentTime()


    def loadExchangeValues(self):
        exchangeValues = self.redisClient.get("Crash:ExchangeValues")
        if exchangeValues:
            self.exchangeValues = json.loads(exchangeValues)
        else:
            self.exchangeValues = []

    def getCryptoPrice(self, balanceType):
        try:
            balanceExchangeVal = next(obj for obj in self.exchangeValues if obj["type"] == balanceType)
            if balanceExchangeVal:
                return float(balanceExchangeVal["price"])
        except Exception as e:
            print("getCryptoPrice",balanceType, json.dumps(self.exchangeValues))
        return 0


    def getLastSessionId(self):
        cursor = self.getCursor()
        cursor.execute("SELECT sessionId FROM CrashSessions ORDER BY sessionId DESC LIMIT 1")
        info = cursor.fetchone()
        cursor.close()
        if info is None:
            return 0
        return int(info["sessionId"])

    def getCursor(self):
        try:
            self.mysqlClient.ping(reconnect=True, attempts=3, delay=5)
        except mysql.connector.Error as err:
            raise err
        return self.mysqlClient.cursor(dictionary=True)

    def saveDatabase(self):
        cursor = self.getCursor()
        cursor.execute("""
                INSERT IGNORE INTO CrashSessions(sessionId,status,hash,lastPoint,createGameTime,runningStartTime,bettingEndTime,runningOverTime,userCount,botCount) 
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,0,0)""", (
            self.sessionId, self.state, self.getHash(), self.getCurrentPoint(), self.createTime, self.runningStartTime,
            self.bettingEndTime, self.runningOverTime
        ))
        self.mysqlClient.commit()
        cursor.close()

    def loadSessionBets(self):
        cursor = self.getCursor()
        cursor.execute("""SELECT * FROM vw_crashBets WHERE sessionId = %s AND status = 'ACTIVE'""", (self.sessionId,))
        self.bets = cursor.fetchall()
        cursor.close()

    def cashOut(self, bet, currentPoint):
        cursor = self.getCursor()
        cursor.execute("""CALL CrashCashout(%s,%s,%s,%s)""", (
            bet["userid"], bet["id"], self.sessionId, currentPoint
        ))
        cashOutResult = cursor.fetchone()
        if cashOutResult["result"] == 1:
            cashOutResult["payoutValue"] = float(cashOutResult["payoutValue"])
            cashOutResult["payoutValueUSD"] = float(cashOutResult["payoutValue"]) * self.getCryptoPrice(
                cashOutResult["balanceType"])
            self.rabbitmq_ch.basic_publish(exchange='', routing_key='crash_order', body=json.dumps(cashOutResult))
            # self.gameStateHandler.redis_stream.sendBetPacket(cashOutResult)

        cursor.close()

    def endSession(self, sessionId):
        cursor = self.getCursor()
        cursor.execute("""CALL CrashEndSession(%s)""", (
            sessionId
        ))
        cursor.close()

    def checkAutoCashout(self):
        currentPoint = self.getCurrentPoint()
        finalPoint = self.getFinalMultiplier()
        for i in range(len(self.bets)):
            bet = self.bets[i]
            if bet["status"] == "ACTIVE":
                autoCashout = float(bet["autoCashout"])
                if 1.01 <= autoCashout <= finalPoint and autoCashout <= currentPoint:
                    self.bets[i]["status"] = "CASHOUT"
                    self.cashOut(bet, autoCashout)

    def setCashout(self, betid):
        for i in range(len(self.bets)):
            bet = self.bets[i]
            if int(bet["id"]) == int(betid):
                self.bets[i]['status'] = "CASHOUT"
                break

    def updateDatabase(self):
        cursor = self.getCursor()
        cursor.execute("""
                        UPDATE CrashSessions 
                        SET status = %s,hash = %s,lastPoint = %s,createGameTime = %s,runningStartTime = %s,bettingEndTime = %s,runningOverTime = %s
                        WHERE sessionId = %s""", (
            self.state, self.getHash(), self.getCurrentPoint(), self.createTime, self.runningStartTime,
            self.bettingEndTime, self.runningOverTime, self.sessionId
        ))
        self.mysqlClient.commit()
        cursor.close()

    def save(self):
        pass

    def saveRedis(self):
        gameInfo = {
            "sessionId": self.sessionId,
            "state": self.state,
            "createTime": self.createTime,
            "bettingEndTime": self.bettingEndTime,
            "runningStartTime": self.runningStartTime,
            "finalMultiplier": self.getFinalMultiplier(),
            "hash": self.getHash(),
            "currentPoint": self.getCurrentPoint(),
            "elapsedTime": self.getElapsedTime()
        }
        self.redisClient.hset('Crash:Game', mapping=gameInfo)

    def getPrecalculatedGame(self, sessionId):
        return self.mongoDb.HashChain.find_one({'sessionId': sessionId})

    def createNewGame(self, sessionId=None):
        if sessionId is None:
            self.sessionId = self.sessionId + 1
        else:
            self.sessionId = sessionId

        preGame = self.getPrecalculatedGame(self.sessionId)
        if preGame is None:
            raise Exception("Precalculated game not found!", self.sessionId)

        currentTime = getCurrentTime()
        self.createTime = currentTime
        self.bettingEndTime = currentTime + (TakingBetTime * 1e3) - 100
        self.runningStartTime = currentTime + (TakingBetTime * 1e3)
        self.runningOverTime = 0

        self.state = State.NotStarted
        self.preGame = preGame
        self.saveDatabase()
        self.loadExchangeValues()

    def isBlowed(self):
        return self.getCurrentPoint() >= self.getFinalMultiplier()

    def getFinalMultiplier(self):
        if self.preGame is None:
            raise Exception("preGame is NULL!")
        return float(self.preGame['point'].to_decimal())

    def getRunningStartTime(self):
        return self.runningStartTime - getCurrentTime()

    def getBettingEndTime(self):
        return self.bettingEndTime - getCurrentTime()

    def getHash(self):
        if self.preGame is None:
            raise Exception("preGame is NULL!")
        return self.preGame['_id']

    def getState(self) -> State:
        return self.state

    def getiState(self):
        if self.state == State.NotStarted:
            return 1
        if self.state == State.TakingBets:
            return 2
        if self.state == State.Running:
            return 3
        if self.state == State.Over:
            return 4

    def insertHistory(self):
        self.GameHistory.insert(0, {
            "crashPoint": self.getFinalMultiplier(),
            "id": str(self.sessionId)
        })
        self.GameHistory = self.GameHistory[0:50]
        self.redisClient.set("Crash:History", json.dumps(self.GameHistory))

    def setState(self, state):
        self.state = state

    def getCurrentPoint(self):
        # TODO: floor
        ElapsedTime = self.getElapsedTime()
        return math.floor(100 * math.e ** (CrashSpeed * ElapsedTime)) / 100

    def getElapsedTime(self):
        return getCurrentTime() - self.runningStartTime
