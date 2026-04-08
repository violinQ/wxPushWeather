import json
import os
import requests
import jwt
from datetime import date, datetime, timedelta

from lunardate import LunarDate
from wechatpy import WeChatClient
from wechatpy.client.api import WeChatMessage


# ================== 环境变量 ==================
start_date = os.environ['START_DATE']
birthday = os.environ['BIRTHDAY']
app_id = os.environ["APP_ID"]
app_secret = os.environ["APP_SECRET"]
user_ids = os.environ["USER_IDS"]
template_id_day = os.environ["TEMPLATE_ID_DAY"]
template_id_night = os.environ["TEMPLATE_ID_NIGHT"]
name = os.environ['NAME']
city = os.environ['CITY']

# ====== 和风天气 JWT ======
qweather_host = os.environ["QWEATHER_HOST"]
qweather_kid = os.environ["QWEATHER_KID"]
qweather_private_key = os.environ["QWEATHER_PRIVATE_KEY"]
qweather_project_id = os.environ["QWEATHER_PROJECT_ID"]

# ================== 时间 ==================
today = datetime.now()
today_date = today.strftime("%Y年%m月%d日")


# ================== JWT（带缓存） ==================
_jwt_token = None
_jwt_expire = 0


def generate_jwt():
    global _jwt_token, _jwt_expire

    now = int(datetime.utcnow().timestamp())

    # 提前60秒刷新
    if _jwt_token and now < _jwt_expire - 60:
        return _jwt_token

    payload = {
        "sub": qweather_project_id,
        "iat": now,
        "exp": now + 3600
    }

    headers = {
        "alg": "EdDSA",
        "kid": qweather_kid
    }

    _jwt_token = jwt.encode(
        payload,
        qweather_private_key,
        algorithm="EdDSA",
        headers=headers
    )

    _jwt_expire = payload["exp"]
    return _jwt_token


# ================== 请求封装 ==================
def qweather_get(path, params):
    token = generate_jwt()

    headers = {
        "Authorization": f"Bearer {token}"
    }

    url = f"{qweather_host}{path}"

    resp = requests.get(url, params=params, headers=headers, timeout=10)

    if resp.status_code != 200:
        raise Exception(f"QWeather API error: {resp.text}")

    return resp.json()


# ================== 获取城市ID ==================
params = {"location": city}
resp_json = qweather_get("/v2/city/lookup", params)
city_id = resp_json["location"][0]["id"]

params["location"] = city_id

# ================== 实时天气 ==================
realtime_json = qweather_get("/v7/weather/now", params)
realtime = realtime_json["now"]
now_temperature = realtime["temp"] + "℃" + realtime["text"]

# ================== 3天天气 ==================
day_forecast_json = qweather_get("/v7/weather/3d", params)

# 今日
today_data = day_forecast_json["daily"][0]
day_forecast_today_weather = today_data["textDay"]
day_forecast_today_temperature_min = today_data["tempMin"] + "℃"
day_forecast_today_temperature_max = today_data["tempMax"] + "℃"
day_forecast_today_sunrise = today_data["sunrise"]
day_forecast_today_sunset = today_data["sunset"]
day_forecast_today_night = today_data["textNight"]
day_forecast_today_windDirDay = today_data["windDirDay"]
day_forecast_today_windDirNight = today_data["windDirNight"]
day_forecast_today_windScaleDay = today_data["windScaleDay"]

# 明天
tomorrow_data = day_forecast_json["daily"][1]
day_forecast_tomorrow_weather = tomorrow_data["textDay"]
day_forecast_tomorrow_temperature_min = tomorrow_data["tempMin"] + "℃"
day_forecast_tomorrow_temperature_max = tomorrow_data["tempMax"] + "℃"
day_forecast_tomorrow_sunrise = tomorrow_data["sunrise"]
day_forecast_tomorrow_sunset = tomorrow_data["sunset"]
day_forecast_tomorrow_night = tomorrow_data["textNight"]
day_forecast_tomorrow_windDirDay = tomorrow_data["windDirDay"]
day_forecast_tomorrow_windDirNight = tomorrow_data["windDirNight"]
day_forecast_tomorrow_windScaleDay = tomorrow_data["windScaleDay"]


# ================== 工具函数 ==================
def days_until_spring_festival(year=None):
    if year is None:
        year = datetime.now().year

    spring = LunarDate(year, 1, 1).toSolarDate()
    today_d = datetime.now().date()

    days = (spring - today_d).days
    if days <= 0:
        return days_until_spring_festival(year + 1)
    return days


def get_count():
    delta = today - datetime.strptime(start_date, "%Y-%m-%d")
    return delta.days + 1


def get_birthday():
    next_birthday = datetime.strptime(
        str(date.today().year) + "-" + birthday, "%Y-%m-%d"
    )
    if next_birthday < datetime.now():
        next_birthday = next_birthday.replace(year=next_birthday.year + 1)
    return (next_birthday - today).days


def get_words():
    try:
        words = requests.get("https://api.shadiao.pro/chp", timeout=5)
        if words.status_code != 200:
            raise Exception("bad response")
        text = words.json()['data']['text']
    except:
        text = "今天也要开心哦~"

    chunk_size = 20
    split_notes = [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]
    return (split_notes + [""] * 5)[:5]


# ================== 主流程 ==================
if __name__ == '__main__':
    client = WeChatClient(app_id, app_secret)
    wm = WeChatMessage(client)

    note1, note2, note3, note4, note5 = get_words()

    now_utc = datetime.utcnow()
    beijing_time = now_utc + timedelta(hours=8)
    hour = beijing_time.hour

    strDay = "today"
    if hour > 15:
        strDay = "tomorrow"
        template_id_day = template_id_night

    print("当前时间：", beijing_time, "推送：", strDay)

    data = {
        "name": {"value": name},
        "today": {"value": today_date},
        "city": {"value": city},
        "weather": {"value": globals()[f'day_forecast_{strDay}_weather']},
        "now_temperature": {"value": now_temperature},
        "min_temperature": {"value": globals()[f'day_forecast_{strDay}_temperature_min']},
        "max_temperature": {"value": globals()[f'day_forecast_{strDay}_temperature_max']},
        "love_date": {"value": get_count()},
        "birthday": {"value": get_birthday()},
        "diff_date1": {"value": days_until_spring_festival()},
        "sunrise": {"value": globals()[f'day_forecast_{strDay}_sunrise']},
        "sunset": {"value": globals()[f'day_forecast_{strDay}_sunset']},
        "textNight": {"value": globals()[f'day_forecast_{strDay}_night']},
        "windDirDay": {"value": globals()[f'day_forecast_{strDay}_windDirDay']},
        "windDirNight": {"value": globals()[f'day_forecast_{strDay}_windDirNight']},
        "windScaleDay": {"value": globals()[f'day_forecast_{strDay}_windScaleDay']},
        "note1": {"value": note1},
        "note2": {"value": note2},
        "note3": {"value": note3},
        "note4": {"value": note4},
        "note5": {"value": note5}
    }

    user_ids = user_ids.split(";")
    for u in user_ids:
        res = wm.send_template(u, template_id_day, data)
        print(res)
