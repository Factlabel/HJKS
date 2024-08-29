import json
import tkinter as tk
from tkinter import ttk
from tkcalendar import DateEntry
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import pandas as pd
from datetime import datetime, timedelta
import numpy as np


# JSONファイルからデータを読み込みます
def load_data(file_name):
    with open(file_name, 'r', encoding='utf-8') as file:
        data = json.load(file)
    if isinstance(data, dict):
        data = data.get('records', [])  # 'records' はリストが格納されているキー名
    return data


# データをフィルタリングします
def filter_data(data, areas, formats, start_date, end_date):
    filtered_data = []
    for entry in data:
        if (entry['area'] in areas or 'すべて' in areas) and (entry['format'] in formats or 'すべて' in formats):
            entry_start_date = datetime.strptime(entry['startdt'], "%Y/%m/%d %H:%M")
            entry_end_date = datetime.strptime(entry.get('restartschdt', "2100/01/01"), "%Y/%m/%d")
            if start_date <= entry_start_date <= end_date or start_date <= entry_end_date <= end_date:
                filtered_data.append(entry)
    return filtered_data


# 棒グラフを作成します
def plot_data(filtered_data, start_date, end_date):
    if not filtered_data:
        print("該当するデータがありません。")
        return

    # downcapacityが存在しない場合の処理
    for entry in filtered_data:
        if 'downcapacity' not in entry:
            entry['downcapacity'] = entry.get('maxcapacity', 0)

    df = pd.DataFrame(filtered_data)
    df['停止量'] = df['downcapacity'].str.replace(',', '').astype(int)
    df['開始時刻'] = pd.to_datetime(df['startdt'])
    df['終了時刻'] = pd.to_datetime(df['restartschdt'].fillna("2100/01/01"))

    # 時間ごとのデータを作成
    time_index = pd.date_range(start=start_date, end=end_date, freq='h')
    summary_df = pd.DataFrame(index=time_index)

    for fmt in df['format'].unique():
        temp_df = df[df['format'] == fmt]
        temp_series = pd.Series(0, index=summary_df.index)

        for _, row in temp_df.iterrows():
            mask = (temp_series.index >= row['開始時刻']) & (temp_series.index < row['終了時刻'])
            temp_series[mask] += row['停止量']

        summary_df[fmt] = temp_series

    summary_df.fillna(0, inplace=True)

    # グラフを描画
    fig, ax = plt.subplots(figsize=(15, 7))
    summary_df.plot(kind='bar', stacked=True, ax=ax, width=1, cmap='tab20')

    # X軸のラベルを10等分した間隔で表示
    num_labels = 10
    step = max(1, len(time_index) // num_labels)
    labels = time_index[::step].strftime('%Y-%m-%d %H:%M')
    ax.set_xticks(np.arange(0, len(time_index), step))
    ax.set_xticklabels(labels, rotation=45, ha='right')

    # フォントの設定で文字化けを防ぐ
    # macOSでは、システムフォントを使用します
    if plt.get_backend() in ['TkAgg', 'Qt4Agg', 'Qt5Agg', 'MacOSX']:
        plt.rcParams['font.family'] = 'Hiragino Sans'  # macOS標準のヒラギノフォント
    else:
        plt.rcParams['font.family'] = 'DejaVu Sans'

    plt.xlabel('日付')
    plt.ylabel('停止量 (kW)')
    plt.title('時間ごとの停止量（積み上げ）')
    plt.tight_layout()
    plt.show()


# 「すべて」チェックボックスを処理する関数
def toggle_select_all(vars_dict, select_all_var):
    state = select_all_var.get()
    for var in vars_dict.values():
        var.set(state)


# UIを作成します
def create_ui(data):
    root = tk.Tk()
    root.title("停止情報集計ツール")

    # エリアと発電形式のリストを定義
    areas = ["北海道", "東北", "東京", "中部", "北陸", "関西", "中国", "四国", "九州"]
    formats = ["原子力", "水力", "火力（石炭）", "火力（ガス）", "火力（石油）", "地熱", "風力", "太陽光・太陽熱", "その他"]

    # エリアのチェックボタンを作成
    area_frame = ttk.Labelframe(root, text="エリア選択", padding=(10, 10))
    area_frame.pack(fill="x", padx=10, pady=5)
    area_vars = {}
    area_select_all_var = tk.BooleanVar(value=False)
    area_vars['すべて'] = area_select_all_var
    tk.Checkbutton(area_frame, text='すべて', variable=area_select_all_var,
                   command=lambda: toggle_select_all(area_vars, area_select_all_var)).pack(side="left")

    for area in areas:
        var = tk.BooleanVar(value=True)
        area_vars[area] = var
        tk.Checkbutton(area_frame, text=area, variable=var).pack(side="left")

    # 発電形式のチェックボタンを作成
    format_frame = ttk.Labelframe(root, text="発電形式選択", padding=(10, 10))
    format_frame.pack(fill="x", padx=10, pady=5)
    format_vars = {}
    format_select_all_var = tk.BooleanVar(value=False)
    format_vars['すべて'] = format_select_all_var
    tk.Checkbutton(format_frame, text='すべて', variable=format_select_all_var,
                   command=lambda: toggle_select_all(format_vars, format_select_all_var)).pack(side="left")

    for fmt in formats:
        var = tk.BooleanVar(value=True)
        format_vars[fmt] = var
        tk.Checkbutton(format_frame, text=fmt, variable=var).pack(side="left")

    # 日付選択
    date_frame = ttk.Labelframe(root, text="期間選択", padding=(10, 10))
    date_frame.pack(fill="x", padx=10, pady=5)

    tk.Label(date_frame, text="開始日").pack(side="left", padx=5)
    start_date_entry = DateEntry(date_frame, width=12, date_pattern='y/mm/dd',
                                 background='darkblue', foreground='white', borderwidth=2)
    start_date_entry.pack(side="left", padx=5)

    tk.Label(date_frame, text="終了日").pack(side="left", padx=5)
    end_date_entry = DateEntry(date_frame, width=12, date_pattern='y/mm/dd',
                               background='darkblue', foreground='white', borderwidth=2)
    end_date_entry.pack(side="left", padx=5)

    # 集計ボタン
    def on_submit():
        selected_areas = [area for area, var in area_vars.items() if var.get() and area != 'すべて']
        selected_formats = [fmt for fmt, var in format_vars.items() if var.get() and fmt != 'すべて']
        start_date = datetime.strptime(start_date_entry.get(), "%Y/%m/%d")
        end_date = datetime.strptime(end_date_entry.get(), "%Y/%m/%d")
        filtered_data = filter_data(data, selected_areas, selected_formats, start_date, end_date)
        plot_data(filtered_data, start_date, end_date)

    submit_button = tk.Button(root, text="集計", command=on_submit)
    submit_button.pack(pady=10)

    root.mainloop()


# メイン関数
def main():
    data_file = 'outages_data.json'
    data = load_data(data_file)
    create_ui(data)


if __name__ == "__main__":
    main()
