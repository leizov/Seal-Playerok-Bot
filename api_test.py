from playerokapi.account import Account
import datetime

token = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxZWZiZWQ2Mi0xZjMzLTYzNDAtMWMxZS04ZWE5MDI5ZTc4OTIiLCJpZGVudGl0eSI6IjFlZmJlZDYyLTFmM2EtNjg3MC1iMWQ4LWYyOGZhZDQ4NTQzOCIsInJvbGUiOiJVU0VSIiwidiI6MSwiaWF0IjoxNzYyNDQ5NDcxLCJleHAiOjE3OTM5ODU0NzF9.C0doaV93BCwl3Nw_zhzw6j5ZB9pADgQjzfW8ixphxCc'
user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
proxy = 'KSbmS3e4:PXHYZPbB@91.221.39.249:63880'
auid = '1f0bb33c-b3c2-6c90-959d-39fb83787adb'

# input_token = input('Введите токен: ')
# input_user_agent = input('Введите user-agent: ')
# input_proxy = input('Введите прокси: ')

print('Создаю экземпляр аккаунта')
account = Account(token=token, user_agent=user_agent, proxy=proxy)

print('Кидаю запрос....')
print(datetime.datetime.now())
account_obj = account.get()
print(datetime.datetime.now())
print('Получил ответ!')

print(f'Наш плейрок аккаунт: {account_obj.username}\nЧаты: {account_obj.get_chats().chats}')