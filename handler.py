import json
import urllib3
import boto3
import os

table_name = "karabula_tb"
table = boto3.resource("dynamodb").Table(table_name)

http = urllib3.PoolManager()

TOKEN = os.environ['TELEGRAM_TOKEN']
BASE_URL = "https://api.telegram.org/bot{}".format(TOKEN)


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
    return "<br/>".join(_list)


def hello(event, context):
	try:
		data = json.loads(event["body"])
		print(data)
		sending_user_id = data["message"]["from"]["id"]
		chat_id = data["message"]["chat"]["id"]
		response = ""
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
				valid_message = True
		else:
			print("not a reply, trying to parse as text")
			if "gratzstats" in message:
				print("sending gratzstats")
				user_id = data["message"]["from"]["id"]
				total_value = 0
				try:
					response = table.get_item(
						Key={"user_id": str(user_id)}
					)
					total_value = int(response["Item"]["amount"])
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
		message_id = int(data["message"]["message_id"])
		_data = {"text": str(response), "chat_id": int(chat_id), "reply_to_message_id": int(message_id), "parse_mode": "HTML"}
		encoded_data = json.dumps(_data).encode('utf-8')

		print(f"sending message {response}")

		r = http.request('POST', 
			url, 
			body = encoded_data, 
			headers = {'Content-Type': 'application/json'}, 
			retries=False)

		http_status = r.status
		print(http_status)

	except Exception as e:
		print(e)

	return {"statusCode": 200}
