# This is a sample Python script.

# Press Shift+F10 to execute it or replace it with your code.
# Press Double Shift to search everywhere for classes, files, tool windows, actions, and settings.
import sys

import yaml
from GameStateHandler import GameStateHandler
import signal
import time
GameStateHandlerThread = None


def signal_handler(sig, frame):
    global GameStateHandlerThread
    print("[X] Call SIGINT - Exiting!")
    print("[X] Please Wait Until Session Ends!")
    if GameStateHandlerThread:
        GameStateHandlerThread.setRunning(False)
        GameStateHandlerThread.join()
    print("[X] Done")
    sys.exit(0)




def main():
    global GameStateHandlerThread
    signal.signal(signal.SIGINT, signal_handler)
    with open('config.yaml', 'r') as configFile:
        config = yaml.safe_load(configFile)
        GameStateHandlerThread = GameStateHandler(config)
        GameStateHandlerThread.start()
        # GameStateHandlerThread.join()

    while True:
        time.sleep(1)


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    main()

# See PyCharm help at https://www.jetbrains.com/help/pycharm/
