import os
import requests
import jwt
from datetime import date, datetime, timezone, timedelta

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
city = os.environ['CITY']

# auto / day / night
mode = os.environ.get("MODE", "auto")

# ================== 中国时区 ==================
CN_TZ = timezone(timedelta(hours=8))

# ====== 和风天气 JWT ======
qweather_host = os.environ["QWEATHER_HOST"]
qweather_kid = os.environ["QWEATHER_KID"]
qweather_private_key = os.environ["QWEATHER_PRIVATE_KEY"]
qweather_project_id = os.environ["QWEATHER_PROJECT_ID"]

today = datetime.now(CN_TZ)
today_date = today.strftime("%Y年%m月%d日")

_jwt_token = None
_jwt_expire = 0


def generate_jwt():
    global _jwt_token, _jwt_expire
    now = int(datetime.utcnow().timestamp())

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


def qweather_get(path, params):
    token = generate_jwt()
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{qweather_host}{path}"

    resp = requests.get(url, params=params, headers=headers, timeout=10)
    if resp.status_code != 200:
        raise Exception(f"QWeather API error: {resp.text}")

    return resp.json()


# ================== 城市ID ==================
params = {"location": city}
resp_json = qweather_get("/geo/v2/city/lookup", params)
city_id = resp_json["location"][0]["id"]
params["location"] = city_id


# ================== 天气 ==================
realtime_json = qweather_get("/v7/weather/now", params)
now_temperature = realtime_json["now"]["temp"] + "摄氏度"

day_forecast_json = qweather_get("/v7/weather/3d", params)
today_data = day_forecast_json["daily"][0]
tomorrow_data = day_forecast_json["daily"][1]


def pack(data):
    return {
        "weather": data["textDay"],
        "min": data["tempMin"] + "摄氏度",
        "max": data["tempMax"] + "摄氏度",
        "sunrise": data["sunrise"],
        "sunset": data["sunset"],
        "night": data["textNight"],
        "wind_day": data["windDirDay"],
        "wind_night": data["windDirNight"],
        "wind_scale": data["windScaleDay"],
    }


today_pack = pack(today_data)
tomorrow_pack = pack(tomorrow_data)


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
    start = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=CN_TZ)
    delta = today - start
    return delta.days + 1


def get_birthday():
    next_birthday = datetime.strptime(
        str(date.today().year) + "-" + birthday,
        "%Y-%m-%d"
    ).replace(tzinfo=CN_TZ)

    if next_birthday < today:
        next_birthday = next_birthday.replace(year=next_birthday.year + 1)

    return (next_birthday - today).days


def get_words():
    try:
        words = requests.get("https://api.shadiao.pro/chp", timeout=5)
        text = words.json()['data']['text']
    except:
        text = "今天也要开心哦~"

    return [(text[i:i + 20]) for i in range(0, 100, 20)]


# ================== 主流程 ==================
if __name__ == '__main__':
    client = WeChatClient(app_id, app_secret)
    wm = WeChatMessage(client)

    note1, note2, note3, note4, note5 = get_words()

    # ================== 时区安全时间 ==================
    now_time = datetime.now(CN_TZ).time()

    sunrise_time = datetime.strptime(today_pack["sunrise"], "%H:%M").time()
    sunset_time = datetime.strptime(today_pack["sunset"], "%H:%M").time()

    # ================== 模式判断 ==================
    if mode == "day":
        mode_auto = "day"
    elif mode == "night":
        mode_auto = "night"
    else:
        # auto mode
        if sunrise_time <= now_time <= sunset_time:
            mode_auto = "day"
        else:
            mode_auto = "night"

    print(f"[MODE] input={mode} -> resolved={mode_auto}")

    # ================== 数据选择 ==================
    if mode_auto == "night":
        data_src = tomorrow_pack
        template_id = template_id_night
        label = "明天"
    else:
        data_src = today_pack
        template_id = template_id_day
        label = "今天"

    print(f"[SEND] {label}")

    # ================== 模板数据 ==================
    data = {
        "today": {"value": today_date},
        "city": {"value": city},
        "weather": {"value": data_src["weather"]},
        "now_temperature": {"value": now_temperature},
        "min_temperature": {"value": data_src["min"]},
        "max_temperature": {"value": data_src["max"]},
        "love_date": {"value": f"{get_count()}天"},
        "birthday": {"value": f"{get_birthday()}天"},
        "diff_date1": {"value": f"{days_until_spring_festival()}天"},
        "sunrise": {"value": data_src["sunrise"]},
        "sunset": {"value": data_src["sunset"]},
        "textNight": {"value": data_src["night"]},
        "windDirDay": {"value": data_src["wind_day"]},
        "windDirNight": {"value": data_src["wind_night"]},
        "windScaleDay": {"value": data_src["wind_scale"]},
        "note1": {"value": note1},
        "note2": {"value": note2},
        "note3": {"value": note3},
        "note4": {"value": note4},
        "note5": {"value": note5}
    }

    # ================== 发送 ==================
    for u in user_ids.split(";"):
        res = wm.send_template(u, template_id, data)
        print(res)
