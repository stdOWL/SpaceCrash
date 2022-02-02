from random_username.generate import generate_username
import string
import hashlib
import base64
import hmac
from datetime import datetime
import random
def getCurrentTime():
    return int(datetime.now().timestamp() * 1e3)


def generate_random_username():
    username = generate_username(1)[0]
    if random.randint(0,10000) < 5000:
        username = username[0:len(username) - 4]
    if random.randint(0, 10000) < 2000:
        username = username + generate_username(1)[0]
        lenUser = random.randint(0, 10)
        if lenUser < len(username):
            username = username[0:len(username) - lenUser]
    return username



def generate_random_password():
    length = 10

    characters = list(string.ascii_letters + string.digits)
    random.shuffle(characters)
    password = []
    for i in range(length):
        password.append(random.choice(characters))

    random.shuffle(password)

    return "".join(password)


def generate_password_hash(password):
    """
              let salt = crypto.randomBytes(16).toString("base64");
              let hash = crypto
                .createHmac("sha512", salt)
                .update(password)
                .digest("base64");
              password = salt + "$" + hash;

    """
    salt = base64.b64encode(random.randbytes(16)).decode('utf-8')
    hmacResult = hmac.new(salt.encode(), password.encode(), hashlib.sha512)
    shaResult = hmacResult.digest()
    shaBase64 = base64.b64encode(shaResult).decode('utf-8')
    shaPassword = f"{salt}${shaBase64}"
    return shaPassword