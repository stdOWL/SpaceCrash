import random
import threading
import requests
import time
from utils import getCurrentTime


def shouldWait():
    time.sleep(random.randint(200, 6000) / 1000)
    return True


def skipRound():
    if random.randint(0, 10000) < 2000:
        return True
    return False


class Bot(threading.Thread):
    botPort = 0

    def __init__(self, config, account, wallets):
        super().__init__()
        self.account = account
        self.config = config
        self.wallets = wallets
        self.wallet = None
        self.running = True
        self.bet = None
        self.minEndTime = getCurrentTime() + int(config['bots']['minKeepOnlineTime']) * 1e3 * 60
        self.maxEndTime = getCurrentTime() + int(config['bots']['maxKeepOnlineTime']) * 1e3 * 60
        self.isFinished = False
        self.error = None

    def isMinTimeSatisfied(self):
        return getCurrentTime() > self.minEndTime

    def getAuthCode(self):
        try:
            selectedPort = (Bot.botPort % 8) + 3000
            Bot.botPort = Bot.botPort + 1

            link = f"http://213.136.91.139:{selectedPort}/auth"
            payload = {"email": self.account["email"], "password": self.account["password"], "fp": ""}
            r = requests.post(link, json=payload)
            response = r.json()
            accesstoken = response["accessToken"]
            self.account["token"] = accesstoken
            return True
        except Exception as e:
            return False

    def selectRandomWallet(self):
        self.wallet = random.choice(self.wallets)

    def setRunning(self, _running):
        self.running = _running

    def getGameState(self):
        try:
            selectedPort = (Bot.botPort % 8) + 3000
            Bot.botPort = Bot.botPort + 1
            r = requests.get(f"http://213.136.91.139:{selectedPort}/crash/getActiveGame")
            return r.json()
        except Exception as e:
            return None

    def cashout(self):
        if self.bet is None:
            return
        try:
            selectedPort = (Bot.botPort % 8) + 3000
            Bot.botPort = Bot.botPort + 1
            link = f"http://213.136.91.139:{selectedPort}/crash/cashout"
            cashoutReq = {"betId": self.bet['id']}
            r = requests.post(link, json=cashoutReq, headers={"authorization": f"Bearer {self.account['token']}"})
            response = r.json()
            if response['status'] == True:
                return True

        except Exception as e:
            return False
        return False

    def waitTillState(self, state, randomCashout=False):
        timeout = 3 * 60
        while self.running and timeout > 0:
            gameState = self.getGameState()
            gameStatus = 'Unknown'
            if gameState is not None and 'game' in gameState and gameState['game']['state']:
                gameStatus = gameState['game']['state']

            if gameStatus == state:
                return True

            if randomCashout is True and gameState == "Running" and self.bet is not None:
                if random.randint(0, 10000) < 500 and self.cashout():
                    return True

            timeout = timeout - 1
            time.sleep(1)
        return False

    def createRandomBet(self):
        autoCashout = round(random.randint(120, 3500) / 100.0, 1)
        maxBet = round(random.uniform(float(self.wallet['minBet']), float(self.wallet['maxBet'])), 5)
        betAmount = round(random.uniform(float(self.wallet['minBet']), maxBet), 4)

        # random.randint(self.wallet['minBet'], self.wallet['minBet'])

        bet = {"walletType": self.wallet['type'], "betAmount": betAmount, "autoCashout": autoCashout, "autobet": None}
        return bet

    def sendBetRequest(self, bet):
        self.bet = None
        try:
            selectedPort = (Bot.botPort % 8) + 3000
            Bot.botPort = Bot.botPort + 1
            link = f"http://213.136.91.139:{selectedPort}/crash/joinGame"
            r = requests.post(link, json=bet, headers={"authorization": f"Bearer {self.account['token']}"})
            response = r.json()
            if response['result'] == 1 or response['result'] == -1:
                self.bet = response
                return True
        except Exception as e:
            return False

        return False

    def createNewBet(self):
        if random.randint(0, 10000) < 1500:
            self.selectRandomWallet()

        bet = self.createRandomBet()
        return self.sendBetRequest(bet)

    def run(self) -> None:
        try:

            if not self.getAuthCode():
                raise Exception("Login Auth Error")

            self.selectRandomWallet()

            while self.running and getCurrentTime() < self.maxEndTime:
                if random.randint(0, 10000) < 1500 and self.isMinTimeSatisfied():
                    break
                self.waitTillState("TakingBets")
                if not skipRound():
                    shouldWait()
                    self.createNewBet()
                self.waitTillState("Over", True)
        except Exception as e:
            self.error = e
        self.isFinished = True
