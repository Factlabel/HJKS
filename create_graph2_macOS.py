import json
import sys
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox, QDateEdit, QFileDialog, QMessageBox
from PyQt5.QtCore import Qt, QDate
import matplotlib.pyplot as plt
import pandas as pd
from datetime import datetime
import numpy as np
import os
import mplcursors

# path.jsonからhjks_data_pathを取得
def get_latest_json_file():
    with open('path.json', 'r', encoding='utf-8') as path_file:
        paths = json.load(path_file)

    hjks_data_path = paths.get('hjks_data_path')

    if not hjks_data_path:
        raise ValueError("hjks_data_pathがpath.jsonに存在しません。")

    # ディレクトリ内の最新のoutages_data_yyyymmdd.jsonファイルを探す
    json_files = [f for f in os.listdir(hjks_data_path) if f.startswith('outages_data_') and f.endswith('.json')]

    if not json_files:
        raise FileNotFoundError(f"{hjks_data_path}にoutages_data_yyyymmdd.jsonファイルが見つかりません。")

    latest_file = max(json_files, key=lambda f: os.path.getmtime(os.path.join(hjks_data_path, f)))
    latest_file_path = os.path.join(hjks_data_path, latest_file)

    return latest_file_path


# JSONファイルからデータを読み込みます
def load_data(file_name):
    with open(file_name, 'r', encoding='utf-8') as file:
        data = json.load(file)
    if isinstance(data, dict):
        data = data.get('records', [])  # 'records' はリストが格納されているキー名

    # 全データをチェックし、restartschdtがない場合はデフォルト値を設定
    for entry in data:
        if 'restartschdt' not in entry:
            entry['restartschdt'] = "2100/01/01"

    return data


# フィルタリングを行う関数
def filter_data(data, areas, formats, start_date, end_date):
    filtered_data = []
    for entry in data:
        if (entry['area'] in areas or 'すべて' in areas) and (entry['format'] in formats or 'すべて' in formats):
            entry_start_date = datetime.strptime(entry['startdt'], "%Y/%m/%d %H:%M").date()
            entry_end_date = datetime.strptime(entry.get('restartschdt', "2100/01/01"), "%Y/%m/%d").date()
            if entry_start_date <= end_date and entry_end_date >= start_date:
                filtered_data.append(entry)
    return filtered_data


# RGBA色を指定する関数
def rgba_color(color, alpha=1.0):
    return (*color[:3], alpha)


# マウスオーバーレイの設定を変更した部分
def plot_data(filtered_data, start_date, end_date, color_dict, alpha=1.0):
    if not filtered_data:
        QMessageBox.warning(None, "データ無し", "対象データ無し")
        return

    # downcapacityが存在しない場合の処理
    for entry in filtered_data:
        if 'downcapacity' not in entry:
            entry['downcapacity'] = entry.get('maxcapacity', 0)

    df = pd.DataFrame(filtered_data)
    df['Down Capacity'] = df['downcapacity'].str.replace(',', '').astype(int)
    df['Start Time'] = pd.to_datetime(df['startdt'])
    df['End Time'] = pd.to_datetime(df['restartschdt'].fillna("2100/01/01"))

    # 発電種別のラベルを英語に変換
    translation_dict = {
        "その他": "Other",
        "太陽光・太陽熱": "Solar",
        "風力": "Wind",
        "地熱": "Geothermal",
        "火力（石油）": "Thermal (Oil)",
        "火力（ガス）": "Thermal (Gas)",
        "火力（石炭）": "Thermal (Coal)",
        "水力": "Hydro",
        "原子力": "Nuclear"
    }
    df['format'] = df['format'].map(translation_dict)

    # 積み上げ順序を定義
    stacking_order = [
        "Nuclear", "Hydro", "Thermal (Coal)", "Thermal (Gas)",
        "Thermal (Oil)", "Geothermal", "Wind", "Solar", "Other"
    ]

    # 時間ごとのデータを作成
    time_index = pd.date_range(start=start_date, end=end_date, freq='h')
    summary_df = pd.DataFrame(index=time_index)

    for fmt in stacking_order:
        if fmt in df['format'].unique():
            temp_df = df[df['format'] == fmt]
            temp_series = pd.Series(0, index=summary_df.index)

            for _, row in temp_df.iterrows():
                mask = (temp_series.index >= row['Start Time']) & (temp_series.index < row['End Time'])
                temp_series[mask] += row['Down Capacity']

            summary_df[fmt] = temp_series

    summary_df.fillna(0, inplace=True)

    # 実際に存在するカテゴリのみにフィルタリング
    available_formats = [fmt for fmt in stacking_order if fmt in summary_df.columns]

    # グラフを描画
    fig, ax = plt.subplots(figsize=(15, 7))

    # 積み上げ順序に従ってプロット
    summary_df[available_formats].plot(kind='bar', stacked=True, ax=ax, width=1,
                                       color=[rgba_color(color_dict[fmt], alpha) for fmt in available_formats])

    # X軸のラベルを10等分した間隔で表示
    num_labels = 10
    step = max(1, len(time_index) // num_labels)
    labels = time_index[::step].strftime('%Y-%m-%d %H:%M')
    ax.set_xticks(np.arange(0, len(time_index), step))
    ax.set_xticklabels(labels, rotation=45, ha='right')

    # 凡例の順序を逆順にする
    handles, labels = ax.get_legend_handles_labels()
    ax.legend(handles[::-1], labels[::-1], loc='best')

    # グラフのフォントを英語に変更
    plt.rcParams['font.family'] = 'DejaVu Sans'

    plt.xlabel('Date')
    plt.ylabel('Down Capacity (kW)')
    plt.title('Down Capacity Over Time (Stacked)')

    # マウスオーバーレイの設定
    cursor = mplcursors.cursor(ax, hover=True)

    @cursor.connect("add")
    def on_add(sel):
        x = sel.target[0]
        y = sel.target[1]
        date_str = pd.to_datetime(time_index[int(x)]).strftime('%Y/%m/%d/%H:%M')
        y_formatted = f"{y / 1000:,.2f}"  # 桁区切りのカンマを追加
        sel.annotation.set(text=f"Date: {date_str}\nDown Capacity: {y_formatted} MW")

    plt.tight_layout()
    plt.show()

# 「すべて」チェックボックスを処理する関数
def toggle_select_all(checkboxes, state):
    for checkbox in checkboxes:
        checkbox.setChecked(state)


# UIを作成します
class MainWindow(QWidget):
    def __init__(self, data):
        super().__init__()
        self.data = data
        self.initUI()

    def initUI(self):
        self.setWindowTitle("停止情報集計ツール")
        self.setGeometry(100, 100, 800, 400)  # ウィンドウの縦幅を短く設定

        layout = QVBoxLayout()

        # エリアと発電形式のリストを定義
        areas = ["北海道", "東北", "東京", "中部", "北陸", "関西", "中国", "四国", "九州"]
        formats = ["原子力", "水力", "火力（石炭）", "火力（ガス）", "火力（石油）", "地熱", "風力", "太陽光・太陽熱", "その他"]

        # エリアのチェックボタンを横並びに作成
        area_label = QLabel("エリア選択")
        layout.addWidget(area_label)

        area_layout = QHBoxLayout()
        self.area_checkboxes = []
        select_all_area_checkbox = QCheckBox("すべて")
        select_all_area_checkbox.stateChanged.connect(lambda state: toggle_select_all(self.area_checkboxes, state == Qt.Checked))
        area_layout.addWidget(select_all_area_checkbox)

        for area in areas:
            checkbox = QCheckBox(area)
            checkbox.setChecked(True)
            self.area_checkboxes.append(checkbox)
            area_layout.addWidget(checkbox)

        layout.addLayout(area_layout)

        # 発電形式のチェックボタンを横並びに作成
        format_label = QLabel("発電形式選択")
        layout.addWidget(format_label)

        format_layout = QHBoxLayout()
        self.format_checkboxes = []
        select_all_format_checkbox = QCheckBox("すべて")
        select_all_format_checkbox.stateChanged.connect(lambda state: toggle_select_all(self.format_checkboxes, state == Qt.Checked))
        format_layout.addWidget(select_all_format_checkbox)

        for fmt in formats:
            checkbox = QCheckBox(fmt)
            checkbox.setChecked(True)
            self.format_checkboxes.append(checkbox)
            format_layout.addWidget(checkbox)

        layout.addLayout(format_layout)

        # 日付選択
        date_layout = QHBoxLayout()
        start_date_label = QLabel("開始日")
        date_layout.addWidget(start_date_label)
        self.start_date_entry = QDateEdit(calendarPopup=True)
        self.start_date_entry.setDate(QDate.currentDate().addDays(-7))
        date_layout.addWidget(self.start_date_entry)

        end_date_label = QLabel("終了日")
        date_layout.addWidget(end_date_label)
        self.end_date_entry = QDateEdit(calendarPopup=True)
        self.end_date_entry.setDate(QDate.currentDate())
        date_layout.addWidget(self.end_date_entry)

        layout.addLayout(date_layout)

        # 比較日ファイル選択ボタン
        compare_file_button = QPushButton("比較日ファイル選択")
        compare_file_button.clicked.connect(self.select_compare_file)
        layout.addWidget(compare_file_button)

        # 集計ボタン
        submit_button = QPushButton("集計")
        submit_button.clicked.connect(self.on_submit)
        layout.addWidget(submit_button)

        self.setLayout(layout)
        self.compare_file = None

    def select_compare_file(self):
        options = QFileDialog.Options()
        self.compare_file, _ = QFileDialog.getOpenFileName(self, "比較日ファイル選択", "", "JSON Files (*.json);;All Files (*)", options=options)

    def on_submit(self):
        try:
            selected_areas = [checkbox.text() for checkbox in self.area_checkboxes if checkbox.isChecked() and checkbox.text() != 'すべて']
            selected_formats = [checkbox.text() for checkbox in self.format_checkboxes if checkbox.isChecked() and checkbox.text() != 'すべて']
            start_date = self.start_date_entry.date().toPyDate()
            end_date = self.end_date_entry.date().toPyDate()

            # 最新データのフィルタリングと描画
            filtered_data = filter_data(self.data, selected_areas, selected_formats, start_date, end_date)
            plot_data(filtered_data, start_date, end_date, color_dict={
                "Nuclear": (0.29, 0.29, 0.29),
                "Hydro": (0.48, 0.68, 0.9),
                "Thermal (Coal)": (0.91, 0.48, 0.46),
                "Thermal (Gas)": (0.95, 0.68, 0.46),
                "Thermal (Oil)": (0.91, 0.48, 0.29),
                "Geothermal": (0.43, 0.44, 0.9),
                "Wind": (0.72, 0.9, 0.54),
                "Solar": (0.35, 0.65, 0.65),
                "Other": (0.9, 0.82, 0.46)
            })

            # 比較日データのフィルタリングと描画
            if self.compare_file:
                compare_data = load_data(self.compare_file)
                filtered_compare_data = filter_data(compare_data, selected_areas, selected_formats, start_date, end_date)
                plot_data(filtered_compare_data, start_date, end_date, color_dict={
                    "Nuclear": (0.29, 0.29, 0.29),
                    "Hydro": (0.48, 0.68, 0.9),
                    "Thermal (Coal)": (0.91, 0.48, 0.46),
                    "Thermal (Gas)": (0.95, 0.68, 0.46),
                    "Thermal (Oil)": (0.91, 0.48, 0.29),
                    "Geothermal": (0.43, 0.44, 0.9),
                    "Wind": (0.72, 0.9, 0.54),
                    "Solar": (0.35, 0.65, 0.65),
                    "Other": (0.9, 0.82, 0.46)
                }, alpha=0.3)
        except ValueError as e:
            QMessageBox.critical(None, "日付エラー", str(e))

# メイン関数
def main():
    # 最新のJSONファイルを取得
    data_file = get_latest_json_file()

    # データを読み込む
    data = load_data(data_file)

    app = QApplication(sys.argv)
    main_window = MainWindow(data)
    main_window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
