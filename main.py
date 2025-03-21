import os
import json
import time
import requests
import websocket
import ssl
from dotenv import load_dotenv
from collections import defaultdict
import threading

# .env에서 APP_KEY, APP_SECRET 불러오기
load_dotenv()
LS_APP_KEY = os.getenv("LS_APP_KEY")
LS_SECRET_KEY = os.getenv("LS_SECRET_KEY")

# WebSocket URL
WS_URL = "wss://openapi.ls-sec.co.kr:9443/websocket"

# VI 상태 설명 맵
VI_STATUS_MAP = {
    "0": "🔓 VI 해제",
    "1": "🔒 정적 VI 발동",
    "2": "🔒 동적 VI 발동",
    "3": "🔒 정적+동적 VI 동시 발동"
}

# VI 발동 종목 저장용 딕셔너리
vi_active_stocks = defaultdict(dict)

# print(LS_APP_KEY, LS_SECRET_KEY)
# Access Token 발급 함수
def get_access_token():
    url = "https://openapi.ls-sec.co.kr:8080/oauth2/token"

    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }

    params = {
        "grant_type": "client_credentials",
        "appkey":  LS_APP_KEY,
        "appsecretkey": LS_SECRET_KEY,
        "scope": "oob"  # LS증권 API scope 추가
    }

    response = requests.post(url, headers=headers, data=params)

    if response.status_code == 200:
        token = response.json().get("access_token")
        print("✅ Access Token 발급 완료")
        return token
    else:
        print("❌ Access Token 발급 실패:", response.text)
        return None

def create_mock_vi_data():
    """가상의 VI 발동 데이터 생성"""
    mock_data = {
        "header": {
            "tr_cd": "VI_",
            "rsp_cd": "00000",
            "rsp_msg": "정상처리"
        },
        "body": {
            "ref_shcode": "005930",  # 삼성전자
            "vi_gubun": "1",         # 정적 VI 발동
            "vi_trgprice": "70000",  # VI 발동가
            "time": "090000",        # 발동시간
            "exchname": "KRX",       # 거래소
            "svi_recprice": "70000", # 정적VI 기준가
            "dvi_recprice": "0"      # 동적VI 기준가
        }
    }
    return mock_data

def cancel_subscription(ws, code, exch_name, reason=""):
    """구독 해지 함수"""
    # 거래소에 따른 체결가 코드 설정
    tr_cd = "S3_" if exch_name == "KRX" else "K3_"  # KRX는 S3_, KOSDAQ은 K3_
    
    cancel_req = {
        "header": {
            "token": ws.access_token,
            "tr_type": "4",  # 실시간 시세 해제
        },
        "body": {
            "tr_cd": tr_cd,   # 실시간 체결가 코드
            "tr_key": code    # 종목코드
        }
    }
    ws.send(json.dumps(cancel_req))
    print(f"⏰ {code} 종목 실시간 체결가 감시 해제 ({reason})")

def register_stock_ccld(ws, code, exch_name):
    """특정 종목의 실시간 체결가 감시 등록"""
    # 거래소에 따른 체결가 코드 설정
    tr_cd = "S3_" if exch_name == "KRX" else "K3_"  # KRX는 S3_, KOSDAQ은 K3_
    
    price_req = {
        "header": {
            "token": ws.access_token,
            "tr_type": "3",  # 실시간 시세 등록
        },
        "body": {
            "tr_cd": tr_cd,   # 실시간 체결가 코드
            "tr_key": code    # 종목코드
        }
    }
    ws.send(json.dumps(price_req))
    print(f"✅ {code} 종목 실시간 체결가 감시 등록 완료 (거래소: {exch_name})")

def create_mock_price_data():
    """가상의 체결가 데이터 생성"""
    mock_data = {
        "header": {
            "tr_cd": "S3_",
            "tr_key": "005930"
        },
        "body": {
            "price": "69500",      # 현재가
            "change": "-500",      # 전일대비
            "drate": "-0.71",      # 등락률
            "volume": "1000",      # 거래량
            "value": "69500000",   # 거래대금
            "bidho": "69400",      # 매수호가
            "offerho": "69600",    # 매도호가
            "chetime": "090001",   # 체결시간
            "exchname": "KRX"      # 거래소
        }
    }
    return mock_data

def on_open(ws):
    print("[WebSocket 연결됨] 전체 종목 VI 감시 시작...")

    # VI 감시 요청
    vi_req = {
        "header": {
            "token": ws.access_token,
            "tr_type": "3",  # 실시간 시세 등록
        },
        "body": {
            "tr_cd": "VI_",   # VI 실시간 코드
            "tr_key": "000000"  # 전체 종목 대상
        }
    }
    ws.send(json.dumps(vi_req))
    
    # 가상의 VI 발동 데이터 생성 및 처리
    mock_data = create_mock_vi_data()
    print("\n[테스트] 가상의 VI 발동 데이터 생성")
    on_message(ws, json.dumps(mock_data))

def on_message(ws, message):
    try:
        data = json.loads(message)
        header = data.get("header", {})
        tr_cd = header.get("tr_cd")
        rsp_cd = header.get("rsp_cd")
        rsp_msg = header.get("rsp_msg")
        
        if rsp_cd == "00000":
            print(f"✅ 전종목 VI 요청 성공: {rsp_msg}")
        elif rsp_cd == "00001":  # 구독 해제 성공
            print(f"✅ 구독 해제 성공: {rsp_msg}")

        body = data.get("body")
        if not body:
            return

        # VI 메시지 처리
        if tr_cd == "VI_":
            code = body.get("ref_shcode")
            vi_type = body.get("vi_gubun")
            price = body.get("vi_trgprice")
            time_ = body.get("time")
            exch_name = body.get("exchname")
            svi_price = body.get("svi_recprice")
            dvi_price = body.get("dvi_recprice")

            status = VI_STATUS_MAP.get(vi_type, "❓ 알 수 없음")
            print(f"\n[{status}]")
            print(f"종목코드: {code}")
            print(f"거래소: {exch_name}")
            print(f"VI 발동가: {price}")
            print(f"정적VI 기준가: {svi_price}")
            print(f"동적VI 기준가: {dvi_price}")
            print(f"발동시간: {time_}")
            print("-" * 50)

            # VI 발동 시 실시간 체결가 감시 등록
            if vi_type in ["1", "2", "3"]:  # VI 발동 상태 (1: 정적VI, 2: 동적VI, 3: 정적+동적VI)
                vi_active_stocks[code] = {
                    "vi_type": vi_type,
                    "vi_price": price,
                    "time": time_,
                    "exch_name": exch_name  # 거래소 정보 저장 (KRX, KOSDAQ)
                }
                register_stock_ccld(ws, code, exch_name)
                    
            elif vi_type == "0":  # VI 해제
                if code in vi_active_stocks:
                    # VI 해제 시 1분 후 구독 해지 예약
                    def delayed_cancel():
                        time.sleep(60)  # 1분 대기
                        if code not in vi_active_stocks:  # 여전히 VI 해제 상태인 경우에만
                            cancel_subscription(ws, code, exch_name, "VI 해제 후 1분 경과")
                    
                    # 백그라운드에서 구독 해지 실행
                    thread = threading.Thread(target=delayed_cancel)
                    thread.daemon = True
                    thread.start()
                    
                    # print(f"❌ {code} 종목 VI 해제 (1분 후 구독 해지 예약)")
                    del vi_active_stocks[code]

        # 실시간 체결가 메시지 처리
        elif tr_cd in ["S3_", "K3_"]:  # 코스피(S3_) 또는 코스닥(K3_) 체결가
            code = header.get("tr_key")
            if code in vi_active_stocks:
                # 기본 정보
                current_price = body.get("price")  # 현재가
                change = body.get("change")  # 전일대비
                drate = body.get("drate")  # 등락률
                volume = body.get("volume")  # 거래량
                value = body.get("value")  # 거래대금
                
                # 호가 정보
                bidho = body.get("bidho")  # 매수호가
                offerho = body.get("offerho")  # 매도호가
                
                # 시간 정보
                chetime = body.get("chetime")  # 체결시간
                
                # VI 정보
                vi_info = vi_active_stocks[code]
                vi_type = vi_info["vi_type"]
                vi_price = vi_info["vi_price"]
                exch_name = vi_info["exch_name"]
                
                print(f"\n[실시간 체결가] {code} ({exch_name})")
                print(f"체결시간: {chetime}")
                print(f"현재가: {current_price} ({change} / {drate}%)")
                print(f"매수호가: {bidho} | 매도호가: {offerho}")
                print(f"거래량: {volume} | 거래대금: {value}")
                print(f"VI 발동가: {vi_price}")
                print(f"VI 상태: {VI_STATUS_MAP.get(vi_type)}")
                print("-" * 30)

    except Exception as e:
        print(f"[에러] 메시지 파싱 실패: {e}")

def on_error(ws, error):
    print(f"[WebSocket 오류] {error}")
    if "Connection refused" in str(error):
        print("서버 연결이 거부되었습니다. 5초 후 재연결을 시도합니다...")
        time.sleep(5)
        ws.run_forever()

def on_close(ws, *args):
    print("[WebSocket 연결 종료됨]")
    print("5초 후 재연결을 시도합니다...")
    time.sleep(5)
    ws.run_forever()

# WebSocket 실행
def run_vi_monitor(access_token):
    try:
        while True:
            try:
                websocket.enableTrace(False)
                ws = websocket.WebSocket()
                
                # SSL 컨텍스트 설정
                ws._ssl_context = ssl.create_default_context()
                ws._ssl_context.check_hostname = False
                ws._ssl_context.verify_mode = ssl.CERT_NONE
                
                # WebSocket 연결
                ws.connect(WS_URL)
                
                # 토큰을 WebSocket 객체에 임시로 바인딩
                ws.access_token = access_token
                
                # VI 감시 요청
                vi_req = {
                    "header": {
                        "token": access_token,
                        "tr_type": "3",  # 실시간 시세 등록
                    },
                    "body": {
                        "tr_cd": "VI_",   # VI 실시간 코드
                        "tr_key": "000000"  # 전체 종목 대상
                    }
                }
                ws.send(json.dumps(vi_req))
                
                # # 가상의 VI 발동 데이터 생성 및 처리 (테스트용)
                # mock_data = create_mock_vi_data()
                # print("\n[테스트] 가상의 VI 발동 데이터 생성")
                # on_message(ws, json.dumps(mock_data))
                
                # 메시지 수신 루프
                while True:
                    try:
                        message = ws.recv()
                        on_message(ws, message)
                    except websocket.WebSocketConnectionClosedException:
                        print("WebSocket 연결이 종료되었습니다. 재연결을 시도합니다...")
                        break
                    except Exception as e:
                        print(f"메시지 수신 중 오류 발생: {e}")
                        break
                        
            except Exception as e:
                print(f"예상치 못한 오류 발생: {e}")
                print("5초 후 재시작을 시도합니다...")
                time.sleep(5)
                
    except KeyboardInterrupt:
        print("\n\n프로그램을 종료합니다...")
        if 'ws' in locals():
            ws.close()
        print("프로그램이 종료되었습니다.")
        exit(0)

# 메인 실행 흐름
def main():
    try:
        access_token = get_access_token()
        if access_token:
            run_vi_monitor(access_token)
        else:
            print("⛔ 프로그램 종료: Access Token 없음")
    except KeyboardInterrupt:
        print("\n\n프로그램을 종료합니다...")
        print("프로그램이 종료되었습니다.")
        exit(0)

if __name__ == "__main__":
    main()
