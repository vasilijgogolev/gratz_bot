import json
import urllib3
import boto3
import os

table_name = "karabula_tb"
table = boto3.resource("dynamodb").Table(table_name)

http = urllib3.PoolManager()

TOKEN = os.environ['TELEGRAM_TOKEN']
BASE_URL = "https://api.telegram.org/bot{}".format(TOKEN)
_CHAT_ID = int(os.environ['CHAT_ID'])

funny_outputs = {
	1: 'Используй команду gratzstats чтобы узнать кол-во грацей',
	30: 'Неплоха',
	69: 'Very nice.',
	99: 'У нас тут мистер 99.999999%'
}

def get_funny(v :int) -> str:
	exist = funny_outputs.get(v)
	if not exist:
		return ""
	return exist

def numeral_noun_declension(number, nominative_singular, genetive_singular, nominative_plural):
    dig_last = number % 10
    return (
        (number in range(5, 20)) and nominative_plural or
        (1 in (number, dig_last)) and nominative_singular or
        ({number, dig_last} & {2, 3, 4}) and genetive_singular or nominative_plural
    )


def declensed_gratz(n: int) -> str:
    return numeral_noun_declension(n, 'грац', 'граца', 'грацей')


def items_to_html(items) -> str:
    _list = []
    item: dict
    for index, item in enumerate(items):
        place = index + 1
        name = item.get("name", "[ДАННЫЕ СКРЫТЫ]")
        amount = item.get("amount", 0)
        _list.append(f"{place}. <b>{name}</b> - {amount} {declensed_gratz(amount)}")
    return "\n".join(_list)


def hello(event, context):
    try:
        data = json.loads(event["body"])
        print(data)
        sending_user_id = data["message"]["from"]["id"]
        chat_id = data["message"]["chat"]["id"]

        if (int(chat_id) != _CHAT_ID):
            return {"statusCode":400, "message":"allowed only in certain chat id"}

        response = ""
        funny = ""
        valid_message = False
        message = str(data["message"]["text"])

        if "reply_to_message" in data["message"]:
            print("entering reply")
            reply = data["message"]["reply_to_message"]
            receiving_user_id = reply["from"]["id"]
            if (sending_user_id == receiving_user_id):
                print("can't gratz himself! returning")
                return {"statusCode": 200}
            first_name = reply["from"]["first_name"]
            user_id = int(reply["from"]["id"])

            if "gratz" in message:
                total_value = 0
                try:
                    _key = str(receiving_user_id)
                    r = table.get_item(
                        Key={"user_id": _key}
                    )
                    total_value = int(r["Item"]["amount"])
                except Exception as _e:
                    print(_e)

                total_value = total_value + 1

                try:
                    r = table.put_item(
                        Item={
                            "user_id": str(receiving_user_id),
                            "amount": total_value,
                            "name": first_name
                        }
                    )
                except Exception as _e_:
                    print(_e_)

                response = f"<b>{first_name}</b>, ты собрал {total_value} {declensed_gratz(total_value)}!"
                funny = get_funny(total_value)
                valid_message = True
        else:
            print("not a reply, trying to parse as text")
            if "gratzstats" in message:
                print("sending gratzstats")
                user_id = data["message"]["from"]["id"]
                total_value = 0
                try:
                    r = table.get_item(
                        Key={"user_id": str(user_id)}
                    )
                    total_value = int(r["Item"]["amount"])
                except Exception as _e:
                    print(_e)

                #total_value = chat_data.get(str(user_id), 0)
                sending_user_name = data["message"]["from"]["first_name"]
                response = f"<b>{sending_user_name}</b>, сейчас у тебя {total_value} {declensed_gratz(total_value)}!"
                valid_message = True
            if "gratztop" in message:
                print("sending gratztop")
                try:
                    # scan across the table with 1 MB limit
                    items = table.scan()["Items"]
                    sorted_items = sorted(items, key=lambda item: int(item["amount"]), reverse=True)
                    response = items_to_html(sorted_items)
                    valid_message = True
                except Exception as _e:
                    print(_e)

        if not valid_message:
            print("not a valid message, returning")
            return {"statusCode": 200}

        url = BASE_URL + "/sendMessage"
        _data = {"text": str(response), "chat_id": int(chat_id), "parse_mode": "HTML"}
        encoded_data = json.dumps(_data).encode('utf-8')

        print(f"sending message {response}")

        r = http.request('POST',
            url,
            body=encoded_data,
            headers={'Content-Type': 'application/json'},
            retries=False)

        http_status = r.status
        print(http_status)

        if (funny):
            funny_data = {"text": funny, "chat_id": int(chat_id), "parse_mode": "HTML"}
            _funny = json.dumps(funny_data).encode('utf-8')
            funny_request = http.request('POST',
                url,
                body=_funny,
                headers={'Content-Type': 'application/json'})
            funny_status = funny_request.status
            print(funny_status)
    except Exception as e:
        print(e)

    return {"statusCode": 200}
