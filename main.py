import requests


def load_jwt_token():
    """`client_secret`를 불러온다."""
    with open("jwt.txt", "r") as f:
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


def get_transfer_id(access_token: str, client_secret: str, user_id: str) -> str:
    """각 유저의 `user_id`에 대응하는 `transfer_id`를 가져온다.

    Args:
        access_token (str): REST API 호출을 위한 토큰
        client_secret (str): REST API 호출을 위한 클라이언트 토큰
        user_id (str): 유저가 애플로 로그인했을 때 발급되는 team-scoped user identifier

    Returns:
        str: transfer id. 팀 간 유저 identifier를 연결하는 다리 역할을 한다.
    """
    res = requests.post(
        url="https://appleid.apple.com/auth/usermigrationinfo",
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Bearer {access_token}",
        },
        data=dict(
            sub=user_id,
            target=RECIPIENT_TEAM_ID,
            client_id=CLIENT_ID,
            client_secret=client_secret,
        ),
    )
    return res.json().get("transfer_sub")


def get_new_user_id(access_token: str, client_secret: str, transfer_id: str) -> dict:
    """`tranfser_id`를 바탕으로 새로운 user_id를 발급받습니다.
    [주의] 이 API는 App Transfer가 완료된 이후부터 사용할 수 있습니다.

    Args:
        access_token (str): REST API 호출을 위한 토큰
        client_secret (str): REST API 호출을 위한 클라이언트 토큰
        transfer_id (str): `get_transfer_id` 등을 통해 발급받은 transfer_id

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
            transfer_sub=transfer_id,
            client_id=CLIENT_ID,
            client_secret=client_secret,
        ),
    )
    return res.json()


def get_all_user_ids() -> list[str]:
    # TODO: DB에 존재하는 모든 user_id(`appleSub`) 필드를 가져온다.
    return ["001896.c91fbf54687a4a61b731add1b715e446.1655"]


def save_transfer_id(user_id: str, transfer_id: str):
    # TODO: transfer_id를 `appleTransferSub`라는 새로운 필드에 저장한다.
    return


def main():
    client_secret = load_jwt_token()
    access_token = generate_access_token(client_secret=client_secret)
    for user_id in get_all_user_ids():
        transfer_id = get_transfer_id(
            access_token=access_token,
            client_secret=client_secret,
            user_id=user_id,
        )
        save_transfer_id(user_id=user_id, transfer_id=transfer_id)


if __name__ == "__main__":
    CLIENT_ID = "com.wafflestudio.snutt"
    RECIPIENT_TEAM_ID = "K9883YB4VR"
    main()
