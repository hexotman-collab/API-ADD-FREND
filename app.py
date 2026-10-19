from flask import Flask, render_template, request, jsonify, send_file
import requests
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

app = Flask(__name__)

# ===== تم إزالة U و P من هنا =====
servers = {"ME": "https://clientbp.ggpolarbear.com/"}

try:
    from google_play_scraper import app as gp_app
    HAS_GP = True
except Exception:
    HAS_GP = False

def buildpacket(fd):
    pk = bytearray()
    for f, v in fd.items():
        n = (f << 3)
        buf = []
        while True:
            b = n & 0x7F
            n >>= 7
            if n:
                b |= 0x80
            buf.append(b)
            if not n:
                break
        pk.extend(bytes(buf))
        if isinstance(v, int):
            buf = []
            while True:
                b = v & 0x7F
                v >>= 7
                if v:
                    b |= 0x80
                buf.append(b)
                if not v:
                    break
            pk.extend(bytes(buf))
    return pk

@app.route('/')
def index():
    return send_file('index.html')

@app.route('/api/execute', methods=['POST'])
def execute():
    data = request.json
    server = data.get('server', 'ME').upper()
    action = data.get('action', 'add')
    target_id = data.get('target_id', '').strip()
    
    # ===== استقبال بيانات الحساب من المستخدم =====
    user_uid = data.get('user_uid', '').strip()
    user_pass = data.get('user_pass', '').strip()

    logs = []

    def log(msg, color="white"):
        logs.append({"text": msg, "color": color})

    # ===== التحقق من البيانات =====
    if not target_id:
        log("خطأ: أدخل معرّف الهدف", "red")
        return jsonify({"logs": logs, "success": False})
        
    if not user_uid or not user_pass:
        log("خطأ: يجب إدخال UID والباسورد الخاص بك أولاً", "red")
        return jsonify({"logs": logs, "success": False})

    base = servers.get(server)
    if not base:
        log("خطأ: سيرفر غير صالح", "red")
        return jsonify({"logs": logs, "success": False})

    url = f"{base}{'RequestAddingFriend' if action == 'add' else 'RemoveFriend'}"

    # ===== جلب الإصدار =====
    log("جاري جلب الإصدار...", "blue")
    obb = "1.0.0"
    try:
        r = requests.get(
            "https://version.ffmax.purplevioleto.com/live/ver.php?lang=ar&device=android",
            timeout=10
        )
        obb = r.json().get('latest_release_version', obb)
    except Exception as e:
        log(f"تحذير الإصدار: {e}", "orange")

    version = "غير معروف"
    if HAS_GP:
        try:
            version = gp_app('com.dts.freefireth')['version']
        except Exception as e:
            log(f"تحذير Play: {e}", "orange")

    log(f"OBB: {obb}")
    log(f"Version: {version}")

    # ===== جلب JWT باستخدام بيانات المستخدم =====
    log("جاري جلب JWT...", "blue")
    try:
        j = requests.get(
            f"https://ff-jwt-gen-api.lovable.app/api/public/token?uid={user_uid}&password={user_pass}",
            timeout=15
        ).json()
        
        # التحقق من وجود توكن في الرد
        if 'token' not in j:
            log(f"فشل جلب التوكن. تأكد من صحة UID والباسورد.", "red")
            return jsonify({"logs": logs, "success": False})
            
        jwt = j['token']
        acc = j['account_id']
    except Exception as e:
        log(f"خطأ JWT: {e}", "red")
        return jsonify({"logs": logs, "success": False})

    log(f"UID: {acc}")
    log("JWT (كامل):", "blue")
    log(jwt, "white")

    # ===== التشفير والإرسال =====
    try:
        payload = buildpacket({1: int(acc), 2: int(target_id), 3: 22}).hex()
        key = bytes([89, 103, 38, 116, 99, 37, 68, 69, 117, 104, 54, 37, 90, 99, 94, 56])
        iv = bytes([54, 111, 121, 90, 68, 114, 50, 50, 69, 51, 121, 99, 104, 106, 77, 37])
        enc = AES.new(key, AES.MODE_CBC, iv).encrypt(pad(bytes.fromhex(payload), 16))

        hr = {
            "Accept": "*/*",
            "Accept-Encoding": "deflate, gzip",
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Bearer {jwt}",
            "ReleaseVersion": obb,
            "User-Agent": "UnityPlayer/2018.4.12f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)",
            "X-GA": "v1 1",
            "X-Unity-Version": "2018.4.12f1",
            "Content-Length": str(len(enc))
        }

        log("جاري إرسال الطلب...", "blue")
        rQ = requests.post(url, headers=hr, data=enc, timeout=20)

        if rQ.status_code == 200:
            log(f"تم بنجاح ✔ status: {rQ.status_code}", "green")
            return jsonify({"logs": logs, "success": True})
        else:
            log(f"الحالة: {rQ.status_code}", "orange")
            log(f"الرد: {rQ.text[:300]}", "white")
            
            if "BR_FRIEND_NOT_SAME_REGION" in rQ.text:
                log("ملاحظة: اللاعب في منطقة/سيرفر مختلف!", "orange")
            
            return jsonify({"logs": logs, "success": False})

    except Exception as e:
        log(f"خطأ خطير: {e}", "red")
        return jsonify({"logs": logs, "success": False})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)