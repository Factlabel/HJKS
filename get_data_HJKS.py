import ssl
import requests
import json
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.poolmanager import PoolManager
from datetime import datetime
import os


class SSLAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        context = ssl.create_default_context()
        context.set_ciphers('HIGH:!DH:!aNULL')
        kwargs['ssl_context'] = context
        return super(SSLAdapter, self).init_poolmanager(*args, **kwargs)


def get_csrf_token(session, url):
    # トップページを取得してCSRFトークンを取得する
    response = session.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    csrf_token = soup.find('input', {'name': '_csrf'}).get('value')
    return csrf_token


def getUnitData(limit):
    session = requests.Session()
    session.mount('https://', SSLAdapter())

    # 最初にCSRFトークンを取得
    csrf_url = 'https://hjks.jepx.or.jp/hjks/outages'
    csrf_token = get_csrf_token(session, csrf_url)

    # POSTリクエストのURLとヘッダー
    url = 'https://hjks.jepx.or.jp/hjks/outages_ajax'
    headers = {
        'Accept': 'text/plain, */*; q=0.01',
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept-Language': 'ja',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'Origin': 'https://hjks.jepx.or.jp',
        'Referer': 'https://hjks.jepx.or.jp/hjks/outages',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Safari/605.1.15',
        'X-Requested-With': 'XMLHttpRequest'
    }
    data = {
        'cmd': 'get-records',
        'limit': str(limit),
        'offset': '0',
        'sort[0][field]': 'upddt',
        'sort[0][direction]': 'desc',
        'sort[1][field]': 'plantcd',
        'sort[1][direction]': 'asc',
        'sort[2][field]': 'unitcd',
        'sort[2][direction]': 'asc',
        'sort[3][field]': 'startdt',
        'sort[3][direction]': 'desc',
        '_csrf': csrf_token
    }

    try:
        # POSTリクエストを送信してデータを取得
        response = session.post(url, headers=headers, data=data)
        response.raise_for_status()  # HTTPエラーが発生した場合は例外を発生させる
        return response.json()  # JSONレスポンスを返す
    except requests.exceptions.SSLError as e:
        print(f"SSLエラーが発生しました: {e}")
    except requests.exceptions.RequestException as e:
        print(f"リクエスト中にエラーが発生しました: {e}")
    return None


def main():
    # path.jsonからhjks_data_pathを取得
    with open('path.json', 'r', encoding='utf-8') as path_file:
        paths = json.load(path_file)

    hjks_data_path = paths.get('hjks_data_path')

    if not hjks_data_path:
        raise ValueError("hjks_data_pathがpath.jsonに存在しません。")

    # 最初にlimit=100でリクエストを送り、totalを取得
    initial_data = getUnitData(limit=100)
    if initial_data:
        total_records = initial_data['total']
        print(f"総レコード数: {total_records}")

        # totalの値を使って全データを取得
        all_data = getUnitData(limit=total_records)
        if all_data:
            print("全データが正常に取得されました。")

            # 現在の日付でファイル名を作成
            current_date = datetime.now().strftime('%Y%m%d')
            output_file_name = f'outages_data_{current_date}.json'
            output_file_path = os.path.join(hjks_data_path, output_file_name)

            # データをファイルに保存
            with open(output_file_path, 'w', encoding='utf-8') as f:
                json.dump(all_data, f, ensure_ascii=False, indent=4)
            print(f"データが{output_file_path}に保存されました。")
        else:
            print("全データの取得に失敗しました。")
    else:
        print("最初のデータ取得に失敗しました。")


if __name__ == "__main__":
    main()
