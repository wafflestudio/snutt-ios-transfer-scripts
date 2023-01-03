import os
from typing import Optional

import pymongo
import requests

CLIENT_ID = os.getenv("CLIENT_ID")
RECIPIENT_TEAM_ID = os.getenv("RECIPIENT_TEAM_ID")
MONGO_URL = os.getenv("MONGO_URL")

client = pymongo.MongoClient(f"mongodb://{MONGO_URL}:27017/")


def load_jwt_token():
    """`client_secret`를 불러온다."""
    with open("client_secret_jwt.txt", "r") as f:
        return f.read()


def generate_access_token(client_secret: str) -> str:
    """REST API 호출을 위한 access_token을 발급받는다.

    Args:
        client_secret (str): transferring team에서 발급한 key를 바탕으로 생성한 JWT

    Returns:
        str: access token.
    """
    res = requests.post(
        url="https://appleid.apple.com/auth/token",
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data=dict(
            grant_type="client_credentials",
            scope="user.migration",
            client_id=CLIENT_ID,
            client_secret=client_secret,
        ),
    )
    return res.json().get("access_token")


def get_transfer_sub(access_token: str, client_secret: str, apple_sub: str) -> Optional[str]:
    """각 유저의 `user_id`에 대응하는 `transfer_sub`를 가져온다.

    Args:
        access_token (str): REST API 호출을 위한 토큰
        client_secret (str): REST API 호출을 위한 클라이언트 토큰
        apple_sub (str): 유저가 애플로 로그인했을 때 발급되는 team-scoped user identifier

    Returns:
        str: transfer sub. 팀 간 유저 identifier를 연결하는 다리 역할을 한다.
    """
    res = requests.post(
        url="https://appleid.apple.com/auth/usermigrationinfo",
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Bearer {access_token}",
        },
        data=dict(
            sub=apple_sub,
            target=RECIPIENT_TEAM_ID,
            client_id=CLIENT_ID,
            client_secret=client_secret,
        ),
    )
    try:
        res.raise_for_status()
        return res.json().get("transfer_sub")
    except requests.exceptions.HTTPError:
        print(res.status_code, res.json())
        return None
    except Exception as e:
        print(e)
        return None


def get_new_apple_user(access_token: str, client_secret: str, transfer_sub: str) -> Optional[dict]:
    """`tranfser_sub`를 바탕으로 새로운 user_id를 발급받습니다.
    [주의] 이 API는 App Transfer가 완료된 이후부터 사용할 수 있습니다.

    Args:
        access_token (str): REST API 호출을 위한 토큰
        client_secret (str): REST API 호출을 위한 클라이언트 토큰
        transfer_sub (str): `get_transfer_sub` 등을 통해 발급받은 transfer_sub

    Returns:
        dict: 아래 3가지 필드가 포함된 json object
            - sub (str): 새로운 user id
            - email (str): 새로운 (private) email
            - is_private_email (bool): private email 사용 여부
    """
    res = requests.post(
        url="https://appleid.apple.com/auth/usermigrationinfo",
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Bearer {access_token}",
        },
        data=dict(
            transfer_sub=transfer_sub,
            client_id=CLIENT_ID,
            client_secret=client_secret,
        ),
    )
    try:
        res.raise_for_status()
        return res.json()
    except requests.exceptions.HTTPError:
        print(res.status_code, res.json())
        return None
    except Exception as e:
        print(e)
        return None


def main_for_creating_apple_transfer_sub_of_all_users():
    client_secret = load_jwt_token()
    access_token = generate_access_token(client_secret=client_secret)

    users = client.snutt.users
    count = 0
    for i, user in enumerate(users.find({"credential.appleSub": {"$ne": None},
                                         "credential.appleTransferSub": {"$eq": None}}
                                        ).sort("regDate", pymongo.ASCENDING)):
        apple_sub = user["credential"]["appleSub"]
        user_id = user["_id"]
        reg_date = user["regDate"]

        if i % 100 == 0:
            print(f"Processed {i} users: {user_id} | {reg_date} | {apple_sub}")

        transfer_sub = get_transfer_sub(
            access_token=access_token,
            client_secret=client_secret,
            apple_sub=apple_sub,
        )
        if not transfer_sub:
            print(f"Failed to get transfer sub: {user_id} | {reg_date} | {apple_sub}")
            continue

        users.update_one(
            {"_id": user_id},
            {"$set": {"credential.appleTransferSub": transfer_sub}},
        )
        count += 1

    print(f"Processed {count} users!")


def main():
    client_secret = load_jwt_token()
    access_token = generate_access_token(client_secret=client_secret)

    users = client.snutt.users
    count = 0
    for i, user in enumerate(users.find({"credential.appleSub": {"$ne": None},
                                         "credential.appleTransferSub": {"$ne": None}}
                                        ).sort("regDate", pymongo.ASCENDING)):
        apple_sub = user["credential"]["appleSub"]
        apple_transfer_sub = user["credential"]["appleTransferSub"]
        user_id = user["_id"]
        reg_date = user["regDate"]

        if i % 100 == 0:
            print(f"Processed {i} users: {user_id} | {reg_date} | {apple_sub}")

        new_apple_user = get_new_apple_user(
            access_token=access_token,
            client_secret=client_secret,
            transfer_sub=apple_transfer_sub,
        )
        new_apple_sub = new_apple_user["sub"]
        new_apple_email = new_apple_user["email"]
        if not new_apple_sub or not new_apple_email:
            print(f"Failed to get transfer sub: {user_id} | {reg_date} | {apple_sub}")
            continue

        if apple_sub == new_apple_sub:
            print(f"Already migrated: {user_id} | {reg_date} | {apple_sub} == {new_apple_sub}")
            continue

        users.update_one(
            {"_id": user_id},
            {"$set": {"credential.appleSub": new_apple_sub, "credential.appleEmail": new_apple_email}},
        )
        count += 1

    print(f"Processed {count} users!")


if __name__ == "__main__":
    main()
